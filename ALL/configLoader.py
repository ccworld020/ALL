"""
配置加载模块
================

该模块集中处理项目的所有配置读取逻辑，确保：
- 结构清晰：通过 `ConfigLoader` 对象统一读取和转换配置
- 命名规范：全部导出常量均为大写，便于在其他模块直接引用
- 注释完善：每个步骤均配有中文说明，便于维护
- 模块化拆分：不同配置段落分别定义，避免硬编码
- 错误处理完整：缺失配置文件时立即抛出清晰的错误信息
- 日志可用：通过 logger 输出关键的配置加载过程
"""

from __future__ import annotations

import logging
import os
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).with_name("config.ini")

DEFAULT_CONFIG = {
    "proxy": {
        "host": "127.0.0.1",
        "port": "10808",
    },
    "headers_common": {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "accept": "application/json",
        "accept_language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "connection": "keep-alive",
    },
    "headers_konachan": {
        "cookie": "__utmz=235754395.1762996902.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); "
        "__utma=235754395.109042595.1762996902.1762996902.1763004153.2; vote=1; "
        "cf_clearance=9qU7e_uKgB1y.CflRwzoyUHPMwP35ljhn2MAXp0RukE-1763104468-1.2.1.1-"
        "HuHtfz.3UI4w9rN1XeJScguMWFfUzjDSkm9exh_eA9aRGRnW75pQ9pkhRfC2d3.bR6Ptky7rT5wXJV_"
        "UuzMYkWw7uv7NQr9balez1JiBXJc68MCNxOenEklnaUqNAeVYRqwa1SANrQdj4MC4NgOF5MSeGdy9yl7m"
        "D7wvPDCY7dGqSi4q7NOj1Dj8VwCDUxtHodgoi94XMfIwDq1bF_WXrRJKxj2ynxCxSVtXZp6rlIk",
    },
    "headers_wallhaven": {},
    "api_konachan": {
        "base_url": "https://konachan.com/post.json",
    },
    "api_wallhaven": {
        "base_url": "https://wallhaven.cc/api/v1/search",
        "api_key": "",
    },
    "storage": {
        "media_root": "Media",
        "log_dir": "logs",
    },
    "download": {
        "request_timeout": "60",
        "max_retries": "5",
        "base_delay": "5",
        "chunk_size_small": str(1024 * 1024),
        "chunk_size_threshold": str(1024 * 1024),
        "chunk_count_small": "3",
        "read_chunk_size": "8192",
    },
    "pagination": {
        "paginate_by_all": "20",
        "paginate_by_gallery": "50",
        "paginate_by_hls": "50",
    },
    "hls": {
        "md5_chunk_size": "4096",
    },
}


class ConfigLoader:
    """封装配置解析逻辑，提供统一的读取接口。"""

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        self.config_path = config_path
        self._parser = self._load_config()

    def _load_config(self) -> ConfigParser:
        parser = ConfigParser()
        parser.read_dict(DEFAULT_CONFIG)
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件 {self.config_path} 不存在，请创建 config.ini 并提供必要的配置。"
            )
        parser.read(self.config_path, encoding="utf-8")
        logger.debug("配置文件已载入：%s", self.config_path)
        return parser

    @property
    def parser(self) -> ConfigParser:
        return self._parser

    def get(self, section: str, option: str, env_key: Optional[str] = None) -> str:
        env_value = os.getenv(env_key or option.upper())
        if env_value:
            logger.debug(
                "环境变量覆盖配置: section=%s, option=%s, value=%s",
                section,
                option,
                "***" if "key" in option.lower() else env_value,
            )
            return env_value
        return self._parser.get(section, option)

    def get_int(self, section: str, option: str, env_key: Optional[str] = None) -> int:
        return int(self.get(section, option, env_key))


try:
    import brotli  # type: ignore

    _SUPPORTS_BROTLI = True
except ImportError:
    _SUPPORTS_BROTLI = False


loader = ConfigLoader()
config = loader.parser


def _build_proxies(host: str, port: str) -> Optional[Dict[str, str]]:
    if host and port:
        proxy_url = f"http://{host}:{port}"
        return {"http": proxy_url, "https": proxy_url}
    return None


