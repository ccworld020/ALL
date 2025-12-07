"""
Konachan视图函数模块
处理HTTP请求，包括数据采集、图片展示、下载等功能
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .api import get_data
from .models import KImage
from .config import PROXIES, HEADERS, PAGINATE_BY_ALL, PAGINATE_BY_GALLERY, KONACHAN_MEDIA_ROOT
from ALL.utils import (
    download_file_in_chunks, assemble_chunks, find_file_in_date_dirs,
    get_mime_type, ChunkError
)
import logging
from datetime import datetime

# 获取日志记录器
logger = logging.getLogger('konachan')


def index(request):
    """
    首页视图函数
    显示数据采集表单页面
    
    Args:
        request: HTTP请求对象
        
    Returns:
        HttpResponse: 渲染后的首页HTML
    """
    return render(request, 'konachan/index.html')


def get_konachan_data(request):
    """
    数据采集视图函数
    接收POST请求，根据参数采集Konachan网站的数据并保存到数据库
    
    Args:
        request: HTTP请求对象，必须为POST方法
                包含以下POST参数：
                - start_page: 起始页码（整数，默认1）
                - end_page: 结束页码（整数，默认10）
                - limit: 每页限制数量（整数，默认500，最大1000）
    
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
            limit = int(request.POST.get('limit', 500))
            
            # 参数验证：确保所有参数都大于0
            if start_page < 1 or end_page < 1 or limit < 1:
                return HttpResponse("错误：参数必须大于0！", status=400)
            
            # 参数验证：起始页码不能大于结束页码
            if start_page > end_page:
                return HttpResponse("错误：起始页码不能大于结束页码！", status=400)
            
            # 参数验证：每页限制数量不能超过1000
            if limit > 1000:
                return HttpResponse("错误：每页限制数量不能超过1000！", status=400)
            
            logger.info(f"开始采集数据 - 起始页码: {start_page}, 结束页码: {end_page}, 每页限制: {limit}")
            
            # 调用数据采集函数
            result = get_data(start_page, end_page, limit)
            
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
    显示数据库中所有已采集的图片数据，支持分页
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
    
    Returns:
        HttpResponse: 渲染后的数据展示页面HTML
    """
    # 获取所有图片数据，按ID倒序排列（最新的在前）
    images_list = KImage.objects.all().order_by('-id')
    
    # 创建分页器，每页显示数量由配置决定
    paginator = Paginator(images_list, PAGINATE_BY_ALL)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        images = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        images = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        images = paginator.page(paginator.num_pages)
    
    return render(request, 'konachan/all.html', {
        'images': images,
        'paginator': paginator,
    })


def local_view(request):
    """
    已下载图片展示视图函数
    显示数据库中所有已下载的图片，使用瀑布流布局，支持分页
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
    
    Returns:
        HttpResponse: 渲染后的已下载图片页面HTML
    """
    # 筛选已下载的图片，按ID倒序排列
    images_list = KImage.objects.filter(
        download_status='已下载'
    ).order_by('-id')
    
    # 创建分页器，每页显示数量由配置决定（瀑布流可以显示更多）
    paginator = Paginator(images_list, PAGINATE_BY_GALLERY)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        images = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        images = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        images = paginator.page(paginator.num_pages)
    
    return render(request, 'konachan/local.html', {
        'images': images,
        'paginator': paginator,
    })


def online_view(request):
    """
    未下载图片展示视图函数
    显示数据库中所有未下载的图片，使用瀑布流布局，支持分页
    
    Args:
        request: HTTP请求对象
                可选的GET参数：
                - page: 页码（整数，默认1）
    
    Returns:
        HttpResponse: 渲染后的未下载图片页面HTML
    """
    # 筛选未下载的图片，按ID倒序排列
    images_list = KImage.objects.filter(
        download_status='未下载'
    ).order_by('-id')
    
    # 创建分页器，每页显示数量由配置决定（瀑布流可以显示更多）
    paginator = Paginator(images_list, PAGINATE_BY_GALLERY)
    
    # 获取当前页码
    page = request.GET.get('page', 1)
    try:
        images = paginator.page(page)
    except PageNotAnInteger:
        # 如果页码不是整数，显示第一页
        images = paginator.page(1)
    except EmptyPage:
        # 如果页码超出范围，显示最后一页
        images = paginator.page(paginator.num_pages)
    
    return render(request, 'konachan/online.html', {
        'images': images,
        'paginator': paginator,
    })


def download_image(request, image_id):
    """
    下载图片视图函数
    下载指定图片的preview、sample、jpeg三个版本，并保存为分片文件
    
    文件存储结构：
    Media/Konachan/YYYYMMDD/md5值/preview|sample|jpeg/
        - md5值.part0, md5值.part1, ... (分片文件)
        - md5值.ext (扩展名信息文件，文本格式)
    
    Args:
        request: HTTP请求对象，必须为POST方法
        image_id: 图片ID（整数）
    
    Returns:
        JsonResponse: 
            - 成功：{'success': True, 'message': '...', 'success_count': int, 'failed_count': int, 'errors': list}
            - 失败：{'success': False, 'message': '...', 'errors': list} (状态码404/405/500)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '请使用POST方法'}, status=405)
    
    try:
        # 获取图片对象
        image = get_object_or_404(KImage, id=image_id)
        
        # 检查是否已下载
        if "已下载" in image.download_status or "success" in image.download_status.lower():
            return JsonResponse({'success': True, 'message': '图片已下载'})
        
        # 获取当前日期（YYYYMMDD格式），用于创建日期目录
        date_str = datetime.now().strftime('%Y%m%d')
        
        # 构建基础路径：Media/Konachan/YYYYMMDD/md5值
        base_dir = KONACHAN_MEDIA_ROOT / date_str / image.md5
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义要下载的URL和对应的子目录
        # 每个图片需要下载三个版本：preview（预览）、sample（样本）、jpeg（JPEG格式）
        download_tasks = [
            ('preview_url', 'preview'),
            ('sample_url', 'sample'),
            ('jpeg_url', 'jpeg')
        ]
        
        success_count = 0
        failed_count = 0
        error_messages = []
        
        # 遍历每个下载任务
        for url_field, subdir in download_tasks:
            # 获取URL
            url = getattr(image, url_field, None)
            if not url:
                logger.warning(f"download_image: 图片 {image_id} 的 {url_field} 为空，跳过")
                failed_count += 1
                error_messages.append(f"{url_field} URL为空")
                continue
            
            try:
                # 创建子目录：Media/Konachan/YYYYMMDD/md5值/preview|sample|jpeg
                subdir_path = base_dir / subdir
                subdir_path.mkdir(parents=True, exist_ok=True)
                
                # 使用通用工具函数下载文件并分片保存
                success, chunk_count, errors = download_file_in_chunks(
                    url=url,
                    base_dir=subdir_path,
                    file_id=image.md5,
                    headers=HEADERS,
                    proxies=PROXIES
                )
                
                if success:
                    logger.info(f"download_image: 成功下载 {url_field}，共 {chunk_count} 个分片")
                    success_count += 1
                else:
                    logger.error(f"download_image: 下载 {url_field} 失败")
                    failed_count += 1
                    error_messages.extend(errors)
                
            except Exception as e:
                # 其他处理错误
                error_msg = f"{url_field} 处理失败: {str(e)}"
                logger.error(f"download_image: {error_msg}")
                failed_count += 1
                error_messages.append(error_msg)
        
        # 如果至少有一个文件下载成功，更新数据库状态
        if success_count > 0:
            image.download_status = '已下载'
            image.save()
            logger.info(f"download_image: 图片 {image_id} 下载完成，成功: {success_count}, 失败: {failed_count}")
            return JsonResponse({
                'success': True,
                'message': f'下载完成！成功: {success_count}, 失败: {failed_count}',
                'success_count': success_count,
                'failed_count': failed_count,
                'errors': error_messages
            })
        else:
            # 所有下载都失败
            logger.error(f"download_image: 图片 {image_id} 所有下载都失败")
            return JsonResponse({
                'success': False,
                'message': '所有下载都失败',
                'errors': error_messages
            }, status=500)
            
    except KImage.DoesNotExist:
        # 图片不存在
        logger.error(f"download_image: 图片 {image_id} 不存在")
        return JsonResponse({'success': False, 'message': '图片不存在'}, status=404)
    except Exception as e:
        # 其他未知错误
        logger.error(f"download_image: 处理图片 {image_id} 时发生未知错误: {e}")
        return JsonResponse({'success': False, 'message': f'发生错误: {str(e)}'}, status=500)


