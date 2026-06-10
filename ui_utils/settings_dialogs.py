"""
settings_dialogs.py — 設定頁彈窗

包含：
  - PersonnelAddDialog    / PersonnelEditDialog    人員 新增 / 修改
  - DeptAddDialog         / DeptEditDialog          部門 新增 / 修改
  - CaseTypeAddDialog     / CaseTypeEditDialog      案件類型 新增 / 修改
  - ChangePasswordDialog                            變更密碼
"""
import re
import sqlite3

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
)

from db_utils import BTN_CONFIRM, BTN_CANCEL, BTN_DANGER

# ── 共用樣式 ───────────────────────────────────────────────────────
_DIALOG_SS = """
    QDialog, QWidget {
        background-color: #FFFFFF;
        color: #000000;
    }
    QLineEdit {
        background-color: #FFFFFF;
        color: #000000;
        border: 1px solid #CCCCCC;
        border-radius: 4px;
        padding: 4px 8px;
    }
    QLineEdit:focus {
        border: 1px solid #8fa8c8;
    }
    QCheckBox { color: #000000; }
    QLabel    { color: #000000; }
"""

_LABEL_W = 100
_FIELD_W = 280
_MARGIN  = 40


def _add_buttons(dlg, layout, confirm_text='儲存', danger=False):
    row = QHBoxLayout()
    row.addStretch()
    btn_cancel = QPushButton('取消')
    btn_ok     = QPushButton(confirm_text)
    btn_cancel.setStyleSheet(BTN_CANCEL)
    btn_ok.setStyleSheet(BTN_DANGER if danger else BTN_CONFIRM)
    row.addWidget(btn_cancel)
    row.addWidget(btn_ok)
    layout.addLayout(row)
    btn_cancel.clicked.connect(dlg.reject)
    return btn_cancel, btn_ok


def _next_id(conn, table, id_col, prefix, digits=2):
    rows = conn.execute(f"SELECT {id_col} FROM {table}").fetchall()
    nums = []
    for (val,) in rows:
        m = re.search(r'(\d+)$', str(val))
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return f"{prefix}{nxt:0{digits}d}"


# ══════════════════════════════════════════════════════════════════
# 人員管理
# ══════════════════════════════════════════════════════════════════

