// miniprogram/utils/api.js
const { request } = require('./request');

module.exports = {
  auth: {
    login(code) {
      return request({ url: '/api/auth/login', method: 'POST', data: { code }, needAuth: false });
    },
  },
  clothing: {
    list() { return request({ url: '/api/clothing', method: 'GET' }); },
    create({ category, color, remark }) {
      return request({ url: '/api/clothing', method: 'POST', data: { category, color, remark } });
    },
  },
};
