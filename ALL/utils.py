"""
通用工具模块
提供文件下载、分片处理、错误处理等通用功能
"""

import os
import math
import logging
import requests
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from django.conf import settings
from .configLoader import (
    PROXIES,
    REQUEST_TIMEOUT,
    CHUNK_SIZE_SMALL,
    CHUNK_SIZE_THRESHOLD,
    CHUNK_COUNT_SMALL,
    READ_CHUNK_SIZE,
)

logger = logging.getLogger(__name__)


class ChunkError(Exception):
    """分片处理错误异常类"""
    pass


def download_file(
    url: str,
    save_path: Path,
    headers: Optional[Dict[str, str]] = None,
    proxies: Optional[Dict[str, str]] = None,
    timeout: int = REQUEST_TIMEOUT,
    stream: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    下载文件到指定路径
    
    Args:
        url: 文件URL
        save_path: 保存路径（完整文件路径，不是目录）
        headers: 请求头字典
        proxies: 代理配置字典
        timeout: 超时时间（秒）
        stream: 是否使用流式下载
    
    Returns:
        Tuple[bool, Optional[str]]: (是否成功, 错误信息)
    """
    try:
        logger.info(f"开始下载文件: {url} -> {save_path}")
        
        response = requests.get(
            url,
            headers=headers or {},
            proxies=proxies or PROXIES,
            timeout=timeout,
            stream=stream
        )
        response.raise_for_status()
        
        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        with open(save_path, 'wb') as f:
            if stream:
                for chunk in response.iter_content(chunk_size=READ_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
            else:
                f.write(response.content)
        
        logger.info(f"文件下载成功: {save_path}")
        return True, None
        
    except requests.RequestException as e:
        error_msg = f"下载文件失败: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"保存文件时发生错误: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def download_file_in_chunks(
    url: str,
    base_dir: Path,
    file_id: str,
    headers: Optional[Dict[str, str]] = None,
    proxies: Optional[Dict[str, str]] = None,
    timeout: int = REQUEST_TIMEOUT,
    file_ext: Optional[str] = None
) -> Tuple[bool, int, List[str]]:
    """
    下载文件并保存为分片
    
    文件存储结构：
    base_dir/
        - file_id.part0, file_id.part1, ... (分片文件)
        - file_id.ext (扩展名信息文件，可选)
    
    Args:
        url: 文件URL
        base_dir: 基础目录路径
        file_id: 文件ID（用于命名分片文件）
        headers: 请求头字典
        proxies: 代理配置字典
        timeout: 超时时间（秒）
        file_ext: 文件扩展名（如果为None，将从URL中提取）
    
    Returns:
        Tuple[bool, int, List[str]]: (是否成功, 分片数量, 错误信息列表)
    """
    try:
        logger.info(f"开始分片下载: {url} -> {base_dir}/{file_id}")
        
        # 确保目录存在
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 从URL中获取文件扩展名（如果未提供）
        if not file_ext:
            file_ext = os.path.splitext(url)[1] or '.jpg'
        
        # 检查第一个分片是否已存在
        first_chunk_path = base_dir / f"{file_id}.part0"
        if first_chunk_path.exists():
            logger.info(f"文件分片已存在，跳过下载: {base_dir}")
            # 计算已存在的分片数量
            chunk_count = count_existing_chunks(base_dir, file_id)
            return True, chunk_count, []
        
        # 下载文件
        response = requests.get(
            url,
            headers=headers or {},
            proxies=proxies or PROXIES,
            timeout=timeout,
            stream=True
        )
        response.raise_for_status()
        
        # 获取文件大小（如果可用）
        content_length = response.headers.get('Content-Length')
        file_size = int(content_length) if content_length else None
        
        # 确定分片大小
        if file_size and file_size < CHUNK_SIZE_THRESHOLD:
            # 小于阈值，分成固定数量的小片
            chunk_size = math.ceil(file_size / CHUNK_COUNT_SMALL)
            logger.info(f"文件大小 {file_size} 字节，将分成 {CHUNK_COUNT_SMALL} 片，每片约 {chunk_size} 字节")
        else:
            # 大于等于阈值，按固定大小分片
            chunk_size = CHUNK_SIZE_SMALL
            if file_size:
                logger.info(f"文件大小 {file_size} 字节，将按 {chunk_size} 字节分片")
            else:
                logger.info(f"文件大小未知，将按 {chunk_size} 字节分片")
        
        # 分片保存文件
        chunk_index = 0
        current_chunk_data = b''
        error_messages = []
        
        try:
            # 以块为单位读取数据流
            for chunk in response.iter_content(chunk_size=READ_CHUNK_SIZE):
                if chunk:
                    current_chunk_data += chunk
                    
                    # 如果达到分片大小，保存当前分片
                    while len(current_chunk_data) >= chunk_size:
                        # 取出一个分片大小的数据
                        chunk_data = current_chunk_data[:chunk_size]
                        current_chunk_data = current_chunk_data[chunk_size:]
                        
                        # 保存分片文件
                        chunk_path = base_dir / f"{file_id}.part{chunk_index}"
                        with open(chunk_path, 'wb') as f:
                            f.write(chunk_data)
                        
                        logger.debug(f"保存分片 {chunk_index} ({len(chunk_data)} 字节)")
                        chunk_index += 1
            
            # 保存最后一个分片（如果有剩余数据）
            if current_chunk_data:
                chunk_path = base_dir / f"{file_id}.part{chunk_index}"
                with open(chunk_path, 'wb') as f:
                    f.write(current_chunk_data)
                logger.debug(f"保存最后分片 {chunk_index} ({len(current_chunk_data)} 字节)")
                chunk_index += 1
            
            # 保存文件扩展名信息（如果提供了扩展名）
            if file_ext:
                ext_file = base_dir / f"{file_id}.ext"
                with open(ext_file, 'w', encoding='utf-8') as f:
                    f.write(file_ext)
            
            logger.info(f"分片下载成功，共 {chunk_index} 个分片")
            return True, chunk_index, error_messages
            
        except Exception as e:
            error_msg = f"保存分片时发生错误: {str(e)}"
            logger.error(error_msg)
            error_messages.append(error_msg)
            return False, chunk_index, error_messages
            
    except requests.RequestException as e:
        error_msg = f"下载文件失败: {str(e)}"
        logger.error(error_msg)
        return False, 0, [error_msg]
    except Exception as e:
        error_msg = f"处理文件时发生错误: {str(e)}"
        logger.error(error_msg)
        return False, 0, [error_msg]


def count_existing_chunks(base_dir: Path, file_id: str) -> int:
    """
    计算已存在的分片数量
    
    Args:
        base_dir: 基础目录路径
        file_id: 文件ID
    
    Returns:
        int: 分片数量
    """
    chunk_count = 0
    while True:
        chunk_path = base_dir / f"{file_id}.part{chunk_count}"
        if chunk_path.exists():
            chunk_count += 1
        else:
            break
    return chunk_count


def assemble_chunks(
    base_dir: Path,
    file_id: str,
    date_dirs: Optional[List[Path]] = None
) -> Tuple[bytes, str]:
    """
    组装分片文件
    
    Args:
        base_dir: 基础目录路径（如果提供date_dirs，此参数将被忽略）
        file_id: 文件ID
        date_dirs: 日期目录列表（用于查找分片文件，按优先级排序）
    
    Returns:
        Tuple[bytes, str]: (文件数据, 文件扩展名)
    
    Raises:
        ChunkError: 如果找不到分片文件或组装失败
    """
    # 如果提供了日期目录列表，尝试查找分片文件
    if date_dirs:
        for date_dir in date_dirs:
            potential_dir = date_dir / file_id
            if potential_dir.exists():
                base_dir = potential_dir
                break
        else:
            raise ChunkError(f"找不到文件分片目录: {file_id}")
    
    # 查找所有分片文件
    chunk_files = []
    chunk_index = 0
    while True:
        chunk_path = base_dir / f"{file_id}.part{chunk_index}"
        if chunk_path.exists():
            chunk_files.append(chunk_path)
            chunk_index += 1
        else:
            break
    
    if not chunk_files:
        raise ChunkError(f"找不到文件分片: {file_id}")
    
    # 读取扩展名（尝试两种格式：file_id.ext 和 file_id）
    ext_file = base_dir / f"{file_id}.ext"
    file_ext = '.jpg'  # 默认扩展名
    
    # 首先尝试 .ext 文件
    if ext_file.exists():
        try:
            with open(ext_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content.startswith('.') and len(content) < 10:
                    file_ext = content
        except (IOError, UnicodeDecodeError, ValueError):
            pass
    
    # 如果没有找到 .ext 文件，尝试直接读取 file_id 文件（Konachan的格式）
    if file_ext == '.jpg':
        name_file = base_dir / file_id
        if name_file.exists():
            try:
                with open(name_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content.startswith('.') and len(content) < 10:
                        file_ext = content
            except (IOError, UnicodeDecodeError, ValueError):
                pass
    
    # 按索引顺序读取所有分片并组装
    def get_chunk_index(chunk_path: Path) -> int:
        """从分片文件路径中提取分片索引"""
        try:
            return int(chunk_path.stem.split('.part')[1])
        except (ValueError, IndexError):
            return 0
    
    assembled_data = b''
    for chunk_file in sorted(chunk_files, key=get_chunk_index):
        with open(chunk_file, 'rb') as f:
            assembled_data += f.read()
    
    logger.info(f"成功组装文件 {file_id}，共 {len(chunk_files)} 个分片，总大小 {len(assembled_data)} 字节")
    return assembled_data, file_ext


def get_mime_type(file_ext: str) -> str:
    """
    根据文件扩展名获取MIME类型
    
    Args:
        file_ext: 文件扩展名（如 '.jpg' 或 'jpg'）
    
    Returns:
        str: MIME类型
    """
    ext_lower = file_ext.lower().lstrip('.')
    mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'bmp': 'image/bmp',
        'm3u8': 'application/vnd.apple.mpegurl',
    }
    return mime_types.get(ext_lower, 'application/octet-stream')


def find_file_in_date_dirs(
    media_root: Path,
    file_id: str,
    subdir: Optional[str] = None
) -> Optional[Path]:
    """
    在日期目录中查找文件
    
    查找逻辑：
    1. 首先尝试当前日期目录
    2. 如果不存在，查找所有日期目录（按日期倒序），找到第一个存在的目录
    
    Args:
        media_root: 媒体文件根目录（如 Media/Konachan）
        file_id: 文件ID或目录名
        subdir: 子目录名（可选，如 'preview', 'sample'）
    
    Returns:
        Optional[Path]: 找到的目录路径，如果不存在则返回None
    """
    from datetime import datetime
    
    # 首先尝试当前日期
    date_str = datetime.now().strftime('%Y%m%d')
    base_dir = media_root / date_str / file_id
    if subdir:
        base_dir = base_dir / subdir
    
    if base_dir.exists():
        return base_dir
    
    # 如果当前日期目录不存在，查找所有日期目录
    if media_root.exists():
        for date_dir in sorted(media_root.iterdir(), reverse=True):
            if date_dir.is_dir():
                potential_dir = date_dir / file_id
                if subdir:
                    potential_dir = potential_dir / subdir
                if potential_dir.exists():
                    return potential_dir
    
    return None

