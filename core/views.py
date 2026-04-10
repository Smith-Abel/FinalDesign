import io
import time
import requests
import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse
from rest_framework import generics, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q

from .models import User, Task, TaskStatus, Message, CreditDetail, Report, ReportStatus, ReportTargetType, Notification, NotificationType
from .serializers import (
    UserSerializer,
    TaskListSerializer,
    TaskDetailSerializer,
    TaskCreateSerializer,
    TaskUpdateSerializer,
    MessageSerializer,
    CreditDetailSerializer,
    ReportCreateSerializer,
    ReportListSerializer,
    NotificationSerializer,
    ReviewSerializer,
    VerifyApplicationSerializer,
)
from . import services as credit_service


def _get_tokens_for_user(user):
    """为指定用户生成 JWT access + refresh token，返回 dict"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ═══════════════════ 认证模块 ═══════════════════

class WxLoginView(APIView):
    """
    POST /api/auth/wx-login/
    接收前端传来的微信临时 code，换取 openid，
    首次登录自动创建用户账号（openid 即唯一身份），
    返回 JWT token 供后续请求鉴权。
    不需要携带 token（AllowAny）。
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'detail': '缺少 code 参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 调用微信 code2session 接口换取 openid
        wx_url = 'https://api.weixin.qq.com/sns/jscode2session'
        resp = requests.get(wx_url, params={
            'appid': settings.WX_APPID,
            'secret': settings.WX_SECRET,
            'js_code': code,
            'grant_type': 'authorization_code',
        }, timeout=5)
        wx_data = resp.json()

        if 'errcode' in wx_data and wx_data['errcode'] != 0:
            return Response(
                {'detail': f"微信接口错误: {wx_data.get('errmsg')}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        openid = wx_data.get('openid')

        # 根据 openid 查找或创建用户
        user, created = User.objects.get_or_create(
            openid=openid,
            defaults={'username': f'wx_{openid[:16]}'},  # 默认用户名，后续可修改
        )

        # 新用户首次注册：发放随机初始积分（50~100）
        register_bonus = None
        if created:
            register_bonus = credit_service.grant_register_bonus(user)

        tokens = _get_tokens_for_user(user)
        return Response({
            'is_new_user': created,
            'register_bonus': register_bonus,
            'token': tokens,
            'user': UserSerializer(user).data,
        })


class AccountLoginView(APIView):
    """
    POST /api/auth/login/
    账号密码登录（username 也可传 student_id），
    不需要携带 token（AllowAny）。
    返回格式与 wx-login 保持一致，便于前端统一处理。
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.contrib.auth import authenticate
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response({'detail': '用户名和密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 支持用 student_id 当账号登录：先查找对应的 username
        user = None
        if User.objects.filter(student_id=username).exists():
            user_obj = User.objects.get(student_id=username)
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = authenticate(request, username=username, password=password)

        if user is None:
            return Response({'detail': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = _get_tokens_for_user(user)
        return Response({
            'is_new_user': False,
            'register_bonus': None,
            'token': tokens,
            'user': UserSerializer(user).data,
        })


class RegisterView(APIView):
    """
    POST /api/auth/register/
    账号注册（用户名+密码，学号选填）。
    注册成功后自动发放初始积分并返回 JWT token，
    和微信首次注册的体验保持一致。
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        password2 = request.data.get('password2', '')
        student_id = request.data.get('student_id', '').strip()

        # 基础校验
        if not username or len(username) < 2:
            return Response({'detail': '用户名至少2个字符'}, status=status.HTTP_400_BAD_REQUEST)
        if not password or len(password) < 6:
            return Response({'detail': '密码至少6位'}, status=status.HTTP_400_BAD_REQUEST)
        if password != password2:
            return Response({'detail': '两次密码不一致'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
            return Response({'detail': '该用户名已被注册'}, status=status.HTTP_400_BAD_REQUEST)
        if student_id and User.objects.filter(student_id=student_id).exists():
            return Response({'detail': '该学号已被绑定'}, status=status.HTTP_400_BAD_REQUEST)

        # 创建用户（openid 留空，password 走 Django 哈希）
        user = User.objects.create_user(
            username=username,
            password=password,
            student_id=student_id or None,
        )
        # 发放注册初始积分
        register_bonus = credit_service.grant_register_bonus(user)

        tokens = _get_tokens_for_user(user)
        return Response({
            'is_new_user': True,
            'register_bonus': register_bonus,
            'token': tokens,
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/auth/profile/ → 获取当前登录用户的个人信息
    PATCH /api/auth/profile/ → 更新个人信息，更新后自动检测资料完善奖励
    """
    serializer_class = UserSerializer

    def get_object(self):
        # 直接从 JWT 中解析的 request.user 返回，无需 pk
        return self.request.user

    def partial_update(self, request, *args, **kwargs):
        # 先执行正常的字段更新
        response = super().partial_update(request, *args, **kwargs)
        # 更新完成后检测是否触发资料完善奖励
        # 此时 request.user 的字段已通过 serializer 保存，需重新从 DB 读取
        user = self.get_object()
        credit_service.grant_profile_bonus(user)
        # 刷新序列化数据（credit_score 可能已变化）
        response.data = UserSerializer(user).data
        return response

    # 禁用 PUT，只允许 PATCH 局部更新
    http_method_names = ['get', 'patch', 'head', 'options']


# ═══════════════════ 任务模块 ═══════════════════

class TaskListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/tasks/           → 获取任务列表，支持 ?category= 和 ?status= 过滤
    POST /api/tasks/           → 发布新任务，publisher 自动设置为当前用户
    """

    def get_queryset(self):
        from django.db.models import Q
        # 预加载 publisher 解决一对多 N+1，预加载 reviews 解决序列化中统计评价的 N+1
        qs = Task.objects.select_related('publisher').prefetch_related('reviews')
        
        category = self.request.query_params.get('category')
        task_status = self.request.query_params.get('status')
        search_query = self.request.query_params.get('search')
        target_college = self.request.query_params.get('target_college')
        ordering = self.request.query_params.get('ordering', '-created_at')

        if category:
            qs = qs.filter(category=category)
        if task_status:
            qs = qs.filter(status=task_status)
        else:
            qs = qs.exclude(status__in=[TaskStatus.CANCELLED, TaskStatus.COMPLETED])
            
        if target_college:
            qs = qs.filter(target_college=target_college)
            
        # 自动风控：过滤已被隐藏的任务
        qs = qs.filter(is_hidden=False)
            
        if search_query:
            qs = qs.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query) | Q(tags__icontains=search_query))
            
        return qs.order_by(ordering)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TaskCreateSerializer
        return TaskListSerializer

    def perform_create(self, serializer):
        user = self.request.user
        title = self.request.data.get('title', '新任务')

        # 检查积分余额是否足够支付发布手续费（5分）
        if not credit_service.check_credits_sufficient(user, credit_service.CREDIT_PUBLISH_FEE):
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f'积分不足，发布任务需要 {credit_service.CREDIT_PUBLISH_FEE} 积分手续费，'
                f'当前余额 {user.credit_score} 分'
            )

        task = serializer.save(publisher=user)
        # 原子性扣除发布手续费
        credit_service.deduct_publish_fee(user, task.title)


class TaskDetailView(generics.RetrieveAPIView):
    """
    GET /api/tasks/{id}/ → 获取任务详情（含发布者、接单者的完整信息）
    """
    queryset = Task.objects.select_related('publisher', 'worker').prefetch_related('reviews')
    serializer_class = TaskDetailSerializer


class TaskAcceptView(APIView):
    """
    POST /api/tasks/{id}/accept/ → 接单
    - 只有状态为 OPEN 的任务可以接单
    - 发布者自己不能接自己的任务
    - 发布者必须拥有足够将支付钟赏的积分
    """

    def post(self, request, pk):
        from django.db import transaction
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

            if task.status != TaskStatus.OPEN:
                return Response({'detail': '该任务已被接单或不可接'}, status=status.HTTP_400_BAD_REQUEST)

            if task.publisher == request.user:
                return Response({'detail': '不能接自己发布的任务'}, status=status.HTTP_400_BAD_REQUEST)

            # 如果任务有悬赏，必须确保发布者积分足够（防止接单后无法支付）
            reward = int(task.reward_amount)
            if not credit_service.check_credits_sufficient(task.publisher, reward):
                return Response(
                    {'detail': f'发布者积分不足，无法支付悬赏 {reward} 分'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            task.worker = request.user
            task.status = TaskStatus.PENDING_ACCEPT
            task.save()

            Notification.objects.create(
                recipient=task.publisher,
                notify_type=NotificationType.TASK_ACCEPTED,
                content=f'有人（{request.user.username}）刚刚抢单了您的任务「{task.title}」，请进入详细页审批是否同意 TA 的接单！',
                related_task=task
            )

            return Response({'detail': '接单申请已发出，等待发布者同意', 'task': TaskDetailSerializer(task).data})

class TaskApproveAcceptView(APIView):
    """
    POST /api/tasks/{id}/approve_accept/ → 雇主同意接单
    - 只有状态为 PENDING_ACCEPT 的任务可以同意
    - 只有发布者可以操作
    """
    def post(self, request, pk):
        from django.db import transaction
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

            if task.publisher != request.user:
                return Response({'detail': '只有发布者可以同意接单'}, status=status.HTTP_403_FORBIDDEN)

            if task.status != TaskStatus.PENDING_ACCEPT:
                return Response({'detail': '任务不在待同意状态'}, status=status.HTTP_400_BAD_REQUEST)

            task.status = TaskStatus.IN_PROGRESS
            task.save()

            Notification.objects.create(
                recipient=task.worker,
                notify_type=NotificationType.SYSTEM,
                content=f'恭喜！您对任务「{task.title}」的接单申请已获发布者同意，任务正式开始，请尽快联系对方。',
                related_task=task
            )

            return Response({'detail': '已同意接单，任务正式开始'})


class TaskRejectAcceptView(APIView):
    """
    POST /api/tasks/{id}/reject_accept/ → 雇主拒绝接单
    - 状态回归 OPEN，清空 worker
    """
    def post(self, request, pk):
        from django.db import transaction
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

            if task.publisher != request.user:
                return Response({'detail': '只有发布者可以操作'}, status=status.HTTP_403_FORBIDDEN)

            if task.status != TaskStatus.PENDING_ACCEPT:
                return Response({'detail': '任务不在待同意状态'}, status=status.HTTP_400_BAD_REQUEST)

            worker = task.worker
            task.worker = None
            task.status = TaskStatus.OPEN
            task.save()

            if worker:
                Notification.objects.create(
                    recipient=worker,
                    notify_type=NotificationType.SYSTEM,
                    content=f'抱歉，您对任务「{task.title}」的接单申请被发布者拒绝了，任务已重回大厅。',
                    related_task=task
                )

            return Response({'detail': '已拒绝该用户的接单，任务重回待接单状态'})


class TaskRequestCompleteView(APIView):
    """
    POST /api/tasks/{id}/request_complete/ → 接单者申请完成任务
    - 状态必须为 IN_PROGRESS
    - 只能是接单者操作
    """

    def post(self, request, pk):
        from django.db import transaction
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

            if task.worker != request.user:
                return Response({'detail': '只有接单者可以申请完成'}, status=status.HTTP_403_FORBIDDEN)

            if task.status != TaskStatus.IN_PROGRESS:
                return Response({'detail': '当前任务状态无法申请完成'}, status=status.HTTP_400_BAD_REQUEST)

            task.status = TaskStatus.PENDING_CONFIRM
            task.save()
            
            Notification.objects.create(
                recipient=task.publisher,
                notify_type=NotificationType.SYSTEM,
                content=f'接单者已提交任务「{task.title}」的完成确认申请，请及时审核打款',
                related_task=task
            )

            return Response({'detail': '已提交完成申请，等待发布者确认'})


class TaskCompleteView(APIView):
    """
    POST /api/tasks/{id}/complete/ → 发布者确认任务完成
    - 只有状态为 IN_PROGRESS 或 PENDING_CONFIRM 时可操作
    - 只有发布者可以确认
    """

    def post(self, request, pk):
        from django.db import transaction
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

            if task.publisher != request.user:
                return Response({'detail': '只有发布者可以确认完成'}, status=status.HTTP_403_FORBIDDEN)

            if task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.PENDING_CONFIRM):
                return Response({'detail': '当前任务状态无法确认完成'}, status=status.HTTP_400_BAD_REQUEST)

            task.status = TaskStatus.COMPLETED
            task.save()

            # 检测接单者是否触发首次助人奖励
            first_help_bonus = False
            if task.worker:
                first_help_bonus = credit_service.grant_first_help_bonus(task.worker)

            # 执行悬赏积分转账（发布者 → 接单者）
            reward_transferred = credit_service.transfer_task_reward(task)
            
            if task.worker:
                Notification.objects.create(
                    recipient=task.worker,
                    notify_type=NotificationType.TASK_COMPLETED,
                    content=f'您承接的任务「{task.title}」刚才已被发布者确认完成！',
                    related_task=task
                )

            return Response({
                'detail': '任务已标记为完成',
                'first_help_bonus': first_help_bonus,
                'reward_transferred': reward_transferred,
            })


class TaskCancelView(APIView):
    """
    POST /api/tasks/{id}/cancel/ → 取消任务
    - 只有发布者可以取消
    - 已完成的任务不能取消
    - OPEN 状态取消时退还发布手续费（已接单则不退，服务已消耗）
    """

    def post(self, request, pk):
        from django.db import transaction
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

            if task.publisher != request.user:
                return Response({'detail': '只有发布者可以取消任务'}, status=status.HTTP_403_FORBIDDEN)

            if task.status == TaskStatus.COMPLETED:
                return Response({'detail': '已完成的任务无法取消'}, status=status.HTTP_400_BAD_REQUEST)

            if task.status == TaskStatus.CANCELLED:
                return Response({'detail': '任务已经是取消状态'}, status=status.HTTP_400_BAD_REQUEST)

            # 发布任务取消由于有退费，后续可在 credit_service 中实现 refund_publish_fee
            refunded = False
            if task.status == TaskStatus.OPEN:
                refunded = credit_service.refund_publish_fee(task.publisher, task.title)

            task.status = TaskStatus.CANCELLED
            task.save()
            
            if task.worker:
                Notification.objects.create(
                    recipient=task.worker,
                    notify_type=NotificationType.TASK_CANCELLED,
                    content=f'您承接的任务「{task.title}」已被发布者取消',
                    related_task=task
                )

            return Response({'detail': '任务已取消', 'fee_refunded': refunded})


class MyTaskListView(generics.ListAPIView):
    """
    GET /api/tasks/mine/ → 获取当前用户相关的任务
    支持 ?role=publisher/worker 过滤视角（默认 publisher）
    支持 ?status= 过滤状态
    """
    serializer_class = TaskDetailSerializer

    def get_queryset(self):
        user = self.request.user
        role = self.request.query_params.get('role', 'publisher')
        task_status = self.request.query_params.get('status')

        if role == 'worker':
            qs = Task.objects.filter(worker=user)
        else:
            qs = Task.objects.filter(publisher=user)

        if task_status:
            qs = qs.filter(status=task_status)
            
        return qs.select_related('publisher', 'worker').prefetch_related('reviews').order_by('-created_at')


class TaskUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/tasks/{id}/edit/ → 发布者修改任务内容
    - 只有任务发布者可以修改
    - 只有 OPEN 状态（待接单）的任务可以修改，接单后锁定
    """
    serializer_class = TaskUpdateSerializer
    http_method_names = ['patch', 'head', 'options']  # 只允许 PATCH 局部更新

    def get_queryset(self):
        # 权限：当前用户才能修改自己的任务
        return Task.objects.filter(publisher=self.request.user)

    def get_object(self):
        try:
            task = Task.objects.get(pk=self.kwargs['pk'], publisher=self.request.user)
        except Task.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('任务不存在或无权限修改')
        return task


# ═══════════════════ 消息模块 ═══════════════════

class TaskMessageView(APIView):
    """
    GET  /api/tasks/{id}/messages/ → 获取任务的消息列表（只有任务参与者可查看）
    POST /api/tasks/{id}/messages/ → 在任务中发送私信
    """

    def _get_task_or_404(self, pk):
        try:
            return Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return None

    def _check_participant(self, task, user):
        """校验用户是否为任务的发布者或接单者"""
        return user == task.publisher or user == task.worker

    def get(self, request, pk):
        task = self._get_task_or_404(pk)
        if not task:
            return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        if not self._check_participant(task, request.user):
            return Response({'detail': '无权查看此任务的消息'}, status=status.HTTP_403_FORBIDDEN)

        # 把发给我的未读消息标记为已读
        Message.objects.filter(task=task, receiver=request.user, is_read=False).update(is_read=True)

        messages = Message.objects.filter(task=task).order_by('created_at')
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, pk):
        task = self._get_task_or_404(pk)
        if not task:
            return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        if not self._check_participant(task, request.user):
            return Response({'detail': '只有任务参与者才能发送消息'}, status=status.HTTP_403_FORBIDDEN)

        content_text = request.data.get('content_text', '').strip()
        if not content_text:
            return Response({'detail': '消息内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 对方即为另一位参与者
        receiver = task.worker if request.user == task.publisher else task.publisher

        msg = Message.objects.create(
            task=task,
            sender=request.user,
            receiver=receiver,
            content_text=content_text,
        )
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)

class ChatSessionListView(APIView):
    """
    GET /api/messages/sessions/ → 获取当前用户的聊天会话聚合列表（按联系人+任务维度聚合）
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 找到与当前用户相关的所有私信，按时间倒序
        messages = Message.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver', 'task').order_by('-created_at')

        sessions_dict = {}
        for msg in messages:
            # 确定对方(partner)
            partner = msg.receiver if msg.sender == user else msg.sender
            
            # 以 任务+联系人 为维度区分不同会话
            session_key = f"{msg.task.id}_{partner.id}"
            
            # 如果该会话尚未加入字典，则加入（因为按 created_at 倒序排列，首次遇到即是最新的消息）
            if session_key not in sessions_dict:
                # 计算该联系人在该任务发给我的所有未读消息
                unread_count = Message.objects.filter(task=msg.task, sender=partner, receiver=user, is_read=False).count()
                
                sessions_dict[session_key] = {
                    'task_id': msg.task.id,
                    'task_title': msg.task.title,
                    'target_college': msg.task.target_college,
                    'status': msg.task.status,
                    'partner_id': partner.id,
                    'partner_name': partner.nickname or partner.username,
                    'partner_avatar': partner.avatar,
                    'last_message': msg.content_text,
                    'last_time': msg.created_at,
                    'unread_count': unread_count,
                }
        
        sessions = list(sessions_dict.values())
        sessions.sort(key=lambda x: x['last_time'], reverse=True)
        return Response(sessions)


# ═══════════════════ 积分模块 ═══════════════════

class CreditListView(generics.ListAPIView):
    """
    GET /api/credits/ → 获取当前用户的积分变更明细（按时间倒序）
    """
    serializer_class = CreditDetailSerializer

    def get_queryset(self):
        return CreditDetail.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


# ═══════════════════ 手机号绑定 ═══════════════════

class BindPhoneView(APIView):
    """
    POST /api/auth/bind-phone/
    接收微信 getPhoneNumber 返回的 code，
    调用微信接口换取真实手机号并绑定到当前账号。
    微信官方方案（2021年后）：code 换取手机号，需先获取 access_token。
    """

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'detail': '缺少 code 参数'}, status=status.HTTP_400_BAD_REQUEST)

        # Step 1: 获取小程序全局 access_token
        token_resp = requests.get(
            'https://api.weixin.qq.com/cgi-bin/token',
            params={
                'grant_type': 'client_credential',
                'appid': settings.WX_APPID,
                'secret': settings.WX_SECRET,
            },
            timeout=5,
        ).json()

        access_token = token_resp.get('access_token')
        if not access_token:
            return Response(
                {'detail': f"获取 access_token 失败: {token_resp.get('errmsg', '未知错误')}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Step 2: 用 code 换取手机号
        phone_resp = requests.post(
            f'https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}',
            json={'code': code},
            timeout=5,
        ).json()

        if phone_resp.get('errcode', 0) != 0:
            return Response(
                {'detail': f"获取手机号失败: {phone_resp.get('errmsg')}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone = phone_resp['phone_info']['phoneNumber']
        request.user.phone = phone
        request.user.save(update_fields=['phone'])

        return Response({'phone': phone})


# ═══════════════════ 图片上传 ═══════════════════

class ImageUploadView(APIView):
    """
    POST /api/upload/image/
    接受 multipart/form-data 中的 image 字段，
    校验格式（JPEG/PNG/GIF/WebP）和大小（≤10MB），
    保存到 MEDIA_ROOT/uploads/ 并返回可访问的绝对 URL。
    """
    parser_classes = [MultiPartParser, FormParser]

    ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    def post(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'detail': '请选择要上传的图片（字段名：image）'}, status=status.HTTP_400_BAD_REQUEST)

        if image_file.content_type not in self.ALLOWED_TYPES:
            return Response({'detail': '仅支持 JPEG / PNG / GIF / WebP 格式'}, status=status.HTTP_400_BAD_REQUEST)

        if image_file.size > self.MAX_SIZE:
            return Response({'detail': '图片不能超过 10MB'}, status=status.HTTP_400_BAD_REQUEST)

        # 用时间戳 + 原始文件名防止重名
        ext = image_file.name.rsplit('.', 1)[-1].lower()
        filename = f'uploads/{int(time.time())}_{image_file.name}'
        saved_path = default_storage.save(filename, ContentFile(image_file.read()))

        # 构建完整可访问 URL（开发时返回 http://127.0.0.1:8000/media/...）
        image_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
        return Response({'url': image_url}, status=status.HTTP_201_CREATED)


# ═══════════════════ 任务二维码 ═══════════════════

class TaskQRCodeView(APIView):
    """
    GET /api/tasks/{id}/qrcode/
    生成任务分享二维码（PNG 图片直接返回）。
    二维码内容为 campus-helper://task/{id}，
    小程序可通过 wx.scanCode 扫描后解析跳转到任务详情页。
    """

    def get(self, request, pk):
        try:
            task = Task.objects.only('id', 'title').get(pk=pk)
        except Task.DoesNotExist:
            return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 生成包含任务 deep-link 的二维码
        qr_content = f'campus-helper://task/{task.pk}'
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)

        img = qr.make_image(fill_color='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return HttpResponse(buffer, content_type='image/png')


# ─────────────────────────────────────────────────────────────────────────────
# 举报模块
# ─────────────────────────────────────────────────────────────────────────────

class ReportCreateView(APIView):
    """
    POST /api/reports/
    创建举报记录。包含防重复、频率限制、内容快照和自动风控逻辑。
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        user = request.user
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')

        # 防重复举报：同一用户对同一对象已有 PENDING 记录
        if Report.objects.filter(
            reporter=user,
            target_type=target_type,
            target_id=target_id,
            status=ReportStatus.PENDING
        ).exists():
            return Response(
                {'detail': '您已对该内容提交过举报，请勿重复举报，等待审核中'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 频率限制：24小时内举报次数不超过5次
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        recent_count = Report.objects.filter(reporter=user, created_at__gte=cutoff).count()
        if recent_count >= 5:
            return Response(
                {'detail': '您今日24小时内的举报次数已达上限，请明日再试'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 报 内容快照：提交时存储被举报对象关键信息
        snapshot = self._build_snapshot(target_type, target_id)

        report = serializer.save(reporter=user, target_snapshot=snapshot)

        # 自动风控：任务被举报天数达5次，自动隐藏该任务
        if target_type == ReportTargetType.TASK:
            report_count = Report.objects.filter(
                target_type=ReportTargetType.TASK,
                target_id=target_id
            ).count()
            if report_count >= 5:
                Task.objects.filter(pk=target_id).update(is_hidden=True)

        return Response(
            {'detail': '举报已提交，我们将尽快审核并反馈结果'},
            status=status.HTTP_201_CREATED
        )

    def _build_snapshot(self, target_type, target_id):
        """构建被举报对象内容快照，防止对象被删除后举报记录无从查看"""
        try:
            if target_type == ReportTargetType.TASK:
                task = Task.objects.get(pk=target_id)
                return {
                    'type': 'task',
                    'title': task.title,
                    'category': task.category,
                    'status': task.status,
                    'publisher': task.publisher.username,
                }
            elif target_type == ReportTargetType.USER:
                user = User.objects.get(pk=target_id)
                return {
                    'type': 'user',
                    'username': user.username,
                    'nickname': user.nickname or '',
                }
        except (Task.DoesNotExist, User.DoesNotExist):
            pass
        return {}


class ReportListView(generics.ListAPIView):
    """
    GET /api/reports/mine/
    返回当前用户提交的所有举报记录及处理状态。
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReportListSerializer

    def get_queryset(self):
        return Report.objects.filter(reporter=self.request.user)


# ─────────────────────────────────────────────────────────────────────────────
# 通知模块
# ─────────────────────────────────────────────────────────────────────────────

class NotificationListView(generics.ListAPIView):
    """
    GET /api/notifications/
    获取当前用户的所有系统通知，按时间倒序排列。
    """
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationReadView(APIView):
    """
    PATCH /api/notifications/{id}/read/
    将单条通知标记为已读
    """

    def patch(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': '通知不存在'}, status=status.HTTP_404_NOT_FOUND)

        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'detail': '已标记为已读'})


class NotificationReadAllView(APIView):
    """
    POST /api/notifications/read-all/
    将所有未读通知标记为已读
    """

    def post(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'detail': f'已将 {count} 条通知标记为已读', 'updated_count': count})


# ─────────────────────────────────────────────────────────────────────────────
# 评价与雷达图模块
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ReviewListView(generics.ListAPIView):
    """
    GET /api/reviews/received/
    获取当前用户收到的所有评价，支持分页
    """
    serializer_class = ReviewSerializer
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        from .models import Review
        return Review.objects.filter(reviewee=self.request.user).select_related('reviewer', 'task').order_by('-created_at')


class ReviewCreateView(APIView):
    """
    POST /api/reviews/
    为已完成的任务提交评价
    """

    def post(self, request):
        task_id = request.data.get('task')
        if not task_id:
            return Response({'detail': '缺少任务ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            task = Task.objects.get(pk=task_id)
        except Task.DoesNotExist:
            return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        if task.status != TaskStatus.COMPLETED:
            return Response({'detail': '只能评价已完成的任务'}, status=status.HTTP_400_BAD_REQUEST)

        # 确定评价方与被评价方
        user = request.user
        if user == task.publisher:
            reviewee = task.worker
        elif user == task.worker:
            reviewee = task.publisher
        else:
            return Response({'detail': '非任务参与者无法进行评价'}, status=status.HTTP_403_FORBIDDEN)

        # 检查是否已评价
        from .models import Review
        if Review.objects.filter(task=task, reviewer=user).exists():
            return Response({'detail': '您已对该任务进行了评价'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(reviewer=user, reviewee=reviewee)
        
        Notification.objects.create(
            recipient=reviewee,
            notify_type=NotificationType.SYSTEM,
            content=f'您收到了来自任务「{task.title}」的新评价！去主页看看吧',
            related_task=task
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserRadarView(APIView):
    """
    GET /api/users/{id}/radar/
    获取指定用户的雷达图各项均分，以及他们收到的评价列表
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        from django.db.models import Avg
        from .models import Review

        aggs = Review.objects.filter(reviewee=user).aggregate(
            avg_communication=Avg('rating_communication'),
            avg_attitude=Avg('rating_attitude'),
            avg_quality=Avg('rating_quality'),
            avg_speed=Avg('rating_speed'),
            avg_reliability=Avg('rating_reliability'),
        )

        # 解析均分，如果没被评价过默认为 5 分满分
        radar_data = {
            'communication': round(aggs['avg_communication'] or 5.0, 1),
            'attitude': round(aggs['avg_attitude'] or 5.0, 1),
            'quality': round(aggs['avg_quality'] or 5.0, 1),
            'speed': round(aggs['avg_speed'] or 5.0, 1),
            'reliability': round(aggs['avg_reliability'] or 5.0, 1),
        }

        # 限制预览，仅获取最新 2 条评价列表供在个人资料页占位展示（更多由 my_reviews 提供）
        reviews = Review.objects.filter(reviewee=user).select_related('reviewer').order_by('-created_at')[:2]
        review_list = ReviewSerializer(reviews, many=True).data

        return Response({
            'radar': radar_data,
            'reviews': review_list,
            'total_reviews': Review.objects.filter(reviewee=user).count()
        })


# ─────────────────────────────────────────────────────────────────────────────
# 认证审核模块
# ─────────────────────────────────────────────────────────────────────────────

class VerifyApplicationView(APIView):
    """
    GET  /api/verify/ → 获取当前用户的认证状态（最后一次申请或现有的审核进度）
    POST /api/verify/ → 提交学生身份认证申请
    """

    def get(self, request):
        from .models import VerifyApplication
        app = VerifyApplication.objects.filter(user=request.user).order_by('-created_at').first()
        if not app:
            return Response(None)
        return Response(VerifyApplicationSerializer(app).data)

    def post(self, request):
        from .models import VerifyApplication, VerifyStatus
        
        # Check active applications
        active_status = [VerifyStatus.PENDING, VerifyStatus.APPROVED]
        if VerifyApplication.objects.filter(user=request.user, status__in=active_status).exists():
            return Response({'detail': '您已提交过申请或已经通过认证'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VerifyApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app = serializer.save(user=request.user)
        
        return Response(VerifyApplicationSerializer(app).data, status=status.HTTP_201_CREATED)
