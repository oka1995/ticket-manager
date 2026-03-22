# card-manager

クレジットカード情報をマスターパスワードで保護して管理するウェブアプリです。
Google Apps Script をバックエンド、静的 HTML をフロントエンドとして使用します。

## 構成

```
card-manager/
├── index.html        # フロントエンド（単一ファイル）
├── Code.gs           # Google Apps Script バックエンド
├── appsscript.json   # GAS プロジェクト設定
├── setup.js          # 自動セットアップスクリプト
└── package.json
```

## セットアップ手順

### 前提条件

- Node.js 18 以上
- Google アカウント

### 1. 依存関係のインストール（clasp）

```bash
npm install -g @google/clasp
```

### 2. 自動セットアップを実行

```bash
node setup.js
```

実行すると以下が自動で行われます：
1. Google アカウントへのログイン（ブラウザが開きます）
2. Google Spreadsheet と Apps Script プロジェクトの作成
3. コードのアップロードとウェブアプリとしてデプロイ
4. `index.html` の `GAS_URL` を自動更新

### 3. Netlify へのデプロイ（任意）

1. [Netlify](https://netlify.com) でこのリポジトリを接続
2. ビルド設定は不要（静的ファイルとして `index.html` を公開）
3. Publish directory: `.`（ルート）

### 4. 初回アクセス

1. `index.html` をブラウザで開く（または Netlify の URL にアクセス）
2. Google のスコープ許可ダイアログが表示されたら「許可」をクリック
3. マスターパスワードを設定してカード情報を登録

## 注意事項

- カード情報は Google Spreadsheet に保存されます
- マスターパスワードを忘れると登録データにアクセスできなくなります
- GAS のウェブアプリ URL は公開設定になっています（アクセス制御はマスターパスワードで行います）
