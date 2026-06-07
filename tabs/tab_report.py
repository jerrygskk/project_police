from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtWidgets import (
    QTableWidgetItem, QRadioButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QSizePolicy,
    QDateEdit, QComboBox, QLineEdit, QLabel,
    QTableWidget, QPushButton
)

from base_tab import BaseTab
from db_utils import getResourcePath, loadUi, nextDocId, DEBUG_MODE, msgInfo, msgWarning, msgCritical, confirmBox
from ui_utils import (
    setupPreviewTable, autoResizeTable, makeDeleteBtn, setDocIdLinkCell,
    setupFilterCombo, setupDateEditToToday,
    CriminalEditDialog, GeneralEditDialog,
)

CRIM_HEADERS = ["", "編號", "狀態", "案類", "陳報主旨", "承辦人", "受理人", "日期", "報案人"]
GEN_HEADERS  = ["", "編號", "業務單位", "陳報主旨", "承辦人", "分類"]

# Radio 圓點縮小，選中用較細 border 呈現
RADIO_STYLE = """
QRadioButton {
    spacing: 6px;
    color: #1c1c1e;
    font-size: 14pt;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 2px solid #c6c6c8;
    border-radius: 7px;
    background-color: #ffffff;
}
QRadioButton::indicator:checked {
    background-color: #8fa8c8;
    border: 4px solid #ffffff;
    outline: 2px solid #8fa8c8;
}
QRadioButton:checked {
    color: #8fa8c8;
}
"""


