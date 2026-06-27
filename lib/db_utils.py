import sys
import os
import sqlite3
import json
import unicodedata
import html as _html

from PySide6.QtWidgets import QMessageBox, QSpacerItem, QSizePolicy, QGridLayout
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt


def getConn(db_path):
    """sqlite3 連線單一來源；呼叫端負責 commit/close。
    後續若要統一加 PRAGMA / timeout / row_factory，集中改這一處即可。"""
    return sqlite3.connect(db_path)


# ── 稽核紀錄（Audit_Log）─────────────────────────────────────────
def buildDetail(category, action, content=""):
    """組稽核 detail 字串：`[類別][動作]內容`。
    例：buildDetail("交辦","刪除","主旨：協尋失蹤人口")
        → "[交辦][刪除]主旨：協尋失蹤人口" """
    return f"[{category}][{action}]{content}"


def auditStaffName(conn, staff_id):
    """以 staff_id 解析當下姓名快照（operator 用）。查無回原 id 字串。"""
    if not staff_id:
        return ""
    try:
        r = conn.execute(
            "SELECT staff_name FROM Ref_Personnel WHERE staff_id=?",
            (staff_id,)).fetchone()
        return r[0] if r and r[0] else str(staff_id)
    except Exception:
        return str(staff_id)


def writeAudit(conn, *, role, action, detail,
               target_table=None, target_id=None, operator=None):
    """寫入一筆稽核紀錄。使用呼叫端傳入的同一個 conn（與業務操作同一
    transaction，由呼叫端統一 commit）。ts 由 SQLite 取本機時間。
    缺 Audit_Log 表的舊 DB 不致中斷業務操作（靜默跳過）。"""
    try:
        conn.execute(
            "INSERT INTO Audit_Log"
            "(ts, role, action, target_table, target_id, operator, detail) "
            "VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?, ?)",
            (role, action, target_table, target_id, operator, detail))
    except Exception:
        pass


# ── 誤刪還原回收筒（Trash_Documents）─────────────────────────────
# 主表「刪除」是清空欄位保留 doc_id（空殼列恆在）。刪除前先快照整列存進
# 回收筒，還原即把 payload 寫回原 doc_id 那列。表結構由 db_schema.ensureSchema
# 啟動時冪等建立；缺表的舊 DB 一律靜默跳過，不中斷業務（同 writeAudit 哲學）。
_TRASH_TABLES = ("Document_Task", "Document_Criminal", "Document_General")


def snapshotRow(conn, table, doc_id):
    """回傳該列 {欄名: 值} dict（清空式刪除前呼叫）。查無回 None。
    table 為呼叫端常數（三主表名），非使用者輸入。"""
    if table not in _TRASH_TABLES:
        return None
    cur = conn.execute(f"SELECT * FROM {table} WHERE doc_id=?", (doc_id,))
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def writeTrash(conn, *, table_name, doc_id, payload,
               subject="", doc_person="", deleted_role=""):
    """把刪除前的整列快照寫進回收筒。用同一 conn（與清空同 transaction，
    呼叫端統一 commit）；缺 Trash_Documents 表的舊 DB 靜默跳過。"""
    try:
        conn.execute(
            "INSERT INTO Trash_Documents"
            "(table_name, doc_id, payload, subject, doc_person, "
            " deleted_ts, deleted_role) "
            "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), ?)",
            (table_name, str(doc_id),
             json.dumps(payload, ensure_ascii=False),
             subject or "", doc_person or "", deleted_role or ""))
    except Exception:
        pass


