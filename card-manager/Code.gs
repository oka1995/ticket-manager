/**
 * カード管理 - Google Apps Script バックエンド
 *
 * 保存されるデータは AES-GCM で暗号化済みのため、
 * スプレッドシート上に平文のカード情報は一切存在しません。
 */

const CARD_SHEET     = 'クレジットカード';
const CARD_HEADERS   = ['カードID','カード名称','ブランド','末尾4桁','支払日','暗号化データ','IV','メモ','画像DriveID'];
const IMG_FOLDER     = 'カード管理-画像';
const SCAN_FOLDER_ID = '14U6au82KeHTCqtGEStlnGfO5hC73Z0gI'; // ScanSnap 保存先フォルダ

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

      // ---- 画像アップロード ----
      if (action === 'uploadImage') {
        const blob = Utilities.newBlob(
          Utilities.base64Decode(body.base64),
          body.mimeType,
          body.fileName || ('card_' + Date.now() + '.jpg')
        );
        const folder = getOrCreateImgFolder();
        const file   = folder.createFile(blob);
        file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
        out.setContent(JSON.stringify({ ok: true, fileId: file.getId() }));
        return out;
      }

      // ---- 画像削除 ----
      if (action === 'deleteImage') {
        if (body.fileId) {
          DriveApp.getFileById(body.fileId).setTrashed(true);
        }
        out.setContent(JSON.stringify({ ok: true }));
        return out;
      }

      // ---- 画像 base64 取得（AI識別用） ----
      if (action === 'getImgBase64') {
        const file = DriveApp.getFileById(body.fileId);
        try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch(e2) {}
        const blob = file.getBlob();
        out.setContent(JSON.stringify({
          ok: true,
          base64:   Utilities.base64Encode(blob.getBytes()),
          mimeType: blob.getContentType() || 'image/jpeg'
        }));
        return out;
      }

    } else {
      action = e.parameter.action;
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = getOrCreate(ss);

    if (action === 'getImgFolderUrl') {
      const folder = getOrCreateImgFolder();
      out.setContent(JSON.stringify({ ok: true, folderId: folder.getId(), folderUrl: folder.getUrl() }));

    } else if (action === 'listImgFolder') {
      const folder  = getOrCreateImgFolder();
      const imgCol  = CARD_HEADERS.indexOf('画像DriveID');
      const rows    = sh.getDataRange().getValues().slice(1);
      const usedIds = new Set(rows.map(r => String(r[imgCol] || '')).filter(Boolean));
      const iter    = folder.getFiles();
      const list    = [];
      while (iter.hasNext()) {
        const f   = iter.next();
        if (!f.getMimeType().startsWith('image/')) continue;
        const fid = f.getId();
        if (usedIds.has(fid)) continue;
        try { f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch(e2) {}
        list.push({ fileId: fid, name: f.getName() });
      }
      out.setContent(JSON.stringify({ ok: true, files: list }));

    } else if (action === 'read') {
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
      out.setContent(JSON.stringify({ ok: false, error: '不明なアクション: ' + action }));
    }

  } catch (err) {
    out.setContent(JSON.stringify({ ok: false, error: err.message }));
  }

  return out;
}

// ----------------------------------------------------------------
// シートを取得、なければヘッダー付きで新規作成。
// 既存シートに不足列があれば末尾に追加（マイグレーション）。
// ----------------------------------------------------------------
function getOrCreate(ss) {
  let sh = ss.getSheetByName(CARD_SHEET);
  if (!sh) {
    sh = ss.insertSheet(CARD_SHEET);
    sh.appendRow(CARD_HEADERS);
    const hRange = sh.getRange(1, 1, 1, CARD_HEADERS.length);
    hRange.setFontWeight('bold');
    hRange.setBackground('#f3f3f3');
    sh.setFrozenRows(1);
    sh.hideColumns(6, 2); // 暗号化データ・IV 列を非表示
  } else {
    // マイグレーション: 不足しているヘッダーを末尾に追加
    const lastCol = sh.getLastColumn();
    const existingHeaders = sh.getRange(1, 1, 1, lastCol).getValues()[0];
    CARD_HEADERS.forEach((h, i) => {
      if (!existingHeaders.includes(h)) {
        sh.getRange(1, lastCol + 1 + i - existingHeaders.length).setValue(h);
      }
    });
  }
  return sh;
}

// ----------------------------------------------------------------
// 画像保存用 Drive フォルダを取得（ScanSnap フォルダを優先使用）
// ----------------------------------------------------------------
function getOrCreateImgFolder() {
  if (SCAN_FOLDER_ID) {
    try { return DriveApp.getFolderById(SCAN_FOLDER_ID); } catch(e2) {}
  }
  const folders = DriveApp.getFoldersByName(IMG_FOLDER);
  if (folders.hasNext()) return folders.next();
  return DriveApp.createFolder(IMG_FOLDER);
}
