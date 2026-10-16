// miniprogram/utils/auth.js
const { getToken, setToken, clearToken } = require('./token-store');
const api = require('./api');

// 在途登录 promise:并发调用共享一次 wx.login(wx.login 的 code 单次性、被限流)。
let pending = null;

function ensureLogin() {
  const t = getToken();
  if (t) return Promise.resolve(t);
  if (pending) return pending;
  pending = new Promise((resolve, reject) => {
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
  // 清理在途标记;用 then(_,_,) 而非 finally,避免 reject 时产生无人接的 rejection。
  const release = () => { pending = null; };
  pending.then(release, release);
  return pending;
}

function loginWithManualToken(t) { setToken(t); return Promise.resolve(t); }

module.exports = { ensureLogin, loginWithManualToken, clearToken };
