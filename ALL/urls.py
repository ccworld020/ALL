"""
ALL项目URL配置模块

该模块定义了项目的所有URL路由规则，包括：
- 应用路由：konachan、wallhaven、hls、fs
- 静态文件服务：支持开发和生产环境
- 媒体文件服务：支持URL编码路径和大小写兼容
- 错误处理：404错误页面
"""

# ==================== Django框架导入 ====================
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
import urllib.parse

# ==================== 本地应用导入 ====================
from .views import home

urlpatterns = [
    path('', home, name='home'),
    path('k/', include('konachan.urls')),
    path('w/', include('wallhaven.urls')),
    path('hls/', include('hls.urls')),
    path('fs/', include('fs.urls')),
    path('admin/', admin.site.urls),
]

# 静态文件服务（开发和生产环境都支持）
# 优先使用staticfiles_urlpatterns（支持STATICFILES_DIRS）
# 如果STATIC_ROOT存在且已收集静态文件，则使用STATIC_ROOT
if settings.STATIC_ROOT.exists():
    # 使用STATIC_ROOT提供静态文件
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', static_serve, {'document_root': settings.STATIC_ROOT}),
    ]
else:
    # 使用STATICFILES_DIRS提供静态文件（开发模式）
    urlpatterns += staticfiles_urlpatterns()

# ==================== 媒体文件服务 ====================
def media_serve(request, path: str):
    """
    自定义媒体文件服务视图，支持URL编码的路径（包括中文等特殊字符）
    
    Args:
        request: HTTP请求对象
        path: URL编码的文件路径
    
    Returns:
        HttpResponse: 文件响应
    """
    # 解码URL编码的路径
    decoded_path = urllib.parse.unquote(path)
    return static_serve(request, decoded_path, document_root=settings.MEDIA_ROOT)

# 支持 /media/ 和 /Media/ 两种路径（兼容大小写）
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', media_serve),
    re_path(r'^Media/(?P<path>.*)$', media_serve),  # 兼容大写Media路径
]

# 404错误处理
handler404 = 'ALL.views.handler404'