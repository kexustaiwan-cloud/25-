/**
 * AI 發票自動辨識系統 - 使用 Document AI Entities 正確版
 */
const PROJECT_ID = 'my-invoice-ai-495707';
const PROCESSOR_ID = '305b7c844678fa3a';
const FOLDER_ID = '1c091HLGCUkUXDj1kQtDhYJp0pY7AMHW4';
const LOCATION = 'us';

function onOpen() {
  try {
    SpreadsheetApp.getUi().createMenu('🚀 AI 智能發票')
      .addItem('1. 開始同步掃描發票', 'main')
      .addToUi();
  } catch (e) {}
}

function main() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  // 取得或建立工作表，並設定標題列
  let sheet = spreadsheet.getSheetByName('發票資料');
  if (!sheet) {
    sheet = spreadsheet.insertSheet('發票資料');
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['掃描時間', '檔案名稱', '發票字母', '發票號碼', '賣方統編', '總金額', '日期']);
    sheet.getRange(1, 1, 1, 7).setFontWeight('bold');
  }

  try {
    const folder = DriveApp.getFolderById(FOLDER_ID);
    const files = folder.getFiles();
    let totalInvoices = 0;

    while (files.hasNext()) {
      const file = files.next();
      const mimeType = file.getMimeType();

      if (!mimeType.includes('pdf') && !mimeType.includes('image')) continue;

      Logger.log('處理檔案：' + file.getName());
      const results = callDocumentAi(file.getBlob());

      results.forEach(data => {
        // 拆分發票號碼字母與數字
        const idMatch = data.invoice_id.match(/^([A-Z]{2})-?(\d+)$/);
        const idLetter = idMatch ? idMatch[1] : data.invoice_id;
        const idNumber = idMatch ? idMatch[2] : '---';

        // 統編加單引號防止 Google Sheets 吃掉前導零
        const taxId = (data.supplier_tax && data.supplier_tax !== '---')
          ? "'" + data.supplier_tax
          : '---';

        sheet.appendRow([
          new Date(),
          file.getName(),
          idLetter,
          idNumber,
          taxId,
          data.total_amount,
          data.date
        ]);
        totalInvoices++;
      });
    }

    ui.alert('掃描完成！共辨識出 ' + totalInvoices + ' 張發票。');
  } catch (err) {
    Logger.log('執行失敗：' + err.stack);
    ui.alert('執行失敗：' + err.message);
  }
}

/**
 * 呼叫 Document AI 並從 entities 抓取欄位
 * 同時用正則做備援，兩者取最佳結果
 */
function callDocumentAi(blob) {
  const url = `https://${LOCATION}-documentai.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/processors/${PROCESSOR_ID}:process`;
  const payload = {
    rawDocument: {
      content: Utilities.base64Encode(blob.getBytes()),
      mimeType: blob.getContentType()
    }
  };
  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  const json = JSON.parse(response.getContentText());

  if (!json.document) {
    Logger.log('Document AI 回應異常：' + response.getContentText());
    return [];
  }

  // ── 方法一：從 entities 抓（Document AI Invoice Parser 標準欄位）──
  const entityResults = extractFromEntities(json.document);

  // ── 方法二：從純文字用正則抓（備援）──
  const regexResults = extractFromText(json.document.text || '');

  // 合併：以 entities 為主，缺欄位時用正則補
  return mergeResults(entityResults, regexResults);
}

/**
 * 從 Document AI 的 entities 陣列抓取發票欄位
 * 台灣電子發票常見 entity type 對照表：
 *   invoice_id / receipt_id       -> 發票號碼
 *   supplier_tax_id               -> 賣方統編
 *   total_amount / net_amount     -> 總金額
 *   invoice_date / purchase_time  -> 日期
 */
