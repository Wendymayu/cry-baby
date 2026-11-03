const api = require('../../utils/api');
const { ensureLogin } = require('../../utils/auth');
const { CATEGORIES, getColorValue } = require('../../utils/constants');
const app = getApp();

function buildRows(items, activeCategory) {
  const visibleItems = activeCategory === '全部'
    ? items
    : items.filter(item => item.category === activeCategory);
  return visibleItems.map(item => ({
    key: 'item:' + item.id,
    item: Object.assign({}, item, {
      photoFull: item.photo_url ? app.globalData.baseUrl + item.photo_url : '',
      swatch: getColorValue(item.color),
    }),
  }));
}

Page({
  data: { items: [], rows: [], filterOptions: [], activeCategory: '全部', loading: false, loadError: false },
  onShow() { this.load(); },
  onPullDownRefresh() { this.load(() => wx.stopPullDownRefresh()); },
  load(done) {
    this.setData({ loading: true, loadError: false });
    ensureLogin()
      .then(() => api.clothing.list())
      .then(items => {
        const list = items || [];
        const categoryOptions = CATEGORIES.slice();
        list.forEach(item => {
          if (categoryOptions.indexOf(item.category) < 0) categoryOptions.push(item.category);
        });
        let activeCategory = this.data.activeCategory;
        if (activeCategory !== '全部' && categoryOptions.indexOf(activeCategory) < 0) {
          activeCategory = '全部';
        }
        const filterOptions = ['全部'].concat(categoryOptions).map(name => ({
          name,
          selected: name === activeCategory,
        }));
        this.setData({
          items: list,
          activeCategory,
          rows: buildRows(list, activeCategory),
          filterOptions,
          loading: false,
          loadError: false,
        });
        if (typeof done === 'function') done();
      })
      .catch(() => {
        this.setData({ loading: false, loadError: true });
        wx.showToast({ title: '加载失败，请检查网络后重试', icon: 'none', duration: 2500 });
        if (typeof done === 'function') done();
      });
  },
  selectCategory(e) {
    const category = e.currentTarget.dataset.category;
    if (!category || category === this.data.activeCategory) return;
    const filterOptions = this.data.filterOptions.map(option => ({
      name: option.name,
      selected: option.name === category,
    }));
    this.setData({
      activeCategory: category,
      filterOptions,
      rows: buildRows(this.data.items, category),
    });
  },
  goAdd() {
    wx.navigateTo({
      url: '/pages/clothing-edit/clothing-edit',
      fail: () => wx.showToast({ title: '无法打开添加衣物页面', icon: 'none' }),
    });
  },
  goDetail(e) {
    if (this._suppressNextTap) {
      this._suppressNextTap = false;
      return;
    }
    const itemId = Number(e.currentTarget.dataset.id);
    if (!Number.isInteger(itemId) || itemId <= 0) return;
    wx.navigateTo({
      url: '/pages/clothing-detail/clothing-detail?id=' + itemId,
      fail: () => wx.showToast({ title: '无法打开衣物详情', icon: 'none' }),
    });
  },
  onItemTouchStart(e) {
    const touch = e.touches && e.touches[0];
    this._itemTouch = {
      id: Number(e.currentTarget.dataset.id),
      startedAt: Date.now(),
      x: touch ? touch.clientX : 0,
      y: touch ? touch.clientY : 0,
      moved: false,
    };
  },
  onItemTouchMove(e) {
    if (!this._itemTouch) return;
    const touch = e.touches && e.touches[0];
    if (touch && (Math.abs(touch.clientX - this._itemTouch.x) > 16 || Math.abs(touch.clientY - this._itemTouch.y) > 16)) {
      this._itemTouch.moved = true;
    }
  },
  onItemTouchEnd() {
    const gesture = this._itemTouch;
    this._itemTouch = null;
    if (!gesture || gesture.moved || !Number.isInteger(gesture.id) || gesture.id <= 0) return;
    if (Date.now() - gesture.startedAt >= 600) {
      this._suppressNextTap = true;
      setTimeout(() => { this._suppressNextTap = false; }, 500);
      this.showItemActions(gesture.id);
    }
  },
  onItemTouchCancel() { this._itemTouch = null; },
  showItemActions(itemId) {
    wx.showActionSheet({
      itemList: ['编辑衣物', '删除衣物'],
      itemColor: '#5a4a3a',
      success: result => {
        if (result.tapIndex === 0) {
          wx.navigateTo({ url: '/pages/clothing-edit/clothing-edit?id=' + itemId });
          return;
        }
        if (result.tapIndex === 1) this.confirmDelete(itemId);
      },
    });
  },
  confirmDelete(itemId) {
    wx.showModal({
      title: '删除衣物',
      content: '确定删除这件衣物？删除后不可恢复。',
      confirmText: '删除',
      confirmColor: '#d93025',
      success: result => {
        if (!result.confirm) return;
        api.clothing.remove(itemId)
          .then(() => {
            wx.showToast({ title: '已删除', icon: 'success' });
            this.load();
          })
          .catch(() => wx.showToast({ title: '删除失败，请重试', icon: 'none' }));
      },
    });
  },
});