def get_local_image(request, image_id, image_type):
    """
    获取本地图片视图函数
    组装分片文件并返回完整的图片数据
    
    文件查找逻辑：
    1. 首先尝试当前日期目录：Media/Konachan/YYYYMMDD/md5值/image_type/
    2. 如果不存在，查找所有日期目录（按日期倒序），找到第一个存在的目录
    
    Args:
        request: HTTP请求对象
        image_id: 图片ID（整数）
        image_type: 图片类型，必须是 'preview'、'sample' 或 'jpeg' 之一
    
    Returns:
        HttpResponse: 
            - 成功：返回图片数据（content_type为对应的MIME类型）
            - 失败：返回404错误
    """
    try:
        # 获取图片对象
        image = get_object_or_404(KImage, id=image_id)
        
        # 检查是否已下载
        if "未下载" in image.download_status or "pending" in image.download_status.lower():
            raise Http404("图片未下载")
        
        # 验证image_type参数
        if image_type not in ['preview', 'sample', 'jpeg']:
            raise Http404("无效的图片类型")
        
        # 使用通用工具函数查找文件目录
        base_dir = find_file_in_date_dirs(
            media_root=KONACHAN_MEDIA_ROOT,
            file_id=image.md5,
            subdir=image_type
        )
        
        if not base_dir:
            raise Http404("找不到图片分片文件")
        
        # 使用通用工具函数组装分片
        try:
            assembled_data, file_ext = assemble_chunks(
                base_dir=base_dir,
                file_id=image.md5
            )
        except ChunkError as e:
            logger.error(f"get_local_image: 组装分片失败: {e}")
            raise Http404(f"获取图片失败: {str(e)}")
        
        # 使用通用工具函数获取MIME类型
        content_type = get_mime_type(file_ext)
        
        # 返回文件响应
        response = HttpResponse(assembled_data, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{image.md5}{file_ext}"'
        response['Content-Length'] = str(len(assembled_data))
        # 添加CORS支持，允许局域网访问
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        # 添加缓存控制
        response['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except KImage.DoesNotExist:
        logger.error(f"get_local_image: 图片 {image_id} 不存在")
        raise Http404("图片不存在")
    except Http404:
        raise
    except Exception as e:
        logger.error(f"get_local_image: 处理图片 {image_id} 的 {image_type} 时发生错误: {e}")
        raise Http404(f"获取图片失败: {str(e)}")
