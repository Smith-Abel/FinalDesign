/**
 * Web 管理端主控制器
 * 功能：路由切换 / 各视图渲染 / 状态筛选 Tabs / 分页 / 用户封禁 / 看板联动
 */
document.addEventListener('DOMContentLoaded', () => {
    // 未登录则跳回登录页
    if (!window.api.token) {
        window.location.href = 'index.html';
        return;
    }

    const navItems = document.querySelectorAll('.nav-item[data-view]');
    const viewContainer = document.getElementById('viewContainer');
    const pageTitle = document.getElementById('pageTitle');
    const logoutBtn = document.getElementById('logoutBtn');

    // 路由 / 视图映射表
    const views = {
        'dashboard': { title: '概览看板', render: renderDashboard },
        'users': { title: '用户管理', render: renderUsers },
        'verifies': { title: '学生审核', render: renderVerifies },
        'tasks': { title: '任务监控', render: renderTasks },
        'reports': { title: '举报工单', render: renderReports },
        'audits': { title: '操作审计', render: renderAudits }
    };

    // 各视图本地状态（保持筛选条件 / 页码 / 排序信息）
    const viewState = {
        users: { page: 1, q: '', is_active: '', ordering: '-date_joined' },
        tasks: { page: 1, q: '', searchMode: 'content', category: '', status: '', is_hidden: 'false', ordering: '-created_at' },
        verifies: { status: '', q: '', college: '' },
        reports: { status: '', q: '' },
        audits: { page: 1, q: '' }
    };

    // ── 导航事件 ──
    navItems.forEach(item => {
        item.addEventListener('click', e => {
            e.preventDefault();
            switchView(item.dataset.view);
        });
    });

    if (logoutBtn) {
        logoutBtn.addEventListener('click', e => {
            e.preventDefault();
            window.api.clearToken();
            window.location.href = 'index.html';
        });
    }

    // ── 核心视图切换 ──
    async function switchView(viewName, extraState = {}) {
        if (!views[viewName]) return;

        // 合并额外状态（例如从看板跳转时携带 status='PENDING'）
        if (viewState[viewName]) {
            Object.assign(viewState[viewName], extraState);
        }

        navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewName);
        });

        pageTitle.textContent = views[viewName].title;
        viewContainer.innerHTML = `<div class="loading-spinner"><span class="spinner-icon">⟳</span> 数据加载中...</div>`;

        try {
            await views[viewName].render(viewContainer);
        } catch (err) {
            viewContainer.innerHTML = `<div class="error-state">⚠️ 加载失败: ${err.message}</div>`;
        }
    }

    // 默认加载概览
    switchView('dashboard');

    /* ================================================================
       工具函数
    ================================================================ */

    /**
     * 生成状态筛选 Tabs HTML
     * @param {Array} tabs - [{label, value}]
     * @param {string} activeValue - 当前激活的 value
     * @param {string} viewName - 所属视图名
     */
    function buildTabs(tabs, activeValue, viewName) {
        return `
            <div class="filter-tabs" id="filterTabs-${viewName}">
                ${tabs.map(t => `
                    <button class="tab-btn ${t.value === activeValue ? 'active' : ''}"
                            data-view="${viewName}" data-status="${t.value}">
                        ${t.label}
                    </button>
                `).join('')}
            </div>
        `;
    }

    /**
     * 生成分页控件 HTML
     * @param {number} count - 总条数
     * @param {number} currentPage - 当前页
     * @param {number} pageSize - 每页条数
     * @param {string} viewName - 所属视图名
     */
    function buildPagination(count, currentPage, pageSize, viewName) {
        const totalPages = Math.ceil(count / pageSize);
        if (totalPages <= 1) return '';

        let pages = '';
        for (let i = 1; i <= totalPages; i++) {
            pages += `<button class="page-btn ${i === currentPage ? 'active' : ''}"
                              data-view="${viewName}" data-page="${i}">${i}</button>`;
        }

        return `
            <div class="pagination">
                <span class="pagination-info">共 ${count} 条 / 第 ${currentPage}/${totalPages} 页</span>
                <div class="pagination-btns">
                    <button class="page-btn" data-view="${viewName}" data-page="${Math.max(1, currentPage - 1)}">&laquo;</button>
                    ${pages}
                    <button class="page-btn" data-view="${viewName}" data-page="${Math.min(totalPages, currentPage + 1)}">&raquo;</button>
                </div>
            </div>
        `;
    }

    // 绑定 Tabs 和分页按钮事件（事件委托到 viewContainer）
    viewContainer.addEventListener('click', e => {
        const tabBtn = e.target.closest('.tab-btn');
        if (tabBtn) {
            const vName = tabBtn.dataset.view;
            const newStatus = tabBtn.dataset.status;
            viewState[vName].status = newStatus;
            switchView(vName);
            return;
        }

        const pageBtn = e.target.closest('.page-btn');
        if (pageBtn) {
            const vName = pageBtn.dataset.view;
            const newPage = parseInt(pageBtn.dataset.page, 10);
            if (viewState[vName]) viewState[vName].page = newPage;
            switchView(vName);
        }
    });


    /* ================================================================
       1. Dashboard 概览看板
    ================================================================ */
    async function renderDashboard(container) {
        const stats = await window.api.getStats();

        // 每张统计卡片点击可联动至对应模块
        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card stat-link" data-goto="users" title="点击查看全部用户">
                    <div class="stat-icon" style="background: rgba(64,158,255,0.1); color: #409eff;">👥</div>
                    <div class="stat-info">
                        <h3>总用户数</h3>
                        <div class="stat-value">${stats.users.total} <span class="stat-sub">+${stats.users.new_today} 今日新增</span></div>
                    </div>
                    <span class="stat-arrow">›</span>
                </div>
                <div class="stat-card stat-link" data-goto="tasks" title="点击查看任务大厅">
                    <div class="stat-icon" style="background: rgba(103,194,58,0.1); color: #67c23a;">📋</div>
                    <div class="stat-info">
                        <h3>总任务数</h3>
                        <div class="stat-value">${stats.tasks.total}</div>
                    </div>
                    <span class="stat-arrow">›</span>
                </div>
                <div class="stat-card stat-link ${stats.todos.pending_verifies > 0 ? 'stat-alert' : ''}"
                     data-goto="verifies" data-status="PENDING" title="点击查看待审核列表">
                    <div class="stat-icon" style="background: rgba(230,162,60,0.1); color: #e6a23c;">🎓</div>
                    <div class="stat-info">
                        <h3>待审核学生认证</h3>
                        <div class="stat-value">${stats.todos.pending_verifies}</div>
                    </div>
                    <span class="stat-arrow">›</span>
                </div>
                <div class="stat-card stat-link ${stats.todos.pending_reports > 0 ? 'stat-alert' : ''}"
                     data-goto="reports" data-status="PENDING" title="点击查看待处理举报">
                    <div class="stat-icon" style="background: rgba(245,108,108,0.1); color: #f56c6c;">🚩</div>
                    <div class="stat-info">
                        <h3>待处理举报工单</h3>
                        <div class="stat-value">${stats.todos.pending_reports}</div>
                    </div>
                    <span class="stat-arrow">›</span>
                </div>
            </div>
            
            <div class="card" style="margin-top: 24px;">
                <h3 style="margin-bottom: 16px; font-size: 15px; color: var(--text-regular);">📊 运营概要</h3>
                <div class="summary-row">
                    <span class="summary-item"><strong>${stats.tasks.in_progress}</strong> 个任务进行中</span>
                    <span class="summary-divider">·</span>
                    <span class="summary-item">累计完成 <strong>${stats.tasks.completed}</strong> 个任务</span>
                </div>
            </div>
        `;

        // 看板统计卡点击联动
        container.querySelectorAll('.stat-link').forEach(card => {
            card.addEventListener('click', () => {
                const goto = card.dataset.goto;
                const extraStatus = card.dataset.status ? { status: card.dataset.status } : {};
                switchView(goto, extraStatus);
            });
        });
    }


    /* ================================================================
       2. 用户管理
    ================================================================ */
    async function renderUsers(container) {
        const state = viewState.users;
        const data = await window.api.getUsers({
            page: state.page,
            q: state.q,
            is_active: state.is_active,
            ordering: state.ordering
        });
        const users = data.results || data; // 兼容非分页情景

        const tableRows = users.length
            ? users.map(u => `
                <tr>
                    <td>${u.id}</td>
                    <td>
                        <div class="user-cell">
                            <img src="${u.avatar || 'https://api.dicebear.com/7.x/notionists/svg?seed=' + u.username}" class="mini-avatar">
                            <div>
                                <div>${u.nickname || u.username}</div>
                                <small style="color:#999">@${u.username}</small>
                            </div>
                        </div>
                    </td>
                    <td>${u.college || '-'}</td>
                    <td><span class="status-badge ${u.is_verified ? 'success' : 'default'}">${u.is_verified ? '已认证' : '未认证'}</span></td>
                    <td>${u.credit_score}</td>
                    <td>${new Date(u.date_joined).toLocaleDateString()}</td>
                    <td>
                        <button class="btn-micro ${u.is_active ? 'danger-btn' : 'success-btn'}"
                                onclick="handleBanUser(${u.id}, ${u.is_active})">
                            ${u.is_active ? '封禁' : '解封'}
                        </button>
                    </td>
                </tr>
            `).join('')
            : '<tr><td colspan="7" class="empty-row">暂无用户记录</td></tr>';

        container.innerHTML = `
            <div class="toolbar" style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;">
                <div class="search-input-wrapper" style="flex: 1; min-width: 200px;">
                    <input type="text" id="userSearchInput" placeholder="按用户名或昵称搜索..." value="${state.q}" class="search-input" style="width: 100%;">
                    <button id="userSearchBtn" class="search-icon-btn" title="筛选检索">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </button>
                </div>
                <select id="userActiveSelect" class="search-input" style="width: auto; min-width: 140px;">
                    <option value="">所有管控状态</option>
                    <option value="true" ${state.is_active === 'true' ? 'selected' : ''}>正常</option>
                    <option value="false" ${state.is_active === 'false' ? 'selected' : ''}>已封禁</option>
                </select>
                <select id="userSortSelect" class="search-input" style="width: auto; min-width: 155px;">
                    <option value="-date_joined" ${state.ordering === '-date_joined' ? 'selected' : ''}>最新注册优先</option>
                    <option value="date_joined" ${state.ordering === 'date_joined' ? 'selected' : ''}>最早注册优先</option>
                    <option value="-credit_score" ${state.ordering === '-credit_score' ? 'selected' : ''}>积分最多优先</option>
                    <option value="credit_score" ${state.ordering === 'credit_score' ? 'selected' : ''}>积分最少优先</option>
                </select>
                <button class="btn-micro" style="padding:0 15px" onclick="window.open(window.api.getExportUsersUrl(), '_blank')">导出数据 (CSV)</button>
            </div>
            <div class="card table-card">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th><th>用户</th><th>学院</th><th>认证</th><th>积分</th><th>注册时间</th><th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
            ${data.count ? buildPagination(data.count, state.page, 20, 'users') : ''}
        `;

        // 搜索筛选事件
        const triggerSearch = () => {
            viewState.users.q = document.getElementById('userSearchInput').value.trim();
            viewState.users.is_active = document.getElementById('userActiveSelect').value;
            viewState.users.ordering = document.getElementById('userSortSelect').value;
            viewState.users.page = 1;
            switchView('users');
        };
        
        document.getElementById('userSearchBtn').addEventListener('click', triggerSearch);
        document.getElementById('userActiveSelect').addEventListener('change', triggerSearch);
        document.getElementById('userSortSelect').addEventListener('change', triggerSearch);
        document.getElementById('userSearchInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') triggerSearch();
        });
    }

    window.handleBanUser = async (id, isActive) => {
        const action = isActive ? '封禁' : '解封';
        if (!confirm(`确认要${action}该用户吗？`)) return;
        try {
            const res = await window.api.banUser(id);
            alert(res.detail);
            switchView('users');
        } catch (e) {
            alert(e.message);
        }
    };


    /* ================================================================
       3. 学生审核（含搜索过滤及 Tabs）
    ================================================================ */
    async function renderVerifies(container) {
        const state = viewState.verifies;
        const list = await window.api.getVerifies({
            status: state.status,
            q: state.q,
            college: state.college
        });

        const tabs = buildTabs([
            { label: '全部', value: '' },
            { label: '⏳ 待审核', value: 'PENDING' },
            { label: '✅ 已通过', value: 'APPROVED' },
            { label: '❌ 已驳回', value: 'REJECTED' }
        ], state.status, 'verifies');

        const statMap = { 'PENDING': '待审核', 'APPROVED': '已通过', 'REJECTED': '已驳回' };

        const renderAction = (id, status) => {
            if (status !== 'PENDING') return `<span style="color:#999">已处理</span>`;
            return `
                <button class="btn-micro success-btn" onclick="handleActionVerify(${id}, 'approve')">通过</button>
                <button class="btn-micro danger-btn" onclick="handleActionVerify(${id}, 'reject')">驳回</button>
            `;
        };

        const tableRows = list.length
            ? list.map(v => `
                <tr>
                    <td>${v.id}</td>
                    <td>
                        <div>${v.real_name}</div>
                        <small style="color:#999">昵称: ${v.user_nickname || '-'}</small>
                    </td>
                    <td>${v.user_college || '-'}</td>
                    <td>
                        <a href="${v.student_id_image}" target="_blank" class="img-preview">
                            <img src="${v.student_id_image}" width="60" alt="凭证"/>
                        </a>
                    </td>
                    <td><span class="status-badge status-${v.status.toLowerCase()}">${statMap[v.status]}</span></td>
                    <td>${new Date(v.created_at).toLocaleString()}</td>
                    <td>${v.note || '-'}</td>
                    <td>${renderAction(v.id, v.status)}</td>
                </tr>
            `).join('')
            : '<tr><td colspan="8" class="empty-row">该状态下暂无审核工单</td></tr>';

        container.innerHTML = `
            ${tabs}
            <div class="toolbar" style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;">
                <div class="search-input-wrapper" style="flex: 1; min-width: 200px;">
                    <input type="text" id="verifySearchInput" placeholder="按姓名或昵称搜索..." value="${state.q}" class="search-input" style="width: 100%;">
                    <button id="verifySearchBtn" class="search-icon-btn" title="筛选检索">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </button>
                </div>
                <input type="text" id="verifyCollegeInput" class="search-input" placeholder="输入学院名称筛选" value="${state.college}" style="width: auto; min-width: 140px;">
            </div>
            <div class="card table-card">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th><th>姓名 / 昵称</th><th>所属学院</th><th>证件照片</th><th>状态</th><th>申请时间</th><th>处理备注</th><th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
        `;
        
        // 绑定搜索事件
        const triggerSearch = () => {
            viewState.verifies.q = document.getElementById('verifySearchInput').value.trim();
            viewState.verifies.college = document.getElementById('verifyCollegeInput').value.trim();
            switchView('verifies');
        };
        
        document.getElementById('verifySearchBtn').addEventListener('click', triggerSearch);
        document.getElementById('verifySearchInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') triggerSearch();
        });
        document.getElementById('verifyCollegeInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') triggerSearch();
        });
    }

    window.handleActionVerify = async (id, action) => {
        let note = '';
        if (action === 'reject') {
            note = prompt('请输入驳回原因:');
            if (note === null) return;
        } else {
            if (!confirm('确认要通过该学生的实名认证吗？')) return;
        }
        try {
            await window.api.actionVerify(id, action, note);
            switchView('verifies');
        } catch (e) {
            alert(e.message);
        }
    };


    /* ================================================================
       4. 任务监控（分页）
    ================================================================ */
    async function renderTasks(container) {
        const state = viewState.tasks;
        const data = await window.api.getTasks({
            page: state.page,
            q: state.q,
            searchMode: state.searchMode,
            category: state.category,
            status: state.status,
            is_hidden: state.is_hidden,
            ordering: state.ordering
        });
        const tasks = data.results || data;

        // 缓存任务数据
        window._taskCache = window._taskCache || {};
        tasks.forEach(t => { window._taskCache[t.id] = t; });

        const statMap = { 'OPEN': '未接单', 'PENDING_ACCEPT': '待接受', 'IN_PROGRESS': '进行中', 'PENDING_CONFIRM': '待确认', 'COMPLETED': '已完成', 'CANCELLED': '已取消' };
        const catMap = { 'STUDY': '学业指导', 'TRADE': '物品交易', 'HELP': '生活协助' };

        const tableRows = tasks.length
            ? tasks.map(t => `
                <tr>
                    <td>${t.id}</td>
                    <td style="max-width:200px;">
                        <button class="task-title-link" onclick="showTaskDetail(${t.id})" title="${t.title}">
                            ${t.title}
                        </button>
                        <br/><small style="color:#999">${catMap[t.category] || t.category}</small>
                    </td>
                    <td>${t.reward_amount} 积分</td>
                    <td><span class="status-badge">${statMap[t.status] || t.status}</span></td>
                    <td>${t.publisher_name || (t.publisher && (t.publisher.nickname || t.publisher.username)) || '-'}</td>
                    <td>${t.worker_name || (t.worker && (t.worker.nickname || t.worker.username)) || '-'}</td>
                    <td>
                        ${t.is_hidden ?
                    `<span style="color:#F56C6C">已屏蔽</span> <button class="btn-micro success-btn" onclick="toggleTaskHide(${t.id})">恢复显示</button>` :
                    `<span style="color:#67C23A">显示中</span> <button class="btn-micro danger-btn" onclick="toggleTaskHide(${t.id})">强制下架</button>`
                }
                    </td>
                </tr>
            `).join('')
            : '<tr><td colspan="7" class="empty-row">暂无查询匹配结果</td></tr>';

        container.innerHTML = `
            <div class="toolbar" style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;">
                <div class="search-input-wrapper" style="flex: 1; min-width: 200px;">
                    <input type="text" id="taskSearchInput" placeholder="输入关键词检索..." value="${state.q}" class="search-input" style="width: 100%;">
                    <button id="taskSearchBtn" class="search-icon-btn" title="筛选检索">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </button>
                </div>
                <select id="taskSearchMode" class="search-input" style="width: auto;">
                    <option value="content" ${state.searchMode === 'content' ? 'selected' : ''}>按标题或内容</option>
                    <option value="publisher" ${state.searchMode === 'publisher' ? 'selected' : ''}>搜发单人昵称</option>
                    <option value="worker" ${state.searchMode === 'worker' ? 'selected' : ''}>搜接单人昵称</option>
                </select>
                <select id="taskCatSelect" class="search-input" style="width: auto; min-width: 120px;">
                    <option value="">全部分类</option>
                    <option value="STUDY" ${state.category === 'STUDY' ? 'selected' : ''}>学业指导</option>
                    <option value="TRADE" ${state.category === 'TRADE' ? 'selected' : ''}>物品交易</option>
                    <option value="HELP" ${state.category === 'HELP' ? 'selected' : ''}>生活协助</option>
                </select>
                <select id="taskStatusSelect" class="search-input" style="width: auto; min-width: 120px;">
                    <option value="">所有进度</option>
                    <option value="OPEN" ${state.status === 'OPEN' ? 'selected' : ''}>未接单</option>
                    <option value="IN_PROGRESS" ${state.status === 'IN_PROGRESS' ? 'selected' : ''}>进行中</option>
                    <option value="COMPLETED" ${state.status === 'COMPLETED' ? 'selected' : ''}>已完成</option>
                    <option value="CANCELLED" ${state.status === 'CANCELLED' ? 'selected' : ''}>已取消</option>
                </select>
                <select id="taskHiddenSelect" class="search-input" style="width: auto; min-width: 120px;">
                    <option value="">管控状态</option>
                    <option value="false" ${state.is_hidden === 'false' ? 'selected' : ''}>正常显示</option>
                    <option value="true" ${state.is_hidden === 'true' ? 'selected' : ''}>被封/下架</option>
                </select>
                <select id="taskSortSelect" class="search-input" style="width: auto; min-width: 155px;">
                    <option value="-created_at" ${state.ordering === '-created_at' ? 'selected' : ''}>最新发单优先</option>
                    <option value="created_at" ${state.ordering === 'created_at' ? 'selected' : ''}>最早发单优先</option>
                    <option value="-reward_amount" ${state.ordering === '-reward_amount' ? 'selected' : ''}>赏金最高优先</option>
                    <option value="reward_amount" ${state.ordering === 'reward_amount' ? 'selected' : ''}>赏金最低优先</option>
                </select>
                <button class="btn-micro" style="padding:0 15px" onclick="window.open(window.api.getExportTasksUrl(), '_blank')">导出数据 (CSV)</button>
            </div>
            <div class="card table-card">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th><th>任务名/分类</th><th>悬赏</th><th>进度状态</th><th>发单人</th><th>接单人</th><th>管控操作</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
            ${data.count ? buildPagination(data.count, state.page, 20, 'tasks') : ''}
        `;

        // 工具栏交互事件
        const triggerTaskSearch = () => {
            viewState.tasks.searchMode = document.getElementById('taskSearchMode').value;
            viewState.tasks.q = document.getElementById('taskSearchInput').value.trim();
            viewState.tasks.category = document.getElementById('taskCatSelect').value;
            viewState.tasks.status = document.getElementById('taskStatusSelect').value;
            viewState.tasks.is_hidden = document.getElementById('taskHiddenSelect').value;
            viewState.tasks.ordering = document.getElementById('taskSortSelect').value;
            viewState.tasks.page = 1;
            switchView('tasks');
        };

        ['taskSearchBtn'].forEach(id => document.getElementById(id).addEventListener('click', triggerTaskSearch));
        ['taskSearchMode', 'taskCatSelect', 'taskStatusSelect', 'taskHiddenSelect', 'taskSortSelect'].forEach(id => 
            document.getElementById(id).addEventListener('change', triggerTaskSearch)
        );
        document.getElementById('taskSearchInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') triggerTaskSearch();
        });
    }

    window.toggleTaskHide = async (id) => {
        try {
            await window.api.toggleTaskVisibility(id);
            switchView('tasks');
        } catch (e) { alert(e.message); }
    };

    /* ================================================================
       全局任务详情弹窗
    ================================================================ */
    window.showTaskDetail = async (id) => {
        let task = window._taskCache && window._taskCache[id];
        
        // 如果缓存里没有或者缓存的数据不完整（例如只是列表基础数据），则进行网络请求
        if (!task || !task.content) {
            try {
                task = await window.api.getTaskDetail(id);
                window._taskCache = window._taskCache || {};
                window._taskCache[id] = task;
            } catch (err) {
                alert('获取任务详情失败，可能是该任务已被彻底删除');
                return;
            }
        }

        const statMap = { 'OPEN': '未接单', 'PENDING_ACCEPT': '待接受', 'IN_PROGRESS': '进行中', 'PENDING_CONFIRM': '待确认', 'COMPLETED': '已完成', 'CANCELLED': '已取消' };
        const catEmoji = { 'STUDY': '📚', 'TRADE': '📦', 'HELP': '🙋', '其他': '✨' };
        const catMap = { 'STUDY': '学业指导', 'TRADE': '物品交易', 'HELP': '生活协助' };

        const images = Array.isArray(task.images) ? task.images : [];
        const galleryHtml = images.length
            ? `<div class="detail-gallery">
                ${images.map((url, i) => `
                    <div class="gallery-item" onclick="previewImage('${url}')" title="点击放大">
                        <img src="${url}" alt="任务图 ${i + 1}" onerror="this.parentElement.style.display='none'">
                        <div class="gallery-overlay">🔍</div>
                    </div>
                `).join('')}
               </div>`
            : `<div class="no-image-tip">📭 该任务未附图</div>`;

        const pub = task.publisher || {};
        const pubAvatar = pub.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${pub.username || 'pub'}`;
        const wkr = task.worker || null;
        
        const workerHtml = wkr
            ? `<div class="detail-person">
                <img src="${wkr.avatar || 'https://api.dicebear.com/7.x/notionists/svg?seed=' + wkr.username}" class="detail-avatar">
                <div>
                    <div class="detail-person-name">${wkr.nickname || wkr.username}</div>
                    <div class="detail-person-sub">@${wkr.username} · ${wkr.credit_score} 积分</div>
                </div>
               </div>`
            : `<span style="color:#999">暂无接单人</span>`;

        const modalHtml = `
            <div class="task-modal-overlay" id="taskModalOverlay" onclick="closeTaskModal(event)">
                <div class="task-modal" onclick="event.stopPropagation()">
                    <div class="task-modal-header">
                        <div>
                            <span class="task-modal-category">${catEmoji[task.category] || '📋'} ${catMap[task.category] || task.category}</span>
                            <h2 class="task-modal-title">${task.title}</h2>
                        </div>
                        <button class="task-modal-close" onclick="closeTaskModal()">✕</button>
                    </div>

                    <div class="task-modal-meta">
                        <span class="meta-chip reward">🎁 ${task.reward_amount} 分</span>
                        <span class="meta-chip status">${statMap[task.status] || task.status}</span>
                        ${task.is_hidden ? '<span class="meta-chip hidden">🚫 已屏蔽</span>' : ''}
                        <span>📍 ${task.location_name || '未设置位置'}</span>
                    </div>

                    <div class="task-modal-section">
                        <div class="section-label">📸 现场图片</div>
                        ${galleryHtml}
                    </div>

                    <div class="task-modal-section">
                        <div class="section-label">📝 详细描述</div>
                        <div class="task-modal-content">${task.content || '（暂无描述）'}</div>
                    </div>

                    <div class="task-modal-persons">
                        <div class="person-col">
                            <div class="section-label">👤 发单人</div>
                            <div class="detail-person">
                                <img src="${pubAvatar}" class="detail-avatar">
                                <div>
                                    <div class="detail-person-name">${pub.nickname || pub.username || '-'}</div>
                                    <div class="detail-person-sub">@${pub.username || '-'} · ${pub.credit_score ?? '-'} 积分</div>
                                </div>
                            </div>
                        </div>
                        <div class="person-col">
                            <div class="section-label">🤝 接单人</div>
                            ${workerHtml}
                        </div>
                    </div>

                    <div class="task-modal-actions">
                        ${task.is_hidden !== undefined ? (task.is_hidden 
                            ? `<button class="btn-micro success-btn" onclick="toggleTaskHide(${task.id}); closeTaskModal();">✅ 恢复显示</button>`
                            : `<button class="btn-micro danger-btn" onclick="toggleTaskHide(${task.id}); closeTaskModal();">🚫 强制下架</button>`
                        ) : ''}
                        <button class="btn-micro" onclick="closeTaskModal()">返回</button>
                    </div>
                </div>
            </div>
        `;

        const existing = document.getElementById('taskModalOverlay');
        if (existing) existing.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.body.style.overflow = 'hidden';
    };

    window.closeTaskModal = (event) => {
        if (event && event.target !== document.getElementById('taskModalOverlay')) return;
        const modal = document.getElementById('taskModalOverlay');
        if (modal) {
            modal.classList.add('closing');
            setTimeout(() => { modal.remove(); document.body.style.overflow = ''; }, 250);
        } else {
            document.body.style.overflow = '';
        }
    };

    window.previewImage = (url) => {
        const overlay = document.createElement('div');
        overlay.className = 'img-preview-overlay';
        overlay.innerHTML = `
            <div class="img-preview-box">
                <img src="${url}">
                <button class="img-preview-close" onclick="this.closest('.img-preview-overlay').remove()">✕ 关闭</button>
            </div>
        `;
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
    };


    /* ================================================================
       5. 举报工单（含搜索过滤及 Tabs）
    ================================================================ */
    async function renderReports(container) {
        const state = viewState.reports;
        const reports = await window.api.getReports({
            status: state.status,
            q: state.q
        });

        const tabs = buildTabs([
            { label: '全部', value: '' },
            { label: '🔴 待处理', value: 'PENDING' },
            { label: '✅ 确认违规', value: 'RESOLVED' },
            { label: '⬜ 已退回', value: 'REJECTED' }
        ], state.status, 'reports');

        const statMap = { 'PENDING': '待审核', 'RESOLVED': '确认违规', 'REJECTED': '已退回' };

        const renderAction = (id, status) => {
            if (status !== 'PENDING') return `<span style="color:#999">已处理</span>`;
            return `
                <button class="btn-micro danger-btn" onclick="handleActionReport(${id}, 'resolve')">确认违规</button>
                <button class="btn-micro" onclick="handleActionReport(${id}, 'reject')">无违规退回</button>
            `;
        };

        const tableRows = reports.length
            ? reports.map(r => `
                <tr>
                    <td>#${r.id}</td>
                    <td>${r.reporter_name}</td>
                    <td>
                        ${r.target_type === 'TASK' 
                            ? `<span class="tag">任务</span> <button class="task-title-link" style="display:inline-block; margin-left:5px" onclick="showTaskDetail(${r.target_id})">#${r.target_id} 查看详情</button>`
                            : `<span class="tag">用户</span> #${r.target_id}`
                        }
                    </td>
                    <td>
                        <span style="color:#E6A23C; font-weight:500">${r.reason}</span>
                        ${r.description ? `<br/><small style="color:#999">${r.description}</small>` : ''}
                    </td>
                    <td><span class="status-badge status-${r.status.toLowerCase()}">${statMap[r.status]}</span></td>
                    <td>${new Date(r.created_at).toLocaleString()}</td>
                    <td>${renderAction(r.id, r.status)}</td>
                </tr>
            `).join('')
            : '<tr><td colspan="7" class="empty-row">该状态下暂无工单</td></tr>';

        container.innerHTML = `
            ${tabs}
            <div class="toolbar" style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;">
                <div class="search-input-wrapper" style="flex: 1; max-width: 400px;">
                    <input type="text" id="reportSearchInput" placeholder="按举报人、原因或详情搜索..." value="${state.q}" class="search-input" style="width: 100%;">
                    <button id="reportSearchBtn" class="search-icon-btn" title="筛选检索">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </button>
                </div>
            </div>
            <div class="card table-card">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>工单号</th><th>举报人</th><th>目标</th><th>原因/详情</th><th>状态</th><th>提交时间</th><th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
        `;
        
        // 绑定搜索事件
        const triggerSearch = () => {
            viewState.reports.q = document.getElementById('reportSearchInput').value.trim();
            switchView('reports');
        };
        
        document.getElementById('reportSearchBtn').addEventListener('click', triggerSearch);
        document.getElementById('reportSearchInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') triggerSearch();
        });
    }

    window.handleActionReport = async (id, action) => {
        let note = prompt('请输入处理备注 (可选):');
        if (note === null) return;
        try {
            await window.api.actionReport(id, action, note);
            switchView('reports');
        } catch (e) {
            alert(e.message);
        }
    };

    /* ================================================================
       6. 操作审计日志
    ================================================================ */
    async function renderAudits(container) {
        const state = viewState.audits;
        const data = await window.api.getAudits({
            page: state.page,
            q: state.q
        });
        const audits = data.results || data;

        const actionColorMap = {
            'BAN': '#F56C6C', 'HIDE': '#E6A23C', 'APPROVE': '#67C23A',
            'REJECT': '#F56C6C', 'VERIFY': '#409EFF', 'OTHER': '#909399'
        };

        const tableRows = audits.length
            ? audits.map(a => `
                <tr>
                    <td>#${a.id}</td>
                    <td>${a.admin_name}</td>
                    <td><span class="status-badge" style="background:${actionColorMap[a.action] || '#909399'}">${a.action}</span></td>
                    <td>${a.target_id}</td>
                    <td>${a.ip_address || '-'}</td>
                    <td style="max-width:300px;white-space:normal;word-break:break-all;">${a.reason}</td>
                    <td>${new Date(a.created_at).toLocaleString()}</td>
                </tr>
            `).join('')
            : '<tr><td colspan="7" class="empty-row">暂无审计记录</td></tr>';

        container.innerHTML = `
            <div class="toolbar" style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;">
                <div class="search-input-wrapper" style="flex: 1; max-width: 400px;">
                    <input type="text" id="auditSearchInput" placeholder="按内容或目标ID搜索..." value="${state.q}" class="search-input" style="width: 100%;">
                    <button id="auditSearchBtn" class="search-icon-btn" title="筛选检索">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </button>
                </div>
            </div>
            <div class="card table-card">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>日志ID</th><th>操作者</th><th>变更类型</th><th>业务目标</th><th>来源IP</th><th>详细说明</th><th>发生时间</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
            ${data.count ? buildPagination(data.count, state.page, 20, 'audits') : ''}
        `;
        
        const triggerSearch = () => {
            viewState.audits.q = document.getElementById('auditSearchInput').value.trim();
            viewState.audits.page = 1;
            switchView('audits');
        };
        
        document.getElementById('auditSearchBtn').addEventListener('click', triggerSearch);
        document.getElementById('auditSearchInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') triggerSearch();
        });
    }

});

