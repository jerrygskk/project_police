from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QTableWidgetItem, QPushButton, QVBoxLayout,
    QDateEdit, QComboBox, QLineEdit, QCheckBox,
    QTableWidget, QMessageBox
)

from base_tab import BaseTab
from db_utils import getResourcePath, loadUi, nextDocId
from ui_utils import (
    setupPreviewTable, autoResizeTable,
    setupFilterCombo, setupDateEditToToday,
    calcOverdue, colorForStatus,
)


class TabReceive(BaseTab):
    """交辦單收文：填表 → 立即寫入 DB → 預覽"""

    PREVIEW_HEADERS = ["交辦單編號", "交辦事由", "業務組", "所承辦人", "收文日期", "限辦日期", "狀態"]

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        recv_widget = loadUi(getResourcePath("Layout2.ui"))
        if not recv_widget:
            return

        inner = recv_widget.centralWidget()
        lay   = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)

        # 取得元件
        self.recv_date       = inner.findChild(QDateEdit,    'recv_date')
        self.recv_receiver   = inner.findChild(QComboBox,    'recv_receiver')
        self.recv_dept       = inner.findChild(QComboBox,    'recv_dept')
        self.recv_subject    = inner.findChild(QLineEdit,    'recv_subject')
        self.recv_processor  = inner.findChild(QComboBox,    'recv_processor')
        self.recv_deadline   = inner.findChild(QDateEdit,    'recv_deadline')
        self.chk_no_deadline = inner.findChild(QCheckBox,   'chk_no_deadline')
        self.recv_table      = inner.findChild(QTableWidget, 'recv_tableWidget')

        # 日期初始化
        self.recv_date.setDate(QDate.currentDate())
        setupDateEditToToday(self.recv_date)
        self.recv_deadline.setDate(QDate.currentDate())
        setupDateEditToToday(self.recv_deadline)

        if self.chk_no_deadline:
            self.chk_no_deadline.stateChanged.connect(self._onNoDeadlineChanged)

        # 下拉選單
        self._personnel, self._depts = self._loadRef()
        setupFilterCombo(self.recv_receiver,  self._personnel)
        setupFilterCombo(self.recv_processor, self._personnel)
        setupFilterCombo(self.recv_dept,      self._depts)

        if self.recv_table:
            setupPreviewTable(self.recv_table, self.PREVIEW_HEADERS)

        # 按鈕綁定
        btn_clear  = inner.findChild(QPushButton, 'btn_recv_clear')
        btn_submit = inner.findChild(QPushButton, 'btn_recv_submit')
        if btn_clear:  btn_clear.clicked.connect(self._formClear)
        if btn_submit: btn_submit.clicked.connect(self._submit)

    # ── 免覆 Checkbox ─────────────────────────────────────
    def _onNoDeadlineChanged(self, state):
        checked = self.chk_no_deadline.isChecked()
        self.recv_deadline.setEnabled(not checked)
        self.recv_deadline.setStyleSheet(
            "background-color: #e5e5ea; color: #aeaeb2; border-color: #d1d1d6;"
            if checked else ""
        )
        if checked:
            self.recv_deadline.setDate(QDate.currentDate())

    # ── 清除表單 ──────────────────────────────────────────
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

    # ── 確認收文 ──────────────────────────────────────────
    def _submit(self):
        recv_date   = self.recv_date.date().toString("yyyy-MM-dd")
        recv_id     = self.recv_receiver.currentData()
        dept_id     = self.recv_dept.currentData()
        subject     = self.recv_subject.text().strip()
        proc_id     = self.recv_processor.currentData()
        no_deadline = self.chk_no_deadline.isChecked() if self.chk_no_deadline else False
        deadline    = None if no_deadline else self.recv_deadline.date().toString("yyyy-MM-dd")

        # 必填驗證
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
            dl    = self.recv_deadline.date()
            today = QDate.currentDate()
            if dl == today:
                if not self._confirmDialog("限辦日期確認",
                                           f"限辦日期為今天（{deadline}），確定要寫入嗎？"):
                    return
            elif dl < today:
                if not self._confirmDialog("限辦日期已逾期",
                                           f"限辦日期（{deadline}）早於今天，"
                                           f"此交辦單收文後將立即逾期，確定要寫入嗎？"):
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

            self._insertPreviewRow(
                new_doc_id, subject,
                self.recv_dept.currentText(),
                self.recv_processor.currentText(),
                recv_date, deadline
            )
            self._formClear()

        except Exception as e:
            QMessageBox.critical(None, "寫入失敗", str(e))

    def _confirmDialog(self, title, text):
        """帶「確認／取消」的 Question dialog，確認回 True"""
        msg    = QMessageBox(None)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Question)
        btn_ok = msg.addButton("確認", QMessageBox.YesRole)
        msg.addButton("取消", QMessageBox.NoRole)
        msg.exec()
        return msg.clickedButton() == btn_ok

    # ── 預覽表格 ──────────────────────────────────────────
    def _insertPreviewRow(self, doc_id, subject, dept_name, processor_name, recv_date, deadline):
        if not self.recv_table:
            return
        pos = self.recv_table.rowCount()
        self.recv_table.insertRow(pos)
        for col, val in enumerate([doc_id, subject, dept_name, processor_name, recv_date, deadline]):
            item = QTableWidgetItem(str(val) if val else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.recv_table.setItem(pos, col, item)

        status      = calcOverdue(deadline, "")
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignCenter)
        color = colorForStatus(status)
        if color:
            status_item.setForeground(color)
        self.recv_table.setItem(pos, 6, status_item)
        autoResizeTable(self.recv_table)
