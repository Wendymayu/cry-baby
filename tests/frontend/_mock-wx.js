// tests/frontend/_mock-wx.js
// 在 Node 里模拟小程序全局 wx 与 getApp,供 utils 单测用。
function setupMockWx(overrides = {}) {
  const storage = {};
  const captured = { requests: [], logins: [] };
  global.wx = {
    setStorageSync: (k, v) => { storage[k] = v; },
    getStorageSync: (k) => storage[k],
    removeStorageSync: (k) => { delete storage[k]; },
    request: (opts) => {
      captured.requests.push(opts);
      if (overrides.request) overrides.request(opts);
    },
    login: (opts) => {
      captured.logins.push(opts);
      if (overrides.login) overrides.login(opts);
    },
  };
  global.getApp = () => ({
    globalData: { baseUrl: overrides.baseUrl || 'http://127.0.0.1:8000' },
  });
  return { captured, storage };
}
function clearMockWx() {
  delete global.wx;
  delete global.getApp;
}
module.exports = { setupMockWx, clearMockWx };
