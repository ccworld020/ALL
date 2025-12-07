/**
 * 首页JavaScript功能文件
 * 包含数据采集表单的交互逻辑
 */

(function() {
    'use strict';
    
    // 获取DOM元素
    const form = document.getElementById('collectForm');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    const startPageInput = document.getElementById('start_page');
    const endPageInput = document.getElementById('end_page');
    
    // 如果元素不存在，直接返回
    if (!form || !submitBtn) {
        return;
    }
    
    /**
     * 验证表单数据
     * @returns {boolean} 验证是否通过
     */
    function validateForm() {
        const startPage = parseInt(startPageInput.value);
        const endPage = parseInt(endPageInput.value);
        
        if (endPage < startPage) {
            showMessage('错误：结束页码必须大于等于起始页码！', 'error', statusMessage);
            return false;
        }
        return true;
    }
    
    /**
     * 实时验证页码输入
     */
    function setupRealTimeValidation() {
        const validatePages = () => {
            if (parseInt(endPageInput.value) < parseInt(startPageInput.value)) {
                endPageInput.setCustomValidity('结束页码必须大于等于起始页码');
            } else {
                endPageInput.setCustomValidity('');
            }
        };
        
        endPageInput.addEventListener('input', validatePages);
        startPageInput.addEventListener('input', validatePages);
    }
    
    /**
     * 处理表单提交
     */
    function setupFormSubmit() {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!validateForm()) {
                return;
            }
            
            // 禁用提交按钮
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner"></span>采集中...';
            
            // 显示加载状态
            showMessage('正在采集数据，请耐心等待...', 'loading', statusMessage);
            progressBar.style.display = 'block';
            progressFill.style.width = '10%';
            
            // 模拟进度（实际进度由后端控制）
            let progress = 10;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 5;
                if (progress > 90) progress = 90;
                progressFill.style.width = progress + '%';
            }, 500);
            
            // 提交表单
            const formData = new FormData(form);
            
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                }
            })
            .then(response => {
                clearInterval(progressInterval);
                progressFill.style.width = '100%';
                
                if (response.ok) {
                    return response.text();
                } else {
                    throw new Error('服务器响应错误');
                }
            })
            .then(data => {
                setTimeout(() => {
                    showMessage('✅ ' + data, 'success', statusMessage);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '开始采集';
                    progressBar.style.display = 'none';
                    progressFill.style.width = '0%';
                }, 500);
            })
            .catch(error => {
                clearInterval(progressInterval);
                progressFill.style.width = '0%';
                showMessage('❌ 采集失败：' + error.message, 'error', statusMessage);
                submitBtn.disabled = false;
                submitBtn.innerHTML = '开始采集';
                progressBar.style.display = 'none';
            });
        });
    }
    
    /**
     * 设置重置按钮功能
     */
    function setupResetButton() {
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                hideMessage(statusMessage);
                progressBar.style.display = 'none';
                progressFill.style.width = '0%';
            });
        }
    }
    
    // 初始化
    setupRealTimeValidation();
    setupFormSubmit();
    setupResetButton();
})();

