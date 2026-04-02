from django.urls import path
from . import manage_views as views

urlpatterns = [
    # 仪表盘
    path('dashboard/', views.AdminDashboardStatsView.as_view(), name='manage-dashboard'),
    
    # 用户管理
    path('users/', views.AdminUserListView.as_view(), name='manage-users'),
    path('users/<int:pk>/ban/', views.AdminUserBanView.as_view(), name='manage-user-ban'),
    
    # 任务管理
    path('tasks/', views.AdminTaskListView.as_view(), name='manage-tasks'),
    path('tasks/<int:pk>/toggle_hide/', views.AdminTaskHideView.as_view(), name='manage-task-hide'),
    
    # 学生认证仲裁
    path('verifies/', views.AdminVerifyListView.as_view(), name='manage-verify-list'),
    path('verifies/<int:pk>/action/', views.AdminVerifyActionView.as_view(), name='manage-verify-action'),
    
    # 举报工单仲裁
    path('reports/', views.AdminReportListView.as_view(), name='manage-report-list'),
    path('reports/<int:pk>/action/', views.AdminReportActionView.as_view(), name='manage-report-action'),
    
    # 审计与导出
    path('audits/', views.AdminAuditLogListView.as_view(), name='manage-audit-list'),
    path('export/users/', views.AdminExportUsersView.as_view(), name='manage-export-users'),
    path('export/tasks/', views.AdminExportTasksView.as_view(), name='manage-export-tasks'),
]
