// miniprogram/utils/token-store.js
const KEY = 'token';
function getToken() { return wx.getStorageSync(KEY) || ''; }
function setToken(t) { wx.setStorageSync(KEY, t); }
function clearToken() { wx.removeStorageSync(KEY); }
module.exports = { getToken, setToken, clearToken };
