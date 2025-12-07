const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB per chunk
        let currentMode = 'files';
        let fileQueue = [];
        let uploading = false;
        let categories = [];
        let tags = [];

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            loadCategoriesAndTags();
            setupUploadArea();
        });

        // 加载分类和标签
        async function loadCategoriesAndTags() {
            try {
                const [catRes, tagRes] = await Promise.all([
                    fetch('/fs/api/ct/?flag=C'),
                    fetch('/fs/api/ct/?flag=T')
                ]);
                
                const catData = await catRes.json();
                const tagData = await tagRes.json();
                
                categories = catData.data || [];
                tags = tagData.data || [];
                
                renderSelectors();
            } catch (error) {
                console.error('加载分类/标签失败:', error);
            }
        }

        // 渲染选择器
        function renderSelectors() {
            const catSelector = document.getElementById('categorySelector');
            const tagSelector = document.getElementById('tagSelector');
            
            catSelector.innerHTML = categories.map(cat => `
                <div class="selector-item">
                    <input type="checkbox" id="cat_${cat.id}" value="${cat.id}">
                    <label for="cat_${cat.id}">${escapeHtml(cat.name)}</label>
                </div>
            `).join('');
            
            tagSelector.innerHTML = tags.map(tag => `
                <div class="selector-item">
                    <input type="checkbox" id="tag_${tag.id}" value="${tag.id}">
                    <label for="tag_${tag.id}">${escapeHtml(tag.name)}</label>
                </div>
            `).join('');
        }

        // 检测拖拽项是文件还是文件夹
        function detectDragType(dataTransfer) {
            // 检查是否有目录项
            if (dataTransfer.items) {
                for (let item of dataTransfer.items) {
                    if (item.webkitGetAsEntry) {
                        const entry = item.webkitGetAsEntry();
                        if (entry && entry.isDirectory) {
                            return 'folder';
                        }
                    }
                }
            }
            // 检查文件列表
            if (dataTransfer.files && dataTransfer.files.length > 0) {
                // 如果有webkitRelativePath，说明是文件夹
                for (let file of dataTransfer.files) {
                    if (file.webkitRelativePath) {
                        return 'folder';
                    }
                }
            }
            return 'files';
        }

        // 设置上传区域
        function setupUploadArea() {
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const folderInput = document.getElementById('folderInput');
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadArea.classList.remove('dragover');
                
                // 检测拖拽的是文件还是文件夹
                const dragType = detectDragType(e.dataTransfer);
                
                if (dragType === 'folder') {
                    // 文件夹拖拽
                    currentMode = 'folder';
                    // 使用DataTransfer API获取文件夹内容
                    handleFolderDrop(e.dataTransfer);
                } else {
                    // 文件拖拽
                    currentMode = 'files';
                    handleFiles(e.dataTransfer.files);
                }
            });
            
            fileInput.addEventListener('change', (e) => {
                currentMode = 'files';
                handleFiles(e.target.files);
            });
            
            folderInput.addEventListener('change', (e) => {
                currentMode = 'folder';
                handleFiles(e.target.files);
            });
        }

        // 处理文件夹拖拽
        function handleFolderDrop(dataTransfer) {
            const items = dataTransfer.items;
            const files = [];
            
            function processEntry(entry, path = '') {
                return new Promise((resolve) => {
                    if (entry.isFile) {
                        entry.file((file) => {
                            // 设置webkitRelativePath以保持路径信息
                            Object.defineProperty(file, 'webkitRelativePath', {
                                value: path + file.name,
                                writable: false
                            });
                            files.push(file);
                            resolve();
                        });
                    } else if (entry.isDirectory) {
                        const dirReader = entry.createReader();
                        const entries = [];
                        
                        function readEntries() {
                            dirReader.readEntries((results) => {
                                if (results.length > 0) {
                                    entries.push(...results);
                                    readEntries();
                                } else {
                                    // 处理所有子项
                                    Promise.all(entries.map(subEntry => 
                                        processEntry(subEntry, path + entry.name + '/')
                                    )).then(() => resolve());
                                }
                            });
                        }
                        
                        readEntries();
                    } else {
                        resolve();
                    }
                });
            }
            
            // 处理所有拖拽项
            const promises = [];
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.webkitGetAsEntry) {
                    const entry = item.webkitGetAsEntry();
                    if (entry) {
                        promises.push(processEntry(entry));
                    }
                }
            }
            
            Promise.all(promises).then(() => {
                if (files.length > 0) {
                    // 创建FileList对象
                    const dataTransfer = new DataTransfer();
                    files.forEach(file => dataTransfer.items.add(file));
                    handleFiles(dataTransfer.files);
                } else {
                    showToast('未找到有效文件', 'error');
                }
            });
        }

        // 触发文件选择
        function triggerFileInput() {
            currentMode = 'files';
            document.getElementById('fileInput').click();
        }

        // 触发文件夹选择
        function triggerFolderInput() {
            currentMode = 'folder';
            document.getElementById('folderInput').click();
        }

        // 处理文件
        async function handleFiles(files) {
            const fileArray = Array.from(files);
            
            // 根据当前模式过滤文件
            let actualFiles = fileArray;
            
            if (currentMode === 'files') {
                // 文件模式：只接受文件，拒绝文件夹
                actualFiles = fileArray.filter(file => {
                    // 如果有webkitRelativePath，说明来自文件夹，拒绝
                    if (file.webkitRelativePath) {
                        return false;
                    }
                    // 确保是文件
                    return file.size >= 0;
                });
                
                if (actualFiles.length < fileArray.length) {
                    showToast('文件模式下不允许上传文件夹，已过滤文件夹内容', 'error');
                }
            } else if (currentMode === 'folder') {
                // 文件夹模式：只接受来自文件夹的文件
                actualFiles = fileArray.filter(file => {
                    // 必须有webkitRelativePath，说明来自文件夹
                    if (!file.webkitRelativePath) {
                        return false;
                    }
                    // 确保是文件而不是目录
                    return file.size > 0 || !file.webkitRelativePath.endsWith('/');
                });
                
                if (actualFiles.length < fileArray.length) {
                    showToast('文件夹模式下只接受文件夹内容，已过滤单独文件', 'error');
                }
            }
            
            // 过滤掉空文件和目录
            actualFiles = actualFiles.filter(file => {
                return file.size > 0 || (file.webkitRelativePath && !file.webkitRelativePath.endsWith('/'));
            });
            
            if (actualFiles.length === 0) {
                showToast('未找到有效文件', 'error');
                return;
            }
            
            showToast(`正在处理 ${actualFiles.length} 个文件...`, 'info');
            
            for (let file of actualFiles) {
                try {
                    // 计算MD5
                    const md5 = await calculateMD5(file);
                    
                    // 检查文件是否已存在
                    const exists = await checkFileExists(md5);
                    
                    // 解析路径（文件夹上传时）
                    let album = '';
                    let subject = '';
                    if (currentMode === 'folder' && file.webkitRelativePath) {
                        // 处理路径，支持Windows和Unix路径分隔符
                        const path = file.webkitRelativePath.replace(/\\/g, '/');
                        const parts = path.split('/').filter(p => p.length > 0);
                        
                        // 一级目录作为Album
                        if (parts.length > 1) {
                            album = parts[0];
                        }
                        // 二级目录作为Subject（不管后面有多少级目录）
                        if (parts.length > 2) {
                            subject = parts[1];
                        }
                    }
                    
                    fileQueue.push({
                        file: file,
                        md5: md5,
                        album: album,
                        subject: subject,
                        status: exists ? 'skipped' : 'waiting',
                        progress: 0,
                        exists: exists
                    });
                } catch (error) {
                    console.error('处理文件失败:', file.name, error);
                    showToast(`处理文件 ${file.name} 失败: ${error.message}`, 'error');
                }
            }
            
            renderFileList();
            updateStats();
            
            if (fileQueue.length > 0) {
                showToast(`已添加 ${fileQueue.length} 个文件到上传队列`, 'success');
            }
        }

        // 计算MD5
        function calculateMD5(file) {
            return new Promise((resolve) => {
                // 使用SparkMD5库计算MD5
                if (typeof SparkMD5 !== 'undefined') {
                    const spark = new SparkMD5.ArrayBuffer();
                    const fileReader = new FileReader();
                    const chunkSize = 2 * 1024 * 1024; // 2MB chunks
                    let currentChunk = 0;
                    const chunks = Math.ceil(file.size / chunkSize);
                    
                    fileReader.onload = function(e) {
                        spark.append(e.target.result);
                        currentChunk++;
                        
                        if (currentChunk < chunks) {
                            loadNext();
                        } else {
                            resolve(spark.end());
                        }
                    };
                    
                    fileReader.onerror = function() {
                        // 如果计算失败，使用文件名+大小+时间的组合作为临时标识
                        const fallback = file.name + file.size + file.lastModified;
                        resolve(Array.from(new TextEncoder().encode(fallback))
                            .map(b => b.toString(16).padStart(2, '0'))
                            .join('').substring(0, 32));
                    };
                    
                    function loadNext() {
                        const start = currentChunk * chunkSize;
                        const end = Math.min(start + chunkSize, file.size);
                        fileReader.readAsArrayBuffer(file.slice(start, end));
                    }
                    
                    loadNext();
                } else {
                    // 如果没有SparkMD5库，使用简化方法（仅用于演示，实际应该加载库）
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        // 使用Web Crypto API计算哈希（如果支持）
                        if (window.crypto && window.crypto.subtle) {
                            window.crypto.subtle.digest('SHA-256', e.target.result)
                                .then(hashBuffer => {
                                    const hashArray = Array.from(new Uint8Array(hashBuffer));
                                    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
                                    // SHA-256转MD5格式（截取前32位）
                                    resolve(hashHex.substring(0, 32));
                                })
                                .catch(() => {
                                    // 降级方案
                                    const fallback = file.name + file.size + file.lastModified;
                                    resolve(Array.from(new TextEncoder().encode(fallback))
                                        .map(b => b.toString(16).padStart(2, '0'))
                                        .join('').substring(0, 32));
                                });
                        } else {
                            // 最终降级方案
                            const fallback = file.name + file.size + file.lastModified;
                            resolve(Array.from(new TextEncoder().encode(fallback))
                                .map(b => b.toString(16).padStart(2, '0'))
                                .join('').substring(0, 32));
                        }
                    };
                    // 只读取文件的一部分来计算（大文件优化）
                    const sampleSize = Math.min(1024 * 1024, file.size); // 1MB样本
                    reader.readAsArrayBuffer(file.slice(0, sampleSize));
                }
            });
        }

        // 检查文件是否存在
        async function checkFileExists(md5) {
            try {
                const response = await fetch('/fs/api/upload/check/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({file_md5: md5})
                });
                const result = await response.json();
                return result.exists || false;
            } catch (error) {
                console.error('检查文件失败:', error);
                return false;
            }
        }

        // 渲染文件列表
        function renderFileList() {
            const fileList = document.getElementById('fileList');
            const actionsBar = document.getElementById('actionsBar');
            
            if (fileQueue.length === 0) {
                fileList.style.display = 'none';
                actionsBar.style.display = 'none';
                return;
            }
            
            fileList.style.display = 'block';
            actionsBar.style.display = 'flex';
            
            fileList.innerHTML = fileQueue.map((item, index) => {
                const file = item.file;
                const statusClass = `status-${item.status}`;
                const statusText = {
                    'waiting': '等待中',
                    'uploading': '上传中',
                    'success': '成功',
                    'error': '失败',
                    'skipped': '已存在'
                }[item.status] || '未知';
                
                return `
                    <div class="file-item">
                        <div class="file-info">
                            <div class="file-name">${escapeHtml(file.name)}</div>
                            ${file.webkitRelativePath ? `<div class="file-path">${escapeHtml(file.webkitRelativePath)}</div>` : ''}
                        </div>
                        <div class="file-size">${formatFileSize(file.size)}</div>
                        <div class="file-progress">
                            <div class="file-progress-bar" style="width: ${item.progress}%"></div>
                        </div>
                        <div class="file-status ${statusClass}">${statusText}</div>
                        <div class="file-actions">
                            <button class="btn btn-remove" onclick="removeFile(${index})">删除</button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // 更新统计
        function updateStats() {
            document.getElementById('totalFiles').textContent = fileQueue.length;
            document.getElementById('successFiles').textContent = fileQueue.filter(f => f.status === 'success').length;
            document.getElementById('failedFiles').textContent = fileQueue.filter(f => f.status === 'error').length;
            document.getElementById('skippedFiles').textContent = fileQueue.filter(f => f.status === 'skipped').length;
        }

        // 移除文件
        function removeFile(index) {
            fileQueue.splice(index, 1);
            renderFileList();
            updateStats();
        }

        // 清空文件列表
        function clearFiles() {
            if (uploading) {
                if (!confirm('正在上传中，确定要清空列表吗？')) {
                    return;
                }
            }
            fileQueue = [];
            renderFileList();
            updateStats();
        }

        // 开始上传
        async function startUpload() {
            if (uploading) {
                showToast('正在上传中，请稍候...', 'info');
                return;
            }
            
            if (fileQueue.length === 0) {
                showToast('请先选择文件', 'error');
                return;
            }
            
            uploading = true;
            document.getElementById('uploadBtn').disabled = true;
            document.getElementById('uploadBtn').textContent = '上传中...';
            
            // 获取表单数据
            const author = document.getElementById('author').value;
            const level = document.getElementById('level').value;
            const remark = document.getElementById('remark').value;
            const generateThumbnail = document.getElementById('generateThumbnail').checked;
            const categoryIds = Array.from(document.querySelectorAll('#categorySelector input:checked')).map(cb => parseInt(cb.value));
            const tagIds = Array.from(document.querySelectorAll('#tagSelector input:checked')).map(cb => parseInt(cb.value));
            
            // 批量上传（限制并发数）
            const CONCURRENT = 3;
            const waitingFiles = fileQueue.filter(f => f.status === 'waiting');
            
            for (let i = 0; i < waitingFiles.length; i += CONCURRENT) {
                const batch = waitingFiles.slice(i, i + CONCURRENT);
                await Promise.all(batch.map(item => uploadFile(item, author, level, remark, categoryIds, tagIds, generateThumbnail)));
            }
            
            uploading = false;
            document.getElementById('uploadBtn').disabled = false;
            document.getElementById('uploadBtn').textContent = '开始上传';
            updateStats();
            showToast('所有文件处理完成', 'success');
        }

        // 生成图片缩略图
        async function generateImageThumbnail(file) {
            return new Promise((resolve, reject) => {
                const img = new Image();
                const objectUrl = URL.createObjectURL(file);
                
                img.onload = function() {
                    try {
                        // 创建canvas
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        
                        // 计算缩略图尺寸（最大300x300）
                        let width = img.width;
                        let height = img.height;
                        const maxSize = 300;
                        
                        if (width > height) {
                            if (width > maxSize) {
                                height = (height * maxSize) / width;
                                width = maxSize;
                            }
                        } else {
                            if (height > maxSize) {
                                width = (width * maxSize) / height;
                                height = maxSize;
                            }
                        }
                        
                        canvas.width = width;
                        canvas.height = height;
                        
                        // 绘制图片
                        ctx.drawImage(img, 0, 0, width, height);
                        
                        // 转换为base64
                        const thumbnailData = canvas.toDataURL('image/jpeg', 0.85);
                        // 提取base64数据部分（去掉data:image/jpeg;base64,前缀）
                        const base64Data = thumbnailData.split(',')[1];
                        
                        // 清理URL对象
                        URL.revokeObjectURL(objectUrl);
                        
                        resolve(base64Data);
                    } catch (error) {
                        URL.revokeObjectURL(objectUrl);
                        reject(error);
                    }
                };
                img.onerror = function() {
                    URL.revokeObjectURL(objectUrl);
                    reject(new Error('图片加载失败'));
                };
                img.src = objectUrl;
            });
        }

        // 生成视频缩略图
        async function generateVideoThumbnail(file) {
            return new Promise((resolve, reject) => {
                const video = document.createElement('video');
                video.preload = 'metadata';
                video.muted = true;
                video.playsInline = true;
                
                let timeoutId = null;
                let resolved = false;
                
                const cleanup = () => {
                    if (timeoutId) {
                        clearTimeout(timeoutId);
                        timeoutId = null;
                    }
                    if (video.src) {
                        URL.revokeObjectURL(video.src);
                        video.src = '';
                    }
                };
                
                const handleSuccess = (base64Data) => {
                    if (resolved) return;
                    resolved = true;
                    cleanup();
                    resolve(base64Data);
                };
                
                const handleError = (error) => {
                    if (resolved) return;
                    resolved = true;
                    cleanup();
                    reject(error);
                };
                
                // 设置超时（10秒）
                timeoutId = setTimeout(() => {
                    handleError(new Error('视频缩略图生成超时'));
                }, 10000);
                
                video.onloadedmetadata = function() {
                    try {
                        // 跳转到第1秒（如果视频长度足够）
                        if (video.duration > 1) {
                            video.currentTime = 1;
                        } else {
                            video.currentTime = 0;
                        }
                    } catch (error) {
                        // 如果无法跳转，使用第0秒
                        video.currentTime = 0;
                    }
                };
                
                video.onseeked = function() {
                    try {
                        // 确保视频尺寸有效
                        if (!video.videoWidth || !video.videoHeight) {
                            handleError(new Error('无法获取视频尺寸'));
                            return;
                        }
                        
                        // 创建canvas
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        
                        // 计算缩略图尺寸（最大300x300）
                        let width = video.videoWidth;
                        let height = video.videoHeight;
                        const maxSize = 300;
                        
                        if (width > height) {
                            if (width > maxSize) {
                                height = (height * maxSize) / width;
                                width = maxSize;
                            }
                        } else {
                            if (height > maxSize) {
                                width = (width * maxSize) / height;
                                height = maxSize;
                            }
                        }
                        
                        canvas.width = width;
                        canvas.height = height;
                        
                        // 绘制视频帧
                        ctx.drawImage(video, 0, 0, width, height);
                        
                        // 转换为base64
                        const thumbnailData = canvas.toDataURL('image/jpeg', 0.85);
                        // 提取base64数据部分
                        const base64Data = thumbnailData.split(',')[1];
                        
                        handleSuccess(base64Data);
                    } catch (error) {
                        handleError(error);
                    }
                };
                
                video.onerror = function() {
                    handleError(new Error('视频加载失败'));
                };
                
                video.src = URL.createObjectURL(file);
            });
        }

        // 生成缩略图（根据文件类型）
        async function generateThumbnail(file) {
            const fileType = file.type || '';
            const isImage = fileType.startsWith('image/');
            const isVideo = fileType.startsWith('video/');
            
            if (isImage) {
                try {
                    return await generateImageThumbnail(file);
                } catch (error) {
                    console.error('生成图片缩略图失败:', error);
                    return null;
                }
            } else if (isVideo) {
                try {
                    return await generateVideoThumbnail(file);
                } catch (error) {
                    console.error('生成视频缩略图失败:', error);
                    return null;
                }
            }
            
            return null;
        }

        // 上传单个文件
        async function uploadFile(item, author, level, remark, categoryIds, tagIds, generateThumbnail) {
            if (item.exists || item.status === 'success') {
                return;
            }
            
            item.status = 'uploading';
            renderFileList();
            
            try {
                const file = item.file;
                
                // 检查文件大小
                if (file.size === 0) {
                    throw new Error('文件大小为0，跳过上传');
                }
                
                // 判断文件是否需要生成缩略图
                const fileType = file.type || '';
                const isImage = fileType.startsWith('image/');
                const isVideo = fileType.startsWith('video/');
                const shouldGenerateThumb = generateThumbnail && (isImage || isVideo);
                
                // 在前端生成缩略图
                let thumbnailBase64 = null;
                if (shouldGenerateThumb) {
                    try {
                        console.log(`[前端] 开始为文件 ${file.name} 生成缩略图...`);
                        console.log(`[前端] 文件类型: ${file.type}, 大小: ${file.size} 字节`);
                        thumbnailBase64 = await generateThumbnail(file);
                        if (thumbnailBase64) {
                            console.log(`[前端] 缩略图生成成功，base64长度: ${thumbnailBase64.length} 字符`);
                        } else {
                            console.warn(`[前端] 缩略图生成失败，返回null`);
                        }
                    } catch (error) {
                        console.error(`[前端] 生成缩略图异常:`, error);
                        thumbnailBase64 = null; // 确保为null
                    }
                } else {
                    console.log(`[前端] 未选择生成缩略图，跳过`);
                }
                
                const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
                const chunks = [];
                
                // 上传所有分片
                for (let i = 0; i < totalChunks; i++) {
                    const start = i * CHUNK_SIZE;
                    const end = Math.min(start + CHUNK_SIZE, file.size);
                    const chunk = file.slice(start, end);
                    const chunkUuid = generateUUID();
                    
                    const formData = new FormData();
                    formData.append('chunk', chunk);
                    formData.append('chunk_index', i);
                    formData.append('total_chunks', totalChunks);
                    formData.append('file_md5', item.md5);
                    formData.append('file_name', file.name);
                    formData.append('chunk_uuid', chunkUuid);
                    
                    let retryCount = 0;
                    const maxRetries = 3;
                    let success = false;
                    
                    while (retryCount < maxRetries && !success) {
                        try {
                            const response = await fetch('/fs/api/upload/chunk/', {
                                method: 'POST',
                                body: formData
                            });
                            
                            const result = await response.json();
                            if (result.success) {
                                chunks.push({
                                    chunk_index: i,
                                    chunk_uuid: chunkUuid
                                });
                                success = true;
                            } else {
                                throw new Error(result.message);
                            }
                        } catch (error) {
                            retryCount++;
                            if (retryCount >= maxRetries) {
                                throw new Error(`分片 ${i + 1}/${totalChunks} 上传失败: ${error.message}`);
                            }
                            // 等待后重试
                            await new Promise(resolve => setTimeout(resolve, 1000 * retryCount));
                        }
                    }
                    
                    item.progress = Math.round(((i + 1) / totalChunks) * 90); // 90%用于上传分片
                    renderFileList();
                }
                
                // 合并分片（包含缩略图数据）
                const mergeData = {
                    file_md5: item.md5,
                    file_name: file.name,
                    file_size: file.size,
                    chunks: chunks,
                    album: item.album || '',
                    subject: item.subject || '',
                    author: author,
                    level: level,
                    category_ids: categoryIds,
                    tag_ids: tagIds,
                    remark: remark,
                    generate_thumbnail: shouldGenerateThumb,
                    thumbnail_base64: thumbnailBase64  // 前端生成的缩略图base64数据
                };
                
                // 调试日志
                console.log('合并分片请求数据:', {
                    file_name: file.name,
                    generate_thumbnail: shouldGenerateThumb,
                    has_thumbnail: !!thumbnailBase64,
                    thumbnail_length: thumbnailBase64 ? thumbnailBase64.length : 0,
                    chunks_count: chunks.length
                });
                
                const mergeResponse = await fetch('/fs/api/upload/merge/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(mergeData)
                });
                
                const mergeResult = await mergeResponse.json();
                if (mergeResult.success) {
                    item.status = 'success';
                    item.progress = 100;
                } else {
                    throw new Error(mergeResult.message);
                }
                
            } catch (error) {
                item.status = 'error';
                console.error('上传失败:', item.file.name, error);
                showToast(`文件 ${item.file.name} 上传失败: ${error.message}`, 'error');
            }
            
            renderFileList();
            updateStats();
        }

        // 生成UUID
        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }

        // 格式化文件大小
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        // 显示提示
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideIn 0.3s reverse';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // HTML转义
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 加载SparkMD5库用于计算MD5
        if (typeof SparkMD5 === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/spark-md5@3.0.2/spark-md5.min.js';
            script.onload = function() {
                console.log('SparkMD5库加载成功');
            };
            script.onerror = function() {
                console.warn('SparkMD5库加载失败，将使用降级方案');
            };
            document.head.appendChild(script);
        }