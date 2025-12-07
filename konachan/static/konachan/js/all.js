/**
 * 所有数据展示页面JavaScript功能文件
 * 包含图片预览、URL预览、下载等功能
 */

(function() {
    'use strict';
    
    /**
     * 计算当前应用的基础路径，例如 /k 或 /w
     * @param {string} fallback 当无法解析时使用的默认前缀
     * @returns {string}
     */
    function getAppBasePath(fallback) {
        const segments = window.location.pathname.split('/').filter(Boolean);
        if (segments.length > 0) {
            return `/${segments[0]}`;
        }
        return fallback;
    }

    const downloadBasePath = window.__KONACHAN_BASE_PATH__ || getAppBasePath('/k');
    
    // 获取DOM元素
    const preview = document.getElementById('imagePreview');
    const previewImage = document.getElementById('previewImage');
    const fileNames = document.querySelectorAll('.file-name');
    const urlPreview = document.getElementById('urlPreview');
    const urlPreviewImage = document.getElementById('urlPreviewImage');
    const urlPreviewText = document.getElementById('urlPreviewText');
    const urlLinks = document.querySelectorAll('.url-link');
    const downloadIcons = document.querySelectorAll('.download-icon');
    const downloadModal = document.getElementById('downloadModal');
    const downloadModalMessage = document.getElementById('downloadModalMessage');
    const downloadModalClose = document.getElementById('downloadModalClose');
    const downloadModalTitle = document.getElementById('downloadModalTitle');
    
    let previewTimeout;
    let urlPreviewTimeout;
    let lastFocusedElement = null;

    /**
     * 显示下载弹窗
     * @param {string} message - 弹窗文案
     * @param {string} [title='下载完成'] - 弹窗标题
     */
    function showDownloadModal(message, title = '下载完成') {
        if (!downloadModal || !downloadModalMessage) {
            alert(message);
            return;
        }

        lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        if (downloadModalMessage) {
            downloadModalMessage.textContent = message || '下载成功！';
        }
        if (downloadModalTitle) {
            downloadModalTitle.textContent = title;
        }

        downloadModal.classList.add('show');
        downloadModal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('modal-open');

        if (downloadModalClose) {
            downloadModalClose.focus();
        }
    }

    /**
     * 隐藏下载弹窗
     */
    function hideDownloadModal() {
        if (!downloadModal) return;

        downloadModal.classList.remove('show');
        downloadModal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('modal-open');

        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
        lastFocusedElement = null;
    }

    /**
     * 注册弹窗事件
     */
    function setupDownloadModal() {
        if (!downloadModal) return;

        if (downloadModalClose) {
            downloadModalClose.addEventListener('click', hideDownloadModal);
        }

        downloadModal.addEventListener('click', function(event) {
            if (event.target === downloadModal) {
                hideDownloadModal();
            }
        });

        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape' && downloadModal.classList.contains('show')) {
                hideDownloadModal();
            }
        });
    }
    
    /**
     * 更新图片预览位置
     * @param {MouseEvent} e - 鼠标事件对象
     */
    function updatePreviewPosition(e) {
        if (!preview) return;
        
        const offset = 15;
        let left = e.pageX + offset;
        let top = e.pageY + offset;
        
        // 确保预览窗口不会超出屏幕边界
        if (left + preview.offsetWidth > window.innerWidth) {
            left = e.pageX - preview.offsetWidth - offset;
        }
        if (top + preview.offsetHeight > window.innerHeight) {
            top = e.pageY - preview.offsetHeight - offset;
        }
        if (top < 0) {
            top = offset;
        }
        if (left < 0) {
            left = offset;
        }
        
        preview.style.left = left + 'px';
        preview.style.top = top + 'px';
    }
    
    /**
     * 更新URL预览位置
     * @param {MouseEvent} e - 鼠标事件对象
     */
    function updateUrlPreviewPosition(e) {
        if (!urlPreview) return;
        
        const offset = 15;
        let left = e.pageX + offset;
        let top = e.pageY + offset;
        
        // 确保预览窗口不会超出屏幕边界
        if (left + urlPreview.offsetWidth > window.innerWidth) {
            left = e.pageX - urlPreview.offsetWidth - offset;
        }
        if (top + urlPreview.offsetHeight > window.innerHeight) {
            top = e.pageY - urlPreview.offsetHeight - offset;
        }
        if (top < 0) {
            top = offset;
        }
        if (left < 0) {
            left = offset;
        }
        
        urlPreview.style.left = left + 'px';
        urlPreview.style.top = top + 'px';
    }
    
    /**
     * 判断URL是否是图片
     * @param {string} url - URL地址
     * @returns {boolean} 是否是图片URL
     */
    function isImageUrl(url) {
        if (!url) return false;
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'];
        const lowerUrl = url.toLowerCase();
        return imageExtensions.some(ext => lowerUrl.includes(ext)) || 
               lowerUrl.includes('/image') || 
               lowerUrl.includes('/img') ||
               lowerUrl.includes('/preview') ||
               lowerUrl.includes('/sample') ||
               lowerUrl.includes('/jpeg');
    }
    
    /**
     * 设置文件名悬停预览
     */
    function setupFileNamePreview() {
        if (!fileNames.length || !preview || !previewImage) return;
        
        fileNames.forEach(fileName => {
            fileName.addEventListener('mouseenter', function(e) {
                clearTimeout(previewTimeout);
                
                // 优先使用 preview_url，如果没有则使用 sample_url，最后使用 jpeg_url
                let imageUrl = this.getAttribute('data-preview-url') || 
                              this.getAttribute('data-sample-url') || 
                              this.getAttribute('data-jpeg-url');
                
                if (imageUrl) {
                    previewImage.src = imageUrl;
                    preview.style.display = 'block';
                    updatePreviewPosition(e);
                }
            });
            
            fileName.addEventListener('mousemove', function(e) {
                if (preview && preview.style.display === 'block') {
                    updatePreviewPosition(e);
                }
            });
            
            fileName.addEventListener('mouseleave', function() {
                previewTimeout = setTimeout(() => {
                    if (preview) {
                        preview.style.display = 'none';
                    }
                }, 100);
            });
        });
        
        // 鼠标进入预览窗口时保持显示
        if (preview) {
            preview.addEventListener('mouseenter', function() {
                clearTimeout(previewTimeout);
            });
            
            preview.addEventListener('mouseleave', function() {
                preview.style.display = 'none';
            });
        }
        
        // 图片加载错误处理
        if (previewImage) {
            previewImage.addEventListener('error', function() {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+';
            });
        }
    }
    
    /**
     * 设置URL链接悬停预览
     */
    function setupUrlLinkPreview() {
        if (!urlLinks.length || !urlPreview) return;
        
        urlLinks.forEach(link => {
            link.addEventListener('mouseenter', function(e) {
                clearTimeout(urlPreviewTimeout);
                
                const fullUrl = this.getAttribute('data-full-url') || this.href;
                if (fullUrl) {
                    if (isImageUrl(fullUrl)) {
                        // 显示图片
                        if (urlPreviewImage) {
                            urlPreviewImage.src = fullUrl;
                            urlPreviewImage.style.display = 'block';
                        }
                        if (urlPreviewText) {
                            urlPreviewText.style.display = 'none';
                        }
                        urlPreview.style.display = 'block';
                        updateUrlPreviewPosition(e);
                    } else {
                        // 显示文本
                        if (urlPreviewText) {
                            urlPreviewText.textContent = fullUrl;
                        }
                        if (urlPreviewImage) {
                            urlPreviewImage.style.display = 'none';
                        }
                        if (urlPreviewText) {
                            urlPreviewText.style.display = 'block';
                        }
                        urlPreview.style.display = 'block';
                        updateUrlPreviewPosition(e);
                    }
                }
            });
            
            link.addEventListener('mousemove', function(e) {
                if (urlPreview && urlPreview.style.display === 'block') {
                    updateUrlPreviewPosition(e);
                }
            });
            
            link.addEventListener('mouseleave', function() {
                urlPreviewTimeout = setTimeout(() => {
                    if (urlPreview) {
                        urlPreview.style.display = 'none';
                    }
                }, 100);
            });
        });
        
        // 鼠标进入链接预览窗口时保持显示
        if (urlPreview) {
            urlPreview.addEventListener('mouseenter', function() {
                clearTimeout(urlPreviewTimeout);
            });
            
            urlPreview.addEventListener('mouseleave', function() {
                urlPreview.style.display = 'none';
            });
        }
        
        // 图片加载错误处理
        if (urlPreviewImage) {
            urlPreviewImage.addEventListener('error', function() {
                const fullUrl = this.src;
                if (fullUrl && fullUrl !== '') {
                    if (urlPreviewText) {
                        urlPreviewText.textContent = fullUrl;
                    }
                    if (urlPreviewImage) {
                        urlPreviewImage.style.display = 'none';
                    }
                    if (urlPreviewText) {
                        urlPreviewText.style.display = 'block';
                    }
                }
            });
        }
    }
    
    /**
     * 设置下载功能
     */
    function setupDownload() {
        if (!downloadIcons.length) return;
        
        downloadIcons.forEach(icon => {
            icon.addEventListener('click', function() {
                const imageId = this.getAttribute('data-image-id');
                if (!imageId) {
                    alert('图片ID不存在');
                    return;
                }
                
                // 禁用点击，防止重复下载
                this.style.pointerEvents = 'none';
                this.style.opacity = '0.5';
                const originalText = this.textContent;
                this.textContent = '⏳';
                
                const csrftoken = getCSRFToken();
                
                // 发送下载请求
                fetch(`${downloadBasePath}/download/${imageId}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken
                    },
                    body: JSON.stringify({})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // 更新图标为已下载状态
                        this.textContent = '👁️';
                        this.className = 'view-icon';
                        this.removeAttribute('data-image-id');
                        this.title = '已下载 - 点击查看';
                        showDownloadModal(data.message || '下载成功！', data.title || '下载完成');
                        // 刷新页面以更新状态
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    } else {
                        alert(data.message || '下载失败');
                        this.textContent = originalText;
                        this.style.pointerEvents = 'auto';
                        this.style.opacity = '1';
                    }
                })
                .catch(error => {
                    console.error('下载错误:', error);
                    alert('下载时发生错误: ' + error.message);
                    this.textContent = originalText;
                    this.style.pointerEvents = 'auto';
                    this.style.opacity = '1';
                });
            });
        });
    }
    
    // 初始化
    setupFileNamePreview();
    setupUrlLinkPreview();
    setupDownload();
    setupDownloadModal();
})();

