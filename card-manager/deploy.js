#!/usr/bin/env node
/**
 * カード管理 GAS デプロイスクリプト
 *
 * 使い方:
 *   node deploy.js
 *
 * 初回: Google ログインと Script ID の入力が必要です。
 * 2回目以降: 自動でプッシュ＆デプロイします。
 */

'use strict';

const { execSync, spawnSync } = require('child_process');
const fs       = require('fs');
const path     = require('path');
const readline = require('readline');

const ROOT          = __dirname;
const CODE_GS       = path.join(ROOT, 'Code.gs');
const MANIFEST_JSON = path.join(ROOT, 'appsscript.json');
const CLASP_JSON    = path.join(ROOT, '.clasp.json');
const CLASPRC       = path.join(require('os').homedir(), '.clasprc.json');

function run(cmd)     { execSync(cmd, { stdio: 'inherit', cwd: ROOT }); }
function capture(cmd) { return execSync(cmd, { encoding: 'utf8', cwd: ROOT }).trim(); }
function ok(msg)      { console.log(`  ✓ ${msg}`); }
function info(msg)    { console.log(`  → ${msg}`); }
function fail(msg)    { console.error(`  ✗ ${msg}`); }

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => rl.question(question, ans => { rl.close(); resolve(ans.trim()); }));
}

async function main() {
  console.log('================================================');
  console.log('  カード管理 GAS デプロイ');
  console.log('================================================\n');

  // Step 1: ログイン確認
  const loggedIn = fs.existsSync(CLASPRC) &&
    (() => { try { return !!JSON.parse(fs.readFileSync(CLASPRC,'utf8')).token; } catch{ return false; } })();

  if (!loggedIn) {
    console.log('[1/3] Google アカウントへのログイン');
    info('ブラウザが開きます。Googleアカウントでログインしてください。');
    info('ブラウザを開けない環境では以下のURLにアクセスしてコードを貼り付けてください。');
    run('clasp login --no-localhost');
    ok('ログイン完了\n');
  } else {
    ok('ログイン済み\n');
  }

  // Step 2: .clasp.json (Script ID) 確認
  let scriptId = '';
  if (fs.existsSync(CLASP_JSON)) {
    scriptId = JSON.parse(fs.readFileSync(CLASP_JSON,'utf8')).scriptId || '';
  }

  if (!scriptId) {
    console.log('[2/3] Script ID の設定');
    info('Google Apps Script の「プロジェクトの設定」から Script ID をコピーしてください。');
    info('URL 例: https://script.google.com/home/projects/<Script ID>/edit');
    scriptId = await ask('  Script ID を入力してください: ');
    if (!scriptId) { fail('Script ID が入力されませんでした'); process.exit(1); }
    fs.writeFileSync(CLASP_JSON, JSON.stringify({ scriptId, rootDir: '.' }, null, 2));
    ok(`Script ID を保存しました: ${scriptId}\n`);
  } else {
    ok(`Script ID: ${scriptId}\n`);
  }

  // Step 3: プッシュ＆デプロイ
  console.log('[3/3] コードのアップロードとデプロイ');

  info('コードをアップロードしています...');
  run('clasp push --force');
  ok('アップロード完了');

  // 既存のデプロイメントを取得
  info('デプロイしています...');
  let deploymentId = '';
  try {
    const deployList = capture('clasp deployments');
    // "@HEAD" 以外の最初のデプロイメントIDを取得
    const match = deployList.match(/- ([\w-]+) @(?!HEAD)/);
    if (match) deploymentId = match[1];
  } catch(e) {}

  let deployOut = '';
  if (deploymentId) {
    // 既存デプロイメントを更新（URLが変わらない）
    deployOut = capture(`clasp deploy --deploymentId ${deploymentId} --description "更新デプロイ"`);
  } else {
    // 新規デプロイ
    deployOut = capture('clasp deploy --description "デプロイ"');
  }
  console.log('  ' + deployOut.replace(/\n/g, '\n  '));
  ok('デプロイ完了');

  console.log('\n================================================');
  console.log('  デプロイ完了！');
  console.log('================================================');
  console.log('\nGAS URL は変更されていません。そのままご利用ください。\n');
}

main().catch(e => {
  fail('デプロイ中にエラーが発生しました:');
  console.error(e.message);
  process.exit(1);
});
