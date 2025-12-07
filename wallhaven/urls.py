from django.urls import path
from . import views

app_name = 'wallhaven'

urlpatterns = [
    path("", views.index, name="index"),
    path("get_data/", views.get_wallhaven_data, name="get_wallhaven_data"),
    path("all/", views.all_view, name="all_view"),
    path("local/", views.local_view, name="local_view"),
    path("online/", views.online_view, name="online_view"),
    path("download/<str:wallpaper_id>/", views.download_wallpaper, name="download_wallpaper"),
    path("wallpaper/<str:wallpaper_id>/", views.get_local_wallpaper, name="get_local_wallpaper"),
]
