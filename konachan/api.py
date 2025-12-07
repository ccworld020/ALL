"""
Konachan API数据采集模块
负责从Konachan网站API获取数据并保存到数据库
包含错误处理、重试机制等功能
"""

from .config import BASE_URL, PROXIES, REQUEST_TIMEOUT, MAX_RETRIES, BASE_DELAY
from django.db import IntegrityError
from .models import KImage
import requests
import json
import time
import logging

try:
    import cloudscraper  # type: ignore
except ImportError:  # pragma: no cover - 可选依赖
    cloudscraper = None

# 获取日志记录器
logger = logging.getLogger('konachan')

_http_client = None


def _create_http_client():
    """
    创建HTTP客户端：
    - 优先使用cloudscraper以自动处理Cloudflare挑战
    - 回退到requests.Session
    """
    if cloudscraper:
        logger.info("konachan.api: 使用cloudscraper创建会话以绕过Cloudflare。")
        session = cloudscraper.create_scraper()
    else:
        if not getattr(_create_http_client, "_missing_scraper_logged", False):
            logger.warning(
                "konachan.api: 未安装cloudscraper，将使用requests，可能会遇到403。"
            )
            _create_http_client._missing_scraper_logged = True  # type: ignore[attr-defined]
        session = requests.Session()

    if PROXIES:
        session.proxies.update(PROXIES)
    return session


def _get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = _create_http_client()
    return _http_client


def _reset_http_client():
    global _http_client
    _http_client = None


