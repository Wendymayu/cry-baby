const api = require('../../utils/api');

Page({
  data: { category: '', color: '', remark: '', saving: false },
  onCategory(e) { this.setData({ category: e.detail.value }); },
  onColor(e) { this.setData({ color: e.detail.value }); },
  onRemark(e) { this.setData({ remark: e.detail.value }); },
  save() {
    const { category, color, remark, saving } = this.data;
    if (saving) return;
    if (!category) { wx.showToast({ title: '请选择分类', icon: 'none' }); return; }
    if (!color) { wx.showToast({ title: '请选择颜色', icon: 'none' }); return; }
    this.setData({ saving: true });
    api.clothing.create({ category, color, remark })
      .then(() => { wx.showToast({ title: '已添加', icon: 'success' }); setTimeout(() => wx.navigateBack(), 600); })
      .catch(() => { wx.showToast({ title: '保存失败', icon: 'none' }); this.setData({ saving: false }); });
  },
});
