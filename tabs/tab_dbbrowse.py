from PySide6.QtCore import Qt, QTimer, QUrl, QSize
from PySide6.QtWidgets import (
    QVBoxLayout, QTabWidget, QComboBox, QLineEdit, QPushButton,
    QCheckBox, QLabel, QTableWidget, QTableWidgetItem, QWidget, QHBoxLayout,
)
from PySide6.QtGui import QColor, QIcon, QDesktopServices

from lib.base_tab import BaseTab
from lib.db_utils import (
    getResourcePath, loadUi, msgInfo, msgWarning, msgCritical, confirmBox,
    resolveArchivedPdf, getSetting, ARCHIVE_ROOT_KEY,
)
from lib.auth_manager import AuthManager
from ui_utils import (
    setupPreviewTable, autoResizeTable, setDocIdLinkCell, makeDeleteBtn, refreshDeleteBtns,
    TaskEditDialog, CriminalEditDialog, GeneralEditDialog,
)


# ─────────────────────────────────────────────────────────────
# 三張表的欄位定義
#   header  : 表頭顯示文字
#   view_col: View 中的欄位名（用於 SELECT / 搜尋）
#   slim    : True = 精簡模式也顯示；False = 僅完整模式
#   link    : True = 此欄為可點擊編號欄
#   color   : True = 套用狀態顏色（僅交辦單狀態欄）
#   search  : True = 可被關鍵字搜尋（布林欄如紙本/電子檔排除）
#   stretch : True = 此欄自動撐滿剩餘寬度
# 順序即為顯示由左至右的順序（重要欄在左）。
# ─────────────────────────────────────────────────────────────
TASK_COLS = [
    {"header": "", "delete": True, "slim": True, "w": 32},
    {"header": "編號",     "view_col": "編號",     "slim": True,  "link": True,  "search": True, "w": 64},
    {"header": "所承辦人", "view_col": "所承辦人", "slim": True,  "search": True, "w": 120, "trim_name": True},
    {"header": "交辦事由", "view_col": "交辦事由", "slim": True,  "search": True, "stretch": True, "w": 240},
    {"header": "業務組",   "view_col": "業務組",   "slim": True,  "search": True, "w": 80},
    {"header": "狀態",     "view_col": "狀態",     "slim": True,  "color": True, "search": True, "w": 200},
    {"header": "限辦日期", "view_col": "限辦日期", "slim": True,  "search": True, "w": 140},
    {"header": "發文日期", "view_col": "發文日期", "slim": True,  "search": True, "w": 140},
    {"header": "收文日期", "view_col": "收文日期", "slim": False, "search": True, "w": 140},
    {"header": "收文人員", "view_col": "收文人員", "slim": False, "search": True, "w": 120},
    {"header": "送文人員", "view_col": "送文人員", "slim": False, "search": True, "w": 120},
    {"header": "紀錄時間", "view_col": "紀錄時間", "slim": False, "search": False, "w": 240, "trunc_sec": True},
]

CRIM_COLS = [
    {"header": "", "delete": True, "slim": True, "w": 32},
    {"header": "送文編號",    "view_col": "送文編號",    "slim": True,  "link": True,  "search": True, "w": 80},
    {"header": "主承辦人",    "view_col": "主承辦人",    "slim": True,  "search": True, "w": 120, "trim_name": True},
    {"header": "案類",        "view_col": "案類",        "slim": True,  "search": True, "w": 180},
    {"header": "嫌疑人/案由", "view_col": "嫌疑人_案由", "slim": True,  "search": True, "stretch": True, "w": 240},
    {"header": "發文分類",    "view_col": "發文分類",    "slim": True,  "search": True, "w": 96, "map": "status"},
    {"header": "陳報日期",    "view_col": "陳報日期",    "slim": True,  "search": True, "w": 140},
    {"header": "受理日期",    "view_col": "受理日期",    "slim": True,  "search": True, "w": 140},
    {"header": "送文人員",    "view_col": "送文人員",    "slim": False, "search": True, "w": 120},
    {"header": "報案人",      "view_col": "報案人",      "slim": False, "search": True, "w": 130},
    {"header": "受理人",      "view_col": "受理人",      "slim": False, "search": True, "w": 120, "trim_name": True},
    {"header": "紙本",        "view_col": "紙本",        "slim": False, "search": False, "w": 56, "bool_col": True},
    {"header": "電子檔",      "view_col": "電子檔",      "slim": False, "search": False, "w": 64, "bool_col": True},
]

