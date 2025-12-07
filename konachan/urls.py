"""
Konachan应用URL配置
"""

from django.urls import path
from . import views

app_name = 'konachan'

urlpatterns = [
    path("", views.index, name="index"),
    path("get_data/", views.get_konachan_data, name="get_konachan_data"),
    path("all/", views.all_view, name="all_view"),
    path("local/", views.local_view, name="local_view"),
    path("online/", views.online_view, name="online_view"),
    path("download/<int:image_id>/", views.download_image, name="download_image"),
    path("image/<int:image_id>/<str:image_type>/", views.get_local_image, name="get_local_image"),
]