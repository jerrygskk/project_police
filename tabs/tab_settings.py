"""
tab_settings.py — 資料庫設定 Tab

流程：
  1. 進入 Tab → 顯示密碼驗證畫面（QStackedWidget index 0）
  2. 輸入正確密碼 → 切換到設定主畫面（index 1）
  3. 離開 Tab → 自動 logout，切回密碼驗證畫面
"""
import os
import sys
import shutil
import subprocess
from datetime import datetime

from PySide6.QtCore    import Qt, QProcess, QObject, QEvent
from PySide6.QtGui     import QColor
from PySide6.QtWidgets import (
    QVBoxLayout, QStackedWidget,
    QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QApplication, QFileDialog,
)

from lib.base_tab import BaseTab
from lib.auth_manager import AuthManager
from lib.db_utils import (
    msgInfo, msgWarning, msgCritical, confirmBox,
    BTN_CONFIRM, BTN_CANCEL,
    loadUi, getResourcePath,
    performYearEndReset, getSetting, ARCHIVE_ROOT_KEY,
)
from ui_utils import (
    PersonnelAddDialog, PersonnelEditDialog,
    DeptAddDialog, DeptEditDialog,
    CaseTypeAddDialog, CaseTypeEditDialog,
    ChangePasswordDialog, ResetDialog, ArchiveRootDialog,
)

# ── 左側導航按鈕樣式 ────────────────────────────────────────────
_NAV_ACTIVE = (
    "QPushButton { background-color: #8fa8c8; color: #ffffff; "
    "border: none; border-radius: 8px; padding: 10px 14px; "
    "font-weight: 600; font-size: 14pt; text-align: left; }"
)
_NAV_INACTIVE = (
    "QPushButton { background-color: transparent; color: #1c1c1e; "
    "border: none; border-radius: 8px; padding: 10px 14px; "
    "font-weight: 500; font-size: 14pt; text-align: left; }"
    "QPushButton:hover { background-color: #e5e5ea; }"
)
_NAV_BOTTOM = (
    "QPushButton { background-color: transparent; color: #636366; "
    "border: none; border-radius: 8px; padding: 10px 14px; "
    "font-weight: 500; font-size: 14pt; text-align: left; }"
    "QPushButton:hover { background-color: #e5e5ea; }"
)
_NAV_DANGER = (
    "QPushButton { background-color: transparent; color: #c0392b; "
    "border: none; border-radius: 8px; padding: 10px 14px; "
    "font-weight: 500; font-size: 14pt; text-align: left; }"
    "QPushButton:hover { background-color: #f8e4e1; }"
)

class _RowDragFilter(QObject):
    """攔截 QTableWidget viewport 的 Drop 事件，實作整列拖拉（Qt InternalMove 只移格，不移列）。"""
    def __init__(self, tbl, callback):
        super().__init__(tbl)
        self._tbl = tbl
        self._cb  = callback  # callback(src_row, dst_row)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Drop:
            src = self._tbl.currentRow()
            dst = self._tbl.rowAt(int(event.position().y()))
            if dst < 0:
                dst = self._tbl.rowCount() - 1
            if src >= 0 and src != dst:
                self._cb(src, dst)
            return True   # 阻止 Qt 的預設錯位行為
        return False


# ── 表格樣式 ────────────────────────────────────────────────────
_TABLE_SS = """
    QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #f2f2f7;
        border: none;
        border-top: 1px solid #c6c6c8;
        font-size: 13pt;
    }
    QHeaderView::section {
        background-color: #f2f2f7;
        color: #3a3a3c;
        font-weight: 600;
        font-size: 13pt;
        padding: 4px 8px;
        border: none;
        border-bottom: 2px solid #c6c6c8;
        border-right: 1px solid #e5e5ea;
    }
    QTableWidget::item {
        padding: 4px 8px;
        border-bottom: 1px solid #e5e5ea;
    }
    QTableWidget::item:selected {
        background-color: #ccdaeb;
    }
"""

