#!/usr/bin/env node
/**
 * ライブチケット管理 & クレジットカード管理
 * 自動セットアップスクリプト
 *
 * 使い方:
 *   node setup.js
 *
 * 必要なもの:
 *   - Node.js 18以上
 *   - インターネット接続
 *   - Googleアカウント（ブラウザでのログイン）
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

// ----------------------------------------------------------------
// ユーティリティ
// ----------------------------------------------------------------
function run(cmd, opts = {}) {
  execSync(cmd, { stdio: 'inherit', cwd: WORK_DIR, ...opts });
}

function capture(cmd, opts = {}) {
  return execSync(cmd, { encoding: 'utf8', cwd: WORK_DIR, ...opts }).trim();
}

function step(n, total, msg) {
  console.log(`\n[${n}/${total}] ${msg}`);
}

function ok(msg)  { console.log(`  ✓ ${msg}`); }
function info(msg){ console.log(`  → ${msg}`); }
function err(msg) { console.error(`  ✗ ${msg}`); }

// ----------------------------------------------------------------
// メイン処理
// ----------------------------------------------------------------
async function main() {
  console.log('================================================');
  console.log('  ライブチケット管理 自動セットアップ');
  console.log('================================================');

  const TOTAL = 5;

  // ---- Step 1: clasp のインストール確認 ----
  step(1, TOTAL, 'clasp の確認');
  try {
    const v = capture('clasp --version', { cwd: ROOT });
    ok(`clasp ${v} が見つかりました`);
  } catch (_) {
    info('clasp をインストールしています（グローバル）...');
    execSync('npm install -g @google/clasp', { stdio: 'inherit' });
    ok('clasp をインストールしました');
  }

  // ---- Step 2: Googleアカウントにログイン ----
  step(2, TOTAL, 'Google アカウントへのログイン');
  info('ブラウザが開きます。Googleアカウントでログインしてください。');
  run('clasp login', { cwd: ROOT });
  ok('ログイン完了');

  // ---- Step 3: 作業ディレクトリを準備してプロジェクト作成 ----
  step(3, TOTAL, 'Google Spreadsheet と Apps Script プロジェクトの作成');

  if (fs.existsSync(WORK_DIR)) fs.rmSync(WORK_DIR, { recursive: true });
  fs.mkdirSync(WORK_DIR);

  // Code.gs と appsscript.json を作業ディレクトリにコピー
  fs.copyFileSync(CODE_GS, path.join(WORK_DIR, 'Code.gs'));
  fs.copyFileSync(MANIFEST_JSON, path.join(WORK_DIR, 'appsscript.json'));

  // clasp プロジェクト作成（新規スプレッドシートも同時に作成される）
  const createOut = capture(
    'clasp create --type sheets --title "ライブチケット管理" --rootDir .'
  );
  console.log(createOut);

  // スクリプトIDを取得
  const claspConfig = JSON.parse(fs.readFileSync(CLASP_JSON, 'utf8'));
  const scriptId = claspConfig.scriptId;
  ok(`Apps Script プロジェクト作成完了 (ID: ${scriptId})`);

  // スプレッドシートIDを取得（出力から解析）
  const ssMatch = createOut.match(/Created new Google Sheet: (.+)/);
  if (ssMatch) {
    const ssUrl = ssMatch[1].trim();
    ok(`スプレッドシート: ${ssUrl}`);
  }

  // ---- Step 4: コードをプッシュしてデプロイ ----
  step(4, TOTAL, 'コードのアップロードとデプロイ');

  info('コードをアップロードしています...');
  run('clasp push --force');
  ok('コードのアップロード完了');

  info('ウェブアプリとしてデプロイしています...');
  const deployOut = capture('clasp deploy --description "初回デプロイ"');
  console.log('  ' + deployOut.replace(/\n/g, '\n  '));

  // デプロイIDを解析して GAS URL を組み立てる
  const deployMatch = deployOut.match(/- ([\w-]+) @/);
  if (!deployMatch) {
    err('デプロイIDの取得に失敗しました。');
    err('以下のURLを手動で Apps Script の「デプロイ」から確認してください。');
    err(`  https://script.google.com/d/${scriptId}/edit`);
    cleanup();
    process.exit(1);
  }

  const deployId = deployMatch[1];
  const gasUrl   = `https://script.google.com/macros/s/${deployId}/exec`;
  ok(`デプロイ完了`);
  ok(`GAS URL: ${gasUrl}`);

  // ---- Step 5: index.html の GAS_URL を自動書き換え ----
  step(5, TOTAL, 'index.html の GAS_URL を更新');

  let html = fs.readFileSync(HTML_FILE, 'utf8');
  const before = html.match(/const GAS_URL = "(.+?)";/)?.[1] ?? '（未設定）';
  html = html.replace(
    /const GAS_URL = ".*?";/,
    `const GAS_URL = "${gasUrl}";`
  );
  fs.writeFileSync(HTML_FILE, html);
  ok(`GAS_URL を更新しました`);
  info(`変更前: ${before}`);
  info(`変更後: ${gasUrl}`);

  // ---- 完了 ----
  cleanup();

  console.log('\n================================================');
  console.log('  セットアップ完了！');
  console.log('================================================');
  console.log(`\nGAS URL:\n  ${gasUrl}\n`);
  console.log('次のステップ:');
  console.log('  1. index.html をブラウザで開く');
  console.log('  2. 初回アクセス時に Google がスコープ許可を求めます');
  console.log('     「許可」をクリックしてください');
  console.log('  3. チケット管理・カード管理を使い始められます\n');
}

function cleanup() {
  if (fs.existsSync(WORK_DIR)) {
    fs.rmSync(WORK_DIR, { recursive: true });
  }
}

main().catch(e => {
  err('セットアップ中にエラーが発生しました:');
  console.error(e.message);
  cleanup();
  process.exit(1);
});
