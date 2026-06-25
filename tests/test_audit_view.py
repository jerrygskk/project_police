"""操作紀錄檢視（tab_audit）純邏輯測試：detail 解析。"""
import unittest

from tabs.tab_audit import parseDetail


class TestParseDetail(unittest.TestCase):

    def test_full(self):
        self.assertEqual(
            parseDetail("[刑案][刪除]主旨：機車失竊案"),
            ("刑案", "刪除", "主旨：機車失竊案"))

    def test_empty_content(self):
        self.assertEqual(parseDetail("[系統][登入失敗]"),
                         ("系統", "登入失敗", ""))

    def test_content_with_brackets(self):
        # 內容含中括號不應被誤切（只吃前兩組 [..]）
        self.assertEqual(
            parseDetail("[歸檔][取消][電子] 主旨：協尋"),
            ("歸檔", "取消", "[電子] 主旨：協尋"))

    def test_no_format(self):
        self.assertEqual(parseDetail("純文字沒有前綴"),
                         ("", "", "純文字沒有前綴"))

    def test_blank(self):
        self.assertEqual(parseDetail(""), ("", "", ""))
        self.assertEqual(parseDetail(None), ("", "", ""))

    def test_arrow_content(self):
        self.assertEqual(
            parseDetail("[交辦][修改]王志明 → 林佳蓉"),
            ("交辦", "修改", "王志明 → 林佳蓉"))


if __name__ == "__main__":
    unittest.main()
