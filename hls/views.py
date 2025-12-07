"""
HLS视图函数模块
处理HTTP请求，包括文件夹扫描、m3u8文件处理等功能
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from .models import HLSInfo
from ALL.configLoader import PAGINATE_BY_HLS, HLS_MD5_CHUNK_SIZE
import hashlib
import mimetypes
import re
import json
from pathlib import Path
import logging

# 获取日志记录器
logger = logging.getLogger('hls')


def index(request):
    """
    首页视图函数
    显示HLS文件扫描页面
    
    Args:
        request: HTTP请求对象
        
    Returns:
        HttpResponse: 渲染后的首页HTML
    """
    return render(request, 'hls/index.html')


@require_http_methods(["GET"])
def get_folders(request):
    """
    获取指定路径下的直接子文件夹列表（级联选择）
    
    GET参数:
        path: 相对路径（相对于 Media/HLS），为空则获取一级目录
    
    Returns:
        JsonResponse: 包含文件夹列表的JSON响应
    """
    try:
        base_dir = Path(settings.BASE_DIR) / 'Media' / 'HLS'
        
        # 如果目录不存在，返回空列表
        if not base_dir.exists():
            logger.warning(f'get_folders: Media/HLS 目录不存在: {base_dir}')
            return JsonResponse({
                'success': True,
                'folders': [],
                'message': f'Media/HLS 目录不存在: {base_dir}'
            })
        
        # 获取请求的路径参数
        relative_path = request.GET.get('path', '').strip()
        
        # 构建目标目录路径
        if relative_path:
            # 将正斜杠路径转换为Path对象（跨平台兼容）
            path_parts = relative_path.replace('\\', '/').split('/')
            target_dir = base_dir
            for part in path_parts:
                if part:  # 跳过空字符串
                    target_dir = target_dir / part
        else:
            target_dir = base_dir
        
        # 验证目录是否存在
        if not target_dir.exists() or not target_dir.is_dir():
            return JsonResponse({
                'success': False,
                'message': f'目录不存在: {relative_path}',
                'folders': []
            })
        
        # 获取直接子目录（不递归）
        folders = []
        try:
            for item in target_dir.iterdir():
                if item.is_dir():
                    folders.append(item.name)
        except PermissionError:
            logger.warning(f'get_folders: 无权限访问目录 {target_dir}')
            return JsonResponse({
                'success': False,
                'message': f'无权限访问目录: {relative_path}',
                'folders': []
            })
        except Exception as e:
            logger.error(f'get_folders: 获取目录 {target_dir} 失败 - {str(e)}')
            return JsonResponse({
                'success': False,
                'message': f'获取目录失败: {str(e)}',
                'folders': []
            })
        
        # 按名称排序
        folders.sort()
        
        logger.info(f'get_folders: 在 {relative_path or "根目录"} 下找到 {len(folders)} 个文件夹')
        
        return JsonResponse({
            'success': True,
            'folders': folders,
            'path': relative_path
        })
    except Exception as e:
        logger.error(f'get_folders: 获取文件夹列表失败 - {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'获取文件夹列表失败: {str(e)}',
            'folders': []
        })


@require_http_methods(["POST"])
def scan_folder(request):
    """
    扫描指定文件夹下的 m3u8 文件并保存到数据库
    
    POST参数:
        folder: 文件夹名称（相对于 Media/HLS）
        level: 文件级别（默认：General）
        author: 作者（默认：CCAV）
        album: 专辑（可选）
        subject: 主题（可选）
    
    Returns:
        JsonResponse: 包含扫描结果的JSON响应
    """
    try:
        # 获取参数
        folder_name = request.POST.get('folder', '').strip()
        level = request.POST.get('level', 'General').strip()
        author = request.POST.get('author', 'CCAV').strip()
        album = request.POST.get('album', '').strip() or None
        subject = request.POST.get('subject', '').strip() or None
        
        # 验证参数
        if not folder_name:
            return JsonResponse({
                'success': False,
                'message': '请选择文件夹'
            })
        
        if not level:
            level = 'General'
        
        if not author:
            author = 'CCAV'
        
        # 构建目标文件夹路径（支持多级目录）
        # 将正斜杠路径转换为Path对象（跨平台兼容）
        folder_path_parts = folder_name.replace('\\', '/').split('/')
        base_dir = Path(settings.BASE_DIR) / 'Media' / 'HLS'
        for part in folder_path_parts:
            if part:  # 跳过空字符串
                base_dir = base_dir / part
        
        # 验证文件夹是否存在
        if not base_dir.exists() or not base_dir.is_dir():
            return JsonResponse({
                'success': False,
                'message': f'文件夹不存在: {folder_name}'
            })
        
        # 扫描 m3u8 文件
        m3u8_files = list(base_dir.rglob('*.m3u8'))
        
        if not m3u8_files:
            return JsonResponse({
                'success': True,
                'message': '未找到 m3u8 文件',
                'scanned_count': 0,
                'saved_count': 0,
                'skipped_count': 0
            })
        
        saved_count = 0
        skipped_count = 0
        
        # 处理每个 m3u8 文件
        for m3u8_file in m3u8_files:
            try:
                # 获取 m3u8 文件所在的直接父文件夹名
                parent_folder_name = m3u8_file.parent.name
                
                # 如果父文件夹名是 MD5，直接使用；否则计算文件 MD5
                if is_md5(parent_folder_name):
                    md5_hash = parent_folder_name.lower()  # MD5 统一使用小写
                    logger.info(f'scan_folder: 使用父文件夹名作为 MD5: {md5_hash} (文件: {m3u8_file.name})')
                else:
                    md5_hash = calculate_md5(m3u8_file)
                    logger.debug(f'scan_folder: 计算文件 MD5: {md5_hash} (文件: {m3u8_file.name})')
                
                # 检查是否已存在（通过 MD5）
                if HLSInfo.objects.filter(md5=md5_hash).exists():
                    logger.info(f'scan_folder: 文件已存在，跳过: {m3u8_file.name} (MD5: {md5_hash})')
                    skipped_count += 1
                    continue
                
                # 获取文件信息
                file_size = m3u8_file.stat().st_size
                file_name = m3u8_file.name
                
                # 获取 MIME 类型
                mime_type, _ = mimetypes.guess_type(str(m3u8_file))
                if not mime_type:
                    mime_type = 'application/vnd.apple.mpegurl'
                
                # 构建相对路径（用于 URL）
                relative_path = m3u8_file.relative_to(Path(settings.BASE_DIR) / 'Media' / 'HLS')
                # 使用正确的路径大小写（HLS而不是hls），并确保路径正确编码
                # 将路径转换为URL格式，使用正斜杠，并对每个路径段进行URL编码以支持中文等特殊字符
                path_str = relative_path.as_posix()
                # 对路径的每个部分进行URL编码，确保中文字符正确处理
                import urllib.parse
                path_parts = path_str.split('/')
                encoded_parts = [urllib.parse.quote(part, safe='') for part in path_parts]
                encoded_path = '/'.join(encoded_parts)
                hls_addr = f'/media/HLS/{encoded_path}'
                
                # 创建 HLSInfo 对象
                hls_info = HLSInfo(
                    name=file_name,
                    md5=md5_hash,
                    size=file_size,
                    type='m3u8',
                    mime=mime_type,
                    level=level,
                    author=author,
                    album=album,
                    subject=subject,
                    hls_addr=hls_addr,
                    status='enable'
                )
                
                hls_info.save()
                saved_count += 1
                logger.info(f'scan_folder: 成功保存文件: {file_name} (MD5: {md5_hash})')
                
            except Exception as e:
                logger.error(f'scan_folder: 处理文件失败 {m3u8_file}: {str(e)}')
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'扫描完成',
            'scanned_count': len(m3u8_files),
            'saved_count': saved_count,
            'skipped_count': skipped_count
        })
        
    except Exception as e:
        logger.error(f'scan_folder: 扫描失败 - {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'扫描失败: {str(e)}'
        })


def is_md5(value):
    """
    检查字符串是否是有效的 MD5 值
    
    Args:
        value: 要检查的字符串
        
    Returns:
        bool: 如果是有效的 MD5 值（32位十六进制字符串）返回 True，否则返回 False
    """
    if not value or len(value) != 32:
        return False
    # 检查是否只包含十六进制字符（0-9, a-f, A-F）
    return bool(re.match(r'^[0-9a-fA-F]{32}$', value))


def calculate_md5(file_path):
    """
    计算文件的 MD5 值
    
    Args:
        file_path: 文件路径（Path 对象或字符串）
        
    Returns:
        str: 文件的 MD5 值（32位十六进制字符串）
    """
    md5_hash = hashlib.md5()
    
    with open(file_path, 'rb') as f:
        # 分块读取，避免大文件占用过多内存，块大小由配置决定
        for chunk in iter(lambda: f.read(HLS_MD5_CHUNK_SIZE), b''):
            md5_hash.update(chunk)
    
    return md5_hash.hexdigest()


def all_view(request):
    """
    所有HLS信息展示视图函数
    显示数据库中所有已扫描的m3u8文件信息，支持分页和搜索
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
                - search: 搜索关键词（字符串，可选）
    
    Returns:
        HttpResponse: 渲染后的数据展示页面HTML
    """
    # 获取所有HLS信息，按创建时间倒序排列（最新的在前）
    hls_list = HLSInfo.objects.filter(status='enable').order_by('-created_time')
    
    # 处理搜索功能
    search_query = request.GET.get('search', '').strip()
    if search_query:
        # 在文件名、作者、专辑、主题中搜索
        hls_list = hls_list.filter(
            Q(name__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(album__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
    
    # 创建分页器，每页显示数量由配置决定
    paginator = Paginator(hls_list, PAGINATE_BY_HLS)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        hls_infos = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        hls_infos = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        hls_infos = paginator.page(paginator.num_pages)
    
    return render(request, 'hls/all.html', {
        'hls_infos': hls_infos,
        'paginator': paginator,
        'search_query': search_query,
    })


@require_http_methods(["POST"])
def update_hls_info(request):
    """
    更新HLS信息视图函数
    用于修改文件的基本信息
    
    POST参数:
        code: HLS信息的唯一标识码（UUID）
        name: 文件名（可选）
        level: 级别（可选）
        author: 作者（可选）
        album: 专辑（可选）
        subject: 主题（可选）
        hls_addr: HLS地址（可选）
        remark: 备注（可选）
    
    Returns:
        JsonResponse: 包含更新结果的JSON响应
    """
    try:
        # 获取参数
        code = request.POST.get('code', '').strip()
        if not code:
            return JsonResponse({
                'success': False,
                'message': '缺少必要参数：code'
            })
        
        # 获取HLS信息对象
        hls_info = get_object_or_404(HLSInfo, code=code, status='enable')
        
        # 更新字段（如果提供了值）
        if 'name' in request.POST:
            hls_info.name = request.POST.get('name', '').strip()
        
        if 'level' in request.POST:
            level = request.POST.get('level', '').strip()
            if level:
                hls_info.level = level
        
        if 'author' in request.POST:
            author = request.POST.get('author', '').strip()
            hls_info.author = author if author else None
        
        if 'album' in request.POST:
            album = request.POST.get('album', '').strip()
            hls_info.album = album if album else None
        
        if 'subject' in request.POST:
            subject = request.POST.get('subject', '').strip()
            hls_info.subject = subject if subject else None
        
        if 'hls_addr' in request.POST:
            hls_addr = request.POST.get('hls_addr', '').strip()
            hls_info.hls_addr = hls_addr if hls_addr else None
        
        if 'remark' in request.POST:
            remark_str = request.POST.get('remark', '').strip()
            if remark_str:
                try:
                    # 尝试解析JSON字符串
                    hls_info.remark = json.loads(remark_str)
                except json.JSONDecodeError:
                    # 如果不是有效的JSON，记录错误并设置为None
                    logger.warning(f'update_hls_info: remark字段不是有效的JSON格式: {remark_str}')
                    hls_info.remark = None
            else:
                hls_info.remark = None
        
        # 保存更改
        hls_info.save()
        
        logger.info(f'update_hls_info: 成功更新HLS信息 - {hls_info.code}')
        
        return JsonResponse({
            'success': True,
            'message': '更新成功'
        })
        
    except Exception as e:
        logger.error(f'update_hls_info: 更新失败 - {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'更新失败: {str(e)}'
        })


def R_view(request):
    """
    视频滑动浏览页面视图函数
    类似抖音/小红书的上下滑动切换视频页面
    
    Args:
        request: HTTP请求对象
    
    Returns:
        HttpResponse: 渲染后的视频滑动页面HTML
    """
    return render(request, 'hls/R.html')


@require_http_methods(["GET"])
def get_videos_api(request):
    """
    获取视频列表API
    用于视频滑动页面获取视频数据，支持分页
    
    GET参数:
        page: 页码（整数，默认1）
        page_size: 每页数量（整数，默认10）
        search: 搜索关键词（字符串，可选）
    
    Returns:
        JsonResponse: 包含视频列表的JSON响应
    """
    try:
        # 获取参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        search_query = request.GET.get('search', '').strip()
        
        # 验证参数
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 50:
            page_size = 10
        
        # 获取所有有HLS地址的视频
        videos = HLSInfo.objects.filter(
            status='enable',
            hls_addr__isnull=False
        ).exclude(hls_addr='')
        
        # 处理搜索功能
        if search_query:
            videos = videos.filter(
                Q(name__icontains=search_query) |
                Q(author__icontains=search_query) |
                Q(album__icontains=search_query) |
                Q(subject__icontains=search_query)
            )
        
        # 转换为列表并随机排列
        import random
        videos_list = list(videos)
        random.shuffle(videos_list)
        
        # 创建分页器（使用列表）
        paginator = Paginator(videos_list, page_size)
        
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        
        # 构建返回数据
        video_list = []
        for video in page_obj:
            video_list.append({
                'code': str(video.code),
                'name': video.name,
                'hls_addr': video.hls_addr,
                'thumbnail_addr': video.thumbnail_addr,
                'author': video.author,
                'album': video.album,
                'subject': video.subject,
                'level': video.level,
                'created_time': video.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                'remark': video.remark,  # 包含收藏和评分信息
            })
        
        return JsonResponse({
            'success': True,
            'data': {
                'videos': video_list,
                'pagination': {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            }
        })
        
    except Exception as e:
        logger.error(f'get_videos_api: 获取视频列表失败 - {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'获取视频列表失败: {str(e)}',
            'data': {
                'videos': [],
                'pagination': {}
            }
        })


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_http_methods(["POST"])
def update_video_interaction(request):
    """
    更新视频交互信息API（收藏和评分）
    将收藏和评分信息保存到remark字段的JSON中
    
    POST参数:
        code: HLS信息的唯一标识码（UUID）
        favorite: 收藏状态（true/false，可选）
        rating: 评分（0-10的整数，可选）
    
    Returns:
        JsonResponse: 包含更新结果的JSON响应
    """
    try:
        # 获取参数
        code = request.POST.get('code', '').strip()
        if not code:
            return JsonResponse({
                'success': False,
                'message': '缺少必要参数：code'
            })
        
        # 获取HLS信息对象
        hls_info = get_object_or_404(HLSInfo, code=code, status='enable')
        
        # 获取当前的remark（JSON格式）
        remark_data = hls_info.remark if hls_info.remark else {}
        if not isinstance(remark_data, dict):
            remark_data = {}
        
        # 更新收藏状态
        if 'favorite' in request.POST:
            favorite_str = request.POST.get('favorite', '').strip().lower()
            remark_data['favorite'] = favorite_str in ('true', '1', 'yes')
        
        # 更新评分
        if 'rating' in request.POST:
            try:
                rating = int(request.POST.get('rating', '0'))
                # 限制评分范围在0-10
                if rating < 0:
                    rating = 0
                elif rating > 10:
                    rating = 10
                remark_data['rating'] = rating
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'message': '评分必须是0-10之间的整数'
                })
        
        # 保存更新后的remark
        hls_info.remark = remark_data if remark_data else None
        hls_info.save()
        
        logger.info(f'update_video_interaction: 成功更新视频交互信息 - {hls_info.code}, favorite: {remark_data.get("favorite")}, rating: {remark_data.get("rating")}')
        
        return JsonResponse({
            'success': True,
            'message': '更新成功',
            'data': {
                'favorite': remark_data.get('favorite', False),
                'rating': remark_data.get('rating', 0)
            }
        })
        
    except Exception as e:
        logger.error(f'update_video_interaction: 更新失败 - {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'更新失败: {str(e)}'
        })