GEN_COLS = [
    {"header": "", "delete": True, "slim": True, "w": 32},
    {"header": "送文編號", "view_col": "送文編號", "slim": True,  "link": True,  "search": True, "w": 80},
    {"header": "陳報人",   "view_col": "陳報人",   "slim": True,  "search": True, "w": 120, "trim_name": True},
    {"header": "陳報主旨", "view_col": "陳報主旨", "slim": True,  "search": True, "stretch": True, "w": 240},
    {"header": "業務單位", "view_col": "業務單位", "slim": True,  "search": True, "w": 96},
    {"header": "分類",     "view_col": "分類",     "slim": True,  "search": True, "w": 96, "map": "cat"},
    {"header": "陳報日期", "view_col": "陳報日期", "slim": True,  "search": True, "w": 140},
    {"header": "送文人員", "view_col": "送文人員", "slim": False, "search": True, "w": 120},
    {"header": "紙本",     "view_col": "紙本",     "slim": False, "search": False, "w": 56, "bool_col": True},
    {"header": "電子檔",   "view_col": "電子檔",   "slim": False, "search": False, "w": 64, "bool_col": True},
]


# 每張表的 View 名、底層表名、底層承辦人欄、View 編號欄、EditDialog
TABLE_META = {
    "task": {
        "cols": TASK_COLS, "view": "View_Task_Full",
        "base": "Document_Task", "proc_fk": "processor_id", "id_col": "編號",
        "dialog": TaskEditDialog,
    },
    "crim": {
        "cols": CRIM_COLS, "view": "View_Criminal_Full",
        "base": "Document_Criminal", "proc_fk": "processor_id", "id_col": "送文編號",
        "dialog": CriminalEditDialog, "archive": True,
    },
    "gen": {
        "cols": GEN_COLS, "view": "View_General_Full",
        "base": "Document_General", "proc_fk": "processor_id", "id_col": "送文編號",
        "dialog": GeneralEditDialog, "archive": True,
    },
}


def _statusColor(status):
    """交辦單狀態欄顏色，比照陳報頁慣例。"""
    s = status or ""
    if s.startswith("逾期"):
        return QColor("#e74c3c")
    if s.startswith("剩餘") or "今日" in s:
        return QColor("#e67e22")
    if s == "已發文":
        return QColor("#27ae60")
    return None  # 免覆 / 空白 → 預設色


