from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from .models import User, Task, Report, VerifyApplication, TaskStatus, ReportStatus, VerifyStatus, AdminAuditLog
from .serializers import (
    UserSerializer, TaskDetailSerializer, ReportListSerializer, VerifyApplicationSerializer, AdminAuditLogSerializer
)
from django.db.models import Q
import csv
from django.http import HttpResponse

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

class AdminPagination(PageNumberPagination):
    """管理端专用分页器，每页20条，支持 ?page=N 参数"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class IsSuperAdmin(permissions.BasePermission):
    """仅允许超级管理员（is_staff=True 或 is_superuser=True）访问"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))


# ── 1. 仪表盘统计 API ──
class AdminDashboardStatsView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 用户统计
        total_users = User.objects.count()
        new_users_today = User.objects.filter(date_joined__gte=today).count()
        
        # 任务统计
        total_tasks = Task.objects.count()
        tasks_in_progress = Task.objects.filter(status=TaskStatus.IN_PROGRESS).count()
        tasks_completed = Task.objects.filter(status=TaskStatus.COMPLETED).count()
        
        # 待办事项
        pending_verifies = VerifyApplication.objects.filter(status=VerifyStatus.PENDING).count()
        pending_reports = Report.objects.filter(status=ReportStatus.PENDING).count()

        return Response({
            'users': {
                'total': total_users,
                'new_today': new_users_today
            },
            'tasks': {
                'total': total_tasks,
                'in_progress': tasks_in_progress,
                'completed': tasks_completed
            },
            'todos': {
                'pending_verifies': pending_verifies,
                'pending_reports': pending_reports
            }
        })


# ── 2. 用户管理 API ──
class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = UserSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = User.objects.all()
        
        # 关键词搜索
        keyword = self.request.query_params.get('q', '')
        if keyword:
            qs = qs.filter(Q(username__icontains=keyword) | Q(nickname__icontains=keyword))
            
        # 状态筛选 (如 is_active=true/false)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None and is_active != '':
            is_active_bool = is_active.lower() == 'true'
            qs = qs.filter(is_active=is_active_bool)
            
        # 排序 (默认按注册时间倒序)
        ordering = self.request.query_params.get('ordering', '-date_joined')
        return qs.order_by(ordering)


