#!/usr/bin/env node
/**
 * カード管理 自動セットアップスクリプト
 *
 * 使い方:
 *   node setup.js
 */

'use strict';

const { execSync } = require('child_process');
const fs   = require('fs');
const path = require('path');

const ROOT          = __dirname;
const CODE_GS       = path.join(ROOT, 'Code.gs');
const MANIFEST_JSON = path.join(ROOT, 'appsscript.json');
const HTML_FILE     = path.join(ROOT, 'index.html');
const WORK_DIR      = path.join(ROOT, '.setup-work');
const CLASP_JSON    = path.join(WORK_DIR, '.clasp.json');

function run(cmd, opts = {})     { execSync(cmd, { stdio: 'inherit', cwd: WORK_DIR, ...opts }); }
function capture(cmd, opts = {}) { return execSync(cmd, { encoding: 'utf8', cwd: WORK_DIR, ...opts }).trim(); }
function step(n, t, msg)  { console.log(`\n[${n}/${t}] ${msg}`); }
function ok(msg)  { console.log(`  ✓ ${msg}`); }
function info(msg){ console.log(`  → ${msg}`); }
function fail(msg){ console.error(`  ✗ ${msg}`); }

async function main() {
  console.log('================================================');
  console.log('  カード管理 自動セットアップ');
  console.log('================================================');

  const TOTAL = 5;

  // Step 1: clasp 確認
  step(1, TOTAL, 'clasp の確認');
  try {
    const v = capture('clasp --version', { cwd: ROOT });
    ok(`clasp ${v}`);
  } catch (_) {
    info('clasp をインストールしています...');
    execSync('npm install -g @google/clasp', { stdio: 'inherit' });
    ok('clasp をインストールしました');
  }

  // Step 2: Google ログイン
  step(2, TOTAL, 'Google アカウントへのログイン');
  info('ブラウザが開きます。Googleアカウントでログインしてください。');
  run('clasp login', { cwd: ROOT });
  ok('ログイン完了');

  // Step 3: プロジェクト作成
  step(3, TOTAL, 'Google Spreadsheet と Apps Script プロジェクトの作成');

  if (fs.existsSync(WORK_DIR)) fs.rmSync(WORK_DIR, { recursive: true });
  fs.mkdirSync(WORK_DIR);
  fs.copyFileSync(CODE_GS, path.join(WORK_DIR, 'Code.gs'));
  fs.copyFileSync(MANIFEST_JSON, path.join(WORK_DIR, 'appsscript.json'));

  const createOut = capture('clasp create --type sheets --title "カード管理" --rootDir .');
  console.log(createOut);

  const claspConfig = JSON.parse(fs.readFileSync(CLASP_JSON, 'utf8'));
  ok(`Apps Script プロジェクト作成完了 (ID: ${claspConfig.scriptId})`);

  const ssMatch = createOut.match(/Created new Google Sheet: (.+)/);
  if (ssMatch) ok(`スプレッドシート: ${ssMatch[1].trim()}`);

  // Step 4: コードをプッシュ & デプロイ
  step(4, TOTAL, 'コードのアップロードとデプロイ');

  info('コードをアップロードしています...');
  run('clasp push --force');
  ok('アップロード完了');

  info('ウェブアプリとしてデプロイしています...');
  const deployOut = capture('clasp deploy --description "初回デプロイ"');
  console.log('  ' + deployOut.replace(/\n/g, '\n  '));

  const deployMatch = deployOut.match(/- ([\w-]+) @/);
  if (!deployMatch) {
    fail('デプロイIDの取得に失敗しました。Apps Script の「デプロイ」からURLを確認してください。');
    cleanup();
    process.exit(1);
  }

  const gasUrl = `https://script.google.com/macros/s/${deployMatch[1]}/exec`;
  ok(`GAS URL: ${gasUrl}`);

  // Step 5: index.html の GAS_URL を書き換え
  step(5, TOTAL, 'index.html の GAS_URL を更新');

  let html = fs.readFileSync(HTML_FILE, 'utf8');
  html = html.replace(/const GAS_URL = ".*?";/, `const GAS_URL = "${gasUrl}";`);
  fs.writeFileSync(HTML_FILE, html);
  ok('GAS_URL を更新しました');

  cleanup();

  console.log('\n================================================');
  console.log('  セットアップ完了！');
  console.log('================================================');
  console.log(`\nGAS URL:\n  ${gasUrl}\n`);
  console.log('次のステップ:');
  console.log('  1. index.html をブラウザで開く');
  console.log('  2. 初回アクセス時に Google のスコープ許可が求められます');
  console.log('     「許可」をクリックしてください');
  console.log('  3. マスターパスワードを設定してカードを登録できます\n');
}

function cleanup() {
  if (fs.existsSync(WORK_DIR)) fs.rmSync(WORK_DIR, { recursive: true });
}

main().catch(e => {
  fail('セットアップ中にエラーが発生しました:');
  console.error(e.message);
  cleanup();
  process.exit(1);
});
