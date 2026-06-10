from PySide6.QtCore import Qt, QDate, QObject, QEvent, QTimer
from PySide6.QtWidgets import QComboBox, QCompleter


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
