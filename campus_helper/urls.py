from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
import os

# Web 管理后台目录绝对路径
WEB_ADMIN_ROOT = os.path.join(settings.BASE_DIR, 'web_admin')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),

    # ── Web 管理后台静态托管 ──
    # 访问 /web/ 默认返回 index.html 登录页
    path('web/', lambda req: serve(req, 'index.html', document_root=WEB_ADMIN_ROOT)),
    # 访问 /web/<path> 返回对应文件（css/js/html）
    re_path(r'^web/(?P<path>.+)$', serve, {'document_root': WEB_ADMIN_ROOT}),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

