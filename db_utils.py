import sys
import os

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
