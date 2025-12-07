"""
文件系统视图函数模块
处理文件分类、标签管理和文件上传、列表展示等功能
"""

import logging
from django.shortcuts import render
from django.http import Http404
from .models import FileAppertain, FileInfo

# 获取日志记录器
logger = logging.getLogger('django')


def category_tag_manage(request):
    """
    分类/标签管理页面视图函数
    显示文件分类和标签的层级结构管理界面
    
    Args:
        request: HTTP请求对象
    
    Returns:
        HttpResponse: 渲染后的分类/标签管理页面HTML
    
    Raises:
        Http404: 如果发生数据库查询错误
    """
    try:
        # 获取所有分类，按排序顺序和名称排序
        categories = FileAppertain.objects.filter(flag='C').order_by('sort_order', 'name')
        # 获取所有标签，按排序顺序和名称排序
        tags = FileAppertain.objects.filter(flag='T').order_by('sort_order', 'name')
        
        # 构建层级结构
        def build_tree(items):
            """
            构建树形结构
            
            Args:
                items: 要构建树形结构的项目列表
            
            Returns:
                list: 根节点列表，每个节点包含item和children字段
            """
            try:
                item_dict = {item.id: {'item': item, 'children': []} for item in items}
                root_items = []
                for item in items:
                    if item.parent_id:
                        if item.parent_id in item_dict:
                            item_dict[item.parent_id]['children'].append(item_dict[item.id])
                    else:
                        root_items.append(item_dict[item.id])
                return root_items
            except Exception as e:
                logger.error(f"build_tree: 构建树形结构失败 - {str(e)}")
                return []
        
        category_tree = build_tree(list(categories))
        tag_tree = build_tree(list(tags))
        
        context = {
            'categories': categories,
            'tags': tags,
            'category_tree': category_tree,
            'tag_tree': tag_tree,
        }
        logger.debug(f"category_tag_manage: 成功加载 {len(categories)} 个分类和 {len(tags)} 个标签")
        return render(request, 'fs/ct.html', context)
        
    except Exception as e:
        logger.error(f"category_tag_manage: 处理请求时发生错误 - {str(e)}")
        raise Http404("加载分类/标签数据失败")


def file_upload(request):
    """
    文件上传页面视图函数
    显示文件上传界面，包含分类和标签选择
    
    Args:
        request: HTTP请求对象
    
    Returns:
        HttpResponse: 渲染后的文件上传页面HTML
    
    Raises:
        Http404: 如果发生数据库查询错误
    """
    try:
        # 获取所有分类，按排序顺序和名称排序
        categories = FileAppertain.objects.filter(flag='C').order_by('sort_order', 'name')
        # 获取所有标签，按排序顺序和名称排序
        tags = FileAppertain.objects.filter(flag='T').order_by('sort_order', 'name')
        
        context = {
            'categories': categories,
            'tags': tags,
        }
        logger.debug(f"file_upload: 成功加载 {len(categories)} 个分类和 {len(tags)} 个标签")
        return render(request, 'fs/upload.html', context)
        
    except Exception as e:
        logger.error(f"file_upload: 处理请求时发生错误 - {str(e)}")
        raise Http404("加载上传页面数据失败")


def file_list(request):
    """
    文件列表展示页面视图函数
    显示所有文件的列表，包含分类和标签筛选功能
    
    Args:
        request: HTTP请求对象
    
    Returns:
        HttpResponse: 渲染后的文件列表页面HTML
    
    Raises:
        Http404: 如果发生数据库查询错误
    """
    try:
        # 获取所有分类，按排序顺序和名称排序
        categories = FileAppertain.objects.filter(flag='C').order_by('sort_order', 'name')
        # 获取所有标签，按排序顺序和名称排序
        tags = FileAppertain.objects.filter(flag='T').order_by('sort_order', 'name')
        
        context = {
            'categories': categories,
            'tags': tags,
        }
        logger.debug(f"file_list: 成功加载 {len(categories)} 个分类和 {len(tags)} 个标签")
        return render(request, 'fs/all.html', context)
        
    except Exception as e:
        logger.error(f"file_list: 处理请求时发生错误 - {str(e)}")
        raise Http404("加载文件列表数据失败")
