"""
auth_manager.py — 權限控管骨架（尚未接線，預留給設定 Tab 使用）

設計說明：
  - 單例模式：AuthManager.instance() 取得全域實例
  - 目前 current_role 永遠是 'user'，等設定 Tab 完成後接線
  - 各 Tab 需要判斷權限時，查 AuthManager.instance().current_role
  - 登入成功後 emit role_changed 信號，各 Tab 訂閱後刷新 UI

使用範例（未來在各 Tab 接線時）：
    from auth_manager import AuthManager

    # 判斷是否有刪除權限
    def _deleteSomething(self, doc_id):
        if not AuthManager.instance().can("delete"):
            msgWarning("權限不足", "請先登入高權限帳號")
            return
        ...

    # 訂閱身份變更，刷新按鈕 enable/disable
    AuthManager.instance().role_changed.connect(self._onRoleChanged)
"""

from PySide6.QtCore import QObject, Signal


class AuthManager(QObject):
    """
    全域單例，管理目前登入身份。

    Roles:
        'user'  — 一般使用者（預設）
        'admin' — 高權限，可修刪改所有資料及維護參照表

    Permissions（未來擴充用）:
        'delete' — 刪除資料
        'edit'   — 修改資料
        'ref'    — 維護參照表（人員、部門等）
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

    def can(self, action: str) -> bool:
        """
        回傳當前身份是否有權執行 action。
        目前 admin 可做一切，user 不能 delete / ref。
        """
        if self._role == 'admin':
            return True
        # user 允許的操作（之後依需求調整）
        USER_ALLOWED = {'edit'}
        return action in USER_ALLOWED

    # ── 登入 / 登出（由設定 Tab 呼叫）────────────────────
    def login(self, password: str) -> bool:
        """
        驗證密碼並提升為 admin。
        密碼驗證邏輯由設定 Tab 實作後填入。
        目前永遠回傳 False（骨架，尚未實作）。
        """
        # TODO: 實作密碼驗證（hash 比對或 DB 查詢）
        return False

    def logout(self):
        """降回一般使用者身份。"""
        if self._role != 'user':
            self._role = 'user'
            self.role_changed.emit(self._role)
