from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout, QTabWidget, QComboBox, QLineEdit, QPushButton,
    QCheckBox, QLabel, QTableWidget, QTableWidgetItem,
)
from PySide6.QtGui import QColor

from lib.base_tab import BaseTab
from lib.db_utils import getResourcePath, loadUi, msgCritical
from ui_utils import (
    setupPreviewTable, autoResizeTable, setDocIdLinkCell,
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
    {"header": "編號",     "view_col": "編號",     "slim": True,  "link": True,  "search": True, "w": 64},
    {"header": "所承辦人", "view_col": "所承辦人", "slim": True,  "search": True, "w": 120},
    {"header": "交辦事由", "view_col": "交辦事由", "slim": True,  "search": True, "stretch": True, "w": 240},
    {"header": "業務組",   "view_col": "業務組",   "slim": True,  "search": True, "w": 80},
    {"header": "狀態",     "view_col": "狀態",     "slim": True,  "color": True, "search": True, "w": 212},
    {"header": "限辦日期", "view_col": "限辦日期", "slim": True,  "search": True, "w": 140},
    {"header": "發文日期", "view_col": "發文日期", "slim": True,  "search": True, "w": 140},
    {"header": "收文日期", "view_col": "收文日期", "slim": False, "search": True, "w": 140},
    {"header": "收文人員", "view_col": "收文人員", "slim": False, "search": True, "w": 120},
    {"header": "送文人員", "view_col": "送文人員", "slim": False, "search": True, "w": 120},
    {"header": "紀錄時間", "view_col": "紀錄時間", "slim": False, "search": False, "w": 240},
]

CRIM_COLS = [
    {"header": "送文編號",    "view_col": "送文編號",    "slim": True,  "link": True,  "search": True, "w": 80},
    {"header": "主承辦人",    "view_col": "主承辦人",    "slim": True,  "search": True, "w": 120},
    {"header": "案類",        "view_col": "案類",        "slim": True,  "search": True, "w": 200},
    {"header": "嫌疑人/案由", "view_col": "嫌疑人_案由", "slim": True,  "search": True, "stretch": True, "w": 240},
    {"header": "發文分類",    "view_col": "發文分類",    "slim": True,  "search": True, "w": 96, "map": "status"},
    {"header": "陳報日期",    "view_col": "陳報日期",    "slim": True,  "search": True, "w": 140},
    {"header": "受理日期",    "view_col": "受理日期",    "slim": True,  "search": True, "w": 140},
    {"header": "送文人員",    "view_col": "送文人員",    "slim": False, "search": True, "w": 120},
    {"header": "報案人",      "view_col": "報案人",      "slim": False, "search": True, "w": 130},
    {"header": "受理人",      "view_col": "受理人",      "slim": False, "search": True, "w": 120},
    {"header": "紙本",        "view_col": "紙本",        "slim": False, "search": False, "w": 56},
    {"header": "電子檔",      "view_col": "電子檔",      "slim": False, "search": False, "w": 64},
]

