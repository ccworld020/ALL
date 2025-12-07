/**
 * 图片画廊JavaScript功能文件
 * 包含图片弹窗、预览、下载等功能
 * 用于local.html和online.html页面
 */

(function() {
    'use strict';
    
    /**
     * 计算当前应用的基础路径，例如 /k
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

    const downloadBasePath = window.__KONACHAN_BASE_PATH__ || getAppBasePath('/k');
    
    // 获取DOM元素
    const imageWrappers = document.querySelectorAll('.image-wrapper');
    const sampleButtons = document.querySelectorAll('.btn-sample');
    const jpegButtons = document.querySelectorAll('.btn-jpeg');
    const downloadButtons = document.querySelectorAll('.btn-download');
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalClose = document.getElementById('modalClose');
    
    /**
     * 打开图片弹窗
     * @param {string} imageUrl - 图片URL地址
     */
    function openModal(imageUrl) {
        if (!modal || !modalImage) return;
        
        modalImage.src = imageUrl;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden'; // 禁止背景滚动
    }
    
    /**
     * 关闭图片弹窗
     */
    function closeModal() {
        if (!modal) return;
        
        modal.classList.remove('active');
        document.body.style.overflow = 'auto'; // 恢复背景滚动
        if (modalImage) {
            modalImage.src = ''; // 清空图片源
        }
    }
    
    /**
     * 设置图片点击预览
     */
    function setupImagePreview() {
        imageWrappers.forEach(wrapper => {
            wrapper.addEventListener('click', function(e) {
                // 如果点击的是按钮，不触发图片预览
                if (e.target.closest('.btn')) {
                    return;
                }
                const previewUrl = this.getAttribute('data-preview-url');
                if (previewUrl) {
                    openModal(previewUrl);
                }
            });
        });
    }
    
    /**
     * 设置Sample按钮点击事件
     */
    function setupSampleButtons() {
        sampleButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.stopPropagation(); // 阻止事件冒泡
                const imageWrapper = this.closest('.masonry-item')?.querySelector('.image-wrapper');
                const sampleUrl = imageWrapper?.getAttribute('data-sample-url') || 
                                this.getAttribute('data-image-url');
                if (sampleUrl) {
                    openModal(sampleUrl);
                }
            });
        });
    }
    
    /**
     * 设置JPEG按钮点击事件
     */
    function setupJpegButtons() {
        jpegButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.stopPropagation(); // 阻止事件冒泡
                const imageWrapper = this.closest('.masonry-item')?.querySelector('.image-wrapper');
                const jpegUrl = imageWrapper?.getAttribute('data-jpeg-url') || 
                               this.getAttribute('data-image-url');
                if (jpegUrl) {
                    openModal(jpegUrl);
                }
            });
        });
    }
    
    /**
     * 设置下载按钮点击事件
     */
    function setupDownloadButtons() {
        if (!downloadButtons.length) return;
        
        downloadButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.stopPropagation(); // 阻止事件冒泡
                const imageId = this.getAttribute('data-image-id');
                if (!imageId) {
                    console.error('图片ID不存在');
                    return;
                }
                
                // 禁用按钮，防止重复下载
                this.disabled = true;
                const originalText = this.textContent;
                this.textContent = '下载中...';
                
                // 更新状态提示
                const statusElement = document.getElementById(`status-${imageId}`);
                if (statusElement) {
                    statusElement.textContent = '正在下载...';
                    statusElement.style.color = '#667eea';
                }
                
                const csrftoken = getCSRFToken();
                if (!csrftoken) {
                    this.disabled = false;
                    this.textContent = originalText;
                    if (statusElement) {
                        statusElement.textContent = '无法获取CSRF token';
                        statusElement.style.color = '#dc3545';
                    }
                    return;
                }
                
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
                        // 更新按钮状态
                        this.textContent = '已下载';
                        this.disabled = true;
                        this.classList.add('downloaded');
                        
                        // 更新状态提示
                        if (statusElement) {
                            statusElement.textContent = '下载完成！';
                            statusElement.style.color = '#28a745';
                        }
                    } else {
                        // 恢复按钮状态
                        this.disabled = false;
                        this.textContent = originalText;
                        
                        // 更新状态提示
                        if (statusElement) {
                            statusElement.textContent = '下载失败：' + (data.message || '未知错误');
                            statusElement.style.color = '#dc3545';
                        }
                    }
                })
                .catch(error => {
                    console.error('下载错误:', error);
                    
                    // 恢复按钮状态
                    this.disabled = false;
                    this.textContent = originalText;
                    
                    // 更新状态提示
                    if (statusElement) {
                        statusElement.textContent = '下载失败：' + error.message;
                        statusElement.style.color = '#dc3545';
                    }
                });
            });
        });
    }
    
    /**
     * 设置弹窗关闭功能
     */
    function setupModalClose() {
        if (modalClose) {
            modalClose.addEventListener('click', closeModal);
        }
        
        // 点击弹窗背景关闭
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closeModal();
                }
            });
        }
        
        // ESC 键关闭弹窗
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
                closeModal();
            }
        });
    }
    
    /**
     * 设置图片加载错误处理
     */
    function setupImageErrorHandling() {
        if (modalImage) {
            modalImage.addEventListener('error', function() {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTgiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+';
            });
        }
    }
    
    // 初始化
    setupImagePreview();
    setupSampleButtons();
    setupJpegButtons();
    setupDownloadButtons();
    setupModalClose();
    setupImageErrorHandling();
})();

