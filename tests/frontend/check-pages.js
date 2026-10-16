// tests/frontend/check-pages.js — 页面/组件层静态校验(node --check + JSON.parse)
// spec §12 豁免页面层自动化行为测试;本脚本做语法/结构校验作为提交前门禁。
const { readFileSync, readdirSync, statSync } = require('fs');
const { join } = require('path');
const { execFileSync } = require('child_process');

const root = join(__dirname, '..', '..', 'miniprogram');
let failures = 0;

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p);
    else if (name.endsWith('.js')) {
      try {
        execFileSync(process.execPath, ['--check', p], { stdio: 'pipe' });
        console.log('JS ok  ' + p);
      } catch (e) {
        failures++;
        console.error('JS FAIL ' + p + '\n' + (e.stderr ? e.stderr.toString() : e.message));
      }
    } else if (name.endsWith('.json')) {
      try {
        JSON.parse(readFileSync(p, 'utf8'));
        console.log('JSON ok ' + p);
      } catch (e) {
        failures++;
        console.error('JSON FAIL ' + p + ' — ' + e.message);
      }
    }
  }
}

walk(root);
if (failures) { console.error(failures + ' static check failures'); process.exit(1); }
console.log('STATIC CHECKS PASS');
