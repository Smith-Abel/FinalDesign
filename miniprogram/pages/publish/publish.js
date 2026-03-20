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
            target_college: '',
            title: '',
            content: '',
            tags: '',
            reward_amount: '0',
            images: [],
        },
        collegeOptions: ['不限', '计算机学院', '经济管理学院', '机械工程学院', '电气工程学院', '理学院', '外国语学院', '建筑与设计学院'],
        collegeIndex: 0,
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
    },

    onInput(e) {
        const field = e.currentTarget.dataset.field
        this.setData({ [`form.${field}`]: e.detail.value })
    },

    onCollegeChange(e) {
        const val = e.detail.value;
        const target_college = val == 0 ? '' : this.data.collegeOptions[val];
        this.setData({
            collegeIndex: val,
            'form.target_college': target_college
        });
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
        const { category, title, content, images } = this.data.form
        const isComplete = !!(category && title.trim() && content.trim() && images && images.length > 0)

        if (!isComplete) {
            wx.showModal({
                title: '提示',
                content: '请填完分类、标题、内容与图片（至少一张）才能发布哦！',
                showCancel: false,
                confirmText: '我知道了',
                confirmColor: '#67C23A',
            })
            return
        }

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
            // 清空表单
            this.setData({
                form: { category: '', target_college: '', title: '', content: '', tags: '', reward_amount: '0', images: [] },
                collegeIndex: 0,
            })
            wx.showToast({
                title: '发布成功！',
                icon: 'success',
                duration: 900,
                complete: () => wx.switchTab({ url: '/pages/index/index' }),
            })
        } finally {
            this.setData({ isLoading: false })
        }
    }),
})