def get_data(start_page: int, end_page: int, limit: int) -> dict:
    """
    获取数据的主函数
    从Konachan API获取指定页码范围的数据并保存到数据库
    
    Args:
        start_page: 起始页码（从1开始）
        end_page: 结束页码（必须大于等于起始页码）
        limit: 每页限制数量（建议范围：1-1000）
    
    Returns:
        dict: 包含以下键的字典：
            - success (int): 成功处理的页数
            - failed (int): 失败的页数
            - total (int): 总页数
    
    Note:
        - 使用指数退避策略进行重试
        - 最大重试次数由配置决定
        - 请求间隔为1秒，避免请求过快
    """
    # 参数验证：检查参数类型
    if not isinstance(start_page, int) or not isinstance(end_page, int) or not isinstance(limit, int):
        logger.error(f"get_data: 参数类型错误 - start_page={type(start_page)}, end_page={type(end_page)}, limit={type(limit)}")
        return {"success": 0, "failed": 0, "total": 0}
    
    # 参数验证：检查参数值是否有效
    if start_page < 1 or end_page < 1 or limit < 1:
        logger.error(f"get_data: 参数值无效 - start_page={start_page}, end_page={end_page}, limit={limit} (必须大于0)")
        return {"success": 0, "failed": 0, "total": 0}
    
    # 参数验证：起始页码不能大于结束页码
    if start_page > end_page:
        logger.error(f"get_data: 起始页码不能大于结束页码 - start_page={start_page}, end_page={end_page}")
        return {"success": 0, "failed": 0, "total": 0}
    
    # 统计信息
    success_pages = 0
    failed_pages = 0
    
    # 遍历每一页
    for page_num in range(start_page, end_page + 1):
        # 设置请求参数
        params = {
            "page": page_num,
            "limit": limit
        }
        
        retry_count = 0
        page_success = False
        
        # 重试循环
        while retry_count < MAX_RETRIES:
            client = _get_http_client()
            try:
                # 请求API，添加超时设置
                response = client.get(
                    BASE_URL, 
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
                
                # 检查HTTP状态码
                if response.status_code != 200:
                    logger.warning(f"get_data: 页面 {page_num} 返回非200状态码: {response.status_code}")
                    # 记录响应内容的前500字符用于诊断
                    response_text = response.text[:500] if response.text else "(空响应)"
                    logger.warning(f"get_data: 页面 {page_num} 响应内容: {response_text}")
                    raise requests.HTTPError(f"HTTP {response.status_code}: {response.reason}")
                
                response.raise_for_status()  # 检查请求是否成功
                
                # 验证响应内容不为空
                if not response.content:
                    logger.warning(f"get_data: 页面 {page_num} 返回空响应")
                    raise ValueError("响应内容为空")
                
                # 检查响应内容类型
                response_content_type = response.headers.get('Content-Type', '').lower()
                if 'application/json' not in response_content_type and 'text/json' not in response_content_type:
                    response_text = response.text[:1000] if response.text else "(空响应)"
                    logger.warning(f"get_data: 页面 {page_num} 响应Content-Type不是JSON: {response_content_type}")
                    logger.warning(f"get_data: 页面 {page_num} 响应内容前1000字符: {response_text}")
                
                # 解析JSON，添加异常处理
                try:
                    data = response.json()
                except (ValueError, json.JSONDecodeError) as json_err:
                    # 记录详细的错误信息，包括响应内容的前1000字符
                    try:
                        response_text = response.text[:1000] if response.text else "(空响应)"
                    except Exception:
                        response_text = f"(无法解码响应，长度: {len(response.content)} 字节)"
                    response_content_type = response.headers.get('Content-Type', '未知')
                    logger.error(f"get_data: 页面 {page_num} JSON解析失败: {json_err}")
                    logger.error(f"get_data: 页面 {page_num} 响应状态码: {response.status_code}")
                    logger.error(f"get_data: 页面 {page_num} 响应Content-Type: {response_content_type}")
                    logger.error(f"get_data: 页面 {page_num} 响应内容前1000字符: {response_text}")
                    logger.error(f"get_data: 页面 {page_num} 请求URL: {response.url}")
                    logger.error(f"get_data: 页面 {page_num} 请求参数: {params}")
                    raise ValueError(f"JSON解析错误: {json_err}")
                
                # 验证数据有效性
                if data is None:
                    logger.warning(f"get_data: 页面 {page_num} 返回None数据")
                    raise ValueError("数据为None")
                
                # 保存数据，捕获可能的异常
                try:
                    save_data(data)
                    page_success = True
                    success_pages += 1
                    logger.info(f"get_data: 页面 {page_num} 处理成功")
                    break
                except Exception as save_err:
                    logger.error(f"get_data: 页面 {page_num} 保存数据时出错: {save_err}")
                    # 保存失败也视为失败，但继续重试可能无意义，所以直接跳出
                    raise

            except requests.Timeout as e:
                # 请求超时，使用指数退避策略重试
                retry_count += 1
                logger.warning(f"get_data: 页面 {page_num} 请求超时 (重试 {retry_count}/{MAX_RETRIES}): {e}")
                if retry_count < MAX_RETRIES:
                    # 指数退避策略：延迟时间 = BASE_DELAY * 2^(retry_count - 1)
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"get_data: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    
            except requests.ConnectionError as e:
                # 连接错误，使用指数退避策略重试
                retry_count += 1
                logger.warning(f"get_data: 页面 {page_num} 连接错误 (重试 {retry_count}/{MAX_RETRIES}): {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"get_data: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    
            except requests.HTTPError as e:
                # HTTP错误（如404, 500等）可能需要特殊处理
                status_code = getattr(e.response, 'status_code', None)
                if status_code == 403:
                    logger.warning(f"get_data: 页面 {page_num} 收到403，尝试刷新会话后重试。")
                    _reset_http_client()
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        delay = BASE_DELAY * (2 ** (retry_count - 1))
                        logger.info(f"get_data: 等待 {delay} 秒后重试403页面...")
                        time.sleep(delay)
                        continue
                    logger.error(f"get_data: 页面 {page_num} 持续403，放弃。")
                    failed_pages += 1
                    break
                if status_code and status_code >= 500:
                    # 服务器错误（5xx），可以重试
                    retry_count += 1
                    logger.warning(f"get_data: 页面 {page_num} HTTP服务器错误 {status_code} (重试 {retry_count}/{MAX_RETRIES}): {e}")
                    if retry_count < MAX_RETRIES:
                        delay = BASE_DELAY * (2 ** (retry_count - 1))
                        logger.info(f"get_data: 等待 {delay} 秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"get_data: 页面 {page_num} 达到最大重试次数，放弃")
                        failed_pages += 1
                        break
                else:
                    # 客户端错误（如404），通常不需要重试
                    logger.error(f"get_data: 页面 {page_num} HTTP客户端错误: {e}")
                    failed_pages += 1
                    break
                    
            except requests.RequestException as e:
                # 其他请求异常，使用指数退避策略重试
                retry_count += 1
                logger.warning(f"get_data: 页面 {page_num} 请求异常 (重试 {retry_count}/{MAX_RETRIES}): {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"get_data: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    
            except (ValueError, json.JSONDecodeError) as e:
                # JSON解析错误通常不需要重试
                logger.error(f"get_data: 页面 {page_num} 数据解析错误: {e}")
                failed_pages += 1
                break
                
            except Exception as e:
                # 捕获其他未预期的异常
                retry_count += 1
                logger.error(f"get_data: 页面 {page_num} 发生未知错误 (重试 {retry_count}/{MAX_RETRIES}): {type(e).__name__}: {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"get_data: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
        
        # 如果达到最大重试次数仍未成功
        if not page_success and retry_count >= MAX_RETRIES:
            logger.error(f"get_data: 页面 {page_num} 达到最大重试次数 ({MAX_RETRIES})，放弃处理")
            failed_pages += 1
        
        # 请求间隔，避免请求过快
        if page_num < end_page:  # 最后一页不需要等待
            time.sleep(1)
    
    # 返回统计信息
    total_pages = end_page - start_page + 1
    logger.info(f"get_data: 处理完成 - 总页数: {total_pages}, 成功: {success_pages}, 失败: {failed_pages}")
    return {"success": success_pages, "failed": failed_pages, "total": total_pages}


def save_data(data):
    """
    保存数据到数据库
    将API返回的JSON数据解析并保存到KImage模型
    
    Args:
        data (list): API返回的数据列表，每个元素是一个包含图片信息的字典
    
    Note:
        - 使用get_or_create避免重复插入
        - 如果记录已存在，则跳过（不更新）
        - 记录详细的统计信息（成功、跳过、错误）
    """
    # 输入验证：检查数据是否为空
    if not data:
        logger.warning("save_data: 接收到空数据")
        return
    
    # 输入验证：检查数据类型
    if not isinstance(data, list):
        logger.error(f"save_data: 数据类型错误，期望列表，得到 {type(data)}")
        return
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    # 遍历每条记录
    for idx, post in enumerate(data):
        # 验证post是否为字典
        if not isinstance(post, dict):
            logger.warning(f"save_data: 索引 {idx} 的数据不是字典类型，跳过")
            error_count += 1
            continue
        
        # 获取必需字段，如果缺失则跳过该记录
        post_id = post.get('id')
        if post_id is None:
            logger.warning(f"save_data: 索引 {idx} 的记录缺少id字段，跳过")
            error_count += 1
            continue
        
        try:
            # 使用get_or_create避免重复插入
            # 如果记录已存在，created为False；如果创建新记录，created为True
            obj, created = KImage.objects.get_or_create(
                id=post_id,
                defaults={
                    'tags': post.get('tags', ''),
                    'created_at': post.get('created_at', 0),
                    'creator_id': post.get('creator_id', 0),
                    'author': post.get('author', ''),
                    'source': post.get('source', '') or '',  # 处理None值
                    'md5': post.get('md5', ''),
                    'file_size': post.get('file_size', 0),
                    'file_url': post.get('file_url', ''),
                    'preview_url': post.get('preview_url', ''),
                    'preview_width': post.get('preview_width', 0),
                    'preview_height': post.get('preview_height', 0),
                    'sample_url': post.get('sample_url', ''),
                    'sample_width': post.get('sample_width', 0),
                    'sample_height': post.get('sample_height', 0),
                    'sample_file_size': post.get('sample_file_size', 0),
                    'jpeg_url': post.get('jpeg_url', ''),
                    'jpeg_width': post.get('jpeg_width', 0),
                    'jpeg_height': post.get('jpeg_height', 0),
                    'jpeg_file_size': post.get('jpeg_file_size', 0),
                    'rating': post.get('rating', ''),
                    'status': post.get('status', ''),
                    'width': post.get('width', 0),
                    'height': post.get('height', 0),
                    'is_held': post.get('is_held', False),
                    'parent_id': post.get('parent_id') or None,  # 处理None值
                    'download_status': '未下载'  # 默认状态为未下载
                }
            )
            
            if created:
                # 成功创建新记录
                success_count += 1
            else:
                # 记录已存在，跳过
                skip_count += 1
                # 可选：如果需要更新已存在的记录，可以在这里添加更新逻辑
                
        except IntegrityError as e:
            # 数据库完整性错误（如唯一约束冲突）
            logger.error(f"save_data: 保存记录 {post_id} 时发生完整性错误: {e}")
            error_count += 1
        except ValueError as e:
            # 数据类型错误
            logger.error(f"save_data: 记录 {post_id} 的数据类型错误: {e}")
            error_count += 1
        except Exception as e:
            # 其他未知错误
            logger.error(f"save_data: 保存记录 {post_id} 时发生未知错误: {e}")
            error_count += 1
    
    # 记录统计信息
    total = len(data)
    logger.info(f"save_data: 处理完成 - 总计: {total}, 成功: {success_count}, 跳过: {skip_count}, 错误: {error_count}")
