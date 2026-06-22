"""lib/archive_text.py 純文字/檔名工具單元測試（無 Qt、無 DB）。

涵蓋 README 踩雷表登記過的歸檔檔名解析案例：
  - 黏連日期＋主旨檔名（1150101匿名竊盜案）
  - PK 為 1xx 時不被誤判成民國年
  - 承辦人去後綴（半形/全形連字號）
執行：專案根目錄下 `python -m unittest tests.test_archive_text`
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.archive_text import _trimName, _tokenize, _parseDate, _sanitize, _pkOf


class TestTrimName(unittest.TestCase):
    def test_half_width_suffix(self):
        self.assertEqual(_trimName("匿名-01"), "匿名")

    def test_full_width_suffix(self):
        self.assertEqual(_trimName("匿名－19.06"), "匿名")

    def test_dotted_suffix(self):
        self.assertEqual(_trimName("匿名-19.06"), "匿名")

    def test_no_suffix(self):
        self.assertEqual(_trimName("匿名"), "匿名")

    def test_empty_and_none(self):
        self.assertEqual(_trimName(""), "")
        self.assertEqual(_trimName(None), "")

    def test_strips_whitespace(self):
        self.assertEqual(_trimName(" 匿名 -01"), "匿名")


class TestTokenize(unittest.TestCase):
    def test_glued_date_subject_name(self):
        # 踩雷表：日期黏主旨檔名，整串中文段須抽得出來並做 2 字滑動
        toks = _tokenize("1150101匿名竊盜案")
        # 整段中文（數字前綴已被排除）
        self.assertIn("匿名竊盜案", toks)
        # 2 字滑動片段（跨人名與主旨皆涵蓋）
        for bigram in ("李小", "小美", "美竊", "竊盜", "盜案"):
            self.assertIn(bigram, toks)

    def test_separators_split(self):
        toks = _tokenize("匿名-竊盜-1150101")
        self.assertIn("匿名", toks)
        self.assertIn("竊盜", toks)

    def test_single_char_dropped(self):
        # 長度 < 2 的片段不入集合
        self.assertNotIn("王", _tokenize("王 竊盜"))

    def test_full_width_brackets(self):
        toks = _tokenize("竊盜案（匿名）")
        self.assertIn("竊盜案", toks)
        self.assertIn("匿名", toks)

    def test_empty(self):
        self.assertEqual(_tokenize(""), set())


class TestParseDate(unittest.TestCase):
    def test_minguo_compact(self):
        self.assertEqual(_parseDate("1150612匿名.pdf"), "1150612")

    def test_glued_subject(self):
        # 格式(2)：日期黏主旨
        self.assertEqual(_parseDate("1150101匿名竊盜案-匿名.pdf"), "1150101")

    # ── PK 撞號（README 踩雷表 / 真實檔名）──────────────────
    # 正規檔名「PK-日期-主旨-承辦」開頭 PK 也是 1xx，日期須前後不接數字才不被
    # PK 咬走。以下皆取自使用者提供的真實清單。
    def test_pk_prefix_not_swallowed(self):
        self.assertEqual(
            _parseDate("103-1150120-匿名遭詐欺案-匿名.pdf"), "1150120")
        self.assertEqual(
            _parseDate("109-1140109-匿名詐欺案-匿名.pdf"), "1140109")
        self.assertEqual(
            _parseDate("116-1150102-匿名遭侵占遺失物案-匿名.pdf"), "1150102")

    def test_multi_pk_prefix(self):
        # 多編號合併「268-269-1150227-…」：兩段 PK 後才是日期
        self.assertEqual(
            _parseDate("268-269-1150227-匿名公共危險案-匿名.pdf"), "1150227")
        self.assertEqual(
            _parseDate("120、224-1150125-匿名違反保護令-匿名.pdf"), "1150125")

    def test_first_invalid_run_skipped(self):
        # 第一個 7 碼湊出不合理月日要跳過，往後找合理的
        # 1159999: 月99日99不合理 → 應抓後方 1150101
        self.assertEqual(_parseDate("1159999-x-1150101案.pdf"), "1150101")

    # ── 畸形 / 無日期：不可誤判 ────────────────────────────
    def test_malformed_rejected(self):
        # 8 碼黏連、6 碼短日期、140 非有效民國年 → 一律抓不到（寧空白）
        self.assertEqual(_parseDate("11506110匿名詐欺案-匿名.pdf"), "")
        self.assertEqual(_parseDate("140-110205-匿名家暴通報-匿名.pdf"), "")

    def test_invalid_month_rejected(self):
        self.assertEqual(_parseDate("1151301.pdf"), "")   # 13 月

    def test_western_compact(self):
        self.assertEqual(_parseDate("20240612報告.pdf"), "20240612")

    def test_no_date(self):
        self.assertEqual(_parseDate("匿名竊盜案.pdf"), "")
        self.assertEqual(_parseDate("匿名遭詐騙案-匿名.pdf"), "")


class TestSanitize(unittest.TestCase):
    def test_removes_windows_illegal(self):
        self.assertEqual(_sanitize('a/b:c*d?e"f<g>h|i\\j'), "abcdefghij")

    def test_keeps_chinese(self):
        self.assertEqual(_sanitize("竊盜案 匿名"), "竊盜案 匿名")

    def test_none(self):
        self.assertEqual(_sanitize(None), "")


class TestPkOf(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_pkOf("103-1150612-竊盜案.pdf"), "103")

    def test_full_width_dash(self):
        self.assertEqual(_pkOf("CT01－主旨.pdf"), "CT01")

    def test_with_path(self):
        self.assertEqual(_pkOf(r"D:\歸檔\刑案\103-1150612.pdf"), "103")

    def test_no_dash(self):
        self.assertEqual(_pkOf("整串無分隔.pdf"), "整串無分隔")

    def test_multi_pk_takes_first(self):
        # 多編號合併取首段（第一個 - 之前）
        self.assertEqual(
            _pkOf("268-269-1150227-匿名公共危險案-匿名.pdf"), "268")

    def test_format2_no_pk(self):
        # 格式(2)「日期主旨-承辦」無 PK 段 → 取到日期黏主旨的首段（呼叫端只在
        # 已格式化檔名上用 _pkOf，這裡僅記錄無 PK 時的實際行為）
        self.assertEqual(
            _pkOf("1150101匿名竊盜案-匿名.pdf"), "1150101匿名竊盜案")


if __name__ == "__main__":
    unittest.main()
