from django.contrib import admin
from .models import FileInfo, FileAppertain, FileRelationship


@admin.register(FileInfo)
class FileInfoAdmin(admin.ModelAdmin):
    """文件信息管理"""
    list_display = ['name', 'md5', 'type', 'size', 'level', 'status', 'author', 'created_time']
    list_filter = ['status', 'level', 'type', 'created_time']
    search_fields = ['name', 'md5', 'album', 'subject', 'remark', 'author']
    readonly_fields = ['code', 'md5', 'created_time', 'updated_time']
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'code', 'md5', 'size', 'type', 'mime')
        }),
        ('媒体属性', {
            'fields': ('wh', 'thumbnail_addr', 'hls_addr', 'source_addr')
        }),
        ('分类和元数据', {
            'fields': ('level', 'author', 'album', 'subject', 'remark')
        }),
        ('状态和时间', {
            'fields': ('status', 'created_time', 'updated_time', 'delete_time')
        }),
        ('扩展数据', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
    )


@admin.register(FileAppertain)
class FileAppertainAdmin(admin.ModelAdmin):
    """文件归属管理（分类/标签）"""
    list_display = ['name', 'flag', 'parent', 'sort_order', 'created_time']
    list_filter = ['flag', 'parent', 'created_time']
    search_fields = ['name', 'description']
    readonly_fields = ['created_time', 'updated_time']
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'flag', 'parent', 'description', 'sort_order')
        }),
        ('时间信息', {
            'fields': ('created_time', 'updated_time')
        }),
    )


@admin.register(FileRelationship)
class FileRelationshipAdmin(admin.ModelAdmin):
    """文件关系管理"""
    list_display = ['file_info', 'file_appertain', 'created_time']
    list_filter = ['file_appertain__flag', 'created_time']
    search_fields = ['file_info__name', 'file_appertain__name']
    readonly_fields = ['created_time']
