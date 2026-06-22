# 公文管理系統

Windows 桌面應用，PySide6 + SQLite，管理警察單位公文（交辦單、刑案陳報、一般陳報）。

---

## 0. 給接手者

協作規定與偏好見 [CLAUDE.md](CLAUDE.md)（Claude 開新對話時會自動載入）。

---

## 1. 架構心智模型

### 進入點與流程

```
main.py
  └─ loading_screen（載入 .ui、註冊 qrc）
      └─ MainMenu（主選單，選要進哪個 Tab）
          └─ DocumentManager（主視窗，建立 7 個 Tab）
```

- `DocumentManager.TAB_CLASSES` 是 `{index: TabClass}` 的字典，新增 Tab 在這裡登記
- 每個 Tab 繼承 `BaseTab`，必須實作 `setup(tab_index)`
- 可 override：`get_tables()`（回傳要 autoresize 的表格）、`get_focus_widget()`（進 Tab 時聚焦的元件）、`on_activated()`（被切到時刷新）

### Tab 結構（共 7 個）

| index | 名稱 | 類別 | Layout |
|-------|------|------|--------|
| 0 | 交辦單發文 | TabDispatch | Layout1 |
| 1 | 交辦單收文 | TabReceive | Layout2 |
| 2 | 公文陳報 | TabReport | Layout3 |
| 3 | 簽收單列印 | TabPrint | Layout4 |
| 4 | 資料庫瀏覽 | TabDBBrowse | Layout5 |
| 5 | 檔案歸檔 | TabArchive | Layout6 |
| 6 | 資料庫設定 | TabSettings | Layout7 |

### 資料流

- **三張主表**：`Document_Task`（交辦）、`Document_Criminal`（刑案）、`Document_General`（一般）
- **三個 View**：`View_Task_Full` 等，JOIN 參照表 + 算狀態，給預覽 / 列印 / 瀏覽用
- **參照表**：人員 / 部門 / 案類 / 案件狀態 / 一般分類（詳見第 6 節）
- 主表存的是參照表的 **ID**（VARCHAR 字串，非真外鍵），顯示時 JOIN 出名稱

### Tab 切換與刷新機制（重要）

`main.py` 的 `_onTabChanged(index)` 是核心調度，做三件事：

1. **從設定 Tab 切走時**：呼叫 `settings_tab._promptUnsaved(context="leave")` 處理未存排序；若 `_ref_dirty=True`，對**其他所有 Tab** 設 `_ref_changed=True` 後呼叫 `on_activated()` 刷新下拉
2. **切到設定 Tab 時**：呼叫 `settings_tab.on_activated()` 重載當前子頁（與 DB 同步）
3. autoresize 表格 + 設定焦點

> ⚠️ **Qt 限制**：`QTabWidget.currentChanged` 是「切換**後**」才發出，無法在切換前攔截詢問「要不要存」。所以「離開大 Tab」的未存提醒只能是「切過去後補跳」，不能攔住不讓切。設定 Tab 內部的子頁切換（按鈕觸發）則攔得住，可以「取消 = 回原狀」。

#### 瀏覽／歸檔頁的三層刷新（避免大表頓挫）

瀏覽頁（Tab4）三表、歸檔頁（Tab5）待歸檔清單各約 700+ 列，重建 cellWidget 才是成本所在。故依「變動性質」分三條路徑：

1. **參照改名（人員／部門／案類）→ 就地輕量更新**：設定頁改過參照表時 `_ref_changed=True`，`on_activated` 走 `_refreshRefCells`（瀏覽）／重載小清單（歸檔），**只對 `ref_col` 標記欄 `setText`，不重建列**（700 列實測 ~20ms）。指紋只看公文表 `last_modified`，碰不到參照改名，故必須走此旗標路徑。
2. **跨頁增／修／刪 → 指紋差異更新**：比對 `(COUNT, MAX(last_modified))`，變了才 `_diffUpdate`／`_diffDocs`，只重建變動列。變動列數 `>= _BUSY_ROW_THRESHOLD`（預設 100）才跳「更新中」提示。
3. **手動「重載」鈕**：瀏覽頁每區塊、歸檔頁每類各一顆，強制整表重建（瀏覽）／重掃資料夾＋重載清單＋重新比對（歸檔），一律以 `runWithBusy` 顯示「更新中」。是使用者面對任何外部變動（如外部新增／改名 PDF）的逃生口。

> 「更新中」提示 `ui_utils.runWithBusy`：同步阻塞工作前 `show + repaint` 強制畫出（frameless 視窗 `processEvents` 不一定即時 repaint），並有最短顯示時間（避免一閃即逝）。

---

## 2. 踩雷速查表

見 [CLAUDE.md](CLAUDE.md)（動手前必掃）。

---

## 3. 慣例與設計決策

### 軟刪除（is_active）

