"""
数据模型模块
定义Konachan图片数据的数据库模型
"""

from django.db import models


class KImage(models.Model):
    """
    Konachan图片数据模型
    存储从Konachan API获取的图片信息
    
    字段说明：
    - id: 图片ID（主键，对应API返回的id字段）
    - tags: 图片标签（文本）
    - created_at: 创建时间戳（Unix时间戳）
    - creator_id: 创建者ID
    - author: 作者名称
    - source: 图片来源URL（可选）
    - md5: 图片MD5值（用于文件命名和去重）
    - file_size: 原始文件大小（字节）
    - file_url: 原始文件URL
    - preview_url: 预览图URL
    - preview_width: 预览图宽度（像素）
    - preview_height: 预览图高度（像素）
    - sample_url: 样本图URL
    - sample_width: 样本图宽度（像素）
    - sample_height: 样本图高度（像素）
    - sample_file_size: 样本图文件大小（字节）
    - jpeg_url: JPEG格式图片URL
    - jpeg_width: JPEG图片宽度（像素）
    - jpeg_height: JPEG图片高度（像素）
    - jpeg_file_size: JPEG图片文件大小（字节）
    - rating: 评级（safe/questionable/explicit）
    - status: 状态（active/deleted等）
    - width: 原始图片宽度（像素）
    - height: 原始图片高度（像素）
    - is_held: 是否被保留（布尔值）
    - parent_id: 父图片ID（如果有，用于关联相关图片）
    - download_status: 下载状态（'已下载'/'未下载'）
    """
    
    # 基本信息
    id = models.BigIntegerField(primary_key=True, verbose_name='图片ID')  # 对应 JSON 的 id
    tags = models.TextField(verbose_name='标签')
    created_at = models.BigIntegerField(verbose_name='创建时间戳')
    creator_id = models.IntegerField(verbose_name='创建者ID')
    author = models.CharField(max_length=255, verbose_name='作者')
    source = models.URLField(blank=True, verbose_name='来源URL')
    
    # 文件信息
    md5 = models.CharField(max_length=32, verbose_name='MD5值')
    file_size = models.BigIntegerField(verbose_name='文件大小')
    file_url = models.URLField(verbose_name='文件URL')
    
    # 预览图信息
    preview_url = models.URLField(verbose_name='预览图URL')
    preview_width = models.IntegerField(verbose_name='预览图宽度')
    preview_height = models.IntegerField(verbose_name='预览图高度')
    
    # 样本图信息
    sample_url = models.URLField(verbose_name='样本图URL')
    sample_width = models.IntegerField(verbose_name='样本图宽度')
    sample_height = models.IntegerField(verbose_name='样本图高度')
    sample_file_size = models.BigIntegerField(verbose_name='样本图文件大小')
    
    # JPEG格式信息
    jpeg_url = models.URLField(verbose_name='JPEG URL')
    jpeg_width = models.IntegerField(verbose_name='JPEG宽度')
    jpeg_height = models.IntegerField(verbose_name='JPEG高度')
    jpeg_file_size = models.BigIntegerField(verbose_name='JPEG文件大小')
    
    # 其他信息
    rating = models.CharField(max_length=10, verbose_name='评级')
    status = models.CharField(max_length=50, verbose_name='状态')
    width = models.IntegerField(verbose_name='原始宽度')
    height = models.IntegerField(verbose_name='原始高度')
    is_held = models.BooleanField(default=False, verbose_name='是否保留')
    parent_id = models.IntegerField(null=True, blank=True, verbose_name='父图片ID')
    
    # 下载状态
    download_status = models.CharField(max_length=10, verbose_name='下载状态', default='未下载')

    def __str__(self):
        """
        返回对象的字符串表示
        
        Returns:
            str: 格式为 "ID - 作者名称"
        """
        return f"{self.id} - {self.author}"

    class Meta:
        """
        模型元数据配置
        """
        verbose_name = 'Konachan图片'
        verbose_name_plural = 'Konachan图片'
        ordering = ['-id']  # 默认按ID倒序排列
