// miniprogram/utils/auth.js
const { getToken, setToken, clearToken } = require('./token-store');
const api = require('./api');

function ensureLogin() {
  const t = getToken();
  if (t) return Promise.resolve(t);
  return new Promise((resolve, reject) => {
    wx.login({
      success(loginRes) {
        api.auth.login(loginRes.code).then(data => {
          if (data && data.token) { setToken(data.token); resolve(data.token); }
          else { reject(new Error('no token')); }
        }).catch(reject);
      },
      fail(err) { reject(new Error((err && err.errMsg) || 'wx.login failed')); },
    });
  });
}

function loginWithManualToken(t) { setToken(t); return Promise.resolve(t); }

module.exports = { ensureLogin, loginWithManualToken, clearToken };
