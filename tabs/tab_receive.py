from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QTableWidgetItem, QPushButton, QVBoxLayout,
    QDateEdit, QComboBox, QLineEdit, QCheckBox,
    QTableWidget
)

from base_tab import BaseTab
from db_utils import getResourcePath, loadUi, nextDocId, DEBUG_MODE, msgWarning, msgCritical, confirmBox
from ui_utils import (
    setupPreviewTable, autoResizeTable, makeDeleteBtn, TaskEditDialog,
    setupFilterCombo, setupDateEditToToday,
    calcOverdue, colorForStatus,
)


class TabReceive(BaseTab):
    """交辦單收文：填表 → 立即寫入 DB → 預覽"""

    PREVIEW_HEADERS = ["", "交辦單編號", "交辦事由", "業務組", "所承辦人", "收文日期", "限辦日期", "狀態"]

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
            setupPreviewTable(self.recv_table, self.PREVIEW_HEADERS, stretch_col=2,
                              fixed_overrides={'狀態': 210})

        # 按鈕綁定
        btn_clear  = inner.findChild(QPushButton, 'btn_recv_clear')
        btn_submit = inner.findChild(QPushButton, 'btn_recv_submit')
        if btn_clear:  btn_clear.clicked.connect(self._formClear)
        if btn_submit: btn_submit.clicked.connect(self._submit)
        if self.recv_subject: self.recv_subject.setFocus()

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
            msgWarning("欄位未填", f"請填寫以下必填欄位：\n{'、'.join(errors)}")
            return

        # 限辦日期確認
        if not no_deadline:
            dl    = self.recv_deadline.date()
            today = QDate.currentDate()
            if dl == today:
                if not confirmBox("限辦日期確認", f"限辦日期為今天（{deadline}），確定要寫入嗎？",
                              confirm_text="確認寫入", default_confirm=False):
                    return
            elif dl < today:
                if not confirmBox("限辦日期已逾期",
                              f"限辦日期（{deadline}）早於今天，此交辦單收文後將立即逾期，確定要寫入嗎？",
                              confirm_text="確認寫入", confirm_danger=True, default_confirm=False):
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
            if not DEBUG_MODE:
                self._formClear()

        except Exception as e:
            msgCritical("寫入失敗", str(e))



    # ── 預覽表格 ──────────────────────────────────────────
    def _insertPreviewRow(self, doc_id, subject, dept_name, processor_name, recv_date, deadline):
        if not self.recv_table:
            return
        pos = self.recv_table.rowCount()
        self.recv_table.insertRow(pos)

        # 刪除按鈕（col 0）
        container, btn = makeDeleteBtn(lambda _, r=pos: self._deleteRow(r))
        self.recv_table.setCellWidget(pos, 0, container)

        # 編號欄（col 1）：超連結
        self._setDocIdCell(pos, 1, doc_id)

        # 資料欄（col 2~6）
        for col, val in enumerate([subject, dept_name, processor_name, recv_date, deadline], start=2):
            item = QTableWidgetItem(str(val) if val else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.recv_table.setItem(pos, col, item)

        # 狀態欄（col 7）
        status      = calcOverdue(deadline, "")
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignCenter)
        color = colorForStatus(status)
        if color:
            status_item.setForeground(color)
        self.recv_table.setItem(pos, 7, status_item)
        autoResizeTable(self.recv_table)

    def _setDocIdCell(self, row, col, doc_id):
        """編號欄：超連結（收文無發文限制，全部可點）"""
        from PySide6.QtWidgets import QLabel
        lbl = QLabel(f'<a href="{doc_id}" style="color:#4A7FA5;">{doc_id}</a>')
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setOpenExternalLinks(False)
        lbl.linkActivated.connect(lambda link, r=row: self._onEditRow(r, link))
        self.recv_table.setCellWidget(row, col, lbl)

    def _rebindDocIdCell(self, row, col):
        """重新綁定 QLabel 的 linkActivated（刪除後 row index 變動時使用）"""
        lbl = self.recv_table.cellWidget(row, col)
        if not lbl:
            return
        lbl.linkActivated.disconnect()
        lbl.linkActivated.connect(lambda link, r=row: self._onEditRow(r, link))

    def _onEditRow(self, row, doc_id):
        """點擊超連結 → 開啟 TaskEditDialog"""
        dlg = TaskEditDialog(self.db_path, doc_id, self.recv_table)
        if dlg.exec():
            updated = dlg.get_updated()
            if updated:
                # updated = (編號, 交辦事由, 業務組, 所承辦人, 限辦日期, 發文日期, 狀態)
                _, subject, dept, proc, deadline, dispatch, status = updated
                for col, val in enumerate([subject, dept, proc], start=2):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.recv_table.setItem(row, col, item)
                # 收文日期（col 5）不在 View_Task_Full 回傳值，保留原值不動
                deadline_item = QTableWidgetItem(str(deadline) if deadline else "")
                deadline_item.setTextAlignment(Qt.AlignCenter)
                self.recv_table.setItem(row, 6, deadline_item)
                status_item = QTableWidgetItem(str(status) if status else "")
                status_item.setTextAlignment(Qt.AlignCenter)
                color = colorForStatus(str(status) if status else "")
                if color:
                    status_item.setForeground(color)
                self.recv_table.setItem(row, 7, status_item)

    def _deleteRow(self, row):
        if not self.recv_table:
            return
        # col 1 是 QLabel widget，用 linkActivated 的 href 取 doc_id
        lbl = self.recv_table.cellWidget(row, 1)
        if not lbl:
            return
        import re
        m = re.search(r'href="([^"]+)"', lbl.text())
        if not m:
            return
        doc_id = m.group(1)

        reply = confirmBox(
            "確認刪除",
            f"本筆資料將被刪除，本文號（{doc_id}）無法再被使用，確認刪除？",
            confirm_text="刪除", confirm_danger=True, default_confirm=False
        )
        if not reply:
            return

        try:
            conn = self._getConn()
            conn.execute("""
                UPDATE Document_Task SET
                    receive_date=NULL, receive_id=NULL, dept_id=NULL,
                    subject=NULL, processor_id=NULL, deadline=NULL,
                    dispatch_date=NULL, sender_id=NULL, timestamp=NULL
                WHERE doc_id=?
            """, (doc_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("刪除失敗", str(e))
            return

        self.recv_table.removeRow(row)
        # 重新綁定刪除按鈕和編號超連結的 row index
        for r in range(self.recv_table.rowCount()):
            container = self.recv_table.cellWidget(r, 0)
            if container:
                btn = container.findChild(QPushButton)
                if btn:
                    btn.clicked.disconnect()
                    btn.clicked.connect(lambda _, ri=r: self._deleteRow(ri))
            self._rebindDocIdCell(r, 1)
