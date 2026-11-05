const api = require('../../utils/api');
const { clearToken } = require('../../utils/token-store');
const { ensureLogin } = require('../../utils/auth');
const app = getApp();
Page({
  data: { baseUrl: '', deletingAccount: false },
  onShow() { this.setData({ baseUrl: app.globalData.baseUrl }); },
  onBaseUrlInput(e) { this.setData({ baseUrl: e.detail.value }); },
  saveBaseUrl() {
    const v = (this.data.baseUrl || '').trim();
    app.globalData.baseUrl = v;
    wx.setStorageSync('baseUrl', v);
    wx.showToast({ title: '已保存', icon: 'success' });
  },
  goTrash() {
    wx.navigateTo({
      url: '/pages/trash/trash',
      fail: () => wx.showToast({ title: '无法打开回收站', icon: 'none' }),
    });
  },
  goDebug() { wx.navigateTo({ url: '/pages/debug/debug' }); },
  openPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' });
  },
  deleteAccount() {
    if (this.data.deletingAccount) return;
    wx.showModal({
      title: '删除账号和全部数据',
      content: '将删除账号标识、全部衣物信息和已上传的照片，且无法恢复。确定继续吗？',
      confirmText: '删除全部数据',
      confirmColor: '#d93025',
      success: result => {
        if (!result.confirm) return;
        this.setData({ deletingAccount: true });
        ensureLogin().then(() => api.auth.deleteAccount())
          .then(() => {
            clearToken();
            wx.showToast({ title: '账号和数据已删除', icon: 'success' });
          })
          .catch(() => wx.showToast({ title: '删除失败，请稍后重试', icon: 'none' }))
          .then(() => this.setData({ deletingAccount: false }));
      },
    });
  },
});
