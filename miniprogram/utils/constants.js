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
