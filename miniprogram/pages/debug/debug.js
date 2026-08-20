// 调试页:对接 backend FastAPI 三个接口,验证小程序↔后端链路
const app = getApp()

Page({
  data: {
    baseUrl: app.globalData.baseUrl,
    health: '',
    token: '',
    manualToken: '',
    clothes: ''
  },

  onLoad() {
    const t = wx.getStorageSync('token')
    if (t) this.setData({ token: t })
  },

  // 1) 连通性:GET /health(无需鉴权,游客模式也能调)
  testHealth() {
    wx.request({
      url: this.data.baseUrl + '/health',
      success: r => this.setData({ health: '✅ ' + JSON.stringify(r.data) }),
      fail: e => this.setData({ health: '❌ ' + e.errMsg })
    })
  },

  // 2) 登录:wx.login 拿 code → POST /api/auth/login 换 token
  login() {
    wx.login({
      success: ({ code }) => {
        wx.request({
          method: 'POST',
          url: this.data.baseUrl + '/api/auth/login',
          data: { code },
          success: r => {
            if (r.data.token) {
              wx.setStorageSync('token', r.data.token)
              this.setData({ token: r.data.token })
            }
            this.setData({ health: 'login: ' + JSON.stringify(r.data) })
          },
          fail: e => this.setData({ health: 'login ❌ ' + e.errMsg })
        })
      },
      fail: e => this.setData({ health: 'wx.login ❌ ' + e.errMsg })
    })
  },

  // 3) 列衣物:GET /api/clothing,带 Authorization 头
  listClothes() {
    const token = this.data.manualToken || this.data.token
    if (!token) {
      this.setData({ clothes: '❌ 无 token(先登录,或在上面粘贴手动 token)' })
      return
    }
    wx.request({
      url: this.data.baseUrl + '/api/clothing',
      header: { Authorization: 'Bearer ' + token },
      success: r => this.setData({ clothes: JSON.stringify(r.data) }),
      fail: e => this.setData({ clothes: '❌ ' + e.errMsg })
    })
  },

  onManualToken(e) {
    this.setData({ manualToken: e.detail.value })
  }
})
