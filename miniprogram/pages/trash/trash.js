const api = require('../../utils/api');
const { ensureLogin } = require('../../utils/auth');
const { getColorValue, getColorName } = require('../../utils/constants');

const DAY_MS = 24 * 60 * 60 * 1000;

function presentItem(item) {
  const expiresAt = Date.parse(item.expires_at);
  const remainingDays = Math.max(1, Math.ceil((expiresAt - Date.now()) / DAY_MS));
  return Object.assign({}, item, {
    photoFull: api.resolvePhotoUrl(item.photo_url),
    swatch: getColorValue(item.color),
    colorName: item.color ? getColorName(item.color) : '未设置颜色',
    remainingDays,
    expiryText: remainingDays === 1 ? '今天到期' : `还剩 ${remainingDays} 天`,
  });
}

Page({
  data: { items: [], loading: false, loadError: false, busyId: 0 },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(() => wx.stopPullDownRefresh()); },

  load(done) {
    this.setData({ loading: true, loadError: false });
    ensureLogin()
      .then(() => api.clothing.listTrash())
      .then(items => this.setData({ items: (items || []).map(presentItem), loading: false }))
      .catch(() => {
        this.setData({ loading: false, loadError: true });
        wx.showToast({ title: '回收站加载失败，请重试', icon: 'none' });
      })
      .then(() => { if (typeof done === 'function') done(); });
  },

  restore(e) {
    const id = Number(e.currentTarget.dataset.id);
    if (!id || this.data.busyId) return;
    this.setData({ busyId: id });
    api.clothing.restore(id)
      .then(() => {
        this.setData({ items: this.data.items.filter(item => item.id !== id), busyId: 0 });
        wx.showToast({ title: '已恢复到衣橱', icon: 'success' });
      })
      .catch(error => {
        this.setData({ busyId: 0 });
        wx.showToast({
          title: error && error.statusCode === 410 ? '已超过保留期限，无法恢复' : '恢复失败，请重试',
          icon: 'none',
        });
        this.load();
      });
  },

  confirmPermanentDelete(e) {
    const id = Number(e.currentTarget.dataset.id);
    if (!id || this.data.busyId) return;
    const item = this.data.items.find(row => row.id === id);
    wx.showModal({
      title: '彻底删除衣物',
      content: `彻底删除“${item ? item.category : '这件衣物'}”及其照片后将无法恢复，确定删除吗？`,
      confirmText: '彻底删除',
      confirmColor: '#b34f43',
      success: result => {
        if (!result.confirm) return;
        this.setData({ busyId: id });
        api.clothing.deletePermanently(id)
          .then(() => {
            this.setData({ items: this.data.items.filter(row => row.id !== id), busyId: 0 });
            wx.showToast({ title: '已彻底删除', icon: 'success' });
          })
          .catch(() => {
            this.setData({ busyId: 0 });
            wx.showToast({ title: '删除失败，请重试', icon: 'none' });
          });
      },
    });
  },
});
