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
