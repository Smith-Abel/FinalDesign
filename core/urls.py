from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # ── 认证模块 ──
    path('auth/wx-login/', views.WxLoginView.as_view(), name='wx-login'),
    path('auth/login/',    views.AccountLoginView.as_view(), name='account-login'),   # 账号密码登录
    path('auth/register/', views.RegisterView.as_view(), name='register'),             # 注册
    path('auth/profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('auth/bind-phone/', views.BindPhoneView.as_view(), name='bind-phone'),
    # 缓存/storage 场景：前端 token 过期时用 refresh token 换新 access token
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # ── 任务模块 ──
    path('tasks/', views.TaskListCreateView.as_view(), name='task-list-create'),
    path('tasks/mine/', views.MyTaskListView.as_view(), name='task-mine'),          # 我的任务（放在 <pk> 前面）
    path('tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('tasks/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task-edit'),
    path('tasks/<int:pk>/accept/', views.TaskAcceptView.as_view(), name='task-accept'),
    path('tasks/<int:pk>/approve_accept/', views.TaskApproveAcceptView.as_view(), name='task-approve-accept'),
    path('tasks/<int:pk>/reject_accept/', views.TaskRejectAcceptView.as_view(), name='task-reject-accept'),
    path('tasks/<int:pk>/request_complete/', views.TaskRequestCompleteView.as_view(), name='task-request-complete'),
    path('tasks/<int:pk>/complete/', views.TaskCompleteView.as_view(), name='task-complete'),
    path('tasks/<int:pk>/cancel/', views.TaskCancelView.as_view(), name='task-cancel'),
    path('tasks/<int:pk>/qrcode/', views.TaskQRCodeView.as_view(), name='task-qrcode'),

    # ── 消息模块 ──
    path('tasks/<int:pk>/messages/', views.TaskMessageView.as_view(), name='task-messages'),
    path('messages/sessions/', views.ChatSessionListView.as_view(), name='message-sessions'),

    # ── 积分模块 ──
    path('credits/', views.CreditListView.as_view(), name='credit-list'),

    # ── 图片上传 ──
    path('upload/image/', views.ImageUploadView.as_view(), name='image-upload'),

    # ── 举报模块 ──
    path('reports/', views.ReportCreateView.as_view(), name='report-create'),
    path('reports/mine/', views.ReportListView.as_view(), name='report-mine'),

    # ── 通知模块 ──
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/read/', views.NotificationReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', views.NotificationReadAllView.as_view(), name='notification-read-all'),

    # ── 评价模块 ──
    path('reviews/', views.ReviewCreateView.as_view(), name='review-create'),
    path('users/<int:pk>/radar/', views.UserRadarView.as_view(), name='user-radar'),

    # ── 学生认证模块 ──
    path('verify/', views.VerifyApplicationView.as_view(), name='verify-application'),

    # ── Web 控制台专用模块 (权限强管控) ──
    path('manage/', include('core.manage_urls')),
]

