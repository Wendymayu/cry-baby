const api = require('../../utils/api');
const { getColorValue, getColorName } = require('../../utils/constants');

Page({
  data: { item: null, photoFull: '', swatch: '#cccccc', colorName: '未设置', tagLines: [], loading: true },

  onLoad(query) {
    const id = Number(query && query.id);
    if (!Number.isInteger(id) || id <= 0) {
      this.setData({ loading: false });
      return;
    }
    this.itemId = id;
    wx.setNavigationBarTitle({ title: '衣物详情' });
    api.clothing.get(id)
      .then(item => {
        if (!item) throw new Error('衣物不存在');
        const tagLines = [
          { label: '适用季节', values: item.season_tags || [] },
          { label: '适用场景', values: item.occasion_tags || [] },
          { label: '风格', values: item.style_tags || [] },
          { label: '材质', values: item.material_tags || [] },
        ].filter(line => line.values.length > 0).map(line => ({ label: line.label, value: line.values.join('、') }));
        if (tagLines.length === 0) tagLines.push({ label: '标签', value: '未设置' });
        this.setData({
          item,
          photoFull: item.photo_url ? getApp().globalData.baseUrl + item.photo_url : '',
          swatch: getColorValue(item.color),
          colorName: item.color ? getColorName(item.color) : '未设置',
          tagLines,
          loading: false,
        });
      })
      .catch(() => {
        this.setData({ item: null, loading: false });
      });
  },

  edit() {
    if (!this.itemId) return;
    wx.navigateTo({
      url: '/pages/clothing-edit/clothing-edit?id=' + this.itemId,
      fail: () => wx.showToast({ title: '无法打开编辑页面', icon: 'none' }),
    });
  },

  goBack() { wx.navigateBack(); },
});
