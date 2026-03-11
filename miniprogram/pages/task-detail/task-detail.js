const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

const CAT_MAP = {
    STUDY: { label: '学业指导', cls: 'badge cat-study' },
    TRADE: { label: '物品交易', cls: 'badge cat-trade' },
    HELP: { label: '生活协助', cls: 'badge cat-help' },
}
const STATUS_MAP = {
    OPEN: { label: '待接单', cls: 'badge badge-open' },
    IN_PROGRESS: { label: '进行中', cls: 'badge badge-progress' },
    PENDING_CONFIRM: { label: '待确认', cls: 'badge badge-pending' },
    COMPLETED: { label: '已完成', cls: 'badge badge-done' },
    CANCELLED: { label: '已取消', cls: 'badge badge-cancel' },
}
function timeAgo(d) {
    const s = (Date.now() - new Date(d)) / 1000
    if (s < 60) return '刚刚'
    if (s < 3600) return `${Math.floor(s / 60)} 分钟前`
    if (s < 86400) return `${Math.floor(s / 3600)} 小时前`
    return `${Math.floor(s / 86400)} 天前`
}

Page({
    data: {
        task: null,
        actionType: 'none',  // accept | complete_cancel | waiting | none
        canReport: false,    // 非发布者可以举报
        isLoading: false,
    },

    onLoad({ id }) {
        this.taskId = id
        this._loadTask()
    },

    async _loadTask() {
        try {
            wx.showLoading({ title: '加载中', mask: true })
            const res = await request.get(`/api/tasks/${this.taskId}/`)
            const cat = CAT_MAP[res.category] || {}
            const st = STATUS_MAP[res.status] || {}
            const task = {
                ...res,
                catLabel: cat.label || res.category,
                catClass: cat.cls || 'badge',
                statusLabel: st.label || res.status,
                statusClass: st.cls || 'badge',
                timeAgo: timeAgo(res.created_at),
                tagList: res.tags ? res.tags.split(',').filter(Boolean) : [],
            }
            const actionType = this._calcActionType(task)
            this.setData({ task, actionType })
        } catch (e) {
            console.error(e)
        } finally {
            wx.hideLoading()
        }
    },

    _calcActionType(task) {
        const userId = app.globalData.userInfo?.id
        if (!userId) return 'none'
        const { status, publisher, worker } = task
        // 非发布者可见举报按钮，已取消和已完成的任务不显示
        const canReport = publisher?.id !== userId && status !== 'CANCELLED' && status !== 'COMPLETED'
        this.setData({ canReport })
        if (status === 'COMPLETED' || status === 'CANCELLED') return 'none'
        if (status === 'OPEN') return publisher?.id === userId ? 'none' : 'accept'
        if (status === 'IN_PROGRESS' || status === 'PENDING_CONFIRM') {
            if (publisher?.id === userId) return 'complete_cancel'
            if (worker?.id === userId) return 'waiting'
        }
        return 'none'
    },

    handleAccept: debounce(async function () {
        this.setData({ isLoading: true })
        try {
            await request.post(`/api/tasks/${this.taskId}/accept/`)
            wx.showToast({
                title: '接单成功！',
                icon: 'success',
                duration: 800,
                complete: () => this._loadTask(),
            })
        } finally {
            this.setData({ isLoading: false })
        }
    }),

    handleComplete: debounce(async function () {
        wx.showModal({
            title: '确认完成',
            content: '确认该任务已完成？积分将会转账给接单者。',
            confirmText: '确认',
            confirmColor: '#67C23A',
            success: async ({ confirm }) => {
                if (!confirm) return
                this.setData({ isLoading: true })
                try {
                    const res = await request.post(`/api/tasks/${this.taskId}/complete/`)
                    let msg = '任务已完成 ✅'
                    if (res.first_help_bonus) msg += '\n接单者获得首次助人奖励！'
                    wx.showModal({ title: '完成', content: msg, showCancel: false, confirmColor: '#67C23A' })
                    this._loadTask()
                } finally {
                    this.setData({ isLoading: false })
                }
            },
        })
    }),

    handleCancel: debounce(async function () {
        wx.showModal({
            title: '取消任务',
            content: '确定要取消这个任务吗？',
            confirmColor: '#F56C6C',
            confirmText: '取消任务',
            success: async ({ confirm }) => {
                if (!confirm) return
                this.setData({ isLoading: true })
                try {
                    await request.post(`/api/tasks/${this.taskId}/cancel/`)
                    wx.showToast({ title: '任务已取消', icon: 'success', duration: 800, complete: () => this._loadTask() })
                } finally {
                    this.setData({ isLoading: false })
                }
            },
        })
    }),

    goToChat() {
        const title = encodeURIComponent(this.data.task?.title || '任务聊天')
        wx.navigateTo({ url: `/pages/chat/chat?id=${this.taskId}&title=${title}` })
    },

    goToReport() {
        wx.navigateTo({ url: `/pages/report/report?target_type=task&target_id=${this.taskId}` })
    },

    previewTaskImage(e) {
        const url = e.currentTarget.dataset.url
        wx.previewImage({
            urls: this.data.task.images,
            current: url
        })
    },
})
