"""
EditDialog — 通用修改彈窗
動態產生表單，目前支援：
  - task：Document_Task（交辦單）
"""
import sqlite3

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDateEdit, QCheckBox,
    QPushButton, QDialogButtonBox,
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
        self.setWindowTitle(f'修改交辦單　編號：{doc_id}')

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
