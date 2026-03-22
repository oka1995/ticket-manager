/**
 * カード管理 - Google Apps Script バックエンド
 *
 * 保存されるデータは AES-GCM で暗号化済みのため、
 * スプレッドシート上に平文のカード情報は一切存在しません。
 */

const CARD_SHEET   = 'クレジットカード';
const CARD_HEADERS = ['カードID','カード名称','ブランド','末尾4桁','支払日','暗号化データ','IV','メモ'];

function doGet(e)  { return handle(e); }
function doPost(e) { return handle(e); }

function handle(e) {
  const out = ContentService.createTextOutput();
  out.setMimeType(ContentService.MimeType.JSON);

  try {
    let action, rowIndex, values;

    if (e.postData && e.postData.contents) {
      const body = JSON.parse(e.postData.contents);
      action   = body.action;
      rowIndex = body.rowIndex;
      values   = body.values;
    } else {
      action = e.parameter.action;
    }

    // このスクリプトはカードシートのみ操作する
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = getOrCreate(ss);

    if (action === 'read') {
      out.setContent(JSON.stringify({ ok: true, data: sh.getDataRange().getValues() }));

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

function getOrCreate(ss) {
  let sh = ss.getSheetByName(CARD_SHEET);
  if (!sh) {
    sh = ss.insertSheet(CARD_SHEET);
    sh.appendRow(CARD_HEADERS);
    const hRange = sh.getRange(1, 1, 1, CARD_HEADERS.length);
    hRange.setFontWeight('bold');
    hRange.setBackground('#f3f3f3');
    sh.setFrozenRows(1);
    // カード番号列などを非表示にして誤操作を防ぐ
    sh.hideColumns(6, 2); // 暗号化データ・IV 列を非表示
  }
  return sh;
}