class AdminUserBanView(APIView):
    """封禁/解封用户：切换 is_active 状态"""
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 超级管理员自身不允许被封禁
        if user.is_superuser:
            return Response({'detail': '无法封禁超级管理员'}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        state = '封禁' if not user.is_active else '解封'
        
        AdminAuditLog.objects.create(
            admin=request.user,
            action='BAN' if not user.is_active else 'OTHER',
            target_id=f"user_{user.id}",
            ip_address=get_client_ip(request),
            reason=f"管理员手动执行{state}"
        )
        
        return Response({'detail': f'用户已{state}', 'is_active': user.is_active})


# ── 3. 任务管理 API ──
class AdminTaskListView(generics.ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = TaskDetailSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = Task.objects.all()
        
        # 关键词搜索
        keyword = self.request.query_params.get('q', '')
        search_mode = self.request.query_params.get('searchMode', 'content')
        
        if keyword:
            if search_mode == 'publisher':
                qs = qs.filter(Q(publisher__username__icontains=keyword) | Q(publisher__nickname__icontains=keyword))
            elif search_mode == 'worker':
                qs = qs.filter(Q(worker__username__icontains=keyword) | Q(worker__nickname__icontains=keyword))
            else:
                qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
            
        # 字段筛选
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
            
        status_val = self.request.query_params.get('status')
        if status_val:
            qs = qs.filter(status=status_val)
            
        is_hidden = self.request.query_params.get('is_hidden')
        if is_hidden is None:
            # 默认：仅展示未隐藏（未下架）的任务
            qs = qs.filter(is_hidden=False)
        elif is_hidden != '':
            is_hidden_bool = is_hidden.lower() == 'true'
            qs = qs.filter(is_hidden=is_hidden_bool)
            
        # 排序 (默认按时间倒序：最新发布在前)
        ordering = self.request.query_params.get('ordering', '-created_at')
        return qs.order_by(ordering)

class AdminTaskHideView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            task = Task.objects.get(pk=pk)
            task.is_hidden = not task.is_hidden
            task.save(update_fields=['is_hidden'])

            state_desc = '隐藏' if task.is_hidden else '恢复显示'
            AdminAuditLog.objects.create(
                admin=request.user,
                action='HIDE' if task.is_hidden else 'OTHER',
                target_id=f"task_{task.id}",
                ip_address=get_client_ip(request),
                reason=f"管理员手动{state_desc}任务"
            )

            return Response({'detail': '状态切换成功', 'is_hidden': task.is_hidden})
        except Task.DoesNotExist:
            return Response({'detail': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)


# ── 4. 认证审批 API ──
class AdminVerifyListView(generics.ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = VerifyApplicationSerializer
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        q = self.request.query_params.get('q', '')
        college = self.request.query_params.get('college', '')
        
        qs = VerifyApplication.objects.select_related('user').all().order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if q:
            qs = qs.filter(Q(real_name__icontains=q) | Q(user__nickname__icontains=q) | Q(user__username__icontains=q))
        if college:
            qs = qs.filter(user__college__icontains=college)
        return qs

class AdminVerifyActionView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        action = request.data.get('action') # 'approve' or 'reject'
        note = request.data.get('note', '')

        try:
            app = VerifyApplication.objects.get(pk=pk)
        except VerifyApplication.DoesNotExist:
            return Response({'detail': '申请单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if app.status != VerifyStatus.PENDING:
            return Response({'detail': '该申请已处理过'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'approve':
            app.status = VerifyStatus.APPROVED
            # Update user
            User.objects.filter(pk=app.user.pk).update(is_verified=True, real_name=app.real_name)
        elif action == 'reject':
            app.status = VerifyStatus.REJECTED
        else:
            return Response({'detail': '无效的 action'}, status=status.HTTP_400_BAD_REQUEST)
        
        app.note = note
        app.save()

        AdminAuditLog.objects.create(
            admin=request.user,
            action='APPROVE' if action == 'approve' else 'REJECT',
            target_id=f"verify_{app.id}",
            ip_address=get_client_ip(request),
            reason=f"学生认证审核: {note}" if note else "学生认证审核"
        )

        return Response({'detail': '处理成功', 'status': app.status})


# ── 5. 举报管理 API ──
class AdminReportListView(generics.ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = ReportListSerializer

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        q = self.request.query_params.get('q', '')
        
        qs = Report.objects.select_related('reporter').all().order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if q:
            qs = qs.filter(Q(reason__icontains=q) | Q(description__icontains=q) | Q(reporter__nickname__icontains=q) | Q(reporter__username__icontains=q))
        return qs

class AdminReportActionView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        action = request.data.get('action') # 'resolve' or 'reject'
        note = request.data.get('note', '')

        try:
            r = Report.objects.get(pk=pk)
        except Report.DoesNotExist:
            return Response({'detail': '举报单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if r.status != ReportStatus.PENDING:
            return Response({'detail': '举报已处理'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'resolve':
            r.status = ReportStatus.RESOLVED
        elif action == 'reject':
            r.status = ReportStatus.REJECTED
        else:
            return Response({'detail': '无效的 action'}, status=status.HTTP_400_BAD_REQUEST)
        
        r.result_note = note
        r.save(update_fields=['status', 'result_note'])

        AdminAuditLog.objects.create(
            admin=request.user,
            action='VERIFY' if action == 'resolve' else 'OTHER',
            target_id=f"report_{r.id}",
            ip_address=get_client_ip(request),
            reason=f"举报工单处理: {note}" if note else "举报工单处理"
        )
        return Response({'detail': '处理成功', 'status': r.status})

# ── 6. 审计与导出 API ──
class AdminAuditLogListView(generics.ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AdminAuditLogSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = AdminAuditLog.objects.all()
        q = self.request.query_params.get('q', '')
        if q:
            qs = qs.filter(Q(reason__icontains=q) | Q(target_id__icontains=q))
        return qs.order_by('-created_at')

class AdminExportUsersView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        # Write BOM to make Excel happy
        response.write('\xef\xbb\xbf')

        writer = csv.writer(response)
        writer.writerow(['ID', 'Username', 'Nickname', 'Student ID', 'Phone', 'College', 'Is Verified', 'Is Active', 'Date Joined'])

        users = User.objects.all().order_by('-date_joined')
        for u in users:
            writer.writerow([
                u.id, u.username, u.nickname, u.student_id, u.phone, u.college,
                'Yes' if u.is_verified else 'No', 'Yes' if u.is_active else 'No',
                u.date_joined.strftime('%Y-%m-%d %H:%M:%S')
            ])

        AdminAuditLog.objects.create(
            admin=request.user, action='OTHER', target_id='export',
            ip_address=get_client_ip(request), reason="导出全量用户CSV"
        )
        return response

class AdminExportTasksView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="tasks_export.csv"'
        response.write('\xef\xbb\xbf')

        writer = csv.writer(response)
        writer.writerow(['ID', 'Title', 'Category', 'Status', 'Publisher', 'Worker', 'Reward Amount', 'Hidden', 'Created At'])

        tasks = Task.objects.all().order_by('-created_at')
        for t in tasks:
            writer.writerow([
                t.id, t.title, t.category, t.status, 
                t.publisher.username if t.publisher else '',
                t.worker.username if t.worker else '',
                t.reward_amount, 'Yes' if t.is_hidden else 'No',
                t.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        AdminAuditLog.objects.create(
            admin=request.user, action='OTHER', target_id='export',
            ip_address=get_client_ip(request), reason="导出全量任务CSV"
        )
        return response