class TabReport(BaseTab):
    """公文陳報：刑案 / 一般陳報，左右並列預覽"""

    # ── 第4點：DB 原始值 → 預覽顯示名 的對照表提成類別常數 ──
    _STATUS_MAP = {'A_現行犯': '現行', 'B_到案': '到案', 'B_未到案': '未到'}
    _CAT_MAP    = {'D_業務陳報': '業務', 'J_其他': '其他', 'F_司法相驗': '相驗'}

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        rpt_widget = loadUi(getResourcePath("Layout3.ui"))
        if not rpt_widget:
            return

        inner = rpt_widget.centralWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)
        self._inner = inner

        # ── 頂部共用欄位 ──────────────────────────────────
        self.rpt_date   = inner.findChild(QDateEdit, 'rpt_date')
        self.rpt_sender = inner.findChild(QComboBox, 'rpt_sender')

        # ── Radio 按鈕 ────────────────────────────────────
        self.radio_criminal = inner.findChild(QRadioButton, 'radio_criminal')
        self.radio_general  = inner.findChild(QRadioButton, 'radio_general')
        for rb in [self.radio_criminal, self.radio_general]:
            if rb:
                rb.setStyleSheet(RADIO_STYLE)

        # ── QStackedWidget ────────────────────────────────
        self.form_stack = inner.findChild(QStackedWidget, 'formStack')

        # ── 刑案欄位（page 0） ────────────────────────────
        self.radio_status_a = inner.findChild(QRadioButton, 'radio_status_a')  # CS01 現行犯
        self.radio_status_b = inner.findChild(QRadioButton, 'radio_status_b')  # CS02 到案
        self.radio_status_c = inner.findChild(QRadioButton, 'radio_status_c')  # CS03 未到案
        for rb in [self.radio_status_a, self.radio_status_b, self.radio_status_c]:
            if rb:
                rb.setStyleSheet(RADIO_STYLE)
        self.crim_casetype  = inner.findChild(QComboBox, 'crim_casetype')
        self.crim_processor = inner.findChild(QComboBox, 'crim_processor')
        self.crim_receiver  = inner.findChild(QComboBox, 'crim_receiver')
        self.crim_subject   = inner.findChild(QLineEdit, 'crim_subject')
        self.crim_occdate   = inner.findChild(QDateEdit, 'crim_occdate')
        self.crim_reporter  = inner.findChild(QLineEdit, 'crim_reporter')

        # ── 一般欄位（page 1） ────────────────────────────
        self.radio_gen_cat_a = inner.findChild(QRadioButton, 'radio_gen_cat_a')  # GC01 業務陳報
        self.radio_gen_cat_b = inner.findChild(QRadioButton, 'radio_gen_cat_b')  # GC03 其他
        self.radio_gen_cat_c = inner.findChild(QRadioButton, 'radio_gen_cat_c')  # GC02 司法相驗
        for rb in [self.radio_gen_cat_a, self.radio_gen_cat_b, self.radio_gen_cat_c]:
            if rb:
                rb.setStyleSheet(RADIO_STYLE)
        self.gen_dept       = inner.findChild(QComboBox, 'gen_dept')
        self.gen_processor  = inner.findChild(QComboBox, 'gen_processor')
        self.gen_subject    = inner.findChild(QLineEdit, 'gen_subject')

        # ── 預覽表格 ──────────────────────────────────────
        self.crim_table = inner.findChild(QTableWidget, 'crim_tableWidget')
        self.gen_table  = inner.findChild(QTableWidget, 'gen_tableWidget')

        if self.crim_table:
            self.crim_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if self.gen_table:
            self.gen_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout = None
        for i in range(inner.layout().count()):
            item = inner.layout().itemAt(i)
            if item and isinstance(item.layout(), QHBoxLayout):
                preview_layout = item.layout()
                break
        if preview_layout and preview_layout.count() >= 2:
            preview_layout.setStretch(0, 8)
            preview_layout.setStretch(1, 5)

        # ── 預覽標題樣式 ──────────────────────────────────
        for lbl_name, color in [('lbl_criminal_title', '#5b8db8'), ('lbl_general_title', '#c0a080')]:
            lbl = inner.findChild(QLabel, lbl_name)
            if lbl:
                lbl.setStyleSheet(
                    f"background-color: {color}; color: white; font-weight: 600;"
                    f"padding: 6px; border-radius: 4px;"
                )

        # ── 日期初始化 ────────────────────────────────────
        if self.rpt_date:
            self.rpt_date.setDate(QDate.currentDate())
            setupDateEditToToday(self.rpt_date)
        if self.crim_occdate:
            self.crim_occdate.setDate(QDate.currentDate())
            setupDateEditToToday(self.crim_occdate)

        # ── 載入參照表 ────────────────────────────────────
        self._personnel, self._depts = self._loadRef()
        self._case_types = self._loadTable(
            "SELECT case_type_id, case_type_name FROM Ref_CaseTypes ORDER BY case_type_id"
        )

        # ── 填入下拉選單 ──────────────────────────────────
        setupFilterCombo(self.rpt_sender,     self._personnel)
        setupFilterCombo(self.crim_casetype,  self._case_types)
        setupFilterCombo(self.crim_processor, self._personnel)
        setupFilterCombo(self.crim_receiver,  self._personnel)
        setupFilterCombo(self.gen_dept,       self._depts)
        setupFilterCombo(self.gen_processor,  self._personnel)

        # ── 預覽表格初始化 ────────────────────────────────
        if self.crim_table:
            setupPreviewTable(self.crim_table, CRIM_HEADERS, cap_mode=True,
                              stretch_col=8, fixed_overrides={"陳報主旨": 184})
        if self.gen_table:
            setupPreviewTable(self.gen_table, GEN_HEADERS, cap_mode=True,
                              stretch_col=5, fixed_overrides={"陳報主旨": 184})

        # ── 預設顯示刑案（page 0） ────────────────────────
        if self.form_stack:
            self.form_stack.setCurrentIndex(0)

        # ── 信號綁定 ──────────────────────────────────────
        if self.radio_criminal:
            self.radio_criminal.toggled.connect(
                lambda checked: self.form_stack.setCurrentIndex(0 if checked else 1)
            )

        btn_clear  = inner.findChild(QPushButton, 'btn_rpt_clear')
        btn_submit = inner.findChild(QPushButton, 'btn_rpt_submit')
        if btn_clear:  btn_clear.clicked.connect(self._formClear)
        if btn_submit: btn_submit.clicked.connect(self._submit)
        if self.crim_subject: self.crim_subject.setFocus()

        # ── 互填按鈕 ──────────────────────────────────────
        btn_copy_to_receiver  = inner.findChild(QPushButton, 'btn_copy_to_receiver')
        btn_copy_to_processor = inner.findChild(QPushButton, 'btn_copy_to_processor')
        for btn in [btn_copy_to_receiver, btn_copy_to_processor]:
            if btn:
                btn.setStyleSheet("font-size: 11pt; padding: 2px 4px;")
        if btn_copy_to_receiver:
            btn_copy_to_receiver.clicked.connect(self._copyProcessorToReceiver)
        if btn_copy_to_processor:
            btn_copy_to_processor.clicked.connect(self._copyReceiverToProcessor)

    # ── BaseTab 介面 ──────────────────────────────────────
    def get_tables(self):
        return [t for t in [self.crim_table, self.gen_table] if t]

    def get_focus_widget(self):
        return self.crim_subject

    # ── 輔助：從 DB 載入二元組列表 ──────────────────────────
    def _loadTable(self, sql):
        try:
            conn = self._getConn()
            rows = conn.execute(sql).fetchall()
            conn.close()
            return [(r[0], r[1]) for r in rows]
        except Exception as e:
            msgCritical("DB錯誤", f"載入對照表失敗: {e}")
            return []

    # ── 互填：同承辦 / 同受理 ────────────────────────────────
    def _copyProcessorToReceiver(self):
        if not self.crim_processor or not self.crim_receiver:
            return
        data = self.crim_processor.currentData()
        text = self.crim_processor.currentText()
        if data:
            for i in range(self.crim_receiver.count()):
                if self.crim_receiver.itemData(i) == data:
                    self.crim_receiver.setCurrentIndex(i)
                    return
            self.crim_receiver.setEditText(text)

    def _copyReceiverToProcessor(self):
        if not self.crim_receiver or not self.crim_processor:
            return
        data = self.crim_receiver.currentData()
        text = self.crim_receiver.currentText()
        if data:
            for i in range(self.crim_processor.count()):
                if self.crim_processor.itemData(i) == data:
                    self.crim_processor.setCurrentIndex(i)
                    return
            self.crim_processor.setEditText(text)

    # ── 清除表單（保留送文日期、發文人員）──────────────────
    def _formClear(self):
        if self.radio_status_a:
            self.radio_status_a.setChecked(True)
        setupFilterCombo(self.crim_casetype,  self._case_types)
        setupFilterCombo(self.crim_processor, self._personnel)
        setupFilterCombo(self.crim_receiver,  self._personnel)
        if self.crim_subject:  self.crim_subject.clear()
        if self.crim_occdate:  self.crim_occdate.setDate(QDate.currentDate())
        if self.crim_reporter: self.crim_reporter.clear()
        if self.radio_gen_cat_a: self.radio_gen_cat_a.setChecked(True)
        setupFilterCombo(self.gen_dept,      self._depts)
        setupFilterCombo(self.gen_processor, self._personnel)
        if self.gen_subject: self.gen_subject.clear()

    # ── 確認陳報 ────────────────────────────────────────────
    def _submit(self):
        report_date = self.rpt_date.date().toString("yyyy-MM-dd") if self.rpt_date else ""
        sender_id   = self.rpt_sender.currentData() if self.rpt_sender else None
        is_criminal = self.radio_criminal.isChecked() if self.radio_criminal else True

        if is_criminal:
            self._submitCriminal(report_date, sender_id)
        else:
            self._submitGeneral(report_date, sender_id)

    def _submitCriminal(self, report_date, sender_id):
        # ⚠️ 顯示名稱與 DB 不同，若修改 Ref_Case_Status 需一起更新
        if self.radio_status_a and self.radio_status_a.isChecked():
            status_id, status_name = 'CS01', '現行'   # DB: A_現行犯
        elif self.radio_status_b and self.radio_status_b.isChecked():
            status_id, status_name = 'CS02', '到案'   # DB: B_到案
        else:
            status_id, status_name = 'CS03', '未到'   # DB: B_未到案
        casetype_id  = self.crim_casetype.currentData()
        processor_id = self.crim_processor.currentData()
        receiver_id  = self.crim_receiver.currentData()
        subject      = self.crim_subject.text().strip()  if self.crim_subject   else ""
        occ_date     = self.crim_occdate.date().toString("yyyy-MM-dd") if self.crim_occdate else None
        reporter     = self.crim_reporter.text().strip() if self.crim_reporter  else ""

        errors = []
        if not sender_id:    errors.append("發文人員")
        if not casetype_id:  errors.append("案類")
        if not processor_id: errors.append("承辦人員")
        if not subject:      errors.append("陳報主旨")
        if errors:
            msgWarning("欄位未填", f"請填寫以下必填欄位：\n{'、'.join(errors)}")
            return

        try:
            conn       = self._getConn()
            new_doc_id = nextDocId(conn, 'Document_Criminal')
            conn.execute("""
                INSERT INTO Document_Criminal
                    (doc_id, report_date, sender_id, case_type, case_status,
                     processor_id, subject_summary, occurrence_date,
                     reporter_name, receiver_id, is_reported, is_electronic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """, (new_doc_id, report_date, sender_id, casetype_id, status_id,
                  processor_id, subject, occ_date or None,
                  reporter or None, receiver_id))
            conn.commit()
            conn.close()

            self._insertCrimRow(
                new_doc_id, status_name,
                self.crim_casetype.currentText(),
                subject,
                self.crim_processor.currentText(),
                self.crim_receiver.currentText(),
                reporter,
                occ_date,
            )
            if not DEBUG_MODE:
                self._formClear()

        except Exception as e:
            msgCritical("寫入失敗", str(e))

    def _submitGeneral(self, report_date, sender_id):
        # ⚠️ 顯示名稱與 DB 不同，若修改 Ref_General_Category 需一起更新
        if self.radio_gen_cat_a and self.radio_gen_cat_a.isChecked():
            cat_id, cat_name = 'GC01', '業務'   # DB: D_業務陳報
        elif self.radio_gen_cat_b and self.radio_gen_cat_b.isChecked():
            cat_id, cat_name = 'GC03', '其他'   # DB: J_其他
        else:
            cat_id, cat_name = 'GC02', '相驗'   # DB: F_司法相驗
        dept_id      = self.gen_dept.currentData()
        processor_id = self.gen_processor.currentData()
        subject      = self.gen_subject.text().strip() if self.gen_subject else ""

        errors = []
        if not sender_id:    errors.append("發文人員")
        if not processor_id: errors.append("承辦人")
        if not subject:      errors.append("陳報主旨")
        if errors:
            msgWarning("欄位未填", f"請填寫以下必填欄位：\n{'、'.join(errors)}")
            return

        try:
            conn       = self._getConn()
            new_doc_id = nextDocId(conn, 'Document_General')
            conn.execute("""
                INSERT INTO Document_General
                    (doc_id, report_date, sender_id, dept_id, gen_cat_id,
                     subject, processor_id, is_reported, is_electronic)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
            """, (new_doc_id, report_date, sender_id, dept_id, cat_id,
                  subject, processor_id))
            conn.commit()
            conn.close()

            self._insertGenRow(
                new_doc_id,
                self.gen_dept.currentText(),
                subject,
                self.gen_processor.currentText(),
                cat_name,
            )
            if not DEBUG_MODE:
                self._formClear()

        except Exception as e:
            msgCritical("寫入失敗", str(e))

    # ── 插入預覽列 ───────────────────────────────────────────
    def _insertCrimRow(self, doc_id, status, casetype, subject,
                       processor, receiver, reporter, occ_date):
        if not self.crim_table:
            return
        pos = self.crim_table.rowCount()
        self.crim_table.insertRow(pos)

        # 刪除按鈕（col 0）：以 doc_id 為準
        container, _ = makeDeleteBtn(lambda _, d=doc_id: self._deleteCrimByDocId(d))
        self.crim_table.setCellWidget(pos, 0, container)

        # 編號欄（col 1）：超連結
        setDocIdLinkCell(self.crim_table, pos, 1, doc_id, self._onEditCrimRow, clickable=True)

        for col, val in enumerate([
            status, casetype, subject,
            self._trimName(processor), self._trimName(receiver),
            self._fmtDate(occ_date), self._trimName(reporter),
        ], start=2):
            item = QTableWidgetItem(str(val) if val else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.crim_table.setItem(pos, col, item)
        autoResizeTable(self.crim_table)

    def _insertGenRow(self, doc_id, dept, subject, processor, cat):
        if not self.gen_table:
            return
        pos = self.gen_table.rowCount()
        self.gen_table.insertRow(pos)

        # 刪除按鈕（col 0）：以 doc_id 為準
        container, _ = makeDeleteBtn(lambda _, d=doc_id: self._deleteGenByDocId(d))
        self.gen_table.setCellWidget(pos, 0, container)

        # 編號欄（col 1）：超連結
        setDocIdLinkCell(self.gen_table, pos, 1, doc_id, self._onEditGenRow, clickable=True)

        for col, val in enumerate([dept, subject, self._trimName(processor), cat], start=2):
            item = QTableWidgetItem(str(val) if val else "")
            item.setTextAlignment(Qt.AlignCenter)
            self.gen_table.setItem(pos, col, item)
        autoResizeTable(self.gen_table)

    # ── 修改回呼 ────────────────────────────────────────────
    def _onEditCrimRow(self, row, doc_id):
        dlg = CriminalEditDialog(self.db_path, doc_id, self.crim_table)
        if dlg.exec():
            updated = dlg.get_updated()
            if updated:
                # updated = (送文編號, 發文分類, 案類, 嫌疑人_案由, 主承辦人, 受理人, 受理日期, 報案人)
                _, status_raw, casetype, subject, processor, receiver, occ_date, reporter = updated
                # 第4點：使用類別常數轉換
                status = self._STATUS_MAP.get(str(status_raw) if status_raw else '',
                                              str(status_raw) if status_raw else '')
                for col, val in enumerate([
                    status, casetype, subject,
                    self._trimName(processor), self._trimName(receiver),
                    self._fmtDate(occ_date), self._trimName(reporter),
                ], start=2):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.crim_table.setItem(row, col, item)
                autoResizeTable(self.crim_table)

    def _onEditGenRow(self, row, doc_id):
        dlg = GeneralEditDialog(self.db_path, doc_id, self.gen_table)
        if dlg.exec():
            updated = dlg.get_updated()
            if updated:
                # updated = (送文編號, 業務單位, 陳報主旨, 陳報人, 分類)
                _, dept, subject, processor, cat_raw = updated
                # 第4點：使用類別常數轉換
                cat = self._CAT_MAP.get(str(cat_raw) if cat_raw else '',
                                        str(cat_raw) if cat_raw else '')
                for col, val in enumerate([dept, subject, self._trimName(processor), cat], start=2):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.gen_table.setItem(row, col, item)
                QTimer.singleShot(0, lambda: autoResizeTable(self.gen_table))

    # ── 刪除（第1點：doc_id 驅動，不需重新綁定）────────────
    def _deleteCrimByDocId(self, doc_id):
        if not self.crim_table:
            return
        if not confirmBox("確認刪除",
                          f"本筆資料將被刪除，本文號（{doc_id}）無法再被使用，確認刪除？",
                          confirm_text="刪除", confirm_danger=True, default_confirm=False):
            return
        try:
            conn = self._getConn()
            conn.execute("""
                UPDATE Document_Criminal SET
                    report_date=NULL, sender_id=NULL, case_type=NULL, case_status=NULL,
                    processor_id=NULL, subject_summary=NULL, occurrence_date=NULL,
                    reporter_name=NULL, receiver_id=NULL, is_reported=0, is_electronic=0
                WHERE doc_id=?
            """, (doc_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("刪除失敗", str(e))
            return
        for r in range(self.crim_table.rowCount()):
            lbl = self.crim_table.cellWidget(r, 1)
            if lbl and self._docIdFromLabel(lbl) == doc_id:
                self.crim_table.removeRow(r)
                return

    def _deleteGenByDocId(self, doc_id):
        if not self.gen_table:
            return
        if not confirmBox("確認刪除",
                          f"本筆資料將被刪除，本文號（{doc_id}）無法再被使用，確認刪除？",
                          confirm_text="刪除", confirm_danger=True, default_confirm=False):
            return
        try:
            conn = self._getConn()
            conn.execute("""
                UPDATE Document_General SET
                    report_date=NULL, sender_id=NULL, dept_id=NULL, gen_cat_id=NULL,
                    subject=NULL, processor_id=NULL, is_reported=0, is_electronic=0
                WHERE doc_id=?
            """, (doc_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("刪除失敗", str(e))
            return
        for r in range(self.gen_table.rowCount()):
            lbl = self.gen_table.cellWidget(r, 1)
            if lbl and self._docIdFromLabel(lbl) == doc_id:
                self.gen_table.removeRow(r)
                return
