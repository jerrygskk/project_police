"""
auth_manager.py — 權限控管

設計說明：
  - 單例模式：AuthManager.instance() 取得全域實例
  - 啟動時 current_role 永遠是 'user'
  - 設定 Tab 呼叫 login(password, db_path) 驗證，成功後升為 'admin'
  - 離開設定 Tab 時呼叫 logout()，降回 'user'
  - 各 Tab 需要判斷權限時，查 AuthManager.instance().can(action)

使用範例：
    from lib.auth_manager import AuthManager

    def _deleteSomething(self, doc_id):
        if not AuthManager.instance().can("delete"):
            msgWarning("權限不足", "請先登入管理者帳號")
            return
        ...

    AuthManager.instance().role_changed.connect(self._onRoleChanged)
"""

import hashlib
import sqlite3

from PySide6.QtCore import QObject, Signal


class AuthManager(QObject):
    """
    全域單例，管理目前登入身份。

    Roles:
        'user'  — 一般使用者（預設）
        'admin' — 管理者，可修刪改所有資料及維護參照表

    Permissions:
        'delete' — 刪除資料
        'edit'   — 修改資料
        'ref'    — 維護參照表（人員、部門、案件類型）
    """

    role_changed = Signal(str)   # 身份變更時 emit，帶新的 role 字串

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._role = 'user'

    # ── 查詢 ────────────────────────────────────────────
    @property
    def current_role(self):
        return self._role

    def is_admin(self) -> bool:
        """便捷判斷：當前是否為管理者。等同 current_role == 'admin'。"""
        return self._role == 'admin'

    def can(self, action: str) -> bool:
        """
        回傳當前身份是否有權執行 action。
        admin 可做一切，user 不能 delete / ref。
        """
        if self._role == 'admin':
            return True
        USER_ALLOWED = {'edit'}
        return action in USER_ALLOWED

    # ── 登入 / 登出（由設定 Tab 呼叫）────────────────────
    def login(self, password: str, db_path: str) -> bool:
        """
        驗證密碼並提升為 admin。
        從 App_Settings 讀取 admin_password_hash，與 SHA-256(password) 比對。
        """
        try:
            h    = hashlib.sha256(password.encode()).hexdigest()
            conn = sqlite3.connect(db_path)
            row  = conn.execute(
                "SELECT value FROM App_Settings WHERE key='admin_password_hash'"
            ).fetchone()
            conn.close()
            if row and row[0] == h:
                self._role = 'admin'
                self.role_changed.emit(self._role)
                return True
        except Exception:
            pass
        return False

    def logout(self):
        """降回一般使用者身份。"""
        if self._role != 'user':
            self._role = 'user'
            self.role_changed.emit(self._role)

    def change_password(self, old_password: str, new_password: str, db_path: str) -> bool:
        """
        變更管理者密碼。
        需先通過舊密碼驗證，再將新密碼 hash 寫入 App_Settings。
        """
        try:
            old_h = hashlib.sha256(old_password.encode()).hexdigest()
            conn  = sqlite3.connect(db_path)
            row   = conn.execute(
                "SELECT value FROM App_Settings WHERE key='admin_password_hash'"
            ).fetchone()
            if not row or row[0] != old_h:
                conn.close()
                return False
            new_h = hashlib.sha256(new_password.encode()).hexdigest()
            conn.execute(
                "UPDATE App_Settings SET value=? WHERE key='admin_password_hash'",
                (new_h,)
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
