from django.shortcuts import redirect, render


def home(request):
    """
    项目根路径的默认视图，重定向到 Konachan 的首页，避免 404。
    """
    return redirect('konachan:index')


def handler404(request, exception):
    """
    404错误处理视图
    当页面不存在时，显示自定义404页面
    
    Args:
        request: HTTP请求对象
        exception: 异常对象
    
    Returns:
        HttpResponse: 渲染后的404页面
    """
    return render(request, '404.html', status=404)

