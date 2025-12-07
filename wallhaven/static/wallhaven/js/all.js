/**
 * 数据展示页面JavaScript功能文件
 * 包含壁纸预览、URL预览、下载等功能
 */

(function() {
    'use strict';
    
    /**
     * 计算当前Wallhaven应用的基础路径，例如 /w
     * @param {string} fallback 默认路径
     * @returns {string}
     */
    function getAppBasePath(fallback) {
        const segments = window.location.pathname.split('/').filter(Boolean);
        if (segments.length > 0) {
            return `/${segments[0]}`;
        }
        return fallback;
    }

    const downloadBasePath = window.__WALLHAVEN_BASE_PATH__ || getAppBasePath('/w');
    
    // 获取DOM元素
    const preview = document.getElementById('wallpaperPreview');
    const previewWallpaper = document.getElementById('previewWallpaper');
    const fileNames = document.querySelectorAll('.file-name');
    const urlPreview = document.getElementById('urlPreview');
    const urlPreviewImage = document.getElementById('urlPreviewImage');
    const urlPreviewText = document.getElementById('urlPreviewText');
    const urlLinks = document.querySelectorAll('.url-link');
    const downloadIcons = document.querySelectorAll('.download-icon');
    const viewIcons = document.querySelectorAll('.view-icon');
    const downloadModal = document.getElementById('downloadModal');
    const downloadModalMessage = document.getElementById('downloadModalMessage');
    const downloadModalClose = document.getElementById('downloadModalClose');
    
    let previewTimeout;
    let urlPreviewTimeout;
    
    /**
     * 更新壁纸预览位置
     * @param {MouseEvent} e - 鼠标事件对象
     */
    function updatePreviewPosition(e) {
        if (!preview) return;
        
        const offset = 15;
        const previewWidth = preview.offsetWidth || 300;
        const previewHeight = preview.offsetHeight || 300;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        // 检查预览窗口是否超出屏幕范围
        const exceedsWidth = previewWidth > windowWidth - offset * 2;
        const exceedsHeight = previewHeight > windowHeight - offset * 2;
        
        if (exceedsWidth || exceedsHeight) {
            // 如果超出屏幕范围，采用居中显示
            preview.style.left = '50%';
            preview.style.top = '50%';
            preview.style.transform = 'translate(-50%, -50%)';
            preview.style.margin = '0';
        } else {
            // 如果没有超出，使用跟随鼠标的逻辑
            preview.style.transform = 'none';
            let left = e.pageX + offset;
            let top = e.pageY + offset;
            
            // 确保预览窗口不会超出屏幕边界
            if (left + previewWidth > windowWidth) {
                left = e.pageX - previewWidth - offset;
            }
            if (top + previewHeight > windowHeight) {
                top = e.pageY - previewHeight - offset;
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
    }
    
    /**
     * 更新URL预览位置
     * @param {MouseEvent} e - 鼠标事件对象
     */
    function updateUrlPreviewPosition(e) {
        if (!urlPreview) return;
        
        const offset = 15;
        const previewWidth = urlPreview.offsetWidth || 300;
        const previewHeight = urlPreview.offsetHeight || 300;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        // 检查预览窗口是否超出屏幕范围
        const exceedsWidth = previewWidth > windowWidth - offset * 2;
        const exceedsHeight = previewHeight > windowHeight - offset * 2;
        
        if (exceedsWidth || exceedsHeight) {
            // 如果超出屏幕范围，采用居中显示
            urlPreview.style.left = '50%';
            urlPreview.style.top = '50%';
            urlPreview.style.transform = 'translate(-50%, -50%)';
            urlPreview.style.margin = '0';
        } else {
            // 如果没有超出，使用跟随鼠标的逻辑
            urlPreview.style.transform = 'none';
            let left = e.pageX + offset;
            let top = e.pageY + offset;
            
            // 确保预览窗口不会超出屏幕边界
            if (left + previewWidth > windowWidth) {
                left = e.pageX - previewWidth - offset;
            }
            if (top + previewHeight > windowHeight) {
                top = e.pageY - previewHeight - offset;
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
               lowerUrl.includes('/wallpaper') ||
               lowerUrl.includes('/thumbs');
    }
    
    /**
     * 设置文件名悬停预览
     */
    function setupFileNamePreview() {
        if (!fileNames.length || !preview || !previewWallpaper) return;
        
        let currentMouseEvent = null;
        
        fileNames.forEach(fileName => {
            fileName.addEventListener('mouseenter', function(e) {
                clearTimeout(previewTimeout);
                currentMouseEvent = e;
                
                // 获取壁纸URL
                let wallpaperUrl = this.getAttribute('data-wallpaper-url');
                
                if (wallpaperUrl) {
                    // 先显示预览容器
                    preview.style.display = 'block';
                    // 设置图片源
                    previewWallpaper.src = wallpaperUrl;
                    // 初始位置计算
                    updatePreviewPosition(e);
                }
            });
            
            fileName.addEventListener('mousemove', function(e) {
                if (preview && preview.style.display === 'block') {
                    currentMouseEvent = e;
                    updatePreviewPosition(e);
                }
            });
            
            fileName.addEventListener('mouseleave', function() {
                previewTimeout = setTimeout(() => {
                    if (preview) {
                        preview.style.display = 'none';
                    }
                    currentMouseEvent = null;
                }, 100);
            });
        });
        
        // 图片加载完成后重新计算位置
        if (previewWallpaper) {
            previewWallpaper.addEventListener('load', function() {
                if (preview && preview.style.display === 'block' && currentMouseEvent) {
                    // 图片加载完成后，重新计算位置以确保居中显示（如果需要）
                    updatePreviewPosition(currentMouseEvent);
                }
            });
            
            // 图片加载错误处理
            previewWallpaper.addEventListener('error', function() {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+';
            });
        }
        
        // 鼠标进入预览窗口时保持显示
        if (preview) {
            preview.addEventListener('mouseenter', function() {
                clearTimeout(previewTimeout);
            });
            
            preview.addEventListener('mouseleave', function() {
                preview.style.display = 'none';
                currentMouseEvent = null;
            });
        }
    }
    
    /**
     * 设置URL链接悬停预览
     */
    function setupUrlLinkPreview() {
        if (!urlLinks.length || !urlPreview) return;
        
        let currentUrlMouseEvent = null;
        
        urlLinks.forEach(link => {
            link.addEventListener('mouseenter', function(e) {
                clearTimeout(urlPreviewTimeout);
                currentUrlMouseEvent = e;
                
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
                    currentUrlMouseEvent = e;
                    updateUrlPreviewPosition(e);
                }
            });
            
            link.addEventListener('mouseleave', function() {
                urlPreviewTimeout = setTimeout(() => {
                    if (urlPreview) {
                        urlPreview.style.display = 'none';
                    }
                    currentUrlMouseEvent = null;
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
                currentUrlMouseEvent = null;
            });
        }
        
        // 图片加载完成后重新计算位置
        if (urlPreviewImage) {
            urlPreviewImage.addEventListener('load', function() {
                if (urlPreview && urlPreview.style.display === 'block' && currentUrlMouseEvent) {
                    // 图片加载完成后，重新计算位置以确保居中显示（如果需要）
                    updateUrlPreviewPosition(currentUrlMouseEvent);
                }
            });
            
            // 图片加载错误处理
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
                const wallpaperId = this.getAttribute('data-wallpaper-id');
                if (!wallpaperId) {
                    alert('壁纸ID不存在');
                    return;
                }
                
                downloadWallpaper(wallpaperId);
            });
        });
    }
    
    /**
     * 设置查看功能
     */
    function setupView() {
        if (!viewIcons.length) return;
        
        viewIcons.forEach(icon => {
            icon.addEventListener('click', function() {
                const row = this.closest('tr');
                const wallpaperUrl = row.querySelector('.file-name').getAttribute('data-wallpaper-url');
                if (wallpaperUrl) {
                    window.open(wallpaperUrl, '_blank');
                }
            });
        });
    }
    
    /**
     * 下载壁纸
     */
    function downloadWallpaper(wallpaperId) {
        const csrfToken = getCSRFToken();
        if (!csrfToken) {
            alert('无法获取CSRF token');
            return;
        }
        
        fetch(`${downloadBasePath}/download/${wallpaperId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showDownloadModal('下载完成！');
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                showDownloadModal('下载失败：' + data.message);
            }
        })
        .catch(error => {
            showDownloadModal('下载失败：' + error.message);
        });
    }
    
    /**
     * 显示下载弹窗
     */
    function showDownloadModal(message) {
        if (downloadModal && downloadModalMessage) {
            downloadModalMessage.textContent = message;
            downloadModal.style.display = 'flex';
        }
    }
    
    /**
     * 设置下载弹窗
     */
    function setupDownloadModal() {
        if (downloadModalClose) {
            downloadModalClose.addEventListener('click', function() {
                if (downloadModal) {
                    downloadModal.style.display = 'none';
                }
            });
        }
        
        if (downloadModal) {
            downloadModal.addEventListener('click', function(e) {
                if (e.target === downloadModal) {
                    downloadModal.style.display = 'none';
                }
            });
        }
    }
    
    // 初始化
    setupFileNamePreview();
    setupUrlLinkPreview();
    setupDownload();
    setupView();
    setupDownloadModal();
})();
