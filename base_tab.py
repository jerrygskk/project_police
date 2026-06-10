import re
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
from db_utils import msgCritical


class BaseTab:
    """
    所有 Tab 的共用基礎介面。

    子類別必須實作：
        setup(tab_index: int) -> None
            在 tabWidget 對應的 tab 上建立 UI 與綁定事件。

    子類別可 override：
        get_tables()       -> list[QTableWidget]  供 _onTabChanged 自動 resize 用
        get_focus_widget() -> QWidget | None       供 _onTabChanged 自動 setFocus 用
    """

    def __init__(self, tab_widget, db_path):
        self.tab_widget = tab_widget   # QTabWidget
        self.db_path    = db_path

    def setup(self, tab_index):
        raise NotImplementedError

    # ── Tab 切換時由 DocumentManager 呼叫 ───────────────────
    def get_tables(self):
        """回傳此 Tab 所有預覽表格，供切換時自動 resize。"""
        return []

    def get_focus_widget(self):
        """回傳此 Tab 預設取得焦點的元件，切換時自動 setFocus。"""
        return None

    def on_activated(self):
        """Tab 被切換到時呼叫，子類別可 override 以刷新參照表等。"""
        pass

    # ── DB 工具 ─────────────────────────────────────────────
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
            msgCritical("DB錯誤", f"載入對照表失敗: {e}")
            return [], []

    # ── 共用資料轉換 helper ──────────────────────────────────
    @staticmethod
    def _trimName(name):
        """去掉 - 後綴，例如 王小明-19.06 → 王小明"""
        return name.split('-')[0] if name and '-' in name else (name or "")

    @staticmethod
    def _fmtDate(d):
        """YYYY-MM-DD → MM-DD-YYYY（僅預覽顯示用）"""
        if not d:
            return ""
        try:
            return datetime.strptime(str(d), "%Y-%m-%d").strftime("%m-%d-%Y")
        except Exception:
            return str(d)

    @staticmethod
    def _docIdFromLabel(lbl):
        """從 QLabel HTML 取出 href 中的 doc_id，找不到回傳 None。"""
        if not lbl:
            return None
        m = re.search(r'href="([^"]+)"', lbl.text())
        return m.group(1) if m else None

