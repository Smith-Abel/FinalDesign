const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

Page({
    data: {
        isLoading: false,
        activeMode: '',        // 'wx' | 'account' | 'register'
        showAccountForm: false,
        formMode: 'login',     // 'login' | 'register'
        form: {
            username: '',
            student_id: '',
            password: '',
            password2: '',
        },
    },

    onLoad() {
        if (app.globalData.token) {
            wx.switchTab({ url: '/pages/index/index' })
        }
    },

    onShow() {
        if (app.globalData.token) {
            wx.switchTab({ url: '/pages/index/index' })
        }
    },

    // ── 展开/收起账号表单 ──
    toggleAccountForm() {
        this.setData({ showAccountForm: !this.data.showAccountForm })
    },

    // ── 切换登录/注册 Tab ──
    switchFormMode(e) {
        const mode = e.currentTarget.dataset.mode
        this.setData({ formMode: mode })
    },

    // ── 表单输入 ──
    onInput(e) {
        const field = e.currentTarget.dataset.field
        this.setData({ [`form.${field}`]: e.detail.value })
    },

    // ── 微信一键登录 ──
    handleWxLogin: debounce(async function () {
        this.setData({ isLoading: true, activeMode: 'wx' })
        try {
            const { code } = await new Promise((resolve, reject) =>
                wx.login({ success: resolve, fail: reject })
            )
            const res = await request.post('/api/auth/wx-login/', { code })
            app.setToken(res.token.access, res.token.refresh)
            app.setUserInfo(res.user)

            if (res.is_new_user && res.register_bonus) {
                wx.showToast({
                    title: `欢迎！获得 ${res.register_bonus} 初始积分 🎉`,
                    icon: 'none', duration: 3000,
                })
                await new Promise(r => setTimeout(r, 1000))
            }
            wx.switchTab({ url: '/pages/index/index' })
        } catch (err) {
            console.error('wx login failed', err)
        } finally {
            this.setData({ isLoading: false, activeMode: '' })
        }
    }, 2000),

    // ── 账号密码登录 ──
    handleAccountLogin: debounce(async function () {
        const { username, password } = this.data.form
        if (!username.trim()) {
            wx.showToast({ title: '请输入用户名', icon: 'none' }); return
        }
        if (!password) {
            wx.showToast({ title: '请输入密码', icon: 'none' }); return
        }
        this.setData({ isLoading: true, activeMode: 'account' })
        try {
            const res = await request.post('/api/auth/login/', { username: username.trim(), password })
            app.setToken(res.token.access, res.token.refresh)
            app.setUserInfo(res.user)
            wx.switchTab({ url: '/pages/index/index' })
        } catch (err) {
            console.error('account login failed', err)
        } finally {
            this.setData({ isLoading: false, activeMode: '' })
        }
    }, 1500),

    // ── 注册 ──
    handleRegister: debounce(async function () {
        const { username, student_id, password, password2 } = this.data.form
        if (!username.trim() || username.trim().length < 2) {
            wx.showToast({ title: '用户名至少2个字符', icon: 'none' }); return
        }
        if (!password || password.length < 6) {
            wx.showToast({ title: '密码至少6位', icon: 'none' }); return
        }
        if (password !== password2) {
            wx.showToast({ title: '两次密码不一致', icon: 'none' }); return
        }
        this.setData({ isLoading: true, activeMode: 'register' })
        try {
            const payload = {
                username: username.trim(),
                password,
                password2,
            }
            if (student_id.trim()) payload.student_id = student_id.trim()

            const res = await request.post('/api/auth/register/', payload)
            app.setToken(res.token.access, res.token.refresh)
            app.setUserInfo(res.user)
            wx.showToast({ title: `注册成功 🎉`, icon: 'success' })
            await new Promise(r => setTimeout(r, 1200))
            wx.switchTab({ url: '/pages/index/index' })
        } catch (err) {
            console.error('register failed', err)
        } finally {
            this.setData({ isLoading: false, activeMode: '' })
        }
    }, 1500),
})