class PersonnelAddDialog(QDialog):

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._new_id = None
        self._result = None
        self.setWindowTitle('新增人員')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build()

    def _build(self):
        conn         = sqlite3.connect(self.db_path)
        self._new_id = _next_id(conn, 'Ref_Personnel', 'staff_id', 'P', digits=2)
        conn.close()

        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        lbl_id = QLabel(self._new_id)
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("人員編號：", lbl_id)

        self.w_name = QLineEdit()
        self.w_name.setPlaceholderText("例：王小明 或 王小明-19.06")
        self.w_name.setFixedWidth(_FIELD_W)
        form.addRow("姓名：", self.w_name)

        self.w_retired = QCheckBox("離職")
        self.w_retired.setChecked(False)
        form.addRow("狀態：", self.w_retired)

        vlay.addLayout(form)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='新增')
        btn_ok.clicked.connect(self._submit)
        self.w_name.returnPressed.connect(self._submit)
        self.w_name.setFocus()

    def _submit(self):
        name      = self.w_name.text().strip()
        is_active = 0 if self.w_retired.isChecked() else 1
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO Ref_Personnel (staff_id, staff_name, is_active) VALUES (?,?,?)",
                (self._new_id, name, is_active))
            conn.commit()
            conn.close()
            self._result = (self._new_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("寫入失敗", str(e), self)

    def get_result(self):
        return self._result


class PersonnelEditDialog(QDialog):

    def __init__(self, db_path, staff_id, staff_name, is_active, parent=None):
        super().__init__(parent)
        self.db_path  = db_path
        self.staff_id = staff_id
        self._result  = None
        self.setWindowTitle('修改人員')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build(staff_name, is_active)

    def _build(self, staff_name, is_active):
        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        lbl_id = QLabel(self.staff_id)
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("人員編號：", lbl_id)

        self.w_name = QLineEdit(staff_name)
        self.w_name.setFixedWidth(_FIELD_W)
        form.addRow("姓名：", self.w_name)

        self.w_retired = QCheckBox("離職")
        self.w_retired.setChecked(not bool(is_active))
        form.addRow("狀態：", self.w_retired)

        vlay.addLayout(form)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='儲存')
        btn_ok.clicked.connect(self._submit)
        self.w_name.returnPressed.connect(self._submit)
        self.w_name.setFocus()

    def _submit(self):
        name      = self.w_name.text().strip()
        is_active = 0 if self.w_retired.isChecked() else 1
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE Ref_Personnel SET staff_name=?, is_active=? WHERE staff_id=?",
                (name, is_active, self.staff_id))
            conn.commit()
            conn.close()
            self._result = (self.staff_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("更新失敗", str(e), self)

    def get_result(self):
        return self._result


# ══════════════════════════════════════════════════════════════════
# 部門管理
# ══════════════════════════════════════════════════════════════════

class DeptAddDialog(QDialog):

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._new_id = None
        self._result = None
        self.setWindowTitle('新增部門')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build()

    def _build(self):
        conn         = sqlite3.connect(self.db_path)
        self._new_id = _next_id(conn, 'Ref_Departments', 'dept_id', 'D', digits=2)
        conn.close()

        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        lbl_id = QLabel(self._new_id)
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("部門編號：", lbl_id)

        self.w_name = QLineEdit()
        self.w_name.setPlaceholderText("例：刑事組")
        self.w_name.setFixedWidth(_FIELD_W)
        form.addRow("部門名稱：", self.w_name)

        vlay.addLayout(form)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='新增')
        btn_ok.clicked.connect(self._submit)
        self.w_name.returnPressed.connect(self._submit)
        self.w_name.setFocus()

    def _submit(self):
        name = self.w_name.text().strip()
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO Ref_Departments (dept_id, dept_name) VALUES (?,?)",
                (self._new_id, name))
            conn.commit()
            conn.close()
            self._result = (self._new_id, name)
            self.accept()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("寫入失敗", str(e), self)

    def get_result(self):
        return self._result


class DeptEditDialog(QDialog):

    def __init__(self, db_path, dept_id, dept_name, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.dept_id = dept_id
        self._result = None
        self.setWindowTitle('修改部門')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build(dept_name)

    def _build(self, dept_name):
        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        lbl_id = QLabel(self.dept_id)
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("部門編號：", lbl_id)

        self.w_name = QLineEdit(dept_name)
        self.w_name.setFixedWidth(_FIELD_W)
        form.addRow("部門名稱：", self.w_name)

        vlay.addLayout(form)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='儲存')
        btn_ok.clicked.connect(self._submit)
        self.w_name.returnPressed.connect(self._submit)
        self.w_name.setFocus()

    def _submit(self):
        name = self.w_name.text().strip()
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE Ref_Departments SET dept_name=? WHERE dept_id=?",
                (name, self.dept_id))
            conn.commit()
            conn.close()
            self._result = (self.dept_id, name)
            self.accept()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("更新失敗", str(e), self)

    def get_result(self):
        return self._result


# ══════════════════════════════════════════════════════════════════
# 案件類型管理
# ══════════════════════════════════════════════════════════════════

class CaseTypeAddDialog(QDialog):

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._new_id = None
        self._result = None
        self.setWindowTitle('新增案件類型')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build()

    def _build(self):
        conn         = sqlite3.connect(self.db_path)
        self._new_id = _next_id(conn, 'Ref_CaseTypes', 'case_type_id', 'CT', digits=2)
        conn.close()

        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        lbl_id = QLabel(self._new_id)
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("類型編號：", lbl_id)

        self.w_name = QLineEdit()
        self.w_name.setPlaceholderText("例：277傷害")
        self.w_name.setFixedWidth(_FIELD_W)
        form.addRow("類型名稱：", self.w_name)

        vlay.addLayout(form)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='新增')
        btn_ok.clicked.connect(self._submit)
        self.w_name.returnPressed.connect(self._submit)
        self.w_name.setFocus()

    def _submit(self):
        name = self.w_name.text().strip()
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO Ref_CaseTypes (case_type_id, case_type_name) VALUES (?,?)",
                (self._new_id, name))
            conn.commit()
            conn.close()
            self._result = (self._new_id, name)
            self.accept()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("寫入失敗", str(e), self)

    def get_result(self):
        return self._result


