"""
Konachan应用配置模块
从项目统一配置模块导入配置信息
"""

from ALL.configLoader import (
    KONACHAN_BASE_URL as BASE_URL,
    KONACHAN_HEADERS as HEADERS,
    PROXIES,
    KONACHAN_MEDIA_ROOT,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    BASE_DELAY,
    PAGINATE_BY_ALL,
    PAGINATE_BY_GALLERY
)
