from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QWidget, QHBoxLayout
)
from PySide6.QtGui import QFontMetrics


# 固定寬度欄位（格式固定，不需動態量）
FIXED_COL_WIDTHS = {
    # 交辦單
    "交辦單編號":    90,
    "限辦日期":     110,
    "發文日期":     110,
    "收文日期":     110,
    "業務組":        80,
    "所承辦人":     120,
    "收文人員":     120,
    # 刑案
    "編號":          56,
    "狀態":          48,
    "案類":         152,
    "承辦人":        72,
    "受理人":        72,
    "報案人":        72,
    "日期":          80,
    # 一般
    "業務單位":      88,
    "分類":          56,
}

# 動態量欄位的 padding（欄位內容寬度 + PAD）
_PAD = 24


def _measureColWidths(table, fm, fixed_overrides=None):
    stretch_col = table.property("stretch_col")
    cap_mode    = table.property("cap_mode")   # True：FIXED_COL_WIDTHS 當上限，False：當固定值
    overrides   = fixed_overrides or {}
    widths = {}
    for col in range(table.columnCount()):
        if col == 0 and table.columnWidth(0) <= 32:
            widths[col] = 32
            continue
        hdr_item = table.horizontalHeaderItem(col)
        hdr_text = hdr_item.text() if hdr_item else ""

        # 量出內容實際寬度
        best = fm.horizontalAdvance(hdr_text) + _PAD
        for row in range(table.rowCount()):
            item = table.item(row, col)
            if item:
                w = fm.horizontalAdvance(item.text()) + _PAD
                if w > best:
                    best = w

        # fixed_overrides 優先（固定上限）
        if hdr_text in overrides:
            widths[col] = min(best, overrides[hdr_text]) if cap_mode else overrides[hdr_text]
            continue

        # FIXED_COL_WIDTHS：cap_mode 下當上限，否則當固定值
        if hdr_text in FIXED_COL_WIDTHS:
            widths[col] = min(best, FIXED_COL_WIDTHS[hdr_text]) if cap_mode else FIXED_COL_WIDTHS[hdr_text]
            continue

        widths[col] = best
    return widths, stretch_col


def autoResizeTable(table):
    if table.property("user_resized"):
        return

    fm             = QFontMetrics(table.font())
    fixed_overrides = table.property("fixed_overrides") or {}
    widths, stretch_col = _measureColWidths(table, fm, fixed_overrides)

    available = table.viewport().width()
    if available <= 0:
        QTimer.singleShot(100, lambda t=table: autoResizeTable(t))
        return

    usable      = int(available * 0.99)
    other_total = sum(w for c, w in widths.items() if c != stretch_col)
    stretch_min = max(widths.get(stretch_col, 80), 60)

    # 暫時關閉 init_done，避免 setColumnWidth 觸發 sectionResized 誤設 user_resized
    table.setProperty("init_done", False)
    if other_total + stretch_min > usable:
        for col, w in widths.items():
            table.setColumnWidth(col, w)
    else:
        stretch_w = usable - other_total
        for col, w in widths.items():
            table.setColumnWidth(col, stretch_w if col == stretch_col else w)
    table.setProperty("init_done", True)


def setDocIdLinkCell(table, row, col, doc_id, on_click, clickable=True):
    """
    在表格 (row, col) 放一個編號欄。
    clickable=True  → 顯示超連結，點擊觸發 on_click(row, doc_id)
    clickable=False → 純文字，不可點擊
    權限控管時，呼叫端自行計算 clickable 值再傳入，此函式不需知道權限邏輯。
    """
    from PySide6.QtWidgets import QLabel, QTableWidgetItem
    # 同格的 item 與 cellWidget 各自獨立、可並存：切換前先清掉另一種表示，
    # 否則 user↔admin 來回切會留下純文字與連結兩個數字疊在一起
    if clickable and doc_id:
        if table.item(row, col) is not None:
            table.takeItem(row, col)
        lbl = QLabel(f'<a href="{doc_id}" style="color:#4A7FA5;">{doc_id}</a>')
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setOpenExternalLinks(False)
        lbl.linkActivated.connect(lambda link, r=row: on_click(r, link))
        table.setCellWidget(row, col, lbl)
    else:
        if table.cellWidget(row, col) is not None:
            table.removeCellWidget(row, col)
        item = QTableWidgetItem(doc_id or "")
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)


def makeDeleteBtn(callback):
    btn = QPushButton("✕")
    btn.setObjectName("deleteBtn")
    btn.setFixedSize(18, 18)
    btn.clicked.connect(callback)
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.addWidget(btn)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(2, 2, 2, 2)
    return container, btn


def refreshDeleteBtns(table, enabled, col=0):
    """逐列切換刪除鈕的啟用狀態（身分變更時即時 greyout/還原）。
    刪除鈕由 makeDeleteBtn 建立、包在 cellWidget 容器內、objectName='deleteBtn'。"""
    for r in range(table.rowCount()):
        cont = table.cellWidget(r, col)
        if cont:
            btn = cont.findChild(QPushButton, "deleteBtn")
            if btn:
                btn.setEnabled(enabled)


def setupPreviewTable(table, headers, row_height=30, stretch_col=None, fixed_overrides=None, cap_mode=False):
    """
    套用 Apple HIG 風格表格樣式，並設定欄位標題。

    stretch_col:
        指定哪一欄自動撐滿剩餘空間。
        預設：headers[0]=="" 時為 col 2，否則為 col 1。

    fixed_overrides:
        dict，格式 {"欄位名稱": 寬度}。
        用於當同名欄位在不同表格需要不同寬度時，
        優先於 FIXED_COL_WIDTHS 套用，不影響其他表格。
        例如：一般陳報「陳報主旨」固定 184px，但刑案「陳報主旨」仍 stretch。
    """
    table.setColumnCount(len(headers))
    for i, h in enumerate(headers):
        table.setHorizontalHeaderItem(i, QTableWidgetItem(h))

    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setDefaultSectionSize(80)

    if stretch_col is None:
        stretch_col = 2 if headers[0] == "" else 1
    if headers[0] == "":
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 32)

    # 行高
    table.verticalHeader().setDefaultSectionSize(row_height)

    table.setProperty("stretch_col",     stretch_col)
    table.setProperty("user_resized",    False)
    table.setProperty("init_done",       False)
    table.setProperty("fixed_overrides", fixed_overrides or {})
    table.setProperty("cap_mode",        cap_mode)

    def _onSectionResized(idx, old_w, new_w, t=table, sc=stretch_col):
        if t.property("init_done") and idx != sc:
            t.setProperty("user_resized", True)

    hdr.sectionResized.connect(_onSectionResized)
    QTimer.singleShot(500, lambda t=table: t.setProperty("init_done", True))
    QTimer.singleShot(200, lambda t=table: autoResizeTable(t))

    hdr.setSectionsMovable(False)
    hdr.setSectionsClickable(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    table.setStyleSheet("""
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
            padding: 2px 4px;
            border-bottom: 1px solid #e5e5ea;
        }
        QTableWidget::item:selected {
            background-color: #ccdaeb;
            color: #1c1c1e;
        }
        QTableWidget::item:selected:!active {
            background-color: #d1d1d6;
            color: #1c1c1e;
        }
    """)
