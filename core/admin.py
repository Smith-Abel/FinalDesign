from django.contrib import admin
from django.utils.html import format_html, mark_safe
from .models import Report, Task


def render_images_html(images):
    """将图片 URL 列表渲染为可预览的 HTML img 标签"""
    if not images:
        return mark_safe('<span style="color:#999;">（无图片）</span>')
    imgs = ''
    for url in images:
        imgs += (
            f'<a href="{url}" target="_blank">'
            f'<img src="{url}" style="max-height:120px;max-width:160px;'
            f'object-fit:cover;border-radius:6px;margin:4px;border:1px solid #eee;"/>'
            f'</a>'
        )
    return mark_safe(f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{imgs}</div>')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'reporter', 'target_type', 'target_id', 'reason', 'status', 'created_at']
    list_filter  = ['status', 'target_type', 'reason']
    search_fields = ['reporter__username', 'description']
    ordering = ['-created_at']
    list_editable = ['status']

    # 用自定义方法替换原始 JSONField 展示
    readonly_fields = [
        'reporter', 'target_type', 'target_id', 'target_snapshot_display',
        'reason', 'description', 'images_preview', 'created_at',
    ]
    fields = [
        'reporter', 'target_type', 'target_id', 'target_snapshot_display',
        'reason', 'description', 'images_preview',
        'status', 'result_note', 'created_at',
    ]

    @admin.display(description='被举报内容快照')
    def target_snapshot_display(self, obj):
        """将快照字典渲染为可读的 key-value 表格"""
        snapshot = obj.target_snapshot
        if not snapshot:
            return mark_safe('<span style="color:#999;">无</span>')
        rows = ''
        for k, v in snapshot.items():
            rows += f'<tr><td style="padding:2px 8px;color:#888;">{k}</td><td style="padding:2px 8px;">{v}</td></tr>'
        return mark_safe(
            f'<table style="font-size:13px;border-collapse:collapse;">{rows}</table>'
        )

    @admin.display(description='证据截图')
    def images_preview(self, obj):
        return render_images_html(obj.images)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display  = ['id', 'title', 'publisher', 'status', 'is_hidden', 'created_at']
    list_filter   = ['status', 'is_hidden', 'category']
    search_fields = ['title', 'publisher__username']
    list_editable = ['is_hidden']
    ordering = ['-created_at']

    # 在详情页展示任务图片预览
    readonly_fields = ['images_preview', 'created_at', 'updated_at']

    @admin.display(description='任务图片预览')
    def images_preview(self, obj):
        return render_images_html(obj.images)


from .models import VerifyApplication, VerifyStatus, User

@admin.register(VerifyApplication)
class VerifyApplicationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'real_name', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['user__username', 'real_name']
    list_editable = ['status']
    
    readonly_fields = ['id', 'user', 'student_id_image_preview', 'created_at']
    fields = ['id', 'user', 'real_name', 'student_id_image_preview', 'status', 'note', 'created_at']

    @admin.display(description='证件照片')
    def student_id_image_preview(self, obj):
        if not obj.student_id_image:
            return mark_safe('<span style="color:#999;">无图片</span>')
        return mark_safe(f'<a href="{obj.student_id_image}" target="_blank">'
                         f'<img src="{obj.student_id_image}" style="max-height:200px;border-radius:4px;"/></a>')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == VerifyStatus.APPROVED:
            User.objects.filter(pk=obj.user.pk).update(is_verified=True)
        elif obj.status == VerifyStatus.REJECTED:
            User.objects.filter(pk=obj.user.pk).update(is_verified=False)
