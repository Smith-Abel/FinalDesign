const storage = require('./utils/storage')

App({
    globalData: {
        userInfo: null,
        token: null,
    },

    onLaunch() {
        const token = storage.getToken()
        if (token) {
            this.globalData.token = token
            const userInfo = storage.getUserInfo()
            if (userInfo) this.globalData.userInfo = userInfo
        }
    },

    setToken(accessToken, refreshToken) {
        this.globalData.token = accessToken
        storage.setToken(accessToken)
        if (refreshToken) storage.setRefreshToken(refreshToken)
    },

    setUserInfo(info) {
        this.globalData.userInfo = info
        storage.setUserInfo(info)
    },

    clearAuth() {
        this.globalData.token = null
        this.globalData.userInfo = null
        storage.clearAll()
    },
})
