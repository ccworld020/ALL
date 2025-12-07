/**
 * 壁纸画廊JavaScript功能文件
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
    
    const modal = document.getElementById('wallpaperModal');
    const modalImage = document.getElementById('modalWallpaper');
    const modalClose = document.getElementById('modalClose');
    const downloadButtons = document.querySelectorAll('.btn-download');
    
    // 打开模态框
    document.querySelectorAll('.wallpaper-wrapper').forEach(wrapper => {
        wrapper.addEventListener('click', function() {
            const wallpaperUrl = this.getAttribute('data-wallpaper-url');
            if (wallpaperUrl && modal && modalImage) {
                modalImage.src = wallpaperUrl;
                modal.style.display = 'block';
            }
        });
    });
    
    // 关闭模态框
    if (modalClose) {
        modalClose.addEventListener('click', function() {
            if (modal) {
                modal.style.display = 'none';
            }
        });
    }
    
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
    
    // 下载功能
    downloadButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const wallpaperId = this.getAttribute('data-wallpaper-id');
            const statusDiv = document.getElementById(`status-${wallpaperId}`);
            
            if (!wallpaperId) return;
            
            this.disabled = true;
            this.textContent = '下载中...';
            if (statusDiv) {
                statusDiv.textContent = '正在下载...';
            }
            
            const csrfToken = getCSRFToken();
            if (!csrfToken) {
                this.disabled = false;
                this.textContent = 'Download';
                if (statusDiv) {
                    statusDiv.textContent = '无法获取CSRF token';
                    statusDiv.style.color = '#dc3545';
                }
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
                    this.textContent = '已下载';
                    this.disabled = true;
                    this.classList.add('downloaded');
                    if (statusDiv) {
                        statusDiv.textContent = '下载完成！';
                        statusDiv.style.color = '#28a745';
                    }
                } else {
                    this.disabled = false;
                    this.textContent = 'Download';
                    if (statusDiv) {
                        statusDiv.textContent = '下载失败：' + data.message;
                        statusDiv.style.color = '#dc3545';
                    }
                }
            })
            .catch(error => {
                this.disabled = false;
                this.textContent = 'Download';
                if (statusDiv) {
                    statusDiv.textContent = '下载失败：' + error.message;
                    statusDiv.style.color = '#dc3545';
                }
            });
        });
    });
})();
