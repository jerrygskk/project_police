import sys
import os

from PySide6.QtWidgets import QWidget, QLabel, QProgressBar, QVBoxLayout
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap

from lib.db_utils import getResourcePath


# ── 載入步驟定義（說明, 完成後的 %）──────────────────────────
LOAD_STEPS = [
    ("偵測暫存區就緒...",           15),
    ("載入資源檔...",               20),
    ("套用介面樣式...",             25),
    ("載入主選單介面...",           32),
    ("連線資料庫...",               40),
    ("載入人員對照表...",           47),
    ("載入部門與案類資料...",       54),
    ("初始化交辦單發文...",         65),
    ("初始化交辦單收文...",         75),
    ("載入案件陳報介面...",         85),
    ("初始化案件陳報選單...",       95),
    ("完成",                       100),
]


class LoadWorker(QThread):
    """
    在背景執行緒依序執行載入步驟。
    每個步驟完成後發出 step_done(desc, percent) 信號。
    全部完成後發出 finished(results) 信號，results 包含載入好的物件。
    """
    step_done = Signal(str, int)   # (步驟說明, %)
    finished  = Signal(object)     # 載入完成，回傳結果 dict

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        import time
        # ⚠️ DEBUG 用：每個步驟至少停 2 秒，方便觀察進度條
        # 正式上線前把 DEBUG_DELAY 改為 0
        DEBUG_DELAY = 0.05

        results = {}

        # 步驟 1：偵測 _MEIPASS 暫存區就緒
        if getattr(sys, 'frozen', False):
            _ = os.path.exists(sys._MEIPASS)
        self.step_done.emit(*LOAD_STEPS[0])
        time.sleep(DEBUG_DELAY)

        # 步驟 2：載入 Qt Resource
        from res import resources_rc  # noqa
        self.step_done.emit(*LOAD_STEPS[1])
        time.sleep(DEBUG_DELAY)

        # 步驟 3：套用樣式（回主執行緒才能真正套，這裡先 import）
        from lib.theme import APPLE_STYLE
        results['style'] = APPLE_STYLE
        self.step_done.emit(*LOAD_STEPS[2])
        time.sleep(DEBUG_DELAY)

        # 步驟 4：載入主選單 UI
        results['menu_ui_path'] = getResourcePath("layouts/main_menu.ui")
        self.step_done.emit(*LOAD_STEPS[3])
        time.sleep(DEBUG_DELAY)

        # 步驟 5：連線 DB
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        self.step_done.emit(*LOAD_STEPS[4])
        time.sleep(DEBUG_DELAY)

        # 步驟 6：載入人員對照表
        results['personnel'] = conn.execute(
            "SELECT staff_id, staff_name FROM Ref_Personnel "
            "WHERE is_active=1 ORDER BY staff_id"
        ).fetchall()
        self.step_done.emit(*LOAD_STEPS[5])
        time.sleep(DEBUG_DELAY)

        # 步驟 7：載入部門、案類
        results['depts'] = conn.execute(
            "SELECT dept_id, dept_name FROM Ref_Departments ORDER BY dept_id"
        ).fetchall()
        results['case_types'] = conn.execute(
            "SELECT case_type_id, case_type_name FROM Ref_CaseTypes ORDER BY case_type_id"
        ).fetchall()
        conn.close()
        self.step_done.emit(*LOAD_STEPS[6])
        time.sleep(DEBUG_DELAY)

        # 步驟 8：載入 Layout1.ui
        results['layout1_path'] = getResourcePath("layouts/Layout1.ui")
        self.step_done.emit(*LOAD_STEPS[7])
        time.sleep(DEBUG_DELAY)

        # 步驟 9：載入 Layout2.ui
        results['layout2_path'] = getResourcePath("layouts/Layout2.ui")
        self.step_done.emit(*LOAD_STEPS[8])
        time.sleep(DEBUG_DELAY)

        # 步驟 10：載入 Layout3.ui
        results['layout3_path'] = getResourcePath("layouts/Layout3.ui")
        self.step_done.emit(*LOAD_STEPS[9])
        time.sleep(DEBUG_DELAY)

        # 步驟 11：預熱 Tab 類別 import
        from tabs import TabDispatch, TabReceive, TabReport  # noqa
        results['tabs'] = (TabDispatch, TabReceive, TabReport)
        self.step_done.emit(*LOAD_STEPS[10])
        time.sleep(DEBUG_DELAY)

        # 步驟 12：完成
        self.step_done.emit(*LOAD_STEPS[11])
        self.finished.emit(results)


class LoadingScreen(QWidget):
    """
    Loading 橫幅視窗。
    - 置中於螢幕
    - 上方橫幅圖片（等比例縮放至寬 700px）
    - 下方進度區 40px：說明文字、百分比、進度條
    - 載入完成後自動關閉並發出 done 信號
    """
    done = Signal(object)

    WIN_W = 700
    WIN_H = 319   # 圖片等比例高度 279 + 進度區 40

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self._setup_ui()
        self._start_worker()

    def _setup_ui(self):
        from PySide6.QtWidgets import QHBoxLayout, QApplication

        self.setFixedSize(self.WIN_W, self.WIN_H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 橫幅圖片 ──────────────────────────────────────
        self.banner_label = QLabel()
        self.banner_label.setFixedSize(self.WIN_W, 279)
        self.banner_label.setAlignment(Qt.AlignCenter)
        self.banner_label.setStyleSheet("background-color: #dde7f7;")

        banner_path = getResourcePath("res/banner.png")
        if os.path.exists(banner_path):
            pix = QPixmap(banner_path).scaled(
                self.WIN_W, 279,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            self.banner_label.setPixmap(pix)
        else:
            self.banner_label.setText("公文收發管理系統")
            self.banner_label.setStyleSheet(
                "background-color: #5b8db8; color: white; font-size: 22pt; font-weight: 700;"
            )
        layout.addWidget(self.banner_label)

        # ── 進度區 ────────────────────────────────────────
        progress_widget = QWidget()
        progress_widget.setFixedHeight(40)
        progress_widget.setStyleSheet("background-color: #dde7f7;")
        p_layout = QVBoxLayout(progress_widget)
        p_layout.setContentsMargins(20, 5, 20, 5)
        p_layout.setSpacing(2)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("啟動中...")
        self.status_label.setStyleSheet("color: #4a6fa5; font-size: 10pt;")

        self.pct_label = QLabel("2%")
        self.pct_label.setStyleSheet("color: #4a6fa5; font-size: 10pt; font-weight: 600;")
        self.pct_label.setAlignment(Qt.AlignRight)

        row_layout.addWidget(self.status_label)
        row_layout.addWidget(self.pct_label)
        p_layout.addWidget(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #c5d5ea;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #4a6fa5;
                border-radius: 3px;
            }
        """)
        p_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_widget)

        # ── 置中螢幕 ──────────────────────────────────────
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.WIN_W) // 2,
            (screen.height() - self.WIN_H) // 2,
        )

    def _start_worker(self):
        self.worker = LoadWorker(self.db_path)
        self.worker.step_done.connect(self._on_step)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_step(self, desc, percent):
        self.progress_bar.setValue(percent)
        self.status_label.setText(desc)
        self.pct_label.setText(f"{percent}%")

    def _on_finished(self, results):
        self.close()
        self.done.emit(results)
