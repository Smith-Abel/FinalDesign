const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

const GENDER_OPTIONS = [
    { key: 'SECRET', label: '保密' },
    { key: 'MALE', label: '男' },
    { key: 'FEMALE', label: '女' },
]

Page({
    data: {
        user: null,
        editForm: { nickname: '', student_id: '', college: '', gender: 'SECRET' },
        genderOptions: GENDER_OPTIONS,
        genderIdx: 0,
        genderLabel: '保密',
        isSaving: false,
        showEditModal: false,
        radarData: null,
    },

    async onShow() {
        if (!app.globalData.token) {
            wx.reLaunch({ url: '/pages/login/login' })
            return
        }
        this._loadProfile()
    },

    async _loadProfile() {
        try {
            const user = await request.get('/api/auth/profile/')
            app.setUserInfo(user)
            const genderIdx = GENDER_OPTIONS.findIndex(g => g.key === user.gender)
            this.setData({
                user,
                genderIdx: Math.max(genderIdx, 0),
                genderLabel: GENDER_OPTIONS[Math.max(genderIdx, 0)].label,
                editForm: {
                    nickname: user.nickname || '',
                    student_id: user.student_id || '',
                    college: user.college || '',
                    gender: user.gender || 'SECRET',
                },
            })
            // 获取数据后重新渲染雷达图
            this._loadRadarData(user.id)
        } catch (e) {
            console.error(e)
        }
    },

    async _loadRadarData(userId) {
        try {
            const res = await request.get(`/api/users/${userId}/radar/`)
            this.setData({ radarData: res.radar })
            this.drawRadar(res.radar)
        } catch (err) {
            console.error('Failed to load radar data', err)
        }
    },

    drawRadar(radar) {
        const query = wx.createSelectorQuery()
        query.select('#radarCanvas')
            .fields({ node: true, size: true })
            .exec((res) => {
                if (!res[0] || !res[0].node) return;
                const canvas = res[0].node
                const ctx = canvas.getContext('2d')
                const dpr = wx.getSystemInfoSync().pixelRatio
                const w = res[0].width
                const h = res[0].height

                canvas.width = w * dpr
                canvas.height = h * dpr
                ctx.scale(dpr, dpr)

                const centerX = w / 2
                const centerY = h / 2 + 10
                const radius = Math.min(w, h) / 2 - 35

                const dims = [
                    { k: 'communication', n: '沟通' },
                    { k: 'attitude', n: '态度' },
                    { k: 'reliability', n: '诚信' },
                    { k: 'speed', n: '速度' },
                    { k: 'quality', n: '质量' },
                ]
                const num = dims.length
                const angles = dims.map((_, i) => (Math.PI * 2 * i / num) - Math.PI / 2)

                // 绘制底图网格 (5层)
                ctx.strokeStyle = '#ebeef5'
                ctx.fillStyle = '#fbfcfd'
                for (let level = 5; level >= 1; level--) {
                    const r = radius * (level / 5)
                    ctx.beginPath()
                    for (let i = 0; i < num; i++) {
                        const x = centerX + r * Math.cos(angles[i])
                        const y = centerY + r * Math.sin(angles[i])
                        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                    }
                    ctx.closePath()
                    ctx.fill()
                    ctx.stroke()
                }

                // 画轴线
                ctx.strokeStyle = '#ebeef5'
                for (let i = 0; i < num; i++) {
                    ctx.beginPath()
                    ctx.moveTo(centerX, centerY)
                    ctx.lineTo(centerX + radius * Math.cos(angles[i]), centerY + radius * Math.sin(angles[i]))
                    ctx.stroke()
                }

                // 画文字
                ctx.fillStyle = '#606266'
                ctx.font = '12px sans-serif'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'middle'
                for (let i = 0; i < num; i++) {
                    const val = radar[dims[i].k] || 5.0
                    let txtR = radius + 20
                    if (i === 0) txtR = radius + 15
                    const x = centerX + txtR * Math.cos(angles[i])
                    const y = centerY + txtR * Math.sin(angles[i])
                    ctx.fillText(`${dims[i].n} ${val}`, x, y)
                }

                // 画得分布区
                ctx.beginPath()
                for (let i = 0; i < num; i++) {
                    const val = radar[dims[i].k] || 5.0
                    const r = radius * (val / 5)
                    const x = centerX + r * Math.cos(angles[i])
                    const y = centerY + r * Math.sin(angles[i])
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                }
                ctx.closePath()
                ctx.fillStyle = 'rgba(103, 194, 58, 0.4)'
                ctx.fill()
                ctx.strokeStyle = '#67c23a'
                ctx.lineWidth = 2
                ctx.stroke()

                // 打点
                ctx.fillStyle = '#fff'
                for (let i = 0; i < num; i++) {
                    const val = radar[dims[i].k] || 5.0
                    const r = radius * (val / 5)
                    const x = centerX + r * Math.cos(angles[i])
                    const y = centerY + r * Math.sin(angles[i])
                    ctx.beginPath()
                    ctx.arc(x, y, 3, 0, Math.PI * 2)
                    ctx.fill()
                    ctx.stroke()
                }
            })
    },

    onInput(e) {
        const field = e.currentTarget.dataset.field
        this.setData({ [`editForm.${field}`]: e.detail.value })
    },

    onGenderChange(e) {
        const idx = e.detail.value
        const gender = GENDER_OPTIONS[idx]
        this.setData({
            genderIdx: idx,
            genderLabel: gender.label,
            'editForm.gender': gender.key,
        })
    },

    // ── 头像修改（修复 tempFilePaths 报错）──
    async changeAvatar() {
        try {
            // wx.chooseMedia 返回 tempFiles 数组，每项有 tempFilePath 属性
            const res = await new Promise((resolve, reject) =>
                wx.chooseMedia({
                    count: 1,
                    mediaType: ['image'],
                    sourceType: ['album', 'camera'],
                    success: resolve,
                    fail: reject,
                })
            )

            // 兼容两种 API：chooseMedia（tempFiles）& chooseImage（tempFilePaths）
            const filePath = res.tempFiles
                ? res.tempFiles[0].tempFilePath
                : res.tempFilePaths[0]

            wx.showLoading({ title: '上传中', mask: true })
            const url = await request.upload(filePath)
            await request.patch('/api/auth/profile/', { avatar: url })
            await this._loadProfile()
            wx.showToast({ title: '头像已更新', icon: 'success' })
        } catch (e) {
            if (e && e.errMsg && e.errMsg.includes('cancel')) return  // 用户取消不提示
            console.error('changeAvatar error:', e)
            wx.showToast({ title: '头像更新失败', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    // ── 保存资料 ──
    handleSave: debounce(async function () {
        this.setData({ isSaving: true })
        try {
            const res = await request.patch('/api/auth/profile/', this.data.editForm)
            app.setUserInfo(res)
            const wasNotRewarded = !this.data.user?.profile_reward_given
            this.setData({ user: res, showEditModal: false })
            if (res.profile_reward_given && wasNotRewarded) {
                wx.showModal({
                    title: '🎉 恭喜！',
                    content: '资料完善成功，已为你赠送 15 积分！',
                    showCancel: false,
                    confirmColor: '#67C23A',
                })
            } else {
                wx.showToast({ title: '保存成功', icon: 'success' })
            }
        } catch (e) {
            console.error(e)
        } finally {
            this.setData({ isSaving: false })
        }
    }),

    // ── 弹出编辑弹窗 ──
    editProfile() {
        this.setData({ showEditModal: true })
    },
    closeEdit() {
        this.setData({ showEditModal: false })
    },
    noop() { },  // 阻止弹窗内点击冒泡

    // ── 跳转 ──
    goToMyTasks() {
        wx.navigateTo({ url: '/pages/my-tasks/my-tasks' })
    },

    // 跳转到"我的任务"并切换到指定 tab
    goToTab(e) {
        const tab = e.currentTarget.dataset.tab
        wx.navigateTo({ url: `/pages/my-tasks/my-tasks?tab=${tab}` })
    },

    goToNotifications() {
        wx.navigateTo({ url: '/pages/notifications/notifications' })
    },

    goToVerify() {
        wx.navigateTo({ url: '/pages/verify/verify' })
    },

    goToCredits() {
        wx.navigateTo({ url: '/pages/credits/credits' })
    },

    goToMyReports() {
        wx.navigateTo({ url: '/pages/my-reports/my-reports' })
    },

    goToSettings() {
        wx.navigateTo({ url: '/pages/settings/settings' })
    },

    handleLogout() {
        wx.showModal({
            title: '退出登录',
            content: '确定要退出当前账号吗？',
            confirmColor: '#F56C6C',
            confirmText: '退出',
            success: ({ confirm }) => {
                if (!confirm) return
                app.clearAuth()
                wx.reLaunch({ url: '/pages/login/login' })
            },
        })
    },
})
