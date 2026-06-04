import sys
import os

from PySide6.QtWidgets import QMessageBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile


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
        QMessageBox.critical(None, "錯誤", f"找不到 UI 檔案: {path}")
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
