"""
Wallhaven视图函数模块
处理HTTP请求，包括数据采集、壁纸展示、下载等功能
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .api import get_data
from .models import Wallpaper
from .config import (
    PROXIES, HEADERS, PAGINATE_BY_ALL, PAGINATE_BY_GALLERY, WALLHAVEN_MEDIA_ROOT,
    REQUEST_TIMEOUT
)
from ALL.utils import (
    download_file_in_chunks, assemble_chunks, find_file_in_date_dirs,
    get_mime_type, ChunkError
)
import logging
import os
from datetime import datetime

# 获取日志记录器
logger = logging.getLogger('wallhaven')


def index(request):
    """
    首页视图函数
    显示数据采集表单页面
    
    Args:
        request: HTTP请求对象
        
    Returns:
        HttpResponse: 渲染后的首页HTML
    """
    return render(request, 'wallhaven/index.html')


def get_wallhaven_data(request):
    """
    数据采集视图函数
    接收POST请求，根据参数采集Wallhaven网站的数据并保存到数据库
    
    Args:
        request: HTTP请求对象，必须为POST方法
                包含以下POST参数：
                - start_page: 起始页码（整数，默认1）
                - end_page: 结束页码（整数，默认10）
                - limit: 每页限制数量（整数，默认24，最大100）
                - q: 搜索关键词（可选）
                - categories: 分类（111表示全部）
                - purity: 纯净度（100表示sfw）
                - sorting: 排序方式（date_added等）
                - order: 排序顺序（desc/asc）
                - toprange: 日期范围（当sorting为toplist时，可多选：1d, 3d, 1w, 1M, 3M, 6M, 1y）
    
    Returns:
        HttpResponse: 
            - 成功：返回采集结果统计信息
            - 失败：返回错误信息（状态码400/405/500）
    """
    if request.method == 'POST':
        try:
            # 获取表单参数并转换为整数
            start_page = int(request.POST.get('start_page', 1))
            end_page = int(request.POST.get('end_page', 10))
            limit = int(request.POST.get('limit', 24))
            
            # 获取可选参数
            q = request.POST.get('q', '').strip()
            categories = request.POST.get('categories', '111').strip()
            purity = request.POST.get('purity', '100').strip()
            sorting = request.POST.get('sorting', 'date_added').strip()
            order = request.POST.get('order', 'desc').strip()
            apikey = request.POST.get('apikey', '').strip()
            
            # 获取多个 topRange 参数（如果选择了排行榜）
            toprange_list = request.POST.getlist('toprange')
            
            # 参数验证：确保所有参数都大于0
            if start_page < 1 or end_page < 1 or limit < 1:
                return HttpResponse("错误：参数必须大于0！", status=400)
            
            # 参数验证：起始页码不能大于结束页码
            if start_page > end_page:
                return HttpResponse("错误：起始页码不能大于结束页码！", status=400)
            
            # 参数验证：每页限制数量不能超过100
            if limit > 100:
                return HttpResponse("错误：每页限制数量不能超过100！", status=400)
            
            # 参数验证：如果选择了NSFW，必须提供API key
            if purity == '001' and not apikey:
                return HttpResponse("错误：选择NSFW时必须填写API Key！", status=400)
            
            # 参数验证：如果选择了排行榜，必须至少选择一个日期范围
            if sorting == 'toplist':
                if not toprange_list:
                    return HttpResponse("错误：选择排行榜时必须至少选择一个日期范围！", status=400)
                # 验证日期范围值是否有效
                valid_ranges = ['1d', '3d', '1w', '1M', '3M', '6M', '1y']
                for tr in toprange_list:
                    if tr not in valid_ranges:
                        return HttpResponse(f"错误：无效的日期范围值: {tr}", status=400)
            
            logger.info(f"开始采集数据 - 起始页码: {start_page}, 结束页码: {end_page}, 每页限制: {limit}, 搜索: {q}, 纯净度: {purity}, 排序: {sorting}, 日期范围: {toprange_list if sorting == 'toplist' else 'N/A'}")
            
            # 调用数据采集函数
            result = get_data(start_page, end_page, limit, q, categories, purity, sorting, order, apikey, toprange_list)
            
            # 解析并返回结果
            success = result.get('success', 0)
            failed = result.get('failed', 0)
            total = result.get('total', 0)
            
            message = f"数据采集完成！总页数: {total}, 成功: {success}, 失败: {failed}"
            return HttpResponse(message)
            
        except ValueError as e:
            # 参数格式错误（如非整数）
            logger.error(f"参数错误: {e}")
            return HttpResponse(f"错误：参数格式不正确 - {e}", status=400)
        except Exception as e:
            # 其他未知错误
            logger.error(f"采集数据时发生错误: {e}")
            return HttpResponse(f"错误：采集过程中发生异常 - {e}", status=500)
    else:
        # 非POST请求
        return HttpResponse("错误：请使用POST方法提交表单", status=405)


def all_view(request):
    """
    所有数据展示视图函数
    显示数据库中所有已采集的壁纸数据，支持分页
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
    
    Returns:
        HttpResponse: 渲染后的数据展示页面HTML
    """
    # 获取所有壁纸数据，按ID倒序排列（最新的在前）
    wallpapers_list = Wallpaper.objects.all().order_by('-id')
    
    # 创建分页器，每页显示数量由配置决定
    paginator = Paginator(wallpapers_list, PAGINATE_BY_ALL)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        wallpapers = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        wallpapers = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        wallpapers = paginator.page(paginator.num_pages)
    
    return render(request, 'wallhaven/all.html', {
        'wallpapers': wallpapers,
        'paginator': paginator,
    })


def local_view(request):
    """
    已下载壁纸展示视图函数
    显示数据库中所有已下载的壁纸，使用瀑布流布局，支持分页
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
    
    Returns:
        HttpResponse: 渲染后的已下载壁纸页面HTML
    """
    # 筛选已下载的壁纸，按ID倒序排列
    wallpapers_list = Wallpaper.objects.filter(
        download_status='已下载'
    ).order_by('-id')
    
    # 创建分页器，每页显示数量由配置决定（瀑布流可以显示更多）
    paginator = Paginator(wallpapers_list, PAGINATE_BY_GALLERY)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        wallpapers = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        wallpapers = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        wallpapers = paginator.page(paginator.num_pages)
    
    return render(request, 'wallhaven/local.html', {
        'wallpapers': wallpapers,
        'paginator': paginator,
    })


def online_view(request):
    """
    未下载壁纸展示视图函数
    显示数据库中所有未下载的壁纸，使用瀑布流布局，支持分页
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
    
    Returns:
        HttpResponse: 渲染后的未下载壁纸页面HTML
    """
    # 筛选未下载的壁纸，按ID倒序排列
    wallpapers_list = Wallpaper.objects.filter(
        download_status='未下载'
    ).order_by('-id')
    
    # 创建分页器，每页显示数量由配置决定（瀑布流可以显示更多）
    paginator = Paginator(wallpapers_list, PAGINATE_BY_GALLERY)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        wallpapers = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        wallpapers = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        wallpapers = paginator.page(paginator.num_pages)
    
    return render(request, 'wallhaven/online.html', {
        'wallpapers': wallpapers,
        'paginator': paginator,
    })


def download_wallpaper(request, wallpaper_id):
    """
    下载壁纸视图函数
    下载指定壁纸并保存为分片文件
    
    文件存储结构：
    Media/Wallhaven/YYYYMMDD/wallpaper_id/wallpaper_id.part0, wallpaper_id.part1, ...
    
    Args:
        request: HTTP请求对象，必须为POST方法
        wallpaper_id: 壁纸ID（字符串）
    
    Returns:
        JsonResponse: 
            - 成功：{'success': True, 'message': '...'}
            - 失败：{'success': False, 'message': '...'} (状态码404/405/500)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '请使用POST方法'}, status=405)
    
    try:
        # 获取壁纸对象
        wallpaper = get_object_or_404(Wallpaper, id=wallpaper_id)
        
        # 检查是否已下载
        if "已下载" in wallpaper.download_status or "success" in wallpaper.download_status.lower():
            return JsonResponse({'success': True, 'message': '壁纸已下载'})
        
        # 获取图片URL（优先使用path字段，如果没有则使用url）
        image_url = wallpaper.path if wallpaper.path else wallpaper.url
        if not image_url:
            return JsonResponse({'success': False, 'message': '壁纸URL为空'}, status=400)
        
        # 获取当前日期（YYYYMMDD格式），用于创建日期目录
        date_str = datetime.now().strftime('%Y%m%d')
        
        # 构建基础路径：Media/Wallhaven/YYYYMMDD/wallpaper_id
        base_dir = WALLHAVEN_MEDIA_ROOT / date_str / wallpaper_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 从URL中获取文件扩展名
        file_ext = os.path.splitext(image_url)[1] or '.jpg'
        
        # 使用通用工具函数下载文件并分片保存
        try:
            success, chunk_count, errors = download_file_in_chunks(
                url=image_url,
                base_dir=base_dir,
                file_id=wallpaper_id,
                headers=HEADERS,
                proxies=PROXIES,
                timeout=REQUEST_TIMEOUT,
                file_ext=file_ext
            )
            
            if success:
                logger.info(f"download_wallpaper: 成功下载，共 {chunk_count} 个分片到 {base_dir}")
                # 更新数据库状态
                wallpaper.download_status = '已下载'
                wallpaper.save()
                return JsonResponse({
                    'success': True,
                    'message': '下载完成！'
                })
            else:
                logger.error(f"download_wallpaper: 下载失败: {errors}")
                return JsonResponse({
                    'success': False,
                    'message': f'下载失败: {"; ".join(errors)}'
                }, status=500)
                
        except Exception as e:
            logger.error(f"download_wallpaper: 处理时发生错误: {e}")
            return JsonResponse({
                'success': False,
                'message': f'发生错误: {str(e)}'
            }, status=500)
            
    except Wallpaper.DoesNotExist:
        logger.error(f"download_wallpaper: 壁纸 {wallpaper_id} 不存在")
        return JsonResponse({'success': False, 'message': '壁纸不存在'}, status=404)
    except Exception as e:
        logger.error(f"download_wallpaper: 处理壁纸 {wallpaper_id} 时发生未知错误: {e}")
        return JsonResponse({'success': False, 'message': f'发生错误: {str(e)}'}, status=500)


