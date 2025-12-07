"""
文件系统API模块
提供文件上传、下载、管理、缩略图生成等API接口
"""

# ==================== 标准库导入 ====================
import base64
import binascii
import hashlib
import json
import logging
import mimetypes
import os
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

# ==================== Django框架导入 ====================
from django.conf import settings
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# ==================== 本地应用导入 ====================
from .models import FileAppertain, FileInfo, FileRelationship

# ==================== 日志配置 ====================
logger = logging.getLogger('django')


# ==================== 加密工具函数 ====================
def get_encryption_key() -> bytes:
    """
    获取缩略图加密密钥（使用Django SECRET_KEY）
    
    Returns:
        bytes: 32字节的加密密钥
    """
    key = settings.SECRET_KEY.encode()
    # 确保密钥长度足够
    while len(key) < 32:
        key = key + key
    return key[:32]

def encrypt_data(data: bytes | str) -> str:
    """
    简单的XOR加密函数
    
    Args:
        data: 要加密的数据（字节或字符串）
    
    Returns:
        str: Base64编码的加密数据
    """
    key = get_encryption_key()
    data_bytes = data if isinstance(data, bytes) else data.encode()
    encrypted = bytearray()
    for i, byte in enumerate(data_bytes):
        encrypted.append(byte ^ key[i % len(key)])
    return base64.b64encode(bytes(encrypted)).decode()

def decrypt_data(encrypted_data: str) -> bytes:
    """
    解密数据（XOR是对称的）
    
    Args:
        encrypted_data: Base64编码的加密数据
    
    Returns:
        bytes: 解密后的原始数据
    """
    key = get_encryption_key()
    encrypted_bytes = base64.b64decode(encrypted_data.encode())
    decrypted = bytearray()
    for i, byte in enumerate(encrypted_bytes):
        decrypted.append(byte ^ key[i % len(key)])
    return bytes(decrypted)

def parse_file_data(file_info: FileInfo) -> dict | None:
    """
    解析文件data字段，兼容多种格式：
    1. JSON对象格式：{'chunks': [...], 'storage_dir': '...'}
    2. JSON字符串格式的路径数组：'["path1", "path2", ...]'
    3. None或空值
    
    Returns:
        dict: 包含chunks和storage_dir的字典，如果无法解析则返回None
    """
    if not file_info.data:
        return None
    
    data = file_info.data
    
    # 如果data是字符串，尝试解析为JSON
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            # 如果解析后是列表（路径数组格式，老数据格式）
            if isinstance(parsed, list) and len(parsed) > 0:
                # 转换为chunks格式
                # 从路径中提取文件名作为chunk标识
                chunks = []
                storage_dir = None
                
                for path in parsed:
                    if not path or not isinstance(path, str):
                        continue
                    
                    # 路径格式：media/2024-09-20/5269532824e245c26aafc8c524812410/b6bff779-3f1c-4dc3-9a5e-d449c882dbbf
                    # 提取最后一部分作为chunk标识（UUID文件名）
                    chunk_name = os.path.basename(path)
                    if chunk_name:
                        chunks.append(chunk_name)
                    
                    # 提取目录路径（只处理第一个有效路径）
                    if not storage_dir:
                        # 统一处理路径分隔符（先统一为/，再根据系统转换）
                        normalized_path = path.replace('\\', '/')
                        
                        # 构建完整路径
                        if normalized_path.startswith('media/'):
                            # 相对路径，需要转换为绝对路径
                            # 先构建完整路径，然后获取父目录
                            full_path = os.path.join(settings.BASE_DIR, normalized_path.replace('/', os.sep))
                            storage_dir = os.path.dirname(full_path)
                            logger.debug(f'[parse_file_data] 从media/路径解析: {path} -> {storage_dir}')
                        elif os.path.isabs(path):
                            # 绝对路径
                            storage_dir = os.path.dirname(path)
                            logger.debug(f'[parse_file_data] 从绝对路径解析: {path} -> {storage_dir}')
                        else:
                            # 其他相对路径（相对于BASE_DIR）
                            full_path = os.path.join(settings.BASE_DIR, normalized_path.replace('/', os.sep))
                            storage_dir = os.path.dirname(full_path)
                            logger.debug(f'[parse_file_data] 从相对路径解析: {path} -> {storage_dir}')
                
                # 确保storage_dir存在且有效
                if storage_dir and chunks:
                    # 验证目录是否存在
                    if os.path.exists(storage_dir) and os.path.isdir(storage_dir):
                        logger.debug(f'[parse_file_data] 解析成功: chunks数量={len(chunks)}, storage_dir={storage_dir}')
                        return {
                            'chunks': chunks,
                            'storage_dir': storage_dir,
                            'paths': parsed  # 保留原始路径列表
                        }
                    else:
                        logger.warning(f'[parse_file_data] 警告: storage_dir不存在或不是目录: {storage_dir}')
                        # 即使目录不存在，也返回数据，让调用者处理
                        return {
                            'chunks': chunks,
                            'storage_dir': storage_dir,
                            'paths': parsed
                        }
            # 如果解析后是字典，直接返回
            elif isinstance(parsed, dict):
                logger.debug(f'[parse_file_data] 解析为字典格式')
                return parsed
            else:
                logger.warning(f'[parse_file_data] 解析后的数据类型不支持: {type(parsed)}')
        except (json.JSONDecodeError, ValueError) as e:
            # 如果解析失败，记录错误并返回None
            logger.error(f'[parse_file_data] 解析JSON失败: {e}, data类型: {type(data)}, data前100字符: {str(data)[:100]}')
            return None
    
    # 如果data是字典，直接返回
    if isinstance(data, dict):
        logger.debug(f'[parse_file_data] data是字典格式')
        return data
    
    logger.warning(f'[parse_file_data] 无法解析data，类型: {type(data)}')
    return None

def get_file_storage_dir(file_info: FileInfo) -> str | None:
    """
    获取文件存储目录，兼容多种data格式
    支持从data、source_addr、hls_addr中提取存储目录
    
    Returns:
        str: 存储目录路径，如果无法确定则返回None
    """
    parsed_data = parse_file_data(file_info)
    if parsed_data:
        # 优先使用storage_dir
        if parsed_data.get('storage_dir'):
            storage_dir = parsed_data['storage_dir']
            # 验证目录是否存在
            if os.path.exists(storage_dir) and os.path.isdir(storage_dir):
                return storage_dir
            # 如果不存在，尝试从paths重新计算
            logger.debug(f'[get_file_storage_dir] storage_dir不存在: {storage_dir}，尝试从paths重新计算')
        
        # 如果有paths，从第一个路径提取目录
        if parsed_data.get('paths') and len(parsed_data['paths']) > 0:
            first_path = parsed_data['paths'][0]
            if not first_path or not isinstance(first_path, str):
                return None
            
            # 统一处理路径分隔符
            normalized_path = first_path.replace('\\', '/')
            
            if normalized_path.startswith('media/'):
                full_path = os.path.join(settings.BASE_DIR, normalized_path.replace('/', os.sep))
                storage_dir = os.path.dirname(full_path)
                if os.path.exists(storage_dir) and os.path.isdir(storage_dir):
                    return storage_dir
            elif os.path.isabs(first_path):
                storage_dir = os.path.dirname(first_path)
                if os.path.exists(storage_dir) and os.path.isdir(storage_dir):
                    return storage_dir
            else:
                full_path = os.path.join(settings.BASE_DIR, normalized_path.replace('/', os.sep))
                storage_dir = os.path.dirname(full_path)
                if os.path.exists(storage_dir) and os.path.isdir(storage_dir):
                    return storage_dir
    
    # 如果没有data，尝试从HLS地址中提取存储目录
    if file_info.hls_addr:
        try:
            # HLS文件路径可能有多种格式：
            # 1. 标准格式：media/2024-09-20/5269532824e245c26aafc8c524812410/HLS/hls_xxx.m3u8.enc
            # 2. 老格式：数据块目录/MD5/m3u8文件（如：.../Japan/37717a7aa2a9f9ece2b2de8d1f55a1f7/xxx.m3u8）
            hls_path = os.path.join(settings.BASE_DIR, file_info.hls_addr.replace('/', os.sep))
            logger.debug(f'[get_file_storage_dir] HLS文件路径: {hls_path}')
            
            if os.path.exists(hls_path):
                # 获取HLS文件所在目录
                hls_dir = os.path.dirname(hls_path)
                logger.debug(f'[get_file_storage_dir] HLS文件所在目录: {hls_dir}')
                
                # 检查是否是标准格式（包含HLS子目录）
                if os.path.basename(hls_dir).upper() == 'HLS':
                    # 标准格式：数据块目录/HLS/hls_xxx.m3u8.enc
                    # 获取父目录（数据块目录）
                    storage_dir = os.path.dirname(hls_dir)
                    logger.debug(f'[get_file_storage_dir] 标准格式，提取数据块目录: {storage_dir}')
                else:
                    # 老格式：数据块目录/MD5/m3u8文件
                    # HLS文件直接在MD5目录下，MD5目录就是存储目录（包含chunks）
                    storage_dir = hls_dir
                    logger.debug(f'[get_file_storage_dir] 老格式，MD5目录即为存储目录: {storage_dir}')
                
                if os.path.exists(storage_dir) and os.path.isdir(storage_dir):
                    logger.debug(f'[get_file_storage_dir] 从HLS地址提取存储目录成功: {storage_dir}')
                    return storage_dir
                else:
                    logger.warning(f'[get_file_storage_dir] 警告: 提取的存储目录不存在或不是目录: {storage_dir}')
            else:
                logger.warning(f'[get_file_storage_dir] 警告: HLS文件不存在: {hls_path}')
        except Exception as e:
            logger.error(f'[get_file_storage_dir] 从HLS地址提取目录失败: {e}', exc_info=True)
    
    # 如果没有data和HLS，尝试使用source_addr
    if file_info.source_addr:
        source_path = os.path.join(settings.BASE_DIR, file_info.source_addr.replace('/', os.sep))
        if os.path.exists(source_path):
            if os.path.isdir(source_path):
                return source_path
            else:
                # 如果是文件，返回其所在目录
                return os.path.dirname(source_path)
    
    return None

