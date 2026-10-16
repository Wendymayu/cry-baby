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

  // 5) 并发去重:两个 ensureLogin 同时调,只应发一次 wx.login(code 单次性、被限流)
  clearToken();
  let cap5;
  ({ captured: cap5 } = setupMockWx({
    login(opts){ opts.success({ code: 'C5' }); },
    request(opts){ opts.success({ statusCode: 200, data: { token: 'T5', user: { id: 1 } } }); },
  }));
  const [a, b] = await Promise.all([auth.ensureLogin(), auth.ensureLogin()]);
  assert.strictEqual(a, 'T5');
  assert.strictEqual(b, 'T5');
  assert.strictEqual(cap5.logins.length, 1, '并发应共享一次 wx.login,实际 ' + cap5.logins.length);

  clearMockWx();
  console.log('PASS auth');
})().catch(e => { console.error('FAIL auth', e); process.exit(1); });
