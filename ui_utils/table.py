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
    "刑案編號":      70,
    "受理/查獲日期": 115,
    "承辦人員":     110,
    "受理人員":      90,
    "報案人":        80,
    "發文分類":      95,
    # 一般
    "陳報編號":      70,
    "承辦人":        90,
    "陳報人":       120,
    "主承辦人":     120,
}

# 動態量欄位的 padding（欄位內容寬度 + PAD）
_PAD = 24


def _measureColWidths(table, fm):
    stretch_col = table.property("stretch_col")
    widths = {}
    for col in range(table.columnCount()):
        if col == 0 and table.columnWidth(0) <= 32:
            widths[col] = 32
            continue
        hdr_item = table.horizontalHeaderItem(col)
        hdr_text = hdr_item.text() if hdr_item else ""

        if hdr_text in FIXED_COL_WIDTHS:
            widths[col] = FIXED_COL_WIDTHS[hdr_text]
            continue

        best = fm.horizontalAdvance(hdr_text) + _PAD
        for row in range(table.rowCount()):
            item = table.item(row, col)
            if item:
                w = fm.horizontalAdvance(item.text()) + _PAD
                if w > best:
                    best = w
        widths[col] = best
    return widths, stretch_col


def autoResizeTable(table):
    if table.property("user_resized"):
        return

    fm = QFontMetrics(table.font())
    widths, stretch_col = _measureColWidths(table, fm)

    available = table.viewport().width()
    if available <= 0:
        QTimer.singleShot(100, lambda t=table: autoResizeTable(t))
        return

    usable      = int(available * 0.99)
    other_total = sum(w for c, w in widths.items() if c != stretch_col)
    stretch_min = max(widths.get(stretch_col, 80), 60)

    if other_total + stretch_min > usable:
        for col, w in widths.items():
            table.setColumnWidth(col, w)
    else:
        stretch_w = usable - other_total
        for col, w in widths.items():
            table.setColumnWidth(col, stretch_w if col == stretch_col else w)


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


def setupPreviewTable(table, headers, row_height=30):
    """套用 Apple HIG 風格表格樣式，並設定欄位標題"""
    table.setColumnCount(len(headers))
    for i, h in enumerate(headers):
        table.setHorizontalHeaderItem(i, QTableWidgetItem(h))

    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setDefaultSectionSize(80)

    stretch_col = 2 if headers[0] == "" else 1
    if headers[0] == "":
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 32)

    # 行高
    table.verticalHeader().setDefaultSectionSize(row_height)

    table.setProperty("stretch_col",  stretch_col)
    table.setProperty("user_resized", False)
    table.setProperty("init_done",    False)

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
            color: #1c1c1e;
            border-bottom: 1px solid #e5e5ea;
        }
        QTableWidget::item:selected {
            background-color: #007aff;
            color: #ffffff;
        }
        QTableWidget::item:selected:!active {
            background-color: #d1d1d6;
            color: #1c1c1e;
        }
    """)
