// tests/frontend/request.test.js
const assert = require('assert');
const { setupMockWx, clearMockWx } = require('./_mock-wx');
const { request, setUnauthorizedHandler } = require('../../miniprogram/utils/request');
const { setToken, clearToken } = require('../../miniprogram/utils/token-store');

(async () => {
  // 1) 成功:注入 Bearer header,resolve res.data
  let cap;
  ({ captured: cap } = setupMockWx({
    request(opts) { opts.success({ statusCode: 200, data: { ok: 1 } }); },
  }));
  setToken('tok1');
  const d = await request({ url: '/api/clothing' });
  assert.deepStrictEqual(d, { ok: 1 });
  assert.strictEqual(cap.requests[0].header.Authorization, 'Bearer tok1');
  assert.strictEqual(cap.requests[0].url, 'http://127.0.0.1:8000/api/clothing');

  // 2) 401 无 handler -> reject Unauthorized
  clearToken();
  setupMockWx({ request(opts) { opts.success({ statusCode: 401, data: {} }); } });
  setUnauthorizedHandler(null);
  await assert.rejects(() => request({ url: '/api/clothing' }), /Unauthorized/);

  // 3) 401 有 handler -> 重试一次成功
  let calls = 0;
  setupMockWx({
    request(opts) {
      calls++;
      if (calls === 1) opts.success({ statusCode: 401, data: {} });
      else opts.success({ statusCode: 200, data: { retried: 1 } });
    },
  });
  setToken('bad');
  setUnauthorizedHandler(() => { setToken('newtok'); return Promise.resolve(); });
  const d2 = await request({ url: '/api/clothing' });
  assert.deepStrictEqual(d2, { retried: 1 });

  // 4) needAuth=false 不注入 Authorization
  let cap4;
  ({ captured: cap4 } = setupMockWx({ request(opts) { opts.success({ statusCode: 200, data: {} }); } }));
  await request({ url: '/api/auth/login', method: 'POST', data: { code: 'c' }, needAuth: false });
  assert.ok(!cap4.requests[0].header.Authorization);

  clearMockWx();
  console.log('PASS request');
})().catch(e => { console.error('FAIL request', e); process.exit(1); });
