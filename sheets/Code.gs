/**
 * Nchoro game recorder: receives game records from the web page and appends them to this sheet.
 *
 * POST (from the game page): one game record as JSON -> one new row in the "games" sheet.
 * GET: a public summary only (counts and the last few results) for the page's record panel.
 *
 * Setup: see SETUP.md next to this file.
 */

const SHEET = "games";
const COLS = ["received_at", "status", "result", "human_side", "level", "sims", "model", "rules_id",
              "move_count", "human_score", "ai_score", "end_reason", "moves", "started_at", "finished_at",
              "game_id", "page", "v"];
const STATUSES = ["finished", "abandoned"];
const RESULTS = ["human", "ai", "draw", ""];
const LEVELS = ["easy", "gentle", "strong", "full"];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) {
    sh = ss.insertSheet(SHEET);
    sh.appendRow(COLS);
    sh.setFrozenRows(1);
  }
  return sh;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// Text that could start a spreadsheet formula is stored as plain text.
function text_(v, max) {
  let s = String(v == null ? "" : v).slice(0, max);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return s;
}

function num_(v, lo, hi) {
  const n = Number(v);
  return isFinite(n) && n >= lo && n <= hi ? n : "";
}

function doPost(e) {
  try {
    const r = JSON.parse(e.postData.contents);
    const moves = String(r.moves || "");
    if (STATUSES.indexOf(r.status) < 0 || LEVELS.indexOf(r.level) < 0 || RESULTS.indexOf(r.result || "") < 0 ||
        moves.length > 3000 || !/^([12][a-f])( [12][a-f])*$/.test(moves)) {
      return out_({ ok: false, error: "not a valid game record" });
    }
    const id = text_(r.gameId, 40);
    const cache = CacheService.getScriptCache();
    if (id && cache.get("seen:" + id)) return out_({ ok: true, duplicate: true });

    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      sheet_().appendRow([
        new Date(), r.status, r.result || "", num_(r.humanSide, 1, 2), r.level, num_(r.sims, 0, 5000),
        num_(r.model, 0, 1e6), text_(r.rulesId, 16), num_(r.moveCount, 0, 1000),
        num_(r.scores && r.scores.human, 0, 48), num_(r.scores && r.scores.ai, 0, 48),
        text_(r.endReason, 80), moves, text_(r.startedAt, 30), text_(r.finishedAt, 30), id,
        text_(r.page, 20), num_(r.v, 0, 100),
      ]);
    } finally {
      lock.releaseLock();
    }
    if (id) cache.put("seen:" + id, "1", 21600);
    return out_({ ok: true });
  } catch (err) {
    return out_({ ok: false, error: "could not save" });
  }
}

function doGet() {
  const rows = sheet_().getDataRange().getValues();
  const head = rows.shift() || [];
  const col = name => head.indexOf(name);
  const finished = rows.filter(r => r[col("status")] === "finished" && r[col("result")]);
  const recent = finished.slice(-8).reverse().map(r => ({
    level: r[col("level")], result: r[col("result")], human: r[col("human_score")], ai: r[col("ai_score")],
    moves: r[col("move_count")], side: r[col("human_side")],
  }));
  return out_({
    games: finished.length,
    humanWins: finished.filter(r => r[col("result")] === "human").length,
    draws: finished.filter(r => r[col("result")] === "draw").length,
    abandoned: rows.filter(r => r[col("status")] === "abandoned").length,
    recent: recent,
  });
}
