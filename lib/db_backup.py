"""平時自動備份：常規祖孫式（GFS）輪替，做到每週為止（本機）。

單機程式平時零備份，硬碟外的損毀（檔案毀損、誤刪、DB malformed）一旦發生即無救。
本模組在 `dbfile.db` 旁維護 `backups/` 子夾，於程式啟動時做兩層帶日期的備份，
各自輪替修剪（不做 monthly 那一層）：

- 每日：`dbfile_backup_day_YYYYMMDD.db`，每天第一次開啟時建一份（當天再開不重做），
        保留最近 `DAILY_KEEP` 份、較舊的刪除。最近一週有逐日粒度。
- 每週：`dbfile_backup_week_YYYYMMDD.db`，每週（ISO 週）第一次開啟時建一份，
        保留最近 `WEEKLY_KEEP` 份。誤刪當天靠每日救、過幾天才發現靠每週救。

備份用 sqlite3 backup API（一致性快照，即使有並發寫入也安全），先寫 `.tmp`
再 `os.replace` 原子換上（中途失敗不會毀掉既有好檔）。**全程失敗一律靜默退讓、
寫 error.log，絕不阻擋程式開啟**（同 app_lock 哲學）。

純邏輯（filename/parse/is_*_due/prune_targets）可單測。
本層只做本機備份，**救不了硬碟整顆故障**；異地備份為後續另一層。
"""
import logging
import os
import re
import sqlite3
from datetime import datetime

BACKUP_DIR_NAME = "backups"
DAILY_PREFIX    = "dbfile_backup_day_"
WEEKLY_PREFIX   = "dbfile_backup_week_"
DAILY_KEEP      = 7    # 每日備份保留份數（最近一週逐日）
WEEKLY_KEEP     = 4    # 每週備份保留份數（約一個月）

_DAILY_RE  = re.compile(r"^dbfile_backup_day_(\d{8})\.db$")
_WEEKLY_RE = re.compile(r"^dbfile_backup_week_(\d{8})\.db$")


# ── 路徑 / 檔名 ─────────────────────────────────────────────────
def backup_dir(db_path):
    """備份子夾：與 dbfile.db 同資料夾下的 backups/。"""
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), BACKUP_DIR_NAME)


def daily_filename(d):
    return f"{DAILY_PREFIX}{d.strftime('%Y%m%d')}.db"


def weekly_filename(d):
    return f"{WEEKLY_PREFIX}{d.strftime('%Y%m%d')}.db"


# ── 純邏輯（可單測）────────────────────────────────────────────
def _parse_dates(regex, filenames):
    out = []
    for name in filenames:
        m = regex.match(name)
        if not m:
            continue
        try:
            out.append(datetime.strptime(m.group(1), "%Y%m%d").date())
        except ValueError:
            pass
    return out


def parse_daily_dates(filenames):
    """從檔名清單解析出所有每日備份的日期。"""
    return _parse_dates(_DAILY_RE, filenames)


def parse_weekly_dates(filenames):
    """從檔名清單解析出所有每週備份的日期。"""
    return _parse_dates(_WEEKLY_RE, filenames)


def is_daily_due(existing_dates, today):
    """每日備份是否到期：今天尚未備份過。"""
    return today not in existing_dates


def is_weekly_due(existing_dates, today):
    """每週備份是否到期：既有週檔中無任一落在 today 的同一 ISO 週。"""
    wk = today.isocalendar()[:2]   # (ISO 年, ISO 週)
    return not any(d.isocalendar()[:2] == wk for d in existing_dates)


def prune_targets(dates, keep):
    """回傳該刪除的日期（保留最近 keep 份，其餘較舊者刪）。"""
    if keep is None or len(dates) <= keep:
        return []
    return sorted(dates)[:-keep]


# ── I/O（失敗靜默）─────────────────────────────────────────────
def do_backup(db_path, dest):
    """以 sqlite3 backup API 做一致性快照；先寫 .tmp 再原子 replace。

    成功回 True、失敗回 False（並記 error.log）；不拋例外。
    """
    tmp = dest + ".tmp"
    try:
        src = sqlite3.connect(db_path)
        try:
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        os.replace(tmp, dest)
        return True
    except Exception:
        logging.error("自動備份寫入失敗：%s", dest, exc_info=True)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False


def _prune(bdir, prefix, dates, keep):
    """刪除超出保留份數的舊備份；失敗靜默。"""
    for d in prune_targets(dates, keep):
        try:
            os.remove(os.path.join(bdir, f"{prefix}{d.strftime('%Y%m%d')}.db"))
        except OSError:
            pass


def run_auto_backup(db_path, now=None):
    """啟動時呼叫：依到期判斷做每日／每週備份並輪替修剪。全程靜默，絕不阻擋開程式。"""
    try:
        today = (now or datetime.now()).date()
        bdir = backup_dir(db_path)
        os.makedirs(bdir, exist_ok=True)

        # 每日
        daily = parse_daily_dates(os.listdir(bdir))
        if is_daily_due(daily, today):
            if do_backup(db_path, os.path.join(bdir, daily_filename(today))):
                daily.append(today)
        _prune(bdir, DAILY_PREFIX, daily, DAILY_KEEP)

        # 每週
        weekly = parse_weekly_dates(os.listdir(bdir))
        if is_weekly_due(weekly, today):
            if do_backup(db_path, os.path.join(bdir, weekly_filename(today))):
                weekly.append(today)
        _prune(bdir, WEEKLY_PREFIX, weekly, WEEKLY_KEEP)
    except Exception:
        logging.error("自動備份程序異常", exc_info=True)
