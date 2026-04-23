/**
 * ポケモンカード管理 - Google Apps Script バックエンド
 *
 * 【セットアップ手順】
 * 1. Google スプレッドシートを新規作成
 * 2. 拡張機能 > Apps Script を開く
 * 3. このファイルの内容を貼り付けて保存
 * 4. スクリプトプロパティに ANTHROPIC_API_KEY を設定（写真解析を使う場合）
 *    プロジェクトの設定 > スクリプトプロパティ > ANTHROPIC_API_KEY
 * 5. デプロイ > 新しいデプロイ
 *    - 種類: ウェブアプリ
 *    - 次のユーザーとして実行: 自分
 *    - アクセスできるユーザー: 全員
 * 6. 発行された URL を index.html に設定して使用開始
 * 7. アプリ上部の「接続＆初期化」ボタンを押してシートを自動作成
 */

// ---------- 定数 ----------

const SHEETS = {
  FURUMONO:  '古物台帳',
  INVENTORY: '在庫台帳',
  SALES:     '売上台帳',
  CONFIG:    '設定',
};

const HEADERS = {
  [SHEETS.FURUMONO]: [
    '台帳No', '取引日', '取引区分',
    'カード名', '拡張パック', '言語', 'レアリティ', 'グレード/状態', '数量',
    '代価（税込）', '消費税率(%)',
    '相手方氏名', '相手方住所', '相手方職業', '相手方年齢', '確認方法',
    '在庫ID', '備考',
  ],
  [SHEETS.INVENTORY]: [
    '在庫ID', '台帳No', '仕入日',
    'カード名', '拡張パック', '言語', 'レアリティ', 'グレード/状態',
    '仕入単価', '数量', '仕入合計',
    '仕入先', '保管場所', '販売状況', 'メモ',
  ],
  [SHEETS.SALES]: [
    '売上ID', '在庫ID', '古物台帳No', '売却日', 'カード名',
    '販路', '売却単価', '数量', '売却小計',
    '手数料率(%)', '手数料額', '送料', '純売上',
    '仕入原価', '粗利', '粗利率(%)',
    '買主名', 'メモ',
  ],
  [SHEETS.CONFIG]: ['キー', '値', '備考'],
};

const DEFAULT_CONFIG = [
  ['消費税率',      '10',           ''],
  ['法人名',        '',             '古物台帳に表示される法人名'],
  ['古物商許可番号', '',             ''],
  ['販路_1',        'メルカリ',      ''],
  ['販路_2',        'ヤフオク',      ''],
  ['販路_3',        'TCGショップ',   ''],
  ['販路_4',        '直接販売',      ''],
  ['保管場所_1',    '事務所',        ''],
  ['確認方法_1',    '運転免許証',    ''],
  ['確認方法_2',    'マイナンバーカード', ''],
  ['確認方法_3',    'パスポート',    ''],
  ['確認方法_4',    'オンライン（10万円未満免除）', '古物営業法施行規則第17条3項'],
];

// ---------- エントリーポイント ----------

function doGet(e)  { return handle(e); }
function doPost(e) { return handle(e); }