# 停用列灰字
_COLOR_INACTIVE = "#aeaeb2"

# 儲存排序鈕樣式（含 disabled 灰色狀態）
_SAVE_BTN_SS = """
    QPushButton {
        background-color: #D0ECF5;
        color: #000000;
        border: 1px solid #b0d4e0;
        border-radius: 6px;
        padding: 6px 16px;
        font-size: 13pt;
    }
    QPushButton:hover    { background-color: #B8D8E8; }
    QPushButton:disabled {
        background-color: #e8e8ed;
        color: #aeaeb2;
        border: 1px solid #d1d1d6;
    }
"""


class TabSettings(BaseTab):
    """資料庫設定 Tab"""

    _PAGE_PERSONNEL = 0
    _PAGE_DEPT      = 1
    _PAGE_CASETYPE  = 2

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        self._my_tab_index = tab_index
        self._ref_dirty    = False
        # 排序暫存狀態：每頁一份 {鍵: {'rows': [...], 'dirty': bool, 'save_btn': btn, 'table': tbl}}
        self._sort_state = {}

        # ── 載入 .ui 靜態骨架 ──
        ui = loadUi(getResourcePath("layouts/Layout7.ui"))
        if not ui:
            return
        inner = ui.centralWidget()
        lay   = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)

        # ── 抓元件 ──
        self._outer_stack = inner.findChild(QStackedWidget, "outer_stack")
        self._inner_stack = inner.findChild(QStackedWidget, "inner_stack")

        # 密碼驗證頁
        self._login_card    = inner.findChild(QWidget,     "login_card")
        self._lbl_login_ttl = inner.findChild(QLabel,      "lbl_login_title")
        self.w_password     = inner.findChild(QLineEdit,   "w_password")
        self.lbl_login_err  = inner.findChild(QLabel,      "lbl_login_err")
        btn_login           = inner.findChild(QPushButton, "btn_login")

        # 左側導航
        self._nav_panel  = inner.findChild(QWidget, "nav_panel")
        self._nav_btns   = [
            inner.findChild(QPushButton, "btn_nav_personnel"),
            inner.findChild(QPushButton, "btn_nav_dept"),
            inner.findChild(QPushButton, "btn_nav_casetype"),
        ]
        btn_change_pwd = inner.findChild(QPushButton, "btn_change_pwd")
        btn_year_reset = inner.findChild(QPushButton, "btn_year_reset")
        btn_logout     = inner.findChild(QPushButton, "btn_logout")
        btn_archive_root = inner.findChild(QPushButton, "btn_archive_root")
        self._btn_archive_root = btn_archive_root

        # 三子頁的表格、新增/修改/儲存排序按鈕
        self.tbl_personnel = inner.findChild(QTableWidget, "tbl_personnel")
        self.tbl_dept      = inner.findChild(QTableWidget, "tbl_dept")
        self.tbl_casetype  = inner.findChild(QTableWidget, "tbl_casetype")

        self.btn_add_personnel  = inner.findChild(QPushButton, "btn_add_personnel")
        self.btn_edit_personnel = inner.findChild(QPushButton, "btn_edit_personnel")
        self.btn_save_personnel = inner.findChild(QPushButton, "btn_save_personnel")
        self.btn_add_dept       = inner.findChild(QPushButton, "btn_add_dept")
        self.btn_edit_dept      = inner.findChild(QPushButton, "btn_edit_dept")
        self.btn_save_dept      = inner.findChild(QPushButton, "btn_save_dept")
        self.btn_add_casetype   = inner.findChild(QPushButton, "btn_add_casetype")
        self.btn_edit_casetype  = inner.findChild(QPushButton, "btn_edit_casetype")
        self.btn_save_casetype  = inner.findChild(QPushButton, "btn_save_casetype")

        # ── 套樣式（動態狀態樣式留在 code，比照其他 Tab 慣例） ──
        self._applyStaticStyles()
        btn_login.setStyleSheet(
            "QPushButton { background-color: #D0ECF5; color: #000000; "
            "border-radius: 8px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #B8D8E8; }"
        )
        btn_change_pwd.setStyleSheet(_NAV_BOTTOM)
        btn_year_reset.setStyleSheet(_NAV_DANGER)
        btn_logout.setStyleSheet(_NAV_BOTTOM)
        if btn_archive_root:
            btn_archive_root.setStyleSheet(_NAV_BOTTOM)

        # ── 綁定 signal ──
        self.w_password.returnPressed.connect(self._doLogin)
        btn_login.clicked.connect(self._doLogin)
        for i, btn in enumerate(self._nav_btns):
            btn.clicked.connect(lambda _=False, idx=i: self._switchPage(idx))
        btn_change_pwd.clicked.connect(self._changePassword)
        btn_year_reset.clicked.connect(self._doReset)
        btn_logout.clicked.connect(self._doLogout)
        if btn_archive_root:
            btn_archive_root.clicked.connect(self._onSetArchiveRoot)

        # ── 初始化三頁的表格與排序暫存狀態 ──
        self._initRefPage("personnel", self.tbl_personnel,
                          self.btn_add_personnel, self.btn_edit_personnel,
                          self.btn_save_personnel, self._addPersonnel, self._editPersonnel)
        self._initRefPage("dept", self.tbl_dept,
                          self.btn_add_dept, self.btn_edit_dept,
                          self.btn_save_dept, self._addDept, self._editDept)
        self._initRefPage("casetype", self.tbl_casetype,
                          self.btn_add_casetype, self.btn_edit_casetype,
                          self.btn_save_casetype, self._addCaseType, self._editCaseType)

        # 提示字（用 inner 查找，避免 btn.parent() 在 QUiLoader 環境觸發 GC 刪 C++ widget）
        for _key in ("personnel", "dept", "casetype"):
            _lbl = inner.findChild(QLabel, f"lbl_hint_{_key}")
            if _lbl:
                _lbl.setText("可拖拉列以調整排序，完成後按「儲存排序」")
                _lbl.setStyleSheet("color: #8e8e93; font-size: 11pt;")

        self._outer_stack.setCurrentIndex(0)

        # 監聽身份變化：登出時自動回到密碼驗證畫面
        AuthManager.instance().role_changed.connect(self._onRoleChanged)
        # 啟動時若已是 admin（理論上不會），直接顯示主畫面
        if AuthManager.instance().is_admin():
            self._outer_stack.setCurrentIndex(1)
            self._switchPage(self._PAGE_PERSONNEL)

    # ── 套用靜態樣式到 .ui 元件 ──────────────────────────────────
    def _applyStaticStyles(self):
        self._login_card.setStyleSheet(
            "QWidget#login_card { background-color: #ffffff; border-radius: 12px; }"
        )
        self._lbl_login_ttl.setStyleSheet(
            "font-size: 16pt; font-weight: 700; color: #1c1c1e; background: transparent;"
        )
        self.w_password.setStyleSheet(
            "QLineEdit { background:#f2f2f7; border:1px solid #c6c6c8; "
            "border-radius:8px; padding:8px 12px; color:#1c1c1e; "
            "qproperty-alignment: AlignCenter; }"
            "QLineEdit:focus { border:2px solid #8fa8c8; }"
        )
        self.lbl_login_err.setStyleSheet(
            "color: #e74c3c; background: transparent; font-size: 12pt;"
        )
        # 登入鈕沿用全域 BTN 樣式
        self._nav_panel.setStyleSheet("QWidget#nav_panel { background-color: #f2f2f7; }")
        # 變更密碼 / 登出（底部 nav）
        # 三個導航鈕的選中/未選中樣式由 _switchPage 動態切換

    # ── 初始化單一參照頁（表格樣式 + 動作鈕綁定 + 排序暫存） ──────
    def _initRefPage(self, key, tbl, btn_add, btn_edit, btn_save, add_cb, edit_cb):
        # 表格樣式與行為
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setSelectionMode(QTableWidget.SingleSelection)
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(False)
        tbl.verticalHeader().setDefaultSectionSize(36)
        tbl.setStyleSheet(_TABLE_SS)
        hdr = tbl.horizontalHeader()
        name_c, alias_c, status_c = self._refCols(key)
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        tbl.setColumnWidth(0, 80)
        hdr.setSectionResizeMode(status_c, QHeaderView.Fixed)
        tbl.setColumnWidth(status_c, 80)
        hdr.setSectionResizeMode(name_c, QHeaderView.Stretch)
        if alias_c is not None:
            hdr.setSectionResizeMode(alias_c, QHeaderView.Stretch)
        tbl.cellDoubleClicked.connect(lambda row, col, cb=edit_cb: cb(row))

        # 拖拉排序（event filter 攔截 Drop，阻止 Qt 的逐格移動行為，改成整列記憶體操作）
        from PySide6.QtWidgets import QAbstractItemView
        tbl.setDragDropMode(QAbstractItemView.InternalMove)
        tbl.setDefaultDropAction(Qt.MoveAction)
        tbl.setAutoScrollMargin(90)
        drag_filter = _RowDragFilter(tbl, lambda s, d, k=key: self._onDragDrop(k, s, d))
        tbl.viewport().installEventFilter(drag_filter)

        # 動作鈕樣式與綁定
        btn_add.setStyleSheet(BTN_CONFIRM)
        btn_edit.setStyleSheet(BTN_CANCEL)
        btn_save.setStyleSheet(_SAVE_BTN_SS)
        btn_add.clicked.connect(lambda _=False, cb=add_cb: cb())
        btn_edit.clicked.connect(lambda _=False, cb=edit_cb: cb())
        btn_save.setEnabled(False)
        btn_save.clicked.connect(lambda _=False, k=key: self._saveSort(k))

        self._sort_state[key] = {
            "rows": [], "dirty": False, "save_btn": btn_save, "table": tbl,
            "drag_filter": drag_filter}  # drag_filter 存入防 GC

    def _onDragDrop(self, key, src_row, dst_row):
        """整列移動：記憶體 rows 重排，重繪表格，選中移動後的列"""
        st   = self._sort_state[key]
        rows = st["rows"]
        rows.insert(dst_row, rows.pop(src_row))
        st["dirty"] = True
        st["save_btn"].setEnabled(True)
        self._renderSortTable(key)
        st["table"].selectRow(dst_row)

    def _item(self, text, color=None):
        it = QTableWidgetItem(str(text) if text is not None else "")
        it.setTextAlignment(Qt.AlignCenter)
        it.setForeground(QColor(color if color else "#1c1c1e"))
        return it

    def _selected_row(self, table):
        sel = table.selectedItems()
        return table.row(sel[0]) if sel else -1

    # ── 左側導航切換 ────────────────────────────────────────────
    def _switchPage(self, idx):
        # 切子頁前：若有未儲存排序，先詢問。取消則不切頁、保留排序（回原狀）
        if hasattr(self, "_sort_state") and self._sort_state:
            if not self._promptUnsaved(context="switch"):
                return
        self._inner_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(_NAV_ACTIVE if i == idx else _NAV_INACTIVE)
        loaders = [self._loadPersonnel, self._loadDept, self._loadCaseType]
        loaders[idx]()

    def on_activated(self):
        """被切回設定 Tab 時重載當前子頁，確保畫面與 DB 一致
        （未存排序會被 DB 真實順序蓋掉 = 離開即放棄）。
        未登入（停在驗證頁）時不動作。"""
        if not hasattr(self, "_inner_stack"):
            return
        if not hasattr(self, "_outer_stack") or self._outer_stack.currentIndex() == 0:
            return  # 還在密碼驗證頁

        # 歸檔根目錄未設定時，每次登入後進入設定頁彈出一次警示
        self._maybeWarnArchiveRoot()

        idx = self._inner_stack.currentIndex()
        loaders = [self._loadPersonnel, self._loadDept, self._loadCaseType]
        if 0 <= idx < len(loaders):
            loaders[idx]()

    # ── 登入 ────────────────────────────────────────────────────
    def _doLogin(self):
        pwd = self.w_password.text()
        if not pwd:
            return
        ok = AuthManager.instance().login(pwd, self.db_path)
        if ok:
            self.lbl_login_err.setText("")
            self.w_password.clear()
            self._outer_stack.setCurrentIndex(1)
            self._switchPage(self._PAGE_PERSONNEL)
            # 登入成功即檢查（登入不走 on_activated，否則重置後首次登入不會提示）
            self._maybeWarnArchiveRoot()
        else:
            self.lbl_login_err.setText("密碼錯誤，請再試一次")
            self.w_password.clear()
            self.w_password.setFocus()

    # ── 身份切換監聽：登出時回到密碼驗證畫面 ─────────────────────
    def _onRoleChanged(self, role):
        if role == 'admin':
            self._outer_stack.setCurrentIndex(1)
            self._switchPage(self._PAGE_PERSONNEL)
        else:
            self._outer_stack.setCurrentIndex(0)
            self.w_password.clear()
            self.lbl_login_err.setText("")
            self._arch_warn_shown = False  # 重置，下次登入仍會檢查

    # ── 變更密碼 ────────────────────────────────────────────────
    def _changePassword(self):
        dlg = ChangePasswordDialog(self.db_path, self.tab_widget)
        if dlg.exec():
            msgInfo("完成", "密碼已成功變更", self.tab_widget)

    # ── 歸檔資料夾設定 ──────────────────────────────────────────
    def _maybeWarnArchiveRoot(self):
        """歸檔根目錄未設定時，登入後彈出一次警示（每次登入最多一次）。"""
        if getattr(self, "_arch_warn_shown", False):
            return
        if getSetting(self.db_path, ARCHIVE_ROOT_KEY, "").strip():
            return
        self._arch_warn_shown = True
        if confirmBox(
            "歸檔資料夾未設定",
            "歸檔根目錄尚未設定。\n是否現在前往「歸檔資料夾」更新？",
            confirm_text="前往設定", cancel_text="稍後",
            default_confirm=True, parent=self.tab_widget
        ):
            self._onSetArchiveRoot()

    def _onSetArchiveRoot(self):
        """設定/更新瀏覽頁開啟電子檔用的歸檔資料夾（年度層 UNC + 刑案/一般子夾名）。"""
        ArchiveRootDialog(self.db_path, self.tab_widget).exec()

    # ── 跨年度重置 ──────────────────────────────────────────────
    def _doReset(self):
        # 1. 確認彈窗（輸入 RESET、列出待清停用項目、防誤按）
        dlg = ResetDialog(self.db_path, self.tab_widget)
        if not dlg.exec():
            return

        # 2. 自動備份至 dbfile 同目錄
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            auto_backup = os.path.join(db_dir, f"dbfile_backup_{ts}.db")
            shutil.copy2(self.db_path, auto_backup)
        except Exception as e:
            msgCritical("備份失敗", f"自動備份失敗，已中止重置：\n{e}", self.tab_widget)
            return

        # 3. 詢問是否另存一份至使用者指定位置
        if confirmBox(
            "另存備份",
            "已於資料庫目錄建立自動備份。\n是否另存一份備份至其他位置？",
            confirm_text="另存", cancel_text="略過",
            confirm_danger=False, default_confirm=True,
            parent=self.tab_widget
        ):
            dest, _ = QFileDialog.getSaveFileName(
                self.tab_widget, "另存備份",
                f"dbfile_backup_{ts}.db", "SQLite 資料庫 (*.db)")
            if dest:
                try:
                    shutil.copy2(self.db_path, dest)
                except Exception as e:
                    msgWarning("另存失敗",
                               f"另存備份失敗（自動備份仍存在）：\n{e}", self.tab_widget)

        # 4. 執行重置（破壞性，transaction 保護）
        try:
            performYearEndReset(self.db_path)
        except Exception as e:
            msgCritical("重置失敗",
                        f"重置過程發生錯誤，資料已還原至重置前狀態：\n{e}",
                        self.tab_widget)
            return

        # 4.5 新年度開始：提示更新本年度歸檔資料夾
        #     （重置已清空 archive_root，須於新年度重新指定，故主動提醒）
        if confirmBox(
                "更新歸檔資料夾",
                "新年度開始，是否現在更新本年度的歸檔資料夾位置？\n"
                "（稍後仍可於設定頁的「歸檔資料夾」變更。）",
                confirm_text="更新", cancel_text="稍後",
                default_confirm=True, parent=self.tab_widget):
            ArchiveRootDialog(self.db_path, self.tab_widget).exec()

        # 5. 完成提示 → 按確定後重啟程式
        msgInfo("重置完成",
                "跨年度重置已完成。\n\n"
                "按下確定後，程式將自動關閉並重新啟動，重啟前畫面會短暫消失，"
                "屬正常現象。", self.tab_widget)
        self._restartApp()

    def _restartApp(self):
        """
        重啟程式。

        打包(onefile)情境的關鍵問題：
          PyInstaller 6.x bootloader 預設把經由 sys.executable 啟動的新程序
          視為「同一 app 的 worker 子程序」，會沿用繼承來的 _MEI 環境（指向
          舊程序正在清理的 _MEIxxxxx 暫存目錄）。新程序因而到舊的、已被刪除的
          目錄找 python3xx.dll / 標準庫，導致：
            - Failed to load Python DLL（_MEIxxxxx 下的 python3xx.dll）
            - ModuleNotFoundError: unicodedata
          （延遲啟動無法解決，反而讓舊 _MEI 清得更乾淨、DLL 更確定不存在。）
        解法（官方機制，PyInstaller 6.10+）：
          啟動新程序前設環境變數 PYINSTALLER_RESET_ENVIRONMENT=1，令新程序的
          bootloader 忽略繼承的 _MEI、解壓全新的暫存目錄，DLL 從新 _MEI 載入。
        開發情境（非 frozen）：
          沿用 QProcess 帶 sys.argv 重啟直譯器即可，無 _MEI 問題。
        """
        if getattr(sys, "frozen", False):
            try:
                env = os.environ.copy()
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                subprocess.Popen([sys.executable], env=env)
            except Exception:
                msgWarning("請手動重啟",
                           "自動重啟失敗，請手動重新開啟程式。", self.tab_widget)
                # 即使啟動失敗仍關閉本程序，避免停留在已重置但未重載的狀態
        else:
            QProcess.startDetached(sys.executable, sys.argv)

        QApplication.quit()

    # ── 登出 ────────────────────────────────────────────────────
    def _doLogout(self):
        if not confirmBox(
            "登出",
            "確定要登出管理者身份？",
            confirm_text="登出", confirm_danger=False, default_confirm=True,
            parent=self.tab_widget
        ):
            return
        AuthManager.instance().logout()

    # ════════════════════════════════════════════════════════════
    # 人員管理
    # ════════════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════════════
    # 排序 — 泛型核心（人員/部門/案類共用）
    # ════════════════════════════════════════════════════════════
    # 每頁的 DB 對應：table 名、id 欄、name 欄、啟用詞、停用詞
    _REF_CFG = {
        "personnel": ("Ref_Personnel",   "staff_id",     "staff_name",     "在職", "離職"),
        "dept":      ("Ref_Departments",  "dept_id",      "dept_name",      "啟用", "停用"),
        "casetype":  ("Ref_CaseTypes",    "case_type_id", "case_type_name", "啟用", "停用"),
    }

    def _refCols(self, key):
        """回傳該頁的欄索引 (name, alias, status)；alias 為 None 表無別名欄。
        人員頁：編號0 / 姓名1 / 別名2 / 狀態3
        部門/案類：編號0 / 名稱1 / 狀態2"""
        if key == "personnel":
            return 1, 2, 3
        return 1, None, 2

    def _loadRefGeneric(self, key):
        """從 DB 依 sort_order 撈進記憶體，清掉暫存 dirty，重繪表格"""
        tbl_name, idc, namec, _, _ = self._REF_CFG[key]
        want_alias = (key == "personnel")
        try:
            conn = self._getConn()
            if want_alias:
                # alias 欄可能尚未套補丁 → 偵測，缺欄則以 NULL 補位，整頁照常顯示（別名空白）
                has_alias = any(
                    c[1] == "alias"
                    for c in conn.execute(f"PRAGMA table_info({tbl_name})"))
                acol = "alias" if has_alias else "NULL"
                rows = conn.execute(
                    f"SELECT {idc}, {namec}, is_active, {acol} FROM {tbl_name} "
                    f"ORDER BY sort_order"
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {idc}, {namec}, is_active FROM {tbl_name} "
                    f"ORDER BY sort_order"
                ).fetchall()
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        st = self._sort_state[key]
        st["rows"]  = [list(r) for r in rows]   # [id, name, is_active(, alias)]
        st["dirty"] = False
        st["save_btn"].setEnabled(False)
        self._renderSortTable(key)

    def _renderSortTable(self, key):
        """依記憶體 rows 重繪整張表（含停用灰字）"""
        _, _, _, word_on, word_off = self._REF_CFG[key]
        name_c, alias_c, status_c = self._refCols(key)
        st  = self._sort_state[key]
        tbl = st["table"]
        tbl.setRowCount(0)
        for r, row in enumerate(st["rows"]):
            rname, active = row[1], row[2]
            tbl.insertRow(r)
            color  = None if active else _COLOR_INACTIVE
            status = word_on if active else word_off
            # col0 顯示「序號」＝目前列位置（r+1），非內部 PK；rid 仍存記憶體供存檔
            tbl.setItem(r, 0,        self._item(r + 1,  color))
            tbl.setItem(r, name_c,   self._item(rname,  color))
            if alias_c is not None:
                alias = (row[3] if len(row) > 3 and row[3] else "")
                tbl.setItem(r, alias_c, self._item(alias, color))
            tbl.setItem(r, status_c, self._item(status, color))

    def _saveSort(self, key, silent=False):
        """把記憶體順序寫回 DB sort_order（連續整數），清 dirty，設 _ref_dirty。
        silent=True 時不跳「已儲存」提示（由修改流程觸發時用）"""
        tbl_name, idc, _, _, _ = self._REF_CFG[key]
        st = self._sort_state[key]
        try:
            conn = self._getConn()
            for i, row in enumerate(st["rows"], start=1):
                conn.execute(
                    f"UPDATE {tbl_name} SET sort_order=? WHERE {idc}=?",
                    (i, row[0]))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("儲存失敗", str(e))
            return
        st["dirty"] = False
        st["save_btn"].setEnabled(False)
        self._ref_dirty = True
        if not silent:
            msgInfo("已儲存", "排序已更新", self.tab_widget)

    def _hasUnsavedSort(self):
        return any(s["dirty"] for s in self._sort_state.values())

    def _promptUnsaved(self, context="edit"):
        """有未存排序時詢問。
        context='edit'  ：取消=保留排序、中止動作（回 False）
        context='switch'：同 edit，文字為切換頁面
        context='leave' ：一律回傳 True(按離開=放棄排序、按儲存=存檔)"""
        if not self._hasUnsavedSort():
            return True
        if context == "leave":
            title, msg, confirm, cancel = "排序未儲存", "離開將遺失排序資料", "儲存", "離開"
        elif context == "switch":
            title, msg, confirm, cancel = "排序未儲存", "儲存目前排序後切換頁面？", "儲存", "取消"
        else:
            title, msg, confirm, cancel = "排序未儲存", "儲存目前排序後繼續編輯？", "儲存", "取消"
        ret = confirmBox(
            title, msg,
            confirm_text=confirm, cancel_text=cancel, parent=self.tab_widget)
        if ret:
            for k, s in self._sort_state.items():
                if s["dirty"]:
                    self._saveSort(k, silent=True)
            return True
        # 按了取消 / 離開
        if context == "leave":
            for s in self._sort_state.values():
                s["dirty"] = False
                s["save_btn"].setEnabled(False)
            return True
        # edit / switch 取消：保留排序、回報中止
        return False

    # ════════════════════════════════════════════════════════════
    # 人員管理
    # ════════════════════════════════════════════════════════════
    def _loadPersonnel(self):
        self._loadRefGeneric("personnel")

    def _addPersonnel(self):
        dlg = PersonnelAddDialog(self.db_path, self.tab_widget)
        if dlg.exec():
            self._ref_dirty = True
            self._loadPersonnel()

    def _editPersonnel(self, row=None):
        if row is None:
            row = self._selected_row(self.tbl_personnel)
        if row < 0:
            msgWarning("請選擇項目", "請先點選要修改的人員", self.tab_widget)
            return
        srow   = self._sort_state["personnel"]["rows"][row]
        sid    = srow[0]              # 真 PK，給 UPDATE 用
        sname  = srow[1]
        active = bool(srow[2])
        if not self._promptUnsaved():
            return
        dlg = PersonnelEditDialog(self.db_path, sid, row + 1, sname, active, self.tab_widget)
        if dlg.exec():
            if dlg.get_result():
                self._ref_dirty = True
                self._loadPersonnel()

    # ════════════════════════════════════════════════════════════
    # 部門管理
    # ════════════════════════════════════════════════════════════
    def _loadDept(self):
        self._loadRefGeneric("dept")

    def _addDept(self):
        dlg = DeptAddDialog(self.db_path, self.tab_widget)
        if dlg.exec():
            self._ref_dirty = True
            self._loadDept()

    def _editDept(self, row=None):
        if row is None:
            row = self._selected_row(self.tbl_dept)
        if row < 0:
            msgWarning("請選擇項目", "請先點選要修改的部門", self.tab_widget)
            return
        drow   = self._sort_state["dept"]["rows"][row]
        did    = drow[0]             # 真 PK，給 UPDATE 用
        dname  = drow[1]
        active = bool(drow[2])
        if not self._promptUnsaved():
            return
        dlg = DeptEditDialog(self.db_path, did, row + 1, dname, active, self.tab_widget)
        if dlg.exec():
            if dlg.get_result():
                self._ref_dirty = True
                self._loadDept()

    # ════════════════════════════════════════════════════════════
    # 案件類型管理
    # ════════════════════════════════════════════════════════════
    def _loadCaseType(self):
        self._loadRefGeneric("casetype")

    def _addCaseType(self):
        dlg = CaseTypeAddDialog(self.db_path, self.tab_widget)
        if dlg.exec():
            self._ref_dirty = True
            self._loadCaseType()

    def _editCaseType(self, row=None):
        if row is None:
            row = self._selected_row(self.tbl_casetype)
        if row < 0:
            msgWarning("請選擇項目", "請先點選要修改的案件類型", self.tab_widget)
            return
        trow   = self._sort_state["casetype"]["rows"][row]
        tid    = trow[0]             # 真 PK，給 UPDATE 用
        tname  = trow[1]
        active = bool(trow[2])
        if not self._promptUnsaved():
            return
        dlg = CaseTypeEditDialog(self.db_path, tid, row + 1, tname, active, self.tab_widget)
        if dlg.exec():
            if dlg.get_result():
                self._ref_dirty = True
                self._loadCaseType()
