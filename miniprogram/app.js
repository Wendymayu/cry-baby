// miniprogram/app.js
const { ensureLogin } = require('./utils/auth');
const { setUnauthorizedHandler } = require('./utils/request');

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

App({
  globalData: {
    baseUrl: DEFAULT_BASE_URL,
    privacyPageOpening: false,
    privacyConsentResolver: null,
    privacyAuthorizationResolvers: [],
  },
  onLaunch() {
    const stored = wx.getStorageSync('baseUrl');
    if (stored) this.globalData.baseUrl = stored;
    setUnauthorizedHandler(ensureLogin);
    if (wx.onNeedPrivacyAuthorization) {
      wx.onNeedPrivacyAuthorization(resolve => {
        this.globalData.privacyAuthorizationResolvers.push(resolve);
        if (this.globalData.privacyPageOpening) return;
        this.globalData.privacyPageOpening = true;
        wx.navigateTo({
          url: '/pages/privacy/privacy?required=1',
          fail: () => {
            const pendingResolvers = this.globalData.privacyAuthorizationResolvers || [];
            pendingResolvers.forEach(pendingResolve => pendingResolve({ event: 'disagree' }));
            this.globalData.privacyAuthorizationResolvers = [];
            this.globalData.privacyPageOpening = false;
            if (this.globalData.privacyConsentResolver) this.globalData.privacyConsentResolver(false);
          },
        });
      });
    }
  },
});
