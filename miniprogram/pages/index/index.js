const app = getApp()
const request = require('../../utils/request')

const TABS = [
    { key: '', label: '推荐' },
    { key: 'STUDY', label: '学业' },
    { key: 'TRADE', label: '交易' },
    { key: 'HELP', label: '生活' },
]

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

function timeAgo(dateStr) {
    const diff = (Date.now() - new Date(dateStr)) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    return `${Math.floor(diff / 86400)} 天前`
}

function formatTask(t) {
    const cat = CAT_MAP[t.category] || {}
    const st = STATUS_MAP[t.status] || {}
    return {
        ...t,
        catLabel: cat.label || t.category,
        catClass: cat.cls || 'badge',
        statusLabel: st.label || t.status,
        statusClass: st.cls || 'badge',
        timeAgo: timeAgo(t.created_at),
    }
}

Page({
    data: {
        tabs: TABS,
        activeTab: '',
        tasks: [],
        page: 1,
        hasMore: true,
        isLoading: false,
        isLoadingMore: false,
        searchKeyword: '',
        searchInput: '',
        sortType: '-created_at', // default sort
    },

    onLoad() {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        this._loadTasks(true)
    },

    onShow() {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        // 从详情页返回后刷新列表（状态可能变化）
        this._loadTasks(true)
    },

    onPullDownRefresh() {
        this._loadTasks(true).finally(() => wx.stopPullDownRefresh())
    },

    onLoadMore() {
        if (!this.data.hasMore || this.data.isLoadingMore) return
        this._loadTasks(false)
    },

    onTabChange(e) {
        const key = e.currentTarget.dataset.key
        if (key === this.data.activeTab) return
        this.setData({ activeTab: key })
        this._loadTasks(true)
    },

    goToDetail(e) {
        const id = e.currentTarget.dataset.id
        wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${id}` })
    },

    onSearchInput(e) {
        this.setData({ searchInput: e.detail.value })
    },

    onSearchConfirm() {
        this.setData({ searchKeyword: this.data.searchInput })
        this._loadTasks(true)
    },

    onSortChange(e) {
        const type = e.currentTarget.dataset.type
        if (this.data.sortType === type) return
        this.setData({ sortType: type })
        this._loadTasks(true)
    },

    async _loadTasks(reset) {
        if (reset) {
            this.setData({ page: 1, hasMore: true, isLoading: true })
        } else {
            this.setData({ isLoadingMore: true })
        }

        try {
            const { activeTab, page, searchKeyword, sortType } = this.data
            let queryStr = `page=${page}&page_size=10&ordering=${sortType}`
            if (activeTab) queryStr += `&category=${activeTab}`
            if (searchKeyword) queryStr += `&search=${encodeURIComponent(searchKeyword)}`

            const res = await request.get(`/api/tasks/?${queryStr}`)
            // 兼容分页和普通数组两种响应格式
            const list = Array.isArray(res) ? res : (res.results || [])
            const formatted = list.map(formatTask)

            this.setData({
                tasks: reset ? formatted : [...this.data.tasks, ...formatted],
                hasMore: list.length === 10,
                page: reset ? 2 : this.data.page + 1,
            })
        } catch (e) {
            console.error(e)
        } finally {
            this.setData({ isLoading: false, isLoadingMore: false })
        }
    },
})
