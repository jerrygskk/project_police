from PySide6.QtCore import Qt, QDate, QObject, QEvent, QTimer
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QLabel,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PySide6.QtGui import QColor, QPainter, QTextLayout, QTextOption


def runWithBusy(parent, func, text="更新中，請稍候…", min_ms=350):
    """顯示無邊框「更新中」提示，同步執行 func（阻塞主執行緒）後自動關閉，回傳 func() 結果。

    重載在 GUI 主執行緒同步執行，事件迴圈被佔住，故先 show + repaint
    強制把提示畫出來，再跑 func；func 結束後於 finally 關閉提示。
    min_ms：最短顯示毫秒數，避免工作太快時提示一閃即逝看不到。
    """
    import time
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QApplication
    dlg = QDialog(parent)
    dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    dlg.setWindowModality(Qt.ApplicationModal)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(40, 30, 40, 30)
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lay.addWidget(lbl)
    dlg.setStyleSheet(
        "QDialog { background:#ffffff; border:1px solid #c6c6c8; border-radius:12px; }"
        "QLabel { color:#1c1c1e; font-size:15pt; font-weight:600; background:transparent; }"
    )
    dlg.adjustSize()
    if parent is not None:
        try:
            pg = parent.window().geometry()
            dlg.move(pg.center() - dlg.rect().center())
        except Exception:
            pass
    dlg.show()
    dlg.raise_()
    dlg.repaint()                  # frameless 視窗：強制立刻畫出來
    QApplication.processEvents()
    start = time.perf_counter()
    try:
        return func()
    finally:
        # 保證最短顯示時間，工作太快也能看到提示
        while (time.perf_counter() - start) * 1000 < min_ms:
            QApplication.processEvents()
            time.sleep(0.01)
        dlg.close()
        QApplication.processEvents()


def preserveScroll(table, func):
    """執行 func（重建／差異更新表格）前後保留垂直捲動位置，避免畫面跳回頂端。

    重建後 maximum 可能改變，還原值 clamp 到當下 maximum；autoResize 等
    延遲動作排在下一個事件迴圈，故還原也用 QTimer.singleShot(0) 排在其後。
    回傳 func() 的結果。
    """
    if table is None:
        return func()
    sb = table.verticalScrollBar()
    pos = sb.value() if sb else 0
    result = func()
    if sb:
        QTimer.singleShot(0, lambda b=sb, v=pos: b.setValue(min(v, b.maximum())))
    return result


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


def nullableDateKeyAction(is_blank, key, text):
    """可空白 QDateEdit 的鍵盤事件決策（純邏輯，便於單測）。

    欄位停在 minimumDate（空白）時，QDateEdit 顯示 specialValueText、收不到
    數字鍵編輯，使用者體感「鍵盤打不動」。本函式判斷該如何讓它離開特殊值：
      'forward' = 先跳今天，再讓此鍵落到段位上繼續編輯（數字鍵）
      'consume' = 先跳今天並消化此鍵，避免在今天之上再 ±1（上下／翻頁鍵）
      None      = 不介入（已有值，或非編輯鍵，照 Qt 原行為）
    """
    if not is_blank:
        return None
    if text and text.isdigit():
        return 'forward'
    if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
        return 'consume'
    return None


def setupNullableDateEdit(date_edit, special_text, on_blank_changed=None):
    """設定「可空白」QDateEdit，修掉空白哨兵的兩個互動雷：

    1. 空白（date==minimumDate）時鍵盤打不動 → 裝事件過濾器攔截數字／上下／
       翻頁鍵與滾輪，先跳今天離開特殊值再正常編輯，使用者怎麼亂點都不會卡死。
    2. 每次 dateChanged 都 setStyleSheet 重設樣式會重建內部 QLineEdit、打斷
       正在進行的鍵盤編輯 → 改成只在「空白↔有值」切換時才回呼 on_blank_changed
       （且延遲到事件處理完才換樣式，不干擾當下按鍵）。

    呼叫前若需自訂 minimumDate（如稽核頁 QDate(2000,1,1)），先自行 setMinimumDate。
    on_blank_changed(is_blank)：可選，由呼叫端據以換色／樣式（會在初始化先呼叫一次）。
    """
    date_edit.setSpecialValueText(special_text)
    date_edit.setDate(date_edit.minimumDate())   # 起始空白
    setupDateEditCalendarOnly(date_edit)         # 空白時開月曆導到今天月份

    # ── 只在「空白↔有值」切換時換樣式（避免每鍵重建 QLineEdit）──
    state = {'blank': date_edit.date() == date_edit.minimumDate()}

    def _onChanged(*_):
        is_blank = date_edit.date() == date_edit.minimumDate()
        if is_blank != state['blank']:
            state['blank'] = is_blank
            if on_blank_changed:
                # 延遲到當前事件處理完再換樣式，避免重建 QLineEdit 打斷按鍵
                QTimer.singleShot(0, lambda b=is_blank: on_blank_changed(b))

    date_edit.dateChanged.connect(_onChanged)
    if on_blank_changed:
        on_blank_changed(state['blank'])   # 初始狀態先上色

    # ── 鍵盤／滾輪離開特殊值 ──
    class _BlankEntryFilter(QObject):
        def eventFilter(self, obj, event):
            et = event.type()
            is_blank = date_edit.date() == date_edit.minimumDate()
            if et == QEvent.Type.KeyPress:
                action = nullableDateKeyAction(is_blank, event.key(), event.text())
                if action == 'forward':
                    date_edit.setDate(QDate.currentDate())
                    return False   # 讓數字鍵落到今天的段位上
                if action == 'consume':
                    date_edit.setDate(QDate.currentDate())
                    return True    # 消化掉，避免再 ±1
            elif et == QEvent.Type.Wheel and is_blank:
                date_edit.setDate(QDate.currentDate())
                return True
            return False

    ef = _BlankEntryFilter(date_edit)
    date_edit.installEventFilter(ef)
    date_edit._blankef = ef   # 防止被 GC 回收


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
        # 移除目前格焦點虛框（黑框/藍線），只保留選取底色
        opt.state &= ~QStyle.State_HasFocus
        super().paint(painter, opt, index)


class LinkCursorFilter(QObject):
    """純 item 連結欄（資料庫瀏覽／歸檔的編號欄）的滑鼠游標處理：
    滑到「可點擊的編號格」顯示手指游標，離開還原箭頭。
    可否點擊以該格字型是否帶底線判定（與 applyLinkStyle 同一來源），
    故權限切換 clickable 後游標自動跟著對，不需另外同步狀態。
    需存成屬性防 GC；在 table.viewport() 上 installEventFilter。"""
    def __init__(self, table, link_col):
        super().__init__(table)
        self._table = table
        self._col = link_col

    def eventFilter(self, obj, event):
        t = self._table
        if obj is t.viewport():
            if event.type() == QEvent.MouseMove:
                idx = t.indexAt(event.pos())
                hand = False
                if idx.isValid() and idx.column() == self._col:
                    it = t.item(idx.row(), self._col)
                    if it is not None and it.text() and it.font().underline():
                        hand = True
                t.viewport().setCursor(
                    Qt.PointingHandCursor if hand else Qt.ArrowCursor)
            elif event.type() == QEvent.Leave:
                t.viewport().setCursor(Qt.ArrowCursor)
        return False


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