def get_file_chunks(file_info: FileInfo) -> list[str]:
    """
    获取文件chunks列表，兼容多种data格式
    
    Returns:
        list: chunks列表，如果无法获取则返回空列表
    """
    parsed_data = parse_file_data(file_info)
    if parsed_data:
        # 优先使用chunks
        if parsed_data.get('chunks') and isinstance(parsed_data['chunks'], list):
            return parsed_data['chunks']
        # 如果有paths，从路径中提取文件名
        if parsed_data.get('paths') and isinstance(parsed_data['paths'], list):
            chunks = []
            for path in parsed_data['paths']:
                if path and isinstance(path, str):
                    chunk_name = os.path.basename(path)
                    if chunk_name:
                        chunks.append(chunk_name)
            return chunks
    
    return []

def generate_thumbnail(file_info: FileInfo, storage_dir: str, chunks: list[str]) -> str | None:
    """生成图片或视频的缩略图"""
    try:
        logger.info(f'[generate_thumbnail] 开始处理: file_name={file_info.name}, mime={file_info.mime}, type={file_info.type}, chunks数量={len(chunks) if chunks else 0}')
        
        # 判断是否为图片或视频（优先使用MIME类型，如果MIME类型无法识别，则使用文件扩展名）
        is_image = False
        is_video = False
        
        # 首先尝试使用MIME类型判断
        if file_info.mime:
            is_image = file_info.mime.startswith('image/')
            is_video = file_info.mime.startswith('video/')
            logger.debug(f'[generate_thumbnail] MIME类型判断: is_image={is_image}, is_video={is_video}')
        
        # 如果MIME类型无法识别，使用文件扩展名判断
        if not (is_image or is_video) and file_info.type:
            image_types = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff', 'tif']
            video_types = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', '3gp', 'rmvb', 'rm']
            file_ext = file_info.type.lower()
            is_image = file_ext in image_types
            is_video = file_ext in video_types
            logger.debug(f'[generate_thumbnail] 扩展名判断: file_ext={file_ext}, is_image={is_image}, is_video={is_video}')
        
        if not (is_image or is_video):
            logger.debug(f'[generate_thumbnail] 不是图片或视频文件，跳过')
            return None
        
        # 临时文件路径（用于组装文件）
        temp_file_path = os.path.join(storage_dir, f'temp_{uuid.uuid4()}')
        logger.debug(f'[generate_thumbnail] 临时文件路径: {temp_file_path}')
        
        # 组装文件（用于生成缩略图）
        total_size = 0
        with open(temp_file_path, 'wb') as outfile:
            for chunk_uuid in chunks:
                chunk_path = os.path.join(storage_dir, chunk_uuid)
                if os.path.exists(chunk_path):
                    with open(chunk_path, 'rb') as infile:
                        chunk_data = infile.read()
                        outfile.write(chunk_data)
                        total_size += len(chunk_data)
                else:
                    logger.warning(f'[generate_thumbnail] 警告: 分片文件不存在: {chunk_path}')
        
        logger.debug(f'[generate_thumbnail] 文件组装完成，总大小: {total_size} 字节')
        
        if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
            logger.error(f'[generate_thumbnail] 错误: 临时文件不存在或为空')
            return None
        
        thumbnail_data = None
        
        if is_image:
            # 使用PIL生成图片缩略图
            logger.debug(f'[generate_thumbnail] 开始生成图片缩略图...')
            try:
                from PIL import Image
                logger.debug(f'[generate_thumbnail] PIL导入成功，打开图片: {temp_file_path}')
                original_img = Image.open(temp_file_path)
                logger.debug(f'[generate_thumbnail] 图片打开成功，格式: {original_img.format}, 模式: {original_img.mode}, 尺寸: {original_img.size}')
                
                # 获取原始图片尺寸
                original_width, original_height = original_img.size
                if not file_info.wh:
                    file_info.wh = {'w': original_width, 'h': original_height}
                    file_info.save()
                
                # 创建缩略图副本
                thumb_img = original_img.copy()
                thumb_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                logger.debug(f'[generate_thumbnail] 缩略图尺寸: {thumb_img.size}')
                
                # 转换为RGB模式（如果是RGBA等）
                if thumb_img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', thumb_img.size, (255, 255, 255))
                    if thumb_img.mode == 'P':
                        thumb_img = thumb_img.convert('RGBA')
                    background.paste(thumb_img, mask=thumb_img.split()[-1] if thumb_img.mode in ('RGBA', 'LA') else None)
                    thumb_img = background
                
                # 保存到内存
                thumb_io = BytesIO()
                thumb_img.save(thumb_io, format='JPEG', quality=85)
                thumbnail_data = thumb_io.getvalue()
                logger.info(f'[generate_thumbnail] 图片缩略图生成成功，大小: {len(thumbnail_data)} 字节')
                
            except ImportError:
                logger.warning('[generate_thumbnail] PIL/Pillow未安装，无法生成图片缩略图')
            except Exception as e:
                import traceback
                logger.error(f'[generate_thumbnail] 生成图片缩略图失败: {e}', exc_info=True)
        
        elif is_video:
            # 视频缩略图生成（需要ffmpeg）
            logger.debug(f'[generate_thumbnail] 开始生成视频缩略图...')
            try:
                import subprocess
                thumbnail_path = os.path.join(storage_dir, f'thumb_{uuid.uuid4()}.jpg')
                logger.debug(f'[generate_thumbnail] 视频缩略图输出路径: {thumbnail_path}')
                
                # 使用ffmpeg提取第一帧作为缩略图
                cmd = [
                    'ffmpeg', '-i', temp_file_path,
                    '-ss', '00:00:01',  # 提取第1秒的帧
                    '-vframes', '1',
                    '-vf', 'scale=300:-1',
                    '-y', thumbnail_path
                ]
                logger.debug(f'[generate_thumbnail] 执行ffmpeg命令: {" ".join(cmd)}')
                
                result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
                logger.debug(f'[generate_thumbnail] ffmpeg返回码: {result.returncode}')
                
                if result.returncode == 0 and os.path.exists(thumbnail_path):
                    with open(thumbnail_path, 'rb') as f:
                        thumbnail_data = f.read()
                    os.remove(thumbnail_path)
                    logger.info(f'[generate_thumbnail] 视频缩略图生成成功，大小: {len(thumbnail_data)} 字节')
                else:
                    error_msg = result.stderr if result.stderr else '未知错误'
                    logger.error(f'[generate_thumbnail] ffmpeg生成视频缩略图失败: {error_msg}')
                    if result.stdout:
                        logger.debug(f'[generate_thumbnail] ffmpeg输出: {result.stdout}')
                    # 如果ffmpeg不可用，尝试使用PIL（仅对某些视频格式有效）
                    try:
                        from PIL import Image
                        # 这里可以尝试其他方法，但大多数视频需要ffmpeg
                        pass
                    except:
                        pass
            except FileNotFoundError:
                logger.warning('[generate_thumbnail] ffmpeg未安装，无法生成视频缩略图')
            except Exception as e:
                import traceback
                logger.error(f'[generate_thumbnail] 生成视频缩略图失败: {e}', exc_info=True)
        
        # 删除临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if thumbnail_data:
            logger.debug(f'[generate_thumbnail] 开始保存缩略图，数据大小: {len(thumbnail_data)} 字节')
            # 加密缩略图
            encrypted_thumbnail = encrypt_data(thumbnail_data)
            logger.debug(f'[generate_thumbnail] 缩略图加密完成，加密后大小: {len(encrypted_thumbnail)} 字符')
            
            # 保存加密的缩略图
            thumbnail_filename = f'thumb_{uuid.uuid4()}.enc'
            thumbnail_path = os.path.join(storage_dir, thumbnail_filename)
            logger.debug(f'[generate_thumbnail] 保存缩略图到: {thumbnail_path}')
            
            with open(thumbnail_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_thumbnail)
            
            # 验证文件是否保存成功
            if os.path.exists(thumbnail_path):
                file_size = os.path.getsize(thumbnail_path)
                logger.info(f'[generate_thumbnail] 缩略图文件保存成功，文件大小: {file_size} 字节')
            else:
                logger.error(f'[generate_thumbnail] 错误: 缩略图文件保存失败')
                return None
            
            # 更新文件信息
            file_info.thumbnail_addr = thumbnail_filename
            file_info.save(update_fields=['thumbnail_addr'])
            # 重新从数据库加载以确保数据一致
            file_info.refresh_from_db()
            logger.debug(f'[generate_thumbnail] 文件信息已更新，thumbnail_addr={file_info.thumbnail_addr}')
            
            return thumbnail_filename
        else:
            logger.error(f'[generate_thumbnail] 错误: thumbnail_data为空，无法保存缩略图')
        
        return None
    
    except Exception as e:
        logger.error(f'生成缩略图异常: {e}', exc_info=True)
        return None

