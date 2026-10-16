const { CATEGORIES } = require('../../utils/constants');
Component({
  properties: { value: { type: String, value: '' } },
  data: { categories: CATEGORIES, idx: 0 },
  observers: {
    'value': function (v) {
      const i = CATEGORIES.indexOf(v);
      this.setData({ idx: i < 0 ? 0 : i });
    },
  },
  methods: {
    onChange(e) {
      const i = e.detail.value;
      const v = CATEGORIES[i];
      this.setData({ idx: i });
      this.triggerEvent('change', { value: v });
    },
  },
});
