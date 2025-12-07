"""
Wallhaven API数据采集模块
负责从Wallhaven网站API获取数据并保存到数据库
包含错误处理、重试机制等功能
"""

from .config import BASE_URL, PROXIES, HEADERS, REQUEST_TIMEOUT, MAX_RETRIES, BASE_DELAY, WALLHAVEN_API_KEY
from django.db import IntegrityError
from .models import Wallpaper
import requests
import json
import time
import logging

# 获取日志记录器
logger = logging.getLogger('wallhaven')


def get_data(
    start_page: int,
    end_page: int,
    limit: int,
    query: str = '',
    categories: str = '111',
    purity: str = '100',
    sorting: str = 'date_added',
    order: str = 'desc',
    apikey: str = '',
    toprange_list: list = None
) -> dict:
    """
    获取数据的主函数
    从Wallhaven API获取指定页码范围的数据并保存到数据库
    
    Args:
        start_page: 起始页码（从1开始）
        end_page: 结束页码（必须大于等于起始页码）
        limit: 每页限制数量（建议范围：1-100）
        query: 搜索关键词（可选）
        categories: 分类（111表示全部，100表示general，010表示anime，001表示people）
        purity: 纯净度（100表示sfw，010表示sketchy，001表示nsfw）
        sorting: 排序方式（date_added, relevance, random, views, favorites, toplist）
        order: 排序顺序（desc, asc）
        apikey: API密钥（选择NSFW时必须提供，如果未提供则使用配置中的默认值）
        toprange_list: 日期范围列表（当sorting为toplist时，可包含多个值：1d, 3d, 1w, 1M, 3M, 6M, 1y）
    
    Returns:
        dict: 包含以下键的字典：
            - success (int): 成功处理的页数
            - failed (int): 失败的页数
            - total (int): 总页数
    
    Note:
        - 使用指数退避策略进行重试
        - 最大重试次数由配置决定
        - 请求间隔为1秒，避免请求过快
        - 选择NSFW时必须提供API key
        - 当sorting为toplist且提供了toprange_list时，会为每个日期范围分别发送请求
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
    
    # 如果没有提供API key，使用配置中的默认值
    if not apikey:
        apikey = WALLHAVEN_API_KEY
    
    # 如果选择了排行榜且有日期范围列表，为每个日期范围分别处理
    if sorting == 'toplist' and toprange_list:
        # 统计信息（累计所有日期范围的结果）
        total_success_pages = 0
        total_failed_pages = 0
        total_pages_count = 0
        
        # 为每个日期范围分别处理
        for toprange in toprange_list:
            logger.info(f"get_data: 处理日期范围 {toprange}")
            result = _get_data_for_range(
                start_page, end_page, limit, query, categories, purity, 
                sorting, order, apikey, toprange
            )
            total_success_pages += result.get('success', 0)
            total_failed_pages += result.get('failed', 0)
            total_pages_count += result.get('total', 0)
        
        logger.info(f"get_data: 所有日期范围处理完成 - 总页数: {total_pages_count}, 成功: {total_success_pages}, 失败: {total_failed_pages}")
        return {"success": total_success_pages, "failed": total_failed_pages, "total": total_pages_count}
    
    # 非排行榜模式或没有日期范围列表，使用原有逻辑
    return _get_data_for_range(
        start_page, end_page, limit, query, categories, purity, 
        sorting, order, apikey, None
    )


def _get_data_for_range(
    start_page: int,
    end_page: int,
    limit: int,
    query: str = '',
    categories: str = '111',
    purity: str = '100',
    sorting: str = 'date_added',
    order: str = 'desc',
    apikey: str = '',
    toprange: str = None
) -> dict:
    """
    为单个日期范围获取数据（内部函数）
    
    Args:
        start_page: 起始页码（从1开始）
        end_page: 结束页码（必须大于等于起始页码）
        limit: 每页限制数量（建议范围：1-100）
        query: 搜索关键词（可选）
        categories: 分类（111表示全部，100表示general，010表示anime，001表示people）
        purity: 纯净度（100表示sfw，010表示sketchy，001表示nsfw）
        sorting: 排序方式（date_added, relevance, random, views, favorites, toplist）
        order: 排序顺序（desc, asc）
        apikey: API密钥
        toprange: 日期范围（1d, 3d, 1w, 1M, 3M, 6M, 1y），仅在sorting为toplist时使用
    
    Returns:
        dict: 包含以下键的字典：
            - success (int): 成功处理的页数
            - failed (int): 失败的页数
            - total (int): 总页数
    """
    # 统计信息
    success_pages = 0
    failed_pages = 0
    
    # 遍历每一页
    for page_num in range(start_page, end_page + 1):
        # 设置请求参数
        params = {
            "page": page_num,
            "limit": limit,
            "categories": categories,
            "purity": purity,
            "sorting": sorting,
            "order": order
        }
        
        # 如果有搜索关键词，添加到参数中
        if query:
            params["q"] = query
        
        # 如果选择了排行榜且有日期范围，添加到参数中
        if sorting == 'toplist' and toprange:
            params["topRange"] = toprange
        
        # 如果有API key，添加到URL参数中（Wallhaven API要求）
        if apikey:
            params["apikey"] = apikey
        
        retry_count = 0
        page_success = False
        
        # 重试循环
        while retry_count < MAX_RETRIES:
            try:
                # 请求API，添加超时设置
                response = requests.get(
                    BASE_URL, 
                    headers=HEADERS, 
                    proxies=PROXIES, 
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
                
                # 检查HTTP状态码
                if response.status_code != 200:
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 返回非200状态码: {response.status_code}")
                    # 记录响应内容的前500字符用于诊断
                    response_text = response.text[:500] if response.text else "(空响应)"
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 响应内容: {response_text}")
                    raise requests.HTTPError(f"HTTP {response.status_code}: {response.reason}")
                
                response.raise_for_status()  # 检查请求是否成功
                
                # 验证响应内容不为空
                if not response.content:
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 返回空响应")
                    raise ValueError("响应内容为空")
                
                # 检查响应内容类型
                response_content_type = response.headers.get('Content-Type', '').lower()
                if 'application/json' not in response_content_type and 'text/json' not in response_content_type:
                    response_text = response.text[:1000] if response.text else "(空响应)"
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 响应Content-Type不是JSON: {response_content_type}")
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 响应内容前1000字符: {response_text}")
                
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
                    logger.error(f"_get_data_for_range: 页面 {page_num} JSON解析失败: {json_err}")
                    logger.error(f"_get_data_for_range: 页面 {page_num} 响应状态码: {response.status_code}")
                    logger.error(f"_get_data_for_range: 页面 {page_num} 响应Content-Type: {response_content_type}")
                    logger.error(f"_get_data_for_range: 页面 {page_num} 响应内容前1000字符: {response_text}")
                    logger.error(f"_get_data_for_range: 页面 {page_num} 请求URL: {response.url}")
                    logger.error(f"_get_data_for_range: 页面 {page_num} 请求参数: {params}")
                    raise ValueError(f"JSON解析错误: {json_err}")
                
                # 验证数据有效性
                if data is None:
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 返回None数据")
                    raise ValueError("数据为None")
                
                # 检查API返回的数据结构
                if 'data' not in data:
                    logger.warning(f"_get_data_for_range: 页面 {page_num} 返回数据格式错误，缺少data字段")
                    raise ValueError("API返回数据格式错误")
                
                # 保存数据，捕获可能的异常
                try:
                    save_data(data['data'])
                    page_success = True
                    success_pages += 1
                    logger.info(f"_get_data_for_range: 页面 {page_num} 处理成功")
                    break
                except Exception as save_err:
                    logger.error(f"_get_data_for_range: 页面 {page_num} 保存数据时出错: {save_err}")
                    raise

            except requests.Timeout as e:
                # 请求超时，使用指数退避策略重试
                retry_count += 1
                logger.warning(f"_get_data_for_range: 页面 {page_num} 请求超时 (重试 {retry_count}/{MAX_RETRIES}): {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"_get_data_for_range: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    
            except requests.ConnectionError as e:
                # 连接错误，使用指数退避策略重试
                retry_count += 1
                logger.warning(f"_get_data_for_range: 页面 {page_num} 连接错误 (重试 {retry_count}/{MAX_RETRIES}): {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"_get_data_for_range: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    
            except requests.HTTPError as e:
                # HTTP错误（如404, 500等）可能需要特殊处理
                status_code = getattr(e.response, 'status_code', None)
                if status_code and status_code >= 500:
                    # 服务器错误（5xx），可以重试
                    retry_count += 1
                    logger.warning(f"_get_data_for_range: 页面 {page_num} HTTP服务器错误 {status_code} (重试 {retry_count}/{MAX_RETRIES}): {e}")
                    if retry_count < MAX_RETRIES:
                        delay = BASE_DELAY * (2 ** (retry_count - 1))
                        logger.info(f"_get_data_for_range: 等待 {delay} 秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"_get_data_for_range: 页面 {page_num} 达到最大重试次数，放弃")
                        failed_pages += 1
                        break
                else:
                    # 客户端错误（如404），通常不需要重试
                    logger.error(f"_get_data_for_range: 页面 {page_num} HTTP客户端错误: {e}")
                    failed_pages += 1
                    break
                    
            except requests.RequestException as e:
                # 其他请求异常，使用指数退避策略重试
                retry_count += 1
                logger.warning(f"_get_data_for_range: 页面 {page_num} 请求异常 (重试 {retry_count}/{MAX_RETRIES}): {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"_get_data_for_range: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    
            except (ValueError, json.JSONDecodeError) as e:
                # JSON解析错误通常不需要重试
                logger.error(f"_get_data_for_range: 页面 {page_num} 数据解析错误: {e}")
                failed_pages += 1
                break
                
            except Exception as e:
                # 捕获其他未预期的异常
                retry_count += 1
                logger.error(f"_get_data_for_range: 页面 {page_num} 发生未知错误 (重试 {retry_count}/{MAX_RETRIES}): {type(e).__name__}: {e}")
                if retry_count < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (retry_count - 1))
                    logger.info(f"_get_data_for_range: 等待 {delay} 秒后重试...")
                    time.sleep(delay)
        
        # 如果达到最大重试次数仍未成功
        if not page_success and retry_count >= MAX_RETRIES:
            logger.error(f"_get_data_for_range: 页面 {page_num} 达到最大重试次数 ({MAX_RETRIES})，放弃处理")
            failed_pages += 1
        
        # 请求间隔，避免请求过快
        if page_num < end_page:  # 最后一页不需要等待
            time.sleep(1)
    
    # 返回统计信息
    total_pages = end_page - start_page + 1
    logger.info(f"_get_data_for_range: 处理完成 - 总页数: {total_pages}, 成功: {success_pages}, 失败: {failed_pages}")
    return {"success": success_pages, "failed": failed_pages, "total": total_pages}


def save_data(data):
    """
    保存数据到数据库
    将API返回的JSON数据解析并保存到Wallpaper模型
    
    Args:
        data (list): API返回的数据列表，每个元素是一个包含壁纸信息的字典
    
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
    for idx, wallpaper in enumerate(data):
        # 验证wallpaper是否为字典
        if not isinstance(wallpaper, dict):
            logger.warning(f"save_data: 索引 {idx} 的数据不是字典类型，跳过")
            error_count += 1
            continue
        
        # 获取必需字段，如果缺失则跳过该记录
        wallpaper_id = wallpaper.get('id')
        if wallpaper_id is None:
            logger.warning(f"save_data: 索引 {idx} 的记录缺少id字段，跳过")
            error_count += 1
            continue
        
        try:
            # 使用get_or_create避免重复插入
            obj, created = Wallpaper.objects.get_or_create(
                id=str(wallpaper_id),
                defaults={
                    'url': wallpaper.get('url', ''),
                    'short_url': wallpaper.get('short_url', ''),
                    'views': wallpaper.get('views', 0),
                    'favorites': wallpaper.get('favorites', 0),
                    'source': wallpaper.get('source', '') or '',
                    'purity': wallpaper.get('purity', 'sfw'),
                    'category': wallpaper.get('category', 'general'),
                    'dimension_x': wallpaper.get('dimension_x', 0),
                    'dimension_y': wallpaper.get('dimension_y', 0),
                    'resolution': wallpaper.get('resolution', ''),
                    'ratio': wallpaper.get('ratio', ''),
                    'file_size': wallpaper.get('file_size', 0),
                    'file_type': wallpaper.get('file_type', ''),
                    'created_at': wallpaper.get('created_at', ''),
                    'colors': wallpaper.get('colors', []),
                    'thumbs': wallpaper.get('thumbs', {}),
                    'tags': wallpaper.get('tags', []),
                    'path': wallpaper.get('path', ''),
                    'download_status': '未下载'
                }
            )
            
            if created:
                # 成功创建新记录
                success_count += 1
            else:
                # 记录已存在，跳过
                skip_count += 1
                
        except IntegrityError as e:
            # 数据库完整性错误（如唯一约束冲突）
            logger.error(f"save_data: 保存记录 {wallpaper_id} 时发生完整性错误: {e}")
            error_count += 1
        except ValueError as e:
            # 数据类型错误
            logger.error(f"save_data: 记录 {wallpaper_id} 的数据类型错误: {e}")
            error_count += 1
        except Exception as e:
            # 其他未知错误
            logger.error(f"save_data: 保存记录 {wallpaper_id} 时发生未知错误: {e}")
            error_count += 1
    
    # 记录统计信息
    total = len(data)
    logger.info(f"save_data: 处理完成 - 总计: {total}, 成功: {success_count}, 跳过: {skip_count}, 错误: {error_count}")
