import sys
import os
import sqlite3

from PySide6.QtWidgets import QMessageBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile

# ── Dialog 按鈕樣式常數 ───────────────────────────────────────
_BTN_BASE    = "border-radius: 6px; padding: 4px 16px; min-width: 80px; font-weight: bold;"
BTN_CONFIRM  = f"QPushButton {{ background-color: #D0ECF5; color: #000000; {_BTN_BASE} }} QPushButton:hover {{ background-color: #B8D8E8; }}"
BTN_DANGER   = f"QPushButton {{ background-color: #F5D4D0; color: #000000; {_BTN_BASE} }} QPushButton:hover {{ background-color: #E0BDB8; }}"
BTN_CANCEL   = f"QPushButton {{ background-color: #F2F2F7; color: #000000; {_BTN_BASE} }} QPushButton:hover {{ background-color: #E5E5EA; }}"


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


# ── 通用確認彈窗 ───────────────────────────────────────────────
def confirmBox(title, text, confirm_text="確認", cancel_text="取消",
               confirm_danger=False, default_confirm=True, parent=None):
    """
    Apple HIG 風格確認對話框。
    confirm_danger=True：確認按鈕顯示紅色（破壞性操作）
    default_confirm=False：預設選取「取消」
    回傳 True 表示使用者點確認
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Question)

    btn_ok     = msg.addButton(confirm_text, QMessageBox.AcceptRole)
    btn_cancel = msg.addButton(cancel_text,  QMessageBox.RejectRole)

    btn_ok.setStyleSheet(BTN_DANGER if confirm_danger else BTN_CONFIRM)
    btn_cancel.setStyleSheet(BTN_CANCEL)

    msg.setDefaultButton(btn_ok if default_confirm else btn_cancel)
    msg.exec()
    return msg.clickedButton() == btn_ok


# ── 測試開關 ───────────────────────────────────────────────
# True：所有 disable/greyout 全部開啟（方便測試）
# False：正式行為，上線前確認為 False
DEBUG_MODE = True


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

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
