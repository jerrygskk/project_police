import pandas as pd
import sqlite3
from datetime import datetime
import os

# --- 設定區 ---
EXCEL_FILE = '●收發公文電子登錄簿-龍興所115年度.xlsm'
DB_FILE = 'dbfile.db'

def convert_date(val):
    if pd.isna(val) or str(val).strip() == "" or str(val).lower() == 'nan': return None
    if isinstance(val, (datetime, pd.Timestamp)):
        y = val.year + 1911 if val.year < 1911 else val.year
        return f"{y}-{val.month:02d}-{val.day:02d}"
    try:
        s = str(val).strip().replace(" ", "").replace("　", "") # 移除空白
        if '/' in s:
            p = s.split('/')
            return f"{int(p)+1911}-{int(p):02d}-{int(p):02d}"
    except: pass
    return None

def get_smart_staff_id(val, s_map):
    """
    智慧比對人員 ID：
    1. 精確比對 (例如: 簡雄雄-25)
    2. 模糊比對 (若輸入 '簡雄雄'，自動找包含這三個字的長名字)
    """
    name = str(val).strip().replace(" ", "").replace("　", "")
    if not name or name == 'nan': return None
    
    # A. 直接命中
    if name in s_map: return s_map[name]
    
    # B. 模糊比對：只要現有名單(長名)包含輸入的(短名)，就回傳長名的ID
    # 例如：輸入「簡雄雄」，匹配到「簡雄雄-25」
    for full_name, s_id in s_map.items():
        if name in full_name:
            return s_id
            
    return None

def start_sync():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    now_gmt8 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 載入主檔對照 (s_map 只存長名字，方便後續比對)
    cur.execute("SELECT staff_id, staff_name FROM Ref_Personnel ORDER BY length(staff_name) DESC")
    s_map = {n.strip().replace(" ", "").replace("　", ""): i for i, n in cur.fetchall()}
    
    cur.execute("SELECT dept_id, dept_name FROM Ref_Departments")
    d_map = {n.strip(): i for i, n in cur.fetchall()}
    
    cur.execute("SELECT cat_id, cat_name FROM Ref_Category")
    cat_map = {n.strip(): i for i, n in cur.fetchall()}
    
    cur.execute("SELECT case_id, case_name FROM Ref_CaseTypes")
    case_map = {n.strip(): i for i, n in cur.fetchall()}

    # --- A. 交辦單 ---
    try:
        print("▶ 同步中：交辦單")
        temp_df = pd.read_excel(EXCEL_FILE, sheet_name='交辦單-收發紀錄', nrows=10)
        h_row = 0
        for i, row in temp_df.iterrows():
            if '條碼' in row.values: h_row = i + 1; break
        df1 = pd.read_excel(EXCEL_FILE, sheet_name='交辦單-收發紀錄', header=h_row)
        
        for _, r in df1.iterrows():
            if pd.isna(r['編號']): continue
            cur.execute('''INSERT OR REPLACE INTO Task_Assignment 
                (serial_no, subject, dept_name, assignee_id, sender_id, deadline, dispatch_date, timestamp) 
                VALUES (?,?,?,?,?,?,?,?)''',
                (int(r['編號']), r['交辦事由'], d_map.get(str(r['業務組']).strip()), 
                 get_smart_staff_id(r['所承辦人'], s_map), 
                 get_smart_staff_id(r['送文人員'], s_map), 
                 convert_date(r['限辦日期']), convert_date(r['發文日期']), r['時間戳記']))
    except Exception as e: print(f"✘ 交辦單錯誤: {e}")

    # --- B. 刑案紀錄 (改用 Index 抓取，防止標題字元錯誤) ---
    try:
        print("▶ 同步中：刑案紀錄")
        # 讀取時直接跳過前兩行（標題列），從第 3 行開始抓資料
        df2 = pd.read_excel(EXCEL_FILE, sheet_name='刑案-收發紀錄', header=None, skiprows=2)
        
        for _, r in df2.iterrows():
            # 根據截圖：A=1, B=2, C=3... (程式 index 從 0 開始)
            # 所以：B欄(編號)是 index 1, C欄(日期)是 index 2...
            
            if pd.isna(r[1]): continue # B 欄「送文編號」為空就跳過
            
            try: d_id = int(r[1])
            except: continue
            
            cur.execute('''INSERT OR REPLACE INTO Document_Criminal 
                (dispatch_id, report_date, sender_id, category, case_type, 
                 suspect, detect_date, processor_id, reporter_name, is_paper, is_electronic) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    d_id,                               # B欄 (1): 送文編號
                    convert_date(r[2]),                 # C欄 (2): 陳報日期
                    get_smart_staff_id(r[3], s_map),    # D欄 (3): 送文人
                    str(r[4]).strip() if pd.notna(r[4]) else None, # E欄 (4): 分類
                    str(r[5]).strip() if pd.notna(r[5]) else None, # F欄 (5): 案類
                    str(r[7]).strip() if pd.notna(r[7]) else None, # H欄 (7): 嫌疑人/案由
                    convert_date(r[8]),                 # I欄 (8): 受理日期
                    get_smart_staff_id(r[9], s_map),    # J欄 (9): 受理人
                    str(r[10]).strip() if pd.notna(r[10]) else None, # K欄 (10): 報案人
                    1 if str(r[11]) == '1' else 0,      # L欄 (11): 紙本
                    str(r[12]).strip() if pd.notna(r[12]) else None # M欄 (12): 電子檔
                ))
    except Exception as e: 
        print(f"✘ 刑案錯誤: {e}")



    # --- C. 非刑案 ---
    try:
        print("▶ 同步中：非刑案陳報")
        temp_df3 = pd.read_excel(EXCEL_FILE, sheet_name='陳報單-收發紀錄', nrows=10)
        h3 = 0
        for i, row in temp_df3.iterrows():
            if '送文編號' in row.values: h3 = i + 1; break
        df3 = pd.read_excel(EXCEL_FILE, sheet_name='陳報單-收發紀錄', header=h3)
        
        for _, r in df3.iterrows():
            if pd.isna(r['送文編號']): continue
            cur.execute('''INSERT OR REPLACE INTO Document_General 
                (dispatch_id, report_date, sender_id, category, dept_id, reporter_id, subject, is_paper, is_reported) 
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (int(r['送文編號']), convert_date(r['陳報日期']),
                 get_smart_staff_id(r['送文人員'], s_map),
                 cat_map.get(str(r['發文分類']).strip()),
                 d_map.get(str(r['業務單位/分類']).strip()),
                 get_smart_staff_id(r['陳報人'], s_map),
                 r['陳報主旨'], 1 if str(r['欄1'])=='1' else 0, 1 if str(r['欄2'])=='Y' else 0))
    except Exception as e: print(f"✘ 非刑案錯誤: {e}")

    conn.commit()
    conn.close()
    print(f"\n✅ 同步成功")

if __name__ == "__main__":
    start_sync()
