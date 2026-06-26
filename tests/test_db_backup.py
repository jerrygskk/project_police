"""lib.db_backup 純邏輯與 sqlite backup round-trip 測試。"""
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from lib import db_backup


class TestDailyDue(unittest.TestCase):
    def test_due_when_today_absent(self):
        self.assertTrue(db_backup.is_daily_due([date(2026, 6, 25)], date(2026, 6, 26)))

    def test_not_due_when_today_present(self):
        d = date(2026, 6, 26)
        self.assertFalse(db_backup.is_daily_due([date(2026, 6, 25), d], d))

    def test_due_when_empty(self):
        self.assertTrue(db_backup.is_daily_due([], date(2026, 6, 26)))


class TestWeeklyDue(unittest.TestCase):
    def test_due_when_empty(self):
        self.assertTrue(db_backup.is_weekly_due([], date(2026, 6, 26)))

    def test_not_due_same_iso_week(self):
        # 2026-06-22(週一) 與 2026-06-26(週五) 同一 ISO 週
        self.assertFalse(
            db_backup.is_weekly_due([date(2026, 6, 22)], date(2026, 6, 26)))

    def test_due_previous_week(self):
        self.assertTrue(
            db_backup.is_weekly_due([date(2026, 6, 19)], date(2026, 6, 26)))


class TestParse(unittest.TestCase):
    def test_daily_roundtrip(self):
        d = date(2026, 6, 26)
        self.assertEqual(
            db_backup.parse_daily_dates([db_backup.daily_filename(d)]), [d])

    def test_weekly_roundtrip(self):
        d = date(2026, 6, 26)
        self.assertEqual(
            db_backup.parse_weekly_dates([db_backup.weekly_filename(d)]), [d])

    def test_daily_ignores_weekly_and_junk(self):
        names = [db_backup.weekly_filename(date(2026, 6, 26)),
                 "dbfile.db", "foo.txt", "dbfile_backup_day_bad.db"]
        self.assertEqual(db_backup.parse_daily_dates(names), [])


class TestPrune(unittest.TestCase):
    def test_keeps_recent_drops_old(self):
        dates = [date(2026, 6, d) for d in (20, 21, 22, 23, 24, 25, 26)]
        # 留最近 3 份 → 該刪最舊 4 份
        self.assertEqual(
            db_backup.prune_targets(dates, 3),
            [date(2026, 6, 20), date(2026, 6, 21),
             date(2026, 6, 22), date(2026, 6, 23)])

    def test_nothing_to_prune_within_keep(self):
        dates = [date(2026, 6, 25), date(2026, 6, 26)]
        self.assertEqual(db_backup.prune_targets(dates, 7), [])


class TestRunAutoBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "dbfile.db")
        conn = sqlite3.connect(self.src)
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany("INSERT INTO t(v) VALUES(?)", [("a",), ("b",), ("c",)])
        conn.commit()
        conn.close()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_do_backup_roundtrip(self):
        dest = os.path.join(self.tmp, "copy.db")
        self.assertTrue(db_backup.do_backup(self.src, dest))
        self.assertTrue(os.path.exists(dest))
        self.assertFalse(os.path.exists(dest + ".tmp"))  # tmp 已換掉
        conn = sqlite3.connect(dest)
        n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        conn.close()
        self.assertEqual(n, 3)

    def test_creates_daily_and_weekly(self):
        db_backup.run_auto_backup(self.src)
        bdir = db_backup.backup_dir(self.src)
        names = os.listdir(bdir)
        self.assertEqual(len(db_backup.parse_daily_dates(names)), 1)
        self.assertEqual(len(db_backup.parse_weekly_dates(names)), 1)

    def test_same_day_reopen_is_idempotent(self):
        db_backup.run_auto_backup(self.src)
        db_backup.run_auto_backup(self.src)  # 同日再開不應多備
        names = os.listdir(db_backup.backup_dir(self.src))
        self.assertEqual(len(db_backup.parse_daily_dates(names)), 1)
        self.assertEqual(len(db_backup.parse_weekly_dates(names)), 1)


if __name__ == "__main__":
    unittest.main()