- **人員 / 部門 / 案類**都用 `is_active` 軟刪除（停用，不真刪）。停用後保留 ID 對應（歷史資料仍引用得到），只是不出現在下拉
- 詞彙：人員用「在職 / 離職」，部門 / 案類用「啟用 / 停用」
- 設定 Tab 列表會顯示停用項目（**灰字 `#aeaeb2`**），下拉則排除（`WHERE is_active=1`）
- 停用 / 啟用一律進「修改」Dialog 勾 checkbox 切換，沒有獨立的停用按鈕

### 排序（sort_order）

- 人員 / 部門 / 案類三表有 `sort_order` 欄，**下拉與列表一律 `ORDER BY sort_order`**（不是 ID）
- 目的：讓顯示順序跟 ID 脫鉤，可手動調整（ID 純粹是正規化用的主鍵）
- 設定 Tab 以**拖拉列**調整順序（`_RowDragFilter` 攔 `QEvent.Drop`、手動換列）；hint label 提示可拖。⚠️ `QTableWidget.InternalMove` 只移 cell 不移 row，不可用
- **暫存模式**：排序在記憶體操作，「儲存排序」鈕初始 disabled、拖拉後才亮；儲存才寫回 DB（連續整數重編）並設 `_ref_dirty=True`
- 未存排序時切子頁 / 切大 Tab / 按修改，會跳確認；取消行為：按鈕觸發的（修改、子頁）回原狀，大 Tab（攔不住）放棄
- 新增項目放最前（`MIN-1`）

### 權限（AuthManager，單例）

- SHA-256 密碼存 `App_Settings`，預設 `0000`，標題列顯示 `[一般使用者]`/`[管理者模式]`，閒置 20 分鐘自動登出
- 設定 Tab 需管理者登入；變更密碼為高風險操作，**Enter 不送出**（防誤按），只能滑鼠點

**編輯 popup 權限模型**（點預覽表編號開的彈窗；身分變更時 `_onRolePerm`／`outer_stack` 即時生效）：

| Tab | admin | 一般使用者 |
|-----|-------|-----------|
| 交辦單發文 Tab0 | 全可改（含已發文，編號恆可點） | 只能改承辦人；**已發文禁止編輯** |
| 交辦單收文 Tab1 | 全可改 | 開放輸入錯誤修正、開放刪除 |
| 公文陳報 Tab2（刑案／一般） | 全可改 | 開放輸入錯誤修正、開放刪除 |
| 簽收單列印 Tab3 | 可使用 | 可使用 |
| 資料庫瀏覽 Tab4 | 全可改 | 不開放編輯 |
| 檔案歸檔 Tab5 | 可使用（需管理者登入） | 無法使用 |
| 設定 Tab6 | 可使用（需管理者登入） | 無法使用 |

> 一般使用者限制由 `TaskEditDialog(restricted=…)` 控制（鎖定欄位顯示 DB 原值＋灰 `:disabled` 樣式，儲存只動承辦人）；連結可點與否由各 tab `setDocIdLinkCell(clickable=…)` 控制，身分變更時 `_onRolePerm` 重刷（編號連結＋刪除鈕）。

### 別名（alias）

- 別名是「人的屬性」，存在 `Ref_Personnel.alias` 欄，分隔符為**半形逗號**，多別名同欄（如 `王佐,所長,副座`）
- 否決新表 `Ref_Alias`：別名跟著人走，跨年度重編 id 時 alias 自動保留，無需額外關聯
- 歸檔比對（`lib/archive_text.py`）從 DB 讀別名後與正名一同納入 `_loadNameDict`；移除舊 `tab_archive._ALIAS` hardcode dict
- 欄位由 `fix_views.py` 補丁新增（見 §5「新增 DB 欄位」,v1.0.2）；讀寫前呼叫 `_has_alias_col(conn)` 做 PRAGMA 缺欄退路，避免舊 DB 報錯


### 資料庫瀏覽（Tab4）搜尋設計

**全量載入 + `setRowHidden` 模式**（非搜尋重建表格）：

- `_reload(key)`：DB 全量抓取，所有非軟刪除列全部 `insertRow`，存入 `_allRows[key]`（row dict 列表，與表格列 1:1 對應）+ `_docorder[key]`（doc_id 列表）。**不做關鍵字過濾**
- `_applyFilter(key)`：讀 `_allRows[key]`，對每列計算是否命中當前 kw/scope，結果存 `_matchedCols[key]`，呼叫 `_applyRowVisibility`
- `_applyRowVisibility(key)`：單一 pass，同時考慮搜尋 filter（`_matchedCols`）和逾期篩選（vertical header item `Qt.UserRole`），`setRowHidden` 決定每列可見；最後呼叫 `_updateFooter`
- `_applyOverdue(key)`：僅呼叫 `_applyRowVisibility`（不獨立重算）
- 搜尋框 / 範圍下拉觸發 `_applyFilter`，**不觸發 `_reload`**；`_reload` 只在 Tab 切換且指紋改變時呼叫（或 `_diffUpdate` fallback）

