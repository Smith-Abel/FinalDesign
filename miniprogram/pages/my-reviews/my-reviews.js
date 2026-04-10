const app = getApp()
const request = require('../../utils/request')

Page({
    data: {
        reviews: [],
        page: 1,
        hasMore: true,
        isLoading: false
    },

    onLoad() {
        this._loadReviews(true)
    },

    async onPullDownRefresh() {
        await this._loadReviews(true)
        wx.stopPullDownRefresh()
    },

    onReachBottom() {
        if (!this.data.hasMore || this.data.isLoading) return
        this._loadReviews(false)
    },

    async _loadReviews(isRefresh = false) {
        if (this.data.isLoading) return
        this.setData({ isLoading: true })
        
        try {
            const page = isRefresh ? 1 : this.data.page
            const res = await request.get(`/api/reviews/received/?page=${page}`)
            
            const newReviews = res.results.map(r => ({
                ...r,
                created_date: r.created_at ? r.created_at.substring(0, 10).replace(/-/g, '/') : ''
            }))
            
            this.setData({
                reviews: isRefresh ? newReviews : [...this.data.reviews, ...newReviews],
                page: page + 1,
                hasMore: res.next !== null
            })
        } catch (e) {
            console.error('load reviews failed:', e)
        } finally {
            this.setData({ isLoading: false })
        }
    },

    goToTaskDetail(e) {
        const taskId = e.currentTarget.dataset.id
        if (taskId) {
            wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${taskId}` })
        }
    }
})
