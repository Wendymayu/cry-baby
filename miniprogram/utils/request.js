// miniprogram/utils/request.js
const { getToken, clearToken } = require('./token-store');

let onUnauthorized = null;
function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

function request({ url, method = 'GET', data, needAuth = true }, retried = false) {
  return new Promise((resolve, reject) => {
    const baseUrl = getApp().globalData.baseUrl;
    const header = {};
    if (needAuth) {
      const t = getToken();
      if (t) header['Authorization'] = 'Bearer ' + t;
    }
    wx.request({
      url: baseUrl + url,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode === 401 && needAuth) {
          clearToken();
          // spec §7.1:重试一次仍失败则 reject。retried 守卫防止破损后端下无限循环/请求风暴。
          if (!retried && onUnauthorized) {
            onUnauthorized().then(() => {
              request({ url, method, data, needAuth }, true).then(resolve).catch(reject);
            }).catch(() => reject(new Error('Unauthorized')));
          } else {
            reject(new Error('Unauthorized'));
          }
        } else if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          const error = new Error('HTTP ' + res.statusCode);
          error.statusCode = res.statusCode;
          reject(error);
        }
      },
      fail(err) { reject(new Error((err && err.errMsg) || 'network error')); },
    });
  });
}

module.exports = { request, setUnauthorizedHandler };
