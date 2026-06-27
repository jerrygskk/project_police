import sys
import os
import traceback
import logging

# 壓掉 Qt DirectWrite 字型警告（MS Sans Serif 找不到屬正常現象，不影響功能）
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

# ──────────────────────────────────────────────
# 全域錯誤處理：寫入 error.log + Windows 事件檢視器
# ──────────────────────────────────────────────
def _setup_error_handler():
    log_path = os.path.join(
        os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__),
        'error.log'
    )
    logging.basicConfig(
        filename=log_path,
        level=logging.ERROR,
        format='%(asctime)s %(levelname)s\n%(message)s\n' + '-'*60,
        encoding='utf-8',
    )

    def _handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))

        # 1. 寫入 error.log
        logging.error(msg)

        # 2. 寫入 Windows 事件檢視器（僅 Windows 且有 pywin32）
        try:
            import win32evtlog
            import win32evtlogutil
            win32evtlogutil.ReportEvent(
                '公文管理系統',
                1,
                eventType=win32evtlog.EVENTLOG_ERROR_TYPE,
                strings=[msg],
            )
        except Exception:
            pass  # 沒有 pywin32 或非 Windows 時靜默跳過

        # 3. 彈出錯誤視窗（QApplication 存在時）
        try:
            from PySide6.QtWidgets import QApplication
            from lib.db_utils import msgCritical as _msgCritical
            from lib.db_utils import friendlyErrorMessage as _friendly
            if QApplication.instance():
                _msgCritical("系統錯誤", _friendly(exc_type, exc_value))
        except Exception:
            pass

    sys.excepthook = _handle_exception

_setup_error_handler()

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