**比對方式**：`kw in str(值)` 的**子字串包含、區分大小寫**（非模糊比對）；選了範圍下拉只比該欄，否則比所有 `search:True` 欄。

**差異更新（`_diffUpdate`）**：查 `last_modified > since` 得到變動 PK；對每筆維護 `_allRows[key]`（append / 就地更新 / pop）、`_docorder[key]`、表格列，最後呼叫 `_applyFilter` 重算可見性。變動列數 `>= _BUSY_ROW_THRESHOLD`（預設 100）時，重建段落以 `runWithBusy` 包起來顯示「更新中」。

**精簡/完整切換**：單顆「完整」切換鈕（`{key}_seg_full`，預設未選＝精簡，與歸檔頁一致）。`_applyMode` 做 `setColumnHidden`，再呼叫 `_applyRowVisibility` 重算 hit_hidden（命中欄在隱藏欄的提示）。

> ⚠️ `_allRows[key]` 和 `_docorder[key]` 必須與表格列嚴格 1:1 對應（索引相同）。`_diffUpdate` 每次 pop / append 時兩者要同步維護，否則 `_applyRowVisibility` 會取到錯誤的 row data。

> ⚠️ `_applyRowVisibility` / 歸檔 `_rematch` 內 `setUpdatesEnabled(False)…(True)` 必須用 **try/finally** 包覆。否則中途丟例外會把表格卡在「不更新」狀態，之後所有 `setRowHidden`（搜尋）在畫面上都無效＝「搜尋完全沒反應」，且持續到下次整表重建。

### 歸檔頁「檔名過濾」（Tab5 候選 PDF）

候選 PDF 區的關鍵字框（`{key}_kw`，標籤「檔名過濾」）做的是**檔名子字串過濾、不分大小寫**：輸入文字 → `_rematch` 只保留 `os.path.basename(fp)` 含該串的 PDF，其餘排除（不是重排、不是斷詞比對）。關鍵字**不**再混入對選定公文的比對分數；評分排序仍照 `match_cols` 斷詞交集計算。觸發為 Enter 或「比對」鈕。

### 其他慣例

- 所有彈窗都加 Enter 確認（高風險操作如變更密碼除外）
- 跨年度會有 **Reset 按鈕**重編所有 ID，所以**不需要** Seq 流水號機制；現有 `Seq_DocId` 等跨年度 Reset 一起歸零
- 主表「刪除」是清空欄位保留 doc_id，流水號永久佔用，彈窗會提示「本文號（XXX）無法再被使用」
- **身分判斷**用 `AuthManager.instance().is_admin()`（等同 `current_role == 'admin'`，勿再各處寫字串比較）
- **DB 連線**統一走 `db_utils.getConn(db_path)`（單一來源，要加 PRAGMA/timeout 集中改一處）；`base_tab._getConn`、`edit_dialog._get_conn` 皆委派它
- 三個編輯彈窗（Task/Criminal/General）共同繼承 `_BaseEditDialog`，集中版面常數 `_LABEL_W/_FIELD_W/_MARGIN`（子類以 `self._LABEL_W` 引用）

---

## 4. 目錄結構

```
專案根/
├── main.py              進入點（從專案根目錄啟動）
├── lib/                 核心模組（被各處 import；含 __init__.py，是 package）
│   ├── db_utils.py      路徑解析 / 通用彈窗 / nextDocId / 跨年度重置（performYearEndReset、listInactiveRefItems）（DEBUG_MODE 在第一行）
│   ├── base_tab.py      BaseTab 基底
│   ├── auth_manager.py  權限單例（`is_admin()` 便捷判斷）
│   ├── archive_text.py  歸檔比對純文字/檔名工具（_tokenize/_parseDate/_pkOf/_sanitize/_trimName；自 tab_archive 抽出，可單測）
│   ├── theme.py         全域 QSS（Apple HIG 風格）
│   ├── version.py       版本號單一來源（__version__；進版只改這裡，主選單顯示自動同步）
│   └── loading_screen.py
├── layouts/             所有 .ui 檔（Layout1~7、main_menu）
├── res/                 圖片 / SVG / qrc（含 __init__.py，是 package）
│   ├── resources.qrc / resources_rc.py
│   ├── arrow.svg / sort_*.svg / banner.png / police_badge.*
│   ├── icon_pdf.svg / icon_archive.svg    ← 歸檔頁操作鈕 Material Icons（灰 #636366）
├── tabs/                各 Tab
└── ui_utils/            共用 UI 工具（table/widgets/status/sticky_scroll/edit_dialog/settings_dialogs）
```

