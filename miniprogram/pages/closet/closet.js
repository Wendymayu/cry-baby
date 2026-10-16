const api = require('../../utils/api');
const { ensureLogin } = require('../../utils/auth');

Page({
  data: { items: [], loading: false },
  onShow() { this.load(); },
  onPullDownRefresh() { this.load(() => wx.stopPullDownRefresh()); },
  load(done) {
    this.setData({ loading: true });
    ensureLogin()
      .then(() => api.clothing.list())
      .then(items => {
        this.setData({ items: items || [], loading: false });
        if (done) done();
      })
      .catch(() => {
        this.setData({ loading: false });
        wx.showToast({ title: '加载失败,请到「我的→开发调试」粘贴 token', icon: 'none', duration: 3000 });
        if (done) done();
      });
  },
  goAdd() { wx.navigateTo({ url: '/pages/clothing-edit/clothing-edit' }); },
});
