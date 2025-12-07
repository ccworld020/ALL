import uuid
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

# Create your models here.
class FileInfoQuerySet(models.QuerySet):
    """FileInfo的自定义查询集，提供常用查询方法"""
    
    def enabled(self):
        """返回启用状态的文件"""
        return self.filter(status='enable')
    
    def deleted(self):
        """返回已删除的文件"""
        return self.filter(status='deleted')
    
    def by_type(self, file_type):
        """按文件类型过滤"""
        return self.filter(type=file_type)
    
    def by_level(self, level):
        """按文件级别过滤"""
        return self.filter(level=level)
    
    def by_author(self, author):
        """按作者过滤"""
        return self.filter(author=author)
    
    def by_album(self, album):
        """按专辑过滤"""
        return self.filter(album=album)
    
    def by_subject(self, subject):
        """按主题过滤"""
        return self.filter(subject=subject)
    
    def search(self, keyword):
        """全文搜索（在name, md5, album, subject, remark中搜索）"""
        if not keyword:
            return self.none()
        return self.filter(
            Q(name__icontains=keyword) |
            Q(md5__icontains=keyword) |
            Q(album__icontains=keyword) |
            Q(subject__icontains=keyword) |
            Q(remark__icontains=keyword)
        )
    
    def recent(self, days=30):
        """返回最近N天的文件"""
        from django.utils import timezone
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_time__gte=cutoff_date)
    
    def large_files(self, min_size_mb=100):
        """返回大于指定大小的文件"""
        min_size_bytes = min_size_mb * 1024 * 1024
        return self.filter(size__gte=min_size_bytes)
    
    def with_thumbnail(self):
        """返回有缩略图的文件"""
        return self.exclude(thumbnail_addr__isnull=True).exclude(thumbnail_addr='')
    
    def with_hls(self):
        """返回有HLS地址的文件"""
        return self.exclude(hls_addr__isnull=True).exclude(hls_addr='')


class FileInfoManager(models.Manager):
    """FileInfo的自定义管理器"""
    
    def get_queryset(self):
        return FileInfoQuerySet(self.model, using=self._db)
    
    def enabled(self):
        return self.get_queryset().enabled()
    
    def deleted(self):
        return self.get_queryset().deleted()
    
    def by_type(self, file_type):
        return self.get_queryset().by_type(file_type)
    
    def by_level(self, level):
        return self.get_queryset().by_level(level)
    
    def by_author(self, author):
        return self.get_queryset().by_author(author)
    
    def by_album(self, album):
        return self.get_queryset().by_album(album)
    
    def by_subject(self, subject):
        return self.get_queryset().by_subject(subject)
    
    def search(self, keyword):
        return self.get_queryset().search(keyword)
    
    def recent(self, days=30):
        return self.get_queryset().recent(days)
    
    def large_files(self, min_size_mb=100):
        return self.get_queryset().large_files(min_size_mb)
    
    def with_thumbnail(self):
        return self.get_queryset().with_thumbnail()
    
    def with_hls(self):
        return self.get_queryset().with_hls()


