let currentTab = 'category';
        let currentView = 'list';
        let allCategories = [];
        let allTags = [];
        let editingItem = null;

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            loadData();
        });

        // 切换标签页
        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('categoryView').style.display = tab === 'category' ? 'block' : 'none';
            document.getElementById('tagView').style.display = tab === 'tag' ? 'block' : 'none';
            
            filterItems();
        }

        // 切换视图
        function switchView(view) {
            currentView = view;
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            const tabContent = currentTab === 'category' ? 'category' : 'tag';
            const listView = document.getElementById(tabContent + 'List');
            const cardView = document.getElementById(tabContent + 'Cards');

            // 先移除所有视图的active类，确保只显示一个视图
            document.querySelectorAll('.list-view, .card-view').forEach(view => view.classList.remove('active'));

            if (view === 'list') {
                listView.classList.add('active');
            } else {
                cardView.classList.add('active');
            }
            
            renderItems();
        }

        // 加载数据
        async function loadData() {
            try {
                const [catRes, tagRes] = await Promise.all([
                    fetch('/fs/api/ct/?flag=C'),
                    fetch('/fs/api/ct/?flag=T')
                ]);
                
                const catData = await catRes.json();
                const tagData = await tagRes.json();
                
                allCategories = catData.data || [];
                allTags = tagData.data || [];
                
                // 确保数据正确加载（包括子分类）
                console.log('加载的分类数据:', allCategories);
                console.log('加载的标签数据:', allTags);
                console.log('分类总数:', allCategories.length, '其中子分类:', allCategories.filter(c => c.parent_id).length);
                console.log('标签总数:', allTags.length, '其中子标签:', allTags.filter(t => t.parent_id).length);
                
                renderItems();
                updateParentSelect();
            } catch (error) {
                showToast('加载数据失败: ' + error.message, 'error');
            }
        }

        // 构建树形结构
        function buildTree(items) {
            const itemMap = new Map();
            const rootItems = [];
            
            // 创建所有项目的映射
            items.forEach(item => {
                itemMap.set(item.id, { ...item, children: [] });
            });
            
            // 构建树形结构
            items.forEach(item => {
                const node = itemMap.get(item.id);
                if (item.parent_id && itemMap.has(item.parent_id)) {
                    // 有父级，添加到父级的children中
                    itemMap.get(item.parent_id).children.push(node);
                } else {
                    // 顶级项目
                    rootItems.push(node);
                }
            });
            
            // 对每个节点的children进行排序
            function sortTree(nodes) {
                nodes.sort((a, b) => {
                    const sortOrderDiff = (a.sort_order || 0) - (b.sort_order || 0);
                    if (sortOrderDiff !== 0) return sortOrderDiff;
                    return a.name.localeCompare(b.name);
                });
                nodes.forEach(node => {
                    if (node.children.length > 0) {
                        sortTree(node.children);
                    }
                });
            }
            
            sortTree(rootItems);
            return rootItems;
        }

        // 渲染项目
        function renderItems() {
            const items = currentTab === 'category' ? allCategories : allTags;
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            
            // 确保所有项目都被包含，包括子分类
            let filtered = items.filter(item => {
                if (!searchTerm) return true; // 如果没有搜索词，显示所有项目
                return item.name.toLowerCase().includes(searchTerm) ||
                    (item.description && item.description.toLowerCase().includes(searchTerm));
            });

            // 如果有搜索词，需要包含父级（即使父级不匹配搜索词）
            if (searchTerm) {
                const matchedIds = new Set(filtered.map(item => item.id));
                const itemsToInclude = new Set(filtered.map(item => item.id));
                
                // 递归添加所有父级
                function addParents(itemId) {
                    const item = items.find(i => i.id === itemId);
                    if (item && item.parent_id) {
                        itemsToInclude.add(item.parent_id);
                        addParents(item.parent_id);
                    }
                }
                
                filtered.forEach(item => {
                    if (item.parent_id) {
                        addParents(item.parent_id);
                    }
                });
                
                filtered = items.filter(item => itemsToInclude.has(item.id));
            }

            // 构建树形结构
            const tree = buildTree(filtered);

            if (currentView === 'list') {
                renderListView(tree);
            } else {
                renderCardView(tree);
            }
        }

        // 渲染列表项（递归）
        function renderListItem(item, level = 0) {
            const badgeClass = item.flag === 'C' ? 'badge-category' : 'badge-tag';
            const badgeText = item.flag === 'C' ? '分类' : '标签';
            const indentClass = level > 0 ? 'hierarchy-indent' : '';
            const indentStyle = level > 0 ? `margin-left: ${level * 30}px;` : '';

            let html = `
                <div class="list-item ${indentClass}" style="${indentStyle}">
                    <div class="list-item-content">
                        <div class="list-item-header">
                            <span class="item-name">${escapeHtml(item.name)}</span>
                            <span class="item-badge ${badgeClass}">${badgeText}</span>
                        </div>
                        ${item.description ? `<div class="item-path">${escapeHtml(item.description)}</div>` : ''}
                        <div class="item-meta">
                            <span>📁 ${item.file_count || 0} 个文件</span>
                            <span>📅 ${item.created_time}</span>
                        </div>
                    </div>
                    <div class="item-actions">
                        <button class="action-btn btn-edit" onclick="editItem(${item.id})">编辑</button>
                        <button class="action-btn btn-delete" onclick="deleteItem(${item.id})">删除</button>
                    </div>
                </div>
            `;

            // 递归渲染子项
            if (item.children && item.children.length > 0) {
                html += item.children.map(child => renderListItem(child, level + 1)).join('');
            }

            return html;
        }

        // 渲染列表视图
        function renderListView(tree) {
            const container = currentTab === 'category' ? 
                document.getElementById('categoryList') : 
                document.getElementById('tagList');
            
            if (tree.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <p>暂无数据</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = tree.map(item => renderListItem(item, 0)).join('');
        }

        // 渲染卡片项（递归）
        function renderCardItem(item, level = 0) {
            const badgeClass = item.flag === 'C' ? 'badge-category' : 'badge-tag';
            const badgeText = item.flag === 'C' ? '分类' : '标签';
            const indentStyle = level > 0 ? `margin-left: ${level * 30}px; border-left: 3px solid #667eea; padding-left: 15px;` : '';

            let html = `
                <div class="card-item" onclick="editItem(${item.id})" style="${indentStyle}">
                    <div class="card-header">
                        <div class="card-name">${escapeHtml(item.name)}</div>
                        <span class="item-badge ${badgeClass}">${badgeText}</span>
                    </div>
                    ${item.description ? `<div class="card-description">${escapeHtml(item.description)}</div>` : '<div class="card-description" style="color: #ccc;">暂无描述</div>'}
                    <div class="card-footer">
                        <div class="card-meta">
                            <div>📁 ${item.file_count || 0} 个文件</div>
                            ${item.children && item.children.length > 0 ? `<div style="margin-top: 5px; color: #667eea;">📂 ${item.children.length} 个子分类</div>` : ''}
                        </div>
                        <div class="item-actions">
                            <button class="action-btn btn-edit" onclick="event.stopPropagation(); editItem(${item.id})">编辑</button>
                            <button class="action-btn btn-delete" onclick="event.stopPropagation(); deleteItem(${item.id})">删除</button>
                        </div>
                    </div>
                </div>
            `;

            // 递归渲染子项
            if (item.children && item.children.length > 0) {
                html += item.children.map(child => renderCardItem(child, level + 1)).join('');
            }

            return html;
        }

        // 渲染卡片视图
        function renderCardView(tree) {
            const container = currentTab === 'category' ? 
                document.getElementById('categoryCards') : 
                document.getElementById('tagCards');
            
            if (tree.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <p>暂无数据</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = tree.map(item => renderCardItem(item, 0)).join('');
        }

        // 获取父级名称
        function getParentName(parentId) {
            if (!parentId) return null;
            const items = currentTab === 'category' ? allCategories : allTags;
            const parent = items.find(item => item.id === parentId);
            return parent ? parent.name : null;
        }

        // 过滤项目
        function filterItems() {
            renderItems();
        }

        // 打开模态框
        function openModal(type) {
            editingItem = null;
            const flag = type === 'category' ? 'C' : 'T';
            document.getElementById('itemId').value = '';
            document.getElementById('itemFlag').value = flag;
            document.getElementById('itemName').value = '';
            document.getElementById('itemParent').value = '';
            document.getElementById('itemSortOrder').value = '0';
            document.getElementById('itemDescription').value = '';
            document.getElementById('modalTitle').textContent = flag === 'C' ? '新建分类' : '新建标签';
            document.getElementById('itemModal').classList.add('active');
            updateParentSelect();
        }

        // 编辑项目
        async function editItem(id) {
            const items = currentTab === 'category' ? allCategories : allTags;
            const item = items.find(i => i.id === id);
            
            if (!item) {
                showToast('项目不存在', 'error');
                return;
            }

            editingItem = item;
            document.getElementById('itemId').value = item.id;
            document.getElementById('itemFlag').value = item.flag;
            document.getElementById('itemName').value = item.name;
            document.getElementById('itemParent').value = item.parent_id || '';
            document.getElementById('itemSortOrder').value = item.sort_order || 0;
            document.getElementById('itemDescription').value = item.description || '';
            document.getElementById('modalTitle').textContent = item.flag === 'C' ? '编辑分类' : '编辑标签';
            document.getElementById('itemModal').classList.add('active');
            updateParentSelect(item.id);
        }

        // 更新父级选择器
        function updateParentSelect(excludeId = null) {
            const select = document.getElementById('itemParent');
            const flagValue = document.getElementById('itemFlag').value;
            const flag = flagValue || (currentTab === 'category' ? 'C' : 'T');
            const items = flag === 'C' ? allCategories : allTags;
            
            const itemIdValue = document.getElementById('itemId').value;
            const currentItemId = itemIdValue ? parseInt(itemIdValue) : null;
            
            select.innerHTML = '<option value="">无（顶级）</option>';
            
            items.forEach(item => {
                // 排除当前编辑的项目和指定的排除ID
                if (item.id !== excludeId && item.id !== currentItemId) {
                    const option = document.createElement('option');
                    option.value = item.id;
                    option.textContent = item.name;
                    if (item.parent_id) {
                        const parent = items.find(p => p.id === item.parent_id);
                        if (parent) {
                            option.textContent = `${parent.name} > ${item.name}`;
                        }
                    }
                    select.appendChild(option);
                }
            });
        }

        // 关闭模态框
        function closeModal() {
            document.getElementById('itemModal').classList.remove('active');
            editingItem = null;
        }

        // 保存项目
        async function saveItem(event) {
            event.preventDefault();
            
            const id = document.getElementById('itemId').value;
            const flag = document.getElementById('itemFlag').value;
            const name = document.getElementById('itemName').value;
            const parentId = document.getElementById('itemParent').value;
            const sortOrder = parseInt(document.getElementById('itemSortOrder').value) || 0;
            const description = document.getElementById('itemDescription').value;

            const data = {
                action: id ? 'update' : 'create',
                name: name,
                flag: flag,
                description: description,
                parent_id: parentId ? parseInt(parentId) : null,
                sort_order: sortOrder,
            };

            if (id) {
                data.id = parseInt(id);
            }

            try {
                const response = await fetch('/fs/api/ct/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                });

                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                    closeModal();
                    // 重新加载数据并渲染
                    await loadData();
                    // 确保当前视图正确显示
                    renderItems();
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                showToast('操作失败: ' + error.message, 'error');
            }
        }

        // 删除项目
        async function deleteItem(id) {
            if (!confirm('确定要删除这个项目吗？')) {
                return;
            }

            try {
                const response = await fetch('/fs/api/ct/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        action: 'delete',
                        id: id
                    })
                });

                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                    await loadData();
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                showToast('删除失败: ' + error.message, 'error');
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
        document.getElementById('itemModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });