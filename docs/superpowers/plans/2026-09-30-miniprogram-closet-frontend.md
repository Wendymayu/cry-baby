# 微信小程序衣橱前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为通用生活助手小程序实现衣橱管理第一阶段:静默登录 + 衣物网格列表 + 新建衣物 + 三 tab 框架(对话占位)。

**Architecture:** 原生小程序,基于现有 `miniprogram/` scaffold。新增 utils 层(request/api/auth/token-store/constants)封装网络与登录,3 个自定义组件(closet-card/category-picker/color-picker),4 个页面(closet/clothing-edit/chat/profile)+ 保留 debug。莫兰迪暖中性视觉风格。

**Tech Stack:** 微信小程序原生(WXML/WXSS/JS,CommonJS)、Node 内置 assert(仅用于 utils 单测,不引入测试框架)。

**关键约定:**
- 后端 baseUrl 默认 `http://127.0.0.1:8000`,从 `app.js globalData.baseUrl` 取。
- `category` 存中文分类名,`color` 存颜色 key(如 `black`),读取时按 `constants` 反查色值。
- 纯逻辑层(utils)用 TDD,测试放 `tests/frontend/`,用 `node tests/frontend/xxx.test.js` 运行;页面/组件层用微信开发者工具手动验证。

---

## File Structure

```
miniprogram/
  app.js                      # 改:onLaunch 恢复 baseUrl + ensureLogin + 注入 401 handler
  app.json                    # 改:注册 pages + tabBar(衣橱/对话/我的)
  app.wxss                    # 改:莫兰迪色板 + 全局基础样式
  utils/
    constants.js              # 新:预设分类、颜色 + 反查函数
    token-store.js            # 新:token storage 存取(纯 wx storage)
    request.js                # 新:wx.request Promise 封装 + 401 重试
    auth.js                   # 新:静默登录 + 手动 token 绕过
    api.js                    # 新:auth/clothing 接口
  components/
    closet-card/index.{js,wxml,wxss,json}
    category-picker/index.{js,wxml,wxss,json}
    color-picker/index.{js,wxml,wxss,json}
  pages/
    closet/closet.{js,wxml,wxss,json}
    clothing-edit/clothing-edit.{js,wxml,wxss,json}
    chat/chat.{js,wxml,wxss,json}
    profile/profile.{js,wxml,wxss,json}
    debug/debug.{js,wxml,wxss,json}   # 保留微调
tests/frontend/
  _mock-wx.js                 # mock global.wx / global.getApp
  constants.test.js
  token-store.test.js
  request.test.js
  auth.test.js
  api.test.js
```

依赖方向(无循环):`auth → api → request → token-store`;`request` 的 401 handler 由 `app.js` 注入(= `auth.ensureLogin`),不在 request 内 import auth。

---

### Task 1: 测试基建与 wx mock

**Files:**
- Create: `tests/frontend/_mock-wx.js`
- Create: `tests/frontend/_sanity.test.js`

- [ ] **Step 1: 写 _mock-wx.js**

```js
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
```

- [ ] **Step 2: 写 sanity 测试**

```js
// tests/frontend/_sanity.test.js
const assert = require('assert');
const { setupMockWx, clearMockWx } = require('./_mock-wx');
const { captured } = setupMockWx({ request(opts){ opts.success({statusCode:200,data:{ok:1}}); } });
wx.request({ url: 'x', success(r){ assert.strictEqual(r.data.ok, 1); } });
assert.strictEqual(captured.requests.length, 1);
assert.strictEqual(getApp().globalData.baseUrl, 'http://127.0.0.1:8000');
clearMockWx();
console.log('PASS sanity');
```

- [ ] **Step 3: 运行**

Run: `node tests/frontend/_sanity.test.js`
Expected: 输出 `PASS sanity`

- [ ] **Step 4: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add tests/frontend/_mock-wx.js tests/frontend/_sanity.test.js
git -C "d:/code/opensource/github/cry-baby" commit -m "test(frontend): add wx mock harness and sanity test"
```

---

### Task 2: utils/constants.js — 预设分类与颜色

**Files:**
- Create: `miniprogram/utils/constants.js`
- Test: `tests/frontend/constants.test.js`

- [ ] **Step 1: 写失败测试**

```js
// tests/frontend/constants.test.js
const assert = require('assert');
const { CATEGORIES, COLORS, getColorValue, getColorName } = require('../../miniprogram/utils/constants');
assert.strictEqual(CATEGORIES.length, 7);
assert.strictEqual(CATEGORIES[0], '上衣');
assert.strictEqual(getColorValue('black'), '#222222');
assert.strictEqual(getColorValue('white'), '#ffffff');
assert.ok(getColorValue('multicolor').indexOf('linear-gradient') === 0);
assert.strictEqual(getColorName('blue'), '蓝');
assert.strictEqual(getColorValue('nonexist'), '#cccccc');
console.log('PASS constants');
```

- [ ] **Step 2: 运行验证失败**

Run: `node tests/frontend/constants.test.js`
Expected: FAIL — `Cannot find module '../../miniprogram/utils/constants'`

- [ ] **Step 3: 写实现**

```js
// miniprogram/utils/constants.js
const CATEGORIES = ['上衣', '外套', '衬衫', '裤子', '裙装', '鞋', '配饰'];

const COLORS = [
  { key: 'black',  name: '黑',  value: '#222222' },
  { key: 'white',  name: '白',  value: '#ffffff' },
  { key: 'gray',   name: '灰',  value: '#9ca3af' },
  { key: 'red',    name: '红',  value: '#dc2626' },
  { key: 'blue',   name: '蓝',  value: '#3b82f6' },
  { key: 'green',  name: '绿',  value: '#16a34a' },
  { key: 'yellow', name: '黄',  value: '#eab308' },
  { key: 'brown',  name: '棕',  value: '#a16207' },
  { key: 'pink',   name: '粉',  value: '#ec4899' },
  { key: 'multicolor', name: '花色', value: 'linear-gradient(135deg,#f87171,#fbbf24,#34d399,#60a5fa,#a78bfa)' },
];

function getColorValue(key) {
  const c = COLORS.find(x => x.key === key);
  return c ? c.value : '#cccccc';
}
function getColorName(key) {
  const c = COLORS.find(x => x.key === key);
  return c ? c.name : key;
}

module.exports = { CATEGORIES, COLORS, getColorValue, getColorName };
```

- [ ] **Step 4: 运行验证通过**

Run: `node tests/frontend/constants.test.js`
Expected: `PASS constants`

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/utils/constants.js tests/frontend/constants.test.js
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add constants (categories/colors)"
```

---

### Task 3: utils/token-store.js — token 存取

**Files:**
- Create: `miniprogram/utils/token-store.js`
- Test: `tests/frontend/token-store.test.js`

- [ ] **Step 1: 写失败测试**

```js
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
```

- [ ] **Step 2: 运行验证失败**

Run: `node tests/frontend/token-store.test.js`
Expected: FAIL — module not found

- [ ] **Step 3: 写实现**

```js
// miniprogram/utils/token-store.js
const KEY = 'token';
function getToken() { return wx.getStorageSync(KEY) || ''; }
function setToken(t) { wx.setStorageSync(KEY, t); }
function clearToken() { wx.removeStorageSync(KEY); }
module.exports = { getToken, setToken, clearToken };
```

- [ ] **Step 4: 运行验证通过**

Run: `node tests/frontend/token-store.test.js`
Expected: `PASS token-store`

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/utils/token-store.js tests/frontend/token-store.test.js
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add token-store"
```

---

### Task 4: utils/request.js — wx.request 封装 + 401 重试

**Files:**
- Create: `miniprogram/utils/request.js`
- Test: `tests/frontend/request.test.js`

- [ ] **Step 1: 写失败测试**

```js
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
```

- [ ] **Step 2: 运行验证失败**

Run: `node tests/frontend/request.test.js`
Expected: FAIL — module not found

- [ ] **Step 3: 写实现**

```js
// miniprogram/utils/request.js
const { getToken, clearToken } = require('./token-store');

let onUnauthorized = null;
function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

function request({ url, method = 'GET', data, needAuth = true }) {
  return new Promise((resolve, reject) => {
    const baseUrl = getApp().globalData.baseUrl;
    const header = {};
    if (needAuth) {
      const t = getToken();
      if (t) header['Authorization'] = 'Bearer ' + t;
    }
    wx.request({
      url: baseUrl + url,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode === 401 && needAuth) {
          clearToken();
          if (onUnauthorized) {
            onUnauthorized().then(() => {
              request({ url, method, data, needAuth }).then(resolve).catch(reject);
            }).catch(() => reject(new Error('Unauthorized')));
          } else {
            reject(new Error('Unauthorized'));
          }
        } else if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject(new Error('HTTP ' + res.statusCode));
        }
      },
      fail(err) { reject(new Error((err && err.errMsg) || 'network error')); },
    });
  });
}