class FileInfo(models.Model):
    """文件信息主表 - 存储文件的基本信息和元数据"""

    # 状态选择
    STATUS_CHOICES = [
        ("enable", "启用"),
        ("disabled", "禁用"),
        ("deleted", "已删除"),
        ("processing", "处理中"),
        ("failed", "处理失败"),
    ]

    # 级别选择
    LEVEL_CHOICES = [
        ("General", "普通"),
        ("Important", "重要"),
        ("Private", "私密"),
        ("Public", "公开"),
    ]

    # 基本信息
    name = models.TextField(
        verbose_name="文件名",
        help_text="文件的完整名称，包括扩展名"
    )
    code = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="文件编码",
        help_text="文件的唯一标识符（UUID）"
    )
    md5 = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name="MD5值",
        help_text="文件的MD5哈希值，用于文件去重和完整性校验",
        # MD5值应该是32位十六进制字符串
    )
    size = models.BigIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="文件大小",
        help_text="文件大小（字节）"
    )
    type = models.CharField(
        max_length=16,
        default="unknown",
        db_index=True,
        verbose_name="文件类型",
        help_text="文件扩展名类型，如：jpg, mp4, pdf等"
    )
    mime = models.CharField(
        max_length=128,
        default="unknown",
        verbose_name="MIME类型",
        help_text="文件的MIME类型，如：image/jpeg, video/mp4等"
    )

    # 媒体属性
    wh = models.JSONField(
        null=True,
        blank=True,
        verbose_name="宽高信息",
        help_text="图片或视频的宽度和高度信息，格式：{'w': width, 'h': height}"
    )

    # 分类和元数据
    level = models.CharField(
        max_length=16,
        choices=LEVEL_CHOICES,
        default="General",
        db_index=True,
        verbose_name="文件级别",
        help_text="文件的保密级别或重要性级别"
    )
    data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="文件数据",
        help_text="文件的分块存储信息或其他扩展数据"
    )

    # 时间戳
    created_time = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="创建时间",
        help_text="文件记录的创建时间"
    )
    updated_time = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name="更新时间",
        help_text="文件记录的最后更新时间"
    )
    delete_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="删除时间",
        help_text="文件被删除的时间（软删除）"
    )

    # 元数据信息
    author = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="作者",
        help_text="文件的作者或创建者"
    )
    # 注意：TextField字段在MySQL中不能直接创建索引
    # 如果需要索引，考虑使用CharField或使用前缀索引
    album = models.TextField(
        null=True,
        blank=True,
        verbose_name="专辑",
        help_text="文件所属的专辑或系列"
    )
    subject = models.TextField(
        null=True,
        blank=True,
        verbose_name="主题",
        help_text="文件的主题或分类主题"
    )

    # 地址信息
    hls_addr = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        verbose_name="HLS地址",
        help_text="视频文件的HLS流媒体地址"
    )
    thumbnail_addr = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        verbose_name="缩略图地址",
        help_text="文件的缩略图存储地址"
    )
    source_addr = models.TextField(
        null=True,
        blank=True,
        verbose_name="源文件地址",
        help_text="文件的原始存储路径"
    )

    # 状态和备注
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="enable",
        db_index=True,
        verbose_name="状态",
        help_text="文件的当前状态"
    )
    remark = models.TextField(
        null=True,
        blank=True,
        verbose_name="备注",
        help_text="文件的附加备注信息，支持特殊标记（如🔥、☆等）"
    )

    # 使用自定义管理器
    objects = FileInfoManager()

    class Meta:
        db_table = 'file_info'
        verbose_name = "文件信息"
        verbose_name_plural = "文件信息"
        ordering = ['-created_time']
        indexes = [
            # 复合索引：状态和时间（用于按状态筛选并按时间排序）
            models.Index(fields=['status', 'created_time'], name='fi_st_crt_idx'),
            # 复合索引：类型和状态（用于按类型和状态筛选）
            models.Index(fields=['type', 'status'], name='fi_tp_st_idx'),
            # 复合索引：级别和状态（用于按级别和状态筛选）
            models.Index(fields=['level', 'status'], name='fi_lv_st_idx'),
            # 复合索引：作者和时间（用于按作者筛选并按时间排序）
            models.Index(fields=['author', 'created_time'], name='fi_author_crt_idx'),
            # 复合索引：状态、类型和时间（用于复杂查询）
            models.Index(fields=['status', 'type', 'created_time'], name='fi_st_tp_crt_idx'),
            # 复合索引：状态、级别和时间（用于复杂查询）
            models.Index(fields=['status', 'level', 'created_time'], name='fi_st_lv_crt_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.md5[:8]}...)"

    def is_deleted(self):
        """检查文件是否已删除"""
        return self.status == "deleted" or self.delete_time is not None
    
    def is_enabled(self):
        """检查文件是否启用"""
        return self.status == "enable"
    
    def get_size_display(self):
        """获取格式化的文件大小"""
        if self.size == 0:
            return "0 B"
        size = float(self.size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def get_width_height(self):
        """获取宽高信息，返回元组(width, height)"""
        if self.wh and isinstance(self.wh, dict):
            return (self.wh.get('w'), self.wh.get('h'))
        return (None, None)
    
    def has_hls(self):
        """检查是否有HLS地址"""
        return bool(self.hls_addr)
    
    def has_thumbnail(self):
        """检查是否有缩略图"""
        return bool(self.thumbnail_addr)


class FileAppertain(models.Model):
    """文件归属表 - 用于分类和标签管理，支持层级结构"""

    # 类型标识常量
    FLAG_CATEGORY = "C"
    FLAG_TAG = "T"
    
    FLAG_CHOICES = [
        (FLAG_CATEGORY, "分类"),
        (FLAG_TAG, "标签"),
    ]

    name = models.CharField(
        max_length=128,
        verbose_name="名称",
        help_text="分类或标签的名称"
    )
    flag = models.CharField(
        max_length=1,
        choices=FLAG_CHOICES,
        db_index=True,
        verbose_name="类型标识",
        help_text="C表示分类（Catalogue），T表示标签（Tag）"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父级",
        help_text="父级分类或标签，用于构建层级结构"
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="描述",
        help_text="分类或标签的详细描述"
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name="排序顺序",
        help_text="用于控制分类或标签的显示顺序"
    )
    created_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    updated_time = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        db_table = 'file_appertain'
        verbose_name = "文件归属"
        verbose_name_plural = "文件归属"
        unique_together = [['name', 'flag']]  # 同一类型下名称唯一
        indexes = [
            models.Index(fields=['flag', 'parent'], name='fa_flag_parent_idx'),
            models.Index(fields=['flag', 'sort_order'], name='fa_flag_sort_idx'),
            models.Index(fields=['parent', 'sort_order'], name='fa_parent_sort_idx'),
        ]
        ordering = ['flag', 'sort_order', 'name']

    def __str__(self):
        parent_str = f" ({self.parent.name})" if self.parent else ""
        flag_str = "分类" if self.flag == "C" else "标签"
        return f"{flag_str}: {self.name}{parent_str}"

    def get_full_path(self):
        """获取完整的层级路径"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return " > ".join(path)
    
    def is_category(self):
        """判断是否为分类"""
        return self.flag == "C"
    
    def is_tag(self):
        """判断是否为标签"""
        return self.flag == "T"
    
    def get_children(self):
        """获取所有子项"""
        return self.children.all()
    
    def get_all_descendants(self):
        """获取所有后代（递归）"""
        descendants = []
        children = self.get_children()
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants


class FileRelationship(models.Model):
    """文件关系表 - 文件与分类/标签的多对多关系"""

    file_info = models.ForeignKey(
        FileInfo,
        on_delete=models.CASCADE,
        related_name='appertains',
        db_index=True,
        verbose_name="文件",
        help_text="关联的文件"
    )
    file_appertain = models.ForeignKey(
        FileAppertain,
        on_delete=models.CASCADE,
        related_name='file_relationships',
        db_index=True,
        verbose_name="归属",
        help_text="关联的分类或标签"
    )
    created_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="关联时间",
        help_text="建立关联关系的时间"
    )

    class Meta:
        db_table = 'file_relationship'
        verbose_name = "文件关系"
        verbose_name_plural = "文件关系"
        unique_together = [['file_info', 'file_appertain']]  # 防止重复关联
        # unique_together会自动创建(file_info, file_appertain)的唯一索引
        indexes = [
            # 反向查询索引：按归属查询并按时间排序
            models.Index(fields=['file_appertain', 'created_time'], name='fr_app_crt_idx'),
            # 按文件查询并按时间排序
            models.Index(fields=['file_info', 'created_time'], name='fr_file_crt_idx'),
        ]

    def __str__(self):
        return f"{self.file_info.name} -> {self.file_appertain.name}"
