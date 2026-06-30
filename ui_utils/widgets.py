from PySide6.QtCore import Qt, QDate, QObject, QEvent, QTimer, Signal, QRegularExpression
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QLabel, QLineEdit, QCalendarWidget,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PySide6.QtGui import (
    QColor, QPainter, QTextLayout, QTextOption, QIcon,
    QRegularExpressionValidator,
)


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


def normalizeDateText(text):
    """把使用者輸入正規化成 `yyyy-MM-dd`（純邏輯，便於單測）。

    - 三段且皆數字（2025-1-3 / 2025-01-30）→ 補零成 2025-01-03
    - 否則抽出所有數字，剛好 8 碼 → 拆成 yyyy-MM-dd
      （容 20250130 / 2026-0125 / 2026/01/25 等混合寫法）
    - 仍無法判定 → 原樣回傳，交由 classifyNullableDate 判非法
    """
    t = (text or "").strip()
    if not t:
        return ""
    # 1) 年-月-日三段（允許單位數）→ 補零
    if "-" in t:
        parts = t.split("-")
        if len(parts) == 3 and all(p.isdigit() and p for p in parts):
            y, m, d = parts
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    # 2) 抽出所有數字，剛好 8 碼 → yyyy-MM-dd
    digits = "".join(ch for ch in t if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return t


def classifyNullableDate(text):
    """判定可空白日期輸入的狀態（純邏輯，便於單測）。

    回傳 (status, QDate|None)：
      'empty'   空字串              → (… , None)
      'valid'   合法且能 round-trip → (… , QDate)
      'invalid' 非空但不是合法日期  → (… , None)
    """
    t = (text or "").strip()
    if not t:
        return ('empty', None)
    norm = normalizeDateText(t)
    qd = QDate.fromString(norm, "yyyy-MM-dd")
    if qd.isValid() and qd.toString("yyyy-MM-dd") == norm:
        return ('valid', qd)
    return ('invalid', None)


_DATE_ERR_CSS = "QLineEdit { border: 2px solid #d9534f; }"


class NullableDateEdit(QLineEdit):
    """可空白日期框（治本版）：底層是 QLineEdit，不再用 QDateEdit 的 minimumDate
    哨兵。因此天生支援「整格清空 → 自由手打 2025-01-30」，不會被 fixup 還原、
    也不會冒 1752/1753 殘值。

    行為：
    - **手打**：直接輸入 `yyyy-MM-dd`（或連打 8 位數字，離開時自動補分隔）。
    - **月曆**：右側箭頭圖示開 `QCalendarWidget` popup 挑日。
    - **驗證**：離開欄位（focus-out / Enter）即判定；非空但非法 → 亮紅框。
      手打過程中不嘮叨（紅框只在離開時亮、再次編輯即收）。
    - **空白**：合法的「未填」狀態（必填與否由呼叫端決定）。

    對外 API（取代舊的 .date()/.minimumDate() 慣用法）：
      getDate()  -> QDate | None    （空白或非法皆 None）
      isBlank()  -> bool            （文字為空）
      hasError() -> bool            （非空且非法）
      setDate(QDate|None)           （None/非法＝清空）
      validateNow()                 （送出前強制驗證並亮紅框）
      changed   訊號                （離開欄位／挑日／清空後發出）
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_css = ""        # 呼叫端可注入的基底樣式（如稽核頁 12pt）
        self._cal = None           # 月曆 popup（延遲建立）
        self.setMaxLength(10)      # yyyy-MM-dd
        # 鍵盤層只放行數字與 - / 分隔符；英文字母與其他符號打不進來
        # （只擋使用者按鍵；setText/月曆挑日等程式設值不受影響）
        self.setValidator(QRegularExpressionValidator(
            QRegularExpression(r"[0-9/\-]*"), self))
        # 右側箭頭圖示：點擊開月曆
        self._cal_action = self.addAction(
            QIcon(":/arrow.svg"), QLineEdit.TrailingPosition)
        self._cal_action.triggered.connect(self._openCalendar)
        self.textEdited.connect(lambda *_: self._showError(False))   # 編輯中收紅框
        self.editingFinished.connect(self.validateNow)               # 離開即驗證
        self._applyStyle(False)

    # ── 樣式 ──────────────────────────────────────────────────
    def setBaseCss(self, css):
        """注入基底 QLineEdit 樣式（與紅框錯誤態共存，不互相洗掉）。"""
        self._base_css = css or ""
        self._applyStyle(self._error_shown())

    def _error_shown(self):
        return _DATE_ERR_CSS in (self.styleSheet() or "")

    def _applyStyle(self, error):
        border = "border: 2px solid #d9534f;" if error else ""
        self.setStyleSheet(f"QLineEdit {{ {self._base_css} {border} }}")

    def _showError(self, error):
        self._applyStyle(error)

    # ── 驗證 ──────────────────────────────────────────────────
    def validateNow(self):
        status, qd = classifyNullableDate(self.text())
        if status == 'valid':
            canon = qd.toString("yyyy-MM-dd")
            if self.text() != canon:
                self.setText(canon)   # 正規化顯示（不再觸發 editingFinished）
        self._showError(status == 'invalid')
        self.changed.emit()

    # ── 對外查詢 ──────────────────────────────────────────────
    def getDate(self):
        status, qd = classifyNullableDate(self.text())
        return qd if status == 'valid' else None

    def isBlank(self):
        return not self.text().strip()

    def hasError(self):
        return classifyNullableDate(self.text())[0] == 'invalid'

    # ── 設值 ──────────────────────────────────────────────────
    def setDate(self, qdate):
        if qdate is None or not qdate.isValid():
            self.setText("")
        else:
            self.setText(qdate.toString("yyyy-MM-dd"))
        self._showError(False)
        self.changed.emit()

    def clear(self):
        super().clear()
        self._showError(False)
        self.changed.emit()

    # ── 月曆 popup ────────────────────────────────────────────
    def _openCalendar(self):
        if self._cal is None:
            self._cal = QCalendarWidget(self)
            self._cal.setWindowFlags(Qt.Popup)
            # 不設 gridVisible：維持與其他日期欄一致的無格線外觀
            # 關掉最左側週數欄（垂直表頭）
            self._cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
            self._cal.clicked.connect(self._onPick)
            self._cal.activated.connect(self._onPick)
        status, qd = classifyNullableDate(self.text())
        self._cal.setSelectedDate(qd if status == 'valid' else QDate.currentDate())
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._cal.move(pos)
        self._cal.show()

    def _onPick(self, qd):
        if self._cal:
            self._cal.hide()
        self.setText(qd.toString("yyyy-MM-dd"))
        self.validateNow()


def setupNullableDateEdit(date_edit, special_text, on_blank_changed=None):
    """設定可空白日期框：填入空白提示文字（灰字 placeholder）。

    保留舊簽名以相容既有呼叫端；`on_blank_changed` 不再需要（placeholder 自帶
    灰字、紅框由元件自管），保留參數僅為相容，會被忽略。
    """
    date_edit.setPlaceholderText(special_text)


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