def get_local_wallpaper(request, wallpaper_id):
    """
    获取本地壁纸视图函数
    组装分片文件并返回完整的壁纸数据
    
    文件查找逻辑：
    1. 首先尝试当前日期目录：Media/Wallhaven/YYYYMMDD/wallpaper_id/
    2. 如果不存在，查找所有日期目录（按日期倒序），找到第一个存在的目录
    
    Args:
        request: HTTP请求对象
        wallpaper_id: 壁纸ID（字符串）
    
    Returns:
        HttpResponse: 
            - 成功：返回壁纸数据（content_type为对应的MIME类型）
            - 失败：返回404错误
    """
    try:
        # 获取壁纸对象
        wallpaper = get_object_or_404(Wallpaper, id=wallpaper_id)
        
        # 检查是否已下载
        if "未下载" in wallpaper.download_status or "pending" in wallpaper.download_status.lower():
            raise Http404("壁纸未下载")
        
        # 使用通用工具函数查找文件目录
        base_dir = find_file_in_date_dirs(
            media_root=WALLHAVEN_MEDIA_ROOT,
            file_id=wallpaper_id,
            subdir=None
        )
        
        if not base_dir:
            raise Http404("找不到壁纸分片文件")
        
        # 使用通用工具函数组装分片
        try:
            assembled_data, file_ext = assemble_chunks(
                base_dir=base_dir,
                file_id=wallpaper_id
            )
        except ChunkError as e:
            logger.error(f"get_local_wallpaper: 组装分片失败: {e}")
            raise Http404(f"获取壁纸失败: {str(e)}")
        
        logger.info(f"get_local_wallpaper: 成功组装壁纸 {wallpaper_id}，总大小 {len(assembled_data)} 字节")
        
        # 使用通用工具函数获取MIME类型
        content_type = get_mime_type(file_ext)
        
        # 返回文件响应
        response = HttpResponse(assembled_data, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{wallpaper_id}{file_ext}"'
        response['Content-Length'] = str(len(assembled_data))
        # 添加CORS支持，允许局域网访问
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        # 添加缓存控制
        response['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except Wallpaper.DoesNotExist:
        logger.error(f"get_local_wallpaper: 壁纸 {wallpaper_id} 不存在")
        raise Http404("壁纸不存在")
    except Exception as e:
        logger.error(f"get_local_wallpaper: 处理壁纸 {wallpaper_id} 时发生错误: {e}")
        raise Http404(f"获取壁纸失败: {str(e)}")