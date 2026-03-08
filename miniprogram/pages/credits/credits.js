const app = getApp()
const request = require('../../utils/request')

function formatTime(dateStr) {
    const d = new Date(dateStr)
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

Page({
    data: {
        totalCredits: 0,
        profileRewarded: false,
        firstHelpRewarded: false,
        records: [],
        isLoading: false,
    },

    onLoad() {
        this._loadData()
    },

    onShow() {
        this._loadData()
    },

    async _loadData() {
        this.setData({ isLoading: true })
        try {
            const [profile, credits] = await Promise.all([
                request.get('/api/auth/profile/'),
                request.get('/api/credits/'),
            ])
            const list = (Array.isArray(credits) ? credits : (credits.results || [])).map(r => ({
                ...r,
                icon: r.change_amount > 0 ? '🟢' : '🔴',
                timeStr: formatTime(r.created_at),
            }))
            this.setData({
                totalCredits: profile.credit_score,
                profileRewarded: profile.profile_reward_given,
                firstHelpRewarded: profile.first_help_rewarded,
                records: list,
            })
        } catch (e) {
            console.error(e)
        } finally {
            this.setData({ isLoading: false })
        }
    },
})
