const app = getApp()
const request = require('../../utils/request')

function formatTimeAgo(dateString) {
    const s = (Date.now() - new Date(dateString)) / 1000
    if (s < 60) return '刚刚'
    if (s < 3600) return `${Math.floor(s / 60)}分钟前`
    if (s < 86400) return `${Math.floor(s / 3600)}小时前`
    return `${Math.floor(s / 86400)}天前`
}

Page({
    data: {
        sessions: [],
        isLoading: false
    },

    onShow() {
        if (app.globalData.token) {
            this.loadSessions()
        }
    },

    onPullDownRefresh() {
        if (app.globalData.token) {
            this.loadSessions().then(() => wx.stopPullDownRefresh())
        } else {
            wx.stopPullDownRefresh()
        }
    },

    async loadSessions() {
        this.setData({ isLoading: true })
        try {
            const res = await request.get(`/api/messages/sessions/?_t=${Date.now()}`)
            const sorted = res.map(item => ({
                ...item,
                timeAgo: formatTimeAgo(item.last_time)
            }))
            this.setData({ sessions: sorted })

            // ── 汇总未读数，驱动 Tab 角标 ──
            const totalUnread = sorted.reduce((sum, s) => sum + (s.unread_count || 0), 0)
            if (totalUnread > 0) {
                wx.setTabBarBadge({ index: 2, text: totalUnread > 99 ? '99+' : String(totalUnread) })
            } else {
                wx.removeTabBarBadge({ index: 2 })
            }

        } catch (e) {
            console.error('获取会话列表失败', e)
        } finally {
            this.setData({ isLoading: false })
        }
    },

    goToSystemNotifications() {
        wx.navigateTo({ url: '/pages/notifications/notifications' })
    },

    goToChat(e) {
        const item = e.currentTarget.dataset.task
        const title = encodeURIComponent(item.task_title)
        const partner = encodeURIComponent(item.partner_name || '任务沟通')
        wx.navigateTo({ url: `/pages/chat/chat?id=${item.task_id}&title=${title}&partner=${partner}` })
    }
})