function extractFromEntities(document) {
  const entities = document.entities || [];
  const pages = document.pages || [];
  const results = [];

  // 先收集所有發票號碼（一份 PDF 可能有多張）
  const invoiceIds = [];
  entities.forEach(e => {
    const type = (e.type || '').toLowerCase();
    if (type === 'invoice_id' || type === 'receipt_id') {
      const val = (e.mentionText || '').replace(/\s/g, '').toUpperCase();
      if (/^[A-Z]{2}-?\d{6,8}$/.test(val)) invoiceIds.push(val);
    }
  });

  // 如果 entities 沒有發票號碼，就只回傳一筆（讓正則接手）
  if (invoiceIds.length === 0) return [];

  // 對每張發票，嘗試找對應的其他欄位
  // 若 entities 只有一組（同頁），直接取；若有多組則依序配對
  invoiceIds.forEach((id, idx) => {
    const taxCandidates   = getEntityValues(entities, ['supplier_tax_id', 'supplier_id']);
    const amountCandidates = getEntityValues(entities, ['total_amount', 'net_amount', 'amount_paid_since_last_statement']);
    const dateCandidates  = getEntityValues(entities, ['invoice_date', 'purchase_time', 'receipt_date']);

    results.push({
      invoice_id:   id,
      supplier_tax: taxCandidates[idx]    || taxCandidates[0]    || '---',
      total_amount: amountCandidates[idx] || amountCandidates[0] || '---',
      date:         dateCandidates[idx]   || dateCandidates[0]   || '---'
    });
  });

  return results;
}

function getEntityValues(entities, types) {
  return entities
    .filter(e => types.includes((e.type || '').toLowerCase()))
    .map(e => (e.normalizedValue && e.normalizedValue.text)
               ? e.normalizedValue.text
               : (e.mentionText || '').trim())
    .filter(Boolean);
}

/**
 * 純文字正則備援抓取
 * 只抓「真正的電子發票號碼」：2 大寫字母 + 連字號(選填) + 8 位數字
 * 排除：序號、機號、店號等其他數字串
 */
function extractFromText(fullText) {
  if (!fullText) return [];

  // 台灣電子發票號碼格式：AB-12345678 或 AB12345678
  // 必須出現在「發票號碼」、「發票號碼」等關鍵字附近，或獨立成行
  // 用較嚴格的正則：前後不能接續字母/數字
  const INVOICE_PATTERN = /\b([A-Z]{2})-?(\d{8})\b/g;

  // 排除清單：這些是非發票的序號前綴（Document AI 辨識到的機台序號等）
  const EXCLUDE_PREFIXES = ['TX', 'SA', 'KS'];

  const found = new Map(); // 用 Map 去重
  let m;
  while ((m = INVOICE_PATTERN.exec(fullText)) !== null) {
    const letters = m[1];
    const digits  = m[2];
    const full    = letters + '-' + digits;

    if (EXCLUDE_PREFIXES.includes(letters)) continue;

    // 簡單驗證：發票號碼的字母前應該有「發票」或換行，不應接在「序號:」「機:」後面
    const before = fullText.substring(Math.max(0, m.index - 10), m.index);
    if (/序號|機號|機:|序:/.test(before)) continue;

    if (!found.has(full)) {
      // 抓該發票號碼後 200 字的區塊來找其他欄位
      const context = fullText.substring(m.index, m.index + 200);
      found.set(full, {
        invoice_id:   full,
        supplier_tax: extractField(context, /(?:賣方|統編)[:\s]*(\d{8})/),
        total_amount: extractField(context, /(?:總計|合計|總金額)[:\s]*\$?([\d,]+)/),
        date:         extractField(context, /(\d{4}[-\/]\d{2}[-\/]\d{2})/)
      });
    }
  }

  return Array.from(found.values());
}

function extractField(text, regex) {
  const m = text.match(regex);
  return m ? (m[1] || m[0]).trim() : '---';
}

/**
 * 合併 entities 結果和正則結果
 * 以 entities 為主，正則做補充
 */
function mergeResults(entityResults, regexResults) {
  if (entityResults.length === 0 && regexResults.length === 0) return [];
  if (entityResults.length === 0) return regexResults;
  if (regexResults.length === 0) return entityResults;

  // 以發票號碼為 key，合併兩份結果
  const merged = new Map();

  regexResults.forEach(r => merged.set(r.invoice_id.replace('-', ''), r));

  entityResults.forEach(e => {
    const key = e.invoice_id.replace('-', '');
    if (merged.has(key)) {
      const existing = merged.get(key);
      // entities 欄位優先；缺的用正則補
      merged.set(key, {
        invoice_id:   e.invoice_id,
        supplier_tax: e.supplier_tax !== '---' ? e.supplier_tax : existing.supplier_tax,
        total_amount: e.total_amount !== '---' ? e.total_amount : existing.total_amount,
        date:         e.date         !== '---' ? e.date         : existing.date
      });
    } else {
      merged.set(key, e);
    }
  });

  return Array.from(merged.values());
}