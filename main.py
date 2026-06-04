import sys
import os

# 壓掉 Qt DirectWrite 字型警告（MS Sans Serif 找不到屬正常現象，不影響功能）
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

from theme    import APPLE_STYLE
from db_utils import getResourcePath, loadUi
from tabs     import TabDispatch, TabReceive, TabReport
import resources_rc  # 註冊 Qt resource（arrow.svg）


# ──────────────────────────────────────────────
# DocumentManager：視窗容器，管理所有 Tab
# ──────────────────────────────────────────────
class DocumentManager:
    """
    新增 Tab 只需：
      1. 在 tabs/ 新增 tab_xxx.py 並實作 BaseTab
      2. 在 tabs/__init__.py 加入 import
      3. 在 TAB_CLASSES 登記 {index: TabClass}
    """
    TAB_CLASSES = {
        0: TabDispatch,
        1: TabReceive,
        2: TabReport,
        # 3: TabPrint,
    }

    def __init__(self, tab_index=0):
        self.db_path   = getResourcePath("dbfile.db")
        self.window    = loadUi(getResourcePath("Layout1.ui"))
        if not self.window:
            return

        self.tab_widget = getattr(self.window, 'tabWidget', None)

        self.tabs = {}
        for idx, TabClass in self.TAB_CLASSES.items():
            tab = TabClass(self.tab_widget, self.db_path)
            tab.setup(idx)
            self.tabs[idx] = tab

        if self.tab_widget:
            self.tab_widget.setCurrentIndex(tab_index)
            self.tab_widget.currentChanged.connect(self._onTabChanged)

    def _onTabChanged(self, index):
        from ui_utils import autoResizeTable
        tab_obj = self.tabs.get(index)
        if not tab_obj:
            return

        def _resize():
            for attr in ['table', 'recv_table', 'crim_table', 'gen_table']:
                t = getattr(tab_obj, attr, None)
                if t and t.columnCount() > 0:
                    autoResizeTable(t)

        def _setFocus():
            if hasattr(tab_obj, 'lineEdit') and tab_obj.lineEdit:
                tab_obj.lineEdit.setFocus()
            elif hasattr(tab_obj, 'recv_subject') and tab_obj.recv_subject:
                tab_obj.recv_subject.setFocus()
            elif hasattr(tab_obj, 'crim_subject') and tab_obj.crim_subject:
                tab_obj.crim_subject.setFocus()

        QTimer.singleShot(150, _resize)
        QTimer.singleShot(50, _setFocus)


# ──────────────────────────────────────────────
# MainMenu：主選單
# ──────────────────────────────────────────────
class MainMenu:
    BTN_MAP = {
        'btn_report_assignment':  0,
        'btn_receive_assignment': 1,
        'btn_report_case':        2,
        'btn_generate_receipt':   3,
    }

    def __init__(self):
        self.ui = loadUi(getResourcePath("main_menu.ui"))
        if not self.ui:
            sys.exit(1)

        self.selected_tab = -1

        for btn_name, idx in self.BTN_MAP.items():
            btn = getattr(self.ui, btn_name, None)
            if btn:
                btn.clicked.connect(lambda checked=False, i=idx: self._onSelect(i))

        btn_exit = getattr(self.ui, 'btn_exit', None)
        if btn_exit:
            btn_exit.clicked.connect(self.ui.reject)

    def _onSelect(self, index):
        if index not in DocumentManager.TAB_CLASSES:
            QMessageBox.information(self.ui, "提示", "此功能尚未開放，敬請期待")
            return
        self.selected_tab = index
        self.ui.accept()


# ──────────────────────────────────────────────
# 進入點
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft JhengHei", 14))
    app.setStyleSheet(APPLE_STYLE)

    from PySide6.QtGui import QIcon
    icon_path = getResourcePath("police_badge.svg")
    app.setWindowIcon(QIcon(icon_path))

    db_path = getResourcePath("dbfile.db")

    # ── Loading 畫面 ──────────────────────────────
    from loading_screen import LoadingScreen

    _menu_ref  = []   # 用 list 讓 closure 能持有參照

    def _on_loading_done(results):
        """Loading 完成後顯示主選單"""
        menu = MainMenu()
        _menu_ref.append(menu)
        if menu.ui.exec() != QDialog.Accepted or menu.selected_tab < 0:
            sys.exit(0)

        mgr = DocumentManager(tab_index=menu.selected_tab)
        if hasattr(mgr, 'window') and mgr.window:
            mgr.window.setWindowIcon(QIcon(icon_path))
            mgr.window.show()
            QTimer.singleShot(50, lambda: mgr._onTabChanged(menu.selected_tab))

    loading = LoadingScreen(db_path)
    loading.done.connect(_on_loading_done)
    loading.show()

    sys.exit(app.exec())
