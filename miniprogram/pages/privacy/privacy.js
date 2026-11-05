const PRIVACY_NOTICE_VERSION = '2';
const PRIVACY_CONTACT_EMAIL = 'jasmin_lv@163.com';

Page({
  data: {
    required: false,
    privacyContractName: '微信小程序用户隐私保护指引',
    contactEmail: PRIVACY_CONTACT_EMAIL,
    resolving: false,
  },

  onLoad(query) {
    const app = getApp();
    app.globalData.privacyPageOpening = true;
    this.setData({ required: !!(query && query.required === '1') });
    if (wx.getPrivacySetting) {
      wx.getPrivacySetting({
        success: result => {
          this.setData({
            privacyContractName: result.privacyContractName || '微信小程序用户隐私保护指引',
            required: this.data.required || !!result.needAuthorization,
          });
        },
      });
    }
  },

  openPrivacyContract() {
    if (!wx.openPrivacyContract) {
      wx.showToast({ title: '请在微信小程序后台查看隐私指引', icon: 'none' });
      return;
    }
    wx.openPrivacyContract({
      fail: () => wx.showToast({ title: '暂时无法打开微信隐私指引', icon: 'none' }),
    });
  },

  copyContactEmail() {
    wx.setClipboardData({
      data: this.data.contactEmail,
      success: () => wx.showToast({ title: '邮箱已复制', icon: 'success' }),
    });
  },

  agreePrivacyAuthorization() {
    if (this.data.resolving) return;
    this.setData({ resolving: true });
    wx.setStorageSync('privacyNoticeVersion', PRIVACY_NOTICE_VERSION);
    const app = getApp();
    const platformResolvers = app.globalData.privacyAuthorizationResolvers || [];
    platformResolvers.forEach(resolve => resolve({ event: 'agree', buttonId: 'privacy-agree' }));
    app.globalData.privacyAuthorizationResolvers = [];
    const consentResolver = app.globalData.privacyConsentResolver;
    app.globalData.privacyConsentResolver = null;
    if (consentResolver) consentResolver(true);
    app.globalData.privacyPageOpening = false;
    this._resolved = true;
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/closet/closet' }) });
  },

  declinePrivacyAuthorization() {
    if (this.data.resolving) return;
    this.setData({ resolving: true });
    const app = getApp();
    const platformResolvers = app.globalData.privacyAuthorizationResolvers || [];
    platformResolvers.forEach(resolve => resolve({ event: 'disagree' }));
    app.globalData.privacyAuthorizationResolvers = [];
    const consentResolver = app.globalData.privacyConsentResolver;
    app.globalData.privacyConsentResolver = null;
    if (consentResolver) consentResolver(false);
    app.globalData.privacyPageOpening = false;
    this._resolved = true;
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/closet/closet' }) });
  },

  onUnload() {
    const app = getApp();
    app.globalData.privacyPageOpening = false;
    if (this._resolved) return;
    const platformResolvers = app.globalData.privacyAuthorizationResolvers || [];
    platformResolvers.forEach(resolve => resolve({ event: 'disagree' }));
    app.globalData.privacyAuthorizationResolvers = [];
    const consentResolver = app.globalData.privacyConsentResolver;
    app.globalData.privacyConsentResolver = null;
    if (consentResolver) consentResolver(false);
  },
});
