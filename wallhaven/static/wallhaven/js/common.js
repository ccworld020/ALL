/**
 * 通用JavaScript功能文件
 * 包含CSRF token获取、通用工具函数等
 */

/**
 * 获取CSRF token
 * @returns {string|null} CSRF token值，如果不存在则返回null
 */
function getCSRFToken() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) {
        return csrfInput.value;
    }
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
