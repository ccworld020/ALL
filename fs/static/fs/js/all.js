let currentPage = 1;
        let currentHlsInstance = null; // 保存当前HLS实例
        let pageSize = 20;
        let totalPages = 1;
        let currentView = 'list';
        let categories = [];
        let tags = [];
        let searchTimeout = null;
        let pendingHLSFileId = null; // 待转换HLS的文件ID

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            loadCategoriesAndTags();
            loadFiles();
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
            } catch (error) {
                console.error('加载分类/标签失败:', error);
            }
        }

        // 切换视图
        function switchView(view) {
            currentView = view;
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            const listView = document.getElementById('listView');
            const cardView = document.getElementById('cardView');

            if (view === 'list') {
                listView.classList.add('active');
                cardView.classList.remove('active');
            } else {
                listView.classList.remove('active');
                cardView.classList.add('active');
            }
            
            // 重新渲染当前视图
            if (window.fileList) {
                renderFiles();
            }
        }

        // 防抖搜索
        function debounceSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentPage = 1;
                loadFiles();
            }, 500);
        }

        // 加载文件列表
        async function loadFiles() {
            try {
                const search = document.getElementById('searchInput').value;
                const type = document.getElementById('typeFilter').value;
                const level = document.getElementById('levelFilter').value;
                const author = document.getElementById('authorFilter').value;
                const album = document.getElementById('albumFilter').value;

                const status = document.getElementById('statusFilter').value;
                
                const params = new URLSearchParams({
                    page: currentPage,
                    page_size: pageSize,
                });
                
                // 只有当不是"全部"时才添加status参数
                if (status && status !== 'all') {
                    params.append('status', status);
                }
                if (search) params.append('search', search);
                if (type) params.append('type', type);
                if (level) params.append('level', level);
                if (author) params.append('author', author);
                if (album) params.append('album', album);

                const response = await fetch(`/fs/api/files/?${params}`);
                const result = await response.json();

                if (result.success) {
                    window.fileList = result.data.files;
                    totalPages = result.data.total_pages;
                    renderFiles();
                    renderPagination();
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('加载文件失败:', error);
                showToast('加载文件失败', 'error');
            }
        }

        // 渲染文件列表
        function renderFiles() {
            if (!window.fileList) return;

            const listView = document.getElementById('listView');
            const cardView = document.getElementById('cardView');

            if (currentView === 'list') {
                renderListView(listView);
            } else {
                renderCardView(cardView);
            }
        }

        // 渲染列表视图
        function renderListView(container) {
            if (window.fileList.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <p>暂无文件</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = window.fileList.map(file => {
                const badgeClass = getBadgeClass(file.type);
                const badgeText = getBadgeText(file.type);
                const thumbUrl = getThumbUrl(file);
                const isDeleted = file.status === 'deleted';
                const deletedClass = isDeleted ? 'deleted' : '';

                return `
                    <div class="list-item ${deletedClass}">
                        <img src="${thumbUrl}" alt="${escapeHtml(file.name)}" class="list-item-thumb" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'80\' height=\'80\'%3E%3Crect fill=\'%23f0f0f0\' width=\'80\' height=\'80\'/%3E%3Ctext x=\'50%25\' y=\'50%25\' text-anchor=\'middle\' dy=\'.3em\' fill=\'%23999\' font-size=\'12\'%3E${escapeHtml(file.type.toUpperCase())}%3C/text%3E%3C/svg%3E'">
                        <div class="list-item-content">
                            <div class="list-item-header">
                                <span class="item-name">${escapeHtml(file.name)}${isDeleted ? ' <span style="color: #999; font-size: 12px;">(已删除)</span>' : ''}</span>
                                <span class="item-badge ${badgeClass}">${badgeText}</span>
                                ${isVideoFile(file) && hasHLS(file) ? `<span class="hls-indicator" onclick="event.stopPropagation(); showHLSInfo(${file.id})" title="已存在HLS文件">📺</span>` : ''}
                            </div>
                            <div class="item-meta">
                                <span>📏 ${formatFileSize(file.size)}</span>
                                ${file.md5 ? `<span title="${escapeHtml(file.md5)}">🔑 ${escapeHtml(file.md5.substring(0, 8))}...</span>` : ''}
                                ${file.author ? `<span>👤 ${escapeHtml(file.author)}</span>` : ''}
                                ${file.album ? `<span>📁 ${escapeHtml(file.album)}</span>` : ''}
                                ${file.subject ? `<span>📂 ${escapeHtml(file.subject)}</span>` : ''}
                                <span>📅 ${file.created_time}</span>
                                ${isDeleted && file.delete_time ? `<span style="color: #999;">🗑️ ${file.delete_time}</span>` : ''}
                            </div>
                        </div>
                        <div class="item-actions">
                            <button class="btn btn-view" onclick="viewFile(${file.id})" ${isDeleted ? 'disabled' : ''}>查看</button>
                            <button class="btn btn-edit" onclick="editFile(${file.id})" ${isDeleted ? 'disabled' : ''}>编辑</button>
                            ${needsThumbnail(file) ? `<button class="btn btn-thumb" onclick="event.stopPropagation(); generateThumbnail(${file.id})" title="生成缩略图" ${isDeleted ? 'disabled' : ''}>🖼️</button>` : ''}
                            ${isVideoFile(file) && !hasHLS(file) ? `<button class="btn btn-hls" onclick="event.stopPropagation(); convertToHLS(${file.id})" title="转换为HLS" ${isDeleted ? 'disabled' : ''}>🎬</button>` : ''}
                            ${!isDeleted ? `<button class="btn btn-delete" onclick="event.stopPropagation(); deleteFile(${file.id})" title="删除文件">🗑️</button>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        }

        // 渲染卡片视图
        function renderCardView(container) {
            if (window.fileList.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <p>暂无文件</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = window.fileList.map(file => {
                const badgeClass = getBadgeClass(file.type);
                const badgeText = getBadgeText(file.type);
                const thumbUrl = getThumbUrl(file);
                const isDeleted = file.status === 'deleted';
                const deletedClass = isDeleted ? 'deleted' : '';

                return `
                    <div class="card-item ${deletedClass}" ${isDeleted ? '' : `onclick="viewFile(${file.id})"`}>
                        <img src="${thumbUrl}" alt="${escapeHtml(file.name)}" class="card-thumb" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'300\' height=\'200\'%3E%3Crect fill=\'%23f0f0f0\' width=\'300\' height=\'200\'/%3E%3Ctext x=\'50%25\' y=\'50%25\' text-anchor=\'middle\' dy=\'.3em\' fill=\'%23999\' font-size=\'16\'%3E${escapeHtml(file.type.toUpperCase())}%3C/text%3E%3C/svg%3E'">
                        <div class="card-content">
                            <div class="card-name">
                                ${escapeHtml(file.name)}${isDeleted ? ' <span style="color: #999; font-size: 12px;">(已删除)</span>' : ''}
                                ${isVideoFile(file) && hasHLS(file) ? `<span class="hls-indicator" onclick="event.stopPropagation(); showHLSInfo(${file.id})" title="已存在HLS文件">📺</span>` : ''}
                            </div>
                            <div class="card-meta">
                                <div>📏 ${formatFileSize(file.size)}</div>
                                ${file.md5 ? `<div title="${escapeHtml(file.md5)}">🔑 MD5: ${escapeHtml(file.md5.substring(0, 12))}...</div>` : ''}
                                ${file.author ? `<div>👤 ${escapeHtml(file.author)}</div>` : ''}
                                <div>📅 ${file.created_time}</div>
                                ${isDeleted && file.delete_time ? `<div style="color: #999;">🗑️ ${file.delete_time}</div>` : ''}
                            </div>
                            <div class="card-actions">
                                <button class="btn btn-view" onclick="event.stopPropagation(); viewFile(${file.id})" ${isDeleted ? 'disabled' : ''}>查看</button>
                                <button class="btn btn-edit" onclick="event.stopPropagation(); editFile(${file.id})" ${isDeleted ? 'disabled' : ''}>编辑</button>
                                ${needsThumbnail(file) ? `<button class="btn btn-thumb" onclick="event.stopPropagation(); generateThumbnail(${file.id})" title="生成缩略图" ${isDeleted ? 'disabled' : ''}>🖼️</button>` : ''}
                                ${isVideoFile(file) && !hasHLS(file) ? `<button class="btn btn-hls" onclick="event.stopPropagation(); convertToHLS(${file.id})" title="转换为HLS" ${isDeleted ? 'disabled' : ''}>🎬</button>` : ''}
                                ${!isDeleted ? `<button class="btn btn-delete" onclick="event.stopPropagation(); deleteFile(${file.id})" title="删除文件">🗑️</button>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // 获取缩略图URL
        function getThumbUrl(file) {
            if (file.thumbnail_addr) {
                // 使用缩略图API（自动解密）
                return `/fs/api/files/thumbnail/?id=${file.id}`;
            }
            // 如果是图片，直接使用文件内容URL
            if (file.mime && file.mime.startsWith('image/')) {
                return `/fs/api/files/content/?id=${file.id}`;
            }
            return '';
        }

        // 检查是否需要显示生成缩略图按钮
        function needsThumbnail(file) {
            const isImage = file.mime && file.mime.startsWith('image/');
            const isVideo = file.mime && file.mime.startsWith('video/');
            return (isImage || isVideo) && !file.thumbnail_addr;
        }

        // 检查是否是视频文件
        function isVideoFile(file) {
            return file.mime && file.mime.startsWith('video/');
        }

        // 检查是否有HLS文件
        function hasHLS(file) {
            return file.hls_addr && file.hls_addr.trim() !== '';
        }

        // 文件类型分类
        const fileTypeCategories = {
            image: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff', 'tif'],
            video: ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', '3gp', 'rmvb', 'rm'],
            audio: ['mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a'],
            document: ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'odt', 'ods', 'odp'],
            archive: ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso', 'dmg'],
            code: ['js', 'html', 'css', 'py', 'java', 'cpp', 'c', 'php', 'rb', 'go', 'rs', 'ts', 'jsx', 'tsx', 'json', 'xml', 'yaml', 'yml'],
            other: [] // 其他所有类型
        };

        // 判断文件类型类别
        function getFileTypeCategory(type) {
            const typeLower = type.toLowerCase();
            for (const [category, types] of Object.entries(fileTypeCategories)) {
                if (types.includes(typeLower)) {
                    return category;
                }
            }
            return 'other';
        }

        // 获取徽章类
        function getBadgeClass(type) {
            const category = getFileTypeCategory(type);
            if (category === 'image') {
                return 'badge-image';
            } else if (category === 'video') {
                return 'badge-video';
            }
            return 'badge-other';
        }

        // 获取徽章文本
        function getBadgeText(type) {
            const category = getFileTypeCategory(type);
            const typeMap = {
                'image': '图片',
                'video': '视频',
                'audio': '音频',
                'document': '文档',
                'archive': '压缩',
                'code': '代码',
                'other': '其他'
            };
            return typeMap[category] || '其他';
        }

        // 查看文件
        function viewFile(fileId) {
            const file = window.fileList.find(f => f.id === fileId);
            if (!file) return;

            // 已删除的文件不允许查看
            if (file.status === 'deleted') {
                showToast('已删除的文件无法查看', 'error');
                return;
            }

            const viewerModal = document.getElementById('viewerModal');
            const viewerContent = document.getElementById('viewerContent');
            const fileUrl = `/fs/api/files/content/?id=${fileId}`;

            if (file.mime && file.mime.startsWith('image/')) {
                viewerContent.innerHTML = `<img src="${fileUrl}" alt="${escapeHtml(file.name)}">`;
            } else if (file.mime && file.mime.startsWith('video/')) {
                // 如果有HLS文件，优先使用HLS播放
                if (hasHLS(file)) {
                    // HLS文件通过API访问（自动解密）
                    const hlsUrl = `/fs/api/files/hls-content/?id=${fileId}&type=m3u8`;
                    
                    viewerContent.innerHTML = `
                        <div style="position: relative; display: inline-block;">
                            <video id="videoPlayer" controls autoplay style="max-width: 100%; max-height: 90vh; display: block;">
                                您的浏览器不支持视频播放
                            </video>
                            <div class="video-controls">
                                <button id="playHLS" class="btn btn-submit" onclick="switchVideoSource('hls', '${hlsUrl}', 'application/x-mpegURL')">播放HLS（推荐）</button>
                                <button id="playOriginal" class="btn btn-submit" onclick="switchVideoSource('original', '${fileUrl}', '${file.mime}')">播放原文件</button>
                            </div>
                        </div>
                    `;
                    // 默认使用HLS播放
                    setTimeout(() => {
                        switchVideoSource('hls', hlsUrl, 'application/x-mpegURL');
                    }, 100);
                } else {
                    viewerContent.innerHTML = `
                        <video controls autoplay style="max-width: 100%; max-height: 90vh;">
                            <source src="${fileUrl}" type="${file.mime}">
                            您的浏览器不支持视频播放
                        </video>
                    `;
                }
            } else {
                window.open(fileUrl, '_blank');
                return;
            }

            viewerModal.classList.add('active');
        }

        // 关闭查看器
        function closeViewer() {
            // 清理HLS实例
            if (currentHlsInstance) {
                currentHlsInstance.destroy();
                currentHlsInstance = null;
            }
            
            const videoPlayer = document.getElementById('videoPlayer');
            if (videoPlayer) {
                videoPlayer.pause();
                videoPlayer.src = '';
            }
            
            document.getElementById('viewerModal').classList.remove('active');
            document.getElementById('viewerContent').innerHTML = '';
        }

        // 切换视频源（原文件或HLS）
        function switchVideoSource(type, url, mimeType) {
            const videoPlayer = document.getElementById('videoPlayer');
            if (!videoPlayer) return;

            const currentTime = videoPlayer.currentTime;
            const wasPlaying = !videoPlayer.paused;

            // 清理之前的HLS实例
            if (currentHlsInstance) {
                currentHlsInstance.destroy();
                currentHlsInstance = null;
            }

            if (type === 'hls') {
                // 使用HLS播放
                if (Hls.isSupported()) {
                    // 使用 hls.js 播放
                    const hls = new Hls({
                        enableWorker: true,
                        lowLatencyMode: false,
                        xhrSetup: function(xhr, url) {
                            // 确保CORS设置
                            xhr.withCredentials = false;
                        }
                    });
                    hls.loadSource(url);
                    hls.attachMedia(videoPlayer);
                    
                    hls.on(Hls.Events.MANIFEST_PARSED, function() {
                        console.log('HLS manifest parsed, ready to play');
                        if (wasPlaying) {
                            videoPlayer.currentTime = currentTime;
                            videoPlayer.play().catch(e => console.log('播放失败:', e));
                        }
                    });

                    hls.on(Hls.Events.ERROR, function(event, data) {
                        console.error('HLS error:', data);
                        if (data.fatal) {
                            switch (data.type) {
                                case Hls.ErrorTypes.NETWORK_ERROR:
                                    console.log('Fatal network error, trying to recover...');
                                    hls.startLoad();
                                    break;
                                case Hls.ErrorTypes.MEDIA_ERROR:
                                    console.log('Fatal media error, trying to recover...');
                                    hls.recoverMediaError();
                                    break;
                                default:
                                    console.log('Fatal error, destroying HLS instance...');
                                    hls.destroy();
                                    alert('HLS视频加载失败，请检查视频地址是否正确');
                                    break;
                            }
                        }
                    });
                    
                    currentHlsInstance = hls;
                } else if (videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {
                    // 原生支持 HLS (Safari)
                    videoPlayer.src = url;
                    videoPlayer.load();
                    if (wasPlaying) {
                        videoPlayer.currentTime = currentTime;
                        videoPlayer.play().catch(e => console.log('播放失败:', e));
                    }
                } else {
                    alert('您的浏览器不支持 HLS 视频播放');
                    return;
                }
            } else {
                // 播放原文件
                videoPlayer.src = url;
                videoPlayer.load();
                if (wasPlaying) {
                    videoPlayer.currentTime = currentTime;
                    videoPlayer.play().catch(e => console.log('播放失败:', e));
                }
            }

            // 更新按钮状态
            const playOriginal = document.getElementById('playOriginal');
            const playHLS = document.getElementById('playHLS');
            if (playOriginal && playHLS) {
                if (type === 'original') {
                    playOriginal.style.background = 'rgba(255, 255, 255, 0.3)';
                    playOriginal.style.borderColor = 'rgba(255, 255, 255, 0.6)';
                    playHLS.style.background = 'rgba(255, 255, 255, 0.15)';
                    playHLS.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                } else {
                    playHLS.style.background = 'rgba(255, 255, 255, 0.3)';
                    playHLS.style.borderColor = 'rgba(255, 255, 255, 0.6)';
                    playOriginal.style.background = 'rgba(255, 255, 255, 0.15)';
                    playOriginal.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                }
            }
        }

        // 转换为HLS（显示确认弹窗）
        function convertToHLS(fileId) {
            const file = window.fileList.find(f => f.id === fileId);
            if (!file) return;

            pendingHLSFileId = fileId;
            document.getElementById('hlsFileName').textContent = file.name;
            document.getElementById('hlsConfirmModal').classList.add('active');
        }

        // 关闭转换为HLS弹窗
        function closeHLSModal() {
            document.getElementById('hlsConfirmModal').classList.remove('active');
            pendingHLSFileId = null;
        }

        // 确认转换为HLS
        async function confirmConvertHLS() {
            if (!pendingHLSFileId) return;

            const fileId = pendingHLSFileId;
            closeHLSModal();

            try {
                showToast('正在转换为HLS格式，请稍候...', 'info');
                
                const response = await fetch('/fs/api/files/convert-hls/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: fileId})
                });

                const result = await response.json();
                if (result.success) {
                    showToast('HLS转换成功', 'success');
                    // 更新文件信息
                    const file = window.fileList.find(f => f.id === fileId);
                    if (file) {
                        file.hls_addr = result.data.hls_addr;
                        // 重新渲染
                        renderFiles();
                    }
                } else {
                    showToast(result.message || 'HLS转换失败', 'error');
                }
            } catch (error) {
                showToast('HLS转换失败: ' + error.message, 'error');
            }
        }

        // 显示HLS信息
        function showHLSInfo(fileId) {
            const file = window.fileList.find(f => f.id === fileId);
            if (!file || !hasHLS(file)) return;

            showToast(`该文件已存在HLS文件：${file.hls_addr}`, 'info');
        }

        // 编辑文件
        async function editFile(fileId) {
            const file = window.fileList.find(f => f.id === fileId);
            if (!file) return;

            // 已删除的文件不允许编辑
            if (file.status === 'deleted') {
                showToast('已删除的文件无法编辑', 'error');
                return;
            }

            document.getElementById('editFileId').value = file.id;
            document.getElementById('editName').value = file.name;
            document.getElementById('editAuthor').value = file.author || '';
            document.getElementById('editLevel').value = file.level;
            document.getElementById('editAlbum').value = file.album || '';
            document.getElementById('editSubject').value = file.subject || '';
            document.getElementById('editRemark').value = file.remark || '';

            // 渲染分类和标签选择器
            renderEditSelectors(file.categories || [], file.tags || []);

            document.getElementById('editModal').classList.add('active');
        }

        // 渲染编辑选择器
        function renderEditSelectors(selectedCategories, selectedTags) {
            const catSelector = document.getElementById('editCategorySelector');
            const tagSelector = document.getElementById('editTagSelector');
            
            const selectedCatIds = selectedCategories.map(c => c.id);
            const selectedTagIds = selectedTags.map(t => t.id);
            
            catSelector.innerHTML = categories.map(cat => `
                <div class="selector-item">
                    <input type="checkbox" id="edit_cat_${cat.id}" value="${cat.id}" ${selectedCatIds.includes(cat.id) ? 'checked' : ''}>
                    <label for="edit_cat_${cat.id}">${escapeHtml(cat.name)}</label>
                </div>
            `).join('');
            
            tagSelector.innerHTML = tags.map(tag => `
                <div class="selector-item">
                    <input type="checkbox" id="edit_tag_${tag.id}" value="${tag.id}" ${selectedTagIds.includes(tag.id) ? 'checked' : ''}>
                    <label for="edit_tag_${tag.id}">${escapeHtml(tag.name)}</label>
                </div>
            `).join('');
        }

        // 关闭编辑模态框
        function closeEditModal() {
            document.getElementById('editModal').classList.remove('active');
        }

        // 保存文件信息
        async function saveFileInfo(event) {
            event.preventDefault();

            const fileId = document.getElementById('editFileId').value;
            const name = document.getElementById('editName').value;
            const author = document.getElementById('editAuthor').value;
            const level = document.getElementById('editLevel').value;
            const album = document.getElementById('editAlbum').value;
            const subject = document.getElementById('editSubject').value;
            const remark = document.getElementById('editRemark').value;
            const categoryIds = Array.from(document.querySelectorAll('#editCategorySelector input:checked')).map(cb => parseInt(cb.value));
            const tagIds = Array.from(document.querySelectorAll('#editTagSelector input:checked')).map(cb => parseInt(cb.value));

            try {
                const response = await fetch('/fs/api/files/update/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        id: parseInt(fileId),
                        name: name,
                        author: author,
                        level: level,
                        album: album,
                        subject: subject,
                        remark: remark,
                        category_ids: categoryIds,
                        tag_ids: tagIds
                    })
                });

                const result = await response.json();
                if (result.success) {
                    showToast('更新成功', 'success');
                    closeEditModal();
                    await loadFiles();
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                showToast('更新失败: ' + error.message, 'error');
            }
        }

        // 渲染分页
        function renderPagination() {
            const pagination = document.getElementById('pagination');
            if (totalPages <= 1) {
                pagination.innerHTML = '';
                return;
            }

            let html = '';
            
            // 上一页
            html += `<button class="page-btn" onclick="goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>上一页</button>`;
            
            // 页码
            const startPage = Math.max(1, currentPage - 2);
            const endPage = Math.min(totalPages, currentPage + 2);
            
            if (startPage > 1) {
                html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
                if (startPage > 2) {
                    html += `<span>...</span>`;
                }
            }
            
            for (let i = startPage; i <= endPage; i++) {
                html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
            }
            
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) {
                    html += `<span>...</span>`;
                }
                html += `<button class="page-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
            }
            
            // 下一页
            html += `<button class="page-btn" onclick="goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>下一页</button>`;
            
            pagination.innerHTML = html;
        }

        // 跳转页面
        function goToPage(page) {
            if (page < 1 || page > totalPages) return;
            currentPage = page;
            loadFiles();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        // 格式化文件大小
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        let pendingThumbnailFileId = null;

        // 生成缩略图（显示确认弹窗）
        function generateThumbnail(fileId) {
            const file = window.fileList.find(f => f.id === fileId);
            if (!file) return;

            pendingThumbnailFileId = fileId;
            document.getElementById('thumbnailFileName').textContent = file.name;
            document.getElementById('thumbnailConfirmModal').classList.add('active');
        }

        // 关闭生成缩略图弹窗
        function closeThumbnailModal() {
            document.getElementById('thumbnailConfirmModal').classList.remove('active');
            pendingThumbnailFileId = null;
        }

        // 确认生成缩略图
        async function confirmGenerateThumbnail() {
            if (!pendingThumbnailFileId) return;

            const fileId = pendingThumbnailFileId;
            closeThumbnailModal();

            try {
                showToast('正在生成缩略图，请稍候...', 'info');
                
                const response = await fetch('/fs/api/files/generate-thumbnail/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: fileId})
                });

                const result = await response.json();
                if (result.success) {
                    showToast('缩略图生成成功', 'success');
                    // 更新文件信息
                    const file = window.fileList.find(f => f.id === fileId);
                    if (file) {
                        file.thumbnail_addr = result.data.thumbnail_addr;
                        // 重新渲染
                        renderFiles();
                    }
                } else {
                    // 显示详细的错误信息
                    let errorMsg = result.message || '生成缩略图失败';
                    if (result.traceback) {
                        console.error('缩略图生成错误详情:', result.traceback);
                        errorMsg += '（详细信息请查看控制台）';
                    }
                    showToast(errorMsg, 'error');
                    console.error('生成缩略图失败:', result);
                }
            } catch (error) {
                const errorMsg = '生成缩略图失败: ' + error.message;
                showToast(errorMsg, 'error');
                console.error('生成缩略图异常:', error);
            }
        }

        // 删除文件
        async function deleteFile(fileId) {
            const file = window.fileList.find(f => f.id === fileId);
            if (!file) return;

            if (!confirm(`确定要删除文件 "${file.name}" 吗？\n\n删除后将：\n- 删除所有文件数据块（分片）\n- 保留缩略图\n- 文件状态将标记为已删除`)) {
                return;
            }

            try {
                const response = await fetch('/fs/api/files/delete/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: fileId})
                });

                const result = await response.json();
                if (result.success) {
                    showToast(result.message || '文件删除成功', 'success');
                    // 从列表中移除
                    window.fileList = window.fileList.filter(f => f.id !== fileId);
                    renderFiles();
                    updateStats();
                } else {
                    showToast(result.message || '删除失败', 'error');
                }
            } catch (error) {
                showToast('删除失败: ' + error.message, 'error');
            }
        }

        // 更新统计（如果需要）
        function updateStats() {
            // 如果页面有统计元素，可以在这里更新
            const totalFilesEl = document.getElementById('totalFiles');
            if (totalFilesEl && window.fileList) {
                totalFilesEl.textContent = window.fileList.length;
            }
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

        // 点击模态框外部关闭
        document.getElementById('editModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeEditModal();
            }
        });

        document.getElementById('viewerModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeViewer();
            }
        });

        document.getElementById('thumbnailConfirmModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeThumbnailModal();
            }
        });

        document.getElementById('hlsConfirmModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeHLSModal();
            }
        });