> 核心模組（db_utils、base_tab、auth_manager、theme、loading_screen）在 `lib/`，本文其餘章節為精簡仍以簡稱（如「db_utils」）指稱，實際 import 路徑為 `from lib.db_utils import ...`。`main.py`、`data_sync_tool.py`、`sql.py` 留根目錄（入口與獨立工具，互不 import 核心模組）。

### 路徑解析（getResourcePath，打包相容）

- `db_utils.getResourcePath(rel)`：開發時從當前目錄找，打包後從 `sys._MEIPASS` 找
- `dbfile.db` 特殊：永遠從 exe 所在目錄讀（真實資料，不打包進 exe）
- `.ui` 用 `getResourcePath("layouts/Layout1.ui")`、圖片用 `getResourcePath("res/banner.png")`
- `arrow.svg` / `sort_*.svg` 走 qrc 虛擬路徑 `:/sort_top.svg`，**不經過 getResourcePath**
- ⚠️ `res/` 是 package（有 `__init__.py`），`resources_rc` 用 `from res import resources_rc`
- ⚠️ `lib/` 是 package（有 `__init__.py`），核心模組用 `from lib.db_utils import ...` 等
- ⚠️ `getResourcePath` 用「當前工作目錄」（`os.path.abspath('.')`）找 dbfile.db，**不是** `__file__`，所以 **程式務必從專案根目錄啟動**（`python main.py`），打包後則是 exe 所在目錄
- ⚠️ 改了任何 qrc 內的 SVG，要重編：`cd res && pyside6-rcc resources.qrc -o resources_rc.py`

---

## 5. 操作手冊（要改特定東西時查）

### 新增 DB 欄位

本專案**不做啟動 migration**（單機、版本由維護者自管，migration 的價值皆不成立）。DB 結構變更走**一次性手打補丁 `fix_views.py`**（不進 git）：

1. 在 `fix_views.py` 的 `_NEW_COLUMNS` dict 登記要新增的欄位，腳本執行後自動 `ALTER TABLE ... ADD COLUMN`
2. 程式碼讀寫新欄位前用 **PRAGMA 缺欄退路**保護，確保套補丁前的舊 DB 不會報錯：

```python
def _has_alias_col(conn):
    """欄位是否存在（fix_views 套用後才有）。未套補丁時跳過讀寫。"""
    return any(r[1] == "alias"
               for r in conn.execute("PRAGMA table_info(Ref_Personnel)"))
```

3. `fix_views.py` 同時負責重建 View（`DROP VIEW IF EXISTS … CREATE VIEW …`）；View 定義若有更動，一律更新此檔而非在啟動時跑 DDL

> **上線流程**：維護者在本機執行 `python fix_views.py` 一次即可；打包 exe 無需感知此補丁存在。

### 新增 Tab 的標準流程

1. 新增 `tabs/tab_xxx.py`，`class TabXxx(BaseTab)` 實作 `setup(tab_index)`
2. `tabs/__init__.py` 加 `from .tab_xxx import TabXxx`
3. `main.py` 的 `TAB_CLASSES` 登記一行（其餘不動）
4. 新增對應 `layouts/LayoutN.ui`（**每個大 Tab 都必須有 .ui，無例外**；彈窗 / Dialog 才用 code 動態建。註：TabSettings 目前違反此規則、待修，見第 8 節）
5. 若有人員/部門/案類下拉，override `on_activated()` 刷新（範例見下）

```python
def on_activated(self):
    personnel, depts = self._loadRef()
    refreshFilterCombo(self.combo_processor, personnel)
    refreshFilterCombo(self.combo_dept, depts)
```

- 沒下拉的 Tab 不用 override（預設空方法）
- `refreshFilterCombo` 保留當前選值，值已不存在（如人員離職）則清空
- 觸發：從設定 Tab 切出 + `_ref_dirty=True`

> ⚠️ **預覽表名稱不會自動跟 rename 更新**：預覽表存「當下抓的字串」，使用者 rename 後會顯示舊名。現有 Tab 都已實作刷新（`tab_dispatch._refreshPreviewNames()` 等），新 Tab 若預覽表有參照表字串欄位，必須仿照寫刷新方法並在 `on_activated()` 末尾呼叫。

### .ui 撰寫規則

見第 2 節踩雷表前兩條（margin 四獨立 property、centralwidget 全小寫）。

### 新增 UI 元件注意

- 所有新 `QDialog`/`QWidget` 明確設背景色 + 文字色（見下）
- 字體 14pt、縮放 125%，算寬度基準：全型字 `24×1.8=43px`、半型 `24×0.65=16px`、ComboBox/DateEdit 加 36px、CheckBox indicator 25px

```python
self.setStyleSheet("""
    QDialog, QWidget { background-color: #FFFFFF; color: #000000; }
    QLineEdit, QComboBox, QDateEdit {
        background-color: #FFFFFF; color: #000000;
        border: 1px solid #CCCCCC; border-radius: 4px; padding: 4px 8px;
    }
    QCheckBox, QRadioButton, QLabel { color: #000000; }
""")
```

