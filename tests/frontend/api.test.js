// tests/frontend/api.test.js
const assert = require('assert');
const { setupMockWx, clearMockWx } = require('./_mock-wx');
const { setToken } = require('../../miniprogram/utils/token-store');
const api = require('../../miniprogram/utils/api');

(async () => {
  let cap;
  ({ captured: cap } = setupMockWx({
    request(opts) { opts.success({ statusCode: 200, data: { ok: 1 } }); },
  }));
  setToken('t');

  // auth.login: POST,不带 auth,body {code}
  await api.auth.login('CODE');
  assert.strictEqual(cap.requests[0].url, 'http://127.0.0.1:8000/api/auth/login');
  assert.strictEqual(cap.requests[0].method, 'POST');
  assert.deepStrictEqual(cap.requests[0].data, { code: 'CODE' });
  assert.ok(!cap.requests[0].header.Authorization);

  // clothing.list: GET,带 auth
  await api.clothing.list();
  assert.strictEqual(cap.requests[1].url, 'http://127.0.0.1:8000/api/clothing');
  assert.strictEqual(cap.requests[1].method, 'GET');
  assert.strictEqual(cap.requests[1].header.Authorization, 'Bearer t');

  // clothing.create: POST body
  await api.clothing.create({ category: '上衣', color: 'black', remark: '圆领T' });
  assert.strictEqual(cap.requests[2].method, 'POST');
  assert.deepStrictEqual(cap.requests[2].data, { category: '上衣', color: 'black', remark: '圆领T' });

  clearMockWx();
  console.log('PASS api');
})().catch(e => { console.error('FAIL api', e); process.exit(1); });
