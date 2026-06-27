"""BaseTab 共用 helper 的回歸測試。

重點：_trimName 已收斂至 archive_text._trimName（單一來源），
原本 base_tab 只處理半形 -，不處理全形 －，導致全形破折號的人名去尾失敗。
"""
import unittest

from lib.base_tab import BaseTab
from lib.archive_text import _trimName as archive_trimName


class TestBaseTabTrimName(unittest.TestCase):

    def test_half_width_suffix(self):
        self.assertEqual(BaseTab._trimName("王小明-01"), "王小明")

    def test_full_width_suffix(self):
        # 修正前的 base_tab 版本只切半形 -，全形 － 會原樣留下
        self.assertEqual(BaseTab._trimName("李美華－19.06"), "李美華")

    def test_no_suffix(self):
        self.assertEqual(BaseTab._trimName("陳志明"), "陳志明")

    def test_empty_and_none(self):
        self.assertEqual(BaseTab._trimName(""), "")
        self.assertEqual(BaseTab._trimName(None), "")

    def test_delegates_to_archive_text(self):
        # 單一來源：兩者行為一致
        for s in ("王小明-01", "李美華－19.06", "陳志明", " 王小明 -01", "", None):
            self.assertEqual(BaseTab._trimName(s), archive_trimName(s))


if __name__ == "__main__":
    unittest.main()