def restoreFromTrash(conn, trash_id):
    """還原一筆：payload 寫回原 doc_id 空殼列，並刪該回收筒列。
    用同一 conn，呼叫端 commit。回 (table_name, doc_id)；查無／表名不合法／
    缺表回 None。"""
    try:
        r = conn.execute(
            "SELECT table_name, doc_id, payload FROM Trash_Documents "
            "WHERE trash_id=?", (trash_id,)).fetchone()
    except Exception:
        return None
    if not r:
        return None
    table_name, doc_id, payload_json = r
    if table_name not in _TRASH_TABLES:
        return None
    data = json.loads(payload_json)
    # 排除 doc_id（WHERE 條件）與 last_modified：後者必須讓 AFTER UPDATE trigger
    # 重新蓋成當下時間。若寫回快照的舊值，trigger 的 WHEN NEW.last_modified IS
    # OLD.last_modified 不成立而不觸發，last_modified 停在舊值，瀏覽/歸檔頁的指紋
    # （MAX(last_modified)／> since）偵測不到還原 → 清單不刷新（需手動重載）。
    cols = [c for c in data if c not in ("doc_id", "last_modified")]
    if not cols:
        return None
    set_clause = ", ".join(f"{c}=?" for c in cols)
    vals = [data[c] for c in cols]
    conn.execute(f"UPDATE {table_name} SET {set_clause} WHERE doc_id=?",
                 vals + [str(doc_id)])
    conn.execute("DELETE FROM Trash_Documents WHERE trash_id=?", (trash_id,))
    return (table_name, doc_id)


# ── Dialog 按鈕樣式常數 ───────────────────────────────────────
_BTN_BASE     = "border-radius: 6px; padding: 4px 16px; min-width: 80px; font-weight: bold;"
_BTN_DISABLED = "QPushButton:disabled { background-color: #e5e5ea; color: #b0b0b5; }"
BTN_CONFIRM  = f"QPushButton {{ background-color: #D0ECF5; color: #000000; {_BTN_BASE} }} QPushButton:hover {{ background-color: #B8D8E8; }} {_BTN_DISABLED}"
BTN_DANGER   = f"QPushButton {{ background-color: #F5D4D0; color: #000000; {_BTN_BASE} }} QPushButton:hover {{ background-color: #E0BDB8; }} {_BTN_DISABLED}"
BTN_CANCEL   = f"QPushButton {{ background-color: #F2F2F7; color: #000000; {_BTN_BASE} }} QPushButton:hover {{ background-color: #E5E5EA; }} {_BTN_DISABLED}"


# ── 通用訊息彈窗（確定按鈕中文，統一樣式）────────────────────
def _makeMsg(icon, title, text, parent=None):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    btn = msg.addButton("確定", QMessageBox.AcceptRole)
    btn.setStyleSheet(BTN_CONFIRM)
    msg.exec()

def msgInfo(title, text, parent=None):
    _makeMsg(QMessageBox.Information, title, text, parent)

def msgWarning(title, text, parent=None):
    _makeMsg(QMessageBox.Warning, title, text, parent)

def msgCritical(title, text, parent=None):
    _makeMsg(QMessageBox.Critical, title, text, parent)


# ── 未預期例外 → 白話訊息 ───────────────────────────────────────
# 全域錯誤處理用：把工程語言的例外轉成承辦看得懂、可行動的提示。
# 技術細節（traceback）仍只進 error.log，不丟給使用者。純邏輯，可單測。
_GENERIC_ERROR = ("程式發生未預期的錯誤，已記錄至 error.log。\n"
                  "請將該檔案提供維護人員協助處理。")

