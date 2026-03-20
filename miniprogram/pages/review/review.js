const request = require('../../utils/request')

Page({
    data: {
        taskId: null,
        dimensions: [
            { key: 'communication', label: '沟通交流' },
            { key: 'attitude', label: '服务态度' },
            { key: 'quality', label: '完成质量' },
            { key: 'speed', label: '响应速度' },
            { key: 'reliability', label: '诚信可靠' },
        ],
        form: {
            communication: 5,
            attitude: 5,
            quality: 5,
            speed: 5,
            reliability: 5,
            comment: ''
        },
        isSubmitting: false
    },

    onLoad(options) {
        if (options.taskId) {
            this.setData({ taskId: options.taskId })
        }
    },

    onStarTap(e) {
        const { key, val } = e.currentTarget.dataset
        this.setData({ [`form.${key}`]: val })
    },

    onCommentInput(e) {
        this.setData({ 'form.comment': e.detail.value })
    },

    async handleSubmit() {
        if (!this.data.taskId) {
            wx.showToast({ title: '缺少任务ID', icon: 'none' })
            return
        }
        
        this.setData({ isSubmitting: true })
        try {
            const payload = {
                task: this.data.taskId,
                rating_communication: this.data.form.communication,
                rating_attitude: this.data.form.attitude,
                rating_quality: this.data.form.quality,
                rating_speed: this.data.form.speed,
                rating_reliability: this.data.form.reliability,
                comment: this.data.form.comment
            }
            await request.post('/api/reviews/', payload)
            wx.showToast({ title: '评价成功', icon: 'success' })
            setTimeout(() => {
                wx.navigateBack()
            }, 1000)
        } catch (e) {
            console.error('评价提交失败', e)
        } finally {
            this.setData({ isSubmitting: false })
        }
    }
})