GEN_COLS = [
    {"header": "送文編號", "view_col": "送文編號", "slim": True,  "link": True,  "search": True, "w": 80},
    {"header": "陳報人",   "view_col": "陳報人",   "slim": True,  "search": True, "w": 120},
    {"header": "陳報主旨", "view_col": "陳報主旨", "slim": True,  "search": True, "stretch": True, "w": 240},
    {"header": "業務單位", "view_col": "業務單位", "slim": True,  "search": True, "w": 96},
    {"header": "分類",     "view_col": "分類",     "slim": True,  "search": True, "w": 96, "map": "cat"},
    {"header": "陳報日期", "view_col": "陳報日期", "slim": True,  "search": True, "w": 140},
    {"header": "送文人員", "view_col": "送文人員", "slim": False, "search": True, "w": 120},
    {"header": "紙本",     "view_col": "紙本",     "slim": False, "search": False, "w": 56},
    {"header": "電子檔",   "view_col": "電子檔",   "slim": False, "search": False, "w": 64},
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
        "dialog": CriminalEditDialog,
    },
    "gen": {
        "cols": GEN_COLS, "view": "View_General_Full",
        "base": "Document_General", "proc_fk": "processor_id", "id_col": "送文編號",
        "dialog": GeneralEditDialog,
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
            }

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
            # 即時搜尋（防抖 200ms，避免每按一鍵就重載 700+ 列造成卡頓）
            timer = QTimer(u["kw"])
            timer.setSingleShot(True)
            timer.setInterval(200)
            timer.timeout.connect(lambda k=key: self._reload(k))
            self._ui[key]["_debounce"] = timer
            u["kw"].textChanged.connect(lambda _, t=timer: t.start())
        if u["scope"]:
            u["scope"].currentIndexChanged.connect(lambda _, k=key: self._reload(k))
        if u["full"]:
            u["full"].toggled.connect(lambda _, k=key: self._onToggleFull(k))
            self._styleSegmented(key)

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

    def _onToggleFull(self, key):
        self._reload(key)

    # ── 目前模式要顯示的欄位清單 ────────────────────────────
    def _visibleCols(self, key):
        full = self._ui[key]["full"].isChecked() if self._ui[key]["full"] else False
        return [c for c in TABLE_META[key]["cols"] if full or c.get("slim")]

    # ── 主載入 / 搜尋 ───────────────────────────────────────
    def _reload(self, key):
        meta = TABLE_META[key]
        u = self._ui[key]
        table = u["table"]
        if not table:
            return

        cols = self._visibleCols(key)
        headers = [c["header"] for c in cols]
        stretch_idx = next((i for i, c in enumerate(cols) if c.get("stretch")), None)

        # 固定欄寬。長文字欄（stretch）也給一個 w 當「最小寬」，
        # 避免 autoResizeTable 量到超長內容（如 36 字事由）而撐爆整欄、
        # 退化成橫向捲動。給最小寬後會走「stretch = 剩餘空間」分支，
        # 超出部分由 QTableWidget 自動截斷成「…」，全文以 tooltip 呈現。
        fixed_overrides = {c["header"]: c["w"] for c in cols if c.get("w")}

        # 建立表頭
        setupPreviewTable(
            table, headers,
            stretch_col=stretch_idx if stretch_idx is not None else 1,
            fixed_overrides=fixed_overrides,
            cap_mode=False,
        )

        # 查詢資料（含底層承辦人 is_active）
        try:
            rows = self._query(key)
        except Exception as e:
            msgCritical("DB錯誤", f"載入資料失敗：{e}")
            return

        kw = (u["kw"].text() or "").strip() if u["kw"] else ""
        scope_col = u["scope"].currentData() if u["scope"] else None

        # 搜尋欄位集合
        if scope_col:
            search_cols = [scope_col]
        else:
            search_cols = [c["view_col"] for c in meta["cols"] if c.get("search")]

        id_col = meta["id_col"]
        visible_view_cols = {c["view_col"] for c in cols}

        hit_hidden = False
        table.setRowCount(0)
        shown = 0
        for r in rows:

            # 關鍵字過濾
            matched_col = None
            if kw:
                ok = False
                for vc in search_cols:
                    val = r.get(vc)
                    if val is not None and kw in str(val):
                        ok = True
                        matched_col = vc
                        break
                if not ok:
                    continue

            if kw and matched_col and matched_col not in visible_view_cols:
                hit_hidden = True

            self._appendRow(key, table, cols, r, id_col)
            shown += 1

        QTimer.singleShot(0, lambda t=table: autoResizeTable(t))
        self._updateFooter(key, shown, kw, hit_hidden)

    def _query(self, key):
        """回傳 dict 列表，含 View 全欄 + _proc_active。"""
        meta = TABLE_META[key]
        sql = f"""
            SELECT v.*, COALESCE(p.is_active, 1) AS _proc_active
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

    def _appendRow(self, key, table, cols, r, id_col):
        pos = table.rowCount()
        table.insertRow(pos)
        inactive = not r["_proc_active"]

        for c_idx, c in enumerate(cols):
            val = r.get(c["view_col"])
            text = "" if val is None else str(val)

            # 套用顯示對照（發文分類 / 分類）：DB 原始值 → 短詞，
            # 與陳報頁共用 BaseTab 的 _STATUS_MAP / _CAT_MAP。
            mkey = c.get("map")
            if mkey and text:
                table_map = self._STATUS_MAP if mkey == "status" else self._CAT_MAP
                text = table_map.get(text, text)

            if c.get("link"):
                doc_id = str(r.get(id_col) or "")
                setDocIdLinkCell(
                    table, pos, c_idx, doc_id,
                    lambda row, did, k=key: self._onEdit(k, row, did),
                    clickable=True,
                )
                continue

            item = QTableWidgetItem(text)
            # 長文字欄（stretch）：左對齊較好讀，並掛 tooltip 顯示截斷的全文
            if c.get("stretch"):
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if text:
                    item.setToolTip(text)
            else:
                item.setTextAlignment(Qt.AlignCenter)

            if c.get("color"):
                col = _statusColor(text)
                if col:
                    item.setForeground(col)
            elif inactive:
                # 承辦人已停用 → 整列文字標灰
                item.setForeground(QColor("#aeaeb2"))

            table.setItem(pos, c_idx, item)

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

    # ── 點編號開 EditDialog ─────────────────────────────────
    def _onEdit(self, key, row, doc_id):
        dialog_cls = TABLE_META[key]["dialog"]
        dlg = dialog_cls(self.db_path, doc_id, self._ui[key]["table"])
        if dlg.exec():
            # 編輯後簡單重載整張表（瀏覽頁資料量可接受）
            self._reload(key)

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
                self._reload(key)
                self._sigs[key] = sig
