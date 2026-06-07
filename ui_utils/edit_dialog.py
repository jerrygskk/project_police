"""
EditDialog — 通用修改彈窗
動態產生表單，目前支援：
  - task：Document_Task（交辦單）
"""
import sqlite3

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDateEdit, QCheckBox,
    QPushButton, QDialogButtonBox, QRadioButton,
)
from PySide6.QtCore import Qt, QDate

from db_utils import getResourcePath, BTN_CONFIRM, BTN_CANCEL, confirmBox


def _get_conn(db_path):
    return sqlite3.connect(db_path)


def _load_combo(conn, sql):
    """回傳 [(id, display), ...]"""
    return conn.execute(sql).fetchall()


# ── Task EditDialog ────────────────────────────────────────────
class TaskEditDialog(QDialog):
    """交辦單修改彈窗（Tab 0 / Tab 1 共用）"""

    def __init__(self, db_path, doc_id, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.doc_id  = doc_id
        self.setWindowTitle('交辦單修改')

        # ── 版面常數 ──────────────────────────────────────────
        self._LABEL_W    = 120   # label 區寬度
        self._FIELD_W    = 340   # 輸入元件總寬度
        self._MARGIN     = 40    # 左右 margin
        self._CHECKBOX_W = 130   # 免覆 checkbox 寬度
        self._SPACING_W  = 30    # DateEdit 與 checkbox 間距
        self._DATE_W     = self._FIELD_W - self._SPACING_W - self._CHECKBOX_W  # = 260

        self.setMinimumWidth(self._LABEL_W + self._FIELD_W + self._MARGIN)  # = 580
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #FFFFFF;
                color: #000000;
            }
            QLineEdit, QComboBox, QDateEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QCheckBox { color: #000000; }
            QLabel { color: #000000; }
        """)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        conn = _get_conn(self.db_path)

        # 參照資料
        self._personnel = _load_combo(conn,
            "SELECT staff_id, staff_name FROM Ref_Personnel WHERE is_active=1 ORDER BY staff_name")
        self._depts = _load_combo(conn,
            "SELECT dept_id, dept_name FROM Ref_Departments ORDER BY dept_name")
        conn.close()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        # 編號（鎖定）
        lbl_id = QLabel(str(self.doc_id))
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("交辦單編號：", lbl_id)

        # 收文日期
        self.w_recv_date = QDateEdit()
        self.w_recv_date.setCalendarPopup(True)
        self.w_recv_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("收文日期：", self.w_recv_date)

        # 收文人員
        self.w_recv_id = QComboBox()
        for sid, sname in self._personnel:
            self.w_recv_id.addItem(sname, sid)
        form.addRow("收文人員：", self.w_recv_id)

        # 業務組
        self.w_dept = QComboBox()
        for did, dname in self._depts:
            self.w_dept.addItem(dname, did)
        form.addRow("業務組：", self.w_dept)

        # 交辦事由
        self.w_subject = QLineEdit()
        self.w_subject.setPlaceholderText("請輸入交辦事由")
        form.addRow("交辦事由：", self.w_subject)

        # 承辦人
        self.w_proc = QComboBox()
        for sid, sname in self._personnel:
            self.w_proc.addItem(sname, sid)
        form.addRow("承辦人：", self.w_proc)

        # 限辦日期 + 免覆
        deadline_row = QHBoxLayout()
        deadline_row.setContentsMargins(0, 0, 0, 0)
        self.w_deadline = QDateEdit()
        self.w_deadline.setCalendarPopup(True)
        self.w_deadline.setDisplayFormat("yyyy-MM-dd")
        self.w_deadline.setFixedWidth(self._DATE_W)
        
        self.w_deadline.setSizePolicy(
            self.w_deadline.sizePolicy().horizontalPolicy(),
            self.w_deadline.sizePolicy().verticalPolicy()
        )
        self.w_no_deadline = QCheckBox("免覆")
        self.w_no_deadline.setFixedWidth(self._CHECKBOX_W)
        self.w_no_deadline.toggled.connect(
            lambda checked: self.w_deadline.setEnabled(not checked))
        deadline_row.addWidget(self.w_deadline)
        deadline_row.addSpacing(self._SPACING_W)
        deadline_row.addWidget(self.w_no_deadline)
        form.addRow("限辦日期：", deadline_row)

        # 按鈕
        btn_save   = QPushButton("儲存")
        btn_cancel = QPushButton("取消")
        btn_save.setStyleSheet(BTN_CONFIRM)
        btn_cancel.setStyleSheet(BTN_CANCEL)
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addSpacing(8)
        root.addLayout(btn_row)

        self.w_subject.setFocus()

    def _load_data(self):
        """從 DB 撈原始資料填入欄位"""
        conn = _get_conn(self.db_path)
        row = conn.execute("""
            SELECT receive_date, receive_id, dept_id, subject,
                   processor_id, deadline
            FROM Document_Task WHERE doc_id=?
        """, (self.doc_id,)).fetchone()
        conn.close()
        if not row:
            return

        recv_date, recv_id, dept_id, subject, proc_id, deadline = row

        # 收文日期
        if recv_date:
            self.w_recv_date.setDate(QDate.fromString(str(recv_date), "yyyy-MM-dd"))
        else:
            self.w_recv_date.setDate(QDate.currentDate())

        # 收文人員
        self._set_combo(self.w_recv_id, recv_id)

        # 業務組
        self._set_combo(self.w_dept, dept_id)

        # 交辦事由
        self.w_subject.setText(str(subject) if subject else "")

        # 承辦人
        self._set_combo(self.w_proc, proc_id)

        # 限辦日期
        if deadline:
            self.w_deadline.setDate(QDate.fromString(str(deadline), "yyyy-MM-dd"))
            self.w_no_deadline.setChecked(False)
        else:
            self.w_deadline.setDate(QDate.currentDate())
            self.w_no_deadline.setChecked(True)
            self.w_deadline.setEnabled(False)

    def _set_combo(self, combo, value):
        """依 data（id）設定 ComboBox 選項，找不到時插入原始值提示"""
        if not value:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        # 找不到：在最前面插入原始值，標示為異常
        combo.insertItem(0, f'⚠ {value}（不在人員清單）', value)
        combo.setCurrentIndex(0)

    def _on_save(self):
        recv_date = self.w_recv_date.date().toString("yyyy-MM-dd")
        recv_id   = self.w_recv_id.currentData()
        dept_id   = self.w_dept.currentData()
        subject   = self.w_subject.text().strip()
        proc_id   = self.w_proc.currentData()
        deadline  = None if self.w_no_deadline.isChecked() \
                    else self.w_deadline.date().toString("yyyy-MM-dd")

        if not subject:
            from db_utils import msgWarning
            msgWarning("欄位未填", "交辦事由不可為空")
            return

        try:
            conn = _get_conn(self.db_path)
            conn.execute("""
                UPDATE Document_Task
                SET receive_date=?, receive_id=?, dept_id=?,
                    subject=?, processor_id=?, deadline=?
                WHERE doc_id=?
            """, (recv_date, recv_id, dept_id, subject, proc_id, deadline, self.doc_id))
            conn.commit()
            conn.close()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("儲存失敗", str(e))
            return

        self.accept()

    def get_updated(self):
        """儲存後回傳更新後的顯示值，供表格刷新用"""
        conn = _get_conn(self.db_path)
        row = conn.execute("""
            SELECT 編號, 交辦事由, 業務組, 所承辦人,
                   限辦日期, 發文日期, 狀態
            FROM View_Task_Full
            WHERE 編號=?
        """, (self.doc_id,)).fetchone()
        conn.close()
        return row

# ── Criminal EditDialog ────────────────────────────────────────
class CriminalEditDialog(QDialog):
    """刑案陳報修改彈窗（Tab 2）"""

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

    # Radio 對應表：(db_value, display_label)
    STATUS_OPTIONS = [
        ('CS01', '現行'),
        ('CS02', '到案'),
        ('CS03', '未到'),
    ]

    def __init__(self, db_path, doc_id, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.doc_id  = doc_id
        self.setWindowTitle('刑案陳報修改')

        self._LABEL_W = 120
        self._FIELD_W = 340
        self._MARGIN  = 40

        self.setMinimumWidth(self._LABEL_W + self._FIELD_W + self._MARGIN)
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #FFFFFF;
                color: #000000;
            }
            QLineEdit, QComboBox, QDateEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QCheckBox, QRadioButton { color: #000000; }
            QLabel { color: #000000; }
        """)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        from PySide6.QtWidgets import QButtonGroup
        conn = _get_conn(self.db_path)
        self._personnel  = _load_combo(conn,
            "SELECT staff_id, staff_name FROM Ref_Personnel WHERE is_active=1 ORDER BY staff_name")
        self._case_types = _load_combo(conn,
            "SELECT case_type_id, case_type_name FROM Ref_CaseTypes ORDER BY case_type_id")
        conn.close()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        # 編號（鎖定）
        lbl_id = QLabel(str(self.doc_id))
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("陳報編號：", lbl_id)

        # 陳報日期
        self.w_report_date = QDateEdit()
        self.w_report_date.setCalendarPopup(True)
        self.w_report_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("陳報日期：", self.w_report_date)

        # 發文人員
        self.w_sender = QComboBox()
        for sid, sname in self._personnel:
            self.w_sender.addItem(sname, sid)
        form.addRow("發文人員：", self.w_sender)

        # 案件分類
        self.w_casetype = QComboBox()
        for cid, cname in self._case_types:
            self.w_casetype.addItem(cname, cid)
        form.addRow("案件分類：", self.w_casetype)

        # 發文分類（Radio）
        radio_row = QHBoxLayout()
        radio_row.setContentsMargins(0, 0, 0, 0)
        self._status_radios = []
        self._status_group  = QButtonGroup(self)
        for i, (val, label) in enumerate(self.STATUS_OPTIONS):
            rb = QRadioButton(label)
            rb.setStyleSheet(self.RADIO_STYLE)
            self._status_group.addButton(rb, i)
            self._status_radios.append((val, rb))
            radio_row.addWidget(rb)
        radio_row.addStretch()
        form.addRow("發文分類：", radio_row)

        # 承辦人
        self.w_processor = QComboBox()
        for sid, sname in self._personnel:
            self.w_processor.addItem(sname, sid)
        form.addRow("承辦人：", self.w_processor)

        # 受理人
        self.w_receiver = QComboBox()
        for sid, sname in self._personnel:
            self.w_receiver.addItem(sname, sid)
        form.addRow("受理人：", self.w_receiver)

        # 陳報主旨
        self.w_subject = QLineEdit()
        self.w_subject.setPlaceholderText("請輸入陳報主旨")
        form.addRow("陳報主旨：", self.w_subject)

        # 查獲日期
        self.w_occ_date = QDateEdit()
        self.w_occ_date.setCalendarPopup(True)
        self.w_occ_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("查獲日期：", self.w_occ_date)

        # 報案人
        self.w_reporter = QLineEdit()
        self.w_reporter.setPlaceholderText("請輸入報案人")
        form.addRow("報案人：", self.w_reporter)

        # 按鈕
        btn_save   = QPushButton("儲存")
        btn_cancel = QPushButton("取消")
        btn_save.setStyleSheet(BTN_CONFIRM)
        btn_cancel.setStyleSheet(BTN_CANCEL)
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addSpacing(8)
        root.addLayout(btn_row)

        self.w_subject.setFocus()

    def _load_data(self):
        conn = _get_conn(self.db_path)
        row = conn.execute("""
            SELECT report_date, sender_id, case_type, case_status,
                   processor_id, receiver_id, subject_summary,
                   occurrence_date, reporter_name
            FROM Document_Criminal WHERE doc_id=?
        """, (self.doc_id,)).fetchone()
        conn.close()
        if not row:
            return

        report_date, sender_id, case_type, case_status, \
            proc_id, recv_id, subject, occ_date, reporter = row

        if report_date:
            self.w_report_date.setDate(QDate.fromString(str(report_date), "yyyy-MM-dd"))
        else:
            self.w_report_date.setDate(QDate.currentDate())

        self._set_combo(self.w_sender,    sender_id)
        self._set_combo(self.w_casetype,  case_type)
        self._set_combo(self.w_processor, proc_id)
        self._set_combo(self.w_receiver,  recv_id)

        # Radio：從 DB 的 case_status 對應
        # DB 存的是 Ref_Case_Status 的 status_id（CS01/CS02/CS03）
        matched = False
        for val, rb in self._status_radios:
            if val == case_status:
                rb.setChecked(True)
                matched = True
                break
        if not matched:
            self._status_radios[0][1].setChecked(True)

        self.w_subject.setText(str(subject) if subject else "")

        if occ_date:
            self.w_occ_date.setDate(QDate.fromString(str(occ_date), "yyyy-MM-dd"))
        else:
            self.w_occ_date.setDate(QDate.currentDate())

        self.w_reporter.setText(str(reporter) if reporter else "")

    def _set_combo(self, combo, value):
        if not value:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.insertItem(0, f'⚠ {value}（不在清單）', value)
        combo.setCurrentIndex(0)

    def _on_save(self):
        from db_utils import msgWarning, msgCritical
        report_date = self.w_report_date.date().toString("yyyy-MM-dd")
        sender_id   = self.w_sender.currentData()
        case_type   = self.w_casetype.currentData()
        proc_id     = self.w_processor.currentData()
        recv_id     = self.w_receiver.currentData()
        subject     = self.w_subject.text().strip()
        occ_date    = self.w_occ_date.date().toString("yyyy-MM-dd")
        reporter    = self.w_reporter.text().strip()

        status_id = 'CS01'
        for val, rb in self._status_radios:
            if rb.isChecked():
                status_id = val
                break

        if not subject:
            msgWarning("欄位未填", "陳報主旨不可為空")
            return

        try:
            conn = _get_conn(self.db_path)
            conn.execute("""
                UPDATE Document_Criminal
                SET report_date=?, sender_id=?, case_type=?, case_status=?,
                    processor_id=?, receiver_id=?, subject_summary=?,
                    occurrence_date=?, reporter_name=?
                WHERE doc_id=?
            """, (report_date, sender_id, case_type, status_id,
                  proc_id, recv_id, subject, occ_date, reporter or None,
                  self.doc_id))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("儲存失敗", str(e))
            return

        self.accept()

    def get_updated(self):
        """儲存後回傳更新後的顯示值，供表格刷新用"""
        conn = _get_conn(self.db_path)
        row = conn.execute("""
            SELECT 送文編號, 發文分類, 案類, 嫌疑人_案由,
                   主承辦人, 受理人, 受理日期, 報案人
            FROM View_Criminal_Full WHERE 送文編號=?
        """, (self.doc_id,)).fetchone()
        conn.close()
        return row


# ── General EditDialog ─────────────────────────────────────────
class GeneralEditDialog(QDialog):
    """一般陳報修改彈窗（Tab 2）"""

    RADIO_STYLE = CriminalEditDialog.RADIO_STYLE

    CAT_OPTIONS = [
        ('GC01', '業務'),
        ('GC03', '其他'),
        ('GC02', '相驗'),
    ]

    def __init__(self, db_path, doc_id, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.doc_id  = doc_id
        self.setWindowTitle('一般陳報修改')

        self._LABEL_W = 120
        self._FIELD_W = 340
        self._MARGIN  = 40

        self.setMinimumWidth(self._LABEL_W + self._FIELD_W + self._MARGIN)
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #FFFFFF;
                color: #000000;
            }
            QLineEdit, QComboBox, QDateEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QCheckBox, QRadioButton { color: #000000; }
            QLabel { color: #000000; }
        """)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        from PySide6.QtWidgets import QButtonGroup
        conn = _get_conn(self.db_path)
        self._personnel = _load_combo(conn,
            "SELECT staff_id, staff_name FROM Ref_Personnel WHERE is_active=1 ORDER BY staff_name")
        self._depts = _load_combo(conn,
            "SELECT dept_id, dept_name FROM Ref_Departments ORDER BY dept_name")
        conn.close()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        # 編號（鎖定）
        lbl_id = QLabel(str(self.doc_id))
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("陳報編號：", lbl_id)

        # 陳報日期
        self.w_report_date = QDateEdit()
        self.w_report_date.setCalendarPopup(True)
        self.w_report_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("陳報日期：", self.w_report_date)

        # 發文人員
        self.w_sender = QComboBox()
        for sid, sname in self._personnel:
            self.w_sender.addItem(sname, sid)
        form.addRow("發文人員：", self.w_sender)

        # 業務單位
        self.w_dept = QComboBox()
        for did, dname in self._depts:
            self.w_dept.addItem(dname, did)
        form.addRow("業務單位：", self.w_dept)

        # 發文分類（Radio）
        radio_row = QHBoxLayout()
        radio_row.setContentsMargins(0, 0, 0, 0)
        self._cat_radios = []
        self._cat_group  = QButtonGroup(self)
        for i, (val, label) in enumerate(self.CAT_OPTIONS):
            rb = QRadioButton(label)
            rb.setStyleSheet(self.RADIO_STYLE)
            self._cat_group.addButton(rb, i)
            self._cat_radios.append((val, rb))
            radio_row.addWidget(rb)
        radio_row.addStretch()
        form.addRow("發文分類：", radio_row)

        # 陳報主旨
        # 承辦人
        self.w_processor = QComboBox()
        for sid, sname in self._personnel:
            self.w_processor.addItem(sname, sid)
        form.addRow("承辦人：", self.w_processor)

        self.w_subject = QLineEdit()
        self.w_subject.setPlaceholderText("請輸入陳報主旨")
        form.addRow("陳報主旨：", self.w_subject)

        # 按鈕
        btn_save   = QPushButton("儲存")
        btn_cancel = QPushButton("取消")
        btn_save.setStyleSheet(BTN_CONFIRM)
        btn_cancel.setStyleSheet(BTN_CANCEL)
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addSpacing(8)
        root.addLayout(btn_row)

        self.w_subject.setFocus()

    def _load_data(self):
        conn = _get_conn(self.db_path)
        row = conn.execute("""
            SELECT report_date, sender_id, dept_id, gen_cat_id,
                   subject, processor_id
            FROM Document_General WHERE doc_id=?
        """, (self.doc_id,)).fetchone()
        conn.close()
        if not row:
            return

        report_date, sender_id, dept_id, gen_cat_id, subject, proc_id = row

        if report_date:
            self.w_report_date.setDate(QDate.fromString(str(report_date), "yyyy-MM-dd"))
        else:
            self.w_report_date.setDate(QDate.currentDate())

        self._set_combo(self.w_sender,    sender_id)
        self._set_combo(self.w_dept,      dept_id)
        self._set_combo(self.w_processor, proc_id)

        matched = False
        for val, rb in self._cat_radios:
            if val == gen_cat_id:
                rb.setChecked(True)
                matched = True
                break
        if not matched:
            self._cat_radios[0][1].setChecked(True)

        self.w_subject.setText(str(subject) if subject else "")

    def _set_combo(self, combo, value):
        if not value:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.insertItem(0, f'⚠ {value}（不在清單）', value)
        combo.setCurrentIndex(0)

    def _on_save(self):
        from db_utils import msgWarning, msgCritical
        report_date = self.w_report_date.date().toString("yyyy-MM-dd")
        sender_id   = self.w_sender.currentData()
        dept_id     = self.w_dept.currentData()
        subject     = self.w_subject.text().strip()
        proc_id     = self.w_processor.currentData()

        cat_id = 'GC01'
        for val, rb in self._cat_radios:
            if rb.isChecked():
                cat_id = val
                break

        if not subject:
            msgWarning("欄位未填", "陳報主旨不可為空")
            return

        try:
            conn = _get_conn(self.db_path)
            conn.execute("""
                UPDATE Document_General
                SET report_date=?, sender_id=?, dept_id=?, gen_cat_id=?,
                    subject=?, processor_id=?
                WHERE doc_id=?
            """, (report_date, sender_id, dept_id, cat_id,
                  subject, proc_id, self.doc_id))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("儲存失敗", str(e))
            return

        self.accept()

    def get_updated(self):
        """儲存後回傳更新後的顯示值，供表格刷新用"""
        conn = _get_conn(self.db_path)
        row = conn.execute("""
            SELECT 送文編號, 業務單位, 陳報主旨, 陳報人, 分類
            FROM View_General_Full WHERE 送文編號=?
        """, (self.doc_id,)).fetchone()
        conn.close()
        return row