module.exports = { request, setUnauthorizedHandler };
```

- [ ] **Step 4: 运行验证通过**

Run: `node tests/frontend/request.test.js`
Expected: `PASS request`

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/utils/request.js tests/frontend/request.test.js
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add request wrapper with 401 retry"
```

---

### Task 5: utils/api.js — auth/clothing 接口

**Files:**
- Create: `miniprogram/utils/api.js`
- Test: `tests/frontend/api.test.js`

- [ ] **Step 1: 写失败测试**

```js
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
```

- [ ] **Step 2: 运行验证失败**

Run: `node tests/frontend/api.test.js`
Expected: FAIL — module not found

- [ ] **Step 3: 写实现**

```js
// miniprogram/utils/api.js
const { request } = require('./request');

module.exports = {
  auth: {
    login(code) {
      return request({ url: '/api/auth/login', method: 'POST', data: { code }, needAuth: false });
    },
  },
  clothing: {
    list() { return request({ url: '/api/clothing', method: 'GET' }); },
    create({ category, color, remark }) {
      return request({ url: '/api/clothing', method: 'POST', data: { category, color, remark } });
    },
  },
};
```

- [ ] **Step 4: 运行验证通过**

Run: `node tests/frontend/api.test.js`
Expected: `PASS api`

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/utils/api.js tests/frontend/api.test.js
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add api wrappers (auth/clothing)"
```

---

### Task 6: utils/auth.js — 静默登录 + 手动 token

**Files:**
- Create: `miniprogram/utils/auth.js`
- Test: `tests/frontend/auth.test.js`

- [ ] **Step 1: 写失败测试**

```js
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
```

- [ ] **Step 2: 运行验证失败**

Run: `node tests/frontend/auth.test.js`
Expected: FAIL — module not found

- [ ] **Step 3: 写实现**

```js
// miniprogram/utils/auth.js
const { getToken, setToken, clearToken } = require('./token-store');
const api = require('./api');

function ensureLogin() {
  const t = getToken();
  if (t) return Promise.resolve(t);
  return new Promise((resolve, reject) => {
    wx.login({
      success(loginRes) {
        api.auth.login(loginRes.code).then(data => {
          if (data && data.token) { setToken(data.token); resolve(data.token); }
          else { reject(new Error('no token')); }
        }).catch(reject);
      },
      fail(err) { reject(new Error((err && err.errMsg) || 'wx.login failed')); },
    });
  });
}

function loginWithManualToken(t) { setToken(t); return Promise.resolve(t); }

