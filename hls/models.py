from django.db import models
import uuid


class HLSInfo(models.Model):
    """
    HLS信息模型
    用于记录扫描到的m3u8文件信息
    """
    # 基本信息
    name = models.TextField(verbose_name='文件名')
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, verbose_name='唯一标识码')
    md5 = models.CharField(max_length=32, unique=True, db_index=True, verbose_name='MD5值')
    
    # 文件信息
    size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    type = models.CharField(max_length=16, default="unknown", db_index=True, verbose_name='文件类型')
    mime = models.CharField(max_length=128, default="unknown", verbose_name='MIME类型')
    wh = models.JSONField(null=True, blank=True, verbose_name='宽高信息')
    
    # 分类信息
    level = models.CharField(max_length=16, default="General", db_index=True, verbose_name='级别')
    author = models.CharField(max_length=64, null=True, blank=True, verbose_name='作者')
    album = models.TextField(null=True, blank=True, verbose_name='专辑')
    subject = models.TextField(null=True, blank=True, verbose_name='主题')
    
    # 地址信息
    hls_addr = models.URLField(max_length=512, null=True, blank=True, verbose_name='HLS地址')
    thumbnail_addr = models.URLField(max_length=512, null=True, blank=True, verbose_name='缩略图地址')
    source_addr = models.URLField(max_length=512, null=True, blank=True, verbose_name='源文件地址')
    
    # 状态信息
    status = models.CharField(max_length=16, default="enable", db_index=True, verbose_name='状态')
    created_time = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='创建时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    remark = models.JSONField(null=True, blank=True, verbose_name='备注')

    def __str__(self):
        """返回对象的字符串表示"""
        return f"{self.name} ({self.code})"

    class Meta:
        db_table = 'hls_info'
        verbose_name = 'HLS信息'
        verbose_name_plural = 'HLS信息'
        ordering = ['-created_time']
        indexes = [
            models.Index(fields=['md5']),
            models.Index(fields=['code']),
            models.Index(fields=['status', 'created_time']),
        ]