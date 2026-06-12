"""
tab_settings.py — 資料庫設定 Tab

流程：
  1. 進入 Tab → 顯示密碼驗證畫面（QStackedWidget index 0）
  2. 輸入正確密碼 → 切換到設定主畫面（index 1）
  3. 離開 Tab → 自動 logout，切回密碼驗證畫面
"""
import os
import sys
import sqlite3
import shutil
import subprocess
from datetime import datetime

from PySide6.QtCore    import Qt, QSize, QProcess
from PySide6.QtGui     import QColor, QIcon
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QStackedWidget,
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
    performYearEndReset,
)
from ui_utils import (
    PersonnelAddDialog, PersonnelEditDialog,
    DeptAddDialog, DeptEditDialog,
    CaseTypeAddDialog, CaseTypeEditDialog,
    ChangePasswordDialog, ResetDialog,
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

# 排序小按鈕樣式（表格內四顆）
_SORT_BTN_SS = """
    QPushButton {
        font-size: 12pt;
        padding: 0px;
        border: 1px solid #c6c6c8;
        border-radius: 4px;
        background-color: #ffffff;
        color: #1c1c1e;
    }
    QPushButton:hover   { background-color: #e8e8ed; }
    QPushButton:pressed { background-color: #d1d1d6; }
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

        # ── 綁定 signal ──
        self.w_password.returnPressed.connect(self._doLogin)
        btn_login.clicked.connect(self._doLogin)
        for i, btn in enumerate(self._nav_btns):
            btn.clicked.connect(lambda _=False, idx=i: self._switchPage(idx))
        btn_change_pwd.clicked.connect(self._changePassword)
        btn_year_reset.clicked.connect(self._doReset)
        btn_logout.clicked.connect(self._doLogout)

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

        self._outer_stack.setCurrentIndex(0)

        # 監聽身份變化：登出時自動回到密碼驗證畫面
        AuthManager.instance().role_changed.connect(self._onRoleChanged)
        # 啟動時若已是 admin（理論上不會），直接顯示主畫面
        if AuthManager.instance().current_role == 'admin':
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
            "border-radius:8px; padding:8px 12px; color:#1c1c1e; }"
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
        for col, w in {0: 80, 2: 80, 3: 140}.items():
            hdr.setSectionResizeMode(col, QHeaderView.Fixed)
            tbl.setColumnWidth(col, w)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.cellDoubleClicked.connect(lambda row, col, cb=edit_cb: cb(row))

        # 動作鈕樣式與綁定
        btn_add.setStyleSheet(BTN_CONFIRM)
        btn_edit.setStyleSheet(BTN_CANCEL)
        btn_save.setStyleSheet(_SAVE_BTN_SS)
        btn_add.clicked.connect(lambda _=False, cb=add_cb: cb())
        btn_edit.clicked.connect(lambda _=False, cb=edit_cb: cb())
        btn_save.setEnabled(False)
        btn_save.clicked.connect(lambda _=False, k=key: self._saveSort(k))

        self._sort_state[key] = {
            "rows": [], "dirty": False, "save_btn": btn_save, "table": tbl}

    # ── 排序欄四顆小按鈕 ────────────────────────────────────────
    def _make_sort_cell(self, page_key, get_row_fn):
        """產生一格含四顆排序小鈕的 widget；get_row_fn() 動態回傳當前列號"""
        cell = QWidget()
        h = QHBoxLayout(cell)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(2)
        specs = [(":/sort_top.svg",    "置頂", "top"),
                 (":/sort_up.svg",     "上移", "up"),
                 (":/sort_down.svg",   "下移", "down"),
                 (":/sort_bottom.svg", "置底", "bottom")]
        for icon_path, tip, act in specs:
            b = QPushButton()
            b.setIcon(QIcon(icon_path))
            b.setIconSize(QSize(14, 14))
            b.setToolTip(tip)
            b.setFixedSize(26, 26)
            b.setStyleSheet(_SORT_BTN_SS)
            b.clicked.connect(
                lambda _=False, a=act, k=page_key, f=get_row_fn: self._moveRow(k, f(), a)
            )
            h.addWidget(b)
        h.addStretch()
        return cell

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

    # ── 變更密碼 ────────────────────────────────────────────────
    def _changePassword(self):
        dlg = ChangePasswordDialog(self.db_path, self.tab_widget)
        if dlg.exec():
            msgInfo("完成", "密碼已成功變更", self.tab_widget)

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

    def _loadRefGeneric(self, key):
        """從 DB 依 sort_order 撈進記憶體，清掉暫存 dirty，重繪表格"""
        tbl_name, idc, namec, _, _ = self._REF_CFG[key]
        try:
            conn = self._getConn()
            rows = conn.execute(
                f"SELECT {idc}, {namec}, is_active FROM {tbl_name} "
                f"ORDER BY sort_order"
            ).fetchall()
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        st = self._sort_state[key]
        st["rows"]  = [list(r) for r in rows]   # [id, name, is_active]
        st["dirty"] = False
        st["save_btn"].setEnabled(False)
        self._renderSortTable(key)

    def _renderSortTable(self, key):
        """依記憶體 rows 重繪整張表（含排序欄四鈕、停用灰字）"""
        _, _, _, word_on, word_off = self._REF_CFG[key]
        st  = self._sort_state[key]
        tbl = st["table"]
        tbl.setRowCount(0)
        for r, (rid, rname, active) in enumerate(st["rows"]):
            tbl.insertRow(r)
            color  = None if active else _COLOR_INACTIVE
            status = word_on if active else word_off
            tbl.setItem(r, 0, self._item(rid,    color))
            tbl.setItem(r, 1, self._item(rname,  color))
            tbl.setItem(r, 2, self._item(status, color))
            # 排序欄：用當前列的 id 動態定位列號（重繪後列號會變）
            cell = self._make_sort_cell(key, lambda rid=rid, k=key: self._rowOfId(k, rid))
            tbl.setCellWidget(r, 3, cell)

    def _rowOfId(self, key, rid):
        for i, row in enumerate(self._sort_state[key]["rows"]):
            if row[0] == rid:
                return i
        return -1

    def _moveRow(self, key, row, action):
        """記憶體層移動列，標 dirty，亮儲存鈕，重繪"""
        st   = self._sort_state[key]
        rows = st["rows"]
        n    = len(rows)
        if row < 0 or n < 2:
            return
        if action == "up":
            if row == 0: return
            rows[row-1], rows[row] = rows[row], rows[row-1]
        elif action == "down":
            if row == n-1: return
            rows[row+1], rows[row] = rows[row], rows[row+1]
        elif action == "top":
            if row == 0: return
            rows.insert(0, rows.pop(row))
        elif action == "bottom":
            if row == n-1: return
            rows.append(rows.pop(row))
        st["dirty"] = True
        st["save_btn"].setEnabled(True)
        self._renderSortTable(key)

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
        sid    = self.tbl_personnel.item(row, 0).text()
        sname  = self.tbl_personnel.item(row, 1).text()
        active = self.tbl_personnel.item(row, 2).text() == "在職"
        if not self._promptUnsaved():
            return
        dlg = PersonnelEditDialog(self.db_path, sid, sname, active, self.tab_widget)
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
        did    = self.tbl_dept.item(row, 0).text()
        dname  = self.tbl_dept.item(row, 1).text()
        active = self.tbl_dept.item(row, 2).text() == "啟用"
        if not self._promptUnsaved():
            return
        dlg = DeptEditDialog(self.db_path, did, dname, active, self.tab_widget)
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
        tid    = self.tbl_casetype.item(row, 0).text()
        tname  = self.tbl_casetype.item(row, 1).text()
        active = self.tbl_casetype.item(row, 2).text() == "啟用"
        if not self._promptUnsaved():
            return
        dlg = CaseTypeEditDialog(self.db_path, tid, tname, active, self.tab_widget)
        if dlg.exec():
            if dlg.get_result():
                self._ref_dirty = True
                self._loadCaseType()
