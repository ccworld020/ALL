from django.urls import path
from . import views

app_name = 'hls'

urlpatterns = [
    path("", views.index, name="index"),
    path("get_folders/", views.get_folders, name="get_folders"),
    path("scan/", views.scan_folder, name="scan"),
    path("all/", views.all_view, name="all"),
    path("update/", views.update_hls_info, name="update"),
    path("R/", views.R_view, name="R"),
    path("api/videos/", views.get_videos_api, name="get_videos_api"),
    path("api/interaction/", views.update_video_interaction, name="update_video_interaction"),
]

