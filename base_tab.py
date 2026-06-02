import sqlite3
from PySide6.QtWidgets import QMessageBox


class BaseTab:
    """
    所有 Tab 的共用基礎介面。

    子類別必須實作：
        setup(tab_index: int) -> None
            在 tabWidget 對應的 tab 上建立 UI 與綁定事件。
    """

    def __init__(self, tab_widget, db_path):
        self.tab_widget = tab_widget   # QTabWidget
        self.db_path    = db_path

    def setup(self, tab_index):
        raise NotImplementedError

    def _getConn(self):
        """回傳新的 sqlite3 連線，呼叫端負責 close()"""
        return sqlite3.connect(self.db_path)

    def _loadRef(self):
        """
        載入人員與部門對照表。
        回傳 (personnel_list, dept_list)，各為 [(id, name), ...] 格式。
        """
        try:
            conn = self._getConn()
            personnel = conn.execute(
                "SELECT staff_id, staff_name FROM Ref_Personnel "
                "WHERE is_active=1 ORDER BY staff_id"
            ).fetchall()
            depts = conn.execute(
                "SELECT dept_id, dept_name FROM Ref_Departments ORDER BY dept_id"
            ).fetchall()
            conn.close()
            return personnel, depts
        except Exception as e:
            QMessageBox.critical(None, "DB錯誤", f"載入對照表失敗: {e}")
            return [], []