> dialog stylesheet 的 `QDateEdit` 是 `border-radius: 4px`，主視窗 theme.py 是 `8px`。

### ui_utils 擴充規則

| 需求 | 做法 |
|------|------|
| 新欄位固定寬度 | `table.py` 的 `FIXED_COL_WIDTHS` 加一行 |
| 同名欄位不同表格不同寬度 | `fixed_overrides` 參數傳入 |
| 欄位寬度隨內容縮、卡上限 | `cap_mode=True` |
| 新狀態顏色 | `status.py` 的 `colorForStatus` 加條件，回 `QColor("#hex")` |
| 新元件行為 | `widgets.py` 新增函式 + `__init__.py` export |
| 身分變更重設刪除鈕（greyout/還原） | `table.py` 的 `refreshDeleteBtns(table, enabled, col=0)` |
| 表格整排 hover 反白 | `widgets.py` 的 `RowHoverFilter` + `RowHoverDelegate`（自 tab_archive 抽出，通用） |
| 可空白日期欄、月曆打開停在今天 | `widgets.py` 的 `setupDateEditCalendarOnly(dateedit)`（搭 `setSpecialValueText(" ")` ＋設 minimumDate 當空白哨兵；過濾器裝 calendarWidget，見 §2 雷） |
| 固定 N 行、超長尾端省略的標籤 | `widgets.py` 的 `TwoLineElideLabel`（固定 2 行高、第 2 行尾 `…`、完整內容入 tooltip；建構後以 `actions.replaceWidget(舊label, 新)` 換掉 .ui 的 QLabel） |
| 預覽表黏底捲動 | `setupPreviewTable` 後呼叫 `attachStickyScroll(table)` |

### 通用彈窗（db_utils）

```python
from db_utils import msgInfo, msgWarning, msgCritical, confirmBox
```

| 函式 | 按鈕 |
|------|------|
| `msgInfo / msgWarning / msgCritical(title, text)` | 確定 |
| `confirmBox(title, text, confirm_text, cancel_text, confirm_danger, default_confirm)` | 自訂，回傳 True=確認 |

### 修改功能（EditDialog）

- 在 `ui_utils/edit_dialog.py`，動態產生表單，不用 .ui
- `TaskEditDialog`（Tab0/1）、`CriminalEditDialog`（Tab2 刑案）、`GeneralEditDialog`（Tab2 一般）
- 觸發：點預覽表編號欄超連結
- 三彈窗共同繼承 `_BaseEditDialog`，版面常數集中於基底：`_LABEL_W=120` / `_FIELD_W=340` / `_MARGIN=40`，`setMinimumWidth = LABEL_W+FIELD_W+MARGIN = 580`
- 刪除列後需重新綁定刪除鈕與編號 QLabel 的 row index（參考 `_rebindDocIdCell`）
- **歸檔狀態區塊（僅 admin）**：`CriminalEditDialog`/`GeneralEditDialog` 表單末端、儲存鈕上方有「歸檔狀態」分組框（`_build_archive_group`；dbbrowse 與 archive 兩頁共用同一 dialog，一改兩頁生效）。紙本 `is_reported` 用 checkbox 雙向可勾消；電子檔 `is_electronic` 只能「清除」（popup 產不出 PDF，故僅提供退回未歸，清空後該筆自動回歸檔頁待歸清單），不動實體 PDF（留孤兒檔，重歸時 rename 覆蓋）。長檔名用 `_ElidingLabel`（`ElideMiddle` 隨寬度中段省略）不撐破版面。清除為標記 pending，按「儲存」才真寫 `is_electronic=''`、取消（reject）則還原；儲存同時寫回 `is_reported`。非 admin 不建立區塊（`self.w_arch_reported=None`，save 跳過這兩欄）

### tab_report.py 特殊架構

- `Layout3.ui` 用 `QStackedWidget`（`formStack`）切換：index 0 刑案、index 1 一般
- 發文分類 radio 對應：刑案 `radio_status_a/b/c` → CS01/CS02/CS03；一般 `radio_gen_cat_a/b/c` → GC01/GC03/GC02
- ⚠️ **預覽顯示 ≠ DB 值**（明年大修資料庫要一起改）：

| 項目 | 預覽 | DB |
|------|------|-----|
| 刑案狀態 | 現行/到案/未到 | A_現行犯/B_到案/B_未到案 |
| 一般分類 | 業務/其他/相驗 | D_業務陳報/J_其他/F_司法相驗 |
| 人名 | 王小明 | 王小明-19.06（去 `-` 後綴） |
| 日期 | MM-DD-YYYY | YYYY-MM-DD |

