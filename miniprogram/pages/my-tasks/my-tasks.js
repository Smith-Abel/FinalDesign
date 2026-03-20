const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

// 状态 Tab 配置
const STATUS_TABS = [
    { key: 'publisher', label: '我发布的' },
    { key: 'worker', label: '我接取的' },
]

const STATUS_MAP = {
    OPEN: { label: '待接单', cls: 'badge badge-open' },
    IN_PROGRESS: { label: '进行中', cls: 'badge badge-progress' },
    PENDING_CONFIRM: { label: '待确认', cls: 'badge badge-pending' },
    COMPLETED: { label: '已完成', cls: 'badge badge-done' },
    CANCELLED: { label: '已取消', cls: 'badge badge-cancel' },
}

function formatTask(t, role) {
    const st = STATUS_MAP[t.status] || {}
    const isPublisher = role === 'publisher';
    const isWorker = role === 'worker';
    return {
        ...t,
        statusLabel: st.label || t.status,
        statusClass: st.cls || 'badge',
        canEdit: t.status === 'OPEN' && isPublisher,       
        canCancel: t.status !== 'COMPLETED' && t.status !== 'CANCELLED' && isPublisher,
        canConfirm: (t.status === 'PENDING_CONFIRM' || t.status === 'IN_PROGRESS') && isPublisher,
        canRequestComplete: t.status === 'IN_PROGRESS' && isWorker,
        canReview: t.status === 'COMPLETED' && !t.is_reviewed,
    }
}

Page({
    data: {
        tabs: STATUS_TABS,
        activeTab: 'publisher',
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
        if (options.tab === 'worker') {
            this.setData({ activeTab: 'worker' })
        } else {
            this.setData({ activeTab: 'publisher' })
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
            const role = this.data.activeTab
            let url = `/api/tasks/mine/?role=${role}`

            const res = await request.get(url)
            const list = Array.isArray(res) ? res : (res.results || [])
            this.setData({ tasks: list.map(t => formatTask(t, role)) })
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

    goToReview(e) {
        const id = e.currentTarget.dataset.id
        wx.navigateTo({ url: `/pages/review/review?taskId=${id}` })
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

    // ── 确认完成（发布者） ──
    handleConfirmComplete(e) {
        const id = e.currentTarget.dataset.id
        wx.showModal({
            title: '确认完成',
            content: '确认后，预付积分将转给接单者。操作不可逆，请核实任务是否真正完成！',
            confirmColor: '#07C160',
            success: async ({ confirm }) => {
                if (!confirm) return
                try {
                    await request.post(`/api/tasks/${id}/complete/`)
                    wx.showToast({ title: '已确认完成', icon: 'success' })
                    await this._loadTasks()
                } catch (err) {
                    console.error('确认完成失败', err)
                }
            }
        })
    },

    // ── 申请完成（接单者） ──
    handleRequestComplete(e) {
        const id = e.currentTarget.dataset.id
        wx.showModal({
            title: '申请完成',
            content: '是否确实已完成任务，并通知发布者验收打款？',
            confirmColor: '#07C160',
            success: async ({ confirm }) => {
                if (!confirm) return
                try {
                    await request.post(`/api/tasks/${id}/request_complete/`)
                    wx.showToast({ title: '已发送申请', icon: 'success' })
                    await this._loadTasks()
                } catch (err) {
                    console.error('申请完成失败', err)
                }
            }
        })
    },
})
