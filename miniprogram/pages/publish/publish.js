const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

Page({
    data: {
        categories: [
            { key: 'STUDY', label: '📚 学业' },
            { key: 'TRADE', label: '🛒 交易' },
            { key: 'HELP', label: '🤝 生活' },
        ],
        form: {
            category: '',
            title: '',
            content: '',
            tags: '',
            reward_amount: '0',
            latitude: null,
            longitude: null,
            location_name: '',
            images: [],
        },
        canSubmit: false,
        isLoading: false,
        myCredits: 0,
    },

    onShow() {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        // 刷新可用积分
        this._loadMyCredits()
    },

    async _loadMyCredits() {
        try {
            const res = await request.get('/api/auth/profile/')
            this.setData({ myCredits: res.credit_score })
        } catch (e) { /* ignore */ }
    },

    onCatSelect(e) {
        const category = e.currentTarget.dataset.key
        this.setData({ 'form.category': category })
        this._checkForm()
    },

    onInput(e) {
        const field = e.currentTarget.dataset.field
        this.setData({ [`form.${field}`]: e.detail.value })
        this._checkForm()
    },

    _checkForm() {
        const { category, title, content } = this.data.form
        this.setData({ canSubmit: !!(category && title.trim() && content.trim()) })
    },

    pickLocation() {
        wx.chooseLocation({
            success: ({ name, latitude, longitude }) => {
                this.setData({
                    'form.location_name': name,
                    'form.latitude': latitude,
                    'form.longitude': longitude,
                })
            },
        })
    },

    async chooseImage() {
        if (this.data.form.images.length >= 3) return
        try {
            const res = await new Promise((resolve, reject) => {
                wx.chooseMedia({
                    count: 3 - this.data.form.images.length,
                    mediaType: ['image'],
                    sourceType: ['album', 'camera'],
                    success: resolve,
                    fail: reject,
                })
            })

            const files = res.tempFiles || []
            if (files.length === 0) return

            wx.showLoading({ title: '上传中...', mask: true })
            const urlList = []
            for (const file of files) {
                const url = await request.upload(file.tempFilePath)
                if (url) urlList.push(url)
            }

            if (urlList.length > 0) {
                this.setData({
                    'form.images': [...this.data.form.images, ...urlList]
                })
            }
        } catch (e) {
            if (e?.errMsg?.includes('cancel')) return
            console.error('上传图片失败', e)
            wx.showToast({ title: '图片上传失败', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    removeImage(e) {
        const idx = e.currentTarget.dataset.index
        const newImages = [...this.data.form.images]
        newImages.splice(idx, 1)
        this.setData({ 'form.images': newImages })
    },

    previewImage(e) {
        const url = e.currentTarget.dataset.url
        wx.previewImage({
            urls: this.data.form.images,
            current: url
        })
    },

    handleSubmit: debounce(async function () {
        if (!this.data.canSubmit) return
        this.setData({ isLoading: true })
        try {
            const { form } = this.data
            const reward = parseFloat(form.reward_amount) || 0
            // 检查积分是否足够
            if (reward > 0 && reward > this.data.myCredits) {
                wx.showToast({ title: `积分不足，当前余额 ${this.data.myCredits}`, icon: 'none', duration: 2500 })
                return
            }
            await request.post('/api/tasks/', {
                ...form,
                reward_amount: reward.toFixed(2),
            })
            wx.showToast({ title: '发布成功！', icon: 'success' })
            // 清空表单
            this.setData({
                form: { category: '', title: '', content: '', tags: '', reward_amount: '0', latitude: null, longitude: null, location_name: '', images: [] },
                canSubmit: false,
            })
            // 跳转到首页广场
            setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 800)
        } finally {
            this.setData({ isLoading: false })
        }
    }),
})
