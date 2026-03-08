const KEYS = {
    TOKEN: 'access_token',
    REFRESH_TOKEN: 'refresh_token',
    USER_INFO: 'user_info',
}

const storage = {
    getToken: () => wx.getStorageSync(KEYS.TOKEN) || '',
    setToken: (v) => wx.setStorageSync(KEYS.TOKEN, v),

    getRefreshToken: () => wx.getStorageSync(KEYS.REFRESH_TOKEN) || '',
    setRefreshToken: (v) => wx.setStorageSync(KEYS.REFRESH_TOKEN, v),

    getUserInfo: () => wx.getStorageSync(KEYS.USER_INFO) || null,
    setUserInfo: (v) => wx.setStorageSync(KEYS.USER_INFO, v),

    clearAll() {
        Object.values(KEYS).forEach(k => wx.removeStorageSync(k))
    },
}

module.exports = storage
