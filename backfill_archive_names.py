#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存量補檔腳本（一次性）

情境：部分 PDF 在進資料庫前就已正名歸檔（檔名一定是 PK-日期-...），
但資料庫的 is_electronic 欄尚未記錄實際檔名。本腳本掃描指定資料夾，
依檔名最前段的 PK 對應到指定資料表，把實際檔名回填 is_electronic。

以後系統一律走資料庫存取、不再有外部歸檔，故此腳本只需執行一次。
刑案 / 一般各自獨立資料夾，請分兩次執行（指定對應的表）。

用法：
    python backfill_archive_names.py <資料夾路徑> <crim|gen> [--db dbfile.db] [--dry-run]

範例：
    python backfill_archive_names.py "D:\\歸檔\\刑案PDF" crim
    python backfill_archive_names.py "D:\\歸檔\\一般PDF" gen --dry-run

安全規則：
    - 檔名拆不出 PK，或資料庫查無此 PK → 跳過
    - 該筆已有「實際檔名」（非空、且不是預設標記）→ 不覆蓋、跳過
    - 該筆為空 或 只有預設標記「(已歸檔)」 → 回填實際檔名
    - --dry-run 只試算、不寫入
"""
import argparse
import os
import re
import sqlite3
import sys

TABLES = {
    "crim": "Document_Criminal",
    "gen": "Document_General",
}
DEFAULT_MARK = "(已歸檔)"   # 轉檔時對「原本有電子檔但無正規檔名」者塞的預設標記


def extract_pk(filename):
    """取檔名最前段（第一個 - / － 之前）為 PK，去除前後空白。"""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.match(r"^\s*([^\-－]+)", base)
    return m.group(1).strip() if m else ""


def scan_pdfs(folder):
    """掃資料夾（含子資料夾）所有 PDF，回傳 [(pk, 檔名), ...]。"""
    out = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".pdf"):
                pk = extract_pk(f)
                if pk:
                    out.append((pk, f))
    return out


def main():
    ap = argparse.ArgumentParser(description="存量已歸檔 PDF 檔名回填")
    ap.add_argument("folder", help="PDF 資料夾路徑（含子資料夾）")
    ap.add_argument("table", choices=["crim", "gen"], help="對應資料表：crim=刑案, gen=一般")
    ap.add_argument("--db", default="dbfile.db", help="資料庫檔案路徑（預設 dbfile.db）")
    ap.add_argument("--dry-run", action="store_true", help="只試算、不寫入")
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        print(f"[錯誤] 資料夾不存在：{args.folder}")
        sys.exit(1)
    if not os.path.isfile(args.db):
        print(f"[錯誤] 資料庫不存在：{args.db}")
        sys.exit(1)

    table = TABLES[args.table]
    pdfs = scan_pdfs(args.folder)
    print(f"掃描資料夾：{args.folder}")
    print(f"對應資料表：{table}")
    print(f"找到 PDF：{len(pdfs)} 個" + ("（試算模式，不寫入）" if args.dry_run else ""))
    print("-" * 60)

    conn = sqlite3.connect(args.db)
    filled, skip_nopk, skip_has, skip_dup = 0, 0, 0, 0
    seen_pk = {}

    for pk, fname in pdfs:
        # 同一 PK 對到多個 PDF：只處理第一個，其餘記為重複
        if pk in seen_pk:
            print(f"  [重複] PK={pk} 已有對應 PDF「{seen_pk[pk]}」，略過「{fname}」")
            skip_dup += 1
            continue

        row = conn.execute(
            f"SELECT is_electronic FROM {table} WHERE doc_id=?", (pk,)
        ).fetchone()
        if row is None:
            print(f"  [查無] PK={pk}（{fname}）資料庫無此筆，略過")
            skip_nopk += 1
            continue

        cur_val = row[0]
        is_real = cur_val not in (None, "", DEFAULT_MARK)
        if is_real:
            print(f"  [已有] PK={pk} 已記檔名「{cur_val}」，不覆蓋")
            skip_has += 1
            continue

        # 回填
        seen_pk[pk] = fname
        if not args.dry_run:
            conn.execute(
                f"UPDATE {table} SET is_electronic=? WHERE doc_id=?", (fname, pk)
            )
        filled += 1
        print(f"  [回填] PK={pk} ← {fname}")

    if not args.dry_run:
        conn.commit()
    conn.close()

    print("-" * 60)
    print("總結：")
    print(f"  回填        ：{filled}")
    print(f"  跳過(查無PK)：{skip_nopk}")
    print(f"  跳過(已有檔名)：{skip_has}")
    print(f"  跳過(PK重複)：{skip_dup}")
    if args.dry_run:
        print("（試算模式，未實際寫入資料庫）")


if __name__ == "__main__":
    main()
