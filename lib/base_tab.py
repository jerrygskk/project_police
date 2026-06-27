import re
from datetime import datetime
from lib.db_utils import msgCritical, getConn
from lib.archive_text import _trimName as _archiveTrimName


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
        """回傳新的 sqlite3 連線，呼叫端負責 close()（統一走 db_utils.getConn）"""
        return getConn(self.db_path)

    def _dbNow(self):
        """資料庫端當前時間字串，與 trigger 寫入的 last_modified 同基準。"""
        conn = self._getConn()
        try:
            return conn.execute("SELECT datetime('now','localtime')").fetchone()[0]
        finally:
            conn.close()

    def _loadRef(self):
        """
        載入人員與部門對照表。
        回傳 (personnel_list, dept_list)，各為 [(id, name), ...] 格式。
        """
        conn = None
        try:
            conn = self._getConn()
            personnel = conn.execute(
                "SELECT staff_id, staff_name FROM Ref_Personnel "
                "WHERE is_active=1 ORDER BY sort_order"
            ).fetchall()
            depts = conn.execute(
                "SELECT dept_id, dept_name FROM Ref_Departments "
                "WHERE is_active=1 ORDER BY sort_order"
            ).fetchall()
            return personnel, depts
        except Exception as e:
            msgCritical("DB錯誤", f"載入對照表失敗: {e}")
            return [], []
        finally:
            if conn:
                conn.close()

    # ── 共用資料轉換 helper ──────────────────────────────────
    @staticmethod
    def _trimName(name):
        """去掉 -／－ 後綴，例如 王小明-19.06 → 王小明（收斂至 archive_text._trimName，
        統一處理半形 - 與全形 －）"""
        return _archiveTrimName(name)

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

    # ── 共用：刷新交辦單預覽表的業務組 / 承辦人欄 ────────────────
    def _refreshTaskPreviewNames(self, table, dept_col=3, proc_col=4, docid_col=1):
        """
        掃 table 每一列，用 doc_id 反查 Document_Task 最新的
        業務組名稱與承辦人名稱並更新顯示。
        發文（tab_dispatch）與收文（tab_receive）共用。
        """
        if not table:
            return
        conn = None
        try:
            conn = self._getConn()
            for r in range(table.rowCount()):
                doc_item = table.item(r, docid_col)
                if not doc_item:
                    continue
                row = conn.execute("""
                    SELECT d.dept_name, p.staff_name
                    FROM Document_Task t
                    LEFT JOIN Ref_Departments d ON t.dept_id      = d.dept_id
                    LEFT JOIN Ref_Personnel   p ON t.processor_id = p.staff_id
                    WHERE t.doc_id = ?
                """, (doc_item.text(),)).fetchone()
                if not row:
                    continue
                dept_name, processor_name = row
                if dept_name is not None and table.item(r, dept_col):
                    table.item(r, dept_col).setText(dept_name)
                if processor_name is not None and table.item(r, proc_col):
                    table.item(r, proc_col).setText(self._trimName(processor_name))
        except Exception as e:
            msgCritical("DB錯誤", f"刷新預覽列失敗: {e}")
        finally:
            if conn:
                conn.close()

