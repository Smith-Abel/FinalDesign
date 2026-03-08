const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

// 状态 Tab 配置
// 前端 tab key → API status 参数的映射
const TAB_TO_STATUS = {
    published: '',
    in_progress: 'IN_PROGRESS',
    completed: 'COMPLETED',
}

const STATUS_TABS = [
    { key: 'published', label: '发布的任务' },
    { key: 'in_progress', label: '进行中的任务' },
    { key: 'completed', label: '完成的任务' },
]

const STATUS_MAP = {
    OPEN: { label: '待接单', cls: 'badge badge-open' },
    IN_PROGRESS: { label: '进行中', cls: 'badge badge-progress' },
    PENDING_CONFIRM: { label: '待确认', cls: 'badge badge-pending' },
    COMPLETED: { label: '已完成', cls: 'badge badge-done' },
    CANCELLED: { label: '已取消', cls: 'badge badge-cancel' },
}

function formatTask(t) {
    const st = STATUS_MAP[t.status] || {}
    return {
        ...t,
        statusLabel: st.label || t.status,
        statusClass: st.cls || 'badge',
        canEdit: t.status === 'OPEN',       // 只有待接单可编辑
        canCancel: t.status !== 'COMPLETED' && t.status !== 'CANCELLED',
    }
}

Page({
    data: {
        tabs: STATUS_TABS,
        activeTab: 'published',
        tasks: [],
        isLoading: false,
        // 编辑弹窗相关
        showEditModal: false,
        editingTask: null,
        editForm: { title: '', content: '', tags: '', reward_amount: '0' },
        isSaving: false,
    },

    onLoad(options) {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        // 支持从个人中心快捷入口携带 tab 参数直接定位
        if (options.tab && TAB_TO_STATUS.hasOwnProperty(options.tab)) {
            this.setData({ activeTab: options.tab })
        } else {
            this.setData({ activeTab: 'published' })
        }
    },

    onShow() {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        this._loadTasks()
    },

    onPullDownRefresh() {
        this._loadTasks().finally(() => wx.stopPullDownRefresh())
    },

    onTabChange(e) {
        const key = e.currentTarget.dataset.key
        if (key === this.data.activeTab) return
        this.setData({ activeTab: key })
        this._loadTasks()
    },

    async _loadTasks() {
        this.setData({ isLoading: true })
        try {
            const { activeTab } = this.data
            // 把前端 tab key 转成 API 需要的 status 值
            const statusParam = TAB_TO_STATUS[activeTab] ?? activeTab
            let url = '/api/tasks/mine/'
            if (statusParam) url += `?status=${statusParam}`

            const res = await request.get(url)
            const list = Array.isArray(res) ? res : (res.results || [])
            this.setData({ tasks: list.map(formatTask) })
        } catch (e) {
            console.error('加载我的任务失败', e)
        } finally {
            this.setData({ isLoading: false })
        }
    },

    goToDetail(e) {
        const id = e.currentTarget.dataset.id
        wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${id}` })
    },

    // ── 编辑任务 ──
    openEdit(e) {
        const id = e.currentTarget.dataset.id
        const task = this.data.tasks.find(t => t.id === id)
        if (!task) return
        this.setData({
            showEditModal: true,
            editingTask: task,
            editForm: {
                title: task.title,
                content: task.content,
                tags: task.tags || '',
                reward_amount: String(task.reward_amount),
            },
        })
    },

    closeEdit() {
        this.setData({ showEditModal: false, editingTask: null })
    },

    onEditInput(e) {
        const field = e.currentTarget.dataset.field
        this.setData({ [`editForm.${field}`]: e.detail.value })
    },

    handleSaveEdit: debounce(async function () {
        const { editingTask, editForm } = this.data
        if (!editingTask) return

        if (!editForm.title.trim() || !editForm.content.trim()) {
            wx.showToast({ title: '标题和内容不能为空', icon: 'none' })
            return
        }

        this.setData({ isSaving: true })
        try {
            await request.patch(`/api/tasks/${editingTask.id}/edit/`, {
                title: editForm.title.trim(),
                content: editForm.content.trim(),
                tags: editForm.tags.trim(),
                reward_amount: (parseFloat(editForm.reward_amount) || 0).toFixed(2),
            })
            wx.showToast({ title: '修改成功', icon: 'success' })
            this.closeEdit()
            await this._loadTasks()
        } catch (e) {
            console.error('修改任务失败', e)
        } finally {
            this.setData({ isSaving: false })
        }
    }),

    // ── 取消任务 ──
    handleCancel(e) {
        const id = e.currentTarget.dataset.id
        const task = this.data.tasks.find(t => t.id === id)
        if (!task) return

        // OPEN 状态提示会退还手续费，已接单则不退
        const tipMsg = task.status === 'OPEN'
            ? '取消后将退还 5 积分发布手续费，确认取消吗？'
            : '任务已被接单，取消后不退还手续费，确认取消吗？'

        wx.showModal({
            title: '取消任务',
            content: tipMsg,
            confirmColor: '#F56C6C',
            confirmText: '确认取消',
            success: async ({ confirm }) => {
                if (!confirm) return
                try {
                    const res = await request.post(`/api/tasks/${id}/cancel/`)
                    const msg = res.fee_refunded ? '已取消，手续费已退还 🎉' : '任务已取消'
                    wx.showToast({ title: msg, icon: 'success', duration: 2500 })
                    await this._loadTasks()
                } catch (e) {
                    console.error('取消任务失败', e)
                }
            },
        })
    },
})
