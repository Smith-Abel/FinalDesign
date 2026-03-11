const request = require('../../utils/request')
const app = getApp()

const STATUS_CLASS = {
    PENDING: 'status-pending',
    HANDLED: 'status-handled',
    REJECTED: 'status-rejected',
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
        reports: [],
        isLoading: true,
    },

    onShow() {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        this._load()
    },

    async _load() {
        this.setData({ isLoading: true })
        try {
            const data = await request.get('/api/reports/mine/')
            // 兼容分页与数组两种返回格式
            const list = Array.isArray(data) ? data : (data.results || [])
            const reports = list.map(r => ({
                ...r,
                statusClass: STATUS_CLASS[r.status] || '',
                timeAgo: timeAgo(r.created_at),
            }))
            this.setData({ reports })
        } catch (e) {
            console.error(e)
        } finally {
            this.setData({ isLoading: false })
        }
    },

    previewImages(e) {
        const { images, url } = e.currentTarget.dataset
        wx.previewImage({ urls: images, current: url })
    },
})
