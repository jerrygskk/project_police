import sqlite3
import pandas as pd
import os

# ---------------------------------------------------------
# 1. 核心設定與對照表
# ---------------------------------------------------------
DB_NAME = 'document_system.db'
EXCEL_FILE = 'import_data.xlsx'

def create_reverse_map(d):
    return {str(v).strip(): k for k, v in d.items()}

# 建立名稱到 ID 的映射
MAPS = {
    'case_status': create_reverse_map({'CS01': 'A_現行犯', 'CS02': 'B_到案', 'CS03': 'B_未到案'}),
    'gen_category': create_reverse_map({'GC01': 'D_業務陳報', 'GC02': 'F_司法相驗', 'GC03': 'J_其他'}),
    'dept': create_reverse_map({'D01': '交通組', 'D02': '偵查隊', 'D03': '防治組', 'D04': '行政組', 'D05': '督察組', 'D06': '人事室', 'D07': '保民組', 'D08': '保防組', 'D09': '秘書室', 'D10': '會計室', 'D11': '勤指中心'}),
    'personnel': create_reverse_map({'P01': '賴柏仁', 'P02': '覃筱蘭', 'P03': '游智程', 'P04': '洪渝勛-01.10', 'P05': '劉志廷-02', 'P06': '徐維陽-04', 'P07': '陳凱霖-05', 'P08': '郭彥麟-07.22', 'P09': '陳力豪-08', 'P10': '劉星緯-09', 'P11': '鄭郁勳-11', 'P12': '楊詠翔-12', 'P13': '謝欣蓉-13', 'P14': '鄧敬豪-14', 'P15': '邱垂政-15', 'P16': '洪哲文-16', 'P17': '嘺俊甫-17', 'P18': '陳正道-18', 'P19': '溫學成-19.06', 'P20': '劉致忻-20.3', 'P21': '古浩成-21', 'P22': '秦志如-23', 'P23': '林柏宏-24', 'P24': '簡雄雄-25', 'P25': '莊守翔-26', 'P26': '馬瑞興-27', 'P27': '呂紹榮-28', 'P28': '黃柏嘉-29', 'P29': '陳冠宇-30', 'P30': '謝煥春-31', 'P31': '胡展維-32', 'P32': '林思維', 'P33': '羅以芯', 'P34': '游琇媛'}),
    'case_type': create_reverse_map({'CT01': '通緝', 'CT02': '毒品危害防制條例', 'CT03': '185-3公共危險(酒)', 'CT04': '185-3公共危險(毒)', 'CT05': '320竊盜', 'CT06': '321加重竊盜', 'CT07': '339詐欺', 'CT08': '失聯移工', 'CT09': '135妨害公務', 'CT10': '149聚眾不解散', 'CT11': '150聚眾鬥毆', 'CT12': '151恐嚇公眾', 'CT13': '169-171誣告', 'CT14': '185-4肇事逃逸', 'CT15': '210-220偽造文書印文罪', 'CT16': '235妨害風化', 'CT17': '266-270賭博罪', 'CT18': '271殺人', 'CT19': '277傷害', 'CT20': '284過失傷害', 'CT21': '302妨害自由(私行拘禁)', 'CT22': '304強制罪', 'CT23': '305恐嚇危安', 'CT24': '306侵入住宅', 'CT25': '309-314妨害名譽及信用罪(公然侮辱、誹謗)', 'CT26': '315-319妨害秘密罪', 'CT27': '319-1到319-6妨害性隱私及不實性影像罪章', 'CT28': '325準強盜', 'CT29': '326搶奪', 'CT30': '328強盜', 'CT31': '330加重強盜', 'CT32': '335侵占', 'CT33': '342背信', 'CT34': '344重利', 'CT35': '346恐嚇取財', 'CT36': '354毀損', 'CT37': '358妨害電腦使用', 'CT38': '★★刑案類找不到法條(暫選)', 'CT39': '汽機車失竊', 'CT40': '汽機車遺失/侵占', 'CT41': '汽機車車牌遺失/侵占', 'CT42': '其他汽機車案類', 'CT43': '社會秩序維護法', 'CT44': '家庭暴力防治法', 'CT45': '個人資料保護法', 'CT46': '跟蹤騷擾防治法', 'CT47': '性騷擾防治法', 'CT48': '菸害防制法', 'CT49': '醫療法', 'CT50': '人口販運防治法', 'CT51': '農田水利法', 'CT52': '廢棄物清理法'})
}