class CaseTypeEditDialog(QDialog):

    def __init__(self, db_path, type_id, type_name, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.type_id = type_id
        self._result = None
        self.setWindowTitle('修改案件類型')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build(type_name)

    def _build(self, type_name):
        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        lbl_id = QLabel(self.type_id)
        lbl_id.setStyleSheet("font-weight: bold;")
        form.addRow("類型編號：", lbl_id)

        self.w_name = QLineEdit(type_name)
        self.w_name.setFixedWidth(_FIELD_W)
        form.addRow("類型名稱：", self.w_name)

        vlay.addLayout(form)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='儲存')
        btn_ok.clicked.connect(self._submit)
        self.w_name.returnPressed.connect(self._submit)
        self.w_name.setFocus()

    def _submit(self):
        name = self.w_name.text().strip()
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE Ref_CaseTypes SET case_type_name=? WHERE case_type_id=?",
                (name, self.type_id))
            conn.commit()
            conn.close()
            self._result = (self.type_id, name)
            self.accept()
        except Exception as e:
            from db_utils import msgCritical
            msgCritical("更新失敗", str(e), self)

    def get_result(self):
        return self._result


# ══════════════════════════════════════════════════════════════════
# 變更密碼
# ══════════════════════════════════════════════════════════════════

class ChangePasswordDialog(QDialog):

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle('變更管理者密碼')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build()

    def _build(self):
        vlay = QVBoxLayout(self)
        vlay.setSpacing(16)
        vlay.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        self.w_old = QLineEdit()
        self.w_old.setEchoMode(QLineEdit.Password)
        self.w_old.setFixedWidth(_FIELD_W)
        self.w_old.setPlaceholderText("請輸入目前密碼")
        form.addRow("目前密碼：", self.w_old)

        self.w_new = QLineEdit()
        self.w_new.setEchoMode(QLineEdit.Password)
        self.w_new.setFixedWidth(_FIELD_W)
        self.w_new.setPlaceholderText("請輸入新密碼")
        form.addRow("新密碼：", self.w_new)

        self.w_confirm = QLineEdit()
        self.w_confirm.setEchoMode(QLineEdit.Password)
        self.w_confirm.setFixedWidth(_FIELD_W)
        self.w_confirm.setPlaceholderText("再次輸入新密碼")
        form.addRow("確認新密碼：", self.w_confirm)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color: #e74c3c;")
        self.lbl_err.setAlignment(Qt.AlignRight)

        vlay.addLayout(form)
        vlay.addWidget(self.lbl_err)
        _, btn_ok = _add_buttons(self, vlay, confirm_text='變更密碼')
        btn_ok.clicked.connect(self._submit)
        self.w_confirm.returnPressed.connect(self._submit)
        self.w_old.setFocus()

    def _submit(self):
        old     = self.w_old.text()
        new     = self.w_new.text()
        confirm = self.w_confirm.text()

        if not old or not new or not confirm:
            self.lbl_err.setText("所有欄位均為必填")
            return
        if new != confirm:
            self.lbl_err.setText("新密碼與確認密碼不一致")
            self.w_confirm.clear()
            self.w_confirm.setFocus()
            return
        if len(new) < 4:
            self.lbl_err.setText("新密碼至少需要 4 個字元")
            return

        from auth_manager import AuthManager
        ok = AuthManager.instance().change_password(old, new, self.db_path)
        if ok:
            self.accept()
        else:
            self.lbl_err.setText("目前密碼錯誤")
            self.w_old.clear()
            self.w_old.setFocus()