function handle(e) {
  const out = ContentService.createTextOutput();
  out.setMimeType(ContentService.MimeType.JSON);

  // CORS 対応
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  try {
    let body = {};
    if (e.postData && e.postData.contents) {
      body = JSON.parse(e.postData.contents);
    } else {
      body = e.parameter || {};
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();

    switch (body.action) {

      case 'init':
        initSheets(ss);
        out.setContent(JSON.stringify({ ok: true }));
        break;

      case 'read': {
        const sh = getOrCreate(ss, body.sheet);
        out.setContent(JSON.stringify({ ok: true, data: sh.getDataRange().getValues() }));
        break;
      }

      case 'readAll': {
        // 全シートを一括取得（起動時用）
        const result = {};
        Object.values(SHEETS).forEach(name => {
          const sh = ss.getSheetByName(name);
          result[name] = sh ? sh.getDataRange().getValues() : [];
        });
        out.setContent(JSON.stringify({ ok: true, data: result }));
        break;
      }

      case 'append': {
        const sh = getOrCreate(ss, body.sheet);
        sh.appendRow(body.values);
        out.setContent(JSON.stringify({ ok: true }));
        break;
      }

      case 'update': {
        if (!body.rowIndex || body.rowIndex < 2) throw new Error('無効な行番号');
        const sh = getOrCreate(ss, body.sheet);
        sh.getRange(body.rowIndex, 1, 1, body.values.length).setValues([body.values]);
        out.setContent(JSON.stringify({ ok: true }));
        break;
      }

      case 'delete': {
        if (!body.rowIndex || body.rowIndex < 2) throw new Error('無効な行番号');
        getOrCreate(ss, body.sheet).deleteRow(body.rowIndex);
        out.setContent(JSON.stringify({ ok: true }));
        break;
      }

      // 仕入登録: 古物台帳 + 在庫台帳 を同時書き込み
      case 'registerPurchase': {
        const { furumono, inventory } = body;
        getOrCreate(ss, SHEETS.FURUMONO).appendRow(furumono);
        getOrCreate(ss, SHEETS.INVENTORY).appendRow(inventory);
        out.setContent(JSON.stringify({ ok: true }));
        break;
      }

      // 売上登録: 売上台帳 + 古物台帳(売却) + 在庫ステータス更新
      case 'registerSale': {
        const { sale, furumono, inventoryRowIndex, inventoryUpdated } = body;
        getOrCreate(ss, SHEETS.SALES).appendRow(sale);
        getOrCreate(ss, SHEETS.FURUMONO).appendRow(furumono);
        if (inventoryRowIndex >= 2) {
          const invSh = getOrCreate(ss, SHEETS.INVENTORY);
          invSh.getRange(inventoryRowIndex, 1, 1, inventoryUpdated.length).setValues([inventoryUpdated]);
        }
        out.setContent(JSON.stringify({ ok: true }));
        break;
      }

      case 'nextId': {
        const id = getNextId(ss, body.sheet, body.prefix);
        out.setContent(JSON.stringify({ ok: true, id }));
        break;
      }

      case 'dashboard': {
        out.setContent(JSON.stringify({ ok: true, data: getDashboard(ss) }));
        break;
      }

      case 'analyzeCard': {
        const result = analyzeCardImage(body.imageBase64, body.mimeType);
        out.setContent(JSON.stringify({ ok: true, data: result }));
        break;
      }

      default:
        out.setContent(JSON.stringify({ ok: false, error: '不明なアクション: ' + body.action }));
    }

  } catch (err) {
    out.setContent(JSON.stringify({ ok: false, error: err.message }));
  }

  return out;
}

// ---------- シート管理 ----------

function getOrCreate(ss, name) {
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    const headers = HEADERS[name];
    if (headers) {
      sh.appendRow(headers);
      const hRange = sh.getRange(1, 1, 1, headers.length);
      hRange.setFontWeight('bold');
      hRange.setBackground('#E8F0FE');
      sh.setFrozenRows(1);
    }
  }
  return sh;
}

function initSheets(ss) {
  Object.values(SHEETS).forEach(name => getOrCreate(ss, name));
  const configSh = ss.getSheetByName(SHEETS.CONFIG);
  if (configSh.getLastRow() <= 1) {
    DEFAULT_CONFIG.forEach(row => configSh.appendRow(row));
  }
}

// ---------- ID 採番 ----------

function getNextId(ss, sheetName, prefix) {
  const sh = getOrCreate(ss, sheetName);
  const lastRow = sh.getLastRow();
  if (lastRow <= 1) return `${prefix}0001`;
  const ids = sh.getRange(2, 1, lastRow - 1, 1).getValues()
    .map(r => r[0])
    .filter(v => String(v).startsWith(prefix))
    .map(v => parseInt(String(v).replace(prefix, ''), 10))
    .filter(n => !isNaN(n));
  const max = ids.length > 0 ? Math.max(...ids) : 0;
  return `${prefix}${String(max + 1).padStart(4, '0')}`;
}

// ---------- ダッシュボード集計 ----------

function getDashboard(ss) {
  const now = new Date();
  const yr = now.getFullYear();
  const mo = now.getMonth();

  // 在庫集計
  let totalStock = 0, totalCost = 0;
  const invSh = ss.getSheetByName(SHEETS.INVENTORY);
  if (invSh && invSh.getLastRow() > 1) {
    invSh.getRange(2, 1, invSh.getLastRow() - 1, HEADERS[SHEETS.INVENTORY].length)
      .getValues()
      .forEach(r => {
        if (r[13] !== '売却済') {
          totalStock += Number(r[9]) || 0;    // 数量
          totalCost  += Number(r[10]) || 0;   // 仕入合計
        }
      });
  }

  // 売上集計（過去6ヶ月分）
  const monthly = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(yr, mo - i, 1);
    monthly.push({ year: d.getFullYear(), month: d.getMonth() + 1, sales: 0, profit: 0, cost: 0, fee: 0 });
  }

  let totalSales = 0, totalProfit = 0;
  let thisMonthSales = 0, thisMonthProfit = 0;

  const salesSh = ss.getSheetByName(SHEETS.SALES);
  if (salesSh && salesSh.getLastRow() > 1) {
    salesSh.getRange(2, 1, salesSh.getLastRow() - 1, HEADERS[SHEETS.SALES].length)
      .getValues()
      .forEach(r => {
        const d = r[3] ? new Date(r[3]) : null;
        const net    = Number(r[12]) || 0;  // 純売上
        const profit = Number(r[14]) || 0;  // 粗利
        const fee    = Number(r[10]) || 0;  // 手数料
        const ship   = Number(r[11]) || 0;  // 送料

        totalSales  += net;
        totalProfit += profit;

        if (d && d.getFullYear() === yr && d.getMonth() === mo) {
          thisMonthSales  += net;
          thisMonthProfit += profit;
        }

        if (d) {
          const m = monthly.find(x => x.year === d.getFullYear() && x.month === d.getMonth() + 1);
          if (m) {
            m.sales  += net;
            m.profit += profit;
            m.cost   += Number(r[13]) || 0;
            m.fee    += fee + ship;
          }
        }
      });
  }

  return { totalStock, totalCost, totalSales, totalProfit, thisMonthSales, thisMonthProfit, monthly };
}

// ---------- Claude Vision によるカード解析 ----------

function analyzeCardImage(imageBase64, mimeType) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty('ANTHROPIC_API_KEY');
  if (!apiKey) throw new Error('スクリプトプロパティに ANTHROPIC_API_KEY が設定されていません');

  const prompt = `このポケモンカードの画像を分析してください。以下のJSON形式のみで返答してください（コードブロック不要）:
{
  "cardName": "カード名（日本語）",
  "set": "拡張パック名（例: 黒炎の支配者）",
  "setCode": "セットコード（例: SV3）",
  "language": "日本語",
  "rarity": "レアリティ（例: SAR, AR, SR, RR, R, U, C）",
  "number": "カード番号（例: 123/165）",
  "condition": "状態推定（美品/良品/並品/傷あり）",
  "grade": "",
  "notes": "PSAグレード番号や特記事項があれば"
}
読み取れない項目は空文字にしてください。`;

  const res = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    payload: JSON.stringify({
      model: 'claude-opus-4-7',
      max_tokens: 512,
      messages: [{
        role: 'user',
        content: [
          { type: 'image', source: { type: 'base64', media_type: mimeType || 'image/jpeg', data: imageBase64 } },
          { type: 'text', text: prompt },
        ],
      }],
    }),
    muteHttpExceptions: true,
  });

  const body = JSON.parse(res.getContentText());
  if (body.error) throw new Error(body.error.message);

  const text = body.content[0].text.trim();
  try {
    return JSON.parse(text);
  } catch (_) {
    const m = text.match(/\{[\s\S]*\}/);
    if (m) return JSON.parse(m[0]);
    throw new Error('カード情報の解析に失敗しました: ' + text);
  }
}
