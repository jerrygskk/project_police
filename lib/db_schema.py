# -*- coding: utf-8 -*-
"""啟動時冪等確保「附加式」結構存在（只增不改）。

界線（重要）：
  - 只放 CREATE TABLE IF NOT EXISTS 與「缺欄才加」的 ADD COLUMN——冪等、零資料風險。
  - 破壞性變更（改型別、改既有資料）不放這裡，走一次性手動腳本。
  - 本層自這版起「前瞻」維護結構：新表／新欄登記在此，第一次開程式自動長齊，
    從此免再為「新增結構」發 fix 腳本。不做回溯自愈（補密碼、改舊資料一律不碰）。
  - 失敗只記 error.log，絕不拋例外、絕不擋開程式（同 db_backup / app_lock 哲學）。
"""
import os
import logging
import sqlite3

# 應用自有、baseline 空殼以外的表。逐句獨立執行（見 ensureSchema）。
_TABLES = (
    # 操作紀錄（v1.1.0 起）
    """CREATE TABLE IF NOT EXISTS Audit_Log (
        log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts            TEXT NOT NULL,
        role          TEXT,
        action        TEXT,
        target_table  TEXT,
        target_id     TEXT,
        operator      TEXT,
        detail        TEXT
    )""",
    # 誤刪還原回收筒（方案 5）：刪除前整列快照，供還原回原 doc_id 空殼列
    """CREATE TABLE IF NOT EXISTS Trash_Documents (
        trash_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name    TEXT NOT NULL,
        doc_id        TEXT NOT NULL,
        payload       TEXT NOT NULL,
        subject       TEXT,
        doc_person    TEXT,
        deleted_ts    TEXT NOT NULL,
        deleted_role  TEXT
    )""",
)

# 既有表新增欄位：(表, 欄, 型別宣告)，缺欄才加。目前無；未來附加式加欄登記於此。
_COLUMNS = ()


def ensureSchema(db_path):
    """逐句冪等套用 _TABLES / _COLUMNS。

    各語句獨立 try：單句失敗（如多機併發短暫 locked）不影響其餘，下次啟動再補。
    整體再包一層 try：任何意外都不阻擋程式開啟。
    """
    if not db_path or not os.path.exists(db_path):
        return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        for sql in _TABLES:
            _run(conn, sql)
        for table, column, decl in _COLUMNS:
            _add_column(conn, table, column, decl)
    except Exception:
        logging.error("ensureSchema 異常", exc_info=True)
    finally:
        if conn is not None:
            conn.close()


def _run(conn, sql):
    """執行單句 DDL（自帶 commit）；失敗只記 log，不中斷其餘。"""
    try:
        conn.execute(sql)
        conn.commit()
    except Exception:
        logging.error("ensureSchema 語句失敗", exc_info=True)


def _add_column(conn, table, column, decl):
    """欄位不存在才 ADD COLUMN（冪等）；失敗只記 log。"""
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            conn.commit()
    except Exception:
        logging.error("ensureSchema 加欄失敗", exc_info=True)
