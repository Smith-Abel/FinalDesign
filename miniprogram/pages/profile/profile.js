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
        editForm: { student_id: '', college: '', gender: 'SECRET' },
        genderOptions: GENDER_OPTIONS,
        genderIdx: 0,
        genderLabel: '保密',
        isSaving: false,
        showEditModal: false,
    },

    onShow() {
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
                    student_id: user.student_id || '',
                    college: user.college || '',
                    gender: user.gender || 'SECRET',
                },
            })
        } catch (e) {
            console.error(e)
        }
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

    goToCredits() {
        wx.navigateTo({ url: '/pages/credits/credits' })
    },

    goToSettings() {
        wx.showToast({ title: '设置功能开发中', icon: 'none' })
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
