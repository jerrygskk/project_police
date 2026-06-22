"""個資防呆：push 前確認 git 追蹤/已提交的內容不含真實人名。

設計重點：
  - 只掃「git 追蹤/已提交」的內容，不掃工作樹的本機真實資料。
    dbfile.db 設了 skip-worktree（本機可換成真資料），故讀「已提交的 blob」
    (git show HEAD:dbfile.db) 比對，避免本機真資料造成誤報。
  - 比對清單 tests/pii_denylist.local.txt 為本機檔（已 gitignore，不入庫，
    才不會把真名又帶進 repo）；清單不存在時自動 skip（別人 clone/CI 不會壞）。
  - 命中即 fail，並列出檔名與名字，提醒「替換後才能 push」。

執行：專案根目錄下 `python -m unittest tests.test_no_pii`
"""
import os
import subprocess
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DENYLIST = os.path.join(_ROOT, "tests", "pii_denylist.local.txt")
# 只掃會帶字串個資的文字類追蹤檔；二進位 dbfile.db 另以 blob bytes 掃。
_TEXT_EXT = (".py", ".md", ".txt", ".ui", ".qrc", ".sql", ".json")


def _git(*args):
    return subprocess.run(["git", "-C", _ROOT, *args],
                          capture_output=True).stdout


def _load_denylist():
    if not os.path.exists(_DENYLIST):
        return []
    names = []
    with open(_DENYLIST, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                names.append(s)
    return names


class TestNoPII(unittest.TestCase):
    def setUp(self):
        self.deny = _load_denylist()
        if not self.deny:
            self.skipTest(f"找不到 {os.path.relpath(_DENYLIST, _ROOT)}，跳過個資掃描")

    def test_tracked_text_files_clean(self):
        """所有 git 追蹤的文字檔不得含 denylist 真名。"""
        tracked = _git("ls-files", "-z").split(b"\x00")
        hits = []
        for rel in (p.decode("utf-8") for p in tracked if p):
            if not rel.lower().endswith(_TEXT_EXT):
                continue
            blob = _git("show", f"HEAD:{rel}")
            try:
                text = blob.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for name in self.deny:
                if name in text:
                    hits.append(f"{rel}：{name}")
        self.assertEqual(
            hits, [],
            "git 追蹤檔含真實人名，替換後才能 push：\n  " + "\n  ".join(hits))

    def test_committed_dbfile_clean(self):
        """已提交的 dbfile.db（含 slack space）不得含 denylist 真名。
        VACUUM 過的乾淨空殼應通過；誤提交真資料 DB 會被擋下。"""
        blob = _git("show", "HEAD:dbfile.db")
        if not blob:
            self.skipTest("HEAD 無 dbfile.db")
        hits = [name for name in self.deny if name.encode("utf-8") in blob]
        self.assertEqual(
            hits, [],
            "已提交的 dbfile.db 含真實人名（可能未 VACUUM 或誤提交真資料），"
            "替換為乾淨空殼後才能 push：\n  " + "\n  ".join(hits))


if __name__ == "__main__":
    unittest.main()
