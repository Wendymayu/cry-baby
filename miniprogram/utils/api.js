// miniprogram/utils/api.js
const { request } = require('./request');
const { getToken } = require('./token-store');

function resolvePhotoUrl(url) {
  if (!url) return '';
  if (/^https?:\/\//i.test(url)) return url;
  return getApp().globalData.baseUrl + url;
}

module.exports = {
  resolvePhotoUrl,
  auth: {
    deleteAccount() {
      return request({ url: '/api/auth/account', method: 'DELETE' });
    },
    login(code) {
      return request({ url: '/api/auth/login', method: 'POST', data: { code }, needAuth: false });
    },
    // 一键调试 token(本地开发态绕过 wx.login;生产配了 AppSecret 后端会返 404)
    devToken() {
      return request({ url: '/api/auth/dev_token', method: 'POST', data: {}, needAuth: false });
    },
  },
  clothing: {
    list() { return request({ url: '/api/clothing', method: 'GET' }); },
    listTrash() { return request({ url: '/api/clothing/trash', method: 'GET' }); },
    get(id) { return request({ url: `/api/clothing/${id}`, method: 'GET' }); },
    create({ category, color, remark, season_tags, occasion_tags, style_tags, material_tags }) {
      return request({ url: '/api/clothing', method: 'POST', data: { category, color, remark, season_tags, occasion_tags, style_tags, material_tags } });
    },
    update(id, { category, color, remark, season_tags, occasion_tags, style_tags, material_tags }) {
      return request({ url: `/api/clothing/${id}`, method: 'PUT', data: { category, color, remark, season_tags, occasion_tags, style_tags, material_tags } });
    },
    remove(id) { return request({ url: `/api/clothing/${id}`, method: 'DELETE' }); },
    restore(id) { return request({ url: `/api/clothing/${id}/restore`, method: 'POST' }); },
    deletePermanently(id) { return request({ url: `/api/clothing/${id}/permanent`, method: 'DELETE' }); },
    // 上传衣物图片(multipart):wx.uploadFile 不走通用 request 封装,需自带 Authorization 头。
    // 返回更新后的 item(含 photo_url)。
    uploadPhoto(itemId, filePath) {
      return new Promise((resolve, reject) => {
        const t = getToken();
        if (!t) { reject(new Error('no token')); return; }
        wx.uploadFile({
          url: getApp().globalData.baseUrl + `/api/clothing/${itemId}/photo`,
          filePath,
          name: 'file',
          header: { Authorization: 'Bearer ' + t },
          success(res) {
            if (res.statusCode >= 200 && res.statusCode < 300) {
              try { resolve(JSON.parse(res.data)); }
              catch (e) { reject(new Error('bad response')); }
            } else { reject(new Error('HTTP ' + res.statusCode)); }
          },
          fail(e) { reject(new Error((e && e.errMsg) || 'upload fail')); },
        });
      });
    },
  },
};
