const app = getApp();
Page({
  data: { baseUrl: '' },
  onShow() { this.setData({ baseUrl: app.globalData.baseUrl }); },
  onBaseUrlInput(e) { this.setData({ baseUrl: e.detail.value }); },
  saveBaseUrl() {
    const v = (this.data.baseUrl || '').trim();
    app.globalData.baseUrl = v;
    wx.setStorageSync('baseUrl', v);
    wx.showToast({ title: '已保存', icon: 'success' });
  },
  goDebug() { wx.navigateTo({ url: '/pages/debug/debug' }); },
});
