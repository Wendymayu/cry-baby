// miniprogram/app.js
const { ensureLogin } = require('./utils/auth');
const { setUnauthorizedHandler } = require('./utils/request');

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

App({
  globalData: { baseUrl: DEFAULT_BASE_URL },
  onLaunch() {
    const stored = wx.getStorageSync('baseUrl');
    if (stored) this.globalData.baseUrl = stored;
    setUnauthorizedHandler(ensureLogin);
    ensureLogin().catch(() => {}); // 静默,失败由页面在调接口时处理
  },
});