> EditDialog 刷新時 `get_updated()` 回的是 DB 原始值，刷新表格前要轉換：刑案經 `_STATUS_MAP`（`_onEditCrimRow`）、一般經 `_CAT_MAP`（`_onEditGenRow`）。

### 列印（tab_print.py）

- 用 **`QPrintPreviewDialog`**（PySide6.QtPrintSupport）跳原生預覽 + 列印選項視窗
- 不碰 PDF 檔案關聯（避免 WinError 1155），頁面以 **300 DPI 點陣化**送印（`_paint_pages` 把 PNG 畫到 QPrinter）
- 「儲存 PDF」按鈕仍走 matplotlib `backend_pdf`（向量），與列印獨立
- 跨版本相容：`setPageSize` 用 `QPageSize` 物件、頁面範圍用 `painter.viewport()`（避開 6.x enum 命名空間差異）

### 跨年度重置（Reset，tab_settings.py）

位置：設定 Tab 左側 nav 底部「跨年度重置」鈕（紅字，管理者登入後才可操作）。屬**破壞性操作**。

執行流程（`_doReset()`）：
1. 開 `ResetDialog`（`ui_utils/settings_dialogs.py`）：列出本次將被清除的停用項目、要求手動輸入 `RESET`、防誤按（確認鈕非 default、輸入框不綁 Enter，沿用變更密碼那套）
2. **自動備份**：複製 `dbfile.db` → 同目錄 `dbfile_backup_YYYYMMDD_HHMMSS.db`；備份失敗則中止
3. 詢問是否**另存**一份至使用者指定位置（可略過）
4. 執行 `performYearEndReset()`（`lib/db_utils.py`）：單一 transaction，失敗 rollback
5. 完成提示 → `_restartApp()` 重啟程式

`performYearEndReset()` 重置內容：
- 清空三張主表（Document_Task / Criminal / General）
- **刪除**停用（is_active=0）項目（決策：跨年度時順便清掉，dialog 會事前列出讓使用者有機會先啟用保留）
- 依 sort_order **重編參照表 id**（連續，維持原前綴與位數，如 P01/D01/CT01）
- sort_order 重設為連續整數
- 歸零 Seq_DocId
- **清空歸檔根目錄設定**（`App_Settings` 的 `archive_root`/`archive_subdir_crim`/`archive_subdir_gen`）— 強制使用者在新年度重新指定歸檔路徑

重編 id 採**兩段式**避主鍵衝突：先把所有列改成暫時前綴（`__TMP__P0001`...），再編回正式 id。**別改成單段直接 UPDATE**，舊新 id 集合有交集會撞 PRIMARY KEY。

### 歸檔根目錄未設定警示

重置後（或首次安裝）歸檔根目錄為空，程式有三層提醒：

1. **瀏覽 Tab4**（`on_activated`）：刑案 / 一般篩選列右側顯示紅字「⚠ 歸檔資料夾未設定，請至設定頁更新」
2. **歸檔 Tab5**（`on_activated` / `_onShown`）：刑案 / 一般資料夾列右側同上紅字
3. **設定 Tab6**（`on_activated`，每次登入首次進入）：彈一次確認框詢問是否立即前往「歸檔資料夾」設定（`_arch_warn_shown` flag 控制，重新登入後重置）

切到 Tab4/5 時每次都檢查；設定頁每次登入只跳一次。

---

重啟（`_restartApp()`）：見第 2 節踩雷表 `_MEI` 條。**打包版啟動新程序前必設 `PYINSTALLER_RESET_ENVIRONMENT=1`**（PyInstaller 6.10+ 官方重啟機制），否則新程序沿用舊 `_MEI` 環境、載入已刪除的 DLL 而崩潰。重置後資料全變（id、主表清空），故用整個程序重啟取代逐一刷新 Tab，最乾淨。

---

## 6. 資料庫結構

### Document_Task（交辦單）

| 欄位 | 型態 | 說明 |
|------|------|------|
| doc_id | VARCHAR(50) | PK 流水號 |
| receive_date | DATE | 收文日期（NULL = 已刪除） |
| receive_id | VARCHAR(10) | 收文人員 → Ref_Personnel |
| dept_id | VARCHAR(10) | 業務組 → Ref_Departments |
| subject | TEXT | 交辦事由 |
| processor_id | VARCHAR(10) | 承辦人 → Ref_Personnel |
| deadline | DATE | 限辦日期（NULL = 免覆） |
| dispatch_date | DATE | 發文日期（NULL = 未發） |
| sender_id | VARCHAR(10) | 送文人員 → Ref_Personnel |
| timestamp | DATETIME | 紀錄時間 |

### Document_Criminal（刑案陳報）

| 欄位 | 型態 | 說明 |
|------|------|------|
| doc_id | VARCHAR(50) | PK 流水號 |
| report_date | DATE | 陳報日期（NULL = 已刪除） |
| sender_id | VARCHAR(10) | 發文人員 → Ref_Personnel |
| case_type | VARCHAR(10) | 案件分類 → Ref_CaseTypes |
| case_status | VARCHAR(10) | 發文分類 → Ref_Case_Status |
| processor_id | VARCHAR(10) | 承辦人員 → Ref_Personnel |
| subject_summary | TEXT | 陳報主旨 |
| occurrence_date | DATE | 查獲/受理日期 |
| reporter_name | VARCHAR(50) | 報案人（純文字） |
| receiver_id | VARCHAR(10) | 受理人員 → Ref_Personnel |
| is_reported | BOOLEAN | 紙本（稽核用，預設 0） |
| is_electronic | TEXT | 電子檔歸檔狀態：空字串 = 未歸，填檔名 = 已歸（稽核用，預設 ''） |

### Document_General（一般陳報）

| 欄位 | 型態 | 說明 |
|------|------|------|
| doc_id | VARCHAR(50) | PK 流水號 |
| report_date | DATE | 陳報日期（NULL = 已刪除） |
| sender_id | VARCHAR(10) | 發文人員 → Ref_Personnel |
| dept_id | VARCHAR(10) | 業務單位 → Ref_Departments |
| gen_cat_id | VARCHAR(10) | 發文分類 → Ref_General_Category |
| subject | TEXT | 陳報主旨 |
| processor_id | VARCHAR(10) | 承辦人 → Ref_Personnel |
| is_reported | BOOLEAN | 紙本（稽核用，預設 0） |
| is_electronic | TEXT | 電子檔歸檔狀態：空字串 = 未歸，填檔名 = 已歸（稽核用，預設 ''） |

### 參照表

| 資料表 | 欄位 |
|--------|------|
| Ref_Personnel | staff_id / staff_name / **alias** / is_active / **sort_order** |
| Ref_Departments | dept_id / dept_name / **is_active** / **sort_order** |
| Ref_CaseTypes | case_type_id / case_type_name / **is_active** / **sort_order**（52 種） |
| Ref_Case_Status | status_id / status_name（CS01~CS03，程式 hardcode，不動） |
| Ref_General_Category | gen_cat_id / gen_cat_name（GC01~GC03，程式 hardcode，不動） |
| Seq_DocId | table_name / last_id（nextDocId() 維護，年底 Reset 歸零） |

### Views

| View | 說明 |
|------|------|
| View_Task_Full | 含狀態判斷（剩餘天數/逾期/已發文，DB 端算） |
| View_Criminal_Full | JOIN 所有參照表，案類 COALESCE 舊資料 |
| View_General_Full | JOIN 所有參照表 |

---

## 7. 打包（PyInstaller 6.20.0）

### 主程式

```cmd
del /q Police-Document-Manager.spec 2>nul & rmdir /s /q build dist 2>nul & pyinstaller --clean --onefile --windowed --icon=res/police_badge.ico ^
  --version-file version_info.txt ^
  --add-data "layouts/*.ui;layouts" ^
  --add-data "res/police_badge.svg;res" ^
  --add-data "res/banner.png;res" ^
  --hidden-import PySide6.QtPrintSupport ^
  --hidden-import lib.db_utils ^
  --hidden-import lib.base_tab ^
  --hidden-import lib.auth_manager ^
  --hidden-import lib.theme ^
  --hidden-import lib.loading_screen ^
  --hidden-import lib.version ^
  --hidden-import lib.archive_text ^
  --hidden-import res.resources_rc ^
  --exclude-module matplotlib.backends.backend_cairo ^
  --exclude-module matplotlib.backends.backend_gtk3 ^
  --exclude-module matplotlib.backends.backend_gtk3agg ^
  --exclude-module matplotlib.backends.backend_gtk3cairo ^
  --exclude-module matplotlib.backends.backend_gtk4 ^
  --exclude-module matplotlib.backends.backend_gtk4agg ^
  --exclude-module matplotlib.backends.backend_gtk4cairo ^
  --exclude-module matplotlib.backends.backend_macosx ^
  --exclude-module matplotlib.backends.backend_nbagg ^
  --exclude-module matplotlib.backends.backend_pgf ^
  --exclude-module matplotlib.backends.backend_ps ^
  --exclude-module matplotlib.backends.backend_qt ^
  --exclude-module matplotlib.backends.backend_qt5 ^
  --exclude-module matplotlib.backends.backend_qt5agg ^
  --exclude-module matplotlib.backends.backend_qt5cairo ^
  --exclude-module matplotlib.backends.backend_qtagg ^
  --exclude-module matplotlib.backends.backend_qtcairo ^
  --exclude-module matplotlib.backends.backend_svg ^
  --exclude-module matplotlib.backends.backend_template ^
  --exclude-module matplotlib.backends.backend_tkagg ^
  --exclude-module matplotlib.backends.backend_tkcairo ^
  --exclude-module matplotlib.backends.backend_webagg ^
  --exclude-module matplotlib.backends.backend_webagg_core ^
  --exclude-module matplotlib.backends.backend_wx ^
  --exclude-module matplotlib.backends.backend_wxagg ^
  --exclude-module matplotlib.backends.backend_wxcairo ^
  --exclude-module tkinter ^
  --name Police-Document-Manager main.py
```

