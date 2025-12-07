/**
 * 首页JavaScript功能文件
 * 包含数据采集表单的交互逻辑
 */

(function() {
    'use strict';
    
    const form = document.getElementById('collectForm');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    const startPageInput = document.getElementById('start_page');
    const endPageInput = document.getElementById('end_page');
    const puritySelect = document.getElementById('purity');
    const apikeyGroup = document.getElementById('apikey-group');
    const apikeyInput = document.getElementById('apikey');
    const sortingSelect = document.getElementById('sorting');
    const toprangeGroup = document.getElementById('toprange-group');
    
    if (!form || !submitBtn) {
        return;
    }
    
    function validateForm() {
        const startPage = parseInt(startPageInput.value);
        const endPage = parseInt(endPageInput.value);
        
        if (endPage < startPage) {
            showMessage('错误：结束页码必须大于等于起始页码！', 'error', statusMessage);
            return false;
        }
        
        // 如果选择了NSFW，验证API key
        if (puritySelect && puritySelect.value === '001') {
            if (!apikeyInput || !apikeyInput.value || apikeyInput.value.trim() === '') {
                showMessage('错误：选择NSFW时必须填写API Key！', 'error', statusMessage);
                return false;
            }
        }
        
        return true;
    }
    
    function setupPurityChange() {
        if (puritySelect && apikeyGroup && apikeyInput) {
            // 初始状态检查
            if (puritySelect.value === '001') {
                apikeyGroup.style.display = 'block';
                apikeyInput.setAttribute('required', 'required');
            } else {
                apikeyGroup.style.display = 'none';
                apikeyInput.removeAttribute('required');
            }
            
            // 监听变化
            puritySelect.addEventListener('change', function() {
                if (this.value === '001') {
                    // 选择NSFW，显示API key输入框
                    apikeyGroup.style.display = 'block';
                    apikeyInput.setAttribute('required', 'required');
                } else {
                    // 选择其他，隐藏API key输入框
                    apikeyGroup.style.display = 'none';
                    apikeyInput.removeAttribute('required');
                }
            });
        }
    }
    
    function setupSortingChange() {
        if (sortingSelect && toprangeGroup) {
            // 初始状态检查
            if (sortingSelect.value === 'toplist') {
                toprangeGroup.style.display = 'block';
            } else {
                toprangeGroup.style.display = 'none';
            }
            
            // 监听变化
            sortingSelect.addEventListener('change', function() {
                if (this.value === 'toplist') {
                    // 选择排行榜，显示日期范围选择器
                    toprangeGroup.style.display = 'block';
                } else {
                    // 选择其他，隐藏日期范围选择器
                    toprangeGroup.style.display = 'none';
                }
            });
        }
    }
    
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
    
    function setupFormSubmit() {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!validateForm()) {
                return;
            }
            
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner"></span>采集中...';
            
            showMessage('正在采集数据，请耐心等待...', 'loading', statusMessage);
            progressBar.style.display = 'block';
            progressFill.style.width = '10%';
            
            let progress = 10;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 5;
                if (progress > 90) progress = 90;
                progressFill.style.width = progress + '%';
            }, 500);
            
            const formData = new FormData(form);
            
            // 如果选择了排行榜，收集所有选中的日期范围
            if (sortingSelect && sortingSelect.value === 'toplist') {
                const toprangeCheckboxes = form.querySelectorAll('input[name="toprange"]:checked');
                if (toprangeCheckboxes.length === 0) {
                    clearInterval(progressInterval);
                    progressFill.style.width = '0%';
                    showMessage('❌ 请至少选择一个日期范围！', 'error', statusMessage);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '开始采集';
                    progressBar.style.display = 'none';
                    return;
                }
                // 移除所有 toprange 参数，然后添加选中的
                formData.delete('toprange');
                toprangeCheckboxes.forEach(checkbox => {
                    formData.append('toprange', checkbox.value);
                });
            }
            
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
    
    function setupResetButton() {
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                hideMessage(statusMessage);
                progressBar.style.display = 'none';
                progressFill.style.width = '0%';
            });
        }
    }
    
    setupRealTimeValidation();
    setupPurityChange();
    setupSortingChange();
    setupFormSubmit();
    setupResetButton();
})();
