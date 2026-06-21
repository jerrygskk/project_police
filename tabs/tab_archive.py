import os
import re

from PySide6.QtCore import Qt, QUrl, QSize, QTimer
from PySide6.QtGui import QDesktopServices, QPalette, QColor, QIcon, QIntValidator
from PySide6.QtWidgets import (
    QVBoxLayout, QTabWidget, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QWidget,
    QHBoxLayout, QListWidget, QHeaderView,
    QStackedWidget, QSizePolicy,
)

from lib.base_tab import BaseTab
from lib.db_utils import getResourcePath, loadUi, msgCritical, msgInfo, confirmBox, archiveDefaultDir, getSetting, ARCHIVE_ROOT_KEY
from lib.auth_manager import AuthManager
from lib.archive_text import _trimName, _tokenize, _parseDate, _sanitize, _pkOf
from ui_utils import (
    setupPreviewTable, autoResizeTable, setDocIdLinkCell,
    RowHoverFilter, RowHoverDelegate, TwoLineElideLabel,
    CriminalEditDialog, GeneralEditDialog,
)


# 車牌／案號連字號（MQM-1763、P77-965、822-NHS、9362-F6…）：兩側英數。
# 字母可能在左或右（數字開頭車牌如 822-NHS），故不用 lookahead 限定側別，
# 改於替換時要求「整段至少含一字母」——純數字-數字（日期 1150617、PK「10」、
# 已格式化的「10-1140601」）不含字母，不會被誤遮成主旨/人名分隔符。
_PLATE_DASH_RE = re.compile(r"[A-Za-z0-9]{2,5}[-－][A-Za-z0-9]{2,6}")
# 開頭（PK-）日期：保護用，遮罩車牌前先抓出，避免日期尾數字與車牌頭被連在一起。
_HEAD_DATE_RE = re.compile(
    r"\s*(?:\d+[-－])*(?:1\d{2}|20\d{2})[-.\/]?\d{1,2}[-.\/]?\d{1,2}")
_PLATE_SENT = "\x01"   # 遮罩用哨兵，組完主旨後還原成 -


def _maskPlateDash(text):
    """把車牌型連字號的 - 暫換成哨兵，避免被當主旨/人名分隔符切散。"""
    def repl(m):
        s = m.group(0)
        if re.search(r"[A-Za-z]", s):   # 含字母才視為車牌/案號
            return s.replace("-", _PLATE_SENT).replace("－", _PLATE_SENT)
        return s
    return _PLATE_DASH_RE.sub(repl, text)


# ─────────────────────────────────────────────────────────────
# 兩張表的設定：View、底層表、可比對欄位、組檔名用的欄位
# ─────────────────────────────────────────────────────────────
META = {
    "crim": {
        "view": "View_Criminal_Full", "base": "Document_Criminal",
        "id_col": "送文編號",
        # 精簡模式只顯示前三欄(slim=True)：編號 案由 承辦人；其餘僅完整模式。
        # 比照資料庫瀏覽：建全欄，切模式用 setColumnHidden 藏/顯示，不重建。
        "cols": [
            {"view": "送文編號",   "header": "編號",   "slim": True,  "w": 64},
            {"view": "嫌疑人_案由", "header": "案由",   "slim": True,  "w": 220, "left": True},
            {"view": "主承辦人",   "header": "承辦人", "slim": True,  "w": 80, "trim": True},
            {"view": "報案人",     "header": "報案人", "slim": False, "w": 70},
            {"view": "案類",       "header": "案類",   "slim": False, "w": 90},
            {"view": "陳報日期",   "header": "日期",   "slim": False, "w": 100},
        ],
        "match_cols": ["主承辦人", "案類", "嫌疑人_案由", "報案人"],
        "subject_col": "嫌疑人_案由", "processor_col": "主承辦人",
        "dialog": CriminalEditDialog,
    },
    "gen": {
        "view": "View_General_Full", "base": "Document_General",
        "id_col": "送文編號",
        "cols": [
            {"view": "送文編號", "header": "編號",   "slim": True,  "w": 64},
            {"view": "陳報主旨", "header": "主旨",   "slim": True,  "w": 220, "left": True},
            {"view": "陳報人",   "header": "陳報人", "slim": True,  "w": 80, "trim": True},
            {"view": "陳報日期", "header": "日期",   "slim": False, "w": 140},
            {"view": "業務單位", "header": "單位",   "slim": False, "w": 90},
        ],
        "match_cols": ["陳報人", "業務單位", "陳報主旨"],
        "subject_col": "陳報主旨", "processor_col": "陳報人",
        "dialog": GeneralEditDialog,
    },
}


