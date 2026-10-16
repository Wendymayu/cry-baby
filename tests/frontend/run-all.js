// tests/frontend/run-all.js — 跑全部 utils 单测,任一失败非零退出
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const dir = __dirname;
const files = fs.readdirSync(dir).filter(f => f.endsWith('.test.js'));
let ok = true;
for (const f of files) {
  try {
    execFileSync(process.execPath, [path.join(dir, f)], { stdio: 'inherit' });
  } catch (e) { ok = false; }
}
if (!ok) process.exit(1);
console.log('ALL FRONTEND TESTS PASS (' + files.length + ')');
