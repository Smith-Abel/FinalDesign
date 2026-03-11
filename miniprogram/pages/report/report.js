const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

const REASONS = [
    { key: 'FAKE', label: '虚假信息', icon: '❌' },
    { key: 'FRAUD', label: '欺诈行为', icon: '🚫' },
    { key: 'BAD_CONTENT', label: '不良内容', icon: '⚠️' },
    { key: 'HARASSMENT', label: '骚扰', icon: '😡' },
    { key: 'OTHER', label: '其他', icon: '📝' },
]

Page({
    data: {
        reasons: REASONS,
        targetType: '',
        targetId: null,
        targetInfo: '',
        targetTypeLabel: '',
        form: {
            reason: '',
            description: '',
            images: [],
        },
        canSubmit: false,
        isLoading: false,
    },

    async onLoad({ target_type, target_id }) {
        this.setData({ targetType: target_type, targetId: target_id })
        this.setData({ targetTypeLabel: target_type === 'task' ? '🗂️ 任务' : '👤 用户' })
        // 加载被举报对象的简要信息
        await this._loadTargetInfo(target_type, target_id)
        wx.setNavigationBarTitle({ title: '举报' })
    },

    async _loadTargetInfo(type, id) {
        try {
            if (type === 'task') {
                const res = await request.get(`/api/tasks/${id}/`)
                this.setData({ targetInfo: res.title })
            }
        } catch (e) { /* 找不到时忽略 */ }
    },

    onReasonSelect(e) {
        const key = e.currentTarget.dataset.key
        this.setData({ 'form.reason': key })
        this._check()
    },

    onDescInput(e) {
        this.setData({ 'form.description': e.detail.value })
    },

    _check() {
        this.setData({ canSubmit: !!this.data.form.reason })
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
            if (!files.length) return
            wx.showLoading({ title: '上传中...', mask: true })
            const urlList = []
            for (const f of files) {
                const url = await request.upload(f.tempFilePath)
                if (url) urlList.push(url)
            }
            if (urlList.length) {
                this.setData({ 'form.images': [...this.data.form.images, ...urlList] })
            }
        } catch (e) {
            if (e?.errMsg?.includes('cancel')) return
            wx.showToast({ title: '图片上传失败', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    removeImage(e) {
        const idx = e.currentTarget.dataset.index
        const imgs = [...this.data.form.images]
        imgs.splice(idx, 1)
        this.setData({ 'form.images': imgs })
    },

    previewImage(e) {
        wx.previewImage({ urls: this.data.form.images, current: e.currentTarget.dataset.url })
    },

    handleSubmit: debounce(async function () {
        if (!this.data.canSubmit) return
        this.setData({ isLoading: true })
        try {
            const { targetType, targetId, form } = this.data
            await request.post('/api/reports/', {
                target_type: targetType,
                target_id: Number(targetId),
                reason: form.reason,
                description: form.description,
                images: form.images,
            })
            wx.showToast({
                title: '举报已提交',
                icon: 'success',
                duration: 1200,
                complete: () => wx.navigateBack(),
            })
        } catch (e) {
            // request.js 中已统一 showToast，这里无需重复处理
        } finally {
            this.setData({ isLoading: false })
        }
    }),
})