class TabDBBrowse(BaseTab):
    """資料庫瀏覽：交辦單 / 刑案 / 一般陳報，歷史全表瀏覽 + 搜尋。"""

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        browse_widget = loadUi(getResourcePath("layouts/Layout5.ui"))
        if not browse_widget:
            return

        inner = browse_widget.centralWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)
        self._inner = inner

        self.subtabs = inner.findChild(QTabWidget, "browse_subtabs")
        if self.subtabs:
            # 內層子頁籤專屬樣式（只套此 QTabWidget，不動外層大 Tab）：
            # 選中頁籤加底部藍色指示線，與下方白色表格區做出分界。
            self.subtabs.setStyleSheet("""
                QTabWidget#browse_subtabs::pane {
                    border: none;
                }
                QTabWidget#browse_subtabs QTabBar::tab {
                    background-color: transparent;
                    color: #636366;
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 8px 18px;
                    margin-right: 4px;
                    font-weight: 500;
                }
                QTabWidget#browse_subtabs QTabBar::tab:selected {
                    color: #8fa8c8;
                    border-bottom: 2px solid #8fa8c8;
                    font-weight: 600;
                }
                QTabWidget#browse_subtabs QTabBar::tab:hover:!selected {
                    color: #3a3a3c;
                }
            """)

        # 每個 key 蒐集自己的元件
        self._ui = {}
        for key in ("task", "crim", "gen"):
            self._ui[key] = {
                "scope":  inner.findChild(QComboBox, f"{key}_scope"),
                "kw":     inner.findChild(QLineEdit, f"{key}_kw"),
                "search": inner.findChild(QPushButton, f"{key}_search"),
                "full":   inner.findChild(QPushButton, f"{key}_seg_full"),
                "slim":   inner.findChild(QPushButton, f"{key}_seg_slim"),
                "table":  inner.findChild(QTableWidget, f"{key}_table"),
                "count":  inner.findChild(QLabel, f"{key}_count"),
                "hint":   inner.findChild(QLabel, f"{key}_hint"),
                "overdue": inner.findChild(QPushButton, f"{key}_overdue"),
            }

        # 歸檔根目錄警示 label（放在 crim/gen filter row 右側，archive_root 空時顯示）
        _ARCH_WARN_SS = "color:#e74c3c; font-size:11pt;"
        _ARCH_WARN_TXT = "⚠ 歸檔資料夾未設定，請至設定頁更新"
        self._arch_warn = {}
        for key in ("crim", "gen"):
            lbl = QLabel(_ARCH_WARN_TXT)
            lbl.setStyleSheet(_ARCH_WARN_SS)
            lbl.setVisible(False)
            fl = inner.findChild(QHBoxLayout, f"{key}_filter")
            if fl:
                fl.addWidget(lbl)
            self._arch_warn[key] = lbl

        # 浮水印 QLabel（疊在每張表上）
        self._watermark = {}
        for key in ("task", "crim", "gen"):
            tbl = self._ui[key]["table"]
            wm = QLabel(tbl)
            wm.setAlignment(Qt.AlignCenter)
            wm.setStyleSheet(
                "color:#c7c7cc; font-size:16pt; font-weight:600;"
                "background:transparent;")
            wm.setAttribute(Qt.WA_TransparentForMouseEvents)
            wm.hide()
            self._watermark[key] = wm

        # 填充範圍下拉、綁定事件
        for key in ("task", "crim", "gen"):
            self._initScope(key)
            self._bindEvents(key)

        # 初次載入三張表
        for key in ("task", "crim", "gen"):
            self._reload(key)

        # 記錄初始指紋，之後切換進來時據此判斷是否需重載
        self._sigs = {}
        for key in ("task", "crim", "gen"):
            try:
                self._sigs[key] = self._tableSignature(key)
            except Exception:
                pass

        # 身分切換時即時更新各表的刪除鈕與編號連結可用狀態
        AuthManager.instance().role_changed.connect(self._onRolePerm)

    def _onRolePerm(self, _role=None):
        """身分變更：逐列切換刪除鈕停用/啟用、編號連結可點/純文字。"""
        is_admin = AuthManager.instance().is_admin()
        for key in ("task", "crim", "gen"):
            table = self._ui.get(key, {}).get("table")
            if not table:
                continue
            cols = TABLE_META[key]["cols"]
            del_col  = next((i for i, c in enumerate(cols) if c.get("delete")), None)
            link_col = next((i for i, c in enumerate(cols) if c.get("link")), None)
            order = getattr(self, "_docorder", {}).get(key, [])
            if del_col is not None:
                refreshDeleteBtns(table, is_admin, del_col)
            if link_col is not None:
                for r in range(table.rowCount()):
                    if r < len(order):
                        did = order[r]
                        setDocIdLinkCell(
                            table, r, link_col, did,
                            lambda _row, d, k=key: self._onEdit(k, self._rowOf(k, d), d),
                            clickable=is_admin,
                        )

    # ── 範圍下拉：全部欄位 + 可搜尋欄位 ──────────────────────
    def _initScope(self, key):
        combo = self._ui[key]["scope"]
        if not combo:
            return
        combo.clear()
        combo.addItem("全部欄位", userData=None)
        for c in TABLE_META[key]["cols"]:
            if c.get("search"):
                combo.addItem(c["header"], userData=c["view_col"])

    def _bindEvents(self, key):
        u = self._ui[key]
        if u["search"]:
            u["search"].clicked.connect(lambda _, k=key: self._reload(k))
        if u["kw"]:
            u["kw"].returnPressed.connect(lambda k=key: self._reload(k))
            # 即時搜尋（防抖 1000ms，打字期間不重載，停手 1 秒才查）
            timer = QTimer(u["kw"])
            timer.setSingleShot(True)
            timer.setInterval(1000)
            timer.timeout.connect(lambda k=key: self._reload(k))
            self._ui[key]["_debounce"] = timer
            u["kw"].textChanged.connect(lambda _, t=timer: t.start())
        if u["scope"]:
            u["scope"].currentIndexChanged.connect(lambda _, k=key: self._reload(k))
        if u["full"]:
            u["full"].toggled.connect(lambda _, k=key: self._onToggleFull(k))
            self._styleSegmented(key)
        if u.get("overdue"):
            u["overdue"].toggled.connect(lambda _, k=key: self._applyOverdue(k))
            self._styleOverdue(key)

    # 精簡 / 完整：兩顆獨立膠囊（藥丸形，圓角=高度一半），選中顆藍底白字。
    _SEG_STYLE = """
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #c6c6c8;
            border-radius: 17px;
            padding: 6px 16px;
            color: #636366;
            font-weight: 500;
        }
        QPushButton:checked {
            background-color: #8fa8c8;
            border: 1px solid #8fa8c8;
            color: #ffffff;
            font-weight: 600;
        }
        QPushButton:!checked:hover { background-color: #f2f2f7; }
    """

    def _styleSegmented(self, key):
        slim = self._ui[key]["slim"]
        full = self._ui[key]["full"]
        if slim:
            slim.setStyleSheet(self._SEG_STYLE)
        if full:
            full.setStyleSheet(self._SEG_STYLE)

    # 逾期未回篩選膠囊：選中紅底白字（警示語意）。
    _OVERDUE_STYLE = """
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #c6c6c8;
            border-radius: 13px;
            padding: 3px 12px;
            color: #636366;
            font-weight: 500;
            font-size: 12px;
        }
        QPushButton:checked {
            background-color: #e07a72;
            border: 1px solid #e07a72;
            color: #ffffff;
            font-weight: 600;
        }
        QPushButton:!checked:hover { background-color: #f2f2f7; }
    """

    def _styleOverdue(self, key):
        btn = self._ui[key].get("overdue")
        if btn:
            btn.setStyleSheet(self._OVERDUE_STYLE)

    def _today(self):
        """今天日期字串，一次 reload 內快取，避免迴圈重複呼叫。"""
        from datetime import date
        return date.today().isoformat()

    def _applyOverdue(self, key):
        """逾期未回篩選：純 setRowHidden，不重建表格。
        逾期旗標已於建列時存在 vertical header item(UserRole)。
        與搜尋天然交集（搜尋決定哪些列在表裡，此處只藏其中非逾期者）。
        切換後重算可見筆數。"""
        if key != "task":
            return
        u = self._ui[key]
        table = u["table"]
        btn = u.get("overdue")
        if not table:
            return
        on = bool(btn and btn.isChecked())
        visible = 0
        table.setUpdatesEnabled(False)
        for row in range(table.rowCount()):
            if on:
                hi = table.verticalHeaderItem(row)
                is_overdue = bool(hi and hi.data(Qt.UserRole))
                table.setRowHidden(row, not is_overdue)
                if is_overdue:
                    visible += 1
            else:
                table.setRowHidden(row, False)
                visible += 1
        table.setUpdatesEnabled(True)
        # 更新筆數（沿用 footer 邏輯，hit_hidden 維持現狀）
        kw = (u["kw"].text() or "").strip() if u["kw"] else ""
        self._updateFooter(key, visible, kw, False)

    def _onToggleFull(self, key):
        # 切換精簡/完整：資料不變，只改欄位可見性 + 重算欄寬，不重查/不重建
        self._applyMode(key)

    # ── 目前模式要顯示的欄位清單 ────────────────────────────
    def _isFull(self, key):
        btn = self._ui[key]["full"]
        return btn.isChecked() if btn else False

    # ── 主載入 / 搜尋（資料變動時才呼叫，建全欄、塞全部 cell）──
    def _reload(self, key):
        meta = TABLE_META[key]
        u = self._ui[key]
        table = u["table"]
        if not table:
            return
        self._today_cache = self._today()

        # 一律建「完整模式的全部欄位」，精簡模式之後用 setColumnHidden 藏欄，
        # 切換模式就不必重查 DB、重建 700+ 列（避免頓挫）。
        cols = meta["cols"]
        headers = [c["header"] for c in cols]
        stretch_idx = next((i for i, c in enumerate(cols) if c.get("stretch")), None)
        fixed_overrides = {c["header"]: c["w"] for c in cols if c.get("w")}

        setupPreviewTable(
            table, headers,
            stretch_col=stretch_idx if stretch_idx is not None else 1,
            fixed_overrides=fixed_overrides,
            cap_mode=False,
        )

        # 查詢資料
        try:
            rows = self._query(key)
        except Exception as e:
            msgCritical("DB錯誤", f"載入資料失敗：{e}")
            return

        kw = (u["kw"].text() or "").strip() if u["kw"] else ""
        scope_col = u["scope"].currentData() if u["scope"] else None
        if scope_col:
            search_cols = [scope_col]
        else:
            search_cols = [c["view_col"] for c in meta["cols"] if c.get("search")]

        id_col = meta["id_col"]
        table.setRowCount(0)
        order = []
        matched_cols_by_id = {}
        shown = 0
        for r in rows:
            # 跳過已清空（軟刪除）的列，全量載入與差異更新一致
            if self._isEmptied(key, r):
                continue
            # 關鍵字過濾：記下這筆實際命中的欄位
            if kw:
                matched = [vc for vc in search_cols
                           if r.get(vc) is not None and kw in str(r.get(vc))]
                if not matched:
                    continue
            else:
                matched = []
            did = str(r.get(id_col) or "")
            self._appendRow(key, table, cols, r, id_col)
            order.append(did)
            matched_cols_by_id[did] = matched
            shown += 1

        # 記住目前顯示的 doc_id 順序（供差異更新定位列）、搜尋狀態、載入時刻
        if not hasattr(self, "_docorder"):
            self._docorder = {}
        self._docorder[key] = order
        self._matchedCols = getattr(self, "_matchedCols", {})
        self._matchedCols[key] = matched_cols_by_id
        self._lastSearch = getattr(self, "_lastSearch", {})
        self._lastSearch[key] = (kw, search_cols, shown)
        self._lastLoad = getattr(self, "_lastLoad", {})
        self._lastLoad[key] = self._dbNow()

        # 套用目前模式（藏/顯示欄）+ 欄寬重算
        self._applyMode(key)
        # 套用逾期篩選（若開啟，藏非逾期列並重算筆數）
        self._applyOverdue(key)

    def _dbNow(self):
        """取資料庫端的當前時間字串，與 trigger 寫入的 last_modified 同基準。"""
        conn = self._getConn()
        try:
            return conn.execute("SELECT datetime('now','localtime')").fetchone()[0]
        finally:
            conn.close()

    def _applyMode(self, key):
        """只改欄位可見性與欄寬，不動資料。精簡↔完整切換走這裡，瞬間完成。"""
        meta = TABLE_META[key]
        table = self._ui[key]["table"]
        if not table:
            return
        full = self._isFull(key)

        # 藏/顯示欄
        for idx, c in enumerate(meta["cols"]):
            hidden = not (full or c.get("slim"))
            table.setColumnHidden(idx, hidden)

        # 欄寬重算（藏欄後 stretch 欄要重新吃掉剩餘空間，避免留白/擠壓）
        QTimer.singleShot(0, lambda t=table: autoResizeTable(t))

        # footer：是否有「某筆只命中於目前隱藏欄」→ 才需提示切完整
        kw, search_cols, shown = getattr(self, "_lastSearch", {}).get(
            key, ("", [], table.rowCount()))
        hit_hidden = False
        if kw:
            visible_view_cols = {
                c["view_col"] for c in meta["cols"]
                if (full or c.get("slim")) and c.get("view_col")
            }
            matched_by_id = getattr(self, "_matchedCols", {}).get(key, {})
            for did, matched in matched_by_id.items():
                if matched and not (set(matched) & visible_view_cols):
                    # 這筆命中的欄全是隱藏欄 → 在可見欄看不出為何命中
                    hit_hidden = True
                    break
        self._updateFooter(key, shown, kw, hit_hidden)

    def _query(self, key):
        """回傳 dict 列表，含 View 全欄 + _proc_active（+ 歸檔表的 _arch_fname 原始檔名）。"""
        meta = TABLE_META[key]
        arch_sel = ", b.is_electronic AS _arch_fname" if meta.get("archive") else ""
        sql = f"""
            SELECT v.*, COALESCE(p.is_active, 1) AS _proc_active{arch_sel}
            FROM {meta['view']} v
            LEFT JOIN {meta['base']} b ON v."{meta['id_col']}" = b.doc_id
            LEFT JOIN Ref_Personnel p ON b.{meta['proc_fk']} = p.staff_id
        """
        conn = self._getConn()
        try:
            cur = conn.execute(sql)
            names = [d[0] for d in cur.description]
            out = [dict(zip(names, row)) for row in cur.fetchall()]
        finally:
            conn.close()
        return out

    def _isEmptied(self, key, r):
        """該筆是否已被清空（軟刪除）。只看真實內容欄是否全空，
        排除：編號(link)、狀態(color，View 補『免覆』)、刪除欄、
        紙本/電子檔(bool_col，清空後 View 補『否』)。"""
        cols = TABLE_META[key]["cols"]
        content_cols = [c for c in cols
                        if not c.get("link") and not c.get("color")
                        and not c.get("delete") and not c.get("bool_col")]
        return not any(r.get(c["view_col"]) for c in content_cols)

    def _rowMatchesSearch(self, key, r):
        """該筆是否符合目前搜尋條件。"""
        u = self._ui[key]
        meta = TABLE_META[key]
        kw = (u["kw"].text() or "").strip() if u["kw"] else ""
        if not kw:
            return True
        scope_col = u["scope"].currentData() if u["scope"] else None
        if scope_col:
            search_cols = [scope_col]
        else:
            search_cols = [c["view_col"] for c in meta["cols"] if c.get("search")]
        for vc in search_cols:
            val = r.get(vc)
            if val is not None and kw in str(val):
                return True
        return False

    def _diffUpdate(self, key):
        """差異更新：只處理上次載入後變動（last_modified 更新）的列，
        其餘列不動。新增→加列、修改→更新列、清空刪除/不符搜尋→移除列。"""
        meta = TABLE_META[key]
        table = self._ui[key]["table"]
        if not table:
            return
        self._today_cache = self._today()
        since = getattr(self, "_lastLoad", {}).get(key)
        if since is None:
            self._reload(key)
            return

        cols = meta["cols"]
        id_col = meta["id_col"]
        # 查變動筆的 PK
        conn = self._getConn()
        try:
            changed_ids = [str(row[0]) for row in conn.execute(
                f"SELECT doc_id FROM {meta['base']} WHERE last_modified > ?",
                (since,)).fetchall()]
        finally:
            conn.close()

        if not changed_ids:
            self._lastLoad[key] = self._dbNow()
            return

        # 取這些 PK 的完整 View 列
        rows_by_id = {}
        for r in self._query(key):
            did = str(r.get(id_col) or "")
            if did in changed_ids:
                rows_by_id[did] = r

        order = self._docorder.setdefault(key, [])
        u = self._ui[key]
        kw = (u["kw"].text() or "").strip() if u["kw"] else ""
        scope_col = u["scope"].currentData() if u["scope"] else None
        if scope_col:
            search_cols = [scope_col]
        else:
            search_cols = [c["view_col"] for c in meta["cols"] if c.get("search")]
        matched_map = self._matchedCols.setdefault(key, {}) if hasattr(
            self, "_matchedCols") else {}
        if not hasattr(self, "_matchedCols"):
            self._matchedCols = {key: matched_map}

        for did in changed_ids:
            r = rows_by_id.get(did)
            in_table = did in order
            emptied = r is not None and self._isEmptied(key, r)
            should_show = (r is not None) and (not emptied) and self._rowMatchesSearch(key, r)

            if should_show and not in_table:
                # 新增：附加到表尾
                pos = table.rowCount()
                table.insertRow(pos)
                order.append(did)
                self._fillRow(key, table, cols, r, id_col, pos)
            elif should_show and in_table:
                # 修改：就地更新該列
                pos = order.index(did)
                self._fillRow(key, table, cols, r, id_col, pos)
            elif (not should_show) and in_table:
                # 移除：刪該列
                pos = order.index(did)
                table.removeRow(pos)
                order.pop(pos)
                matched_map.pop(did, None)
                continue

            # 維護命中欄記錄（供切完整提示判斷）
            if should_show:
                matched_map[did] = [vc for vc in search_cols
                                    if r.get(vc) is not None and kw in str(r.get(vc))] if kw else []

        self._lastLoad[key] = self._dbNow()
        # 更新筆數與欄寬
        shown = table.rowCount()
        kw, search_cols, _ = getattr(self, "_lastSearch", {}).get(key, ("", [], shown))
        self._lastSearch[key] = (kw, search_cols, shown)
        self._applyMode(key)
        # 差異更新後同步套用逾期篩選（新列若不符逾期則藏）
        self._applyOverdue(key)

    def _appendRow(self, key, table, cols, r, id_col):
        pos = table.rowCount()
        table.insertRow(pos)
        self._fillRow(key, table, cols, r, id_col, pos)

    def _fillRow(self, key, table, cols, r, id_col, pos):
        """在指定列 pos 寫入所有 cell（差異更新與全量載入共用）。"""
        inactive = not r["_proc_active"]

        for c_idx, c in enumerate(cols):
            # 刪除欄（最左）：放 X 鈕，點擊以 doc_id 觸發刪除
            if c.get("delete"):
                doc_id = str(r.get(id_col) or "")
                container, del_btn = makeDeleteBtn(
                    lambda _=None, k=key, d=doc_id: self._onDelete(k, d))
                # 一般使用者無修改權限 → 刪除鈕停用變灰（admin 全開）
                if not AuthManager.instance().is_admin():
                    del_btn.setEnabled(False)
                table.setCellWidget(pos, c_idx, container)
                continue

            val = r.get(c["view_col"])
            text = "" if val is None else str(val)

            # 承辦/協辦欄：顯示去 - 後綴（王小明-19.06 → 王小明），比照預覽頁
            if c.get("trim_name") and text:
                text = self._trimName(text)

            # 套用顯示對照（發文分類 / 分類）：DB 原始值 → 短詞，
            # 與陳報頁共用 BaseTab 的 _STATUS_MAP / _CAT_MAP。
            mkey = c.get("map")
            if mkey and text:
                table_map = self._STATUS_MAP if mkey == "status" else self._CAT_MAP
                text = table_map.get(text, text)

            # 紀錄時間：去掉秒以下小數（排序用的微秒不顯示），只留到秒
            if c.get("trunc_sec") and "." in text:
                text = text.split(".", 1)[0]

            if c.get("link"):
                doc_id = str(r.get(id_col) or "")
                # 一般使用者無修改權限 → 編號改純文字不可點（admin 才可開編輯）
                is_admin = AuthManager.instance().is_admin()
                setDocIdLinkCell(
                    table, pos, c_idx, doc_id,
                    lambda _row, did, k=key: self._onEdit(k, self._rowOf(k, did), did),
                    clickable=is_admin,
                )
                continue

            # 主旨欄：cellWidget =（有真實歸檔檔名時）前置電子檔圖示鈕 + 文字。
            # 只有點圖示鈕才開檔（行為比照歸檔頁），整格其餘區域不觸發。
            if c.get("stretch"):
                afn = ""
                if TABLE_META[key].get("archive"):
                    afn = (r.get("_arch_fname") or "").strip()
                    if not afn.lower().endswith(".pdf"):
                        afn = ""
                cont = QWidget()
                hl = QHBoxLayout(cont)
                hl.setContentsMargins(6, 0, 6, 0)
                hl.setSpacing(4)
                hl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if afn:
                    bo = QPushButton()
                    bo.setIcon(QIcon(":/icon_pdf.svg"))
                    bo.setIconSize(QSize(16, 16))
                    bo.setFixedSize(22, 22)
                    bo.setCursor(Qt.PointingHandCursor)
                    bo.setToolTip("開啟 PDF 檢視")
                    bo.setStyleSheet(
                        "QPushButton{border:1px solid #c6c6c8;border-radius:6px;background:#fff;}"
                        "QPushButton:hover{background:#eaf1f8;}")
                    bo.clicked.connect(
                        lambda _=False, k=key, f=afn: self._openArchivedPdf(k, f))
                    hl.addWidget(bo)
                lab = QLabel(text)
                if text:
                    lab.setToolTip(text)
                if inactive:
                    lab.setStyleSheet("color: #aeaeb2;")
                hl.addWidget(lab, 1)
                table.setCellWidget(pos, c_idx, cont)
                continue

            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)

            if c.get("color"):
                col = _statusColor(text)
                if col:
                    item.setForeground(col)
            elif inactive:
                # 承辦人已停用 → 整列文字標灰
                item.setForeground(QColor("#aeaeb2"))

            table.setItem(pos, c_idx, item)

        # 存逾期旗標到該列 vertical header item（toggle 時直接讀，不重算/不重查）
        if key == "task":
            due  = (r.get("限辦日期") or "").strip()
            sent = (r.get("發文日期") or "").strip()
            today = getattr(self, "_today_cache", None) or self._today()
            overdue = bool(due and due < today and not sent)
            hi = table.verticalHeaderItem(pos)
            if hi is None:
                hi = QTableWidgetItem()
                table.setVerticalHeaderItem(pos, hi)
            hi.setData(Qt.UserRole, overdue)

    def _rowOf(self, key, doc_id):
        """以 doc_id 找出目前在表格中的列號（差異更新後仍正確）。"""
        order = getattr(self, "_docorder", {}).get(key, [])
        try:
            return order.index(doc_id)
        except ValueError:
            return -1

    def _updateFooter(self, key, shown, kw, hit_hidden):
        u = self._ui[key]
        if u["count"]:
            u["count"].setText(f"共 {shown} 筆")

        # 浮水印（查無資料時顯示）
        wm = self._watermark.get(key)
        tbl = u["table"]
        if wm and tbl:
            if shown == 0:
                msg = f"查無符合「{kw}」的資料" if kw else "查無資料"
                wm.setText(msg)
                wm.resize(tbl.viewport().size())
                wm.move(0, 0)
                wm.show()
                wm.raise_()
            else:
                wm.hide()

        # footer 右側提示：命中欄位在精簡模式被隱藏
        if u["hint"]:
            if hit_hidden:
                u["hint"].setText("部分結果命中的欄位需切「完整預覽」查看")
                u["hint"].setStyleSheet("color:#e6a23c; font-size:11pt;")
            else:
                u["hint"].setText("")

    # ── 刪除（清空式 UPDATE，比照陳報/收文頁）────────────────
    _CLEAR_SQL = {
        "task": (
            "UPDATE Document_Task SET receive_date=NULL, receive_id=NULL, "
            "dept_id=NULL, subject=NULL, processor_id=NULL, deadline=NULL, "
            "dispatch_date=NULL, sender_id=NULL, timestamp=NULL WHERE doc_id=?"),
        "crim": (
            "UPDATE Document_Criminal SET report_date=NULL, sender_id=NULL, "
            "case_type=NULL, case_status=NULL, processor_id=NULL, "
            "subject_summary=NULL, occurrence_date=NULL, reporter_name=NULL, "
            "receiver_id=NULL, is_reported=0, is_electronic='' WHERE doc_id=?"),
        "gen": (
            "UPDATE Document_General SET report_date=NULL, sender_id=NULL, "
            "dept_id=NULL, gen_cat_id=NULL, subject=NULL, processor_id=NULL, "
            "is_reported=0, is_electronic='' WHERE doc_id=?"),
    }

    def _onDelete(self, key, doc_id):
        if not doc_id:
            return
        if not confirmBox(
                "確認刪除",
                f"本筆資料將被刪除，本文號（{doc_id}）無法再被使用，確認刪除？",
                confirm_text="刪除", confirm_danger=True, default_confirm=False):
            return
        try:
            conn = self._getConn()
            conn.execute(self._CLEAR_SQL[key], (doc_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("刪除失敗", str(e))
            return
        # 差異更新：清空後該列會被判定為 emptied → 自動移除。
        # 刪除前後保留捲動位置，避免畫面跳回頂端。
        table = self._ui[key]["table"]
        sb = table.verticalScrollBar() if table else None
        scroll_pos = sb.value() if sb else 0
        self._diffUpdate(key)
        if sb:
            # autoResize 在下一個事件迴圈才跑，捲動還原也排在其後
            QTimer.singleShot(0, lambda b=sb, v=scroll_pos: b.setValue(min(v, b.maximum())))
        self._sigs = getattr(self, "_sigs", {})
        try:
            self._sigs[key] = self._tableSignature(key)
        except Exception:
            pass

    # ── 點編號開 EditDialog ─────────────────────────────────
    def _onEdit(self, key, row, doc_id):
        dialog_cls = TABLE_META[key]["dialog"]
        dlg = dialog_cls(self.db_path, doc_id, self._ui[key]["table"])
        if dlg.exec():
            # 編輯後差異更新，只動到改過的那列
            self._diffUpdate(key)
            self._sigs = getattr(self, "_sigs", {})
            try:
                self._sigs[key] = self._tableSignature(key)
            except Exception:
                pass

    def _openArchivedPdf(self, key, fname):
        """以 is_electronic 檔名定位並開啟實體 PDF（唯讀檢視）。"""
        # 轉檔前存量資料可能只記占位字串（非真正檔名），無法開啟
        if not fname.lower().endswith(".pdf"):
            msgInfo("無電子檔",
                    "本筆未記錄可開啟的電子檔名稱，可能為轉檔前的存量資料。")
            return
        path, status = resolveArchivedPdf(self.db_path, key, fname)
        if status == "ok":
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            return
        if status == "noroot":
            msgWarning("尚未設定歸檔資料夾",
                       "請先於設定頁指定本年度歸檔資料夾後，再開啟電子檔。")
        elif status == "noaccess":
            msgCritical("無法存取歸檔資料夾",
                        "歸檔資料夾目前無法存取，請確認：\n"
                        "1. 網路磁碟機是否已透過 NET USE 連線\n"
                        "2. 設定的歸檔資料夾路徑是否正確")
        else:  # notfound
            msgCritical("找不到電子檔",
                        f"無法定位檔案：{fname}\n\n請確認：\n"
                        "1. 網路磁碟機是否已連線\n"
                        "2. 該 PDF 是否已被移動或刪除")

    # ── 框架掛鉤 ────────────────────────────────────────────
    def get_tables(self):
        return [self._ui[k]["table"] for k in ("task", "crim", "gen")
                if self._ui.get(k, {}).get("table")]

    def _tableSignature(self, key):
        """回傳該表的變動指紋：(筆數, 最大 last_modified)。
        任一新增/修改/清空刪除都會改變這個指紋（trigger 會更新 last_modified）。"""
        meta = TABLE_META[key]
        conn = self._getConn()
        try:
            row = conn.execute(
                f"SELECT COUNT(*), MAX(last_modified) FROM {meta['base']}"
            ).fetchone()
        finally:
            conn.close()
        return (row[0], row[1])

    def on_activated(self):
        # 切換進「資料庫瀏覽」時，逐表比對變動指紋：
        # 指紋未變 → 不重載（避免無謂重建 700+ 列造成頓挫）；
        # 指紋改變 → 只重載該表，反映其他頁的增/修/刪。
        if not hasattr(self, "_sigs"):
            self._sigs = {}
        for key in ("task", "crim", "gen"):
            if not self._ui.get(key, {}).get("table"):
                continue
            try:
                sig = self._tableSignature(key)
            except Exception:
                # 比對失敗時保守重載，確保看到最新資料
                self._reload(key)
                continue
            if self._sigs.get(key) != sig:
                self._diffUpdate(key)
                self._sigs[key] = sig

        # 歸檔根目錄警示
        has_root = bool(getSetting(self.db_path, ARCHIVE_ROOT_KEY, "").strip())
        for key in ("crim", "gen"):
            lbl = self._arch_warn.get(key)
            if lbl:
                lbl.setVisible(not has_root)
