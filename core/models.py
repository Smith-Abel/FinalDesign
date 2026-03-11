from django.db import models
from django.contrib.auth.models import AbstractUser


class GenderChoices(models.TextChoices):
    MALE = 'MALE', '男'
    FEMALE = 'FEMALE', '女'
    SECRET = 'SECRET', '保密'

class User(AbstractUser):
    openid = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name="微信OpenID")
    nickname = models.CharField(max_length=50, null=True, blank=True, verbose_name="昵称")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="手机号")
    student_id = models.CharField(max_length=50, null=True, blank=True, verbose_name="学号")
    avatar = models.URLField(null=True, blank=True, verbose_name="头像URL")
    college = models.CharField(max_length=100, null=True, blank=True, verbose_name="学院")
    credit_score = models.IntegerField(default=0, verbose_name="信用积分")
    is_verified = models.BooleanField(default=False, verbose_name="学生认证状态")
    gender = models.CharField(
        max_length=10,
        choices=GenderChoices.choices,
        default=GenderChoices.SECRET,
        verbose_name="性别"
    )
    # 积分奖励标志位，确保每种奖励只发放一次，防止重复刷分
    profile_reward_given = models.BooleanField(default=False, verbose_name="资料完善奖励已发放")
    first_help_rewarded = models.BooleanField(default=False, verbose_name="首次助人奖励已发放")

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = verbose_name


class TaskCategory(models.TextChoices):
    STUDY = 'STUDY', '学业指导'
    TRADE = 'TRADE', '物品交易'
    HELP = 'HELP', '生活协助'

class TaskStatus(models.TextChoices):
    OPEN = 'OPEN', '待接单'
    IN_PROGRESS = 'IN_PROGRESS', '进行中'
    PENDING_CONFIRM = 'PENDING_CONFIRM', '待确认'
    COMPLETED = 'COMPLETED', '已完成'
    CANCELLED = 'CANCELLED', '已取消'

class Task(models.Model):
    publisher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='published_tasks', verbose_name="发单者")
    worker = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_tasks', verbose_name="接单者")
    category = models.CharField(max_length=20, choices=TaskCategory.choices, verbose_name="任务分类")
    title = models.CharField(max_length=100, verbose_name="标题")
    content = models.TextField(verbose_name="详细内容")
    tags = models.CharField(max_length=200, blank=True, verbose_name="标签")
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="悬赏金额")
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.OPEN, verbose_name="状态")
    # 地理位置：可不填，填写后展示地图入口
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="纬度")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="经度")
    location_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="位置名称")
    images = models.JSONField(default=list, blank=True, verbose_name="任务图片")
    # 自动风控：被多次举报后自动隐藏，管理员审核处理后可恢复
    is_hidden = models.BooleanField(default=False, verbose_name="已被隐藏")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "互助任务"
        verbose_name_plural = verbose_name

class Message(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='messages', verbose_name="关联任务")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name="发送者")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', verbose_name="接收者")
    content_text = models.TextField(verbose_name="消息内容")
    is_read = models.BooleanField(default=False, verbose_name="是否已读")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发送时间")

    class Meta:
        verbose_name = "私信消息"
        verbose_name_plural = verbose_name

class CreditDetail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_records', verbose_name="用户")
    change_amount = models.IntegerField(verbose_name="变更额度 (+/-)")
    reason = models.CharField(max_length=200, verbose_name="变更原因")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="记录时间")

    class Meta:
        verbose_name = "积分明细"
        verbose_name_plural = verbose_name


class ReportReason(models.TextChoices):
    FAKE = 'FAKE', '虚假信息'
    FRAUD = 'FRAUD', '欺诈行为'
    BAD_CONTENT = 'BAD_CONTENT', '不良内容'
    HARASSMENT = 'HARASSMENT', '骚扰'
    OTHER = 'OTHER', '其他'


class ReportStatus(models.TextChoices):
    PENDING = 'PENDING', '审核中'
    HANDLED = 'HANDLED', '已处理'
    REJECTED = 'REJECTED', '已驳回'


class ReportTargetType(models.TextChoices):
    TASK = 'task', '任务'
    USER = 'user', '用户'


class Report(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_reports', verbose_name="举报人")
    target_type = models.CharField(max_length=10, choices=ReportTargetType.choices, verbose_name="举报对象类型")
    target_id = models.IntegerField(verbose_name="被举报对象ID")
    # 提交时抓取被举报内容快照，防止对象被删除后数据丢失
    target_snapshot = models.JSONField(default=dict, verbose_name="被举报内容快照")
    reason = models.CharField(max_length=20, choices=ReportReason.choices, verbose_name="举报类型")
    description = models.TextField(blank=True, verbose_name="举报说明")
    images = models.JSONField(default=list, blank=True, verbose_name="证据截图")
    status = models.CharField(
        max_length=10,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        verbose_name="处理状态"
    )
    result_note = models.TextField(blank=True, verbose_name="管理员处理说明")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="举报时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="最后处理时间")

    class Meta:
        verbose_name = "举报记录"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
