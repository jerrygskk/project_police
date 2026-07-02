import os, sqlite3, tempfile, unittest
from lib.db_utils import INPUT_LOCK_KEYS, isInputLocked, setSetting


class TestInputLock(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db"); os.close(fd)
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE App_Settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit(); conn.close()

    def tearDown(self):
        os.remove(self.db)

    def test_keys_present(self):
        self.assertEqual(set(INPUT_LOCK_KEYS), {"task", "crim", "gen"})

    def test_default_unlocked(self):
        for kind in INPUT_LOCK_KEYS:
            self.assertFalse(isInputLocked(self.db, kind))

    def test_locked_when_one(self):
        setSetting(self.db, INPUT_LOCK_KEYS["task"], "1")
        self.assertTrue(isInputLocked(self.db, "task"))
        self.assertFalse(isInputLocked(self.db, "crim"))

    def test_zero_and_junk_are_unlocked(self):
        setSetting(self.db, INPUT_LOCK_KEYS["gen"], "0")
        self.assertFalse(isInputLocked(self.db, "gen"))
        setSetting(self.db, INPUT_LOCK_KEYS["gen"], "x")
        self.assertFalse(isInputLocked(self.db, "gen"))

    def test_unknown_kind_is_false(self):
        self.assertFalse(isInputLocked(self.db, "nope"))


if __name__ == "__main__":
    unittest.main()
