// 调试页:对接 backend FastAPI 三个接口,验证小程序↔后端链路
const { setToken } = require('../../utils/token-store')
const { loginWithManualToken } = require('../../utils/auth')
const api = require('../../utils/api')
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
              setToken(r.data.token)
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
  },

  // 应用手动 token:写入 storage,使衣橱页等正式链路也能用(游客绕过)
  applyManualToken() {
    const t = (this.data.manualToken || '').trim()
    if (!t) { wx.showToast({ title: '先粘贴 token', icon: 'none' }); return }
    loginWithManualToken(t)
    this.setData({ token: t })
    wx.showToast({ title: '已应用', icon: 'success' })
  },

  // 一键从后端获取调试 token 并应用(游客/测试 AppID 无法走 wx.login 时的绕过;
  // 走 HTTP JSON,不存在手动粘贴截断问题)
  fetchDevToken() {
    api.auth.devToken()
      .then(r => {
        if (r && r.token) {
          loginWithManualToken(r.token)
          this.setData({ token: r.token, manualToken: r.token })
          wx.showToast({ title: '已获取并应用', icon: 'success' })
        } else {
          this.setData({ health: 'dev_token: ' + JSON.stringify(r) })
        }
      })
      .catch(e => this.setData({ health: 'dev_token ❌ ' + (e.message || e) }))
  }
})
