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
                errorMsg.textContent = err.message || '账号或密码错误或无管理员权限';
            } finally {
                submitBtn.textContent = '登录认证';
                submitBtn.disabled = false;
            }
        });
    }
});