@csrf_exempt
@require_http_methods(["GET", "POST"])
def category_tag_api(request):
    """分类/标签API接口"""
    if request.method == 'GET':
        flag = request.GET.get('flag', None)  # 'C' 或 'T'
        parent_id = request.GET.get('parent_id', None)
        
        queryset = FileAppertain.objects.all()
        if flag:
            queryset = queryset.filter(flag=flag)
        # 只有当明确提供了 parent_id 参数时才过滤，否则返回所有（包括子分类）
        if parent_id is not None:
            if parent_id == '':
                # 如果 parent_id 是空字符串，返回顶级分类
                queryset = queryset.filter(parent__isnull=True)
            else:
                # 如果 parent_id 有值，返回该父级下的子项
                queryset = queryset.filter(parent_id=parent_id)
        # 如果没有提供 parent_id 参数，返回所有项目（包括子分类）
        
        items = queryset.order_by('sort_order', 'name')
        data = [{
            'id': item.id,
            'name': item.name,
            'flag': item.flag,
            'description': item.description or '',
            'parent_id': item.parent_id,
            'sort_order': item.sort_order,
            'created_time': item.created_time.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_time': item.updated_time.strftime('%Y-%m-%d %H:%M:%S'),
            'file_count': FileRelationship.objects.filter(file_appertain=item).count(),
        } for item in items]
        
        return JsonResponse({'success': True, 'data': data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'create':
                item = FileAppertain.objects.create(
                    name=data.get('name'),
                    flag=data.get('flag'),
                    description=data.get('description', ''),
                    parent_id=data.get('parent_id'),
                    sort_order=data.get('sort_order', 0),
                )
                return JsonResponse({
                    'success': True,
                    'message': '创建成功',
                    'data': {
                        'id': item.id,
                        'name': item.name,
                        'flag': item.flag,
                        'description': item.description or '',
                        'parent_id': item.parent_id,
                        'sort_order': item.sort_order,
                    }
                })
            
            elif action == 'update':
                item_id = data.get('id')
                item = FileAppertain.objects.get(id=item_id)
                item.name = data.get('name', item.name)
                item.description = data.get('description', item.description)
                if 'parent_id' in data:
                    item.parent_id = data.get('parent_id')
                if 'sort_order' in data:
                    item.sort_order = data.get('sort_order', item.sort_order)
                item.save()
                return JsonResponse({
                    'success': True,
                    'message': '更新成功',
                    'data': {
                        'id': item.id,
                        'name': item.name,
                        'flag': item.flag,
                        'description': item.description or '',
                        'parent_id': item.parent_id,
                        'sort_order': item.sort_order,
                    }
                })
            
            elif action == 'delete':
                item_id = data.get('id')
                item = FileAppertain.objects.get(id=item_id)
                # 检查是否有子项
                if item.children.exists():
                    return JsonResponse({
                        'success': False,
                        'message': '该分类/标签下还有子项，无法删除'
                    })
                # 检查是否有关联文件
                file_count = FileRelationship.objects.filter(file_appertain=item).count()
                if file_count > 0:
                    return JsonResponse({
                        'success': False,
                        'message': f'该分类/标签下还有 {file_count} 个文件，无法删除'
                    })
                item.delete()
                return JsonResponse({
                    'success': True,
                    'message': '删除成功'
                })
            
            else:
                return JsonResponse({'success': False, 'message': '未知操作'})
        
        except FileAppertain.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': '不支持的请求方法'})


@csrf_exempt
@require_http_methods(["POST"])
def upload_chunk(request):
    """上传文件分片"""
    try:
        if 'chunk' not in request.FILES:
            return JsonResponse({'success': False, 'message': '未找到分片数据'})
        
        chunk = request.FILES['chunk']
        chunk_index = int(request.POST.get('chunk_index', 0))
        total_chunks = int(request.POST.get('total_chunks', 1))
        file_md5 = request.POST.get('file_md5', '')
        file_name = request.POST.get('file_name', '')
        chunk_uuid = request.POST.get('chunk_uuid', str(uuid.uuid4()))
        
        if not file_md5:
            return JsonResponse({'success': False, 'message': '缺少文件MD5值'})
        
        # 创建存储目录：media+时间+md5
        now = datetime.now()
        time_str = now.strftime('%Y%m%d')
        storage_dir = os.path.join(str(settings.FS_MEDIA_ROOT), time_str, file_md5)
        os.makedirs(storage_dir, exist_ok=True)
        
        # 保存分片（使用UUID命名）
        chunk_path = os.path.join(storage_dir, chunk_uuid)
        with open(chunk_path, 'wb') as f:
            for chunk_data in chunk.chunks():
                f.write(chunk_data)
        
        return JsonResponse({
            'success': True,
            'message': '分片上传成功',
            'data': {
                'chunk_index': chunk_index,
                'chunk_uuid': chunk_uuid,
                'chunk_path': chunk_path,
                'total_chunks': total_chunks,
            }
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'上传失败: {str(e)}'})


@csrf_exempt
@require_http_methods(["POST"])
def merge_chunks(request):
    """合并分片并保存文件信息"""
    try:
        data = json.loads(request.body)
        file_md5 = data.get('file_md5')
        file_name = data.get('file_name')
        file_size = data.get('file_size', 0)
        chunks_info = data.get('chunks', [])  # [{chunk_index, chunk_uuid}, ...]
        album = data.get('album', '')
        subject = data.get('subject', '')
        author = data.get('author', '')
        level = data.get('level', 'General')
        category_ids = data.get('category_ids', [])
        tag_ids = data.get('tag_ids', [])
        remark = data.get('remark', '')
        # 确保should_generate_thumbnail是布尔值（避免与函数名冲突）
        should_generate_thumbnail = data.get('generate_thumbnail', True)
        if isinstance(should_generate_thumbnail, str):
            should_generate_thumbnail = should_generate_thumbnail.lower() in ('true', '1', 'yes')
        should_generate_thumbnail = bool(should_generate_thumbnail)
        
        # 接收前端生成的缩略图（base64编码）
        thumbnail_base64 = data.get('thumbnail_base64', None)
        
        if not file_md5 or not file_name or not chunks_info:
            return JsonResponse({'success': False, 'message': '缺少必要参数'})
        
        # 检查文件是否已存在
        existing_file = FileInfo.objects.filter(md5=file_md5).first()
        if existing_file:
            return JsonResponse({
                'success': True,
                'message': '文件已存在',
                'data': {
                    'file_id': existing_file.id,
                    'file_code': str(existing_file.code),
                    'exists': True
                }
            })
        
        # 创建存储目录
        now = datetime.now()
        time_str = now.strftime('%Y%m%d')
        storage_dir = os.path.join(str(settings.FS_MEDIA_ROOT), time_str, file_md5)
        os.makedirs(storage_dir, exist_ok=True)
        
        # 计算相对路径（相对于项目根目录）
        # 例如: media/20251115/286a5cb34fe62fb7530522cc7792635a
        relative_path = os.path.join('media', time_str, file_md5).replace('\\', '/')
        
        # 按chunk_index排序
        chunks_info.sort(key=lambda x: x.get('chunk_index', 0))
        
        # 合并分片
        merged_file_path = os.path.join(storage_dir, file_name)
        chunk_uuids = []
        with open(merged_file_path, 'wb') as outfile:
            for chunk_info in chunks_info:
                chunk_uuid = chunk_info.get('chunk_uuid')
                chunk_path = os.path.join(storage_dir, chunk_uuid)
                
                if os.path.exists(chunk_path):
                    with open(chunk_path, 'rb') as infile:
                        outfile.write(infile.read())
                    chunk_uuids.append(chunk_uuid)
                else:
                    return JsonResponse({'success': False, 'message': f'分片 {chunk_uuid} 不存在'})
        
        # 验证MD5
        with open(merged_file_path, 'rb') as f:
            calculated_md5 = hashlib.md5(f.read()).hexdigest()
        
        if calculated_md5 != file_md5:
            os.remove(merged_file_path)
            return JsonResponse({'success': False, 'message': 'MD5校验失败'})
        
        # MD5验证通过后，删除合并后的完整文件，只保留分片
        os.remove(merged_file_path)
        
        # 获取文件类型和MIME
        file_ext = os.path.splitext(file_name)[1][1:].lower() if '.' in file_name else 'unknown'
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = 'unknown'
        
        # 创建文件记录
        # source_addr保存相对路径（相对于项目根目录），例如: media/20251115/286a5cb34fe62fb7530522cc7792635a
        file_info = FileInfo.objects.create(
            name=file_name,
            md5=file_md5,
            size=file_size,
            type=file_ext,
            mime=mime_type,
            album=album,
            subject=subject,
            author=author,
            level=level,
            remark=remark,
            source_addr=relative_path,  # 相对路径，例如: media/20251115/286a5cb34fe62fb7530522cc7792635a
            status='processing',  # 初始状态为处理中
            data={
                'chunks': chunk_uuids,  # 保存分片UUID列表，按顺序
                'storage_dir': storage_dir,  # 保留绝对路径在data中，用于内部使用
                'time_str': time_str,
            }
        )
        
        # 关联分类和标签
        if category_ids:
            for cat_id in category_ids:
                try:
                    FileRelationship.objects.create(
                        file_info=file_info,
                        file_appertain_id=cat_id
                    )
                except Exception:
                    # 忽略重复关联错误
                    pass
        
        if tag_ids:
            for tag_id in tag_ids:
                try:
                    FileRelationship.objects.create(
                        file_info=file_info,
                        file_appertain_id=tag_id
                    )
                except Exception:
                    # 忽略重复关联错误
                    pass
        
        # 处理缩略图（优先使用前端生成的缩略图）
        is_image = mime_type.startswith('image/')
        is_video = mime_type.startswith('video/')
        
        # 如果MIME类型无法识别，使用文件扩展名判断
        if not (is_image or is_video):
            image_types = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff', 'tif']
            video_types = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', '3gp', 'rmvb', 'rm']
            file_ext = file_ext.lower()
            is_image = file_ext in image_types
            is_video = file_ext in video_types
        
        # 详细日志输出
        logger.debug(f'[缩略图处理] 文件: {file_name}, should_generate_thumbnail={should_generate_thumbnail}, is_image={is_image}, is_video={is_video}, 前端缩略图={bool(thumbnail_base64)}, mime_type={mime_type}, file_ext={file_ext}')
        if thumbnail_base64:
            logger.debug(f'[缩略图处理] 前端缩略图数据长度: {len(thumbnail_base64)} 字符')
        
        # 优先使用前端生成的缩略图
        # 检查thumbnail_base64是否为有效值（非None、非空字符串）
        if thumbnail_base64 and isinstance(thumbnail_base64, str) and len(thumbnail_base64.strip()) > 0 and should_generate_thumbnail:
            logger.debug(f'[缩略图处理] 使用前端生成的缩略图')
            try:
                # 解码base64数据
                thumbnail_data = base64.b64decode(thumbnail_base64)
                logger.debug(f'[缩略图处理] base64解码成功，数据大小: {len(thumbnail_data)} 字节')
                
                # 加密缩略图
                encrypted_thumbnail = encrypt_data(thumbnail_data)
                logger.debug(f'[缩略图处理] 缩略图加密完成，加密后大小: {len(encrypted_thumbnail)} 字符')
                
                # 保存加密的缩略图
                thumbnail_filename = f'thumb_{uuid.uuid4()}.enc'
                thumbnail_path = os.path.join(storage_dir, thumbnail_filename)
                logger.debug(f'[缩略图处理] 保存缩略图到: {thumbnail_path}')
                
                with open(thumbnail_path, 'w', encoding='utf-8') as f:
                    f.write(encrypted_thumbnail)
                
                # 验证文件是否保存成功
                if os.path.exists(thumbnail_path):
                    file_size = os.path.getsize(thumbnail_path)
                    logger.info(f'[缩略图处理] 缩略图文件保存成功，文件大小: {file_size} 字节')
                else:
                    logger.error(f'[缩略图处理] 错误: 缩略图文件保存失败')
                    thumbnail_filename = None
                
                # 更新文件信息
                if thumbnail_filename:
                    file_info.thumbnail_addr = thumbnail_filename
                    file_info.save(update_fields=['thumbnail_addr'])
                    # 重新从数据库加载以确保数据一致
                    file_info.refresh_from_db()
                    logger.debug(f'[缩略图处理] 文件信息已更新，thumbnail_addr={file_info.thumbnail_addr}')
                else:
                    logger.warning(f'[缩略图处理] 警告: thumbnail_filename为空，未更新数据库')
            except Exception as e:
                logger.error(f'[缩略图处理] 处理前端缩略图失败: {e}', exc_info=True)
                # 如果前端缩略图处理失败，尝试后端生成
                if should_generate_thumbnail and (is_image or is_video) and chunk_uuids:
                    logger.debug(f'[缩略图处理] 尝试后端生成缩略图...')
                    try:
                        thumbnail_result = generate_thumbnail(file_info, storage_dir, chunk_uuids)
                        if thumbnail_result:
                            logger.info(f'[缩略图处理] 后端生成成功: {thumbnail_result}')
                    except Exception as e2:
                        logger.error(f'[缩略图处理] 后端生成也失败: {e2}', exc_info=True)
        elif should_generate_thumbnail and (is_image or is_video) and chunk_uuids:
            # 如果没有前端缩略图，使用后端生成
            logger.debug(f'[缩略图处理] 使用后端生成缩略图...')
            try:
                thumbnail_result = generate_thumbnail(file_info, storage_dir, chunk_uuids)
                if thumbnail_result:
                    logger.info(f'[缩略图处理] 后端生成成功: {thumbnail_result}')
                else:
                    logger.warning(f'[缩略图处理] 后端生成失败: generate_thumbnail函数返回None')
            except Exception as e:
                logger.error(f'[缩略图处理] 后端生成异常: {e}', exc_info=True)
        else:
            reason = []
            if not should_generate_thumbnail:
                reason.append('用户未选择生成缩略图')
            if not (is_image or is_video):
                reason.append(f'不是图片或视频文件(mime={mime_type}, ext={file_ext})')
            if not chunk_uuids:
                reason.append('分片列表为空')
            logger.debug(f'[缩略图处理] 跳过: {", ".join(reason)}')
        
        # 清理分片文件（可选，也可以保留用于断点续传）
        # for chunk_uuid in chunk_uuids:
        #     chunk_path = os.path.join(storage_dir, chunk_uuid)
        #     if os.path.exists(chunk_path):
        #         os.remove(chunk_path)
        
        # 更新状态为启用（同时保存所有字段，确保缩略图字段也被保存）
        file_info.status = 'enable'
        file_info.save()
        # 再次确认缩略图字段
        if file_info.thumbnail_addr:
            logger.debug(f'[缩略图处理] 最终确认: 文件ID={file_info.id}, thumbnail_addr={file_info.thumbnail_addr}')
        
        return JsonResponse({
            'success': True,
            'message': '文件上传成功',
            'data': {
                'file_id': file_info.id,
                'file_code': str(file_info.code),
                'exists': False
            }
        })
    
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'合并失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["POST"])
def check_file_exists(request):
    """检查文件是否已存在（通过MD5）"""
    try:
        data = json.loads(request.body)
        file_md5 = data.get('file_md5')
        
        if not file_md5:
            return JsonResponse({'success': False, 'message': '缺少MD5参数'})
        
        existing_file = FileInfo.objects.filter(md5=file_md5).first()
        
        if existing_file:
            return JsonResponse({
                'success': True,
                'exists': True,
                'data': {
                    'file_id': existing_file.id,
                    'file_code': str(existing_file.code),
                    'file_name': existing_file.name,
                    'file_size': existing_file.size,
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'exists': False
            })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'检查失败: {str(e)}'})


@csrf_exempt
@require_http_methods(["GET"])
def file_list_api(request):
    """文件列表API接口"""
    try:
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = request.GET.get('search', '')
        file_type = request.GET.get('type', '')
        level = request.GET.get('level', '')
        status = request.GET.get('status', '')
        category_id = request.GET.get('category_id', '')
        tag_id = request.GET.get('tag_id', '')
        author = request.GET.get('author', '')
        album = request.GET.get('album', '')
        subject = request.GET.get('subject', '')
        
        # 构建查询
        queryset = FileInfo.objects.all()
        
        # 状态筛选（如果status为空或'all'，则显示所有状态；否则只显示指定状态）
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        # 类型筛选
        if file_type:
            # 文件类型分类定义
            image_types = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff', 'tif']
            video_types = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', '3gp', 'rmvb', 'rm']
            audio_types = ['mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a']
            document_types = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'odt', 'ods', 'odp']
            archive_types = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso', 'dmg']
            code_types = ['js', 'html', 'css', 'py', 'java', 'cpp', 'c', 'php', 'rb', 'go', 'rs', 'ts', 'jsx', 'tsx', 'json', 'xml', 'yaml', 'yml']
            
            if file_type.startswith('category:'):
                # 按大类筛选
                category = file_type.replace('category:', '')
                if category == 'image':
                    queryset = queryset.filter(type__in=image_types)
                elif category == 'video':
                    queryset = queryset.filter(type__in=video_types)
                elif category == 'audio':
                    queryset = queryset.filter(type__in=audio_types)
                elif category == 'document':
                    queryset = queryset.filter(type__in=document_types)
                elif category == 'archive':
                    queryset = queryset.filter(type__in=archive_types)
                elif category == 'code':
                    queryset = queryset.filter(type__in=code_types)
                elif category == 'other':
                    # 其他类型：排除所有已定义的类型
                    exclude_types = image_types + video_types + audio_types + document_types + archive_types + code_types
                    queryset = queryset.exclude(type__in=exclude_types)
            elif file_type == 'other':
                # 兼容旧的方式
                exclude_types = image_types + video_types + audio_types + document_types + archive_types + code_types
                queryset = queryset.exclude(type__in=exclude_types)
            else:
                # 单个文件类型筛选
                queryset = queryset.filter(type=file_type)
        
        # 级别筛选
        if level:
            queryset = queryset.filter(level=level)
        
        # 作者筛选
        if author:
            queryset = queryset.filter(author__icontains=author)
        
        # 专辑筛选
        if album:
            queryset = queryset.filter(album__icontains=album)
        
        # 主题筛选
        if subject:
            queryset = queryset.filter(subject__icontains=subject)
        
        # 分类筛选
        if category_id:
            queryset = queryset.filter(appertains__file_appertain_id=category_id, appertains__file_appertain__flag='C').distinct()
        
        # 标签筛选
        if tag_id:
            queryset = queryset.filter(appertains__file_appertain_id=tag_id, appertains__file_appertain__flag='T').distinct()
        
        # 搜索
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(md5__icontains=search) |
                models.Q(album__icontains=search) |
                models.Q(subject__icontains=search) |
                models.Q(remark__icontains=search) |
                models.Q(author__icontains=search)
            )
        
        # 总数
        total = queryset.count()
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        files = queryset.order_by('-created_time')[start:end]
        
        # 构建返回数据（优化：使用prefetch_related减少查询次数）
        file_list = []
        # 预加载关联的分类和标签关系
        files = files.prefetch_related('appertains__file_appertain')
        for file_info in files:
            # 获取关联的分类和标签（已预加载，不会产生额外查询）
            categories = []
            tags = []
            for rel in file_info.appertains.all():
                appertain = rel.file_appertain
                if appertain.flag == 'C':
                    categories.append({
                        'id': appertain.id,
                        'name': appertain.name
                    })
                else:
                    tags.append({
                        'id': appertain.id,
                        'name': appertain.name
                    })
            
            file_list.append({
                'id': file_info.id,
                'code': str(file_info.code),
                'name': file_info.name,
                'md5': file_info.md5,
                'size': file_info.size,
                'type': file_info.type,
                'mime': file_info.mime,
                'level': file_info.level,
                'status': file_info.status,
                'delete_time': file_info.delete_time.strftime('%Y-%m-%d %H:%M:%S') if file_info.delete_time else None,
                'author': file_info.author or '',
                'album': file_info.album or '',
                'subject': file_info.subject or '',
                'remark': file_info.remark or '',
                'wh': file_info.wh,
                'source_addr': file_info.source_addr or '',
                'thumbnail_addr': file_info.thumbnail_addr or '',
                'hls_addr': file_info.hls_addr or '',
                'created_time': file_info.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_time': file_info.updated_time.strftime('%Y-%m-%d %H:%M:%S'),
                'categories': categories,
                'tags': tags,
                'has_chunks': bool(get_file_chunks(file_info)),
            })
        
        return JsonResponse({
            'success': True,
            'data': {
                'files': file_list,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            }
        })
    
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'获取文件列表失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["POST"])
def file_update_api(request):
    """更新文件信息API"""
    try:
        data = json.loads(request.body)
        file_id = data.get('id')
        
        if not file_id:
            return JsonResponse({'success': False, 'message': '缺少文件ID'})
        
        file_info = FileInfo.objects.get(id=file_id)
        
        # 更新字段
        if 'name' in data:
            file_info.name = data.get('name')
        if 'author' in data:
            file_info.author = data.get('author', '')
        if 'level' in data:
            file_info.level = data.get('level', 'General')
        if 'album' in data:
            file_info.album = data.get('album', '')
        if 'subject' in data:
            file_info.subject = data.get('subject', '')
        if 'remark' in data:
            file_info.remark = data.get('remark', '')
        if 'status' in data:
            file_info.status = data.get('status', 'enable')
        
        file_info.save()
        
        # 更新分类和标签
        if 'category_ids' in data:
            # 删除旧的分类关联
            FileRelationship.objects.filter(
                file_info=file_info,
                file_appertain__flag='C'
            ).delete()
            # 添加新的分类关联
            for cat_id in data.get('category_ids', []):
                try:
                    FileRelationship.objects.create(
                        file_info=file_info,
                        file_appertain_id=cat_id
                    )
                except Exception:
                    # 忽略重复关联错误
                    pass
        
        if 'tag_ids' in data:
            # 删除旧的标签关联
            FileRelationship.objects.filter(
                file_info=file_info,
                file_appertain__flag='T'
            ).delete()
            # 添加新的标签关联
            for tag_id in data.get('tag_ids', []):
                try:
                    FileRelationship.objects.create(
                        file_info=file_info,
                        file_appertain_id=tag_id
                    )
                except Exception:
                    # 忽略重复关联错误
                    pass
        
        return JsonResponse({
            'success': True,
            'message': '更新成功'
        })
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'更新失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["GET"])
def file_content_api(request):
    """
    获取文件内容API（组装分片）
    
    支持流式传输，适用于大文件下载
    
    GET参数:
        id: 文件ID（整数）
        code: 文件编码（UUID字符串，与id二选一）
    
    Returns:
        StreamingHttpResponse: 文件流响应
        JsonResponse: 错误响应
    """
    from django.http import StreamingHttpResponse
    import mimetypes
    
    try:
        file_id = request.GET.get('id')
        file_code = request.GET.get('code')
        
        if not file_id and not file_code:
            return JsonResponse({'success': False, 'message': '缺少文件ID或编码'})
        
        # 获取文件信息
        if file_id:
            file_info = FileInfo.objects.get(id=file_id)
        else:
            file_info = FileInfo.objects.get(code=file_code)
        
        # 获取chunks和存储目录（兼容多种data格式）
        chunks = get_file_chunks(file_info)
        if not chunks:
            return JsonResponse({'success': False, 'message': '文件没有分片数据'})
        
        storage_dir = get_file_storage_dir(file_info)
        if not storage_dir:
            return JsonResponse({'success': False, 'message': '无法确定文件存储位置'})
        
        # 组装文件
        def file_generator():
            for chunk_uuid in chunks:
                chunk_path = os.path.join(storage_dir, chunk_uuid)
                if os.path.exists(chunk_path):
                    with open(chunk_path, 'rb') as f:
                        while True:
                            chunk_data = f.read(8192)  # 8KB chunks
                            if not chunk_data:
                                break
                            yield chunk_data
                else:
                    raise Exception(f'分片 {chunk_uuid} 不存在')
        
        # 确定MIME类型
        mime_type = file_info.mime or mimetypes.guess_type(file_info.name)[0] or 'application/octet-stream'
        
        # 返回文件流
        response = StreamingHttpResponse(file_generator(), content_type=mime_type)
        response['Content-Disposition'] = f'inline; filename="{file_info.name}"'
        response['Content-Length'] = file_info.size
        
        return response
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'获取文件内容失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["POST"])
def generate_thumbnail_api(request):
    """手动生成缩略图API"""
    try:
        data = json.loads(request.body)
        file_id = data.get('id')
        
        if not file_id:
            return JsonResponse({'success': False, 'message': '缺少文件ID'})
        
        file_info = FileInfo.objects.get(id=file_id)
        
        # 检查是否为图片或视频
        is_image = file_info.mime and file_info.mime.startswith('image/')
        is_video = file_info.mime and file_info.mime.startswith('video/')
        
        # 如果MIME类型无法识别，使用文件扩展名判断
        if not (is_image or is_video) and file_info.type:
            image_types = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff', 'tif']
            video_types = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', '3gp', 'rmvb', 'rm']
            file_ext = file_info.type.lower()
            is_image = file_ext in image_types
            is_video = file_ext in video_types
        
        if not (is_image or is_video):
            return JsonResponse({
                'success': False, 
                'message': f'只能为图片或视频生成缩略图（当前文件类型: mime={file_info.mime}, type={file_info.type}）'
            })
        
        # 获取chunks和存储目录（兼容多种data格式）
        chunks = get_file_chunks(file_info)
        storage_dir = get_file_storage_dir(file_info)
        
        # 如果data为空但有HLS，尝试从HLS目录中查找可能的原始文件
        if not chunks and file_info.hls_addr and storage_dir:
            logger.debug(f'[generate_thumbnail_api] data为空，但存在HLS文件，尝试从HLS目录查找原始文件')
            # 检查HLS目录的父目录中是否有其他文件（可能是原始文件或分片）
            try:
                import glob
                # 查找可能的文件（排除HLS相关文件）
                possible_files = []
                for pattern in ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.jpg', '*.jpeg', '*.png', '*.gif']:
                    files = glob.glob(os.path.join(storage_dir, pattern))
                    possible_files.extend([os.path.basename(f) for f in files])
                
                if possible_files:
                    logger.debug(f'[generate_thumbnail_api] 在存储目录中找到可能的文件: {possible_files[:5]}')
                    # 如果有单个文件，可以尝试直接使用
                    if len(possible_files) == 1:
                        # 对于单个文件，可以尝试直接生成缩略图
                        # 但需要修改generate_thumbnail函数支持单个文件路径
                        pass
            except Exception as e:
                logger.error(f'[generate_thumbnail_api] 查找原始文件失败: {e}', exc_info=True)
        
        if not chunks:
            # 尝试解析data字段，提供更详细的错误信息
            parsed_data = parse_file_data(file_info)
            error_detail = f'文件data字段: {type(file_info.data).__name__ if file_info.data else "None"}'
            if file_info.data:
                if isinstance(file_info.data, str):
                    error_detail += f' (字符串长度: {len(file_info.data)})'
                elif isinstance(file_info.data, dict):
                    error_detail += f' (包含keys: {list(file_info.data.keys())})'
            
            # 如果有HLS但没有chunks，提供特殊提示
            if file_info.hls_addr:
                error_detail += f' 文件存在HLS地址: {file_info.hls_addr}，但无法找到原始文件分片。'
                error_detail += ' 如果原始文件已删除，无法生成缩略图。'
            else:
                error_detail += ' 请检查文件data字段是否正确。'
            
            return JsonResponse({
                'success': False, 
                'message': f'文件没有分片数据。{error_detail}'
            })
        
        if not storage_dir:
            # 提供更详细的错误信息
            error_detail = f'无法确定文件存储位置。'
            if file_info.data:
                error_detail += f' data字段类型: {type(file_info.data).__name__}'
            if file_info.source_addr:
                error_detail += f' source_addr: {file_info.source_addr}'
            if file_info.hls_addr:
                error_detail += f' hls_addr: {file_info.hls_addr}'
            return JsonResponse({
                'success': False, 
                'message': error_detail
            })
        
        # 验证存储目录是否存在
        if not os.path.exists(storage_dir):
            return JsonResponse({
                'success': False, 
                'message': f'存储目录不存在: {storage_dir}'
            })
        
        if not os.path.isdir(storage_dir):
            return JsonResponse({
                'success': False, 
                'message': f'存储路径不是目录: {storage_dir}'
            })
        
        # 验证chunks文件是否存在
        missing_chunks = []
        for chunk_uuid in chunks:
            chunk_path = os.path.join(storage_dir, chunk_uuid)
            if not os.path.exists(chunk_path):
                missing_chunks.append(chunk_uuid)
        
        if missing_chunks:
            return JsonResponse({
                'success': False, 
                'message': f'部分分片文件不存在（共{len(missing_chunks)}个）: {missing_chunks[:5]}...' if len(missing_chunks) > 5 else f'部分分片文件不存在: {missing_chunks}'
            })
        
        # 生成缩略图
        thumbnail_filename = generate_thumbnail(file_info, storage_dir, chunks)
        
        if thumbnail_filename:
            return JsonResponse({
                'success': True,
                'message': '缩略图生成成功',
                'data': {
                    'thumbnail_addr': thumbnail_filename
                }
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': '缩略图生成失败，请查看服务器日志获取详细信息'
            })
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '请求数据格式错误'})
    except Exception as e:
        import traceback
        error_msg = f'生成缩略图失败: {str(e)}'
        traceback_str = traceback.format_exc() if settings.DEBUG else None
        logger.error(f'[generate_thumbnail_api] 异常: {error_msg}', exc_info=True)
        return JsonResponse({
            'success': False,
            'message': error_msg,
            'traceback': traceback_str
        })


