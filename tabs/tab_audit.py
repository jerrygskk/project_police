"""
tab_audit.py — 操作紀錄檢視（Tab7）

唯讀，僅管理者（admin）可檢視；非管理者顯示遮罩，導引至設定頁登入。
資料來源 Audit_Log；detail 解析 `[類別][動作]內容` 拆三欄顯示。
全量載入後以 setRowHidden 做篩選（比照資料庫瀏覽頁）。
"""
import re
import csv
from datetime import datetime

from PySide6.QtWidgets import (
    QVBoxLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QDateEdit, QComboBox, QLineEdit, QPushButton, QLabel,
    QHeaderView, QFileDialog, QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from lib.base_tab import BaseTab
from lib.db_utils import getResourcePath, loadUi, msgInfo, msgWarning
from lib.auth_manager import AuthManager
from ui_utils import setupDateEditCalendarOnly, runWithBusy


# 身分碼 → 中文
ROLE_ZH = {'admin': '管理者', 'archive': '歸檔管理', 'user': '一般使用者'}
# detail 類別（與 db_utils.buildDetail 一致）
CATEGORIES = ['交辦', '刑案', '一般', '人員', '部門', '案類', '歸檔', '系統']
# 需以紅字標示的動作
DANGER_ACTIONS = {'刪除', '重置', '登入失敗'}

# 日期空白哨兵（= minimumDate），代表「不限」
_BLANK_DATE = QDate(2000, 1, 1)

_DETAIL_RE = re.compile(r'^\[([^\]]*)\]\[([^\]]*)\](.*)$', re.S)


def parseDetail(detail):
    """`[類別][動作]內容` → (類別, 動作, 內容)。不符格式時回 ('', '', 原字串)。"""
    if not detail:
        return '', '', ''
    m = _DETAIL_RE.match(detail)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return '', '', detail


# 欄位索引
COL_TS, COL_ROLE, COL_CAT, COL_ACT, COL_CONTENT, COL_OP = range(6)
HEADERS = ['時間', '身分', '類別', '動作', '內容', '對象人']


class TabAudit(BaseTab):

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return
        widget = loadUi(getResourcePath("layouts/Layout8.ui"))
        if not widget:
            return
        inner = widget.centralWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)
        self._inner = inner

        # 權限牆：page 0 遮罩 / page 1 內容
        self._outer_stack = inner.findChild(QStackedWidget, "outer_stack")

        # 元件
        self._from  = inner.findChild(QDateEdit,   "audit_from")
        self._to    = inner.findChild(QDateEdit,   "audit_to")
        self._role  = inner.findChild(QComboBox,   "audit_role")
        self._cat   = inner.findChild(QComboBox,   "audit_cat")
        self._kw    = inner.findChild(QLineEdit,   "audit_kw")
        self._btn_export = inner.findChild(QPushButton, "btn_export")
        self._table = inner.findChild(QTableWidget, "audit_table")
        self._count = inner.findChild(QLabel,      "lbl_count")

        self._initDateEdits()
        self._initCombos()
        self._initTable()

        # 全量資料快取（list of dict）
        self._rows = []

        # 事件
        self._from.dateChanged.connect(lambda *_: self._applyFilter())
        self._to.dateChanged.connect(lambda *_: self._applyFilter())
        self._role.currentIndexChanged.connect(lambda *_: self._applyFilter())
        self._cat.currentIndexChanged.connect(lambda *_: self._applyFilter())
        self._kw.textChanged.connect(lambda *_: self._applyFilter())
        if self._btn_export:
            self._btn_export.clicked.connect(self._export)

        # 身分牆
        self._applyGate()
        AuthManager.instance().role_changed.connect(self._applyGate)

    # ── 初始化 ────────────────────────────────────────────────
    def _initDateEdits(self):
        for de in (self._from, self._to):
            de.setMinimumDate(_BLANK_DATE)
            de.setSpecialValueText(" ")      # 空白＝不限
            de.setDate(_BLANK_DATE)          # 預設皆不限（顯示全部）
            setupDateEditCalendarOnly(de)

    def _initCombos(self):
        self._role.addItem("全部", None)
        for code in ('admin', 'archive', 'user'):
            self._role.addItem(ROLE_ZH[code], code)
        self._cat.addItem("全部", None)
        for c in CATEGORIES:
            self._cat.addItem(c, c)

    def _initTable(self):
        t = self._table
        t.setColumnCount(len(HEADERS))
        t.setHorizontalHeaderLabels(HEADERS)
        vh = t.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(30)      # 固定列高 30，與資料庫瀏覽頁一致
        t.setWordWrap(False)              # 不換行（內容單行省略，完整內容放 tooltip）
        t.setSelectionMode(QAbstractItemView.NoSelection)   # 唯讀，不需選取反白
        t.setFocusPolicy(Qt.NoFocus)                        # 去焦點虛線框
        t.setShowGrid(False)              # 無格線，只留列底細線（比照資料庫瀏覽頁）
        t.setAlternatingRowColors(True)
        # 與資料庫瀏覽頁一致的 Apple HIG 表格樣式（無格線、淺灰交錯、表頭灰底粗線）
        t.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f2f2f7;
                border: none;
                border-top: 1px solid #c6c6c8;
                font-size: 13pt;
            }
            QHeaderView::section {
                background-color: #f2f2f7;
                color: #3a3a3c;
                font-weight: 600;
                font-size: 13pt;
                padding: 4px 4px;
                border: none;
                border-bottom: 2px solid #c6c6c8;
                border-right: 1px solid #e5e5ea;
            }
            QTableWidget::item {
                padding: 2px 6px;
                border-bottom: 1px solid #e5e5ea;
            }
        """)
        hdr = t.horizontalHeader()
        for c in (COL_TS, COL_ROLE, COL_CAT, COL_ACT, COL_OP):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(COL_CONTENT, QHeaderView.Stretch)

    # ── 身分牆 ────────────────────────────────────────────────
    def _applyGate(self, _role=None):
        stack = getattr(self, "_outer_stack", None)
        if not stack:
            return
        is_admin = AuthManager.instance().is_admin()
        stack.setCurrentIndex(1 if is_admin else 0)
        if is_admin:
            self._load()

    def on_activated(self):
        # 每次切入都重套牆並（若已登入）重載，反映最新紀錄
        self._applyGate()

    # ── 載入 ──────────────────────────────────────────────────
    def _load(self):
        def _do():
            rows = []
            try:
                conn = self._getConn()
                cur = conn.execute(
                    "SELECT ts, role, operator, detail FROM Audit_Log "
                    "ORDER BY log_id DESC")
                for ts, role, operator, detail in cur.fetchall():
                    cat, act, content = parseDetail(detail or "")
                    rows.append({
                        "ts": ts or "",
                        "date": (ts or "")[:10],
                        "role": role or "",
                        "cat": cat,
                        "act": act,
                        "content": content,
                        "operator": operator or "",
                    })
                conn.close()
            except Exception as e:
                msgWarning("讀取失敗", f"載入操作紀錄失敗：{e}")
            return rows

        self._rows = runWithBusy(self._inner, _do, text="載入中，請稍候…")
        self._populate()
        self._applyFilter()

    def _populate(self):
        t = self._table
        t.setRowCount(0)
        t.setRowCount(len(self._rows))
        red  = QColor("#c0392b")
        blue = QColor("#185fa5")
        gray = QColor("#8e8e93")
        for r, row in enumerate(self._rows):
            role_zh = ROLE_ZH.get(row["role"], row["role"] or "")
            danger = row["act"] in DANGER_ACTIONS
            act_text = ("● " + row["act"]) if danger else row["act"]
            cells = [row["ts"], role_zh, row["cat"], act_text,
                     row["content"], row["operator"]]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if c == COL_CONTENT and text:
                    item.setToolTip(text)     # 內容單行省略，完整內容看 tooltip
                # 狀態色（交給 setForeground，勿用 ::item{color}）
                if c == COL_ACT and danger:
                    item.setForeground(red)
                elif c == COL_ROLE:
                    if row["role"] == 'admin':
                        item.setForeground(blue)
                    elif row["role"] == 'archive':
                        item.setForeground(QColor("#6e8fac"))
                    elif not row["role"]:
                        item.setForeground(gray)
                t.setItem(r, c, item)

    # ── 篩選 ──────────────────────────────────────────────────
    def _applyFilter(self):
        if not hasattr(self, "_rows"):
            return
        d_from = self._from.date()
        d_to   = self._to.date()
        from_s = d_from.toString("yyyy-MM-dd") if d_from != _BLANK_DATE else None
        to_s   = d_to.toString("yyyy-MM-dd")   if d_to   != _BLANK_DATE else None
        role_f = self._role.currentData()
        cat_f  = self._cat.currentData()
        kw     = (self._kw.text() or "").strip()

        shown = 0
        for r, row in enumerate(self._rows):
            ok = True
            if from_s and (not row["date"] or row["date"] < from_s):
                ok = False
            if ok and to_s and (not row["date"] or row["date"] > to_s):
                ok = False
            if ok and role_f is not None and row["role"] != role_f:
                ok = False
            if ok and cat_f is not None and row["cat"] != cat_f:
                ok = False
            if ok and kw and (kw not in row["content"] and kw not in row["operator"]):
                ok = False
            self._table.setRowHidden(r, not ok)
            if ok:
                shown += 1

        if self._count:
            self._count.setText(f"顯示 {shown} ／ 共 {len(self._rows)} 筆")

    # ── 匯出 CSV ──────────────────────────────────────────────
    def _export(self):
        # 匯出目前篩選後（可見）的列
        visible = [row for r, row in enumerate(self._rows)
                   if not self._table.isRowHidden(r)]
        if not visible:
            msgInfo("提示", "目前沒有可匯出的紀錄。")
            return
        default = f"操作紀錄_{datetime.now().strftime('%Y%m%d')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self._inner, "匯出 CSV", default, "CSV 檔案 (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(HEADERS)
                for row in visible:
                    w.writerow([
                        row["ts"], ROLE_ZH.get(row["role"], row["role"]),
                        row["cat"], row["act"], row["content"], row["operator"],
                    ])
            msgInfo("匯出完成", f"已匯出 {len(visible)} 筆至：\n{path}")
        except Exception as e:
            msgWarning("匯出失敗", f"寫入檔案失敗：{e}")

    # ── BaseTab 介面 ──────────────────────────────────────────
    def get_focus_widget(self):
        return self._kw if getattr(self, "_kw", None) else None
