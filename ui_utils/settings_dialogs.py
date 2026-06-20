"""
settings_dialogs.py — 設定頁彈窗

包含：
  - PersonnelAddDialog    / PersonnelEditDialog    人員 新增 / 修改
  - DeptAddDialog         / DeptEditDialog          部門 新增 / 修改
  - CaseTypeAddDialog     / CaseTypeEditDialog      案件類型 新增 / 修改
  - ChangePasswordDialog                            變更密碼
"""
import os
import re
import sqlite3

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QFileDialog,
)

from lib.db_utils import BTN_CONFIRM, BTN_CANCEL, BTN_DANGER

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


def _add_buttons(dlg, layout, confirm_text='儲存', danger=False, default_confirm=True):
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
    # default_confirm=True：Enter 確認（確認鈕為 default）
    # default_confirm=False：Enter 不確認，改由取消鈕為 default（高風險操作用，防誤按）
    if default_confirm:
        btn_cancel.setAutoDefault(False); btn_cancel.setDefault(False)
        btn_ok.setAutoDefault(True);      btn_ok.setDefault(True)
    else:
        btn_ok.setAutoDefault(False);     btn_ok.setDefault(False)
        btn_cancel.setAutoDefault(True);  btn_cancel.setDefault(True)
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

def _has_alias_col(conn):
    """Ref_Personnel.alias 是否已存在（補丁 fix_views 套用後才有）。
    未套補丁時別名相關讀寫一律跳過，避免缺欄報錯。"""
    return any(r[1] == "alias"
               for r in conn.execute("PRAGMA table_info(Ref_Personnel)"))

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

        self.w_alias = QLineEdit()
        self.w_alias.setPlaceholderText("綽號/簡稱，半形逗號分隔（可空）")
        self.w_alias.setFixedWidth(_FIELD_W)
        form.addRow("別名：", self.w_alias)

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
        alias     = self.w_alias.text().strip()
        is_active = 0 if self.w_retired.isChecked() else 1
        if not name:
            self.w_name.setStyleSheet(
                "border: 1px solid #e74c3c; border-radius: 4px; padding: 4px 8px;")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT MIN(sort_order) FROM Ref_Personnel").fetchone()
            new_sort = (row[0] - 1) if row and row[0] is not None else 1
            conn.execute(
                "INSERT INTO Ref_Personnel (staff_id, staff_name, is_active, sort_order) VALUES (?,?,?,?)",
                (self._new_id, name, is_active, new_sort))
            if _has_alias_col(conn):
                conn.execute("UPDATE Ref_Personnel SET alias=? WHERE staff_id=?",
                             (alias, self._new_id))
            conn.commit()
            conn.close()
            self._result = (self._new_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from lib.db_utils import msgCritical
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

        # 別名預填：清單未帶 alias，直接由 staff_id 查 DB（缺欄則留空）
        cur_alias = ""
        try:
            conn = sqlite3.connect(self.db_path)
            if _has_alias_col(conn):
                row = conn.execute(
                    "SELECT alias FROM Ref_Personnel WHERE staff_id=?",
                    (self.staff_id,)).fetchone()
                cur_alias = (row[0] if row and row[0] else "")
            conn.close()
        except Exception:
            pass
        self.w_alias = QLineEdit(cur_alias)
        self.w_alias.setPlaceholderText("綽號/簡稱，半形逗號分隔（可空）")
        self.w_alias.setFixedWidth(_FIELD_W)
        form.addRow("別名：", self.w_alias)

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
        alias     = self.w_alias.text().strip()
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
            if _has_alias_col(conn):
                conn.execute("UPDATE Ref_Personnel SET alias=? WHERE staff_id=?",
                             (alias, self.staff_id))
            conn.commit()
            conn.close()
            self._result = (self.staff_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from lib.db_utils import msgCritical
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

        self.w_retired = QCheckBox("停用")
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
            row = conn.execute("SELECT MIN(sort_order) FROM Ref_Departments").fetchone()
            new_sort = (row[0] - 1) if row and row[0] is not None else 1
            conn.execute(
                "INSERT INTO Ref_Departments (dept_id, dept_name, is_active, sort_order) VALUES (?,?,?,?)",
                (self._new_id, name, is_active, new_sort))
            conn.commit()
            conn.close()
            self._result = (self._new_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from lib.db_utils import msgCritical
            msgCritical("寫入失敗", str(e), self)

    def get_result(self):
        return self._result


class DeptEditDialog(QDialog):

    def __init__(self, db_path, dept_id, dept_name, is_active, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.dept_id = dept_id
        self._result = None
        self.setWindowTitle('修改部門')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build(dept_name, is_active)

    def _build(self, dept_name, is_active):
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

        self.w_retired = QCheckBox("停用")
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
                "UPDATE Ref_Departments SET dept_name=?, is_active=? WHERE dept_id=?",
                (name, is_active, self.dept_id))
            conn.commit()
            conn.close()
            self._result = (self.dept_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from lib.db_utils import msgCritical
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

        self.w_retired = QCheckBox("停用")
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
            row = conn.execute("SELECT MIN(sort_order) FROM Ref_CaseTypes").fetchone()
            new_sort = (row[0] - 1) if row and row[0] is not None else 1
            conn.execute(
                "INSERT INTO Ref_CaseTypes (case_type_id, case_type_name, is_active, sort_order) VALUES (?,?,?,?)",
                (self._new_id, name, is_active, new_sort))
            conn.commit()
            conn.close()
            self._result = (self._new_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from lib.db_utils import msgCritical
            msgCritical("寫入失敗", str(e), self)

    def get_result(self):
        return self._result


class CaseTypeEditDialog(QDialog):

    def __init__(self, db_path, type_id, type_name, is_active, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.type_id = type_id
        self._result = None
        self.setWindowTitle('修改案件類型')
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build(type_name, is_active)

    def _build(self, type_name, is_active):
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

        self.w_retired = QCheckBox("停用")
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
                "UPDATE Ref_CaseTypes SET case_type_name=?, is_active=? WHERE case_type_id=?",
                (name, is_active, self.type_id))
            conn.commit()
            conn.close()
            self._result = (self.type_id, name, bool(is_active))
            self.accept()
        except Exception as e:
            from lib.db_utils import msgCritical
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
        _, btn_ok = _add_buttons(self, vlay, confirm_text='變更密碼', default_confirm=False)
        btn_ok.clicked.connect(self._submit)
        # 變更密碼為高風險操作，不綁 Enter 送出，須以滑鼠點按「變更密碼」
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

        from lib.auth_manager import AuthManager
        ok = AuthManager.instance().change_password(old, new, self.db_path)
        if ok:
            self.accept()
        else:
            self.lbl_err.setText("目前密碼錯誤")
            self.w_old.clear()
            self.w_old.setFocus()


# ══════════════════════════════════════════════════════════════════
# 跨年度重置確認
# ══════════════════════════════════════════════════════════════════
class ResetDialog(QDialog):
    """
    跨年度重置確認彈窗（高風險操作）。

    - 顯示重置範圍警語
    - 動態列出本次將清除的停用項目（人員 / 部門 / 案類）
    - 須手動輸入「RESET」才能執行（防誤按：確認鈕非 default、輸入框不綁 Enter）

    本 Dialog 只負責「取得使用者明確同意」，回傳 accept/reject；
    實際重置由呼叫端（tab_settings）執行。
    """

    _CONFIRM_WORD = "RESET"

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("跨年度重置")
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN)
        self.setStyleSheet(_DIALOG_SS)
        self._build()

    def _build(self):
        from lib.db_utils import listInactiveRefItems

        vlay = QVBoxLayout(self)
        vlay.setSpacing(14)
        vlay.setContentsMargins(24, 20, 24, 16)

        lbl_title = QLabel("跨年度重置將執行下列不可復原的操作：")
        lbl_title.setStyleSheet("font-weight: 700; font-size: 14pt;")
        vlay.addWidget(lbl_title)

        lbl_db = QLabel(f"目標資料庫：{os.path.basename(self.db_path)}")
        lbl_db.setStyleSheet("color: #8e8e93;")
        vlay.addWidget(lbl_db)

        lbl_scope = QLabel(
            "1. 清空全部交辦單、刑案陳報、一般陳報資料\n"
            "2. 移除已停用的人員、部門、案件類型（如需保留請先返回啟用）\n"
            "3. 流水號歸零\n"
            "4. 清除歸檔資料夾路徑設定（需於新年度重新指定）"
        )
        lbl_scope.setStyleSheet("color: #3a3a3c;")
        vlay.addWidget(lbl_scope)

        # 動態列出待清停用項目
        inactive = listInactiveRefItems(self.db_path)
        if inactive:
            lines = "\n".join(f"　• {kind}　{name}" for kind, _id, name in inactive)
            lbl_inactive = QLabel(
                "本次將一併移除以下停用項目：\n" + lines
            )
            lbl_inactive.setStyleSheet(
                "background-color: #FDF2F2; color: #c0392b; "
                "border: 1px solid #f5c6c6; border-radius: 6px; padding: 8px 12px;"
            )
            vlay.addWidget(lbl_inactive)
        else:
            lbl_none = QLabel("（目前無停用項目需移除）")
            lbl_none.setStyleSheet("color: #8e8e93;")
            vlay.addWidget(lbl_none)

        lbl_warn = QLabel("執行前請確認已備份資料。此操作無法復原。")
        lbl_warn.setStyleSheet("color: #c0392b; font-weight: 600;")
        vlay.addWidget(lbl_warn)

        # 確認字串輸入
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.w_confirm = QLineEdit()
        self.w_confirm.setFixedWidth(_FIELD_W)
        self.w_confirm.setPlaceholderText(f"請輸入 {self._CONFIRM_WORD} 以確認")
        form.addRow(f"輸入「{self._CONFIRM_WORD}」：", self.w_confirm)
        vlay.addLayout(form)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color: #e74c3c;")
        self.lbl_err.setAlignment(Qt.AlignRight)
        vlay.addWidget(self.lbl_err)

        # 按鈕：確認鈕為危險樣式、非 default；不綁 Enter（防誤按）
        _, btn_ok = _add_buttons(
            self, vlay, confirm_text="執行重置", danger=True, default_confirm=False)
        btn_ok.clicked.connect(self._submit)
        self.w_confirm.setFocus()

    def _submit(self):
        if self.w_confirm.text().strip() != self._CONFIRM_WORD:
            self.lbl_err.setText(f"請正確輸入 {self._CONFIRM_WORD}")
            self.w_confirm.clear()
            self.w_confirm.setFocus()
            return
        self.accept()


# ══════════════════════════════════════════════════════════════════
# 歸檔資料夾設定（瀏覽 Tab4 開啟電子檔用）
#   存 App_Settings：archive_root(UNC，年度層) / archive_subdir_crim / archive_subdir_gen
#   - 使用者用一般磁碟機代號選資料夾 → 自動轉 UNC（與代號脫鉤），可手動覆寫
#   - 自動列出年度層下的子資料夾，供確認刑案/一般對應夾
# ══════════════════════════════════════════════════════════════════
class ArchiveRootDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("設定歸檔資料夾")
        self.setMinimumWidth(_LABEL_W + _FIELD_W + _MARGIN + 80)
        self.setStyleSheet(_DIALOG_SS)
        self._build()

    def _build(self):
        from lib.db_utils import getSetting, ARCHIVE_ROOT_KEY

        cur_root = getSetting(self.db_path, ARCHIVE_ROOT_KEY, "")
        cur_crim = getSetting(self.db_path, "archive_subdir_crim", "")
        cur_gen  = getSetting(self.db_path, "archive_subdir_gen", "")

        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(24, 20, 24, 16)

        title = QLabel("指定本年度歸檔資料夾")
        title.setStyleSheet("font-weight: 700; font-size: 14pt;")
        v.addWidget(title)

        hint = QLabel(
            "請選擇存放本年度 PDF 的「年度資料夾」（其下含刑案／一般子夾）。\n"
            "選擇後將自動轉為網路路徑（UNC），與磁碟機代號脫鉤。")
        hint.setStyleSheet("color: #3a3a3c;")
        v.addWidget(hint)

        # 路徑列：可編輯 UNC + 選擇鈕
        self.w_path = QLineEdit(cur_root)
        self.w_path.setPlaceholderText("\\\\伺服器\\分享\\…\\年度")
        btn_pick = QPushButton("選擇資料夾…")
        btn_pick.setStyleSheet(BTN_CANCEL)
        row = QHBoxLayout()
        row.addWidget(self.w_path, 1)
        row.addWidget(btn_pick)
        v.addLayout(row)
        btn_pick.clicked.connect(self._pick)

        # 子夾對應
        v.addWidget(QLabel("刑案子資料夾"))
        self.cb_crim = QComboBox()
        self.cb_crim.setEditable(True)
        v.addWidget(self.cb_crim)
        v.addWidget(QLabel("一般子資料夾"))
        self.cb_gen = QComboBox()
        self.cb_gen.setEditable(True)
        v.addWidget(self.cb_gen)

        if cur_crim:
            self.cb_crim.addItem(cur_crim)
            self.cb_crim.setCurrentText(cur_crim)
        if cur_gen:
            self.cb_gen.addItem(cur_gen)
            self.cb_gen.setCurrentText(cur_gen)

        note = QLabel(
            "若分享當下未掛載而無法列出子夾，可直接於上方輸入框輸入 UNC、"
            "並手動鍵入子夾名稱。")
        note.setStyleSheet("color: #8e8e93;")
        note.setWordWrap(True)
        v.addWidget(note)

        # 以目前路徑（若可存取）預先列出子夾
        self._populateSubdirs(cur_root)

        _, btn_ok = _add_buttons(self, v, confirm_text="儲存")
        btn_ok.clicked.connect(self._save)

    def _pick(self):
        from lib.db_utils import toUncPath
        start = self.w_path.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self, "選擇本年度歸檔資料夾",
            start if os.path.isdir(start) else "")
        if not folder:
            return
        unc = toUncPath(folder)
        self.w_path.setText(unc if unc else folder.replace("/", "\\"))
        # 轉不出 UNC（非網路磁碟）→ 橘框提示請確認/改貼 UNC
        self.w_path.setStyleSheet("" if unc else "border: 1px solid #e67e22;")
        # 以實際可存取的本機路徑列子夾（剛選的代號路徑保證可達）
        self._populateSubdirs(folder)

    def _populateSubdirs(self, accessible_path):
        try:
            if accessible_path and os.path.isdir(accessible_path):
                subs = sorted(
                    d for d in os.listdir(accessible_path)
                    if os.path.isdir(os.path.join(accessible_path, d)))
            else:
                subs = []
        except Exception:
            subs = []
        for cb, guess in ((self.cb_crim, "刑"), (self.cb_gen, "一般")):
            cur = cb.currentText().strip()
            cb.blockSignals(True)
            cb.clear()
            for d in subs:
                cb.addItem(d)
            if cur and cur not in subs:
                cb.insertItem(0, cur)
            pick = cur or next((d for d in subs if guess in d), "")
            cb.setCurrentText(pick)
            cb.blockSignals(False)

    def _save(self):
        from lib.db_utils import setSetting, ARCHIVE_ROOT_KEY, clearPdfIndexCache
        root = self.w_path.text().strip().replace("/", "\\").rstrip("\\")
        if not root:
            self.w_path.setStyleSheet("border: 1px solid #c0392b;")
            return
        setSetting(self.db_path, ARCHIVE_ROOT_KEY, root)
        setSetting(self.db_path, "archive_subdir_crim", self.cb_crim.currentText().strip())
        setSetting(self.db_path, "archive_subdir_gen",  self.cb_gen.currentText().strip())
        clearPdfIndexCache()
        self.accept()
