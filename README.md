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

| index | 名稱 | 類別 | Layout | 狀態 |
|-------|------|------|--------|------|
| 0 | 交辦單發文 | TabDispatch | Layout1 | 完成 |
| 1 | 交辦單收文 | TabReceive | Layout2 | 完成 |
| 2 | 公文陳報 | TabReport | Layout3 | 完成 |
| 3 | 簽收單列印 | TabPrint | Layout4 | 完成 |
| 4 | 資料庫瀏覽 | TabDBBrowse | Layout5 | 完成 |
| 5 | 檔案歸檔 | TabArchive | Layout6 | 完成 |
| 6 | 資料庫設定 | TabSettings | Layout7 | 功能完成 |

> **TabSettings 架構**：已比照其他 Tab 改用 `loadUi(Layout7.ui)` 建靜態骨架（密碼驗證頁、左側 nav、三個子頁的表格容器與動作鈕，全部具名），`tab_settings.py` 只保留動態內容（填表格列、每列四顆排序鈕、暫存排序狀態與邏輯、登入登出、跨年度重置）。動態狀態樣式（nav 選中切換、save_btn disabled 灰色）留在 code，比照其他 Layout（Layout1/2/3/5/6 皆不在 `.ui` 帶 stylesheet）。

### 資料流

- **三張主表**：`Document_Task`（交辦）、`Document_Criminal`（刑案）、`Document_General`（一般）
- **三個 View**：`View_Task_Full` 等，JOIN 參照表 + 算狀態，給預覽 / 列印 / 瀏覽用
- **參照表**：人員 / 部門 / 案類 / 案件狀態 / 一般分類（詳見第 6 節）
- 主表存的是參照表的 **ID**（VARCHAR 字串，非真外鍵），顯示時 JOIN 出名稱

### Tab 切換與刷新機制（重要）

`main.py` 的 `_onTabChanged(index)` 是核心調度，做三件事：

1. **從設定 Tab 切走時**：呼叫 `settings_tab._promptUnsaved(context="leave")` 處理未存排序；若 `_ref_dirty=True`，呼叫**其他所有 Tab** 的 `on_activated()` 刷新下拉
2. **切到設定 Tab 時**：呼叫 `settings_tab.on_activated()` 重載當前子頁（與 DB 同步）
3. autoresize 表格 + 設定焦點

> ⚠️ **Qt 限制**：`QTabWidget.currentChanged` 是「切換**後**」才發出，無法在切換前攔截詢問「要不要存」。所以「離開大 Tab」的未存提醒只能是「切過去後補跳」，不能攔住不讓切。設定 Tab 內部的子頁切換（按鈕觸發）則攔得住，可以「取消 = 回原狀」。

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
- 設定 Tab 每列有四顆排序鈕：置頂 / 上移 / 下移 / 置底（SVG 圖示，見 `res/sort_*.svg`）
- **暫存模式**：排序在記憶體操作，「儲存排序」鈕初始 disabled、動過才亮；儲存才寫回 DB（連續整數重編）並設 `_ref_dirty=True`
- 未存排序時切子頁 / 切大 Tab / 按修改，會跳確認；取消行為：按鈕觸發的（修改、子頁）回原狀，大 Tab（攔不住）放棄
- 新增項目放最前（`MIN-1`）

### 權限（AuthManager，單例）

- SHA-256 密碼存 `App_Settings`，預設 `0000`，標題列顯示 `[一般使用者]`/`[管理者模式]`，閒置 20 分鐘自動登出
- 設定 Tab 需管理者登入；變更密碼為高風險操作，**Enter 不送出**（防誤按），只能滑鼠點

**編輯 popup 權限模型**（點預覽表編號開的彈窗；身分變更時 `_onRolePerm`／`outer_stack` 即時生效）：

| Tab | admin | 一般使用者 |
|-----|-------|-----------|
| 交辦單發文 Tab0 | 全可改（含已發文，編號恆可點） | 只能改承辦人；**已發文鎖住開不了** |
| 交辦單收文 Tab1 | 全可改 | 全可改（誤輸更正屬正常作業，檢查後修改合理） |
| 公文陳報 Tab2（刑案／一般） | 全可改 | 全可改 |
| 資料庫瀏覽 Tab4 | 全可改 | 無法開（編號變純文字） |
| 檔案歸檔 Tab5 | 全可改 | 無法開（整頁 `outer_stack` 登入 gate） |

> 一般使用者限制由 `TaskEditDialog(restricted=…)` 控制（鎖定欄位顯示 DB 原值＋灰 `:disabled` 樣式，儲存只動承辦人）；連結可點與否由各 tab `setDocIdLinkCell(clickable=…)` 控制，身分變更時 `_onRolePerm` 重刷（編號連結＋刪除鈕）。

### 其他慣例

- 所有彈窗都加 Enter 確認（高風險操作如變更密碼除外）
- 跨年度會有 **Reset 按鈕**（尚未做）重編所有 ID，所以**不需要** Seq 流水號機制；現有 `Seq_DocId` 等年底 Reset 一起歸零
- 主表「刪除」是清空欄位保留 doc_id，流水號永久佔用，彈窗會提示「本文號（XXX）無法再被使用」
- **身分判斷**用 `AuthManager.instance().is_admin()`（等同 `current_role == 'admin'`，勿再各處寫字串比較）
- **DB 連線**統一走 `db_utils.getConn(db_path)`（單一來源，要加 PRAGMA/timeout 集中改一處）；`base_tab._getConn`、`edit_dialog._get_conn` 皆委派它
- 三個編輯彈窗（Task/Criminal/General）共同繼承 `_BaseEditDialog`，集中版面常數 `_LABEL_W/_FIELD_W/_MARGIN`（子類以 `self._LABEL_W` 引用）

