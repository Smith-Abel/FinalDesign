const app = getApp()

Page({
  data: {
    cacheSize: '0KB'
  },

  onShow() {
    this.calculateCache()
  },

  calculateCache() {
    try {
      const res = wx.getStorageInfoSync()
      const size = res.currentSize
      let displaySize = size + 'KB'
      if (size > 1024) {
        displaySize = (size / 1024).toFixed(2) + 'MB'
      }
      this.setData({
        cacheSize: displaySize
      })
    } catch (e) {
      console.error('获取缓存失败', e)
    }
  },

  clearCache() {
    wx.showModal({
      title: '提示',
      content: '确定要清除所有本地数据缓存吗？',
      confirmColor: '#67C23A',
      success: (res) => {
        if (res.confirm) {
          try {
            // 保留核心信息避免掉登录状态
            const storage = require('../../utils/storage')
            const token = storage.getToken()
            const refresh = storage.getRefreshToken()
            const userInfo = storage.getUserInfo()
            
            wx.clearStorageSync()
            
            if (token) storage.setToken(token)
            if (refresh) storage.setRefreshToken(refresh)
            if (userInfo) storage.setUserInfo(userInfo)
            
            wx.showToast({ title: '清理完成', icon: 'success' })
            this.calculateCache()
          } catch (e) {
            console.error('清理缓存失败', e)
          }
        }
      }
    })
  },

  showAbout() {
    wx.showModal({
      title: '关于系统',
      content: '校园互助系统致力于为大家提供一个安全、便捷的任务发布与接单平台。如遇违规信息或产品建议，可通过系统反馈。',
      showCancel: false,
      confirmColor: '#67C23A'
    })
  },

  contactUs() {
    wx.showModal({
      title: '联系我们',
      content: '客服联系方式：support@example.com\n官方微信：hu-zhu-1234',
      showCancel: false,
      confirmColor: '#67C23A'
    })
  }
})
