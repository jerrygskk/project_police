import sys
import os
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTableWidgetItem
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile

def getResourcePath(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class DocumentManager:
    def __init__(self, tabIndex=0):
        self.uiPath = getResourcePath("Layout1.ui")
        self.dbPath = getResourcePath("dbfile.db")
        
        loader = QUiLoader()
        uiFile = QFile(self.uiPath)
        if not uiFile.exists():
            print(f"錯誤: 找不到 {self.uiPath}")
            return
        uiFile.open(QFile.ReadOnly)
        self.window = loader.load(uiFile)
        uiFile.close()

        # 防呆處理：檢查 tabWidget 是否存在
        self.tab = getattr(self.window, 'tabWidget', None)
        if self.tab:
            self.tab.setCurrentIndex(tabIndex)

        self.bindEvents()

    def bindEvents(self):
        # 使用 safe_connect 防止因為 UI 命名錯誤導致當機
        self.safe_connect('lineEdit_docNum', 'returnPressed', self.handleQuery)
        self.safe_connect('btn_send', 'clicked', self.handleDispatch)
        
        # 讓輸入框自動聚焦
        input_box = getattr(self.window, 'lineEdit_docNum', None)
        if input_box: input_box.setFocus()

    def safe_connect(self, widget_name, signal_name, slot_func):
        """安全連接信號，若找不到元件則印出警告而不崩潰"""
        widget = getattr(self.window, widget_name, None)
        if widget:
            getattr(widget, signal_name).connect(slot_func)
        else:
            print(f"警告: 在 Layout1.ui 中找不到元件 '{widget_name}'")

    def calculateOverdueStatus(self, deadlineStr, dispatchStr):
        if not deadlineStr or str(deadlineStr) == "None" or deadlineStr == "":
            return "未設定"
        try:
            today = datetime.now().date()
            deadlineDate = datetime.strptime(str(deadlineStr), "%Y-%m-%d").date()
            hasDispatched = dispatchStr and str(dispatchStr) != "None" and dispatchStr != ""
            
            if hasDispatched:
                dispatchDate = datetime.strptime(str(dispatchStr), "%Y-%m-%d").date()
                diff = (dispatchDate - deadlineDate).days
                return "已發文" if diff <= 0 else f"已發文，逾期 {diff} 日"
            else:
                diff = (deadlineDate - today).days
                return f"剩餘 {diff} 日" if diff >= 0 else f"逾期 {-diff} 日"
        except:
            return "格式錯誤"

    def handleQuery(self):
        # 這裡就是你原本運作正常的邏輯，加上新的逾期判斷
        input_box = getattr(self.window, 'lineEdit_docNum', None)
        if not input_box: return
        serialNo = input_box.text().strip()
        if not serialNo: return

        currentTab = self.tab.currentIndex() if self.tab else 0
        
        # 根據你提供的資料庫架構對齊
        queries = {
            0: ("View_Task_Assignment", "序號", ["序號", "交辦事由", "業務組", "承辦人", "限辦日期", "發文日期"]),
            1: ("View_Criminal_Report", "編號", ["編號", "案類", "分類", "受理承辦人", "受理日期", "發文日期"]),
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
                input_box.clear()
            else:
                QMessageBox.warning(self.window, "查詢", f"找不到資料：{serialNo}")
        except Exception as e:
            QMessageBox.critical(self.window, "SQL錯誤", f"請檢查資料庫: {str(e)}")

    def insertToTable(self, data):
        table = getattr(self.window, 'tableWidget', None)
        if not table: return
        rowPos = table.rowCount()
        table.insertRow(rowPos)
        
        for i in range(4): # 填入前四欄
            table.setItem(rowPos, i, QTableWidgetItem(str(data[i])))
        
        # 發文日期與限辦日期
        dispDate = str(data[5]) if data[5] and str(data[5]) != "None" else ""
        table.setItem(rowPos, 4, QTableWidgetItem(dispDate))
        table.setItem(rowPos, 5, QTableWidgetItem(str(data[4])))
        
        # 狀態欄
        status = self.calculateOverdueStatus(data[4], data[5])
        table.setItem(rowPos, 6, QTableWidgetItem(status))

    def handleDispatch(self):
        # 這裡維持你的批次更新邏輯
        pass

class MainMenu:
    def __init__(self):
        loader = QUiLoader()
        ui_file_path = getResourcePath("公文輸入系統.ui")
        file = QFile(ui_file_path)
        if not file.exists():
            QMessageBox.critical(None, "錯誤", f"找不到 UI 檔案: {ui_file_path}")
            sys.exit(1)
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file)
        file.close()
        
        self.selectedTab = 0
        # 如果你的按鈕名稱不是這兩個，請修改這裡
        if hasattr(self.ui, 'btn_report_assignment'):
            self.ui.btn_report_assignment.clicked.connect(lambda: self.on_select(0))
        if hasattr(self.ui, 'btn_receive_assignment'):
            self.ui.btn_receive_assignment.clicked.connect(lambda: self.on_select(1))

    def on_select(self, index):
        self.selectedTab = index
        self.ui.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    menu = MainMenu()
    if menu.ui.exec() == QDialog.Accepted:
        mgr = DocumentManager(tabIndex=menu.selectedTab)
        if hasattr(mgr, 'window'):
            mgr.window.show()
            sys.exit(app.exec())