@csrf_exempt
@require_http_methods(["GET"])
def thumbnail_api(request):
    """获取缩略图API（解密后返回）"""
    try:
        file_id = request.GET.get('id')
        file_code = request.GET.get('code')
        
        if not file_id and not file_code:
            return JsonResponse({'success': False, 'message': '缺少文件ID或编码'})
        
        # 获取文件信息
        if file_id:
            file_info = FileInfo.objects.get(id=file_id)
        else:
            file_info = FileInfo.objects.get(code=file_code)
        
        if not file_info.thumbnail_addr:
            return JsonResponse({'success': False, 'message': '文件没有缩略图'})
        
        # 获取存储目录（兼容多种data格式）
        storage_dir = get_file_storage_dir(file_info)
        if not storage_dir:
            return JsonResponse({'success': False, 'message': '无法确定文件存储位置'})
        
        # 读取加密的缩略图
        thumbnail_path = os.path.join(storage_dir, file_info.thumbnail_addr)
        if not os.path.exists(thumbnail_path):
            return JsonResponse({'success': False, 'message': '缩略图文件不存在'})
        
        with open(thumbnail_path, 'r', encoding='utf-8') as f:
            encrypted_data = f.read()
        
        # 解密缩略图
        thumbnail_data = decrypt_data(encrypted_data)
        
        # 返回图片
        response = HttpResponse(thumbnail_data, content_type='image/jpeg')
        response['Cache-Control'] = 'public, max-age=31536000'
        return response
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'获取缩略图失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["POST"])
def file_delete_api(request):
    """删除文件API（软删除，删除分片，保留缩略图）"""
    try:
        data = json.loads(request.body)
        file_id = data.get('id')
        
        if not file_id:
            return JsonResponse({'success': False, 'message': '缺少文件ID'})
        
        file_info = FileInfo.objects.get(id=file_id)
        
        # 获取存储目录（兼容多种data格式）
        storage_dir = get_file_storage_dir(file_info)
        if not storage_dir:
            return JsonResponse({'success': False, 'message': '无法确定文件存储位置'})
        
        # 删除分片文件
        deleted_count = 0
        chunks = get_file_chunks(file_info)
        if chunks:
            for chunk_uuid in chunks:
                chunk_path = os.path.join(storage_dir, chunk_uuid)
                try:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f'删除分片 {chunk_uuid} 失败: {e}')
            
            # 更新data字段，移除chunks信息（兼容多种格式）
            parsed_data = parse_file_data(file_info)
            if parsed_data:
                # 如果是字典格式，移除chunks和storage_dir
                if isinstance(file_info.data, dict):
                    data_dict = file_info.data.copy()
                    data_dict.pop('chunks', None)
                    data_dict.pop('storage_dir', None)
                    data_dict.pop('paths', None)
                    file_info.data = data_dict if data_dict else None
                # 如果是字符串格式，清空
                elif isinstance(file_info.data, str):
                    file_info.data = None
        
        # 删除HLS文件
        hls_deleted_count = 0
        if file_info.hls_addr:
            try:
                # 删除加密的m3u8文件
                m3u8_path = os.path.join(settings.BASE_DIR, file_info.hls_addr.replace('/', os.sep))
                if os.path.exists(m3u8_path):
                    os.remove(m3u8_path)
                    hls_deleted_count += 1
                
                # 从hls_addr中提取UUID（格式：media/.../hls_{uuid}.m3u8.enc）
                import glob
                import re
                m3u8_filename = os.path.basename(file_info.hls_addr)
                uuid_match = re.search(r'hls_([a-f0-9-]+)\.m3u8\.enc', m3u8_filename)
                if uuid_match:
                    hls_uuid = uuid_match.group(1)
                    # 删除所有相关的ts分片文件
                    ts_pattern = os.path.join(storage_dir, f'hls_seg_{hls_uuid}_*.ts')
                    for ts_path in glob.glob(ts_pattern):
                        try:
                            if os.path.exists(ts_path):
                                os.remove(ts_path)
                                hls_deleted_count += 1
                        except Exception as e:
                            logger.warning(f'删除TS分片 {ts_path} 失败: {e}')
            except Exception as e:
                logger.error(f'删除HLS文件失败: {e}', exc_info=True)
        
        # 保留缩略图（不删除）
        # 缩略图文件保留在 storage_dir 中
        
        # 更新文件状态和删除时间
        from django.utils import timezone
        file_info.status = 'deleted'
        file_info.delete_time = timezone.now()
        file_info.hls_addr = ''  # 清空HLS地址
        file_info.save()
        
        message_parts = [f'已删除 {deleted_count} 个分片']
        if hls_deleted_count > 0:
            message_parts.append(f'{hls_deleted_count} 个HLS文件')
        message_parts.append('缩略图已保留')
        
        return JsonResponse({
            'success': True,
            'message': f'文件已删除（{"，".join(message_parts)}）'
        })
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'删除失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["POST"])
def convert_hls_api(request):
    """转换视频为HLS格式API"""
    try:
        data = json.loads(request.body)
        file_id = data.get('id')
        
        if not file_id:
            return JsonResponse({'success': False, 'message': '缺少文件ID'})
        
        file_info = FileInfo.objects.get(id=file_id)
        
        # 检查是否是视频文件
        if not file_info.mime or not file_info.mime.startswith('video/'):
            return JsonResponse({'success': False, 'message': '该文件不是视频文件'})
        
        # 检查是否已有HLS文件
        if file_info.hls_addr:
            return JsonResponse({
                'success': True,
                'message': '该文件已存在HLS文件',
                'data': {'hls_addr': file_info.hls_addr}
            })
        
        # 获取chunks和存储目录（兼容多种data格式）
        chunks = get_file_chunks(file_info)
        if not chunks:
            return JsonResponse({'success': False, 'message': '文件分片信息不存在'})
        
        storage_dir = get_file_storage_dir(file_info)
        if not storage_dir:
            return JsonResponse({'success': False, 'message': '无法确定文件存储位置'})
        
        # 组装临时文件用于转换
        import tempfile
        import subprocess
        
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_info.type}')
        temp_input_path = temp_input.name
        temp_input.close()
        
        try:
            # 组装文件
            with open(temp_input_path, 'wb') as output_file:
                for chunk_uuid in chunks:
                    chunk_path = os.path.join(storage_dir, chunk_uuid)
                    if os.path.exists(chunk_path):
                        with open(chunk_path, 'rb') as chunk_file:
                            output_file.write(chunk_file.read())
            
            # HLS文件保存在数据块目录下的HLS子目录
            # 创建HLS子目录
            hls_dir = os.path.join(storage_dir, 'HLS')
            os.makedirs(hls_dir, exist_ok=True)
            
            # HLS输出文件路径（使用UUID命名，避免冲突）
            hls_playlist_uuid = str(uuid.uuid4())
            hls_output = os.path.join(hls_dir, f'hls_{hls_playlist_uuid}.m3u8')
            
            # 使用ffmpeg转换为HLS
            # 注意：需要系统安装ffmpeg
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', temp_input_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-hls_time', '10',
                '-hls_list_size', '0',
                '-hls_segment_filename', os.path.join(hls_dir, f'hls_seg_{hls_playlist_uuid}_%03d.ts'),
                '-f', 'hls',
                hls_output
            ]
            
            try:
                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1小时超时
                )
                
                if result.returncode != 0:
                    return JsonResponse({
                        'success': False,
                        'message': f'FFmpeg转换失败: {result.stderr}'
                    })
                
                # 检查输出文件是否存在
                if not os.path.exists(hls_output):
                    return JsonResponse({
                        'success': False,
                        'message': 'HLS文件生成失败'
                    })
                
                # 读取m3u8文件内容
                with open(hls_output, 'r', encoding='utf-8') as f:
                    m3u8_content = f.read()
                
                # 查找所有ts文件并加密
                import re
                ts_files = []
                ts_pattern = re.compile(r'hls_seg_' + re.escape(hls_playlist_uuid) + r'_(\d+)\.ts')
                
                # 加密所有ts分片文件
                for ts_match in ts_pattern.finditer(m3u8_content):
                    ts_filename = ts_match.group(0)
                    ts_path = os.path.join(hls_dir, ts_filename)
                    if os.path.exists(ts_path):
                        # 读取ts文件并加密
                        with open(ts_path, 'rb') as ts_file:
                            ts_data = ts_file.read()
                        # 使用XOR加密（直接对字节操作）
                        key = get_encryption_key()
                        encrypted_bytes = bytearray()
                        for i, byte in enumerate(ts_data):
                            encrypted_bytes.append(byte ^ key[i % len(key)])
                        # 保存加密后的ts文件（覆盖原文件）
                        with open(ts_path, 'wb') as ts_file:
                            ts_file.write(bytes(encrypted_bytes))
                        ts_files.append(ts_filename)
                
                # 修改m3u8文件内容，将ts文件路径改为通过API访问
                # 注意：ts文件已经加密，但文件名不变，在m3u8中标记为.enc以便识别
                def replace_ts_path(match):
                    ts_filename = match.group(0)
                    # 在m3u8中标记为.enc，实际文件没有.enc后缀，只是加密了
                    return f'{ts_filename}.enc'
                
                m3u8_content = ts_pattern.sub(replace_ts_path, m3u8_content)
                
                # 加密m3u8文件内容
                encrypted_m3u8 = encrypt_data(m3u8_content)
                
                # 保存加密后的m3u8文件（覆盖原文件）
                encrypted_m3u8_path = hls_output + '.enc'
                with open(encrypted_m3u8_path, 'w', encoding='utf-8') as f:
                    f.write(encrypted_m3u8)
                
                # 删除未加密的m3u8文件
                if os.path.exists(hls_output):
                    os.remove(hls_output)
                
                # 计算相对路径（保存加密后的m3u8文件路径）
                relative_hls_path = os.path.relpath(encrypted_m3u8_path, settings.BASE_DIR).replace('\\', '/')
                
                # 更新数据库
                file_info.hls_addr = relative_hls_path
                file_info.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'HLS转换成功',
                    'data': {'hls_addr': relative_hls_path}
                })
            
            except subprocess.TimeoutExpired:
                return JsonResponse({
                    'success': False,
                    'message': 'HLS转换超时，请稍后重试'
                })
            except FileNotFoundError:
                return JsonResponse({
                    'success': False,
                    'message': '系统未安装FFmpeg，无法进行HLS转换'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'HLS转换失败: {str(e)}'
                })
        
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_input_path):
                    os.remove(temp_input_path)
            except:
                pass
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'转换失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@csrf_exempt
@require_http_methods(["GET"])
def hls_content_api(request):
    """HLS文件内容API（自动解密）"""
    try:
        file_id = request.GET.get('id')
        file_type = request.GET.get('type', 'm3u8')  # m3u8 或 ts
        
        if not file_id:
            return JsonResponse({'success': False, 'message': '缺少文件ID'})
        
        file_info = FileInfo.objects.get(id=file_id)
        
        if not file_info.hls_addr:
            return JsonResponse({'success': False, 'message': 'HLS文件不存在'})
        
        # 获取存储目录（兼容多种data格式）
        storage_dir = get_file_storage_dir(file_info)
        if not storage_dir:
            return JsonResponse({'success': False, 'message': '无法确定文件存储位置'})
        
        if file_type == 'm3u8':
            # 返回m3u8文件（解密或直接读取）
            m3u8_path = os.path.join(settings.BASE_DIR, file_info.hls_addr.replace('/', os.sep))
            if not os.path.exists(m3u8_path):
                return JsonResponse({'success': False, 'message': 'HLS文件不存在'})
            
            # 检查文件是否加密（通过扩展名或内容判断）
            is_encrypted = m3u8_path.endswith('.enc')
            
            try:
                if is_encrypted:
                    # 加密文件：读取并解密
                    with open(m3u8_path, 'r', encoding='utf-8') as f:
                        encrypted_content = f.read()
                    
                    try:
                        decrypted_content = decrypt_data(encrypted_content)
                        m3u8_text = decrypted_content.decode('utf-8')
                    except (ValueError, binascii.Error) as e:
                        # 如果解密失败，可能是文件损坏或格式不对
                        logger.warning(f'[hls_content_api] 解密m3u8文件失败: {e}，尝试作为未加密文件读取')
                        # 尝试直接读取（可能是未加密但扩展名是.enc）
                        with open(m3u8_path, 'r', encoding='utf-8') as f:
                            m3u8_text = f.read()
                else:
                    # 未加密文件：直接读取
                    with open(m3u8_path, 'r', encoding='utf-8') as f:
                        m3u8_text = f.read()
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'读取m3u8文件失败: {str(e)}'
                })
            
            # 修改m3u8中的ts文件路径为API路径
            import re
            import urllib.parse
            
            # 匹配ts文件路径（支持多种格式）：
            # 1. hls_seg_xxx_000.ts (标准格式，包含下划线和数字)
            # 2. xxx.ts (老格式，如bb8daf95-dadb-11ee-a2eb-04421aa823900.ts)
            # 3. 可能带.enc后缀
            # 注意：匹配整行中的ts文件路径，不限于行尾
            # 使用更宽泛的模式：匹配任何以.ts结尾的文件名（可能带.enc后缀）
            ts_pattern = re.compile(r'([a-zA-Z0-9_\-]+\.ts)(\.enc)?', re.IGNORECASE)
            
            def replace_with_api(match):
                ts_filename = match.group(1)  # 获取实际文件名（去掉.enc后缀）
                # 对文件名进行URL编码，确保特殊字符正确处理
                encoded_filename = urllib.parse.quote(ts_filename, safe='')
                api_url = f'/fs/api/files/hls-content/?id={file_id}&type=ts&file={encoded_filename}'
                logger.debug(f'[hls_content_api] 替换TS路径: {match.group(0)} -> {api_url}')
                return api_url
            
            m3u8_text = ts_pattern.sub(replace_with_api, m3u8_text)
            logger.debug(f'[hls_content_api] m3u8文件处理后的前500字符: {m3u8_text[:500]}')
            
            # 处理AES-128加密密钥URI，将其转换为API路径
            # 匹配格式：URI="http://..." 或 URI="相对路径"
            key_uri_pattern = re.compile(r'URI="([^"]+)"', re.IGNORECASE)
            
            def replace_key_uri(match):
                original_uri = match.group(1)
                # 如果是相对路径（如 /media/VKey/ALL/encrypt.key），转换为API路径
                if original_uri.startswith('/') or not original_uri.startswith('http'):
                    # 提取密钥文件名
                    key_filename = os.path.basename(original_uri)
                    # 转换为API路径（使用hls-content API，type=key）
                    encoded_key = urllib.parse.quote(key_filename, safe='')
                    api_uri = f'/fs/api/files/hls-content/?id={file_id}&type=key&key={encoded_key}'
                    logger.debug(f'[hls_content_api] 转换密钥URI: {original_uri} -> {api_uri}')
                    return f'URI="{api_uri}"'
                # 如果是外部URL，保持原样
                return match.group(0)
            
            m3u8_text = key_uri_pattern.sub(replace_key_uri, m3u8_text)
            
            response = HttpResponse(m3u8_text, content_type='application/vnd.apple.mpegurl')
            response['Access-Control-Allow-Origin'] = '*'
            return response
        
        elif file_type == 'ts':
            # 返回ts分片文件（解密或直接读取）
            import urllib.parse
            ts_filename_encoded = request.GET.get('file')
            if not ts_filename_encoded:
                return JsonResponse({'success': False, 'message': '缺少ts文件名'})
            
            # URL解码文件名
            ts_filename = urllib.parse.unquote(ts_filename_encoded)
            
            # TS文件可能在HLS子目录中，也可能直接在存储目录中（老格式）
            ts_path = None
            possible_paths = [
                os.path.join(storage_dir, 'HLS', ts_filename),  # 标准格式
                os.path.join(storage_dir, ts_filename),  # 老格式（直接在MD5目录下）
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    ts_path = path
                    break
            
            if not ts_path:
                return JsonResponse({
                    'success': False, 
                    'message': f'TS文件不存在，尝试的路径: {possible_paths}'
                })
            
            # 读取ts文件（二进制）
            with open(ts_path, 'rb') as f:
                ts_data = f.read()
            
            # 注意：如果m3u8文件使用了AES-128加密（通过#EXT-X-KEY标签），
            # TS文件本身可能已经是AES-128加密的，这种情况下：
            # 1. 如果TS文件是我们系统XOR加密的，需要解密
            # 2. 如果TS文件是AES-128加密的，应该直接返回，让浏览器/HLS.js处理AES-128解密
            # 3. 如果TS文件未加密，直接返回
            
            # 尝试判断是否是我们系统的XOR加密
            # 简单验证：检查原始数据是否看起来像有效的TS流
            is_valid_ts = len(ts_data) > 0 and ts_data[0] == 0x47
            
            if not is_valid_ts:
                # 原始数据不像TS流，可能是我们系统的XOR加密，尝试解密
                try:
                    key = get_encryption_key()
                    decrypted_data = bytearray()
                    for i, byte in enumerate(ts_data):
                        decrypted_data.append(byte ^ key[i % len(key)])
                    decrypted_data = bytes(decrypted_data)
                    
                    # 检查解密后的数据是否看起来像有效的TS流
                    if len(decrypted_data) > 0 and decrypted_data[0] == 0x47:
                        # 看起来是有效的TS流，使用解密后的数据
                        ts_data = decrypted_data
                        logger.debug(f'[hls_content_api] TS文件使用XOR解密成功')
                    else:
                        # 解密后的数据不像TS流，可能是AES-128加密或其他格式，使用原始数据
                        logger.debug(f'[hls_content_api] TS文件可能使用AES-128加密或其他格式，使用原始数据')
                except Exception as e:
                    # 解密失败，使用原始数据
                    logger.warning(f'[hls_content_api] TS文件解密失败: {e}，使用原始数据')
            else:
                # 原始数据已经是有效的TS流，直接使用
                logger.debug(f'[hls_content_api] TS文件未加密，直接返回')
            
            response = HttpResponse(ts_data, content_type='video/mp2t')
            response['Access-Control-Allow-Origin'] = '*'
            response['Cache-Control'] = 'public, max-age=31536000'
            return response
        
        elif file_type == 'key':
            # 返回AES-128加密密钥文件
            import urllib.parse
            key_filename_encoded = request.GET.get('key')
            if not key_filename_encoded:
                return JsonResponse({'success': False, 'message': '缺少密钥文件名'})
            
            # URL解码文件名
            key_filename = urllib.parse.unquote(key_filename_encoded)
            
            # 密钥文件可能在多个位置：
            # 1. 存储目录中
            # 2. 存储目录的父目录中（如 VKey/ALL/encrypt.key）
            # 3. 系统配置的密钥目录中
            key_path = None
            possible_paths = [
                os.path.join(storage_dir, key_filename),  # 直接在存储目录
                os.path.join(storage_dir, 'VKey', 'ALL', key_filename),  # VKey/ALL/子目录
                os.path.join(os.path.dirname(storage_dir), 'VKey', 'ALL', key_filename),  # 父目录的VKey
                os.path.join(settings.BASE_DIR, 'media', 'VKey', 'ALL', key_filename),  # 系统media目录
            ]
            
            for path in possible_paths:
                if os.path.exists(path) and os.path.isfile(path):
                    key_path = path
                    break
            
            if not key_path:
                # 如果找不到密钥文件，返回错误
                return JsonResponse({
                    'success': False,
                    'message': f'AES-128密钥文件不存在，尝试的路径: {possible_paths}'
                })
            
            # 读取密钥文件（二进制，AES-128密钥通常是16字节）
            with open(key_path, 'rb') as f:
                key_data = f.read()
            
            response = HttpResponse(key_data, content_type='application/octet-stream')
            response['Access-Control-Allow-Origin'] = '*'
            response['Cache-Control'] = 'public, max-age=31536000'
            return response
        
        else:
            return JsonResponse({'success': False, 'message': '不支持的文件类型'})
    
    except FileInfo.DoesNotExist:
        return JsonResponse({'success': False, 'message': '文件不存在'})
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'获取HLS文件失败: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })
