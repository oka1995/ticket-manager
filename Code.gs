/**
 * ライブチケット管理 & クレジットカード管理
 * Google Apps Script バックエンド
 *
 * 【デプロイ手順】
 * 1. Google スプレッドシートを新規作成
 * 2. 拡張機能 > Apps Script を開く
 * 3. このファイルの内容を貼り付けて保存
 * 4. デプロイ > 新しいデプロイ
 *    - 種類: ウェブアプリ
 *    - 次のユーザーとして実行: 自分
 *    - アクセスできるユーザー: 全員
 * 5. 発行されたURLを index.html の GAS_URL に設定
 */

// シート名定数
const SHEET = {
  PERF:    '公演',
  GROUP:   '連番グループ',
  TICKET:  'チケット',
};

// ヘッダー定義（シートが存在しない場合に自動作成）
const HEADERS = {
  [SHEET.PERF]: [
    'カードID', 'アーティスト名', 'ツアー名', '開催地（都道府県）',
    '公演日テキスト\n（例: 20260417(金)）', '表示ラベル\n（例: 東京1日目 4/17(金)）'
  ],
  [SHEET.GROUP]: [
    'グループID', 'グループ名', '紐付け公演ID',
    'レシート管理No\n（発券情報管理より）', 'メモ'
  ],
  [SHEET.TICKET]: [
    'チケットID', '公演ID', '連番グループID', '公演内\n通し番号',
    'レシート管理No\n（単番のみ）', 'アカウント名義', '支払い者名義',
    'チケットステータス', '資金回収ステータス', '譲渡ステータス',
    '席番号/整理番号', '支払い番号', '支払いURL',
    '譲渡先の名前', 'SNSプロフィールURL', 'メモ'
  ],
};

// ----------------------------------------------------------------
// エントリーポイント
// ----------------------------------------------------------------
function doGet(e) {
  return handle(e);
}

function doPost(e) {
  return handle(e);
}

function handle(e) {
  const out = ContentService.createTextOutput();
  out.setMimeType(ContentService.MimeType.JSON);

  try {
    let action, sheetName, rowIndex, values;

    if (e.postData && e.postData.contents) {
      const body = JSON.parse(e.postData.contents);
      action    = body.action;
      sheetName = body.sheet;
      rowIndex  = body.rowIndex;
      values    = body.values;
    } else {
      action    = e.parameter.action;
      sheetName = e.parameter.sheet;
    }

    // 許可されたシート名のみ受け付ける（それ以外は拒否）
    const allowed = Object.values(SHEET);
    if (!allowed.includes(sheetName)) {
      out.setContent(JSON.stringify({ ok: false, error: '不正なシート名です' }));
      return out;
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = getOrCreate(ss, sheetName);

    if (action === 'read') {
      const data = sh.getDataRange().getValues();
      out.setContent(JSON.stringify({ ok: true, data }));

    } else if (action === 'append') {
      sh.appendRow(values);
      out.setContent(JSON.stringify({ ok: true }));

    } else if (action === 'update') {
      if (!rowIndex || rowIndex < 2) throw new Error('無効な行番号');
      sh.getRange(rowIndex, 1, 1, values.length).setValues([values]);
      out.setContent(JSON.stringify({ ok: true }));

    } else if (action === 'delete') {
      if (!rowIndex || rowIndex < 2) throw new Error('無効な行番号');
      sh.deleteRow(rowIndex);
      out.setContent(JSON.stringify({ ok: true }));

    } else {
      out.setContent(JSON.stringify({ ok: false, error: '不明なアクション' }));
    }

  } catch (err) {
    out.setContent(JSON.stringify({ ok: false, error: err.message }));
  }

  return out;
}

// ----------------------------------------------------------------
// シートを取得、なければヘッダー付きで新規作成
// ----------------------------------------------------------------
function getOrCreate(ss, name) {
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    const headers = HEADERS[name];
    if (headers) {
      sh.appendRow(headers);
      // ヘッダー行を固定・装飾
      const hRange = sh.getRange(1, 1, 1, headers.length);
      hRange.setFontWeight('bold');
      hRange.setBackground('#f3f3f3');
      sh.setFrozenRows(1);
    }
  }
  return sh;
}
