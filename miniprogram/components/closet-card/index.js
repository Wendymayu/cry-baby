const { getColorValue } = require('../../utils/constants');
const { resolvePhotoUrl } = require('../../utils/api');

// 衣橱卡片:有图显图,无图回落到颜色色块。
Component({
  properties: {
    item: { type: Object, value: {} },
  },
  data: { swatch: '#cccccc', photoFull: '' },
  observers: {
    'item.color': function (color) {
      this.setData({ swatch: getColorValue(color) });
    },
    'item.photo_url': function (url) {
      this.setData({ photoFull: resolvePhotoUrl(url) });
    },
  },
  lifetimes: {
    attached() {
      const item = this.data.item || {};
      this.setData({
        swatch: getColorValue(item.color),
        photoFull: resolvePhotoUrl(item.photo_url),
      });
    },
  },
  methods: {
    onTap() {
      if (this._suppressTap) {
        this._suppressTap = false;
        return;
      }
      const id = Number(this.data.item && this.data.item.id);
      if (Number.isInteger(id) && id > 0) this.triggerEvent('select', { id });
    },
    onTouchStart(e) {
      const touch = e.touches && e.touches[0];
      this._touch = {
        startedAt: Date.now(),
        x: touch ? touch.clientX : 0,
        y: touch ? touch.clientY : 0,
        moved: false,
      };
    },
    onTouchMove(e) {
      if (!this._touch) return;
      const touch = e.touches && e.touches[0];
      if (touch && (Math.abs(touch.clientX - this._touch.x) > 16 || Math.abs(touch.clientY - this._touch.y) > 16)) {
        this._touch.moved = true;
      }
    },
    onTouchEnd() {
      const touch = this._touch;
      this._touch = null;
      if (!touch || touch.moved || Date.now() - touch.startedAt < 600) return;
      this._suppressTap = true;
      setTimeout(() => { this._suppressTap = false; }, 500);
      const id = Number(this.data.item && this.data.item.id);
      if (Number.isInteger(id) && id > 0) this.triggerEvent('actions', { id });
    },
    onTouchCancel() { this._touch = null; },
  },
});
