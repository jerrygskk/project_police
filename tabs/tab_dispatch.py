from datetime import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QTableWidgetItem, QPushButton

from base_tab import BaseTab
from db_utils import msgInfo, msgWarning, msgCritical, confirmBox, DEBUG_MODE
from ui_utils import (
    setupPreviewTable, autoResizeTable, makeDeleteBtn, TaskEditDialog,
    setupFilterCombo, setupDateEditToToday,
    calcOverdue, colorForStatus,
)


class TabDispatch(BaseTab):
    """交辦單發文：掃入文號 → 預覽清單 → 批次發文"""

    HEADERS   = ["", "交辦單編號", "交辦事由", "業務組", "所承辦人", "限辦日期", "發文日期", "狀態"]
    DB_COLS   = ["編號", "交辦事由", "業務組", "所承辦人", "限辦日期", "發文日期"]
    VIEW      = "View_Task_Full"
    KEY       = "編號"
    DOC_TABLE = "Document_Task"

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        mw = self.tab_widget.window()
        self.lineEdit        = getattr(mw, 'lineEdit_docNum', None)
        self.table           = getattr(mw, 'tableWidget',     None)
        self.dispatch_date   = getattr(mw, 'dispatch_date',   None)
        self.dispatch_sender = getattr(mw, 'dispatch_sender', None)
        btn_send             = getattr(mw, 'btn_send',        None)
        btn_clear            = getattr(mw, 'btn_clear_all',   None)

        if self.table:
            setupPreviewTable(self.table, self.HEADERS, stretch_col=2,
                              fixed_overrides={'狀態': 210})

        if self.dispatch_date:
            self.dispatch_date.setDate(QDate.currentDate())
            setupDateEditToToday(self.dispatch_date)

        if self.dispatch_sender:
            personnel, _ = self._loadRef()
            setupFilterCombo(self.dispatch_sender, personnel)

        if self.lineEdit:
            self.lineEdit.returnPressed.connect(self.handleQuery)
            self.lineEdit.setFocus()
        if btn_send:  btn_send.clicked.connect(self.handleDispatch)
        if btn_clear: btn_clear.clicked.connect(self.handleClearAll)

    # ── 查詢單筆 ──────────────────────────────────────────
    def handleQuery(self):
        if not self.lineEdit:
            return
        serial = self.lineEdit.text().strip()
        if not serial:
            return

        col_str = ", ".join([f'"{c}"' for c in self.DB_COLS])
        sql     = f'SELECT {col_str} FROM "{self.VIEW}" WHERE "{self.KEY}" = ?'
        try:
            conn = self._getConn()
            row  = conn.execute(sql, (serial,)).fetchone()
            conn.close()
        except Exception as e:
            msgCritical("SQL 錯誤", str(e))
            return

        if row:
            # 另外查 receive_date 判斷是否已刪除
            try:
                conn2  = self._getConn()
                rd_row = conn2.execute(
                    "SELECT receive_date FROM Document_Task WHERE doc_id=?", (serial,)
                ).fetchone()
                conn2.close()
            except Exception:
                rd_row = None

            recv_date = rd_row[0] if rd_row else None
            if recv_date is None:
                msgWarning("查無資料", f"找不到文號「{serial}」，可能已被刪除")
                self.lineEdit.clear()
                return

            if self._rowExists(str(row[0])):
                msgInfo("提示", f"「{serial}」已在清單中")
            else:
                # DB_COLS = ["編號", "交辦事由", "業務組", "所承辦人", "限辦日期", "發文日期"]
                # row[0]=編號, row[1]=交辦事由, row[2]=業務組, row[3]=所承辦人
                missing = []
                if not row[2]: missing.append("業務組")
                if not row[1]: missing.append("交辦事由")
                if not row[3]: missing.append("所承辦人")
                if missing:
                    if not confirmBox(
                        "資料不完整",
                        f"此文號資料不完整（缺少：{'、'.join(missing)}），仍可發文，確認加入清單？",
                        confirm_text="仍要加入", default_confirm=True
                    ):
                        self.lineEdit.clear()
                        return
                self._insertRow(row)
            self.lineEdit.clear()
        else:
            msgWarning("查無資料", f"找不到：{serial}")

    def _rowExists(self, doc_id):
        if not self.table:
            return False
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 1)
            if item and item.text() == doc_id:
                return True
        return False

    def _insertRow(self, data):
        if not self.table:
            return
        pos = self.table.rowCount()
        self.table.insertRow(pos)

        container, _ = makeDeleteBtn(lambda _, r=pos: self._deleteRow(r))
        self.table.setCellWidget(pos, 0, container)

        deadline_str = str(data[4]) if data[4] else ""
        dispatch_str = str(data[5]) if data[5] else ""
        doc_id       = str(data[0]) if data[0] else ""

        # 編號欄（col 1）：已發文 → 純文字；未發文 → 超連結
        is_dispatched = bool(dispatch_str)
        self._setDocIdCell(pos, 1, doc_id, is_dispatched)

        # 其他欄位（col 2~4）
        for i in range(1, 4):
            item = QTableWidgetItem(str(data[i]) if data[i] else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(pos, i + 1, item)

        for col, val in [(5, deadline_str), (6, dispatch_str)]:
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(pos, col, item)

        status      = calcOverdue(deadline_str, dispatch_str)
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignCenter)
        color = colorForStatus(status)
        if color:
            status_item.setForeground(color)
        self.table.setItem(pos, 7, status_item)
        autoResizeTable(self.table)

    def _setDocIdCell(self, row, col, doc_id, is_dispatched):
        """編號欄：已發文 → 純文字，未發文 → 超連結（DEBUG_MODE 下全部可點）"""
        from PySide6.QtWidgets import QLabel
        if (is_dispatched and not DEBUG_MODE) or not doc_id:
            item = QTableWidgetItem(doc_id)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, item)
        else:
            lbl = QLabel(f'<a href="{doc_id}" style="color:#4A7FA5;">{doc_id}</a>')
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setOpenExternalLinks(False)
            lbl.linkActivated.connect(lambda link: self._onEditRow(row, link))
            self.table.setCellWidget(row, col, lbl)

    def _onEditRow(self, row, doc_id):
        """點擊超連結 → 開啟 EditDialog"""
        dlg = TaskEditDialog(self.db_path, doc_id, self.table)
        if dlg.exec():
            updated = dlg.get_updated()
            if updated:
                # 刷新表格該列（col 2~7）
                # updated = (編號, 交辦事由, 業務組, 所承辦人, 限辦日期, 發文日期, 狀態)
                _, subject, dept, proc, deadline, dispatch, status = updated
                for col, val in enumerate([subject, dept, proc], start=2):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col, item)
                for col, val in [(5, deadline), (6, dispatch)]:
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col, item)
                status_item = QTableWidgetItem(str(status) if status else "")
                status_item.setTextAlignment(Qt.AlignCenter)
                color = colorForStatus(str(status) if status else "")
                if color:
                    status_item.setForeground(color)
                self.table.setItem(row, 7, status_item)

    def _rebindDocIdCell(self, row, col):
        """重新綁定 QLabel 的 linkActivated（刪除後 row index 變動時使用）"""
        lbl = self.table.cellWidget(row, col)
        if not lbl:
            return
        lbl.linkActivated.disconnect()
        lbl.linkActivated.connect(lambda link, r=row: self._onEditRow(r, link))

    def _deleteRow(self, row):
        if not self.table:
            return
        self.table.removeRow(row)
        # 刪除後重新綁定所有刪除按鈕和編號超連結的 row index
        for r in range(self.table.rowCount()):
            container = self.table.cellWidget(r, 0)
            if container:
                btn = container.findChild(QPushButton)
                if btn:
                    btn.clicked.disconnect()
                    btn.clicked.connect(lambda _, ri=r: self._deleteRow(ri))
            self._rebindDocIdCell(r, 1)

    # ── 全部清除 ──────────────────────────────────────────
    def handleClearAll(self):
        if not self.table or self.table.rowCount() == 0:
            msgInfo("提示", "清單已經是空的")
            return
        if confirmBox("確認清除", f"確定要清除全部 {self.table.rowCount()} 筆資料？",
                      confirm_text="清除", confirm_danger=True, default_confirm=True):
            self.table.setRowCount(0)

    # ── 批次發文 ──────────────────────────────────────────
    def handleDispatch(self):
        if not self.table or self.table.rowCount() == 0:
            msgInfo("提示", "清單是空的，請先掃入文號")
            return

        today   = datetime.now().strftime("%Y-%m-%d")
        pending = [
            (r, self.table.item(r, 1).text())
            for r in range(self.table.rowCount())
            if self.table.item(r, 1)
        ]

        dispatch_day = (
            self.dispatch_date.date().toString("yyyy-MM-dd")
            if self.dispatch_date else today
        )
        sender_id   = self.dispatch_sender.currentData() if self.dispatch_sender else None
        sender_name = self.dispatch_sender.currentText() if self.dispatch_sender else "未選擇"

        if not confirmBox(
            "確認發文",
            f"發文日期：{dispatch_day}\n發文人員：{sender_name}\n"
            f"將對 {len(pending)} 筆資料寫入（已有資料者將被覆蓋）\n確認送出？",
            confirm_text="發文", default_confirm=True
        ):
            return

        sql = (
            f'UPDATE "{self.DOC_TABLE}" '
            f'SET dispatch_date=?, sender_id=?, timestamp=? '
            f'WHERE doc_id=?'
        )
        try:
            conn = self._getConn()
            for seq, (row_idx, doc_id) in enumerate(pending):
                ts     = datetime.now()
                us     = (ts.microsecond + seq) % 1_000_000
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.") + f"{us:06d}"
                conn.execute(sql, (dispatch_day, sender_id, ts_str, doc_id))

                item = QTableWidgetItem(dispatch_day)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 6, item)

                deadline_item = self.table.item(row_idx, 5)
                deadline_val  = deadline_item.text() if deadline_item else ""
                status        = calcOverdue(deadline_val, dispatch_day)
                status_item   = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignCenter)
                color = colorForStatus(status)
                if color:
                    status_item.setForeground(color)
                self.table.setItem(row_idx, 7, status_item)

            conn.commit()
            conn.close()
            msgInfo("完成", f"已成功更新 {len(pending)} 筆發文日期（{dispatch_day}）")
        except Exception as e:
            msgCritical("更新失敗", str(e))
