const storage = require('./storage')

const BASE_URL = 'http://localhost:8000'

/**
 * 统一 HTTP 请求封装
 * - 自动注入 Bearer token
 * - 401 统一跳登录页
 * - 非 2xx 自动 Toast 错误提示
 */
function request(url, method, data, showError = true) {
    return new Promise((resolve, reject) => {
        const token = storage.getToken()
        const header = { 'Content-Type': 'application/json' }
        if (token) header['Authorization'] = `Bearer ${token}`

        wx.request({
            url: `${BASE_URL}${url}`,
            method,
            data,
            header,
            success(res) {
                if (res.statusCode === 401) {
                    storage.clearAll()
                    wx.reLaunch({ url: '/pages/login/login' })
                    reject(new Error('登录已过期，请重新登录'))
                    return
                }
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(res.data)
                    return
                }
                const msg = res.data?.detail || `请求失败 (${res.statusCode})`
                if (showError) wx.showToast({ title: msg, icon: 'none', duration: 2500 })
                reject(new Error(msg))
            },
            fail(err) {
                const msg = '网络连接失败，请检查网络'
                if (showError) wx.showToast({ title: msg, icon: 'none' })
                reject(err)
            },
        })
    })
}

/**
 * 上传图片（multipart/form-data）
 */
function uploadImage(filePath) {
    return new Promise((resolve, reject) => {
        const token = storage.getToken()
        wx.uploadFile({
            url: `${BASE_URL}/api/upload/image/`,
            filePath,
            name: 'image',
            header: token ? { Authorization: `Bearer ${token}` } : {},
            success(res) {
                const data = JSON.parse(res.data)
                if (res.statusCode === 201) {
                    resolve(data.url)
                } else {
                    wx.showToast({ title: data?.detail || '上传失败', icon: 'none' })
                    reject(new Error('upload failed'))
                }
            },
            fail() {
                wx.showToast({ title: '上传失败，请重试', icon: 'none' })
                reject(new Error('upload failed'))
            },
        })
    })
}

module.exports = {
    get: (url, data) => request(url, 'GET', data),
    post: (url, data) => request(url, 'POST', data),
    patch: (url, data) => request(url, 'PATCH', data),
    delete: (url) => request(url, 'DELETE', {}),
    upload: uploadImage,
}
