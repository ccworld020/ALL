"""
fs应用的URL配置
"""
from django.urls import path
from . import views
from . import api

urlpatterns = [
    path('ct/', views.category_tag_manage, name='category_tag_manage'),
    path('api/ct/', api.category_tag_api, name='category_tag_api'),
    path('upload/', views.file_upload, name='file_upload'),
    path('api/upload/chunk/', api.upload_chunk, name='upload_chunk'),
    path('api/upload/merge/', api.merge_chunks, name='merge_chunks'),
    path('api/upload/check/', api.check_file_exists, name='check_file_exists'),
    path('all/', views.file_list, name='file_list'),
    path('api/files/', api.file_list_api, name='file_list_api'),
    path('api/files/update/', api.file_update_api, name='file_update_api'),
    path('api/files/content/', api.file_content_api, name='file_content_api'),
    path('api/files/thumbnail/', api.thumbnail_api, name='thumbnail_api'),
    path('api/files/generate-thumbnail/', api.generate_thumbnail_api, name='generate_thumbnail_api'),
    path('api/files/delete/', api.file_delete_api, name='file_delete_api'),
    path('api/files/convert-hls/', api.convert_hls_api, name='convert_hls_api'),
    path('api/files/hls-content/', api.hls_content_api, name='hls_content_api'),
]

