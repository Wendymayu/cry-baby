// miniprogram/utils/auth.js
const { getToken, setToken, clearToken } = require('./token-store');
const api = require('./api');

// 在途登录 promise:并发调用共享一次 wx.login(wx.login 的 code 单次性、被限流)。
let pending = null;
let privacyPending = null;
const PRIVACY_NOTICE_VERSION = '1';

function ensurePrivacyConsent() {
  if (privacyPending) return privacyPending;
  const app = getApp();
  privacyPending = new Promise((resolve, reject) => {
    const acceptedVersion = wx.getStorageSync('privacyNoticeVersion');
    const openNotice = () => {
      app.globalData.privacyPageOpening = true;
      app.globalData.privacyConsentResolver = accepted => {
        app.globalData.privacyConsentResolver = null;
        app.globalData.privacyPageOpening = false;
        if (accepted) {
          wx.setStorageSync('privacyNoticeVersion', PRIVACY_NOTICE_VERSION);
          resolve(true);
        } else {
          const error = new Error('privacy consent declined');
          error.code = 'PRIVACY_DECLINED';
          reject(error);
        }
      };
      wx.navigateTo({
        url: '/pages/privacy/privacy?required=1',
        fail: error => {
          app.globalData.privacyConsentResolver = null;
          app.globalData.privacyPageOpening = false;
          reject(error);
        },
      });
    };

    if (wx.getPrivacySetting) {
      wx.getPrivacySetting({
        success: setting => {
          if (acceptedVersion === PRIVACY_NOTICE_VERSION && !setting.needAuthorization) resolve(true);
          else openNotice();
        },
        fail: () => {
          if (acceptedVersion === PRIVACY_NOTICE_VERSION) resolve(true);
          else openNotice();
        },
      });
    } else if (acceptedVersion === PRIVACY_NOTICE_VERSION) {
      resolve(true);
    } else {
      openNotice();
    }
  });
  const release = () => { privacyPending = null; };
  privacyPending.then(release, release);
  return privacyPending;
}

function ensureLogin() {
  if (pending) return pending;
  pending = ensurePrivacyConsent().then(() => {
    const t = getToken();
    if (t) return t;
    return new Promise((resolve, reject) => {
      wx.login({
        success(loginRes) {
          api.auth.login(loginRes.code).then(data => {
            if (data && data.token) { setToken(data.token); resolve(data.token); }
            else {
              // Tourist/preview AppIDs cannot exchange wx.login codes for an openid.
              api.auth.devToken().then(devData => {
                if (devData && devData.token) {
                  setToken(devData.token);
                  resolve(devData.token);
                } else {
                  reject(new Error('no token'));
                }
              }).catch(() => reject(new Error('login unavailable')));
            }
          }).catch(reject);
        },
        fail(err) { reject(new Error((err && err.errMsg) || 'wx.login failed')); },
      });
    });
  });
  // 清理在途标记;用 then(_,_,) 而非 finally,避免 reject 时产生无人接的 rejection。
  const release = () => { pending = null; };
  pending.then(release, release);
  return pending;
}

function loginWithManualToken(t) { setToken(t); return Promise.resolve(t); }

module.exports = { ensureLogin, loginWithManualToken, clearToken };
