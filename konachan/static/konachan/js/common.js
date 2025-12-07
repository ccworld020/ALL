/**
 * 通用JavaScript功能文件
 * 包含CSRF token获取、通用工具函数等
 */

/**
 * 获取CSRF token
 * @returns {string|null} CSRF token值，如果不存在则返回null
 */
function getCSRFToken() {
    // 优先从隐藏的csrf token输入获取
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) {
        return csrfInput.value;
    }
    
    // 如果不存在，则从cookie获取
    return getCookie('csrftoken');
}

/**
 * 从cookie中获取指定名称的值
 * @param {string} name - Cookie名称
 * @returns {string|null} Cookie值，如果不存在则返回null
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * 显示消息提示
 * @param {string} message - 要显示的消息
 * @param {string} type - 消息类型：'success', 'error', 'info', 'warning'
 * @param {HTMLElement} container - 消息容器元素
 */
function showMessage(message, type, container) {
    if (!container) {
        console.error('消息容器不存在');
        return;
    }
    
    container.textContent = message;
    container.className = `status-message status-${type}`;
    container.style.display = 'block';
}

/**
 * 隐藏消息提示
 * @param {HTMLElement} container - 消息容器元素
 */
function hideMessage(container) {
    if (container) {
        container.style.display = 'none';
    }
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的文件大小字符串
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * 防抖函数
 * @param {Function} func - 要执行的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 * @param {Function} func - 要执行的函数
 * @param {number} limit - 时间限制（毫秒）
 * @returns {Function} 节流后的函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

