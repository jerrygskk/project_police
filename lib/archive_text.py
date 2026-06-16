"""歸檔比對用的純文字/檔名工具（無 Qt、無狀態）。

從 tabs/tab_archive.py 抽出，便於單獨單元測試。
名稱保留底線前綴以維持呼叫端不變（顯式 import 不受 `_` 影響）。
"""
import os
import re


def _trimName(name):
    """承辦人去後綴：匿名-01 / 匿名-19.06 → 匿名 / 匿名"""
    if not name:
        return ""
    return re.split(r"[-－]", str(name))[0].strip()


def _tokenize(text):
    """斷詞：依分隔符切；再從每個片段抽出其中的中文連續段做 2 字滑動片段。
    （檔名常見日期與主旨黏連，如 1150101匿名竊盜案，需抽出中文段才比得到。）"""
    toks = set()
    for x in re.split(r"[\s_\-－.,，、（）()]+", str(text)):
        x = x.strip()
        if len(x) >= 2:
            toks.add(x)
        # 抽出片段內所有中文連續段（即使與數字/英文黏連）
        for seg in re.findall(r"[\u4e00-\u9fff]+", x):
            if len(seg) >= 2:
                toks.add(seg)
            if len(seg) >= 3:
                for i in range(len(seg) - 1):
                    toks.add(seg[i:i + 2])
    return toks


def _parseDate(filename):
    """從舊檔名拆出日期片段，拆不到回空字串。
    以民國年為主（如 1150612 = 115年6月12日，亦容忍 115-06-12 / 115.6.12），
    保留民國年原樣；若抓不到民國年，再嘗試西元 20xx 格式。
    """
    base = os.path.splitext(filename)[0]
    # 民國年：1xx(3碼) + 月 + 日，分隔可有可無，並做月/日合理性檢查
    m = re.search(r"(1\d{2})[-.\/]?(\d{1,2})[-.\/]?(\d{1,2})", base)
    if m:
        try:
            mo, d = int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{m.group(1)}{mo:02d}{d:02d}"
        except ValueError:
            pass
    # 退而求其次：西元 20xx
    m = re.search(r"(20\d{2})[-.\/]?(\d{1,2})[-.\/]?(\d{1,2})", base)
    if m:
        try:
            mo, d = int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{m.group(1)}{mo:02d}{d:02d}"
        except ValueError:
            pass
    return ""


def _sanitize(text):
    """檔名安全化：移除 Windows 不允許的字元。"""
    return re.sub(r'[\\/:*?"<>|]', "", str(text or "")).strip()


def _pkOf(filepath):
    """取檔名最前段（第一個 - / － 之前）為 PK；正規檔名格式為 PK-日期-…。"""
    base = os.path.splitext(os.path.basename(filepath))[0]
    m = re.match(r"^\s*([^\-－]+)", base)
    return m.group(1).strip() if m else ""
