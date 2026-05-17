import sqlite3
import pandas as pd
import os
import re
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# 1. 配置
DB_NAME = 'dbfile.db'
EXCEL_FILE = 'ori.xlsm'
SQL_INIT_FILE = 'init_ref_tables.sql'

SHEET_CONFIGS = {
    'Task': {
        'sheet': '交辦單-收發紀錄', 'header': 0,
        'mapping': {
            '編號': ('doc_id', 'str', None),
            '收文日期': ('receive_date', 'date', None),
            '收文人員': ('receive_id', 'str', 'personnel'),
            '業務組': ('dept_id', 'str', 'dept'),
            '交辦事由': ('subject', 'str', None),
            '所承辦人': ('processor_id', 'str', 'personnel'),
            '限辦日期': ('deadline', 'date', None),
            '發文日期': ('dispatch_date', 'date', None),
            '送文人員': ('sender_id', 'str', 'personnel'),
            '時間戳記': ('timestamp', 'datetime', None)
        }
    },
    'Criminal': {
        'sheet': '刑案-收發紀錄', 'header': 1,
        'mapping': {
            '送文編號': ('doc_id', 'str', None), '陳報日期': ('report_date', 'date', None),
            '送文人員': ('sender_id', 'str', 'personnel'), '案類': ('case_type', 'str', 'case_type'),
            '發文分類': ('case_status', 'str', 'case_status'), '主承辦/查獲人': ('processor_id', 'str', 'personnel'),
            '嫌疑人/案由': ('subject_summary', 'str', None), '受理/查獲日期': ('occurrence_date', 'date', None),
            '報案人': ('reporter_name', 'str', None), '受理人': ('receiver_id', 'str', 'personnel'),
            '紙本': ('is_reported', 'bool', None), '電子檔': ('is_electronic', 'bool', None)
        }
    },
    'General': {
        'sheet': '陳報單-收發紀錄', 'header': 1,
        'mapping': {
            '送文編號': ('doc_id', 'str', None), '陳報日期': ('report_date', 'date', None),
            '送文人員': ('sender_id', 'str', 'personnel'), '業務單位/分類': ('dept_id', 'str', 'dept'),
            '發文分類': ('gen_cat_id', 'str', 'gen_cat'), '陳報主旨': ('subject', 'str', None),
            '陳報人': ('processor_id', 'str', 'personnel'), '欄1': ('is_reported', 'bool', None), '欄2': ('is_electronic', 'bool', None)
        }
    }
}

def run_sync():
    if not os.path.exists(EXCEL_FILE) or not os.path.exists(SQL_INIT_FILE):
        print("❌ 錯誤: 找不到原始檔案"); return

    with open(SQL_INIT_FILE, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    def get_map(table_name):
        match = re.search(rf"INSERT INTO {table_name}.*?VALUES\s*(.*?);", sql_content, re.S)
        return {n.strip(): i.strip() for i, n in re.findall(r"\('([^']+?)','([^']+?)'", match.group(1))} if match else {}

    maps = {k: get_map(v) for k, v in {
        'dept': 'Ref_Departments', 'personnel': 'Ref_Personnel', 
        'case_status': 'Ref_Case_Status', 'case_type': 'Ref_CaseTypes', 'gen_cat': 'Ref_General_Category'}.items()}

    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()

    try:
        print("⚙️ 初始化資料庫結構與視圖...")
        cur.executescript(sql_content); conn.commit()
        xls = pd.ExcelFile(EXCEL_FILE, engine='openpyxl')

        for key, cfg in SHEET_CONFIGS.items():
            if cfg['sheet'] not in xls.sheet_names: continue
            df = pd.read_excel(xls, cfg['sheet'], header=cfg['header'])
            if df.empty: continue
            df.columns = [str(c).strip() for c in df.columns]

            processed = pd.DataFrame()
            for ex_col, (db_col, dtype, m_key) in cfg['mapping'].items():
                if ex_col not in df.columns: continue
                col = df[ex_col].copy()

                if dtype == 'str':
                    col = col.astype(str).str.strip().replace('nan', None)
                    if m_key: col = col.map(maps[m_key]).fillna(col)
                elif dtype == 'bool':
                    bm = {'Y':1,'N':0,'1':1,'0':0,'1.0':1,'0.0':0,'是':1,'否':0,'TRUE':1,'FALSE':0}
                    col = col.astype(str).str.strip().str.upper().map(bm).fillna(0).astype(int)
                elif dtype in ['date', 'datetime']:
                    num = pd.to_numeric(col, errors='coerce')
                    mask = num.notnull() & (num > 1) & (num < 100000)
                    res = pd.Series(index=col.index, dtype='datetime64[ns]')
                    res.update(pd.to_datetime(num[mask], unit='D', origin='1899-12-30'))
                    res.update(pd.to_datetime(col[~mask], errors='coerce'))
                    fmt = '%Y-%m-%d' if dtype == 'date' else '%Y-%m-%d %H:%M:%S'
                    col = res.dt.strftime(fmt).where(res.notnull(), None)
                processed[db_col] = col

            processed = processed.dropna(subset=['doc_id'])
            for _, r in processed.iterrows():
                cur.execute(f"REPLACE INTO Document_{key} ({', '.join(r.index)}) VALUES ({', '.join(['?']*len(r))})", 
                            tuple(None if pd.isna(v) else v for v in r.values))
            print(f"✅ {cfg['sheet']}: 資料匯入成功")
        conn.commit()
    except Exception as e:
        print(f"❌ 錯誤: {e}"); import traceback; traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    run_sync()