from lib.theme import APPLE_STYLE
from lib.version import __version__
from lib.db_utils import getResourcePath, loadUi, msgInfo
from lib.auth_manager import AuthManager
from tabs     import TabDispatch, TabReceive, TabReport, TabPrint, TabDBBrowse, TabArchive, TabSettings, TabAudit
from res import resources_rc  # 註冊 Qt resource（arrow.svg）


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
        3: TabPrint,
        4: TabDBBrowse,
        5: TabArchive,
        6: TabSettings,
        7: TabAudit,
    }

    def __init__(self, tab_index=0, prefetch=None, progress=None):
        self.db_path   = getResourcePath("dbfile.db")
        self.window    = loadUi(getResourcePath("layouts/Layout1.ui"))
        if not self.window:
            return

        self.tab_widget = getattr(self.window, 'tabWidget', None)

        self.tabs = {}
        for idx, TabClass in self.TAB_CLASSES.items():
            tab = TabClass(self.tab_widget, self.db_path)
            tab._manager = self          # 供 Tab 取得其他 Tab（如還原後清快取）
            tab.setup(idx)
            self.tabs[idx] = tab

        # 瀏覽頁三表：用啟動預查資料分段建表，逐表更新載入進度條（65~100%）。
        # 建表必須在主執行緒，故放在此處（非背景 worker）；processEvents 讓進度條即時重繪。
        from PySide6.QtWidgets import QApplication
        from lib.loading_screen import BUILD_STEPS
        browse = self.tabs.get(self._IDX_DBBROWSE)
        if browse and hasattr(browse, 'buildInitial'):
            bdata = (prefetch or {}).get('browse', {})
            for key, label, pct in BUILD_STEPS:
                if progress:
                    progress(label, pct)
                    QApplication.processEvents()
                browse.buildInitial(key, rows=bdata.get(key))
            browse.markLoaded()
            if progress:
                progress("完成", 100)
                QApplication.processEvents()

        if self.tab_widget:
            self.tab_widget.setCurrentIndex(tab_index)
            self.tab_widget.currentChanged.connect(self._onTabChanged)
            self._prev_tab_index = tab_index
            # 分頁列右上角 ? 鈕（依當前頁開說明）＋ 各欄位 tooltip
            from ui_utils import attachHelpButton
            attachHelpButton(self.tab_widget, self.window)

        # 標題隨身份切換
        self._base_title = "公文管理系統"
        self._updateTitle(AuthManager.instance().current_role)
        AuthManager.instance().role_changed.connect(self._updateTitle)

        # 閒置 10 分鐘自動登出（僅管理者／歸檔管理）
        self._IDLE_TIMEOUT_MS = 10 * 60 * 1000
        self._idle_timer = QTimer(self.window)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._onIdleTimeout)
        # 閒置 20 分鐘自動關閉整支程式（不分身分，一律計時）
        self._CLOSE_TIMEOUT_MS = 20 * 60 * 1000
        self._close_timer = QTimer(self.window)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._onIdleClose)
        self._close_timer.start(self._CLOSE_TIMEOUT_MS)
        self._installIdleFilter()

    def _updateTitle(self, role):
        suffix = {'admin': '管理者模式', 'archive': '歸檔管理'}.get(role, '一般使用者')
        self.window.setWindowTitle(f"{self._base_title}  [{suffix}]  - v{__version__}")
        # 登入時啟動計時，登出時停掉（管理者與歸檔管理皆計時）
        if hasattr(self, '_idle_timer'):
            if role in ('admin', 'archive'):
                self._idle_timer.start(self._IDLE_TIMEOUT_MS)
            else:
                self._idle_timer.stop()

    def _installIdleFilter(self):
        """安裝全域事件過濾器，監聽使用者操作以重設閒置計時。"""
        from PySide6.QtCore import QObject, QEvent

        mgr = self
        class _IdleFilter(QObject):
            def eventFilter(self, obj, ev):
                t = ev.type()
                if t in (QEvent.MouseButtonPress, QEvent.MouseMove,
                         QEvent.KeyPress, QEvent.Wheel):
                    # 任何操作都重設「自動關閉」計時（不分身分）
                    mgr._close_timer.start(mgr._CLOSE_TIMEOUT_MS)
                    # 「自動登出」計時僅管理者／歸檔管理
                    if AuthManager.instance().is_manager():
                        mgr._idle_timer.start(mgr._IDLE_TIMEOUT_MS)
                return False

        self._idle_filter = _IdleFilter()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self._idle_filter)

    def _onIdleTimeout(self):
        if AuthManager.instance().is_manager():
            AuthManager.instance().logout()
            msgInfo("自動登出", "閒置已超過 10 分鐘，已自動登出，請重新登入。", self.window)

    def _onIdleClose(self):
        # 閒置 20 分鐘自動關閉整支程式（靜默，僅 error.log 留痕）。
        logging.error("閒置已超過 20 分鐘，自動關閉程式。")
        QApplication.instance().quit()

    _IDX_SETTINGS = 6          # 資料庫設定 Tab index
    _IDX_DBBROWSE = 4          # 資料庫瀏覽 Tab index

    def _onTabChanged(self, index):
        from ui_utils import autoResizeTable
        tab_obj = self.tabs.get(index)
        if not tab_obj:
            self._prev_tab_index = index
            return

        # 從設定 Tab 切出來：先處理未儲存的排序變更（D3c）
        settings_tab = self.tabs.get(self._IDX_SETTINGS)
        if (self._prev_tab_index == self._IDX_SETTINGS
                and settings_tab
                and hasattr(settings_tab, '_promptUnsaved')):
            settings_tab._promptUnsaved(context="leave")

        # 只有「從設定 Tab 切出來 且 有實際改過資料」才刷新參照表
        # 一次刷新所有 Tab，避免之後切其他 Tab 時 dirty 已被清掉
        if (self._prev_tab_index == self._IDX_SETTINGS
                and settings_tab
                and getattr(settings_tab, '_ref_dirty', False)):
            for idx, t in self.tabs.items():
                if idx != self._IDX_SETTINGS:
                    # 通知瀏覽/歸檔頁：參照表改過 → on_activated 內就地輕量刷 ref 欄
                    setattr(t, "_ref_changed", True)
                    t.on_activated()
            settings_tab._ref_dirty = False

        # 切「到」設定 Tab：重載當前子頁（放棄未存排序、與 DB 同步）
        if (index == self._IDX_SETTINGS
                and settings_tab
                and hasattr(settings_tab, 'on_activated')):
            settings_tab.on_activated()

        # 切「到」資料庫瀏覽 Tab：比對資料指紋，只在其他頁改過資料時重載。
        # （on_activated 內部會逐表比對 last_modified，未變則不重建、不頓。）
        if (index == self._IDX_DBBROWSE
                and tab_obj
                and hasattr(tab_obj, 'on_activated')):
            tab_obj.on_activated()

        self._prev_tab_index = index

        def _resize():
            for t in tab_obj.get_tables():
                if t and t.columnCount() > 0:
                    autoResizeTable(t)

        def _setFocus():
            w = tab_obj.get_focus_widget()
            if w:
                w.setFocus()

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
        'btn_dbbrowse':           4,
        'btn_archive':            5,
        'btn_settings':           6,
        'btn_audit':              7,
    }

    # 各功能磚格圖示（qrc 別名 :/menu/，於程式內套用以免 QUiLoader 解析 resource 問題）
    ICON_MAP = {
        'btn_report_assignment':  ':/menu/dispatch.svg',
        'btn_receive_assignment': ':/menu/receive.svg',
        'btn_report_case':        ':/menu/report.svg',
        'btn_generate_receipt':   ':/menu/print.svg',
        'btn_dbbrowse':           ':/menu/browse.svg',
        'btn_archive':            ':/menu/archive.svg',
        'btn_settings':           ':/menu/settings.svg',
        'btn_audit':              ':/menu/audit.svg',
    }

    def __init__(self):
        from PySide6.QtGui import QIcon
        from PySide6.QtCore import QSize

        self.ui = loadUi(getResourcePath("layouts/main_menu.ui"))
        if not self.ui:
            sys.exit(1)

        self.selected_tab = -1

        # 版本號顯示（單一來源 lib/version.py）
        version_label = getattr(self.ui, 'versionLabel', None)
        if version_label:
            version_label.setText(f"Ver: {__version__}")

        for btn_name, idx in self.BTN_MAP.items():
            btn = getattr(self.ui, btn_name, None)
            if btn:
                icon_path = self.ICON_MAP.get(btn_name)
                if icon_path:
                    btn.setIcon(QIcon(icon_path))
                    btn.setIconSize(QSize(30, 30))
                btn.clicked.connect(lambda checked=False, i=idx: self._onSelect(i))

        btn_exit = getattr(self.ui, 'btn_exit', None)
        if btn_exit:
            btn_exit.clicked.connect(self.ui.reject)

    def _onSelect(self, index):
        if index not in DocumentManager.TAB_CLASSES:
            msgInfo("提示", "此功能尚未開放，敬請期待")
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
    icon_path = getResourcePath("res/buttons/police_badge.svg")
    app.setWindowIcon(QIcon(icon_path))

    db_path = getResourcePath("dbfile.db")

    # ── APP 層軟性互斥：開啟時偵測是否已有人在用（純勸導，不擋 DB）──
    from datetime import datetime as _dt
    from lib import app_lock as _lock
    from lib.db_utils import confirmBox as _confirmBox
    _lock_path = _lock.lock_file_path(db_path)
    _machine, _user, _pid = _lock.current_identity()
    _opened_iso = _dt.now().isoformat(timespec="seconds")

    _existing = _lock.read_lock(_lock_path)
    if _existing and not _lock.is_stale(
            _existing.get("heartbeat", ""), _dt.now().isoformat(timespec="seconds")):
        _who = _existing.get("user") or "其他使用者"
        _mc = _existing.get("machine") or "其他電腦"
        _since = (_existing.get("opened") or "").replace("T", " ")[:16]
        if not _confirmBox(
                "系統使用中",
                f"{_who}（電腦 {_mc}）自 {_since} 起正在使用本系統。",
                confirm_text="仍要開啟", cancel_text="取消離開",
                confirm_danger=True, default_confirm=False,
                informative="多人同時編輯可能造成資料毀損，建議稍後再開。\n"
                            "開啟後若閒置超過 20 分鐘，程式將自動關閉。"):
            sys.exit(0)

    # 寫入自己的鎖檔並啟動心跳；正常結束時清掉（含閒置自動關）。
    _lock.write_lock(_lock_path, _machine, _user, _opened_iso,
                     _dt.now().isoformat(timespec="seconds"), _pid)

    # ── 冪等確保附加式結構（建表／加欄，只增不改；失敗不擋開程式）──
    from lib import db_schema as _schema
    _schema.ensureSchema(db_path)

    # ── 平時自動備份：每日覆蓋＋每週另存（本機輪替，純靜默）──
    from lib import db_backup as _backup
    _backup.run_auto_backup(db_path)

    def _heartbeat():
        _lock.write_lock(_lock_path, _machine, _user, _opened_iso,
                         _dt.now().isoformat(timespec="seconds"), _pid)

    _hb_timer = QTimer()
    _hb_timer.timeout.connect(_heartbeat)
    _hb_timer.start(_lock.HEARTBEAT_MS)

    # 清鎖檔：aboutToQuit 蓋正常關窗/自動關閉；atexit 補蓋 sys.exit（主選單離開、
    # 建表失敗）等不經 Qt quit 的路徑。當機/斷電兩者皆蓋不到，靠心跳失效自癒。
    def _cleanup_lock():
        _lock.remove_lock(_lock_path, machine=_machine, pid=_pid)
    app.aboutToQuit.connect(_cleanup_lock)
    import atexit
    atexit.register(_cleanup_lock)

    from lib.loading_screen import LoadingScreen

    # _refs 持有 menu / loading / mgr 引用，防止被 GC 回收導致閃退
    _refs = []

    def _on_data_ready(results):
        # 進度條期間就把整個主視窗建好（含三表建表）；建完才出主選單，選完秒進。
        mgr = DocumentManager(tab_index=0, prefetch=results, progress=loading.setStep)
        _refs.append(mgr)
        loading.finishAndClose()
        if not (hasattr(mgr, 'window') and mgr.window):
            sys.exit(1)
        mgr.window.setWindowIcon(QIcon(icon_path))

        # 一切就緒後才顯示主選單，使用者選功能後直接切到該頁
        menu = MainMenu()
        _refs.append(menu)
        # 打包版偶爾因 Windows 前景鎖，主選單被壓到別的視窗後面：
        # exec() 進事件迴圈、dialog 顯示後立刻清最小化狀態並搶到最前。
        def _bringMenuFront():
            w = menu.ui
            w.setWindowState((w.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
            w.raise_()
            w.activateWindow()
        QTimer.singleShot(0, _bringMenuFront)
        if menu.ui.exec() != QDialog.Accepted or menu.selected_tab < 0:
            sys.exit(0)
        mgr.tab_widget.blockSignals(True)
        mgr.tab_widget.setCurrentIndex(menu.selected_tab)
        mgr.tab_widget.blockSignals(False)
        mgr.window.show()
        QTimer.singleShot(50, lambda: mgr._onTabChanged(menu.selected_tab))

    loading = LoadingScreen(db_path)
    _refs.append(loading)
    loading.dataReady.connect(_on_data_ready)
    loading.show()

    sys.exit(app.exec())
