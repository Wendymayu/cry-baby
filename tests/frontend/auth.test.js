// tests/frontend/auth.test.js
const assert = require('assert');
const { setupMockWx, clearMockWx } = require('./_mock-wx');
const { setToken, clearToken } = require('../../miniprogram/utils/token-store');
const auth = require('../../miniprogram/utils/auth');

(async () => {
  // 1) 已有 token -> 直接 resolve,不调 wx.login
  setupMockWx({ login(opts){ opts.success({ code: 'should-not-call' }); } });
  setToken('existing');
  const t = await auth.ensureLogin();
  assert.strictEqual(t, 'existing');
  clearToken();

  // 2) 无 token -> wx.login + api.login 成功 -> setToken
  setupMockWx({
    login(opts){ opts.success({ code: 'CODE123' }); },
    request(opts){ opts.success({ statusCode: 200, data: { token: 'TOK', user: { id: 1 } } }); },
  });
  const t2 = await auth.ensureLogin();
  assert.strictEqual(t2, 'TOK');

  // 3) api 返回无 token -> reject (no token)
  clearToken();
  setupMockWx({
    login(opts){ opts.success({ code: 'C' }); },
    request(opts){ opts.success({ statusCode: 200, data: { error: 'no openid' } }); },
  });
  await assert.rejects(() => auth.ensureLogin(), /no token/);

  // 4) loginWithManualToken
  clearToken();
  auth.loginWithManualToken('manual');
  assert.strictEqual(require('../../miniprogram/utils/token-store').getToken(), 'manual');

  clearMockWx();
  console.log('PASS auth');
})().catch(e => { console.error('FAIL auth', e); process.exit(1); });
