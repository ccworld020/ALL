"""
数据模型模块
定义Wallhaven壁纸数据的数据库模型
"""

from django.db import models


class Wallpaper(models.Model):
    """
    Wallhaven壁纸数据模型
    存储从Wallhaven API获取的壁纸信息
    
    字段说明：
    - id: 壁纸ID（主键，对应API返回的id字段）
    - url: 壁纸URL
    - short_url: 短链接
    - views: 浏览次数
    - favorites: 收藏次数
    - source: 来源URL
    - purity: 纯净度（sfw/sketchy/nsfw）
    - category: 分类（general/anime/people）
    - dimension_x: 宽度（像素）
    - dimension_y: 高度（像素）
    - resolution: 分辨率
    - ratio: 宽高比
    - file_size: 文件大小（字节）
    - file_type: 文件类型（image/jpeg等）
    - created_at: 创建时间
    - colors: 颜色列表（JSON格式）
    - path: 图片路径
    - thumbs: 缩略图信息（JSON格式）
    - tags: 标签列表（JSON格式）
    - download_status: 下载状态（'已下载'/'未下载'）
    """
    
    # 基本信息
    id = models.CharField(max_length=20, primary_key=True, verbose_name='壁纸ID')
    url = models.URLField(verbose_name='壁纸URL')
    short_url = models.URLField(blank=True, verbose_name='短链接')
    
    # 统计信息
    views = models.IntegerField(default=0, verbose_name='浏览次数')
    favorites = models.IntegerField(default=0, verbose_name='收藏次数')
    
    # 来源和分类
    source = models.URLField(blank=True, verbose_name='来源URL')
    purity = models.CharField(max_length=10, verbose_name='纯净度')  # sfw, sketchy, nsfw
    category = models.CharField(max_length=20, verbose_name='分类')  # general, anime, people
    
    # 图片信息
    dimension_x = models.IntegerField(verbose_name='宽度')
    dimension_y = models.IntegerField(verbose_name='高度')
    resolution = models.CharField(max_length=20, verbose_name='分辨率')
    ratio = models.CharField(max_length=10, verbose_name='宽高比')
    file_size = models.BigIntegerField(verbose_name='文件大小')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    
    # 时间信息
    created_at = models.CharField(max_length=50, verbose_name='创建时间')
    
    # JSON字段
    colors = models.JSONField(null=True, blank=True, verbose_name='颜色列表')
    thumbs = models.JSONField(null=True, blank=True, verbose_name='缩略图信息')
    tags = models.JSONField(null=True, blank=True, verbose_name='标签列表')
    
    # 图片路径（用于下载后的本地路径）
    path = models.URLField(blank=True, verbose_name='图片路径')
    
    # 下载状态
    download_status = models.CharField(max_length=10, verbose_name='下载状态', default='未下载')

    def __str__(self):
        """
        返回对象的字符串表示
        
        Returns:
            str: 格式为 "ID - 分辨率"
        """
        return f"{self.id} - {self.resolution}"

    class Meta:
        """
        模型元数据配置
        """
        verbose_name = 'Wallhaven壁纸'
        verbose_name_plural = 'Wallhaven壁纸'
        ordering = ['-id']  # 默认按ID倒序排列