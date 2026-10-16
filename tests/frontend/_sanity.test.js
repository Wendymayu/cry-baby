// tests/frontend/_sanity.test.js
const assert = require('assert');
const { setupMockWx, clearMockWx } = require('./_mock-wx');
const { captured } = setupMockWx({ request(opts){ opts.success({statusCode:200,data:{ok:1}}); } });
wx.request({ url: 'x', success(r){ assert.strictEqual(r.data.ok, 1); } });
assert.strictEqual(captured.requests.length, 1);
assert.strictEqual(getApp().globalData.baseUrl, 'http://127.0.0.1:8000');
clearMockWx();
console.log('PASS sanity');