def friendlyErrorMessage(exc_type, exc_value):
    """依例外型別回傳白話、可行動的錯誤訊息（不含技術細節）。

    對照不到的型別一律回泛用訊息。`exc_type` 可為 None（此時只看 value）。
    """
    name = getattr(exc_type, "__name__", "") or type(exc_value).__name__
    text = str(exc_value or "")
    low = text.lower()

    # SQLite：忙線鎖定 / 缺表 / 檔案損毀
    if name in ("OperationalError",) or "operationalerror" in low:
        if "locked" in low or "busy" in low:
            return ("資料庫忙線中，可能有其他視窗正開啟本程式。\n"
                    "請關閉其他視窗後再試一次。")
        return ("資料庫存取發生問題，請關閉程式後重新開啟；\n"
                "若持續發生，請聯繫維護人員並提供 error.log。")
    if name in ("DatabaseError", "IntegrityError", "DataError") or \
            "databaseerror" in low or "malformed" in low:
        return ("資料庫檔案可能損毀或格式異常。\n"
                "請聯繫維護人員，並提供 error.log 與資料庫備份檔。")

    # 檔案 / 權限 / 網路磁碟
    if name in ("PermissionError",):
        return ("無法存取檔案（可能正被其他程式開啟，或權限不足）。\n"
                "請關閉相關檔案後再試一次。")
    if name in ("FileNotFoundError",):
        return ("找不到所需的檔案或資料夾。\n"
                "若為歸檔資料夾，請至「設定」頁確認路徑是否正確。")
    if name in ("OSError", "IOError"):
        return ("檔案或資料夾存取失敗，可能是網路磁碟機已中斷連線。\n"
                "請確認網路磁碟機連線後再試一次。")

    return _GENERIC_ERROR


