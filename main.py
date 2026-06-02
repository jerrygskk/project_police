import sys
import os
import sqlite3
from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QApplication, QDialog, QMessageBox, QTableWidgetItem, QHeaderView,
    QTableWidget, QPushButton, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QComboBox, QDateEdit, QCompleter, QCheckBox
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QDate
from PySide6.QtGui import QFont


# ──────────────────────────────────────────────
# 工具函式
# ──────────────────────────────────────────────
def getResourcePath(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def loadUi(path):
    """載入 .ui 檔案，回傳 widget，失敗回傳 None"""
    f = QFile(path)
    if not f.exists():
        QMessageBox.critical(None, "錯誤", f"找不到 UI 檔案: {path}")
        return None
    f.open(QFile.ReadOnly)
    widget = QUiLoader().load(f)
    f.close()
    return widget


def calcOverdue(deadlineStr, dispatchStr):
    """計算逾期狀態字串"""
    if not deadlineStr or str(deadlineStr) in ("", "None", "nan"):
        return "免覆"
    try:
        today    = datetime.now().date()
        deadline = datetime.strptime(str(deadlineStr), "%Y-%m-%d").date()
        dispatched = dispatchStr and str(dispatchStr) not in ("", "None", "nan")
        if dispatched:
            d = datetime.strptime(str(dispatchStr), "%Y-%m-%d").date()
            diff = (d - deadline).days
            return "已發文" if diff <= 0 else f"已發文（逾期 {diff} 日）"
        diff = (deadline - today).days
        if diff > 0:  return f"剩餘 {diff} 日"
        if diff == 0: return "今日到期"
        return f"逾期 {-diff} 日"
    except Exception:
        return "格式錯誤"


def colorForStatus(status):
    """根據狀態字串回傳前景色"""
    if "逾期" in status and "已發文" not in status: return Qt.red
    if "今日" in status:                            return Qt.darkYellow
    if "已發文" in status and "逾期" not in status: return Qt.darkGreen
    if "已發文" in status and "逾期" in status:     return Qt.darkYellow
    return None


def nextDocId(conn, table_name):
    """從 Seq_DocId 取得下一個流水號（只增不減）"""
    conn.execute(
        "UPDATE Seq_DocId SET last_id = last_id + 1 WHERE table_name = ?",
        (table_name,)
    )
    row = conn.execute(
        "SELECT last_id FROM Seq_DocId WHERE table_name = ?",
        (table_name,)
    ).fetchone()
    return str(row[0])


def setupDateEditToToday(date_edit):
    """QDateEdit 開啟月曆後自動捲到今天所在的月份"""
    from PySide6.QtCore import QTimer

    class _EventFilter(QObject):
        def eventFilter(self, obj, event):
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.Type.Show:
                QTimer.singleShot(10, _scroll)
            return False

        def _scroll_fn(self):
            cal = date_edit.calendarWidget()
            if cal:
                today = QDate.currentDate()
                cal.setCurrentPage(today.year(), today.month())

    def _scroll():
        cal = date_edit.calendarWidget()
        if cal:
            today = QDate.currentDate()
            # 如果目前是空值（minimumDate），打開時先跳到今天
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

    names = [name for _, name in data_list]
    completer = QCompleter(names, combo)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)
    # 修正 completer popup 黑色背景問題
    completer.popup().setStyleSheet("""
        QAbstractItemView {
            background-color: #ffffff;
            color: #1c1c1e;
            border: 1px solid #c6c6c8;
            selection-background-color: #007aff;
            selection-color: #ffffff;
        }
        QAbstractItemView::item {
            background-color: #ffffff;
            color: #1c1c1e;
            padding: 4px 8px;
            min-height: 28px;
        }
        QAbstractItemView::item:selected {
            background-color: #007aff;
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


# 固定寬度欄位（格式固定不需要動態量）
# key = 表頭文字, value = 固定寬度px
FIXED_COL_WIDTHS = {
    "交辦單編號": 110,
    "限辦日期":   130,
    "發文日期":   130,
    "收文日期":   130,
    "業務組":     100,
    "所承辦人":   180,
    "收文人員":   180,
    "陳報人":     180,
    "主承辦人":   180,
    # 狀態欄動態量（內容長度不固定）
}


def _measureColWidths(table, fm, PAD=40):
    """量出每欄需要的最小寬度（固定欄寫死，其餘量文字）"""
    stretch_col = table.property("stretch_col")
    widths = {}
    for col in range(table.columnCount()):
        if col == 0 and table.columnWidth(0) <= 32:
            widths[col] = 32
            continue
        hdr_item = table.horizontalHeaderItem(col)
        hdr_text = hdr_item.text() if hdr_item else ""

        # 固定寬度欄直接用寫死的值
        if hdr_text in FIXED_COL_WIDTHS:
            widths[col] = FIXED_COL_WIDTHS[hdr_text]
            continue

        # 其餘欄動態量（表頭 vs 資料取最大）
        best = fm.horizontalAdvance(hdr_text) + PAD
        for row in range(table.rowCount()):
            item = table.item(row, col)
            if item:
                w = fm.horizontalAdvance(item.text()) + PAD
                if w > best:
                    best = w
        widths[col] = best
    return widths, stretch_col


def autoResizeTable(table):
    """量出欄寬後：加總 < 可用寬度 → 等比例放大填滿；超過 → 保持原寬讓 scrollbar 出現"""
    if table.property("user_resized"):
        return
    # 不管有沒有資料都量（空白時量表頭，有資料時量表頭+內容取最大）
    from PySide6.QtGui import QFontMetrics
    fm = QFontMetrics(table.font())
    widths, stretch_col = _measureColWidths(table, fm)

    available = table.viewport().width()
    if available <= 0:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda t=table: autoResizeTable(t))
        return

    usable = int(available * 0.99)

    # 非 stretch 欄的量測寬度加總
    other_total = sum(w for c, w in widths.items() if c != stretch_col)
    # stretch_col 最小保留寬度（表頭文字寬，至少 60px）
    stretch_min = max(widths.get(stretch_col, 80), 60)

    if other_total + stretch_min > usable:
        # 所有欄加總超過可用寬度，scrollbar 出現
        for col, w in widths.items():
            table.setColumnWidth(col, w)
    else:
        # 未超過：stretch_col 吃剩餘空間
        stretch_w = usable - other_total
        for col, w in widths.items():
            if col == stretch_col:
                table.setColumnWidth(col, stretch_w)
            else:
                table.setColumnWidth(col, w)


def makeDeleteBtn(callback):
    """建立紅色刪除按鈕，放在 container widget 內置中"""
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


def setupPreviewTable(table, headers):
    """套用 Apple HIG 風格表格樣式"""
    table.setColumnCount(len(headers))
    for i, h in enumerate(headers):
        table.setHorizontalHeaderItem(i, QTableWidgetItem(h))

    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    stretch_col = -1
    if headers[0] == "":
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 32)
        stretch_col = 2   # 交辦事由欄
    else:
        stretch_col = 1   # 無刪除欄時事由欄
    # 全部用 Interactive，stretch_col 由 autoResizeTable 手動計算填滿
    # 記錄 stretch 欄和「使用者是否手動拉過」
    table.setProperty("stretch_col", stretch_col)
    table.setProperty("user_resized", False)
    table.setProperty("init_done", False)
    def _onSectionResized(idx, old_w, new_w, t=table, sc=stretch_col):
        if t.property("init_done") and idx != sc:
            t.setProperty("user_resized", True)
    hdr.sectionResized.connect(_onSectionResized)
    # 初始化完成後才開始監聽使用者拖拉
    from PySide6.QtCore import QTimer
    QTimer.singleShot(500, lambda t=table: t.setProperty("init_done", True))
    # 開啟時用同一套邏輯量表頭寬度
    from PySide6.QtCore import QTimer
    QTimer.singleShot(200, lambda t=table: autoResizeTable(t))
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    hdr.setSectionsMovable(False)
    hdr.setSectionsClickable(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setSelectionBehavior(QTableWidget.SelectRows)

    table.setStyleSheet("""
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f2f2f7;
            border: none;
            border-top: 1px solid #c6c6c8;
        }
        QHeaderView::section {
            background-color: #f2f2f7;
            color: #3a3a3c;
            font-weight: 600;
            padding: 8px 6px;
            border: none;
            border-bottom: 2px solid #c6c6c8;
            border-right: 1px solid #e5e5ea;
        }
        QTableWidget::item {
            padding: 6px;
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


# ──────────────────────────────────────────────
# 基礎 Tab 類別
# ──────────────────────────────────────────────
class BaseTab:
    """所有 Tab 的共用基礎介面"""
    def __init__(self, tab_widget, db_path):
        self.tab_widget = tab_widget   # QTabWidget
        self.db_path    = db_path

    def setup(self, tab_index):
        """在 tabWidget 對應的 tab 上建立 UI，子類別覆寫"""
        raise NotImplementedError

    def _getConn(self):
        return sqlite3.connect(self.db_path)

    def _loadRef(self):
        """載入人員與部門對照表，回傳 (personnel_list, dept_list)"""
        try:
            conn = self._getConn()
            personnel = conn.execute(
                "SELECT staff_id, staff_name FROM Ref_Personnel WHERE is_active=1 ORDER BY staff_id"
            ).fetchall()
            depts = conn.execute(
                "SELECT dept_id, dept_name FROM Ref_Departments ORDER BY dept_id"
            ).fetchall()
            conn.close()
            return personnel, depts
        except Exception as e:
            QMessageBox.critical(None, "DB錯誤", f"載入對照表失敗: {e}")
            return [], []


# ──────────────────────────────────────────────
# Tab 0：交辦單發文
# ──────────────────────────────────────────────
class TabDispatch(BaseTab):
    """交辦單發文：掃入文號 → 預覽 → 批次發文"""

    HEADERS   = ["", "交辦單編號", "交辦事由", "業務組", "所承辦人", "限辦日期", "發文日期", "狀態"]
    DB_COLS   = ["編號", "交辦事由", "業務組", "所承辦人", "限辦日期", "發文日期"]
    VIEW      = "View_Task_Full"
    KEY       = "編號"
    DOC_TABLE = "Document_Task"

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        # 取得 UI 元件（已在 Layout1.ui 定義）
        # 往上找到 MainWindow 再取元件
        mw = self.tab_widget.window()
        self.lineEdit  = getattr(mw, 'lineEdit_docNum', None)
        self.table     = getattr(mw, 'tableWidget', None)
        btn_send       = getattr(mw, 'btn_send', None)
        btn_clear      = getattr(mw, 'btn_clear_all', None)

        if self.table:
            setupPreviewTable(self.table, self.HEADERS)

        # 發文日期
        self.dispatch_date = getattr(mw, 'dispatch_date', None)
        if self.dispatch_date:
            self.dispatch_date.setDate(QDate.currentDate())
            setupDateEditToToday(self.dispatch_date)

        # 發文人員
        self.dispatch_sender = getattr(mw, 'dispatch_sender', None)
        if self.dispatch_sender:
            try:
                conn = self._getConn()
                personnel = conn.execute(
                    "SELECT staff_id, staff_name FROM Ref_Personnel WHERE is_active=1 ORDER BY staff_id"
                ).fetchall()
                conn.close()
                setupFilterCombo(self.dispatch_sender, personnel)
            except Exception as e:
                print(f"[警告] 載入發文人員失敗: {e}")

        if self.lineEdit:
            self.lineEdit.returnPressed.connect(self.handleQuery)
            self.lineEdit.setFocus()
        if btn_send:  btn_send.clicked.connect(self.handleDispatch)
        if btn_clear: btn_clear.clicked.connect(self.handleClearAll)

    # ── 查詢 ──
    def handleQuery(self):
        if not self.lineEdit: return
        serial = self.lineEdit.text().strip()
        if not serial: return

        colStr = ", ".join([f'"{c}"' for c in self.DB_COLS])
        sql    = f'SELECT {colStr} FROM "{self.VIEW}" WHERE "{self.KEY}" = ?'
        try:
            conn = self._getConn()
            row  = conn.execute(sql, (serial,)).fetchone()
            conn.close()
        except Exception as e:
            QMessageBox.critical(None, "SQL 錯誤", str(e)); return

        if row:
            if self._rowExists(str(row[0])):
                QMessageBox.information(None, "提示", f"「{serial}」已在清單中")
            else:
                self._insertRow(row)
            self.lineEdit.clear()
        else:
            QMessageBox.warning(None, "查無資料", f"找不到：{serial}")

    def _rowExists(self, docId):
        if not self.table: return False
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 1)
            if item and item.text() == docId:
                return True
        return False

    def _insertRow(self, data):
        if not self.table: return
        pos = self.table.rowCount()
        self.table.insertRow(pos)

        # 刪除按鈕
        container, _ = makeDeleteBtn(lambda _, r=pos: self._deleteRow(r))
        self.table.setCellWidget(pos, 0, container)

        deadline_str = str(data[4]) if data[4] else ""
        dispatch_str = str(data[5]) if data[5] else ""

        for i in range(4):
            item = QTableWidgetItem(str(data[i]) if data[i] else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(pos, i + 1, item)

        for col, val in [(5, deadline_str), (6, dispatch_str)]:
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(pos, col, item)

        status     = calcOverdue(deadline_str, dispatch_str)
        statusItem = QTableWidgetItem(status)
        statusItem.setTextAlignment(Qt.AlignCenter)
        color = colorForStatus(status)
        if color: statusItem.setForeground(color)
        self.table.setItem(pos, 7, statusItem)
        autoResizeTable(self.table)

    def _deleteRow(self, row):
        if not self.table: return
        self.table.removeRow(row)
        for r in range(self.table.rowCount()):
            container = self.table.cellWidget(r, 0)
            if container:
                btn = container.findChild(QPushButton)
                if btn:
                    btn.clicked.disconnect()
                    btn.clicked.connect(lambda _, ri=r: self._deleteRow(ri))

    # ── 全部清除 ──
    def handleClearAll(self):
        if not self.table or self.table.rowCount() == 0:
            QMessageBox.information(None, "提示", "清單已經是空的"); return
        if QMessageBox.question(None, "確認清除",
                                f"確定要清除全部 {self.table.rowCount()} 筆資料？",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.table.setRowCount(0)

    # ── 批次發文 ──
    def handleDispatch(self):
        if not self.table or self.table.rowCount() == 0:
            QMessageBox.information(None, "提示", "清單是空的，請先掃入文號"); return

        today   = datetime.now().strftime("%Y-%m-%d")
        pending = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 1)
            if item: pending.append((r, item.text()))

        dispatch_day = self.dispatch_date.date().toString("yyyy-MM-dd") if self.dispatch_date else today
        sender_id    = self.dispatch_sender.currentData() if self.dispatch_sender else None
        sender_name  = self.dispatch_sender.currentText() if self.dispatch_sender else "未選擇"

        if QMessageBox.question(
            None, "確認發文",
            f"發文日期：{dispatch_day}\n發文人員：{sender_name}\n"
            f"將對 {len(pending)} 筆資料寫入（已有資料者將被覆蓋）\n確認送出？",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        sql = (f'UPDATE "{self.DOC_TABLE}" '
               f'SET dispatch_date=?, sender_id=?, timestamp=? '
               f'WHERE doc_id=?')
        try:
            conn = self._getConn()
            for seq, (row_idx, doc_id) in enumerate(pending):
                # 用序號確保同毫秒內的資料也有唯一 timestamp
                ts = datetime.now()
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.") + f"{ts.microsecond + seq:06d}"
                conn.execute(sql, (dispatch_day, sender_id, ts_str, doc_id))
                item = QTableWidgetItem(dispatch_day)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 6, item)
                deadline_item = self.table.item(row_idx, 5)
                deadline_val  = deadline_item.text() if deadline_item else ""
                status        = calcOverdue(deadline_val, today)
                statusItem    = QTableWidgetItem(status)
                statusItem.setTextAlignment(Qt.AlignCenter)
                color = colorForStatus(status)
                if color: statusItem.setForeground(color)
                self.table.setItem(row_idx, 7, statusItem)
            conn.commit()
            conn.close()
            QMessageBox.information(None, "完成", f"已成功更新 {len(pending)} 筆發文日期（{today}）")
        except Exception as e:
            QMessageBox.critical(None, "更新失敗", str(e))


# ──────────────────────────────────────────────
# Tab 1：交辦單收文
# ──────────────────────────────────────────────
class TabReceive(BaseTab):
    """交辦單收文：填表 → 立即寫入 DB → 預覽"""

    PREVIEW_HEADERS = ["交辦單編號", "交辦事由", "業務組", "所承辦人", "收文日期", "限辦日期", "狀態"]

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        # 嵌入 Layout2.ui
        recv_widget = loadUi(getResourcePath("Layout2.ui"))
        if not recv_widget:
            return
        inner = recv_widget.centralWidget()
        lay   = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)

        # 取得元件
        self.recv_date      = inner.findChild(QDateEdit,  'recv_date')
        self.recv_receiver  = inner.findChild(QComboBox,  'recv_receiver')
        self.recv_dept      = inner.findChild(QComboBox,  'recv_dept')
        self.recv_subject   = inner.findChild(QLineEdit,  'recv_subject')
        self.recv_processor = inner.findChild(QComboBox,  'recv_processor')
        self.recv_deadline  = inner.findChild(QDateEdit,   'recv_deadline')
        self.chk_no_deadline = inner.findChild(QCheckBox, 'chk_no_deadline')
        self.recv_table     = inner.findChild(QTableWidget, 'recv_tableWidget')

        # 初始化
        self.recv_date.setDate(QDate.currentDate())
        setupDateEditToToday(self.recv_date)
        # 限辦日期：預設今天
        self.recv_deadline.setDate(QDate.currentDate())
        setupDateEditToToday(self.recv_deadline)
        # 免覆 checkbox 邏輯
        if self.chk_no_deadline:
            self.chk_no_deadline.stateChanged.connect(self._onNoDeadlineChanged)

        self._personnel, self._depts = self._loadRef()
        setupFilterCombo(self.recv_receiver,  self._personnel)
        setupFilterCombo(self.recv_processor, self._personnel)
        setupFilterCombo(self.recv_dept,      self._depts)


        if self.recv_table:
            setupPreviewTable(self.recv_table, self.PREVIEW_HEADERS)

        # 綁定按鈕
        btn_clear  = inner.findChild(QPushButton, 'btn_recv_clear')
        btn_submit = inner.findChild(QPushButton, 'btn_recv_submit')
        if btn_clear:  btn_clear.clicked.connect(self._formClear)
        if btn_submit: btn_submit.clicked.connect(self._submit)

    def _onNoDeadlineChanged(self, state):
        """免覆勾選時：反灰限辦日期；取消勾選時：還原可輸入"""
        checked = self.chk_no_deadline.isChecked()
        self.recv_deadline.setEnabled(not checked)
        self.recv_deadline.setStyleSheet(
            "background-color: #e5e5ea; color: #aeaeb2; border-color: #d1d1d6;"
            if checked else ""
        )
        if checked:
            self.recv_deadline.setDate(QDate.currentDate())

    def _formClear(self):
        """清除表單，保留收文日期與收文人員"""
        setupFilterCombo(self.recv_dept,      self._depts)
        setupFilterCombo(self.recv_processor, self._personnel)
        self.recv_subject.clear()
        self.recv_deadline.setEnabled(True)
        self.recv_deadline.setStyleSheet("")
        self.recv_deadline.setDate(QDate.currentDate())
        if self.chk_no_deadline:
            self.chk_no_deadline.setChecked(False)
        self.recv_subject.setFocus()

    def _submit(self):
        recv_date = self.recv_date.date().toString("yyyy-MM-dd")
        recv_id   = self.recv_receiver.currentData()
        dept_id   = self.recv_dept.currentData()
        subject   = self.recv_subject.text().strip()
        proc_id   = self.recv_processor.currentData()
        no_deadline = self.chk_no_deadline.isChecked() if self.chk_no_deadline else False
        deadline    = None if no_deadline else self.recv_deadline.date().toString("yyyy-MM-dd")

        errors = []
        if not recv_id: errors.append("收文人員")
        if not dept_id: errors.append("業務組")
        if not subject: errors.append("交辦事由")
        if not proc_id: errors.append("承辦人")
        if errors:
            QMessageBox.warning(None, "欄位未填", f"請填寫以下必填欄位：\n{'、'.join(errors)}")
            return

        # 限辦日期確認
        if not no_deadline:
            dl = self.recv_deadline.date()
            today = QDate.currentDate()
            if dl == today:
                msg = QMessageBox(None)
                msg.setWindowTitle("限辦日期確認")
                msg.setText(f"限辦日期為今天（{deadline}），確定要寫入嗎？")
                msg.setIcon(QMessageBox.Question)
                btn_ok = msg.addButton("確認", QMessageBox.YesRole)
                msg.addButton("取消", QMessageBox.NoRole)
                msg.exec()
                if msg.clickedButton() != btn_ok:
                    return
            elif dl < today:
                msg = QMessageBox(None)
                msg.setWindowTitle("限辦日期已逾期")
                msg.setText(f"限辦日期（{deadline}）早於今天，此交辦單收文後將立即逾期，確定要寫入嗎？")
                msg.setIcon(QMessageBox.Question)
                btn_ok = msg.addButton("確認", QMessageBox.YesRole)
                msg.addButton("取消", QMessageBox.NoRole)
                msg.exec()
                if msg.clickedButton() != btn_ok:
                    return

        try:
            conn       = self._getConn()
            new_doc_id = nextDocId(conn, 'Document_Task')
            conn.execute("""
                INSERT INTO Document_Task
                    (doc_id, receive_date, receive_id, dept_id, subject,
                     processor_id, deadline, dispatch_date, sender_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
            """, (new_doc_id, recv_date, recv_id, dept_id, subject, proc_id, deadline))
            conn.commit()
            conn.close()

            self._insertPreviewRow(new_doc_id, subject,
                                   self.recv_dept.currentText(),
                                   self.recv_processor.currentText(),
                                   recv_date, deadline)
            self._formClear()

        except Exception as e:
            QMessageBox.critical(None, "寫入失敗", str(e))

    def _insertPreviewRow(self, doc_id, subject, dept_name, processor_name, recv_date, deadline):
        if not self.recv_table: return
        pos = self.recv_table.rowCount()
        self.recv_table.insertRow(pos)
        for col, val in enumerate([doc_id, subject, dept_name, processor_name, recv_date, deadline]):
            item = QTableWidgetItem(str(val) if val else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.recv_table.setItem(pos, col, item)
        status     = calcOverdue(deadline, "")
        statusItem = QTableWidgetItem(status)
        statusItem.setTextAlignment(Qt.AlignCenter)
        color = colorForStatus(status)
        if color: statusItem.setForeground(color)
        self.recv_table.setItem(pos, 6, statusItem)
        autoResizeTable(self.recv_table)


# ──────────────────────────────────────────────
# DocumentManager：視窗容器，管理所有 Tab
# ──────────────────────────────────────────────
class DocumentManager:
    # 新增 Tab 只需在這裡登記
    TAB_CLASSES = {
        0: TabDispatch,
        1: TabReceive,
        # 2: TabCriminal,   ← 未來加這一行就好
        # 3: TabGeneral,
    }

    def __init__(self, tabIndex=0):
        self.dbPath = getResourcePath("dbfile.db")
        self.window = loadUi(getResourcePath("Layout1.ui"))
        if not self.window:
            return

        self.tabWidget = getattr(self.window, 'tabWidget', None)

        # 初始化所有已登記的 Tab
        self.tabs = {}
        for idx, TabClass in self.TAB_CLASSES.items():
            tab = TabClass(self.tabWidget, self.dbPath)
            tab.setup(idx)
            self.tabs[idx] = tab

        if self.tabWidget:
            self.tabWidget.setCurrentIndex(tabIndex)
            # 切換 tab 時重新量寬度（非 active tab 的 viewport 寬度為 0）
            self.tabWidget.currentChanged.connect(self._onTabChanged)

    def _onTabChanged(self, index):
        from PySide6.QtCore import QTimer
        tab_obj = self.tabs.get(index)
        if not tab_obj:
            return
        def _resize():
            for attr in ['table', 'recv_table']:
                t = getattr(tab_obj, attr, None)
                if t and t.columnCount() > 0:
                    autoResizeTable(t)
        QTimer.singleShot(150, _resize)


# ──────────────────────────────────────────────
# 主選單
# ──────────────────────────────────────────────
class MainMenu:
    def __init__(self):
        self.ui = loadUi(getResourcePath("公文輸入系統.ui"))
        if not self.ui:
            sys.exit(1)

        self.selectedTab = -1

        btn_map = {
            'btn_report_assignment':  0,
            'btn_receive_assignment': 1,
            'btn_report_case':        2,
            'btn_generate_receipt':   3,
        }
        for btn_name, idx in btn_map.items():
            btn = getattr(self.ui, btn_name, None)
            if btn:
                btn.clicked.connect(lambda checked=False, i=idx: self._onSelect(i))

        btn_exit = getattr(self.ui, 'btn_exit', None)
        if btn_exit:
            btn_exit.clicked.connect(self.ui.reject)

    def _onSelect(self, index):
        if index not in DocumentManager.TAB_CLASSES:
            QMessageBox.information(self.ui, "提示", "此功能尚未開放，敬請期待")
            return
        self.selectedTab = index
        self.ui.accept()


# ──────────────────────────────────────────────
# 進入點
# ──────────────────────────────────────────────
from theme import APPLE_STYLE


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont()
    font.setPointSize(14)
    app.setFont(font)
    app.setStyleSheet(APPLE_STYLE)

    menu = MainMenu()
    if menu.ui.exec() != QDialog.Accepted or menu.selectedTab < 0:
        sys.exit(0)

    mgr = DocumentManager(tabIndex=menu.selectedTab)
    if hasattr(mgr, 'window') and mgr.window:
        mgr.window.show()
        sys.exit(app.exec())