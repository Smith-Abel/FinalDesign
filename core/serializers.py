from rest_framework import serializers
from .models import User, Task, Message, CreditDetail


# ───────── 用户序列化器 ─────────

class UserSerializer(serializers.ModelSerializer):
    """用户信息序列化器，用于 profile 接口的读取与更新"""
    tasks_created = serializers.SerializerMethodField()
    tasks_done = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'phone', 'student_id', 'avatar', 'college',
            'gender', 'credit_score', 'is_verified',
            'profile_reward_given', 'first_help_rewarded',
            'tasks_created', 'tasks_done'
        ]
        # 系统控制字段，前端不可直接修改
        read_only_fields = [
            'id', 'username', 'credit_score', 'is_verified',
            'profile_reward_given', 'first_help_rewarded',
        ]

    def get_tasks_created(self, obj):
        return obj.published_tasks.count()

    def get_tasks_done(self, obj):
        from .models import TaskStatus
        return obj.accepted_tasks.filter(status=TaskStatus.COMPLETED).count()



# ───────── 任务序列化器 ─────────

class TaskListSerializer(serializers.ModelSerializer):
    """列表页使用的轻量序列化器，减少不必要字段传输"""
    publisher_name = serializers.CharField(source='publisher.username', read_only=True)
    publisher_avatar = serializers.URLField(source='publisher.avatar', read_only=True)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'category', 'title', 'tags',
            'reward_amount', 'status', 'publisher_name', 'publisher_avatar', 'created_at', 'cover_image',
        ]

    def get_cover_image(self, obj):
        if obj.images and len(obj.images) > 0:
            return obj.images[0]
        return None


class TaskDetailSerializer(serializers.ModelSerializer):
    """详情页使用的完整序列化器"""
    publisher = UserSerializer(read_only=True)
    worker = UserSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'category', 'title', 'content', 'tags',
            'reward_amount', 'status', 'publisher', 'worker',
            'latitude', 'longitude', 'location_name', 'images',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'publisher', 'worker', 'created_at', 'updated_at']


class TaskCreateSerializer(serializers.ModelSerializer):
    """创建任务使用，publisher 由后端自动注入，不由前端传入"""

    class Meta:
        model = Task
        fields = [
            'id', 'category', 'title', 'content', 'tags', 'reward_amount',
            'latitude', 'longitude', 'location_name', 'images',
        ]
        read_only_fields = ['id']


class TaskUpdateSerializer(serializers.ModelSerializer):
    """
    发布者修改自己任务的序列化器。
    仅允许修改内容类字段，状态/发布者/接单者等核心字段由后端控制。
    只有 OPEN 状态的任务才允许编辑（接单后不能随意改动）。
    """

    class Meta:
        model = Task
        fields = [
            'title', 'content', 'tags', 'reward_amount',
            'latitude', 'longitude', 'location_name', 'images',
        ]

    def validate(self, attrs):
        # 只有待接单状态才允许编辑，接单后内容锁定避免纠纷
        if self.instance and self.instance.status != 'OPEN':
            raise serializers.ValidationError('只有待接单状态的任务可以编辑')
        return attrs




# ───────── 消息序列化器 ─────────

class MessageSerializer(serializers.ModelSerializer):
    # sender 返回用户 ID，便于前端判断消息是否是自己发送（isMine）
    sender = serializers.IntegerField(source='sender.id', read_only=True)
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    sender_avatar = serializers.URLField(source='sender.avatar', read_only=True, default='')

    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_name', 'sender_avatar', 'content_text', 'is_read', 'created_at']
        read_only_fields = ['id', 'sender', 'sender_name', 'sender_avatar', 'is_read', 'created_at']


# ───────── 积分明细序列化器 ─────────

class CreditDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = CreditDetail
        fields = ['id', 'change_amount', 'reason', 'created_at']
