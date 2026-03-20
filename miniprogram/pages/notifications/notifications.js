const request = require('../../utils/request')
const { formatTime } = require('../../utils/util')

Page({
    data: {
        notifications: [],
        isLoading: false,
    },

    onLoad() {
        this.loadNotifications()
    },

    onShow() {
        this.loadNotifications()
    },

    onPullDownRefresh() {
        this.loadNotifications().finally(() => wx.stopPullDownRefresh())
    },

    async loadNotifications() {
        this.setData({ isLoading: true })
        try {
            const res = await request.get('/api/notifications/')
            const list = Array.isArray(res) ? res : (res.results || [])
            
            // 格式化时间
            list.forEach(item => {
                if(item.created_at) {
                    item.created_at = formatTime(new Date(item.created_at))
                }
            })
            
            this.setData({ notifications: list })
        } catch (e) {
            console.error('加载通知失败', e)
        } finally {
            this.setData({ isLoading: false })
        }
    },

    async handleReadAll() {
        if (this.data.notifications.length === 0) return;
        try {
            const res = await request.post('/api/notifications/read-all/')
            wx.showToast({ title: '全部已读', icon: 'success' })
            this.loadNotifications()
        } catch (e) {
            console.error('一键已读失败', e)
        }
    },

    async handleClickNotice(e) {
        const { id, taskid } = e.currentTarget.dataset;
        const notice = this.data.notifications.find(n => n.id === id);
        
        // 如果未读，先标记已读
        if (notice && !notice.is_read) {
            try {
                await request.patch(`/api/notifications/${id}/read/`)
                notice.is_read = true;
                this.setData({ notifications: this.data.notifications })
            } catch (err) {
                console.error('标记已读失败', err)
            }
        }
        
        // 跳转到任务详情
        if (taskid) {
            wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${taskid}` })
        }
    }
})
