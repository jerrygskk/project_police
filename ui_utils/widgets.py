from PySide6.QtCore import Qt, QDate, QObject, QEvent, QTimer, QPointF
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QLabel,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PySide6.QtGui import QColor, QPainter, QTextLayout, QTextOption


def setupDateEditToToday(date_edit):
    """QDateEdit 開啟月曆後自動捲到今天所在的月份"""

    class _EventFilter(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show:
                QTimer.singleShot(10, _scroll)
            return False

    def _scroll():
        cal   = date_edit.calendarWidget()
        today = QDate.currentDate()
        if cal:
            if date_edit.date() == date_edit.minimumDate():
                date_edit.setDate(today)
                setattr(date_edit, '_jumped', True)
            cal.setCurrentPage(today.year(), today.month())

    ef = _EventFilter(date_edit)
    date_edit.installEventFilter(ef)
    date_edit._ef = ef   # 防止被 GC 回收


def setupDateEditCalendarOnly(date_edit):
    """供「可空白」QDateEdit 使用：
    欄位處於空白（date==minimumDate）時，打開月曆自動導到今天月份；
    但不填入日期、也不影響已有真實日期的欄位（打開時維持該日期月份）。
    注意：event filter 必須裝在 calendarWidget 上（其 Show 在每次彈窗開啟時觸發），
    裝在 date_edit 上只會在表單載入時觸發一次、彈窗開啟時不生效。
    """
    cal = date_edit.calendarWidget()
    if cal is None:
        return

    class _EventFilter(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show and \
               date_edit.date() == date_edit.minimumDate():
                today = QDate.currentDate()
                QTimer.singleShot(
                    0, lambda: cal.setCurrentPage(today.year(), today.month()))
            return False

    ef = _EventFilter(cal)
    cal.installEventFilter(ef)
    cal._calef = ef   # 防止被 GC 回收


def setupFilterCombo(combo, data_list):
    """
    設定 QComboBox 為可輸入即時篩選模式。
    data_list: [(id, name), ...]
    """
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.clear()
    combo.addItem("", None)
    for id_, name in data_list:
        combo.addItem(name, id_)

    names     = [name for _, name in data_list]
    completer = QCompleter(names, combo)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)

    # 修正 completer popup 黑色背景問題
    # dropdown 自動展開到最長選項的寬度
    fm = combo.fontMetrics()
    max_w = max((fm.horizontalAdvance(name) for _, name in data_list), default=0)
    max_w += 48  # padding + scrollbar
    combo.view().setMinimumWidth(max(max_w, combo.minimumWidth()))

    completer.popup().setStyleSheet("""
        QAbstractItemView {
            background-color: #ffffff;
            color: #1c1c1e;
            border: 1px solid #c6c6c8;
        }
        QAbstractItemView::item {
            background-color: #ffffff;
            color: #1c1c1e;
            padding: 4px 8px;
            min-height: 28px;
        }
        QAbstractItemView::item:hover {
            background-color: #e5e5ea;
            color: #1c1c1e;
        }
        QAbstractItemView::item:selected {
            background-color: #6e8fac;
            color: #ffffff;
        }
        QAbstractItemView::item:selected:hover {
            background-color: #5c7a9a;
            color: #ffffff;
        }
    """)

    def _onTextChanged(text):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("", None)
        for id_, name in data_list:
            if not text or text in name:
                combo.addItem(name, id_)
        combo.setEditText(text)
        combo.blockSignals(False)

    combo.lineEdit().textEdited.connect(_onTextChanged)


def refreshFilterCombo(combo, data_list):
    """
    重新載入 combo 的選項，保留目前選取。
    若原選取項目已不在新列表中（例如離職），自動回到空白。
    """
    current_data = combo.currentData()
    setupFilterCombo(combo, data_list)
    if current_data is not None:
        for i in range(combo.count()):
            if combo.itemData(i) == current_data:
                combo.setCurrentIndex(i)
                return
    # 找不到 → 保持空白（index 0）
    combo.setCurrentIndex(0)


# ── 表格整排 hover（自 tab_archive 抽出，通用） ───────────────
class RowHoverFilter(QObject):
    """追蹤滑鼠在 viewport 上的列號，供 RowHoverDelegate 使用。
    需存成屬性防 GC；在 table.viewport() 上 installEventFilter。"""
    def __init__(self, table):
        super().__init__(table)
        self._table = table
        self.row = -1

    def eventFilter(self, obj, event):
        t = self._table
        if obj is t.viewport():
            if event.type() == QEvent.MouseMove:
                idx = t.indexAt(event.pos())
                new = idx.row() if idx.isValid() else -1
                if new != self.row:
                    self.row = new
                    t.viewport().update()
            elif event.type() == QEvent.Leave:
                if self.row != -1:
                    self.row = -1
                    t.viewport().update()
        return False


class RowHoverDelegate(QStyledItemDelegate):
    """非選中列：整排 hover 時填 #eaf1f8。"""
    _HOVER_COLOR = QColor("#eaf1f8")

    def __init__(self, hover_filter, parent=None):
        super().__init__(parent)
        self._hf = hover_filter

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        is_selected = bool(opt.state & QStyle.State_Selected)
        if not is_selected and index.row() == self._hf.row:
            painter.fillRect(opt.rect, self._HOVER_COLOR)
            opt.state &= ~QStyle.State_MouseOver
        super().paint(painter, opt, index)


class TwoLineElideLabel(QLabel):
    """固定 2 行高度的標籤：
    - 一般文字 1～2 行正常顯示（中文逐字、長英數任意位置皆可斷行）
    - 超過 2 行時，第 2 行尾以 '…' 省略，完整內容放 tooltip
    - 高度固定為 2 行，永不往下長高、不橫向撐寬版面
    """
    MAX_LINES = 2

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = text or ""
        fm = self.fontMetrics()
        self.setFixedHeight(fm.lineSpacing() * self.MAX_LINES + 4)
        self.setToolTip(self._full)

    def setText(self, text):
        self._full = text or ""
        self.setToolTip(self._full)
        self.update()

    def text(self):
        return self._full

    def paintEvent(self, ev):
        p = fm = None
        try:
            p = QPainter(self)
            fm = self.fontMetrics()
            w = max(1, self.width())
            full = self._full
            if not full:
                return

            # 用 QTextLayout 找第 1 行斷點（允許任意位置斷行，長英數串才會斷）
            opt = QTextOption()
            opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            tl = QTextLayout(full, self.font())
            tl.setTextOption(opt)
            tl.beginLayout()
            line0 = tl.createLine()
            line0.setLineWidth(w)
            n0 = line0.textLength()
            tl.endLayout()

            ascent = fm.ascent()
            ls = fm.lineSpacing()

            text0 = full[:n0]
            p.drawText(0, ascent, text0)

            rest = full[n0:]
            if rest:
                if fm.horizontalAdvance(rest) > w:
                    rest = fm.elidedText(rest, Qt.TextElideMode.ElideRight, w)
                p.drawText(0, ls + ascent, rest)
        finally:
            if p is not None:
                p.end()
