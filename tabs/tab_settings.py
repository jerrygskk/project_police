"""
tab_settings.py — 資料庫設定 Tab

流程：
  1. 進入 Tab → 顯示密碼驗證畫面（QStackedWidget index 0）
  2. 輸入正確密碼 → 切換到設定主畫面（index 1）
  3. 離開 Tab → 自動 logout，切回密碼驗證畫面
"""
import sqlite3

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QColor
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QSizePolicy, QFrame,
)

from base_tab     import BaseTab
from auth_manager import AuthManager
from db_utils     import (
    msgInfo, msgWarning, msgCritical, confirmBox,
    BTN_CONFIRM, BTN_CANCEL, BTN_DANGER,
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
        color: #1c1c1e;
        border-bottom: 1px solid #e5e5ea;
    }
    QTableWidget::item:selected {
        background-color: #ccdaeb;
        color: #1c1c1e;
    }
"""

# ── 離職人員文字色 ───────────────────────────────────────────────
_COLOR_INACTIVE = "#aeaeb2"


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
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        self.tbl_personnel = self._make_table(
            ["編號", "姓名", "狀態"],
            col_widths={0: 80, 2: 80},
            stretch_col=1,
        )
        self.tbl_personnel.cellDoubleClicked.connect(
            lambda row, col: self._editPersonnel(row)
        )
        lay.addWidget(self.tbl_personnel)

        lay.addLayout(self._make_action_row(
            self._addPersonnel, self._editPersonnel, self._deletePersonnel
        ))
        return w

    # ── 部門管理頁 ──────────────────────────────────────────────
    def _build_dept_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        self.tbl_dept = self._make_table(
            ["編號", "部門名稱"],
            col_widths={0: 80},
            stretch_col=1,
        )
        self.tbl_dept.cellDoubleClicked.connect(
            lambda row, col: self._editDept(row)
        )
        lay.addWidget(self.tbl_dept)

        lay.addLayout(self._make_action_row(
            self._addDept, self._editDept, self._deleteDept
        ))
        return w

    # ── 案件類型頁 ──────────────────────────────────────────────
    def _build_casetype_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        self.tbl_casetype = self._make_table(
            ["編號", "案件類型名稱"],
            col_widths={0: 80},
            stretch_col=1,
        )
        self.tbl_casetype.cellDoubleClicked.connect(
            lambda row, col: self._editCaseType(row)
        )
        lay.addWidget(self.tbl_casetype)

        lay.addLayout(self._make_action_row(
            self._addCaseType, self._editCaseType, self._deleteCaseType
        ))
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
        t.verticalHeader().setDefaultSectionSize(32)
        t.setStyleSheet(_TABLE_SS)

        hdr = t.horizontalHeader()
        if col_widths:
            for col, w in col_widths.items():
                hdr.setSectionResizeMode(col, QHeaderView.Fixed)
                t.setColumnWidth(col, w)
        if stretch_col is not None:
            hdr.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
        return t

    def _make_action_row(self, add_cb, edit_cb, del_cb):
        row = QHBoxLayout()
        row.addStretch()
        btn_add  = QPushButton("＋ 新增")
        btn_edit = QPushButton("✎ 修改")
        btn_del  = QPushButton("✕ 刪除")
        btn_add.setStyleSheet(BTN_CONFIRM)
        btn_edit.setStyleSheet(BTN_CANCEL)
        btn_del.setStyleSheet(BTN_DANGER)
        btn_add.clicked.connect(add_cb)
        btn_edit.clicked.connect(lambda: edit_cb())
        btn_del.clicked.connect(del_cb)
        for b in [btn_add, btn_edit, btn_del]:
            row.addWidget(b)
        return row

    def _item(self, text, color=None):
        it = QTableWidgetItem(str(text) if text is not None else "")
        it.setTextAlignment(Qt.AlignCenter)
        if color:
            it.setForeground(QColor(color))
        return it

    def _selected_row(self, table):
        sel = table.selectedItems()
        return table.row(sel[0]) if sel else -1

    # ── 左側導航切換 ────────────────────────────────────────────
    def _switchPage(self, idx):
        self._inner_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(_NAV_ACTIVE if i == idx else _NAV_INACTIVE)
        loaders = [self._loadPersonnel, self._loadDept, self._loadCaseType]
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
    def _loadPersonnel(self):
        self.tbl_personnel.setRowCount(0)
        try:
            conn = self._getConn()
            rows = conn.execute(
                "SELECT staff_id, staff_name, is_active FROM Ref_Personnel ORDER BY staff_id"
            ).fetchall()
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        for sid, sname, active in rows:
            r = self.tbl_personnel.rowCount()
            self.tbl_personnel.insertRow(r)
            color  = None if active else _COLOR_INACTIVE
            status = "在職" if active else "離職"
            self.tbl_personnel.setItem(r, 0, self._item(sid,    color))
            self.tbl_personnel.setItem(r, 1, self._item(sname,  color))
            self.tbl_personnel.setItem(r, 2, self._item(status, color))

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
        dlg = PersonnelEditDialog(self.db_path, sid, sname, active, self.tab_widget)
        if dlg.exec():
            result = dlg.get_result()
            if result:
                self._ref_dirty = True
                _, new_name, new_active = result
                color  = None if new_active else _COLOR_INACTIVE
                status = "在職" if new_active else "離職"
                self.tbl_personnel.setItem(row, 0, self._item(sid,      color))
                self.tbl_personnel.setItem(row, 1, self._item(new_name, color))
                self.tbl_personnel.setItem(row, 2, self._item(status,   color))

    def _deletePersonnel(self):
        row = self._selected_row(self.tbl_personnel)
        if row < 0:
            msgWarning("請選擇項目", "請先點選要設為離職的人員", self.tab_widget)
            return
        sid   = self.tbl_personnel.item(row, 0).text()
        sname = self.tbl_personnel.item(row, 1).text()
        if self.tbl_personnel.item(row, 2).text() == "離職":
            msgInfo("提示", f"人員「{sname}」已是離職狀態", self.tab_widget)
            return
        if not confirmBox(
            "確認離職",
            f"將人員「{sname}」設為離職，該人員將不再出現於下拉選單。\n確認離職？",
            confirm_text="離職", confirm_danger=True, default_confirm=False,
            parent=self.tab_widget
        ):
            return
        try:
            conn = self._getConn()
            conn.execute(
                "UPDATE Ref_Personnel SET is_active=0 WHERE staff_id=?", (sid,)
            )
            conn.commit()
            conn.close()
            self._ref_dirty = True
            color = _COLOR_INACTIVE
            self.tbl_personnel.setItem(row, 0, self._item(sid,   color))
            self.tbl_personnel.setItem(row, 1, self._item(sname, color))
            self.tbl_personnel.setItem(row, 2, self._item("離職", color))
        except Exception as e:
            msgCritical("更新失敗", str(e))

    # ════════════════════════════════════════════════════════════
    # 部門管理
    # ════════════════════════════════════════════════════════════
    def _loadDept(self):
        self.tbl_dept.setRowCount(0)
        try:
            conn = self._getConn()
            rows = conn.execute(
                "SELECT dept_id, dept_name FROM Ref_Departments ORDER BY dept_id"
            ).fetchall()
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        for did, dname in rows:
            r = self.tbl_dept.rowCount()
            self.tbl_dept.insertRow(r)
            self.tbl_dept.setItem(r, 0, self._item(did))
            self.tbl_dept.setItem(r, 1, self._item(dname))

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
        did   = self.tbl_dept.item(row, 0).text()
        dname = self.tbl_dept.item(row, 1).text()
        dlg = DeptEditDialog(self.db_path, did, dname, self.tab_widget)
        if dlg.exec():
            result = dlg.get_result()
            if result:
                self._ref_dirty = True
                _, new_name = result
                self.tbl_dept.setItem(row, 1, self._item(new_name))

    def _deleteDept(self):
        row = self._selected_row(self.tbl_dept)
        if row < 0:
            msgWarning("請選擇項目", "請先點選要刪除的部門", self.tab_widget)
            return
        did   = self.tbl_dept.item(row, 0).text()
        dname = self.tbl_dept.item(row, 1).text()
        try:
            conn  = self._getConn()
            count = conn.execute(
                "SELECT COUNT(*) FROM Document_Task WHERE dept_id=? AND subject IS NOT NULL",
                (did,)
            ).fetchone()[0]
            count2 = conn.execute(
                "SELECT COUNT(*) FROM Document_General WHERE dept_id=? AND subject IS NOT NULL",
                (did,)
            ).fetchone()[0]
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        total = count + count2
        if total > 0:
            msgWarning(
                "無法刪除",
                f"部門「{dname}」已有 {total} 筆公文資料引用，無法刪除。",
                self.tab_widget
            )
            return
        if not confirmBox(
            "確認刪除",
            f"確定要刪除部門「{dname}」？此操作無法復原。",
            confirm_text="刪除", confirm_danger=True, default_confirm=False,
            parent=self.tab_widget
        ):
            return
        try:
            conn = self._getConn()
            conn.execute("DELETE FROM Ref_Departments WHERE dept_id=?", (did,))
            conn.commit()
            conn.close()
            self._ref_dirty = True
            self.tbl_dept.removeRow(row)
        except Exception as e:
            msgCritical("刪除失敗", str(e))

    # ════════════════════════════════════════════════════════════
    # 案件類型管理
    # ════════════════════════════════════════════════════════════
    def _loadCaseType(self):
        self.tbl_casetype.setRowCount(0)
        try:
            conn = self._getConn()
            rows = conn.execute(
                "SELECT case_type_id, case_type_name FROM Ref_CaseTypes ORDER BY case_type_id"
            ).fetchall()
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        for tid, tname in rows:
            r = self.tbl_casetype.rowCount()
            self.tbl_casetype.insertRow(r)
            self.tbl_casetype.setItem(r, 0, self._item(tid))
            self.tbl_casetype.setItem(r, 1, self._item(tname))

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
        tid   = self.tbl_casetype.item(row, 0).text()
        tname = self.tbl_casetype.item(row, 1).text()
        dlg = CaseTypeEditDialog(self.db_path, tid, tname, self.tab_widget)
        if dlg.exec():
            result = dlg.get_result()
            if result:
                self._ref_dirty = True
                _, new_name = result
                self.tbl_casetype.setItem(row, 1, self._item(new_name))

    def _deleteCaseType(self):
        row = self._selected_row(self.tbl_casetype)
        if row < 0:
            msgWarning("請選擇項目", "請先點選要刪除的案件類型", self.tab_widget)
            return
        tid   = self.tbl_casetype.item(row, 0).text()
        tname = self.tbl_casetype.item(row, 1).text()
        try:
            conn  = self._getConn()
            count = conn.execute(
                "SELECT COUNT(*) FROM Document_Criminal WHERE case_type=? AND report_date IS NOT NULL",
                (tid,)
            ).fetchone()[0]
            conn.close()
        except Exception as e:
            msgCritical("DB錯誤", str(e))
            return
        if count > 0:
            msgWarning(
                "無法刪除",
                f"案件類型「{tname}」已有 {count} 筆刑案資料引用，無法刪除。",
                self.tab_widget
            )
            return
        if not confirmBox(
            "確認刪除",
            f"確定要刪除案件類型「{tname}」？此操作無法復原。",
            confirm_text="刪除", confirm_danger=True, default_confirm=False,
            parent=self.tab_widget
        ):
            return
        try:
            conn = self._getConn()
            conn.execute("DELETE FROM Ref_CaseTypes WHERE case_type_id=?", (tid,))
            conn.commit()
            conn.close()
            self._ref_dirty = True
            self.tbl_casetype.removeRow(row)
        except Exception as e:
            msgCritical("刪除失敗", str(e))
