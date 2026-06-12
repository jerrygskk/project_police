"""
tab_settings.py — 資料庫設定 Tab

流程：
  1. 進入 Tab → 顯示密碼驗證畫面（QStackedWidget index 0）
  2. 輸入正確密碼 → 切換到設定主畫面（index 1）
  3. 離開 Tab → 自動 logout，切回密碼驗證畫面
"""
import sqlite3

from PySide6.QtCore    import Qt, QSize
from PySide6.QtGui     import QColor, QIcon
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QSizePolicy, QFrame,
)

from lib.base_tab import BaseTab
from lib.auth_manager import AuthManager
from lib.db_utils import (
    msgInfo, msgWarning, msgCritical, confirmBox,
    BTN_CONFIRM, BTN_CANCEL,
)
from ui_utils import (
    PersonnelAddDialog, PersonnelEditDialog,
    DeptAddDialog, DeptEditDialog,
    CaseTypeAddDialog, CaseTypeEditDialog,
    ChangePasswordDialog,
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

        # 外層 QStackedWidget：index 0 = 密碼驗證，index 1 = 設定主畫面
        self._outer_stack = QStackedWidget(tab)
        root_lay = QVBoxLayout(tab)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.addWidget(self._outer_stack)

        self._outer_stack.addWidget(self._build_login_page())
        self._outer_stack.addWidget(self._build_main_page())
        self._outer_stack.setCurrentIndex(0)

        # 監聽身份變化：登出時自動回到密碼驗證畫面
        AuthManager.instance().role_changed.connect(self._onRoleChanged)
        # 啟動時若已是 admin（理論上不會），直接顯示主畫面
        if AuthManager.instance().current_role == 'admin':
            self._outer_stack.setCurrentIndex(1)
            self._switchPage(self._PAGE_PERSONNEL)

    # ════════════════════════════════════════════════════════════
    # 密碼驗證頁
    # ════════════════════════════════════════════════════════════
    def _build_login_page(self):
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        # 置中卡片
        card = QWidget()
        card.setFixedWidth(320)
        card.setStyleSheet(
            "QWidget { background-color: #ffffff; border-radius: 12px; }"
        )
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(12)
        card_lay.setContentsMargins(32, 28, 32, 28)

        lbl_title = QLabel("管理者驗證")
        lbl_title.setStyleSheet(
            "font-size: 16pt; font-weight: 700; color: #1c1c1e; background: transparent;"
        )
        lbl_title.setAlignment(Qt.AlignCenter)
        card_lay.addWidget(lbl_title)

        card_lay.addSpacing(4)

        self.w_password = QLineEdit()
        self.w_password.setEchoMode(QLineEdit.Password)
        self.w_password.setPlaceholderText("請輸入管理者密碼")
        self.w_password.setStyleSheet(
            "QLineEdit { background:#f2f2f7; border:1px solid #c6c6c8; "
            "border-radius:8px; padding:8px 12px; color:#1c1c1e; }"
            "QLineEdit:focus { border:2px solid #8fa8c8; }"
        )
        self.w_password.returnPressed.connect(self._doLogin)
        card_lay.addWidget(self.w_password)

        self.lbl_login_err = QLabel("")
        self.lbl_login_err.setStyleSheet("color: #e74c3c; background: transparent; font-size: 12pt;")
        self.lbl_login_err.setAlignment(Qt.AlignCenter)
        card_lay.addWidget(self.lbl_login_err)

        btn_login = QPushButton("登入")
        btn_login.setStyleSheet(
            "QPushButton { background-color: #D0ECF5; color: #000000; "
            "border-radius: 8px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #B8D8E8; }"
        )
        btn_login.clicked.connect(self._doLogin)
        card_lay.addWidget(btn_login)

        center_row = QHBoxLayout()
        center_row.addStretch()
        center_row.addWidget(card)
        center_row.addStretch()
        outer.addLayout(center_row)
        outer.addStretch()

        return page

    # ════════════════════════════════════════════════════════════
    # 設定主畫面（左導航 + 右內容）
    # ════════════════════════════════════════════════════════════
    def _build_main_page(self):
        page = QWidget()
        hlay = QHBoxLayout(page)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(0)

        # ── 左側導航 ──
        nav = QWidget()
        nav.setFixedWidth(160)
        nav.setStyleSheet("QWidget { background-color: #f2f2f7; }")
        nav_lay = QVBoxLayout(nav)
        nav_lay.setContentsMargins(12, 16, 12, 16)
        nav_lay.setSpacing(4)

        self._nav_btns = []
        nav_labels = ["人員管理", "部門管理", "案件類型"]
        for i, lbl in enumerate(nav_labels):
            btn = QPushButton(lbl)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked=False, idx=i: self._switchPage(idx))
            nav_lay.addWidget(btn)
            self._nav_btns.append(btn)

        nav_lay.addStretch()

        # 分隔線
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #d1d1d6;")
        nav_lay.addWidget(sep)
        nav_lay.addSpacing(4)

        btn_pwd = QPushButton("變更密碼")
        btn_pwd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_pwd.setStyleSheet(_NAV_BOTTOM)
        btn_pwd.clicked.connect(self._changePassword)
        nav_lay.addWidget(btn_pwd)

        btn_logout = QPushButton("登出")
        btn_logout.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_logout.setStyleSheet(_NAV_BOTTOM)
        btn_logout.clicked.connect(self._doLogout)
        nav_lay.addWidget(btn_logout)

        hlay.addWidget(nav)

        # ── 右側內容 ──
        self._inner_stack = QStackedWidget()
        self._inner_stack.addWidget(self._build_personnel_page())
        self._inner_stack.addWidget(self._build_dept_page())
        self._inner_stack.addWidget(self._build_casetype_page())
        hlay.addWidget(self._inner_stack, 1)

        # 預設人員管理
        self._switchPage(self._PAGE_PERSONNEL)

        return page

    # ── 人員管理頁 ──────────────────────────────────────────────
    def _build_personnel_page(self):
        return self._build_ref_page(
            key="personnel", name_header="姓名",
            edit_cb=self._editPersonnel, add_cb=self._addPersonnel,
            table_attr="tbl_personnel")

    # ── 部門管理頁 ──────────────────────────────────────────────
    def _build_dept_page(self):
        return self._build_ref_page(
            key="dept", name_header="部門名稱",
            edit_cb=self._editDept, add_cb=self._addDept,
            table_attr="tbl_dept")

    # ── 案件類型頁 ──────────────────────────────────────────────
    def _build_casetype_page(self):
        return self._build_ref_page(
            key="casetype", name_header="案件類型名稱",
            edit_cb=self._editCaseType, add_cb=self._addCaseType,
            table_attr="tbl_casetype")

    # ── 泛型參照頁建立器 ────────────────────────────────────────
    def _build_ref_page(self, key, name_header, edit_cb, add_cb, table_attr):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        tbl = self._make_table(
            ["編號", name_header, "狀態", "排序"],
            col_widths={0: 80, 2: 80, 3: 140},
            stretch_col=1,
        )
        tbl.cellDoubleClicked.connect(lambda row, col: edit_cb(row))
        setattr(self, table_attr, tbl)

        action_row, btn_save = self._make_action_row(
            add_cb, edit_cb, lambda _=False, k=key: self._saveSort(k))
        lay.addLayout(action_row)
        lay.addWidget(tbl)

        self._sort_state[key] = {
            "rows": [], "dirty": False, "save_btn": btn_save, "table": tbl}
        return w

    # ════════════════════════════════════════════════════════════
    # 共用工具
    # ════════════════════════════════════════════════════════════
    def _make_table(self, headers, col_widths=None, stretch_col=None):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setSelectionMode(QTableWidget.SingleSelection)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.verticalHeader().setDefaultSectionSize(36)
        t.setStyleSheet(_TABLE_SS)

        hdr = t.horizontalHeader()
        if col_widths:
            for col, w in col_widths.items():
                hdr.setSectionResizeMode(col, QHeaderView.Fixed)
                t.setColumnWidth(col, w)
        if stretch_col is not None:
            hdr.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
        return t

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

    def _make_action_row(self, add_cb, edit_cb, save_cb):
        row = QHBoxLayout()
        btn_add  = QPushButton("＋ 新增")
        btn_edit = QPushButton("✎ 修改")
        btn_add.setStyleSheet(BTN_CONFIRM)
        btn_edit.setStyleSheet(BTN_CANCEL)
        btn_add.clicked.connect(lambda: add_cb())
        btn_edit.clicked.connect(lambda: edit_cb())
        row.addWidget(btn_add)
        row.addWidget(btn_edit)
        row.addStretch()
        btn_save = QPushButton("💾 儲存排序")
        btn_save.setStyleSheet(_SAVE_BTN_SS)
        btn_save.setEnabled(False)
        btn_save.clicked.connect(save_cb)
        row.addWidget(btn_save)
        return row, btn_save

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
