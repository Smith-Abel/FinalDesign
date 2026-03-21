// 简易精美的 Toast 提示函数
function showToast(message, type = 'error') {
    const toast = document.createElement('div');
    toast.className = `custom-toast ${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%) translateY(-20px);
        background: ${type === 'error' ? '#fde2e2' : '#e1f3d8'};
        color: ${type === 'error' ? '#f56c6c' : '#67c23a'};
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        z-index: 9999;
        opacity: 0;
        transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        display: flex;
        align-items: center;
        gap: 8px;
    `;
    
    // 图标
    const icon = document.createElement('span');
    icon.innerHTML = type === 'error' ? '⚠️' : '✅';
    toast.appendChild(icon);

    const text = document.createElement('span');
    text.textContent = message;
    toast.appendChild(text);

    document.body.appendChild(toast);

    // 动画驶入
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(-50%) translateY(0)';
        toast.style.opacity = '1';
    });

    // 3秒后驶出并移除
    setTimeout(() => {
        toast.style.transform = 'translateX(-50%) translateY(-20px)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

document.addEventListener('DOMContentLoaded', () => {
    // 若已登录，直接跳面板
    if (window.api.token && window.location.pathname.endsWith('index.html')) {
        window.location.href = 'dashboard.html';
    }

    const loginForm = document.getElementById('loginForm');
    const errorMsg = document.getElementById('loginError');
    const submitBtn = document.getElementById('submitBtn');

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            
            errorMsg.textContent = '';
            
            if (!username || !password) {
                errorMsg.textContent = '账号和密码不能为空';
                return;
            }

            submitBtn.textContent = '验证中...';
            submitBtn.disabled = true;

            try {
                const res = await window.api.login(username, password);
                // 后端 /auth/login/ 返回 { token: { access, refresh } } 结构
                const accessToken = res && res.token && res.token.access;
                if (accessToken) {
                    window.api.setToken(accessToken);
                    window.location.href = 'dashboard.html';
                } else {
                    throw new Error('账号或密码错误，或无管理员权限');
                }
            } catch (err) {
                const errMsg = err.message || '账号或密码错误或无管理员权限';
                errorMsg.textContent = errMsg;
                // 触发抖动动画
                errorMsg.classList.remove('shake');
                void errorMsg.offsetWidth;
                errorMsg.classList.add('shake');
                
                // 弹出 Toast 提示
                showToast(errMsg, 'error');
                
                // 清空密码框，防止浏览器自动回填
                const pwdInput = document.getElementById('password');
                pwdInput.value = '';
                pwdInput.focus(); // 重新聚焦，方便用户重新输入
            } finally {
                submitBtn.textContent = '登录认证';
                submitBtn.disabled = false;
            }
        });
    }
});