module.exports = { ensureLogin, loginWithManualToken, clearToken };
```

- [ ] **Step 4: 运行验证通过**

Run: `node tests/frontend/auth.test.js`
Expected: `PASS auth`

- [ ] **Step 5: 跑全部 utils 测试**

Run: `for f in tests/frontend/*.test.js; do node "$f" || exit 1; done`
Expected: 全部 PASS(constants / token-store / request / api / auth / sanity)

- [ ] **Step 6: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/utils/auth.js tests/frontend/auth.test.js
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add silent login + manual token"
```

---

### Task 7: 全局 app.js / app.json / app.wxss

**Files:**
- Modify: `miniprogram/app.js`
- Modify: `miniprogram/app.json`
- Modify: `miniprogram/app.wxss`

- [ ] **Step 1: 改 app.js**

```js
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
```

- [ ] **Step 2: 改 app.json**

```json
{
  "pages": [
    "pages/closet/closet",
    "pages/clothing-edit/clothing-edit",
    "pages/chat/chat",
    "pages/profile/profile",
    "pages/debug/debug"
  ],
  "window": {
    "navigationBarBackgroundColor": "#ffffff",
    "navigationBarTitleText": "衣橱",
    "navigationBarTextStyle": "black",
    "backgroundColor": "#faf8f5"
  },
  "tabBar": {
    "color": "#a89a8a",
    "selectedColor": "#a68a64",
    "backgroundColor": "#ffffff",
    "borderStyle": "white",
    "list": [
      { "pagePath": "pages/closet/closet", "text": "衣橱" },
      { "pagePath": "pages/chat/chat", "text": "对话" },
      { "pagePath": "pages/profile/profile", "text": "我的" }
    ]
  },
  "sitemapLocation": "sitemap.json"
}
```

> 注:tabBar 本期用纯文字(无图标)。微信开发者工具对无图标 tabBar 通常可正常运行;若报错需图标,后续补 81x81 图标并填 iconPath/selectedIconPath。

- [ ] **Step 3: 改 app.wxss**

```css
/* miniprogram/app.wxss — 莫兰迪暖中性 */
/* primary #a68a64 | text #5a4a3a | bg #faf8f5 | card #fff | card-border #f0ece6 | text-secondary #a89a8a */
page {
  background: #faf8f5;
  color: #5a4a3a;
  font-size: 28rpx;
  font-family: -apple-system, "PingFang SC", "Helvetica Neue", sans-serif;
}
.btn-primary {
  background: #a68a64;
  color: #ffffff;
  border-radius: 12rpx;
  padding: 20rpx 0;
  text-align: center;
}
.btn-primary[disabled] { opacity: 0.5; }
.card {
  background: #ffffff;
  border: 1rpx solid #f0ece6;
  border-radius: 16rpx;
}
.subtitle { color: #a89a8a; font-size: 24rpx; }
```

- [ ] **Step 4: 开发者工具手动验证**

打开微信开发者工具加载 `miniprogram/`(编译会因 pages 目录文件还不存在报错,属正常,本步只验证 app.json 语法与 tabBar 配色无拼写错误)。重点看控制台无 `app.json` 解析错误;tabBar 字段颜色为莫兰迪值。
Expected: 控制台可能提示页面缺失,但 `app.json` 本身无 JSON 语法错误。

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/app.js miniprogram/app.json miniprogram/app.wxss
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): wire app global (login, tabBar, palette)"
```

---

### Task 8: components/closet-card

**Files:**
- Create: `miniprogram/components/closet-card/index.{js,wxml,wxss,json}`

- [ ] **Step 1: index.json**

```json
{ "component": true }
```

- [ ] **Step 2: index.js**

```js
const { getColorValue } = require('../../utils/constants');
Component({
  properties: {
    item: { type: Object, value: {} },
  },
  data: { swatch: '#cccccc' },
  observers: {
    'item.color': function (color) {
      this.setData({ swatch: getColorValue(color) });
    },
  },
  lifetimes: {
    attached() {
      this.setData({ swatch: getColorValue(this.data.item.color) });
    },
  },
});
```

- [ ] **Step 3: index.wxml**

```xml
<view class="card closet-card">
  <view class="swatch" style="background: {{swatch}};"></view>
  <view class="meta">
    <view class="cat">{{item.category}}</view>
    <view class="remark" wx:if="{{item.remark}}">{{item.remark}}</view>
  </view>
</view>
```

- [ ] **Step 4: index.wxss**

```css
.closet-card { overflow: hidden; }
.swatch { height: 180rpx; border-bottom: 1rpx solid #f0ece6; }
.meta { padding: 12rpx 16rpx; }
.cat { font-size: 28rpx; font-weight: 500; }
.remark { font-size: 22rpx; color: #a89a8a; margin-top: 4rpx; }
```

- [ ] **Step 5: 开发者工具验证**

在 closet 页(下个 task 建)引用前,本步确保组件文件无语法错误:开发者工具编译,组件文件不报错即可(组件未被引用不会触发渲染)。
Expected: 编译无 `closet-card` 组件脚本错误。

- [ ] **Step 6: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/components/closet-card/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add closet-card component"
```

---

### Task 9: components/category-picker

**Files:**
- Create: `miniprogram/components/category-picker/index.{js,wxml,wxss,json}`

- [ ] **Step 1: index.json**

```json
{ "component": true }
```

- [ ] **Step 2: index.js**

```js
const { CATEGORIES } = require('../../utils/constants');
Component({
  properties: { value: { type: String, value: '' } },
  data: { categories: CATEGORIES, idx: 0 },
  observers: {
    'value': function (v) {
      const i = CATEGORIES.indexOf(v);
      this.setData({ idx: i < 0 ? 0 : i });
    },
  },
  methods: {
    onChange(e) {
      const i = e.detail.value;
      const v = CATEGORIES[i];
      this.setData({ idx: i });
      this.triggerEvent('change', { value: v });
    },
  },
});
```

- [ ] **Step 3: index.wxml**

```xml
<picker mode="selector" range="{{categories}}" value="{{idx}}" bindchange="onChange">
  <view class="picker-row">
    <text wx:if="{{value}}">{{value}}</text>
    <text wx:else class="placeholder">请选择分类</text>
  </view>
</picker>
```

- [ ] **Step 4: index.wxss**

```css
.picker-row {
  padding: 20rpx;
  background: #fff;
  border: 1rpx solid #f0ece6;
  border-radius: 12rpx;
}
.placeholder { color: #a89a8a; }
```

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/components/category-picker/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add category-picker component"
```

---

### Task 10: components/color-picker

**Files:**
- Create: `miniprogram/components/color-picker/index.{js,wxml,wxss,json}`

- [ ] **Step 1: index.json**

```json
{ "component": true }
```

- [ ] **Step 2: index.js**

```js
const { COLORS } = require('../../utils/constants');
Component({
  properties: { value: { type: String, value: '' } },
  data: { colors: COLORS },
  methods: {
    pick(e) {
      this.triggerEvent('change', { value: e.currentTarget.dataset.key });
    },
  },
});
```

- [ ] **Step 3: index.wxml**

```xml
<view class="colors">
  <view wx:for="{{colors}}" wx:key="key"
        class="color-item {{value === item.key ? 'selected' : ''}}"
        bindtap="pick" data-key="{{item.key}}">
    <view class="swatch" style="background: {{item.value}};"></view>
    <text class="name">{{item.name}}</text>
  </view>
</view>
```

- [ ] **Step 4: index.wxss**

```css
.colors { display: flex; flex-wrap: wrap; gap: 16rpx; }
.color-item { width: 120rpx; text-align: center; }
.swatch {
  width: 100rpx; height: 100rpx; margin: 0 auto 8rpx;
  border-radius: 50%; border: 4rpx solid transparent;
}
.color-item.selected .swatch { border-color: #a68a64; }
.name { font-size: 22rpx; color: #5a4a3a; }
```

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/components/color-picker/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add color-picker component"
```

---

### Task 11: pages/closet — 衣橱首页

**Files:**
- Create: `miniprogram/pages/closet/closet.{js,wxml,wxss,json}`

- [ ] **Step 1: closet.json**

```json
{
  "navigationBarTitleText": "衣橱",
  "enablePullDownRefresh": true,
  "usingComponents": {
    "closet-card": "/components/closet-card/index"
  }
}
```

- [ ] **Step 2: closet.js**

```js
const api = require('../../utils/api');
const { ensureLogin } = require('../../utils/auth');

Page({
  data: { items: [], loading: false },
  onShow() { this.load(); },
  onPullDownRefresh() { this.load(() => wx.stopPullDownRefresh()); },
  load(done) {
    this.setData({ loading: true });
    ensureLogin()
      .then(() => api.clothing.list())
      .then(items => {
        this.setData({ items: items || [], loading: false });
        if (done) done();
      })
      .catch(() => {
        this.setData({ loading: false });
        wx.showToast({ title: '加载失败,请到「我的→开发调试」粘贴 token', icon: 'none', duration: 3000 });
        if (done) done();
      });
  },
  goAdd() { wx.navigateTo({ url: '/pages/clothing-edit/clothing-edit' }); },
});
```

- [ ] **Step 3: closet.wxml**

```xml
<view class="page">
  <view class="grid" wx:if="{{items.length}}">
    <view wx:for="{{items}}" wx:key="id" class="cell">
      <closet-card item="{{item}}"></closet-card>
    </view>
  </view>
  <view class="empty" wx:elif="{{!loading}}">
    <text class="subtitle">衣橱还是空的</text>
    <button class="btn-primary add-btn" bindtap="goAdd">添加第一件</button>
  </view>
  <view class="fab" bindtap="goAdd">+</view>
</view>
```

- [ ] **Step 4: closet.wxss**

```css
.page { padding: 16rpx; padding-bottom: 120rpx; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 24rpx; padding-top: 200rpx; }
.add-btn { width: 320rpx; margin-top: 16rpx; }
.fab {
  position: fixed; right: 32rpx; bottom: 140rpx;
  width: 96rpx; height: 96rpx; border-radius: 50%;
  background: #a68a64; color: #fff; font-size: 56rpx;
  text-align: center; line-height: 96rpx;
  box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.25);
}
```

- [ ] **Step 5: 开发者工具手动验证**

后端先起:`uvicorn fastapi_app.main:app --reload --port 8000`(在 `backend/`)。开发者工具编译,衣橱 tab 应显示空状态(因游客模式登录失败)。控制台可见 401/登录失败提示。
Expected: 衣橱页显示「衣橱还是空 + 添加第一件」按钮;浮动「+」可见;控制台有登录失败信息(游客模式预期)。

- [ ] **Step 6: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/pages/closet/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add closet page (grid + fab + refresh)"
```

---

### Task 12: pages/clothing-edit — 新建衣物

**Files:**
- Create: `miniprogram/pages/clothing-edit/clothing-edit.{js,wxml,wxss,json}`

- [ ] **Step 1: clothing-edit.json**

```json
{
  "navigationBarTitleText": "添加衣物",
  "usingComponents": {
    "category-picker": "/components/category-picker/index",
    "color-picker": "/components/color-picker/index"
  }
}
```

- [ ] **Step 2: clothing-edit.js**

```js
const api = require('../../utils/api');

Page({
  data: { category: '', color: '', remark: '', saving: false },
  onCategory(e) { this.setData({ category: e.detail.value }); },
  onColor(e) { this.setData({ color: e.detail.value }); },
  onRemark(e) { this.setData({ remark: e.detail.value }); },
  save() {
    const { category, color, remark, saving } = this.data;
    if (saving) return;
    if (!category) { wx.showToast({ title: '请选择分类', icon: 'none' }); return; }
    if (!color) { wx.showToast({ title: '请选择颜色', icon: 'none' }); return; }
    this.setData({ saving: true });
    api.clothing.create({ category, color, remark })
      .then(() => { wx.showToast({ title: '已添加', icon: 'success' }); setTimeout(() => wx.navigateBack(), 600); })
      .catch(() => { wx.showToast({ title: '保存失败', icon: 'none' }); this.setData({ saving: false }); });
  },
});
```

- [ ] **Step 3: clothing-edit.wxml**

```xml
<view class="page">
  <view class="field">
    <view class="label">分类</view>
    <category-picker value="{{category}}" bind:change="onCategory"></category-picker>
  </view>
  <view class="field">
    <view class="label">颜色</view>
    <color-picker value="{{color}}" bind:change="onColor"></color-picker>
  </view>
  <view class="field">
    <view class="label">备注（可选）</view>
    <textarea class="remark" value="{{remark}}" bindinput="onRemark" placeholder="如：圆领T、牛仔" maxlength="50"></textarea>
  </view>
  <button class="btn-primary save-btn" bindtap="save" disabled="{{saving}}">{{saving ? '保存中…' : '保存'}}</button>
</view>
```

- [ ] **Step 4: clothing-edit.wxss**

```css
.page { padding: 24rpx; }
.field { margin-bottom: 32rpx; }
.label { font-size: 26rpx; color: #a89a8a; margin-bottom: 12rpx; }
.remark {
  width: 100%; min-height: 120rpx; padding: 20rpx; box-sizing: border-box;
  background: #fff; border: 1rpx solid #f0ece6; border-radius: 12rpx;
}
.save-btn { margin-top: 48rpx; }
```

- [ ] **Step 5: 开发者工具手动验证**

从衣橱页点「+」进入新建页。选分类、选颜色、填备注、点保存。游客模式下会失败(无 token),先去 debug 页粘贴 token(Task 15)再回来保存,或本步仅验证表单交互(选中有高亮、保存按钮禁用态)。
Expected: 分类 picker 可展开选择;颜色选中加边框;未选时保存提示「请选择分类/颜色」。

- [ ] **Step 6: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/pages/clothing-edit/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add clothing-edit page"
```

---

### Task 13: pages/chat — 对话占位

**Files:**
- Create: `miniprogram/pages/chat/chat.{js,wxml,wxss,json}`

- [ ] **Step 1: chat.json**

```json
{ "navigationBarTitleText": "对话" }
```

- [ ] **Step 2: chat.js**

```js
Page({});
```

- [ ] **Step 3: chat.wxml**

```xml
<view class="page">
  <view class="placeholder-box">
    <view class="title">对话功能即将上线</view>
    <view class="desc">后续将接入智能穿搭建议与生活助手对话，敬请期待。</view>
  </view>
</view>
```

- [ ] **Step 4: chat.wxss**

```css
.page { padding: 40rpx; }
.placeholder-box {
  margin-top: 200rpx; padding: 48rpx; text-align: center;
  background: #fff; border: 1rpx solid #f0ece6; border-radius: 16rpx;
}
.title { font-size: 32rpx; font-weight: 600; margin-bottom: 16rpx; }
.desc { font-size: 26rpx; color: #a89a8a; line-height: 1.6; }
```

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/pages/chat/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add chat placeholder page"
```

---

### Task 14: pages/profile — 我的

**Files:**
- Create: `miniprogram/pages/profile/profile.{js,wxml,wxss,json}`

- [ ] **Step 1: profile.json**

```json
{ "navigationBarTitleText": "我的" }
```

- [ ] **Step 2: profile.js**

```js
const app = getApp();
Page({
  data: { baseUrl: '' },
  onShow() { this.setData({ baseUrl: app.globalData.baseUrl }); },
  onBaseUrlInput(e) { this.setData({ baseUrl: e.detail.value }); },
  saveBaseUrl() {
    const v = (this.data.baseUrl || '').trim();
    app.globalData.baseUrl = v;
    wx.setStorageSync('baseUrl', v);
    wx.showToast({ title: '已保存', icon: 'success' });
  },
  goDebug() { wx.navigateTo({ url: '/pages/debug/debug' }); },
});
```

- [ ] **Step 3: profile.wxml**

```xml
<view class="page">
  <view class="field">
    <view class="label">后端地址</view>
    <input class="input" value="{{baseUrl}}" bindinput="onBaseUrlInput" placeholder="http://127.0.0.1:8000"></input>
    <button class="btn-primary save" bindtap="saveBaseUrl">保存</button>
  </view>
  <view class="row" bindtap="goDebug">
    <text>开发调试</text>
    <text class="arrow">›</text>
  </view>
  <view class="row about">
    <text>通用生活助手 · 衣橱管理 v0.1</text>
  </view>
</view>
```

- [ ] **Step 4: profile.wxss**

```css
.page { padding: 24rpx; }
.field { background: #fff; border: 1rpx solid #f0ece6; border-radius: 16rpx; padding: 24rpx; margin-bottom: 24rpx; }
.label { font-size: 26rpx; color: #a89a8a; margin-bottom: 12rpx; }
.input { padding: 16rpx; background: #faf8f5; border-radius: 8rpx; margin-bottom: 16rpx; }
.save { width: 200rpx; }
.row {
  display: flex; justify-content: space-between; align-items: center;
  background: #fff; border: 1rpx solid #f0ece6; border-radius: 16rpx;
  padding: 28rpx 24rpx; margin-bottom: 16rpx;
}
.arrow { color: #a89a8a; }
.about { justify-content: center; color: #a89a8a; font-size: 24rpx; }
```

- [ ] **Step 5: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/pages/profile/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): add profile page (baseUrl/debug/about)"
```

---

### Task 15: pages/debug — 加「应用手动 token」绕过入口

现有 `debug.js` 登录分支已用 `wx.setStorageSync('token', ...)`,与 token-store 的 key `'token'` 相同,登录链路天然兼容。但手动 token(`manualToken`)只在 `listClothes` 时临时读取,不写 storage,所以衣橱页(走 `getToken()`)拿不到。本 task 加一个「应用手动 token」按钮,把手动 token 写入 storage,使正式页也能绕过。

**Files:**
- Modify: `miniprogram/pages/debug/debug.js`(顶部加 require,新增 `applyManualToken` 方法)
- Modify: `miniprogram/pages/debug/debug.wxml`(手动 token 输入框后加按钮)

- [ ] **Step 1: 改 debug.js 顶部加 require**

在文件第 1 行注释 `// 调试页...` 之后、`const app = getApp()` 之前,插入:

```js
const { setToken } = require('../../utils/token-store')
const { loginWithManualToken } = require('../../utils/auth')
```

- [ ] **Step 2: 改 debug.js 登录分支统一用 setToken**

把 `login()` 里的 `wx.setStorageSync('token', r.data.token)`(约 line 37)替换为:

```js
              setToken(r.data.token)
```

- [ ] **Step 3: 在 debug.js 的 `onManualToken` 方法后新增 `applyManualToken`**

在 `onManualToken(e) { this.setData({ manualToken: e.detail.value }) }` 之后、Page 对象结束的 `}` 之前,插入:

```js
,
  // 应用手动 token:写入 storage,使衣橱页等正式链路也能用(游客绕过)
  applyManualToken() {
    const t = (this.data.manualToken || '').trim()
    if (!t) { wx.showToast({ title: '先粘贴 token', icon: 'none' }); return }
    loginWithManualToken(t)
    this.setData({ token: t })
    wx.showToast({ title: '已应用', icon: 'success' })
  }
```

- [ ] **Step 4: 改 debug.wxml 加按钮**

在手动 token `<input>`(约 line 11)之后、`<button ... listClothes>`(line 13)之前,插入:

```xml
  <button type="primary" bindtap="applyManualToken">应用手动 token(写入 storage)</button>
```

- [ ] **Step 5: 开发者工具验证**

从「我的→开发调试」进入 debug 页。粘贴后端 `make_token` 造的 JWT 到手动 token 输入框,点「应用手动 token」→ toast「已应用」→ 返回衣橱 tab 下拉刷新,应能加载衣物列表(若 token 有效)。
Expected: 衣橱页从空/加载失败变为正常列出衣物。

- [ ] **Step 6: Commit**

```bash
git -C "d:/code/opensource/github/cry-baby" add miniprogram/pages/debug/
git -C "d:/code/opensource/github/cry-baby" commit -m "feat(miniprogram): debug apply-manual-token writes to storage"
```

---

### Task 16: 端到端验证

**Files:** 无(仅验证)

- [ ] **Step 1: 跑全部 utils 单测**

Run: `for f in tests/frontend/*.test.js; do node "$f" || exit 1; done`
Expected: 全部 PASS。

- [ ] **Step 2: 起后端**

在 `backend/` 跑:`uvicorn fastapi_app.main:app --reload --port 8000`
Expected: 监听 8000,`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`。

- [ ] **Step 3: 游客模式端到端(手动 token 绕过)**

1. 微信开发者工具加载 `miniprogram/`(AppID 保持 touristappid)。
2. 后端用 `make_token` 造一个 JWT(参考 `backend/fastapi_app/auth.py` 的 `make_token`)。
3. 小程序「我的→开发调试」粘贴该 token,点应用。
4. 回衣橱 tab:应空(无衣物)。
5. 点「+」新建:选分类、颜色、备注、保存 → toast「已添加」→ 返回衣橱应出现该卡片(色块为所选颜色)。
6. 下拉刷新正常。
Expected: 衣物出现在网格,色块颜色与所选一致,备注显示。

- [ ] **Step 4: (可选)真机真 AppID 端到端**

把真 AppID 填入 `project.config.json`,AppSecret 填入 `backend/.env`,真机预览。冷启动静默登录无感,直接走 Step 3 的 4-6。
Expected: 无需手动 token,衣橱链路自动跑通。

- [ ] **Step 5: 收尾 commit(若有遗留改动)**

```bash
git -C "d:/code/opensource/github/cry-baby" status
# 若有未提交改动:
git -C "d:/code/opensource/github/cry-baby" add -A && git -C "d:/code/opensource/github/cry-baby" commit -m "chore(miniprogram): e2e verification tweaks"
```

---

## Self-Review(执行者参照,确认 spec 覆盖)

- 登录链路(静默 + 绕过):Task 6 + Task 7 + Task 15 ✓
- 衣物列表(网格):Task 11 + Task 8 ✓
- 新建衣物:Task 12 + Task 9 + Task 10 ✓
- 三 tab 框架:Task 7(app.json tabBar)+ Task 11/13/14 ✓
- 对话占位:Task 13 ✓
- 我的页:Task 14 ✓
- 网络层封装:Task 3/4/5/6 ✓
- 莫兰迪色板:Task 7(app.wxss)+ 各组件/页面 wxss ✓
- 预设分类/颜色:Task 2 + Task 9/10 ✓
- 验证方式:Task 16 ✓
- 不本次做(对话/删改/照片):均无对应实现 task ✓(占位在 Task 13)
