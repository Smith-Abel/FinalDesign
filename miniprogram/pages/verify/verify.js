const request = require('../../utils/request')

Page({
    data: {
        isLoading: true,
        application: null,
        form: {
            real_name: '',
            student_id_image: ''
        },
        isSubmitting: false
    },

    onShow() {
        this.fetchStatus();
    },

    async fetchStatus() {
        this.setData({ isLoading: true })
        try {
            const res = await request.get('/api/verify/')
            if (res) {
                this.setData({ application: res })
                // IF rejected, prefill real_name
                if (res.status === 'REJECTED') {
                    this.setData({ 'form.real_name': res.real_name })
                }
            } else {
                this.setData({ application: null })
            }
        } catch (e) {
            console.error('获取认证状态失败', e)
        } finally {
            this.setData({ isLoading: false })
        }
    },

    onInput(e) {
        const field = e.currentTarget.dataset.field
        this.setData({ [`form.${field}`]: e.detail.value })
    },

    async chooseImage() {
        try {
            const res = await new Promise((resolve, reject) => {
                wx.chooseMedia({
                    count: 1,
                    mediaType: ['image'],
                    sourceType: ['album', 'camera'],
                    success: resolve,
                    fail: reject,
                })
            })

            const file = res.tempFiles[0]
            if (!file) return

            wx.showLoading({ title: '上传中...' })
            const url = await request.upload(file.tempFilePath)
            if (url) {
                this.setData({ 'form.student_id_image': url })
            }
        } catch (e) {
            console.error('上传图片失败', e)
        } finally {
            wx.hideLoading()
        }
    },

    async handleSubmit() {
        const { real_name, student_id_image } = this.data.form
        if (!real_name.trim() || !student_id_image) {
            wx.showToast({ title: '请填写完整信息', icon: 'none' })
            return
        }

        this.setData({ isSubmitting: true })
        try {
            await request.post('/api/verify/', {
                real_name: real_name.trim(),
                student_id_image
            })
            wx.showToast({ title: '提交成功', icon: 'success' })
            setTimeout(() => {
                this.fetchStatus()
            }, 1000)
        } catch (e) {
            wx.showToast({ title: '提交失败了', icon: 'none' })
            console.error('提交认证失败', e)
        } finally {
            this.setData({ isSubmitting: false })
        }
    }
})