---

## 4. 目錄結構

```
專案根/
├── main.py              進入點（從專案根目錄啟動）
├── data_sync_tool.py    Excel→SQLite 匯入工具（單次使用，獨立打包，不被 import）
├── sql.py               DB 結構查看工具（analyze_database，獨立 __main__ 跑，不被 import）
├── backfill_archive_names.py  存量補檔腳本（一次性，掃資料夾回填 is_electronic）
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

重編 id 採**兩段式**避主鍵衝突：先把所有列改成暫時前綴（`__TMP__P0001`...），再編回正式 id。**別改成單段直接 UPDATE**，舊新 id 集合有交集會撞 PRIMARY KEY。

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
| Ref_Personnel | staff_id / staff_name / is_active / **sort_order** |
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

### 資料同步工具

```cmd
pyinstaller --onefile --name Data-Sync-Tool data_sync_tool.py
```

### 注意事項

- `dbfile.db` 不打包，與 exe 同資料夾（真實資料）
- `ori.xlsm`（資料同步工具用）不打包，與 Data-Sync-Tool.exe 同資料夾
- `arrow.svg` / `sort_*.svg` / `icon_pdf.svg` / `icon_archive.svg` 已透過 `resources_rc.py` 內嵌，不需 `--add-data`；改了要重編 qrc
- 列印用 `QtPrintSupport`，加 `--hidden-import PySide6.QtPrintSupport` 保險
- matplotlib 只用 `backend_agg`（PNG）+ `backend_pdf`（存 PDF），其餘 backend 全排除
- 結構重組後 `.ui` 進 `layouts/`、圖片進 `res/`，`--add-data` 路徑要對應第二參數（解壓目標目錄）
- 指令開頭 `del ...spec & rmdir build dist` 是刻意的：開發期不信任殘留 spec（會用到上次的過期設定），每次砍掉 spec / build / dist 用乾淨 CLI 參數全新生成。`2>nul` 讓首次執行（檔案不存在）不報錯
- **跨年度重置的自動重啟**：onefile 版重啟新程序前必設環境變數 `PYINSTALLER_RESET_ENVIRONMENT=1`（PyInstaller 6.10+ 官方機制），否則新程序沿用舊 `_MEI` 環境、到已刪除的暫存目錄找 `python3xx.dll`/標準庫而崩潰（`Failed to load Python DLL` / `unicodedata` 缺失）。`_restartApp()` 已處理。詳見第 2 節踩雷表與第 5 節 Reset 子節
- 若打包後報 `No module named res`，加 `--hidden-import res.resources_rc`
- 核心模組在 `lib/`，主程式打包已列 `--hidden-import lib.*` 七個（含 `lib.archive_text`）；若仍報 `No module named lib.xxx`，補對應的 hidden-import
- GitHub release 上傳用英文檔名

---

## 8. 待辦

| 項目 | 說明 |
|------|------|
| 別名表 `_ALIAS` | tab_archive 的人名別名對照目前為空 dict，等維護者提供綽號清單 |
| 重跑轉檔重建 DB | schema 有 is_electronic TEXT、last_modified、trigger，差異更新需重跑轉檔才完整生效 |
| 存量補檔腳本 | backfill_archive_names.py 需重跑轉檔後再執行 |

---

## 9. 版本記錄

> 版本號單一來源為 `lib/version.py` 的 `__version__`。進版時改該處一行，主選單顯示自動同步；本表與 git tag（`v{__version__}`）需手動對齊。

| 版本 | 摘要 |
|------|------|
| v1.0.0 | 正式版。瀏覽頁（Tab4）有歸檔檔名者顯示圖示鈕可直接開 PDF；歸檔資料夾設定存 UNC 路徑（Tab6）；歸檔頁（Tab5）自動帶入預設資料夾。 |
| v0.9.0-beta.12 | admin 解除已發文編號鎖定；內部重構（抽 `lib/archive_text.py`、統一 `AuthManager.is_admin()`、`db_utils.getConn`）。 |
| v0.9.0-beta.11 | 分頁權限控管（Tab0 限改承辦人、Tab4 無修改、Tab5 需登入）；修 dbbrowse 編號欄 item/cellWidget 疊現；刑案/一般 popup 新增歸檔狀態區塊（僅 admin）。 |
| v0.9.0-beta.10 | 歸檔頁新增「只歸紙本」鈕；修斷詞比對日期黏主旨漏字（310 筆）；交辦單新增逾期未回篩選。 |
| v0.9.0-beta.9 | 完成瀏覽（Tab4）與歸檔（Tab5）頁；統一 popup 左確認右取消（ActionRole）；code review 清理 import。 |
| v0.9.0-beta.8 | 設定 Tab 改用 Layout7.ui 靜態骨架；新增跨年度重置（備份＋兩段式重編 ID＋自動重啟）；版本號集中至 `lib/version.py`。 |
| v0.9.0-beta.7 | 部門/案類 is_active 軟刪除、sort_order 四向排序鈕；列印改 QPrintPreviewDialog；檔案結構重組（layouts/ res/ lib/）。 |
| v0.9.0-beta.6 | 設定 Tab 人員/部門/案類維護＋變更密碼；AuthManager；參照表連動；黏底捲動；狀態色。 |