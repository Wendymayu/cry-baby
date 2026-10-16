// tests/frontend/token-store.test.js
const assert = require('assert');
const { setupMockWx, clearMockWx } = require('./_mock-wx');
const { getToken, setToken, clearToken } = require('../../miniprogram/utils/token-store');
setupMockWx();
assert.strictEqual(getToken(), '');
setToken('abc');
assert.strictEqual(getToken(), 'abc');
clearToken();
assert.strictEqual(getToken(), '');
clearMockWx();
console.log('PASS token-store');