PROXY_HOST = loader.get("proxy", "host", "PROXY_HOST")
PROXY_PORT = loader.get("proxy", "port", "PROXY_PORT")
PROXIES = _build_proxies(PROXY_HOST, PROXY_PORT)

ACCEPT_ENCODING_HEADER = "gzip, deflate, br" if _SUPPORTS_BROTLI else "gzip, deflate"

COMMON_HEADERS = {
    "User-Agent": loader.get("headers_common", "user_agent", "COMMON_USER_AGENT"),
    "Accept": loader.get("headers_common", "accept"),
    "Accept-Language": loader.get("headers_common", "accept_language"),
    "Accept-Encoding": ACCEPT_ENCODING_HEADER,
    "Connection": loader.get("headers_common", "connection"),
}

KONACHAN_HEADERS = {
    **COMMON_HEADERS,
    "Cookie": loader.get("headers_konachan", "cookie", "KONACHAN_COOKIE"),
}

WALLHAVEN_HEADERS = {
    **COMMON_HEADERS,
    **{
        key: value
        for key, value in config.items("headers_wallhaven")
        if value and key not in COMMON_HEADERS
    },
}

KONACHAN_BASE_URL = loader.get("api_konachan", "base_url")
WALLHAVEN_BASE_URL = loader.get("api_wallhaven", "base_url")
WALLHAVEN_API_KEY = loader.get("api_wallhaven", "api_key", "WALLHAVEN_API_KEY")

MEDIA_ROOT = BASE_DIR / loader.get("storage", "media_root", "MEDIA_ROOT")
KONACHAN_MEDIA_ROOT = MEDIA_ROOT / "Konachan"
WALLHAVEN_MEDIA_ROOT = MEDIA_ROOT / "Wallhaven"
HLS_MEDIA_ROOT = MEDIA_ROOT / "HLS"

LOG_DIR = BASE_DIR / loader.get("storage", "log_dir", "LOG_DIR")
LOG_DIR.mkdir(exist_ok=True, parents=True)

REQUEST_TIMEOUT = loader.get_int("download", "request_timeout", "REQUEST_TIMEOUT")
MAX_RETRIES = loader.get_int("download", "max_retries", "MAX_RETRIES")
BASE_DELAY = loader.get_int("download", "base_delay", "BASE_DELAY")
CHUNK_SIZE_SMALL = loader.get_int("download", "chunk_size_small")
CHUNK_SIZE_THRESHOLD = loader.get_int("download", "chunk_size_threshold")
CHUNK_COUNT_SMALL = loader.get_int("download", "chunk_count_small")
READ_CHUNK_SIZE = loader.get_int("download", "read_chunk_size")

PAGINATE_BY_ALL = loader.get_int("pagination", "paginate_by_all")
PAGINATE_BY_GALLERY = loader.get_int("pagination", "paginate_by_gallery")
PAGINATE_BY_HLS = loader.get_int("pagination", "paginate_by_hls")

HLS_MD5_CHUNK_SIZE = loader.get_int("hls", "md5_chunk_size")

__all__ = [
    "BASE_DIR",
    "CONFIG_PATH",
    "loader",
    "config",
    "PROXY_HOST",
    "PROXY_PORT",
    "PROXIES",
    "ACCEPT_ENCODING_HEADER",
    "COMMON_HEADERS",
    "KONACHAN_HEADERS",
    "WALLHAVEN_HEADERS",
    "KONACHAN_BASE_URL",
    "WALLHAVEN_BASE_URL",
    "WALLHAVEN_API_KEY",
    "MEDIA_ROOT",
    "KONACHAN_MEDIA_ROOT",
    "WALLHAVEN_MEDIA_ROOT",
    "HLS_MEDIA_ROOT",
    "LOG_DIR",
    "REQUEST_TIMEOUT",
    "MAX_RETRIES",
    "BASE_DELAY",
    "CHUNK_SIZE_SMALL",
    "CHUNK_SIZE_THRESHOLD",
    "CHUNK_COUNT_SMALL",
    "READ_CHUNK_SIZE",
    "PAGINATE_BY_ALL",
    "PAGINATE_BY_GALLERY",
    "PAGINATE_BY_HLS",
    "HLS_MD5_CHUNK_SIZE",
]

