/**
 * 防抖工厂函数
 * 冷却期内重复调用直接忽略，防止按钮连点导致重复请求
 * @param {Function} fn    原始函数
 * @param {number}   delay 冷却时间（ms），默认 1500
 */
function debounce(fn, delay = 1500) {
    let timer = null
    return function (...args) {
        if (timer) return
        timer = setTimeout(() => { timer = null }, delay)
        return fn.apply(this, args)
    }
}

module.exports = { debounce }
