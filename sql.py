import sqlite3

def analyze_database(dbPath):
    # 變數命名符合 camelCase
    connection = sqlite3.connect(dbPath)
    cursor = connection.cursor()
    
    try:
        # 1. 取得所有資料表名稱
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"🔍 資料庫檔案: {dbPath}")
        print("-" * 30)
        
        for table in tables:
            tableName = table[0]
            print(f"資料表名稱: {tableName}")
            
            # 2. 取得該表的詳細欄位資訊
            cursor.execute(f"PRAGMA table_info({tableName});")
            columns = cursor.fetchall()
            
            print(f"{'ID':<3} | {'欄位名稱':<15} | {'型態':<10} | {'主鍵':<5}")
            print("-" * 35)
            for col in columns:
                # col[0]=ID, col[1]=Name, col[2]=Type, col[5]=PK
                print(f"{col[0]:<3} | {col[1]:<15} | {col[2]:<10} | {col[5]:<5}")
            print("\n")
            
    except sqlite3.Error as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        connection.close()

# 導入方式：確保 dbfile.db 與此程式碼在同一資料夾
if __name__ == "__main__":
    analyze_database("dbfile.db")