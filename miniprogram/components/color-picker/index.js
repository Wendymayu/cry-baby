const { COLORS } = require('../../utils/constants');
Component({
  properties: { value: { type: String, value: '' } },
  data: { colors: COLORS },
  methods: {
    pick(e) {
      this.triggerEvent('change', { value: e.currentTarget.dataset.key });
    },
  },
});
