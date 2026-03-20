"""
后端 API 全量自动化测试
使用 unittest.mock 模拟微信 code2session 接口，无需真实小程序环境
"""
import io
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from .models import User, Task, TaskCategory, TaskStatus, Message, CreditDetail


def _mock_wx_response(openid='test_openid_001'):
    """返回模拟的微信接口成功响应"""
    return {'openid': openid, 'session_key': 'fake_session_key'}


class AuthModuleTest(TestCase):
    """认证模块测试"""

    def setUp(self):
        self.client = APIClient()

    # ── 微信登录 ──

    @patch('core.views.requests.get')
    def test_wx_login_new_user(self, mock_get):
        """首次登录自动注册新用户，返回 token"""
        mock_get.return_value.json.return_value = _mock_wx_response('openid_new')

        resp = self.client.post('/api/auth/wx-login/', {'code': 'fake_code'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_new_user'])
        self.assertIn('access', resp.data['token'])
        self.assertEqual(resp.data['user']['gender'], 'SECRET')  # 默认保密

    @patch('core.views.requests.get')
    def test_wx_login_existing_user(self, mock_get):
        """同一 openid 再次登录，返回已有用户（is_new_user=False）"""
        mock_get.return_value.json.return_value = _mock_wx_response('openid_exist')

        self.client.post('/api/auth/wx-login/', {'code': 'c1'})
        resp = self.client.post('/api/auth/wx-login/', {'code': 'c2'})

        self.assertFalse(resp.data['is_new_user'])
        self.assertEqual(User.objects.filter(openid='openid_exist').count(), 1)

    def test_wx_login_missing_code(self):
        """缺少 code 参数，返回 400"""
        resp = self.client.post('/api/auth/wx-login/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core.views.requests.get')
    def test_wx_login_wx_error(self, mock_get):
        """微信接口返回错误码，返回 400"""
        mock_get.return_value.json.return_value = {'errcode': 40029, 'errmsg': 'invalid code'}
        resp = self.client.post('/api/auth/wx-login/', {'code': 'bad_code'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 用户 Profile ──

    def _make_user_and_auth(self, openid='openid_profile'):
        """辅助方法：创建用户并完成 JWT 认证"""
        user = User.objects.create_user(
            username=f'wx_{openid[:8]}',
            password='',
            openid=openid,
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return user

    def test_get_profile(self):
        """获取自己的 profile"""
        user = self._make_user_and_auth()
        resp = self.client.get('/api/auth/profile/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], user.pk)

    def test_update_profile_gender(self):
        """PATCH 更新性别字段"""
        self._make_user_and_auth()
        resp = self.client.patch('/api/auth/profile/', {'gender': 'MALE'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['gender'], 'MALE')

    def test_profile_requires_auth(self):
        """未携带 token 时返回 401"""
        resp = self.client.get('/api/auth/profile/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class TaskModuleTest(TestCase):
    """任务模块测试"""

    def setUp(self):
        self.client = APIClient()
        # publisher 需要足够积分才能展示悬赉任务被接单
        self.publisher = User.objects.create_user(username='publisher', password='pw', credit_score=500)
        self.worker = User.objects.create_user(username='worker', password='pw')
        self._auth(self.publisher)

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create_task(self, **kwargs):
        defaults = {
            'category': TaskCategory.HELP,
            'title': '帮我买饭',
            'content': '详情内容',
            'images': ['http://test.com/a.jpg'],
            'reward_amount': '0.00',  # 默认无悬赏，避免积分不足干扰接单测试
        }
        defaults.update(kwargs)
        resp = self.client.post('/api/tasks/', defaults, format='json')
        return resp

    # ── 发布任务 ──

    def test_create_task(self):
        """成功发布任务，publisher 自动绑定"""
        resp = self._create_task()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=resp.data['id'])
        self.assertEqual(task.publisher, self.publisher)
        self.assertEqual(task.status, TaskStatus.OPEN)

    # ── 任务列表 ──

    def test_list_tasks(self):
        """获取任务列表"""
        self._create_task()
        self._create_task(title='帮我打印', category=TaskCategory.STUDY)
        resp = self.client.get('/api/tasks/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_filter_tasks_by_category(self):
        """按分类筛选任务"""
        self._create_task(category=TaskCategory.HELP)
        self._create_task(category=TaskCategory.STUDY)
        resp = self.client.get('/api/tasks/?category=HELP')
        self.assertEqual(len(resp.data), 1)

    # ── 任务详情 ──

    def test_task_detail(self):
        """获取任务详情，包含完整的 publisher 信息"""
        create_resp = self._create_task()
        resp = self.client.get(f'/api/tasks/{create_resp.data["id"]}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('content', resp.data)  # 详情有 content，列表没有

    # ── 接单 ──

    def test_accept_task(self):
        """接单者成功接单，状态变为 IN_PROGRESS"""
        task_id = self._create_task().data['id']
        self._auth(self.worker)
        resp = self.client.post(f'/api/tasks/{task_id}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        task = Task.objects.get(pk=task_id)
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        self.assertEqual(task.worker, self.worker)

    def test_publisher_cannot_accept_own_task(self):
        """发布者不能接自己的任务"""
        task_id = self._create_task().data['id']
        resp = self.client.post(f'/api/tasks/{task_id}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_accept_non_open_task(self):
        """非 OPEN 状态的任务不可接单"""
        task_id = self._create_task().data['id']
        self._auth(self.worker)
        self.client.post(f'/api/tasks/{task_id}/accept/')  # 第一次接单
        # 再创建另一个用户尝试接同一个任务
        other = User.objects.create_user(username='other', password='pw')
        self._auth(other)
        resp = self.client.post(f'/api/tasks/{task_id}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 完成 ──

    def test_complete_task(self):
        """发布者确认完成，状态变为 COMPLETED"""
        task_id = self._create_task().data['id']
        self._auth(self.worker)
        self.client.post(f'/api/tasks/{task_id}/accept/')
        self._auth(self.publisher)
        resp = self.client.post(f'/api/tasks/{task_id}/complete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Task.objects.get(pk=task_id).status, TaskStatus.COMPLETED)

    def test_worker_cannot_complete_task(self):
        """接单者无法确认完成"""
        task_id = self._create_task().data['id']
        self._auth(self.worker)
        self.client.post(f'/api/tasks/{task_id}/accept/')
        resp = self.client.post(f'/api/tasks/{task_id}/complete/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── 取消 ──

    def test_cancel_task(self):
        """发布者取消任务，状态变为 CANCELLED"""
        task_id = self._create_task().data['id']
        resp = self.client.post(f'/api/tasks/{task_id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Task.objects.get(pk=task_id).status, TaskStatus.CANCELLED)

    def test_cannot_cancel_completed_task(self):
        """已完成的任务无法取消"""
        task_id = self._create_task().data['id']
        self._auth(self.worker)
        self.client.post(f'/api/tasks/{task_id}/accept/')
        self._auth(self.publisher)
        self.client.post(f'/api/tasks/{task_id}/complete/')
        resp = self.client.post(f'/api/tasks/{task_id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class MessageModuleTest(TestCase):
    """消息模块测试"""

    def setUp(self):
        self.client = APIClient()
        self.publisher = User.objects.create_user(username='pub', password='pw')
        self.worker = User.objects.create_user(username='wkr', password='pw')
        self.outsider = User.objects.create_user(username='out', password='pw')

        # 创建进行中的任务
        self.task = Task.objects.create(
            publisher=self.publisher,
            worker=self.worker,
            category=TaskCategory.HELP,
            title='测试任务',
            content='内容',
            status=TaskStatus.IN_PROGRESS,
        )
        self._auth(self.publisher)

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_send_message(self):
        """发布者向接单者发送消息成功"""
        resp = self.client.post(
            f'/api/tasks/{self.task.pk}/messages/',
            {'content_text': '你好，请尽快完成'},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), 1)

    def test_get_messages(self):
        """任务参与者可以获取消息列表"""
        Message.objects.create(
            task=self.task,
            sender=self.publisher,
            receiver=self.worker,
            content_text='你好',
        )
        resp = self.client.get(f'/api/tasks/{self.task.pk}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_outsider_cannot_send_message(self):
        """非参与者无法发送消息，返回 403"""
        self._auth(self.outsider)
        resp = self.client.post(
            f'/api/tasks/{self.task.pk}/messages/',
            {'content_text': '我来插一句'},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_message_rejected(self):
        """空消息内容返回 400"""
        resp = self.client.post(
            f'/api/tasks/{self.task.pk}/messages/',
            {'content_text': '  '},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class CreditModuleTest(TestCase):
    """积分模块测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='u1', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_credit_list_empty(self):
        """新用户积分明细为空列表"""
        resp = self.client.get('/api/credits/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_credit_list_with_records(self):
        """有积分记录时正常返回"""
        CreditDetail.objects.create(user=self.user, change_amount=10, reason='完成任务奖励')
        CreditDetail.objects.create(user=self.user, change_amount=-5, reason='违规扣分')
        resp = self.client.get('/api/credits/')
        self.assertEqual(len(resp.data), 2)

    def test_credit_requires_auth(self):
        """未认证用户无法访问"""
        self.client.credentials()
        resp = self.client.get('/api/credits/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class CreditBonusTest(TestCase):
    """积分奖励机制测试"""

    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # ── 奖励一：新用户注册 ──

    @patch('core.views.requests.get')
    def test_register_bonus_given_to_new_user(self, mock_get):
        """新用户注册后自动获得 50~100 的初始积分"""
        mock_get.return_value.json.return_value = {
            'openid': 'bonus_openid_001', 'session_key': 'sk'
        }
        resp = self.client.post('/api/auth/wx-login/', {'code': 'c1'})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_new_user'])
        bonus = resp.data['register_bonus']
        self.assertIsNotNone(bonus)
        self.assertGreaterEqual(bonus, 50)
        self.assertLessEqual(bonus, 100)

        # 验证数据库中积分分数和明细记录一致
        user = User.objects.get(openid='bonus_openid_001')
        self.assertEqual(user.credit_score, bonus)
        self.assertEqual(CreditDetail.objects.filter(user=user).count(), 1)

    @patch('core.views.requests.get')
    def test_register_bonus_not_given_to_existing_user(self, mock_get):
        """老用户再次登录，register_bonus 为 None，积分不变"""
        mock_get.return_value.json.return_value = {
            'openid': 'bonus_openid_002', 'session_key': 'sk'
        }
        # 第一次登录（注册）
        self.client.post('/api/auth/wx-login/', {'code': 'c1'})
        user_first = User.objects.get(openid='bonus_openid_002')
        score_after_register = user_first.credit_score

        # 第二次登录（已有账号）
        resp = self.client.post('/api/auth/wx-login/', {'code': 'c2'})
        self.assertFalse(resp.data['is_new_user'])
        self.assertIsNone(resp.data['register_bonus'])

        # 积分不应再次增加
        user_first.refresh_from_db()
        self.assertEqual(user_first.credit_score, score_after_register)

    # ── 奖励二：资料完善 ──

    def test_profile_bonus_when_all_fields_filled(self):
        """首次同时填写学号、头像、学院，触发 15 积分奖励"""
        user = User.objects.create_user(username='profuser', password='pw')
        self._auth(user)

        resp = self.client.patch('/api/auth/profile/', {
            'student_id': '20210001',
            'avatar': 'https://example.com/avatar.jpg',
            'college': '计算机学院',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertEqual(user.credit_score, 15)  # CREDIT_PROFILE_COMPLETE = 15
        self.assertTrue(user.profile_reward_given)
        self.assertEqual(CreditDetail.objects.filter(user=user).count(), 1)

    def test_profile_bonus_not_repeated(self):
        """资料完善奖励只发一次，多次 PATCH 不重复发放"""
        user = User.objects.create_user(username='profuser2', password='pw')
        self._auth(user)

        for _ in range(3):
            self.client.patch('/api/auth/profile/', {
                'student_id': '20210002',
                'avatar': 'https://example.com/a.jpg',
                'college': '数学学院',
            })

        user.refresh_from_db()
        self.assertEqual(user.credit_score, 15)  # 只发一次
        self.assertEqual(CreditDetail.objects.filter(user=user).count(), 1)

    def test_profile_bonus_not_given_when_incomplete(self):
        """只填了部分信息（缺少 college），不触发奖励"""
        user = User.objects.create_user(username='profuser3', password='pw')
        self._auth(user)

        self.client.patch('/api/auth/profile/', {
            'student_id': '20210003',
            'avatar': 'https://example.com/a.jpg',
            # 未填 college
        })

        user.refresh_from_db()
        self.assertEqual(user.credit_score, 0)
        self.assertFalse(user.profile_reward_given)

    # ── 奖励三：首次助人 ──

    def _make_completed_task(self, publisher, worker):
        """辅助：创建并完成一个任务，返回 task 对象"""
        task = Task.objects.create(
            publisher=publisher,
            worker=worker,
            category=TaskCategory.HELP,
            title='测试任务',
            content='内容',
            status=TaskStatus.IN_PROGRESS,
        )
        # 以发布者身份调用完成接口
        self._auth(publisher)
        self.client.post(f'/api/tasks/{task.pk}/complete/')
        return task

    def test_first_help_bonus_on_first_completion(self):
        """接单者第一次完成任务，获得 10 积分首次助人奖励"""
        publisher = User.objects.create_user(username='pub_fh', password='pw')
        worker = User.objects.create_user(username='wkr_fh', password='pw')

        self._auth(publisher)
        resp = self.client.post(f'/api/tasks/{self._make_completed_task(publisher, worker).pk}/complete/')

        # 注意：_make_completed_task 内部已调用了 complete，这里重新创建一个单独测
        publisher2 = User.objects.create_user(username='pub_fh2', password='pw')
        worker2 = User.objects.create_user(username='wkr_fh2', password='pw')
        task = Task.objects.create(
            publisher=publisher2,
            worker=worker2,
            category=TaskCategory.HELP,
            title='任务2',
            content='内容2',
            status=TaskStatus.IN_PROGRESS,
        )
        self._auth(publisher2)
        resp = self.client.post(f'/api/tasks/{task.pk}/complete/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['first_help_bonus'])

        worker2.refresh_from_db()
        self.assertEqual(worker2.credit_score, 10)  # CREDIT_FIRST_HELP = 10
        self.assertTrue(worker2.first_help_rewarded)

    def test_first_help_bonus_not_repeated(self):
        """首次助人奖励只发一次，第二次完成任务不再发放"""
        publisher = User.objects.create_user(username='pub_fh3', password='pw')
        publisher2 = User.objects.create_user(username='pub_fh4', password='pw')
        worker = User.objects.create_user(username='wkr_fh3', password='pw')

        # 第一次完成
        task1 = Task.objects.create(
            publisher=publisher,
            worker=worker,
            category=TaskCategory.HELP,
            title='任务1',
            content='内容',
            status=TaskStatus.IN_PROGRESS,
        )
        self._auth(publisher)
        resp1 = self.client.post(f'/api/tasks/{task1.pk}/complete/')
        self.assertTrue(resp1.data['first_help_bonus'])

        # 第二次完成
        task2 = Task.objects.create(
            publisher=publisher2,
            worker=worker,
            category=TaskCategory.HELP,
            title='任务2',
            content='内容',
            status=TaskStatus.IN_PROGRESS,
        )
        self._auth(publisher2)
        resp2 = self.client.post(f'/api/tasks/{task2.pk}/complete/')
        self.assertFalse(resp2.data['first_help_bonus'])

        # 积分只有首次的 10
        worker.refresh_from_db()
        self.assertEqual(worker.credit_score, 10)


class BindPhoneTest(TestCase):
    """手机号绑定测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='phone_user', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    @patch('core.views.requests.get')
    @patch('core.views.requests.post')
    def test_bind_phone_success(self, mock_post, mock_get):
        """mock 微信接口，成功绑定手机号"""
        # mock 获取 access_token
        mock_get.return_value.json.return_value = {'access_token': 'fake_token', 'expires_in': 7200}
        # mock 手机号接口
        mock_post.return_value.json.return_value = {
            'errcode': 0,
            'phone_info': {'phoneNumber': '13800138000', 'purePhoneNumber': '13800138000'},
        }

        resp = self.client.post('/api/auth/bind-phone/', {'code': 'fake_phone_code'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['phone'], '13800138000')

        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '13800138000')

    def test_bind_phone_missing_code(self):
        """缺少 code 返回 400"""
        resp = self.client.post('/api/auth/bind-phone/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core.views.requests.get')
    def test_bind_phone_access_token_fail(self, mock_get):
        """获取 access_token 失败返回 502"""
        # 模拟微信返回错误番号（无 access_token 字段）
        mock_get.return_value.json.return_value = {'errcode': -1, 'errmsg': 'system error'}
        resp = self.client.post('/api/auth/bind-phone/', {'code': 'bad_code'})
        # 获取 access_token 失败应返回 502
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_502_BAD_GATEWAY])


class ImageUploadTest(TestCase):
    """图片上传测试"""

    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username='img_user', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _make_image(self, name='test.jpg', content_type='image/jpeg', size=1024):
        """[辅助] 生成内存测试图片"""
        return SimpleUploadedFile(name, b'\xff\xd8\xff' + b'0' * size, content_type=content_type)

    def test_upload_image_success(self):
        """上传合法 JPEG 图片，返回 URL"""
        img = self._make_image()
        resp = self.client.post('/api/upload/image/', {'image': img}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('url', resp.data)
        self.assertIn('/media/', resp.data['url'])

    def test_upload_image_no_file(self):
        """没有附件返回 400"""
        resp = self.client.post('/api/upload/image/', {}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_image_wrong_type(self):
        """上传非图片文件被拒绝"""
        txt = SimpleUploadedFile('evil.txt', b'hello', content_type='text/plain')
        resp = self.client.post('/api/upload/image/', {'image': txt}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_requires_auth(self):
        """未认证用户无法上传"""
        self.client.credentials()
        img = self._make_image()
        resp = self.client.post('/api/upload/image/', {'image': img}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class TaskQRCodeTest(TestCase):
    """任务二维码测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='qr_user', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.task = Task.objects.create(
            publisher=self.user,
            category=TaskCategory.HELP,
            title='二维码测试任务',
            content='内容',
        )

    def test_qrcode_returns_image(self):
        """返回 PNG 图片， Content-Type 正确"""
        resp = self.client.get(f'/api/tasks/{self.task.pk}/qrcode/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'image/png')
        # PNG 文件头验证
        self.assertTrue(resp.content[:4] == b'\x89PNG')

    def test_qrcode_not_found(self):
        """任务不存在返回 404"""
        resp = self.client.get('/api/tasks/99999/qrcode/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class CreditPaymentTest(TestCase):
    """积分支付测试（接单盈额检查 + 任务完成转账）"""

    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _make_open_task(self, publisher, reward=20):
        return Task.objects.create(
            publisher=publisher,
            category=TaskCategory.HELP,
            title='支付测试任务',
            content='内容',
            status=TaskStatus.OPEN,
            reward_amount=str(reward),
        )

    # ── 接单时盈额检查 ──

    def test_accept_fails_when_publisher_has_insufficient_credits(self):
        """发布者积分不足时，工人无法接单"""
        publisher = User.objects.create_user(username='poor_pub', password='pw', credit_score=10)
        worker = User.objects.create_user(username='rich_wkr', password='pw', credit_score=200)
        task = self._make_open_task(publisher, reward=50)  # 悬赉 50，但发布者只有 10

        self._auth(worker)
        resp = self.client.post(f'/api/tasks/{task.pk}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('积分不足', resp.data['detail'])

    def test_accept_succeeds_when_publisher_has_enough_credits(self):
        """发布者积分足够时接单成功"""
        publisher = User.objects.create_user(username='rich_pub', password='pw', credit_score=100)
        worker = User.objects.create_user(username='wkr2', password='pw')
        task = self._make_open_task(publisher, reward=20)

        self._auth(worker)
        resp = self.client.post(f'/api/tasks/{task.pk}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_zero_reward_task_can_always_be_accepted(self):
        """无悬赉任务（reward=0）不需要积分检查"""
        publisher = User.objects.create_user(username='zero_pub', password='pw', credit_score=0)
        worker = User.objects.create_user(username='zero_wkr', password='pw')
        task = self._make_open_task(publisher, reward=0)

        self._auth(worker)
        resp = self.client.post(f'/api/tasks/{task.pk}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── 任务完成转账 ──

    def test_credit_transfer_on_complete(self):
        """任务完成后，悬赉积分从发布者转移到接单者"""
        publisher = User.objects.create_user(username='pub_pay', password='pw', credit_score=100)
        worker = User.objects.create_user(username='wkr_pay', password='pw', credit_score=0)
        task = Task.objects.create(
            publisher=publisher,
            worker=worker,
            category=TaskCategory.HELP,
            title='转账测试',
            content='内容',
            status=TaskStatus.IN_PROGRESS,
            reward_amount='30.00',
        )

        self._auth(publisher)
        resp = self.client.post(f'/api/tasks/{task.pk}/complete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['reward_transferred'])

        publisher.refresh_from_db()
        worker.refresh_from_db()
        self.assertEqual(publisher.credit_score, 70)   # 100 - 30（悬赏支付）
        # worker = 悬赏30 + 首次助人奖励10 = 40
        self.assertGreaterEqual(worker.credit_score, 30)  # 至少拿到悬赏部分

        # 确认产生了悬赏相关明细记录
        self.assertEqual(CreditDetail.objects.filter(user=publisher, change_amount=-30).count(), 1)
        self.assertEqual(CreditDetail.objects.filter(user=worker, change_amount=30).count(), 1)


    def test_no_transfer_when_reward_is_zero(self):
        """无悬赉任务完成不发生转账"""
        publisher = User.objects.create_user(username='pub_free', password='pw', credit_score=50)
        worker = User.objects.create_user(username='wkr_free', password='pw', credit_score=0)
        task = Task.objects.create(
            publisher=publisher,
            worker=worker,
            category=TaskCategory.HELP,
            title='免费任务',
            content='内容',
            status=TaskStatus.IN_PROGRESS,
            reward_amount='0.00',
        )

        self._auth(publisher)
        resp = self.client.post(f'/api/tasks/{task.pk}/complete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['reward_transferred'])

        publisher.refresh_from_db()
        worker.refresh_from_db()
        self.assertEqual(publisher.credit_score, 50)  # 悬赉不转账，积分不变
        # worker 可能因 首次助人奖励(+10) 而得分，但就是没有悬赉转账
        self.assertEqual(CreditDetail.objects.filter(
            user=worker, reason__contains='就是悬赉'
        ).count(), 0)  # 确认没有悬赉转账记录

    def test_task_with_location(self):
        """创建带地理位置的任务，详情接口能正确返回经纬度"""
        publisher = User.objects.create_user(username='loc_pub', password='pw', credit_score=100)
        self._auth(publisher)

        resp = self.client.post('/api/tasks/', {
            'category': TaskCategory.HELP,
            'title': '带地址的任务',
            'content': '内容',
            'images': ['http://test.com/a.jpg'],
            'reward_amount': '5.00',
            'latitude': '39.908823',
            'longitude': '116.397470',
            'location_name': '天安门广场',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        detail_resp = self.client.get(f'/api/tasks/{resp.data["id"]}/')
        self.assertEqual(detail_resp.data['location_name'], '天安门广场')
        self.assertIsNotNone(detail_resp.data['latitude'])


class NotificationModuleTest(TestCase):
    """通知模块测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='u_noti', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        from .models import Notification, NotificationType
        Notification.objects.create(
            recipient=self.user,
            notify_type=NotificationType.SYSTEM,
            content='Test Notification 1'
        )
        Notification.objects.create(
            recipient=self.user,
            notify_type=NotificationType.TASK_ACCEPTED,
            content='Test Notification 2'
        )

    def test_list_notifications(self):
        resp = self.client.get('/api/notifications/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Check that there are 2 notifications
        data = resp.data.get('results', resp.data) if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(data), 2)
        self.assertFalse(data[0]['is_read'])

    def test_read_single_notification(self):
        from .models import Notification
        notif = Notification.objects.filter(recipient=self.user).first()
        resp = self.client.patch(f'/api/notifications/{notif.pk}/read/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_read_all_notifications(self):
        resp = self.client.post('/api/notifications/read-all/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated_count'], 2)
        from .models import Notification
        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 0)


class ReviewModuleTest(TestCase):
    """评价与雷达图模块测试"""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='rev_pub', password='pw')
        self.user2 = User.objects.create_user(username='rev_wkr', password='pw')
        
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user1).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        self.task = Task.objects.create(
            publisher=self.user1,
            worker=self.user2,
            category=TaskCategory.HELP,
            title='评价测试任务',
            status=TaskStatus.COMPLETED
        )

    def test_submit_review_success(self):
        from .models import Review
        resp = self.client.post('/api/reviews/', {
            'task': self.task.pk,
            'rating_communication': 5,
            'rating_attitude': 4,
            'rating_quality': 5,
            'rating_speed': 3,
            'rating_reliability': 5,
            'comment': '合作很愉快'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 1)
        r = Review.objects.first()
        self.assertEqual(r.reviewer, self.user1)
        self.assertEqual(r.reviewee, self.user2)

    def test_duplicate_review_fails(self):
        from .models import Review
        self.client.post('/api/reviews/', {
            'task': self.task.pk,
            'comment': 'first'
        })
        resp = self.client.post('/api/reviews/', {
            'task': self.task.pk,
            'comment': 'second'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)

    def test_outsider_cannot_review(self):
        outsider = User.objects.create_user(username='outsider', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(outsider).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp = self.client.post('/api/reviews/', {
            'task': self.task.pk,
            'comment': 'test'
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_radar_view(self):
        from .models import Review
        # Create some reviews for user2
        Review.objects.create(
            task=self.task, reviewer=self.user1, reviewee=self.user2,
            rating_communication=4, rating_attitude=5, rating_quality=4, rating_speed=5, rating_reliability=4
        )
        task2 = Task.objects.create(publisher=self.user2, worker=self.user1, status=TaskStatus.COMPLETED)
        Review.objects.create(
            task=task2, reviewer=self.user1, reviewee=self.user2,
            rating_communication=5, rating_attitude=3, rating_quality=4, rating_speed=4, rating_reliability=5
        )

        # anyone can view radar
        self.client.credentials() 
        resp = self.client.get(f'/api/users/{self.user2.pk}/radar/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        radar = resp.data['radar']
        self.assertEqual(radar['communication'], 4.5)
        self.assertEqual(radar['attitude'], 4.0)
        self.assertEqual(radar['quality'], 4.0)
        self.assertEqual(radar['speed'], 4.5)
        self.assertEqual(radar['reliability'], 4.5)
        self.assertEqual(resp.data['total_reviews'], 2)


class VerifyModuleTest(TestCase):
    """学生认证模块测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='test_verify', password='pw')
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_verify_application_lifecycle(self):
        from .models import VerifyApplication

        # 1. initially None
        resp = self.client.get('/api/verify/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data)

        # 2. post Application
        resp = self.client.post('/api/verify/', {
            'real_name': '张三',
            'student_id_image': 'http://test.image'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'PENDING')

        # 3. auto-block duplicate active application
        resp = self.client.post('/api/verify/', {
            'real_name': '李四',
            'student_id_image': 'http://test.image2'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Get current application
        resp = self.client.get('/api/verify/')
        self.assertEqual(resp.data['status'], 'PENDING')
        self.assertEqual(resp.data['real_name'], '张三')