class TabArchive(BaseTab):
    """檔案歸檔：刑案 / 一般分開歸檔，各自選資料夾，模糊比對 PDF 後正名歸檔。"""

    # 膠囊型 toggle 鈕樣式（比照資料庫瀏覽頁）
    _SEG_STYLE = """
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #c6c6c8;
            border-radius: 17px;
            padding: 6px 16px;
            color: #636366;
            font-weight: 500;
        }
        QPushButton:checked {
            background-color: #8fa8c8;
            border: 1px solid #8fa8c8;
            color: #ffffff;
            font-weight: 600;
        }
        QPushButton:!checked:hover { background-color: #f2f2f7; }
    """

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return
        widget = loadUi(getResourcePath("layouts/Layout6.ui"))
        if not widget:
            return
        inner = widget.centralWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)
        self._inner = inner

        # 權限牆：非管理者顯示提示頁（page_gate），管理者顯示內容（page_content）
        self._outer_stack = inner.findChild(QStackedWidget, "outer_stack")
        self._applyGate()
        AuthManager.instance().role_changed.connect(self._applyGate)

        # 子頁籤樣式：比照資料庫瀏覽頁（選中加底部藍線指示），只套此 QTabWidget
        subtabs = inner.findChild(QTabWidget, "arch_subtabs")
        if subtabs:
            subtabs.setStyleSheet("""
                QTabWidget#arch_subtabs::pane { border: none; }
                QTabWidget#arch_subtabs QTabBar::tab {
                    background-color: transparent;
                    color: #636366;
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 8px 18px;
                    margin-right: 4px;
                    font-weight: 500;
                }
                QTabWidget#arch_subtabs QTabBar::tab:selected {
                    color: #8fa8c8;
                    border-bottom: 2px solid #8fa8c8;
                    font-weight: 600;
                }
                QTabWidget#arch_subtabs QTabBar::tab:hover:!selected { color: #3a3a3c; }
            """)

        self._folders = {"crim": "", "gen": ""}   # 各自的 PDF 資料夾
        self._pdfs = {"crim": [], "gen": []}       # 各自掃到的 PDF 完整路徑
        self._selected = {"crim": None, "gen": None}  # 鎖定的 doc_id

        # 歸檔根目錄警示 label（放在 pick 按鈕右側，archive_root 空時顯示）
        _ARCH_WARN_SS  = "color:#e74c3c; font-size:11pt;"
        _ARCH_WARN_TXT = "⚠ 歸檔資料夾未設定，請至設定頁更新"
        self._arch_warn = {}
        for key in ("crim", "gen"):
            lbl = QLabel(_ARCH_WARN_TXT)
            lbl.setStyleSheet(_ARCH_WARN_SS)
            lbl.setVisible(False)
            fl = inner.findChild(QHBoxLayout, f"{key}_folder")
            if fl:
                fl.addWidget(lbl)
            self._arch_warn[key] = lbl

        self._ui = {}
        for key in ("crim", "gen"):
            self._ui[key] = {
                "path":         inner.findChild(QLineEdit, f"{key}_path"),
                "pick":         inner.findChild(QPushButton, f"{key}_pick"),
                "doc":          inner.findChild(QTableWidget, f"{key}_doc_table"),
                "doc_search":   inner.findChild(QLineEdit, f"{key}_doc_search"),
                "kw":           inner.findChild(QLineEdit, f"{key}_kw"),
                "paper_only":   inner.findChild(QPushButton, f"{key}_paper_only"),
                "match":        inner.findChild(QPushButton, f"{key}_match"),
                "pdf":          inner.findChild(QTableWidget, f"{key}_pdf_table"),
                "h_pk":         inner.findChild(QLineEdit, f"{key}_h_pk"),
                "h_date":       inner.findChild(QLineEdit, f"{key}_h_date"),
                "h_subj":       inner.findChild(QLineEdit, f"{key}_h_subj"),
                "h_proc":       inner.findChild(QLineEdit, f"{key}_h_proc"),
                "people":       inner.findChild(QListWidget, f"{key}_people_list"),
                "final":        inner.findChild(QLabel, f"{key}_final"),
                "archive":      inner.findChild(QPushButton, f"{key}_do_archive"),
                "reset":        inner.findChild(QPushButton, f"{key}_reset"),
                # 單顆 toggle 鈕（layout 內，不浮貼，避免重複/定位問題）
                "full":         inner.findChild(QPushButton, f"{key}_toggle_full"),
                "pdf_all":      inner.findChild(QPushButton, f"{key}_toggle_archived"),
            }
            # 套 toggle 樣式
            for k in ("full", "pdf_all"):
                btn = self._ui[key][k]
                if btn:
                    btn.setStyleSheet(self._SEG_STYLE)
            # 最終檔名：換成固定 2 行的省略標籤，避免長檔名破版／往下長到第 3 行
            fin = self._ui[key]["final"]
            actions = inner.findChild(QHBoxLayout, f"{key}_pv_actions")
            if fin and actions is not None:
                new_fin = TwoLineElideLabel(fin.text())
                new_fin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                actions.replaceWidget(fin, new_fin)
                fin.deleteLater()
                self._ui[key]["final"] = new_fin
            self._curPdf = getattr(self, "_curPdf", {})
            self._curPdf[key] = None
            self._bind(key)
            self._initPdfTable(key)
            self._loadPeople(key)
            self._loadDocs(key)
        # 記錄初始指紋，供切換進來時判斷是否需重載
        self._sigs = {}
        for key in ("crim", "gen"):
            try:
                self._sigs[key] = self._tableSignature(key)
            except Exception:
                pass

        # 被切換顯示時自動帶入歸檔根資料夾（framework 不會對本頁呼叫 on_activated）
        self._tab_index = tab_index
        try:
            self.tab_widget.currentChanged.connect(self._onShown)
        except Exception:
            pass
        # 若一進來就停在本頁且已是管理者，立即帶入一次
        if self.tab_widget.currentIndex() == tab_index \
                and AuthManager.instance().is_admin():
            for key in ("crim", "gen"):
                self._autoloadDefault(key)

    def _onShown(self, idx):
        """本頁被切換顯示時，自動帶入歸檔根資料夾（尚未選擇時）。"""
        if idx != getattr(self, "_tab_index", -1):
            return
        self._updateArchWarn()
        if AuthManager.instance().is_admin():
            for key in ("crim", "gen"):
                self._autoloadDefault(key)

    def _updateArchWarn(self):
        has_root = bool(getSetting(self.db_path, ARCHIVE_ROOT_KEY, "").strip())
        for key in ("crim", "gen"):
            lbl = self._arch_warn.get(key)
            if lbl:
                lbl.setVisible(not has_root)

    def _bind(self, key):
        u = self._ui[key]
        if u["pick"]:
            u["pick"].clicked.connect(lambda _, k=key: self._pickFolder(k))
        if u["match"]:
            u["match"].clicked.connect(lambda _, k=key: self._rematch(k))
        if u["kw"]:
            u["kw"].returnPressed.connect(lambda k=key: self._rematch(k))
        # 預覽四格任一編輯 → 即時更新最終檔名
        for fld in ("h_date", "h_subj", "h_proc"):
            if u[fld]:
                u[fld].textChanged.connect(lambda _, k=key: self._refreshFinal(k))
        # 承辦人清單點一下 → 加到承辦人格（去重）
        if u["people"]:
            u["people"].itemClicked.connect(
                lambda item, k=key: self._addProc(k, item.text()))
        # 確認歸檔
        if u["archive"]:
            u["archive"].clicked.connect(lambda _, k=key: self._doArchive(k))
        # 還原預設（回到選定 PDF 當下的初判值）
        if u["reset"]:
            u["reset"].clicked.connect(lambda _, k=key: self._resetDefault(k))
        # 精簡/完整切換（鈕已於 _makeSegButtons 建立、分組、套樣式）
        if u.get("full"):
            u["full"].toggled.connect(lambda _, k=key: self._applyDocMode(k))
        # 候選檔案 未歸檔/全部顯示 切換 → 重新比對（過濾已歸檔 PDF）
        if u.get("pdf_all"):
            u["pdf_all"].toggled.connect(lambda _, k=key: self._rematch(k))
        # 只歸紙本：標記 is_reported=1，不需 PDF
        if u.get("paper_only"):
            u["paper_only"].clicked.connect(lambda _, k=key: self._archivePaperOnly(k))
        # 待歸檔「編號搜尋」：只收數字、1 秒延遲自動套用、用 setRowHidden 過濾不重建
        se = u.get("doc_search")
        if se:
            se.setValidator(QIntValidator(0, 9_999_999, se))
            self._searchTimers = getattr(self, "_searchTimers", {})
            t = QTimer(se)
            t.setSingleShot(True)
            t.setInterval(1000)
            t.timeout.connect(lambda k=key: self._applyDocSearch(k))
            self._searchTimers[key] = t
            se.textChanged.connect(lambda _txt, tm=t: tm.start())

    # ── 承辦人清單（DB 全體，點擊加入預覽承辦人格）──────────
    def _loadPeople(self, key):
        lw = self._ui[key]["people"]
        if not lw:
            return
        lw.clear()
        try:
            conn = self._getConn()
            for (raw,) in conn.execute(
                    "SELECT staff_name FROM Ref_Personnel ORDER BY sort_order"):
                full = _trimName(raw)
                if full:
                    lw.addItem(full)
            conn.close()
        except Exception:
            pass

    def _addProc(self, key, name):
        el = self._ui[key]["h_proc"]
        if not el:
            return
        cur = [s.strip() for s in (el.text() or "").split("、") if s.strip()]
        if name not in cur:
            cur.append(name)
        el.setText("、".join(cur))   # textChanged 會觸發 _refreshFinal

    def _refreshFinal(self, key):
        u = self._ui[key]
        if not u["final"]:
            return
        pk = (u["h_pk"].text() or "").strip() if u["h_pk"] else ""
        date = (u["h_date"].text() or "").strip() if u["h_date"] else ""
        subj = (u["h_subj"].text() or "").strip() if u["h_subj"] else ""
        proc = (u["h_proc"].text() or "").strip() if u["h_proc"] else ""
        parts = [p for p in [pk, date, subj, proc] if p]
        name = "-".join(parts) + ".pdf" if parts else "—"
        u["final"].setText(f"最終檔名：{name}")

    # ── 未歸檔公文清單 ──────────────────────────────────────
    def _loadDocs(self, key):
        meta = META[key]
        table = self._ui[key]["doc"]
        if not table:
            return
        # 未歸檔 = is_electronic 為空（查詢統一走 _queryUnarchived）
        try:
            rows = self._queryUnarchived(key)
        except Exception as e:
            msgCritical("DB錯誤", f"載入未歸檔公文失敗：{e}")
            return

        cols = meta["cols"]
        headers = [c["header"] for c in cols]
        # 自行初始化表格（不走 setupPreviewTable，避開其 200ms 延遲 autoResize）。
        # 編號/承辦人等固定欄維持固定寬；案由/主旨為彈性欄(_fitDocCols 計算)，
        # 文字過長以 elide(…) 切字。
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setTextElideMode(Qt.ElideRight)   # 欄寬不足時案由切字顯示 …
        table.setWordWrap(False)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionsMovable(False)
        # 案由/主旨(left 欄)用 Stretch 自動吃剩餘空間(Qt 內建，不需自算/不依賴時序)，
        # 其餘欄 Fixed 固定寬。如此承辦人等固定欄一定可見，主旨自動伸縮、過長 elide 切字。
        stretch_ci = next((i for i, c in enumerate(cols) if c.get("left")), 1)
        for ci, c in enumerate(cols):
            if ci == stretch_ci:
                hdr.setSectionResizeMode(ci, QHeaderView.Stretch)
            else:
                hdr.setSectionResizeMode(ci, QHeaderView.Fixed)
                table.setColumnWidth(ci, c["w"])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setRowCount(0)
        # 點整列即選（取代 radio）
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        # 選中色用 palette 設定（避免被全域 stylesheet 蓋成預設深藍）
        pal = table.palette()
        pal.setColor(QPalette.Highlight, QColor("#eaf1f8"))
        pal.setColor(QPalette.HighlightedText, QColor("#1c1c1e"))
        table.setPalette(pal)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f2f2f7;
                border: none; border-top: 1px solid #c6c6c8;
                font-size: 13pt;
            }
            QHeaderView::section {
                background-color: #f2f2f7; color: #3a3a3c;
                font-weight: 600; font-size: 13pt;
                padding: 4px 4px; border: none;
                border-bottom: 1px solid #c6c6c8;
            }
            QTableWidget::item { padding: 2px 4px; }
            QTableWidget::item:hover { background-color: transparent; }
            QTableWidget::item:selected {
                background-color: #eaf1f8; color: #1c1c1e;
                border-left: 3px solid #8fa8c8;
            }
        """)
        # 列選取訊號只接一次
        self._selBound = getattr(self, "_selBound", set())
        if key not in self._selBound:
            table.itemSelectionChanged.connect(lambda k=key: self._onRowSelected(k))
            self._selBound.add(key)

        self._docrows = getattr(self, "_docrows", {})
        self._docrows[key] = {}
        self._docorder = getattr(self, "_docorder", {})
        self._docorder[key] = []
        for r in rows:
            pos = table.rowCount()
            table.insertRow(pos)
            doc_id = str(r.get(meta["id_col"]) or "")
            self._fillDocRow(key, table, cols, r, pos)
            self._docrows[key][doc_id] = r
            self._docorder[key].append(doc_id)
        # 記錄載入時間，供差異更新比對
        self._lastLoad = getattr(self, "_lastLoad", {})
        self._lastLoad[key] = self._dbNow()
        # 套用目前模式（精簡只顯示前三欄）+ 算彈性欄寬
        self._applyDocMode(key)
        # 全量載入後重新套用編號搜尋（若有）
        self._applyDocSearch(key)

    def _fillDocRow(self, key, table, cols, r, pos):
        """填一列（新建或就地更新）。編號→超連結(點開編輯)、承辦人去後綴、案由靠左+tooltip。"""
        meta = META[key]
        for ci, c in enumerate(cols):
            if c["view"] == meta["id_col"]:
                # 編號欄：超連結，點擊開該筆編輯視窗（比照交辦單/資料庫瀏覽）
                doc_id = str(r.get(c["view"]) or "")
                setDocIdLinkCell(
                    table, pos, ci, doc_id,
                    lambda _row, did, k=key: self._onEditDoc(k, did))
                continue
            val = r.get(c["view"])
            text = "" if val is None else str(val)
            if c.get("trim"):
                text = _trimName(text)
            item = QTableWidgetItem(text)
            if c.get("left"):
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if text:
                    item.setToolTip(text)
                # 紙本已歸（is_reported=1，View『紙本』欄='是'）→ 案由前加紙圖示
                if str(r.get("紙本") or "") == "是":
                    item.setIcon(QIcon(":/icon_paper.svg"))
            else:
                item.setTextAlignment(Qt.AlignCenter)
            table.setItem(pos, ci, item)

    def _onEditDoc(self, key, doc_id):
        """點編號開該筆編輯視窗；改完做差異更新並同步指紋（dirty flag）。"""
        dialog_cls = META[key].get("dialog")
        if not dialog_cls:
            return
        dlg = dialog_cls(self.db_path, doc_id, self._ui[key]["doc"])
        if dlg.exec():
            self._diffDocs(key)
            self._sigs = getattr(self, "_sigs", {})
            try:
                self._sigs[key] = self._tableSignature(key)
            except Exception:
                pass


    def _isEmptiedDoc(self, key, r):
        """判斷該列是否為清空式刪除（編號以外的內容欄全空）。"""
        meta = META[key]
        for c in meta["cols"]:
            if c["view"] == meta["id_col"]:
                continue
            if r.get(c["view"]):
                return False
        return True

    def _diffDocs(self, key):
        """差異更新待歸檔清單：只處理上次載入後變動的列，其餘不動。
        新增→加列、修改→就地更新、已歸檔/清空/已不在未歸檔→移除列。"""
        meta = META[key]
        table = self._ui[key]["doc"]
        if not table:
            return
        since = getattr(self, "_lastLoad", {}).get(key)
        if since is None:
            self._loadDocs(key)
            return

        conn = self._getConn()
        try:
            changed_ids = [str(row[0]) for row in conn.execute(
                f"SELECT doc_id FROM {meta['base']} WHERE last_modified > ?",
                (since,)).fetchall()]
        finally:
            conn.close()
        if not changed_ids:
            self._lastLoad[key] = self._dbNow()
            return

        # 取變動筆的完整 View 列（僅未歸檔者會出現在查詢結果）
        rows_by_id = {}
        for r in self._queryUnarchived(key):
            did = str(r.get(meta["id_col"]) or "")
            if did in changed_ids:
                rows_by_id[did] = r

        cols = meta["cols"]
        order = self._docorder.setdefault(key, [])
        for did in changed_ids:
            r = rows_by_id.get(did)
            in_table = did in order
            # 應顯示 = 在未歸檔查詢結果內、且非清空列
            should_show = (r is not None) and (not self._isEmptiedDoc(key, r))

            if should_show and not in_table:
                pos = table.rowCount()
                table.insertRow(pos)
                self._fillDocRow(key, table, cols, r, pos)
                order.append(did)
                self._docrows[key][did] = r
            elif should_show and in_table:
                pos = order.index(did)
                self._fillDocRow(key, table, cols, r, pos)
                self._docrows[key][did] = r
            elif (not should_show) and in_table:
                pos = order.index(did)
                table.removeRow(pos)
                order.pop(pos)
                self._docrows[key].pop(did, None)

        self._lastLoad[key] = self._dbNow()
        self._applyDocMode(key)
        # 列集合可能變動 → 重新套用目前的編號搜尋過濾
        self._applyDocSearch(key)

    # ── 待歸檔編號搜尋（setRowHidden 過濾，不重建表格）──────────
    def _applyDocSearch(self, key):
        u = self._ui.get(key, {})
        table = u.get("doc")
        se = u.get("doc_search")
        if not table or not se:
            return
        q = (se.text() or "").strip()
        order = self._docorder.get(key, [])
        for row in range(table.rowCount()):
            doc_id = order[row] if row < len(order) else ""
            hide = bool(q) and not str(doc_id).startswith(q)
            table.setRowHidden(row, hide)

    def _clearDocSearch(self, key):
        """清空搜尋字串＋取消待觸發的延遲＋顯示全部列。"""
        u = self._ui.get(key, {})
        se = u.get("doc_search")
        table = u.get("doc")
        t = getattr(self, "_searchTimers", {}).get(key)
        if t:
            t.stop()
        if se:
            se.blockSignals(True)
            se.clear()
            se.blockSignals(False)
        if table:
            for row in range(table.rowCount()):
                table.setRowHidden(row, False)

    def _queryUnarchived(self, key):
        """查未歸檔公文（is_electronic 為空）的完整 View 列。
        排除已軟刪除的空殼：刪除是清空式 UPDATE（案由/主旨設 NULL），
        這類列雖 is_electronic 空但已無內容，不應出現在待歸檔。"""
        meta = META[key]
        # 底層內容欄（案由/主旨）為空即視為已刪除空殼
        subj_base = "subject_summary" if key == "crim" else "subject"
        conn = self._getConn()
        try:
            cur = conn.execute(
                f"SELECT * FROM {meta['view']} v "
                f"JOIN {meta['base']} b ON v.\"{meta['id_col']}\" = b.doc_id "
                f"WHERE (b.is_electronic IS NULL OR b.is_electronic = '') "
                f"AND b.{subj_base} IS NOT NULL AND b.{subj_base} != ''")
            names = [d[0] for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def _isFull(self, key):
        btn = self._ui[key].get("full")
        return btn.isChecked() if btn else False

    def _applyDocMode(self, key):
        """精簡/完整切換：改欄位可見性 + resize 模式。
        精簡：案由/主旨 Stretch 吃滿，其餘 Fixed。
        完整：全欄 Interactive 可拖拉（比照資料庫瀏覽），各欄給初始寬。"""
        table = self._ui[key]["doc"]
        if not table:
            return
        full = self._isFull(key)
        cols = META[key]["cols"]
        for ci, c in enumerate(cols):
            table.setColumnHidden(ci, not (full or c.get("slim")))
        hdr = table.horizontalHeader()
        if full:
            for ci, c in enumerate(cols):
                hdr.setSectionResizeMode(ci, QHeaderView.Interactive)
                table.setColumnWidth(ci, c["w"])
        else:
            stretch_ci = next((i for i, c in enumerate(cols) if c.get("left")), 1)
            for ci, c in enumerate(cols):
                if ci == stretch_ci:
                    hdr.setSectionResizeMode(ci, QHeaderView.Stretch)
                else:
                    hdr.setSectionResizeMode(ci, QHeaderView.Fixed)
                    table.setColumnWidth(ci, c["w"])

    def _onRowSelected(self, key):
        table = self._ui[key]["doc"]
        rows = table.selectionModel().selectedRows() if table else []
        if not rows:
            return
        pos = rows[0].row()
        order = getattr(self, "_docorder", {}).get(key, [])
        doc_id = order[pos] if 0 <= pos < len(order) else None
        if doc_id:
            self._lock(key, doc_id)

    def _lock(self, key, doc_id):
        self._selected[key] = doc_id
        self._rematch(key)

    # ── 選資料夾、掃 PDF（含子資料夾）──────────────────────
    def _pickFolder(self, key):
        # 預設起始路徑＝設定的歸檔根(+刑案/一般子夾)，省得每次手動找
        start = archiveDefaultDir(self.db_path, key)
        folder = QFileDialog.getExistingDirectory(
            self._inner, "選擇 PDF 資料夾", start)
        if not folder:
            return
        self._loadFolder(key, folder)

    def _loadFolder(self, key, folder):
        """掃描資料夾(含子夾)所有 PDF、更新路徑顯示與比對。手動選與自動帶入共用。"""
        self._folders[key] = folder
        pdfs = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(root, f))
        self._pdfs[key] = pdfs
        self._pdfTokCache = {}   # 換資料夾→清斷詞快取
        if self._ui[key]["path"]:
            self._ui[key]["path"].setText(f"{folder}（含子資料夾，共 {len(pdfs)} 個 PDF）")
        self._rematch(key)

    def _autoloadDefault(self, key):
        """進歸檔頁時若尚未選資料夾且已設定歸檔根，自動帶入並掃描（手動選仍可覆蓋）。"""
        if self._folders.get(key):
            return
        d = archiveDefaultDir(self.db_path, key)
        if d and os.path.isdir(d):
            self._loadFolder(key, d)

    # ── 模糊比對 ────────────────────────────────────────────
    def _pdfTokens(self, filepath):
        """PDF 檔名斷詞（快取，檔名不變則不重算）。"""
        cache = getattr(self, "_pdfTokCache", None)
        if cache is None:
            cache = self._pdfTokCache = {}
        toks = cache.get(filepath)
        if toks is None:
            base = os.path.splitext(os.path.basename(filepath))[0]
            toks = _tokenize(base)
            cache[filepath] = toks
        return toks

    def _docTokens(self, doc_fields, keyword):
        """公文欄位 + 關鍵字 的斷詞集合（一次 _rematch 內共用，不必每個 PDF 重算）。"""
        toks = set()
        for v in doc_fields.values():
            if not v:
                continue
            toks |= _tokenize(v)
            toks.add(_trimName(v))
        if keyword:
            for k in keyword.split():
                toks |= _tokenize(k)
        return toks

    def _archivedPKs(self, key):
        """回傳該表『已歸檔』(is_electronic 有值) 的 doc_id 集合，供候選過濾。"""
        meta = META[key]
        conn = self._getConn()
        try:
            return {str(r[0]) for r in conn.execute(
                f"SELECT doc_id FROM {meta['base']} "
                f"WHERE is_electronic IS NOT NULL AND is_electronic != ''")}
        finally:
            conn.close()

    def _initPdfTable(self, key):
        """pdf_table 一次性初始化：樣式 + 欄寬（不走 setupPreviewTable，避開其 200ms autoResize）。"""
        table = self._ui[key]["pdf"]
        if not table:
            return
        table.setColumnCount(3)
        for i, h in enumerate(["操作", "符合", "PDF 檔名"]):
            table.setHorizontalHeaderItem(i, QTableWidgetItem(h))
        hdr = table.horizontalHeader()
        hdr.setSectionsMovable(False)
        hdr.setSectionsClickable(True)
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 68)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        table.setColumnWidth(1, 48)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(30)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setStyleSheet("""
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
                padding: 4px 4px;
                border: none;
                border-bottom: 2px solid #c6c6c8;
                border-right: 1px solid #e5e5ea;
            }
            QTableWidget::item {
                padding: 2px 4px;
                border-bottom: 1px solid #e5e5ea;
            }
            QTableWidget::item:selected {
                background-color: #ccdaeb;
                color: #1c1c1e;
            }
            QTableWidget::item:selected:!active {
                background-color: #d1d1d6;
                color: #1c1c1e;
            }
            QTableWidget::item:hover { background-color: transparent; }
        """)
        # 整排 hover
        table.viewport().setMouseTracking(True)
        hf = RowHoverFilter(table)
        table.viewport().installEventFilter(hf)
        table._hover_filter = hf          # 防 GC
        table.setItemDelegate(RowHoverDelegate(hf, table))

    def _rematch(self, key):
        meta = META[key]
        table = self._ui[key]["pdf"]
        if not table:
            return
        table.setRowCount(0)
        doc_id = self._selected.get(key)
        keyword = (self._ui[key]["kw"].text() or "").strip() if self._ui[key]["kw"] else ""
        # 沒選公文時：若也沒打關鍵字，無從比對 → 清空即可；
        # 有關鍵字 → 仍以關鍵字列出候選，但歸檔預覽鈕禁用（不知歸到哪筆）。
        if not doc_id and not keyword:
            return
        doc = self._docrows.get(key, {}).get(doc_id, {}) if doc_id else {}
        doc_fields = {c: doc.get(c) for c in meta["match_cols"]} if doc_id else {}

        # doc 斷詞只算一次（原本每個 PDF 重算，是頓的主因之一）
        doc_toks = self._docTokens(doc_fields, keyword)
        # 候選過濾：預設「未歸檔」模式時，排除檔名 PK 已歸檔的 PDF
        show_all = self._ui[key].get("pdf_all") and self._ui[key]["pdf_all"].isChecked()
        archived = set() if show_all else self._archivedPKs(key)

        scored = []
        for fp in self._pdfs.get(key, []):
            if archived and (pk := _pkOf(fp)) and pk in archived:
                continue
            common = {c for c in (doc_toks & self._pdfTokens(fp)) if len(c) >= 2}
            scored.append((len(common), fp))
        scored.sort(key=lambda x: -x[0])

        # 大量列時關閉即時排序/更新，建好再開，加速
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        for score, fp in scored:
            pos = table.rowCount()
            table.insertRow(pos)
            # 0=操作
            cont = QWidget()
            hl = QHBoxLayout(cont)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.setSpacing(4)
            hl.setAlignment(Qt.AlignCenter)
            b_open = QPushButton()
            b_open.setIcon(QIcon(":/icon_pdf.svg"))
            b_open.setIconSize(QSize(20, 20))
            b_open.setFixedSize(28, 28)
            b_open.setToolTip("開啟 PDF 檢視")
            b_open.setStyleSheet("QPushButton{border:1px solid #c6c6c8;border-radius:6px;background:#fff;}"
                                 "QPushButton:hover{background:#eaf1f8;}")
            b_open.clicked.connect(lambda _, p=fp: self._openPdf(p))
            b_pick = QPushButton()
            b_pick.setIcon(QIcon(":/icon_archive.svg"))
            b_pick.setIconSize(QSize(20, 20))
            b_pick.setFixedSize(28, 28)
            if doc_id:
                b_pick.setToolTip("歸檔預覽")
                b_pick.clicked.connect(lambda _, k=key, d=doc_id, p=fp: self._selectPdf(k, d, p))
            else:
                b_pick.setToolTip("請先於左側選擇待歸檔公文")
                b_pick.setEnabled(False)
            b_pick.setStyleSheet("QPushButton{border:1px solid #c6c6c8;border-radius:6px;background:#fff;}"
                                 "QPushButton:hover{background:#eaf1f8;}"
                                 "QPushButton:disabled{background:#f2f2f7;}")
            hl.addWidget(b_open)
            hl.addWidget(b_pick)
            table.setCellWidget(pos, 0, cont)
            # 1=符合
            si = QTableWidgetItem(f"{score}字" if score > 0 else "無")
            si.setTextAlignment(Qt.AlignCenter)
            table.setItem(pos, 1, si)
            # 2=檔名
            ni = QTableWidgetItem(os.path.basename(fp))
            ni.setToolTip(fp)
            table.setItem(pos, 2, ni)
        table.setUpdatesEnabled(True)

    def _parseSubject(self, old_path):
        """從舊檔名拆主旨。支援兩種格式：
        (1) 已格式化「PK-日期-主旨-人名」：以 - 分段，去開頭純數字段＋結尾人名段，中間為主旨。
        (2) 實務候選檔「日期+主旨(人名)」(無 -)：去開頭日期(連續數字，含西元/民國)，
            再從尾端剝除人名區（比照 _resolveNames 規則），剩下即主旨。
        拆不到回空字串（呼叫端會退用 DB 主旨）。"""
        base = os.path.splitext(os.path.basename(old_path))[0]
        # 遮罩車牌連字號（MQM-1763、822-NHS 等）前，先保護開頭的（PK-）日期：
        # 否則日期尾數字會和後方車牌頭被遮罩規則連起來（如 1150617-MQM、1150617-822
        # 被當車牌），反吃掉日期與車牌間分隔。只對日期之後做遮罩，組完再還原。
        m = _HEAD_DATE_RE.match(base)
        head = base[:m.end()] if m else ""
        base = head + _maskPlateDash(base[m.end():] if m else base)
        unmask = lambda s: s.replace(_PLATE_SENT, "-")

        # 格式 (1)：含 - 分隔 → 沿用原分段邏輯
        if re.search(r"[-－]", base):
            segs = [s.strip() for s in re.split(r"[-－]", base) if s.strip()]
            if not segs:
                return ""
            i = 0
            while i < len(segs) and re.fullmatch(r"\d+", segs[i]):
                i += 1
            j = len(segs)
            # 只有「最後一段的開頭詞本身是人名」才視為人名段移除。
            # 開頭詞 = 末段以括號/頓號切出的第一片；若開頭是主旨（如
            # 「NXK-1252匿名竊盜(馬佐)」承辦黏在括號內、無 -人名段），
            # 開頭詞為長案由非人名 → 不移除，避免把主旨整段砍掉成空。
            if len(segs) > 1:
                nd = self._loadNameDict()
                head_tok = next(
                    (t for t in re.split(r"[、,，（）()]+", segs[-1]) if t.strip()), "")
                if head_tok and (len(head_tok) <= 3 or head_tok in nd):
                    j -= 1
            mid = segs[i:j]
            # 日期可能與主旨黏在同一段（如「1150617陳若蘭詐欺」非純數字、逃過上面 i 迴圈），
            # 剝掉首段開頭日期，否則最終檔名會「日期-日期主旨」重複日期。
            if mid:
                mid[0] = re.sub(
                    r"^\s*(?:1\d{2}|20\d{2})[-.\/]?\d{1,2}[-.\/]?\d{1,2}",
                    "", mid[0]).strip()
                mid = [m for m in mid if m]
            return self._stripStaffParen(unmask("、".join(mid))) if mid else ""

        # 格式 (2)：無 - → 去開頭日期 + 去結尾人名
        s = re.sub(r"^\s*(?:1\d{2}|20\d{2})[-.\/]?\d{1,2}[-.\/]?\d{1,2}", "", base)
        if s == base:                      # 開頭非日期格式 → 至少去掉開頭連續數字
            s = re.sub(r"^\s*\d+", "", base)
        name_dict = self._loadNameDict()
        pieces = [p for p in re.split(r"[-－.、，,（）()／/_\s·．]+", s) if p.strip()]
        # 從尾端剝除人名（純數字→停；短片段(<=3)或 DB 有的視為人名；長且非名→停）
        while pieces:
            p = pieces[-1]
            if re.fullmatch(r"\d+", p):
                break
            if len(p) <= 3 or p in name_dict:
                pieces.pop()
            else:
                break
        return self._stripStaffParen(unmask("".join(pieces)))

    def _stripStaffParen(self, subj):
        """主旨尾端括號內若全是承辦/協辦（皆能對到人名字典）則整組去掉；
        對不到（被害人、關係人、窗口地點等不在名單）則保留。"""
        nd = self._loadNameDict()
        m = re.search(r"[（(]([^（）()]*)[）)]\s*$", subj)
        if not m:
            return subj
        parts = [p for p in re.split(r"[、,，/／\s]+", m.group(1)) if p.strip()]
        if parts and all(p in nd for p in parts):
            return subj[:m.start()].strip()
        return subj

    # ── 選定 PDF：把組好的檔名填入可編輯預覽四格（不立即改名）────
    def _selectPdf(self, key, doc_id, filepath):
        meta = META[key]
        doc = self._docrows.get(key, {}).get(doc_id, {})
        self._curPdf[key] = filepath
        u = self._ui[key]
        pk = str(doc.get(meta["id_col"]) or "")
        date = _parseDate(os.path.basename(filepath))
        # 主旨：預設填 PDF 檔名解析出的主旨；拆不到才退用 DB 主旨
        subj = _sanitize(self._parseSubject(filepath) or doc.get(meta["subject_col"]))
        names = self._resolveNames(filepath)
        proc = _sanitize("、".join(names) if names
                         else _trimName(doc.get(meta["processor_col"])))
        # 記住初判預設值，供「還原預設」用
        self._defaults = getattr(self, "_defaults", {})
        self._defaults[key] = {"pk": pk, "date": date, "subj": subj, "proc": proc}
        self._applyDefaults(key)

    def _applyDefaults(self, key):
        u = self._ui[key]
        d = getattr(self, "_defaults", {}).get(key)
        if not d:
            return
        if u["h_pk"]:
            u["h_pk"].setText(d["pk"])
        if u["h_date"]:
            u["h_date"].setText(d["date"])
        if u["h_subj"]:
            u["h_subj"].setText(d["subj"])
        if u["h_proc"]:
            u["h_proc"].setText(d["proc"])
        self._refreshFinal(key)

    def _resetDefault(self, key):
        """還原為選定 PDF 當下的程式初判值。"""
        if getattr(self, "_defaults", {}).get(key):
            self._applyDefaults(key)

    # ── 開啟 PDF（系統預設程式）─────────────────────────────
    def _openPdf(self, filepath):
        if not os.path.exists(filepath):
            msgCritical("開啟失敗", "檔案不存在或已被移動。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))

    # ── 選定歸檔：重新命名 PDF + 寫回 is_electronic ─────────
    # 承辦人別名 / 簡稱對照純走 DB：Ref_Personnel.alias（半形逗號分隔），
    # 於設定頁「人員」維護；本檔不再保留硬編別名表。
    def _loadNameDict(self):
        """從 DB 載入人名字典：{全名: 全名}、{去姓2字: 全名}、{別名: 全名}。
        別名取自 Ref_Personnel.alias（半形逗號分隔）。
        （目前人員去姓後 2 字名皆唯一，可唯一反查。）"""
        if getattr(self, "_name_dict", None) is not None:
            return self._name_dict
        d = {}
        try:
            conn = self._getConn()
            # alias 欄可能尚未套補丁 → 動態偵測，缺欄則退回只讀姓名，
            # 避免「no such column」吞成空字典、害全部人名都對不到。
            has_alias = any(
                r[1] == "alias"
                for r in conn.execute("PRAGMA table_info(Ref_Personnel)"))
            sql = ("SELECT staff_name, alias FROM Ref_Personnel" if has_alias
                   else "SELECT staff_name, NULL FROM Ref_Personnel")
            for raw, alias in conn.execute(sql):
                full = _trimName(raw)
                if not full:
                    continue
                d[full] = full
                if len(full) >= 3:
                    d[full[1:]] = full          # 去姓(後2字)→全名
                for a in (alias or "").split(","):
                    a = a.strip()
                    if a:
                        d[a] = full             # 別名→全名
            conn.close()
        except Exception:
            pass
        self._name_dict = d
        return d

    def _resolveNames(self, old_path):
        """解析舊檔名的人名區並補全名。
        界定人名區：從尾端往前收，純數字(日期/PK)即停；
        短片段(<=3字)一律視為人名；長片段(>=4字)僅在 DB 有時才收，
        否則視為案由、停止。對到 DB 的補全名/別名，對不到原樣保留。
        """
        base = os.path.splitext(os.path.basename(old_path))[0]
        name_dict = self._loadNameDict()
        pieces = [p for p in re.split(r"[-－.、，,（）()／/_\s·．]+", base) if p.strip()]
        picked = []
        for p in reversed(pieces):
            if re.fullmatch(r"\d+", p):         # 純數字 → 離開人名區
                break
            if len(p) <= 3:                      # 短片段 → 人名
                picked.insert(0, p)
            elif p in name_dict:                 # 長片段但 DB 有 → 人名
                picked.insert(0, p)
            else:                                # 長片段且 DB 無 → 案由，停
                break
        out, seen = [], set()
        for p in picked:
            name = name_dict.get(p, p)           # 對到→全名/別名；否則原樣
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def _archivePaperOnly(self, key):
        """只歸紙本：將選定公文標記 is_reported=1，不需 PDF、不寫 is_electronic。
        公文續留未歸檔清單（is_electronic 仍空，等日後補 PDF）。"""
        meta = META[key]
        doc_id = self._selected.get(key)
        if not doc_id:
            msgCritical("尚未選擇", "請先在左側「待歸檔」清單選一筆公文。")
            return
        doc = self._docrows.get(key, {}).get(doc_id, {})
        # 已是紙本歸檔 → 提示無需重複
        if str(doc.get("紙本") or "") == "是":
            msgInfo("已歸紙本", f"公文 {doc_id} 的紙本已標記歸檔。")
            return
        subj = doc.get(meta["match_cols"][0]) if meta.get("match_cols") else ""
        kind = "刑案" if key == "crim" else "一般"
        if not confirmBox(
                "只歸紙本",
                f"將{kind}編號 {doc_id} 標記為「紙本已歸檔」：\n\n"
                f"{subj or ''}\n\n"
                f"此操作不需 PDF，公文仍留在清單等待補電子檔。",
                confirm_text="標記紙本", default_confirm=True):
            return
        # 送出確認 → 清空編號搜尋（避免操作後列表停在過濾狀態）
        self._clearDocSearch(key)
        try:
            conn = self._getConn()
            conn.execute(
                f"UPDATE {meta['base']} SET is_reported=1 WHERE doc_id=?",
                (doc_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            msgCritical("寫入資料庫失敗", str(e))
            return
        msgInfo("完成", f"公文 {doc_id} 已標記紙本歸檔。")
        # 差異更新該頁（案由前出現紙圖示），同步指紋
        self._diffDocs(key)
        self._sigs = getattr(self, "_sigs", {})
        try:
            self._sigs[key] = self._tableSignature(key)
        except Exception:
            pass

    def _doArchive(self, key):
        """確認歸檔：用『可編輯預覽四格』目前的值組檔名，重新命名 PDF + 寫回 is_electronic。"""
        meta = META[key]
        u = self._ui[key]
        old_path = self._curPdf.get(key)
        if not old_path:
            msgCritical("尚未選定", "請先在 PDF 候選清單點「選定」。")
            return
        if not os.path.exists(old_path):
            msgCritical("歸檔失敗", "選定的 PDF 不存在或已被移動，請重新比對。")
            return

        pk = (u["h_pk"].text() or "").strip() if u["h_pk"] else ""
        if not pk:
            msgCritical("缺少系統號碼", "預覽的系統號碼(PK)為空，無法歸檔。")
            return
        date = _sanitize((u["h_date"].text() or "").strip()) if u["h_date"] else ""
        subj = _sanitize((u["h_subj"].text() or "").strip()) if u["h_subj"] else ""
        proc = _sanitize((u["h_proc"].text() or "").strip()) if u["h_proc"] else ""
        parts = [p for p in [pk, date, subj, proc] if p]
        new_name = "-".join(parts) + ".pdf"
        new_path = os.path.join(os.path.dirname(old_path), new_name)

        kind = "刑案" if key == "crim" else "一般"
        if not confirmBox(
                "確認歸檔",
                f"歸檔{kind}編號 {pk}：\n\n"
                f"原檔名：{os.path.basename(old_path)}\n"
                f"新檔名：{new_name}\n\n"
                f"確認後將重新命名檔案並記錄為已歸檔。",
                confirm_text="歸檔", default_confirm=True):
            return
        # 送出確認 → 清空編號搜尋
        self._clearDocSearch(key)

        # 1) 重新命名實體檔案
        try:
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
                msgCritical("歸檔失敗", f"目標檔名已存在：\n{new_name}")
                return
            os.rename(old_path, new_path)
        except Exception as e:
            msgCritical("重新命名失敗", str(e))
            return

        # 2) 寫回 is_electronic = 新檔名
        try:
            conn = self._getConn()
            conn.execute(
                f"UPDATE {meta['base']} SET is_electronic=? WHERE doc_id=?",
                (new_name, pk))
            conn.commit()
            conn.close()
        except Exception as e:
            try:
                os.rename(new_path, old_path)   # DB 失敗→還原檔名
            except Exception:
                pass
            msgCritical("寫入資料庫失敗", str(e))
            return

        msgInfo("歸檔完成", f"公文 {pk} 已歸檔。\n檔名：{new_name}")
        # 該 PDF 已改名；該筆已歸檔 → 重載未歸檔清單、清空預覽、重新比對
        self._pdfs[key] = [
            new_path if p == old_path else p for p in self._pdfs.get(key, [])
        ]
        self._curPdf[key] = None
        self._selected[key] = None
        for fld in ("h_pk", "h_date", "h_subj", "h_proc"):
            if u[fld]:
                u[fld].setText("")
        self._refreshFinal(key)
        self._loadDocs(key)
        self._rematch(key)
        # 同步指紋，避免切走再回來時重複重載
        self._sigs = getattr(self, "_sigs", {})
        try:
            self._sigs[key] = self._tableSignature(key)
        except Exception:
            pass

    # ── 框架掛鉤 ────────────────────────────────────────────
    def get_tables(self):
        out = []
        for k in ("crim", "gen"):
            t = self._ui.get(k, {}).get("doc")
            if t:
                out.append(t)
        return out

    def _tableSignature(self, key):
        """未歸檔資料指紋：(未歸檔筆數, MAX(last_modified))。
        別頁增/修/刪 或本頁歸檔都會改變，據此判斷是否需重載清單。
        排除已軟刪除空殼，與 _queryUnarchived 條件一致。"""
        meta = META[key]
        subj_base = "subject_summary" if key == "crim" else "subject"
        conn = self._getConn()
        try:
            row = conn.execute(
                f"SELECT COUNT(*), MAX(last_modified) FROM {meta['base']} "
                f"WHERE (is_electronic IS NULL OR is_electronic = '') "
                f"AND {subj_base} IS NOT NULL AND {subj_base} != ''"
            ).fetchone()
        finally:
            conn.close()
        return (row[0], row[1])

    def _applyGate(self, _role=None):
        """依身分切換權限牆：admin → 內容頁，其餘 → 提示頁。"""
        stack = getattr(self, "_outer_stack", None)
        if stack:
            is_admin = AuthManager.instance().is_admin()
            stack.setCurrentIndex(1 if is_admin else 0)
            # 登入成為管理者（即使正停在本頁）也自動帶入歸檔根
            if is_admin and hasattr(self, "_folders"):
                for key in ("crim", "gen"):
                    self._autoloadDefault(key)

    def on_activated(self):
        self._applyGate()
        self._updateArchWarn()
        # 切換進來時，比對未歸檔資料指紋；變了才做「差異更新」（只動變動列，不重建整表）。
        if not hasattr(self, "_sigs"):
            self._sigs = {}
        for key in ("crim", "gen"):
            if not self._ui.get(key, {}).get("doc"):
                continue
            try:
                sig = self._tableSignature(key)
            except Exception:
                self._loadDocs(key)
                continue
            if self._sigs.get(key) != sig:
                self._diffDocs(key)        # 差異更新
                self._sigs[key] = sig

        # 自動帶入歸檔根資料夾（尚未選擇時顯示名稱並掃描），手動選仍可覆蓋
        if AuthManager.instance().is_admin():
            for key in ("crim", "gen"):
                self._autoloadDefault(key)
