"""lib/auth_manager.py 權限 / 密碼邏輯單元測試（暫存 sqlite，無 GUI）。

涵蓋：
  - can() 權限矩陣（admin 全可、user 只能 edit）
  - is_admin()
  - login 正確/錯誤密碼、登出
  - change_password 舊密碼驗證 + 寫回 round-trip

注意：AuthManager 是單例，但這裡直接 `AuthManager()` 建獨立實例避免污染全域
單例狀態（_role 預設 'user'）。
執行：專案根目錄下 `python -m unittest tests.test_auth_manager`
"""
import os
import sys
import hashlib
import sqlite3
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.auth_manager import AuthManager


def _hash(p):
    return hashlib.sha256(p.encode()).hexdigest()


class _AuthBase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE App_Settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO App_Settings VALUES('admin_password_hash', ?)",
            (_hash("0000"),))
        conn.commit()
        conn.close()
        self.auth = AuthManager()   # 獨立實例，不動全域單例

    def tearDown(self):
        os.remove(self.db_path)


class TestPermissions(_AuthBase):
    def test_default_is_user(self):
        self.assertEqual(self.auth.current_role, "user")
        self.assertFalse(self.auth.is_admin())

    def test_user_can_only_edit(self):
        self.assertTrue(self.auth.can("edit"))
        self.assertFalse(self.auth.can("delete"))
        self.assertFalse(self.auth.can("ref"))

    def test_admin_can_everything(self):
        self.auth.login("0000", self.db_path)
        self.assertTrue(self.auth.is_admin())
        for action in ("edit", "delete", "ref", "anything"):
            self.assertTrue(self.auth.can(action))


class TestLogin(_AuthBase):
    def test_correct_password(self):
        self.assertTrue(self.auth.login("0000", self.db_path))
        self.assertEqual(self.auth.current_role, "admin")

    def test_wrong_password(self):
        self.assertFalse(self.auth.login("9999", self.db_path))
        self.assertEqual(self.auth.current_role, "user")

    def test_logout(self):
        self.auth.login("0000", self.db_path)
        self.auth.logout()
        self.assertEqual(self.auth.current_role, "user")
        self.assertFalse(self.auth.is_admin())

    def test_bad_db_path(self):
        self.assertFalse(self.auth.login("0000", "Z:/does/not/exist.db"))


class TestChangePassword(_AuthBase):
    def test_change_then_login_with_new(self):
        self.assertTrue(
            self.auth.change_password("0000", "1234", self.db_path))
        # 舊密碼失效、新密碼可登入
        self.assertFalse(self.auth.login("0000", self.db_path))
        self.assertTrue(self.auth.login("1234", self.db_path))
        # DB 內確實存的是新密碼的 hash
        conn = sqlite3.connect(self.db_path)
        val = conn.execute(
            "SELECT value FROM App_Settings WHERE key='admin_password_hash'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(val, _hash("1234"))

    def test_wrong_old_password_rejected(self):
        self.assertFalse(
            self.auth.change_password("xxxx", "1234", self.db_path))
        # 密碼未變
        self.assertTrue(self.auth.login("0000", self.db_path))


if __name__ == "__main__":
    unittest.main()