def get_ref_id(val, map_key, table_name, col_name, doc_id):
    """檢查並獲取對照 ID"""
    s_val = str(val).strip() if pd.notna(val) else ""
    if not s_val: return None
    
    if s_val not in MAPS[map_key]:
        print(f"[警告] 找不到對照值! | 表格: {table_name} | 欄位: {col_name} | 數值: '{s_val}' | 文號: {doc_id}")
        return "ERR_MISSING"
    return MAPS[map_key][s_val]

# ---------------------------------------------------------
# 2. 資料庫操作
# ---------------------------------------------------------
def run_import():
    if not os.path.exists(EXCEL_FILE):
        print(f"錯誤: 找不到 {EXCEL_FILE}")
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    try:
        # 行為 1: 清空並重置
        tables = ['Document_Task', 'Document_Criminal', 'Document_General']
        for t in tables:
            cur.execute(f"DELETE FROM {t}")
        cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('Document_Task', 'Document_Criminal', 'Document_General')")
        print("系統: 已清空舊有資料並重置計數器。")

        xls = pd.ExcelFile(EXCEL_FILE)

        # A. Document_Task
        if 'Document_Task' in xls.sheet_names:
            df = pd.read_excel(xls, 'Document_Task')
            for _, r in df.iterrows():
                d_id = r['doc_id']
                s_id = get_ref_id(r['sender_id'], 'personnel', 'Task', 'sender_id', d_id)
                dept = get_ref_id(r['dept_id'], 'dept', 'Task', 'dept_id', d_id)
                a_id = get_ref_id(r['assignee_id'], 'personnel', 'Task', 'assignee_id', d_id)
                
                if "ERR_MISSING" in [s_id, dept, a_id]: continue
                
                cur.execute("""INSERT INTO Document_Task (doc_id, dispatch_date, sender_id, subject, dept_id, receive_date, assignee_id, deadline) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                            (str(d_id), r['dispatch_date'], s_id, r['subject'], dept, r['receive_date'], a_id, r['deadline']))

        # B. Document_Criminal
        if 'Document_Criminal' in xls.sheet_names:
            df = pd.read_excel(xls, 'Document_Criminal')
            for _, r in df.iterrows():
                d_id = r['doc_id']
                s_id = get_ref_id(r['sender_id'], 'personnel', 'Criminal', 'sender_id', d_id)
                c_t  = get_ref_id(r['case_type'], 'case_type', 'Criminal', 'case_type', d_id)
                c_s  = get_ref_id(r['case_status'], 'case_status', 'Criminal', 'case_status', d_id)
                p_id = get_ref_id(r['processor_id'], 'personnel', 'Criminal', 'processor_id', d_id)
                
                if "ERR_MISSING" in [s_id, c_t, c_s, p_id]: continue
                
                cur.execute("""INSERT INTO Document_Criminal (doc_id, report_date, sender_id, case_type, case_status, processor_id, subject_summary, occurrence_date, reporter_name, is_reported, is_electronic) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (str(d_id), r['report_date'], s_id, c_t, c_s, p_id, r['subject_summary'], r['occurrence_date'], r['reporter_name'], r['is_reported'], r['is_electronic']))

        # C. Document_General
        if 'Document_General' in xls.sheet_names:
            df = pd.read_excel(xls, 'Document_General')
            for _, r in df.iterrows():
                d_id = r['doc_id']
                s_id = get_ref_id(r['sender_id'], 'personnel', 'General', 'sender_id', d_id)
                dept = get_ref_id(r['dept_id'], 'dept', 'General', 'dept_id', d_id)
                p_id = get_ref_id(r['processor_id'], 'personnel', 'General', 'processor_id', d_id)
                
                if "ERR_MISSING" in [s_id, dept, p_id]: continue
                
                cur.execute("""INSERT INTO Document_General (doc_id, report_date, sender_id, dept_id, subject, processor_id, is_reported, is_electronic) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (str(d_id), r['report_date'], s_id, dept, r['subject'], p_id, r['is_reported'], r['is_electronic']))

        conn.commit()
        print("系統: 匯入作業完成。")
    except Exception as e:
        print(f"錯誤: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_import()
