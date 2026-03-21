/**
 * 核心 API 管理与拦截器
 * - 支持 JWT 鉴权与 401 自动跳转
 * - 所有管理端列表接口支持分页及筛选
 */
const BASE_URL = 'http://127.0.0.1:8000/api';

class ApiClient {
    constructor() {
        this.token = localStorage.getItem('adminToken');
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('adminToken', token);
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('adminToken');
    }

    async request(endpoint, options = {}) {
        const url = `${BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (response.status === 401) {
                // 如果是请求登录接口时帐号密码错误引起的 401，则不触发全局拦截和跳转重载
                if (endpoint !== '/auth/login/') {
                    this.clearToken();
                    window.location.href = 'index.html';
                    return null;
                }
            }

            let data;
            const resText = await response.text();
            try {
                data = resText ? JSON.parse(resText) : {};
            } catch (e) {
                data = {};
            }
            
            if (!response.ok) {
                throw new Error(data.detail || '请求失败，请稍后重试');
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // ── 认证 ──
    // 使用项目自定义的账号密码登录接口，返回 { token: { access, refresh } }
    login(username, password) {
        return this.request('/auth/login/', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    }

    // ── 仪表盘 ──
    getStats() {
        return this.request('/manage/dashboard/');
    }

    // ── 用户管理（分页 + 关键词搜索 + 筛选/排序）──
    // 返回 { count, results: [...] }
    getUsers({ page = 1, pageSize = 20, q = '', ...filters } = {}) {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (q) params.append('q', q);
        Object.entries(filters).forEach(([k, v]) => {
            if (v !== undefined && v !== '') params.append(k, v);
        });
        return this.request(`/manage/users/?${params}`);
    }

    banUser(userId) {
        return this.request(`/manage/users/${userId}/ban/`, { method: 'POST' });
    }

    // ── 任务管理（分页 + 筛选/排序）──
    // 返回 { count, results: [...] }
    getTasks({ page = 1, pageSize = 20, q = '', ...filters } = {}) {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (q) params.append('q', q);
        Object.entries(filters).forEach(([k, v]) => {
            if (v !== undefined && v !== '') params.append(k, v);
        });
        return this.request(`/manage/tasks/?${params}`);
    }
    
    toggleTaskVisibility(taskId) {
        return this.request(`/manage/tasks/${taskId}/toggle_hide/`, { method: 'POST' });
    }

    getTaskDetail(taskId) {
        return this.request(`/tasks/${taskId}/`);
    }

    // ── 学生认证（状态筛选）──
    getVerifies(status = '') {
        const query = status ? `?status=${status}` : '';
        return this.request(`/manage/verifies/${query}`);
    }
    
    actionVerify(id, action, note = '') {
        return this.request(`/manage/verifies/${id}/action/`, {
            method: 'POST',
            body: JSON.stringify({ action, note })
        });
    }

    // ── 举报工单（状态筛选）──
    getReports(status = '') {
        const query = status ? `?status=${status}` : '';
        return this.request(`/manage/reports/${query}`);
    }
    
    actionReport(id, action, note = '') {
        return this.request(`/manage/reports/${id}/action/`, {
            method: 'POST',
            body: JSON.stringify({ action, note })
        });
    }
}

window.api = new ApiClient();