# ── 通用確認彈窗 ───────────────────────────────────────────────
def confirmBox(title, text, confirm_text="確認", cancel_text="取消",
               confirm_danger=False, default_confirm=True, parent=None,
               informative="", min_width=0):
    """
    Apple HIG 風格確認對話框。版面統一為「左確認、右取消」。
    confirm_danger=True：確認按鈕顯示紅色（破壞性操作）
    default_confirm=False：預設選取「取消」
    informative：次要說明（顯示為較小的灰字，置於主訊息下方，HIG 兩層式）
    min_width：對話框最小內容寬度(px)；用於長檔名等需要更寬不換行的場合（有上限）
    回傳 True 表示使用者點確認
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    if informative:
        # Windows 的 QMessageBox 不會自動把 informativeText 縮小／變灰（那是 macOS
        # 原生行為），故用 rich text 自行做 HIG 兩層式：主訊息正常、次要說明灰字。
        body = (
            f'<div style="font-size:14pt; color:#1c1c1e;">{_html.escape(text)}</div>'
            f'<div style="font-size:14pt; color:#6b6b6e; margin-top:10px; '
            f'line-height:150%;">{_html.escape(informative).replace(chr(10), "<br>")}</div>'
        )
        msg.setTextFormat(Qt.RichText)
        msg.setText(body)
    else:
        msg.setText(text)
    msg.setIcon(QMessageBox.Question)

    # 拉寬對話框：QMessageBox 無直接設寬 API，於 grid layout 末列塞水平 spacer 撐出
    # 最小寬度；超過上限的超長內容仍會自動換行（不會無限拉寬）。
    if min_width:
        lay = msg.layout()
        if isinstance(lay, QGridLayout):
            lay.addItem(
                QSpacerItem(min_width, 0, QSizePolicy.Minimum, QSizePolicy.Expanding),
                lay.rowCount(), 0, 1, lay.columnCount())

    # 兩顆都用 ActionRole，避免 Qt 依平台慣例重排左右；
    # 如此按加入順序排列 → 左：確認、右：取消。
    btn_ok     = msg.addButton(confirm_text, QMessageBox.ActionRole)
    btn_cancel = msg.addButton(cancel_text,  QMessageBox.ActionRole)

    btn_ok.setStyleSheet(BTN_DANGER if confirm_danger else BTN_CONFIRM)
    btn_cancel.setStyleSheet(BTN_CANCEL)

    # Enter 預設鈕、Esc 對應取消
    msg.setDefaultButton(btn_ok if default_confirm else btn_cancel)
    msg.setEscapeButton(btn_cancel)
    msg.exec()
    return msg.clickedButton() == btn_ok


# ── 測試開關 ───────────────────────────────────────────────
# True：所有 disable/greyout 全部開啟（方便測試）
# False：正式行為，上線前確認為 False
DEBUG_MODE = False


def getResourcePath(relative_path):
    """
    - dbfile.db：永遠從 exe 所在目錄讀（真實資料）
    - 其他（.ui, .svg）：打包後從 _MEIPASS，開發時從當前目錄
    """
    if relative_path == 'dbfile.db':
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), relative_path)
        return os.path.join(os.path.abspath('.'), relative_path)

    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)


def loadUi(path):
    """載入 .ui 檔案，回傳 widget；找不到檔案時彈出錯誤並回傳 None"""
    f = QFile(path)
    if not f.exists():
        msgCritical("錯誤", f"找不到 UI 檔案: {path}")
        return None
    f.open(QFile.ReadOnly)
    widget = QUiLoader().load(f)
    f.close()
    return widget


def nextDocId(conn, table_name):
    """
    從 Seq_DocId 取得下一個流水號（只增不減）。
    conn 必須是已開啟的 sqlite3 連線，呼叫端負責 commit/close。
    """
    conn.execute(
        "UPDATE Seq_DocId SET last_id = last_id + 1 WHERE table_name = ?",
        (table_name,)
    )
    row = conn.execute(
        "SELECT last_id FROM Seq_DocId WHERE table_name = ?",
        (table_name,)
    ).fetchone()
    return str(row[0])


# ══════════════════════════════════════════════════════════════════
# 跨年度重置（Reset）
# ══════════════════════════════════════════════════════════════════
# 三張參照表的重編設定：(表名, id欄, 前綴, 位數)
_RESET_REF_TABLES = [
    ("Ref_Personnel",   "staff_id",     "P",  2),
    ("Ref_Departments", "dept_id",      "D",  2),
    ("Ref_CaseTypes",   "case_type_id", "CT", 2),
]

# 主表中參照到參照表 id 的欄位：{參照表: [(主表, 欄位), ...]}
# 跨年度時主表會被清空，故重編 id 不需連動更新主表；此表僅供文件參考。
_RESET_SEQ_TABLES = ["Document_Task", "Document_Criminal", "Document_General"]


def listInactiveRefItems(db_path):
    """
    回傳三張參照表中所有停用（is_active=0）項目，供 Reset 確認彈窗預覽。
    格式：[(表中文名, id, name), ...]
    """
    label = {
        "Ref_Personnel":   "人員",
        "Ref_Departments": "部門",
        "Ref_CaseTypes":   "案類",
    }
    name_col = {
        "Ref_Personnel":   "staff_name",
        "Ref_Departments": "dept_name",
        "Ref_CaseTypes":   "case_type_name",
    }
    out = []
    conn = sqlite3.connect(db_path)
    try:
        for tbl, idc, _, _ in _RESET_REF_TABLES:
            rows = conn.execute(
                f"SELECT {idc}, {name_col[tbl]} FROM {tbl} "
                f"WHERE is_active=0 ORDER BY sort_order"
            ).fetchall()
            for rid, rname in rows:
                out.append((label[tbl], rid, rname))
    finally:
        conn.close()
    return out


def performYearEndReset(db_path):
    """
    跨年度重置（破壞性操作，呼叫端須先備份 + 強確認）：
      1. 清空三張主表（Document_Task / Criminal / General）
      2. 刪除參照表中停用（is_active=0）項目
      3. 依 sort_order 重編參照表 id（連續，維持原前綴與位數）
      4. 重設 sort_order 為連續整數（1 起）
      5. 歸零 Seq_DocId

    全程單一 transaction，任一步失敗則 rollback 並拋出例外（資料不變）。

    重編 id 採兩段式避開主鍵衝突：
      先把所有列改成暫時前綴（如 _TMP_P0001），再編回正式 id。
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        # 1. 清空三張主表
        for t in _RESET_SEQ_TABLES:
            conn.execute(f"DELETE FROM {t}")

        # 2~4. 逐張參照表：刪停用 → 依 sort_order 兩段式重編 → 重設 sort_order
        for tbl, idc, prefix, digits in _RESET_REF_TABLES:
            # 刪除停用項目
            conn.execute(f"DELETE FROM {tbl} WHERE is_active=0")

            # 依現行 sort_order 取出存活列（順序即為重編後順序）
            rows = conn.execute(
                f"SELECT {idc} FROM {tbl} ORDER BY sort_order, {idc}"
            ).fetchall()

            # 第一段：全部改為暫時前綴，避免與目標 id 撞主鍵
            for i, (old_id,) in enumerate(rows, start=1):
                tmp_id = f"__TMP__{prefix}{i:0{digits}d}"
                conn.execute(
                    f"UPDATE {tbl} SET {idc}=? WHERE {idc}=?", (tmp_id, old_id))

            # 第二段：暫時前綴 → 正式 id，並同步重設 sort_order
            for i in range(1, len(rows) + 1):
                tmp_id = f"__TMP__{prefix}{i:0{digits}d}"
                new_id = f"{prefix}{i:0{digits}d}"
                conn.execute(
                    f"UPDATE {tbl} SET {idc}=?, sort_order=? WHERE {idc}=?",
                    (new_id, i, tmp_id))

        # 5. 歸零 Seq_DocId
        conn.execute("UPDATE Seq_DocId SET last_id = 0")

        # 6. 清除歸檔根目錄設定（強制使用者進新年度後重新指定）
        for _k in (ARCHIVE_ROOT_KEY, "archive_subdir_crim", "archive_subdir_gen"):
            conn.execute(
                "INSERT INTO App_Settings(key, value) VALUES(?,'')"
                " ON CONFLICT(key) DO UPDATE SET value=''", (_k,))

        # 7. 清空稽核紀錄（重置前已整庫備份，歷史 log 留在備份檔；當前庫歸零）
        try:
            conn.execute("DELETE FROM Audit_Log")
        except Exception:
            pass  # 缺表的舊 DB 跳過

        # 8. 清空誤刪還原回收筒（主表已清，殘留快照無意義；缺表跳過）
        try:
            conn.execute("DELETE FROM Trash_Documents")
        except Exception:
            pass

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
# App_Settings 讀寫（key-value 設定；schema 不變，只新增 key）
# ══════════════════════════════════════════════════════════════════
def getSetting(db_path, key, default=""):
    """讀 App_Settings 單一設定；不存在回 default。"""
    conn = getConn(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM App_Settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def setSetting(db_path, key, value):
    """寫 App_Settings 單一設定（upsert）。value 欄為 NOT NULL，None 一律存空字串。"""
    conn = getConn(db_path)
    try:
        conn.execute(
            "INSERT INTO App_Settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value or ""))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
# 歸檔 PDF 定位（瀏覽 Tab4 開啟電子檔用）
#   - 根存「當年度資料夾」的 UNC（archive_root），與磁碟機代號脫鉤
#   - 刑案/一般各一個子夾名（archive_subdir_crim/gen），可空（空則走整年度層）
#   - 用 is_electronic 整串檔名於對應子夾遞迴比對；檔名 NFC 正規化避免同形不同碼
# ══════════════════════════════════════════════════════════════════
ARCHIVE_ROOT_KEY = "archive_root"
_ARCH_SUBDIR_KEY = {"crim": "archive_subdir_crim", "gen": "archive_subdir_gen"}

_PDF_INDEX_CACHE = {}   # base_dir -> {nfc(檔名): 完整路徑}


def _nfc(s):
    return unicodedata.normalize("NFC", s or "")


def clearPdfIndexCache():
    """設定變更或年度重置後呼叫，清掉檔名索引快取。"""
    _PDF_INDEX_CACHE.clear()


def _buildPdfIndex(base_dir, force=False):
    """遞迴 base_dir 建「nfc(檔名)→完整路徑」索引（含子資料夾）。同名取第一個。"""
    if not force and base_dir in _PDF_INDEX_CACHE:
        return _PDF_INDEX_CACHE[base_dir]
    idx = {}
    for root, _dirs, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                idx.setdefault(_nfc(f), os.path.join(root, f))
    _PDF_INDEX_CACHE[base_dir] = idx
    return idx


def archiveSubdir(db_path, key):
    """回傳該類別(crim/gen)設定的子夾名稱；未設定回空字串。"""
    return getSetting(db_path, _ARCH_SUBDIR_KEY.get(key, ""), "")


def archiveDefaultDir(db_path, key):
    """歸檔 Tab 選 PDF 資料夾時的預設起始路徑＝歸檔根(+該類別子夾)。
    未設定根回空字串（QFileDialog 會退回系統預設位置）。"""
    root = (getSetting(db_path, ARCHIVE_ROOT_KEY, "") or "").strip()
    if not root:
        return ""
    sub = (archiveSubdir(db_path, key) or "").strip()
    return os.path.join(root, sub) if sub else root


def resolveArchivedPdf(db_path, key, fname):
    """以 is_electronic 檔名定位實體 PDF。
    回傳 (完整路徑 or None, 狀態碼)：
      ok       命中
      noroot   尚未設定歸檔根
      noaccess 根/子夾無法存取（網路碟未掛或路徑錯）
      notfound 走訪後找不到該檔名
    """
    fname = _nfc((fname or "").strip())
    if not fname:
        return None, "notfound"
    root = (getSetting(db_path, ARCHIVE_ROOT_KEY, "") or "").strip()
    if not root:
        return None, "noroot"
    sub = (archiveSubdir(db_path, key) or "").strip()
    base = os.path.join(root, sub) if sub else root
    if not os.path.isdir(base):
        return None, "noaccess"
    idx = _buildPdfIndex(base)
    hit = idx.get(fname)
    if hit is None:                       # miss → 重建一次（吸收新歸檔的檔）
        idx = _buildPdfIndex(base, force=True)
        hit = idx.get(fname)
    if hit is None:
        return None, "notfound"
    return hit, "ok"


def _driveToUnc(path):
    """用 Windows 原生 WNetGetConnection 把對應的網路磁碟機代號（如 Z:）解析成 UNC。
    非對應磁碟機 / 非 Windows / 失敗皆回 None。"""
    p = path.replace("/", "\\")
    if len(p) < 2 or p[1] != ":":
        return None
    drive = p[:2]  # 如 Z:
    try:
        import ctypes
        from ctypes import wintypes
        mpr = ctypes.WinDLL("mpr")
        length = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(length.value)
        res = mpr.WNetGetConnectionW(drive, buf, ctypes.byref(length))
        if res != 0:  # 緩衝不足等，依回報長度重試一次
            buf = ctypes.create_unicode_buffer(length.value)
            res = mpr.WNetGetConnectionW(drive, buf, ctypes.byref(length))
        if res == 0 and buf.value.startswith("\\\\"):
            unc = buf.value.rstrip("\\")
            rel = p[2:].lstrip("\\")  # 磁碟機代號之後的相對路徑
            return unc + ("\\" + rel if rel else "")
    except Exception:
        pass
    return None


def toUncPath(path):
    """把含磁碟機代號的路徑（如 Z:\\歸檔\\2026）轉成 UNC（\\\\伺服器\\分享\\歸檔\\2026）。
    已是 UNC 直接回；非網路磁碟或轉換失敗回 None（呼叫端應改要求手動輸入 UNC）。"""
    if not path:
        return None
    p = path.replace("/", "\\")
    if p.startswith("\\\\"):
        return p.rstrip("\\")
    # 首選：WNetGetConnection 直接問磁碟機代號對應的 UNC（最可靠）
    unc = _driveToUnc(p)
    if unc:
        return unc
    # 後備：QStorageInfo（部分環境可抓到 \\伺服器\分享 來源）
    try:
        from PySide6.QtCore import QStorageInfo
        si = QStorageInfo(path)
        dev = (si.device() or "").replace("/", "\\")
        root = si.rootPath()
        if dev.startswith("\\\\") and root:
            rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
            if rel in (".", ""):
                return dev.rstrip("\\")
            return dev.rstrip("\\") + "\\" + rel.replace("/", "\\")
    except Exception:
        pass
    return None
