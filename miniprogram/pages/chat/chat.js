const app = getApp()
const request = require('../../utils/request')
const { debounce } = require('../../utils/debounce')

const POLL_INTERVAL = 3000  // 轮询间隔 ms

Page({
    data: {
        messages: [],
        inputText: '',
        scrollToId: '',
        keyboardHeight: 0,
        isLoading: false,
        isSending: false,
        myAvatar: '',
        myName: '',
        taskTitle: '',  // 导航栏标题
    },

    onLoad({ id, title }) {
        this.taskId = id

        // 设置导航栏标题
        if (title) {
            wx.setNavigationBarTitle({ title: decodeURIComponent(title) })
            this.setData({ taskTitle: decodeURIComponent(title) })
        }

        // 获取当前用户信息
        // 注意：app.globalData.userInfo 在冷启动直接进聊天时可能为 null
        // 因此优先从 globalData 取，若无则从本地存储读兜底
        const user = app.globalData.userInfo || wx.getStorageSync('userInfo')
        if (user) {
            this.myUserId = user.id
            this.setData({
                myAvatar: user.avatar || '',
                myName: user.username || '我',
            })
        }

        this._loadMessages()
        this._startPolling()

        // 监听键盘高度变化，让输入栏随键盘上移（不使用 adjust-position 避免双重偏移）
        wx.onKeyboardHeightChange(({ height }) => {
            this.setData({ keyboardHeight: height })
            this._scrollToBottom()
        })
    },

    onUnload() {
        this._stopPolling()
        wx.offKeyboardHeightChange()
    },

    _startPolling() {
        this._pollTimer = setInterval(() => this._loadMessages(false), POLL_INTERVAL)
    },
    _stopPolling() {
        if (this._pollTimer) clearInterval(this._pollTimer)
    },

    async _loadMessages(showLoading = true) {
        if (showLoading) this.setData({ isLoading: true })
        try {
            const res = await request.get(`/api/tasks/${this.taskId}/messages/`)
            const rawList = Array.isArray(res) ? res : (res.results || [])

            // 如果此时 myUserId 还未赋值（极少数情况），尝试再次从 globalData 取
            if (!this.myUserId) {
                const user = app.globalData.userInfo || wx.getStorageSync('userInfo')
                if (user) {
                    this.myUserId = user.id
                    this.setData({ myAvatar: user.avatar || '', myName: user.username || '我' })
                }
            }

            const msgs = rawList.map(m => ({
                ...m,
                // sender 字段已由后端序列化为用户 ID（整数）
                isMine: m.sender === this.myUserId,
                sender_name: m.sender_name || '用户',
                sender_avatar: m.sender_avatar || '',
            }))
            this.setData({ messages: msgs })
            this._scrollToBottom()
        } catch (e) {
            console.error('加载消息失败:', e)
        } finally {
            if (showLoading) this.setData({ isLoading: false })
        }
    },

    _scrollToBottom() {
        // 延迟一帧确保渲染完成后再滚动
        setTimeout(() => {
            this.setData({ scrollToId: 'msg-bottom' })
        }, 50)
    },

    onInputChange(e) {
        this.setData({ inputText: e.detail.value })
    },

    handleSend: debounce(async function () {
        const text = this.data.inputText.trim()
        if (!text || this.data.isSending) return

        this.setData({ isSending: true, inputText: '' })  // 先清空输入，提升响应感
        try {
            await request.post(`/api/tasks/${this.taskId}/messages/`, { content_text: text })
            await this._loadMessages(false)
        } catch (e) {
            // 发送失败时恢复文本，方便用户重试
            this.setData({ inputText: text })
            console.error('发送消息失败:', e)
        } finally {
            this.setData({ isSending: false })
        }
    }, 800),
})
