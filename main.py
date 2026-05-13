import sys
import os
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTableWidgetItem
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile

def getResourcePath(relative_path):
    """處理資源文件的絕對路徑"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class DocumentManager:
    """執行頁面邏輯控管"""
    def __init__(self, tabIndex=0):
        self.uiPath = getResourcePath("Layout1.ui")
        self.dbPath = getResourcePath("dbfile.db")
        
        loader = QUiLoader()
        uiFile = QFile(self.uiPath)
        uiFile.open(QFile.ReadOnly)
        self.window = loader.load(uiFile)
        uiFile.close()

        if hasattr(self.window, 'tabWidget'):
            self.window.tabWidget.setCurrentIndex(tabIndex)

        self.bindEvents()

    def bindEvents(self):
        """綁定 UI 元件事件"""
        if hasattr(self.window, 'lineEdit_docNum'):
            self.window.lineEdit_docNum.returnPressed.connect(self.handleQuery)
            self.window.lineEdit_docNum.setFocus()
        
        if hasattr(self.window, 'btn_send'):
            self.window.btn_send.clicked.connect(self.handleDispatch)

    def handleQuery(self):
        """核心查詢邏輯：確保欄位別名與資料庫 View 完全對齊"""
        serialNo = self.window.lineEdit_docNum.text().strip()
        if not serialNo: return

        currentTab = self.window.tabWidget.currentIndex()
        
        # 查詢映射表 (確保包含發文日期欄位以利邏輯計算)
        queries = {
            0: ("View_Task_Assignment", "序號", ["序號", "交辦事由", "業務組", "承辦人", "限辦日期", "發文日期"]),
            1: ("View_Criminal_Report", "編號", ["編號", "案類", "分類", "受理承辦人", "受理日期", "陳報日期"]),
            2: ("View_General_Report", "編號", ["編號", "主旨", "業務單位", "陳報人", "陳報日期", "發文日期"])
        }

        viewName, keyName, columns = queries.get(currentTab, queries[0])
        colString = ", ".join([f'"{c}"' for c in columns]) 

        try:
            conn = sqlite3.connect(self.dbPath)
            cursor = conn.cursor()
            sql = f"SELECT {colString} FROM {viewName} WHERE \"{keyName}\" = ?"
            cursor.execute(sql, (serialNo,))
            row = cursor.fetchone()
            conn.close()

            if row:
                self.insertToTable(row)
                self.window.lineEdit_docNum.clear()
                self.window.lineEdit_docNum.setFocus()
            else:
                QMessageBox.warning(self.window, "查詢結果", f"找不到資料：{serialNo}")
        except Exception as e:
            QMessageBox.critical(self.window, "SQL 錯誤", f"查詢失敗: {str(e)}")

    def calculateOverdue(self, deadlineStr, dispatchStr):
        """
        核心逾期邏輯判斷
        1. 已發文且準時 -> 已發文
        2. 已發文且逾期 -> 已發文，逾期 N 日
        3. 未發文且準時 -> 剩餘 N 日
        4. 未發文且逾期 -> 逾期 N 日
        """
        if not deadlineStr or str(deadlineStr) == "None" or deadlineStr == "":
            return "未設定"

        try:
            today = datetime.now().date()
            deadlineDate = datetime.strptime(str(deadlineStr), "%Y-%m-%d").date()
            
            # 判斷是否已發文
            hasDispatched = dispatchStr and str(dispatchStr) != "None" and dispatchStr != ""
            
            if hasDispatched:
                dispatchDate = datetime.strptime(str(dispatchStr), "%Y-%m-%d").date()
                diff = (dispatchDate - deadlineDate).days
                if diff <= 0:
                    return "已發文"
                else:
                    return f"已發文，逾期 {diff} 日"
            else:
                diff = (deadlineDate - today).days
                if diff >= 0:
                    return f"剩餘 {diff} 日"
                else:
                    return f"逾期 {-diff} 日"
        except:
            return "格式錯誤"

    def insertToTable(self, data):
        """將資料填充至 QTableWidget"""
        table = self.window.tableWidget
        rowPos = table.rowCount()
        table.insertRow(rowPos)
        
        # 填入基礎資料 (序號, 事由, 業務組, 承辦人)
        for i in range(4):
            table.setItem(rowPos, i, QTableWidgetItem(str(data[i])))
        
        # 填入日期 (根據 View 順序：data[5] 是發文日期，data[4] 是限辦日期)
        table.setItem(rowPos, 4, QTableWidgetItem(str(data[5]) if data[5] and str(data[5]) != "None" else "")) # 收文/發文日期
        table.setItem(rowPos, 5, QTableWidgetItem(str(data[4]))) # 限辦日期

        # 逾期判斷邏輯
        if self.window.tabWidget.currentIndex() == 0:
            status = self.calculateOverdue(data[4], data[5])
            table.setItem(rowPos, 6, QTableWidgetItem(status))

    def handleDispatch(self):
        """批次更新發文日期"""
        table = self.window.tableWidget
        if table.rowCount() == 0: return

        if QMessageBox.question(self.window, "確認", "確定要執行批次發文處理？") == QMessageBox.Yes:
            try:
                conn = sqlite3.connect(self.dbPath)
                cursor = conn.cursor()
                tab = self.window.tabWidget.currentIndex()
                
                targetTable = ["Task_Assignment", "Document_Criminal", "Document_General"][tab]
                keyField = ["serial_no", "dispatch_id", "dispatch_id"][tab]

                for i in range(table.rowCount()):
                    sn = table.item(i, 0).text()
                    cursor.execute(f"UPDATE {targetTable} SET dispatch_date = date('now') WHERE {keyField} = ?", (sn,))
                
                conn.commit()
                conn.close()
                QMessageBox.information(self.window, "完成", "發文日期已更新")
                table.setRowCount(0)
            except Exception as e:
                QMessageBox.critical(self.window, "錯誤", str(e))

class MainMenu:
    """主導覽選單"""
    def __init__(self):
        loader = QUiLoader()
        file = QFile(getResourcePath("公文輸入系統.ui"))
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file)
        file.close()
        
        self.selectedTab = 0
        self.ui.btn_report_assignment.clicked.connect(lambda: self.on_select(0))
        self.ui.btn_receive_assignment.clicked.connect(lambda: self.on_select(1))
        if hasattr(self.ui, 'btn_exit'):
            self.ui.btn_exit.clicked.connect(sys.exit)

    def on_select(self, index):
        self.selectedTab = index
        self.ui.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    menu = MainMenu()
    if menu.ui.exec() == QDialog.Accepted:
        mgr = DocumentManager(tabIndex=menu.selectedTab)
        mgr.window.show()
        sys.exit(app.exec())