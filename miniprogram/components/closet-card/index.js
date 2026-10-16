const { getColorValue } = require('../../utils/constants');
Component({
  properties: {
    item: { type: Object, value: {} },
  },
  data: { swatch: '#cccccc' },
  observers: {
    'item.color': function (color) {
      this.setData({ swatch: getColorValue(color) });
    },
  },
  lifetimes: {
    attached() {
      this.setData({ swatch: getColorValue(this.data.item.color) });
    },
  },
});
