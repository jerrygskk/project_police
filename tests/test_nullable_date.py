import unittest

from PySide6.QtCore import Qt

from ui_utils.widgets import nullableDateKeyAction


class TestNullableDateKeyAction(unittest.TestCase):
    """可空白 QDateEdit 鍵盤離開特殊值的決策邏輯（純邏輯回歸）。"""

    def test_not_blank_never_intervenes(self):
        # 已有值：任何鍵都不介入，照 Qt 原行為
        self.assertIsNone(nullableDateKeyAction(False, Qt.Key_5, "5"))
        self.assertIsNone(nullableDateKeyAction(False, Qt.Key_Up, ""))
        self.assertIsNone(nullableDateKeyAction(False, Qt.Key_A, "a"))

    def test_blank_digit_forwards(self):
        # 空白＋數字鍵：先跳今天，再讓此鍵落到段位上
        for d in "0123456789":
            self.assertEqual(
                nullableDateKeyAction(True, getattr(Qt, f"Key_{d}"), d),
                "forward",
                msg=f"digit {d}",
            )

    def test_blank_step_keys_consume(self):
        # 空白＋上下／翻頁鍵：先跳今天並消化，避免在今天之上再 ±1
        for key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
            self.assertEqual(nullableDateKeyAction(True, key, ""), "consume")

    def test_blank_other_keys_ignored(self):
        # 空白＋非編輯鍵（字母／方向左右／Tab）：不介入
        self.assertIsNone(nullableDateKeyAction(True, Qt.Key_A, "a"))
        self.assertIsNone(nullableDateKeyAction(True, Qt.Key_Left, ""))
        self.assertIsNone(nullableDateKeyAction(True, Qt.Key_Right, ""))
        self.assertIsNone(nullableDateKeyAction(True, Qt.Key_Tab, "\t"))

    def test_blank_non_ascii_digit_text_ignored(self):
        # 空白＋非數字可見字元：不介入（text.isdigit() 為 False 的符號）
        self.assertIsNone(nullableDateKeyAction(True, Qt.Key_Slash, "/"))
        self.assertIsNone(nullableDateKeyAction(True, Qt.Key_Minus, "-"))


if __name__ == "__main__":
    unittest.main()