### 注意事項

- `dbfile.db` 不打包，與 exe 同資料夾（真實資料）
- `arrow.svg` / `sort_*.svg` / `icon_pdf.svg` / `icon_archive.svg` 已透過 `resources_rc.py` 內嵌，不需 `--add-data`；改了要重編 qrc
- 列印用 `QtPrintSupport`，加 `--hidden-import PySide6.QtPrintSupport` 保險
- matplotlib 只用 `backend_agg`（PNG）+ `backend_pdf`（存 PDF），其餘 backend 全排除
- 結構重組後 `.ui` 進 `layouts/`、圖片進 `res/`，`--add-data` 路徑要對應第二參數（解壓目標目錄）
- 指令開頭 `del ...spec & rmdir build dist` 是刻意的：開發期不信任殘留 spec（會用到上次的過期設定），每次砍掉 spec / build / dist 用乾淨 CLI 參數全新生成。`2>nul` 讓首次執行（檔案不存在）不報錯
- **跨年度重置的自動重啟**：onefile 版重啟新程序前必設環境變數 `PYINSTALLER_RESET_ENVIRONMENT=1`（PyInstaller 6.10+ 官方機制），否則新程序沿用舊 `_MEI` 環境、到已刪除的暫存目錄找 `python3xx.dll`/標準庫而崩潰（`Failed to load Python DLL` / `unicodedata` 缺失）。`_restartApp()` 已處理。詳見第 2 節踩雷表與第 5 節 Reset 子節
- 若打包後報 `No module named res`，加 `--hidden-import res.resources_rc`
- 核心模組在 `lib/`，主程式打包已列 `--hidden-import lib.*` 七個（含 `lib.archive_text`）；若仍報 `No module named lib.xxx`，補對應的 hidden-import
- GitHub release 上傳用英文檔名
- **exe 檔案資訊（右鍵→內容→詳細資料）**：由 `--version-file version_info.txt` 帶入。`version_info.txt` 不在 build 時生成，而是**進版時由 `bump_version.py` 連同版號一起產生**（見 §8 進版），已收進 git。打包只需引用、不用多做。要改顯示文字（公司/產品名）改 `bump_version.py` 頂部常數

---

## 8. 版本記錄

> 版本號單一來源為 `lib/version.py` 的 `__version__`。**進版一律用 `python bump_version.py <版號>`**（版號自帶，不自動進位；執行前會先印出目前版號），它會同時改 `version.py` 與產出 `version_info.txt`（exe 檔案資訊）；標題列與主選單顯示自動同步。本表與 git tag（`v{__version__}`）需手動對齊。⚠️ 勿手改 `version.py`，否則 `version_info.txt` 不同步。

| 版本 | 摘要 |
|------|------|
| v1.0.4 | 瀏覽頁／歸檔頁新增「重載」鈕（強制重掃資料夾＋整表重建）；設定頁改參照表名稱後，瀏覽／歸檔頁自動就地反映（零重建成本）；重載與大量差異更新顯示「更新中」提示；歸檔頁「自訂關鍵字」改為檔名過濾（只留符合的 PDF）；搜尋畫面更新改 try/finally 避免凍結；瀏覽頁精簡／完整改單顆切換鈕（預設精簡）。歸檔檔名解析強化（黏連日期、車牌連字號、承辦括號）。 |
| v1.0.3 | 公文陳報頁（Tab3）改版：刑案／一般陳報合併為單一表單版面，切換時欄位位置、寬度、高度一致不跳動；下方左右預覽表高度對齊；輸入欄與下拉欄高度統一；案件分類／查獲受理日期灰字不再影響下拉清單與月曆。 |
| v1.0.2 | 設定頁拖拉排序（移除四顆排序鈕）；人員別名欄（`Ref_Personnel.alias`，歸檔比對一併納入）；歸檔根目錄未設定三層警示；瀏覽 Tab4 搜尋改為全量載入＋`setRowHidden`，大幅提升搜尋速度。 |
| v1.0.1 | 人員別名初版（alias 欄）；設定頁人員清單加別名欄；歸檔比對從 DB 讀取別名。 |
| v1.0.0 | 正式版。瀏覽頁（Tab4）有歸檔檔名者顯示圖示鈕可直接開 PDF；歸檔資料夾設定存 UNC 路徑（Tab6）；歸檔頁（Tab5）自動帶入預設資料夾。 |
