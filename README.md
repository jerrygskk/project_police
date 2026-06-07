# 公文管理系統

> 版本：115年度

---

## 系統功能

| Tab | 功能 | 說明 |
|-----|------|------|
| 0 | 交辦單發文 | 掃入文號 → 預覽清單 → 批次發文 |
| 1 | 交辦單收文 | 填表 → 立即寫入 DB → 預覽，支援刪除 |
| 2 | 案件陳報 | 刑案 / 一般陳報，左右並列預覽，支援刪除 |
| 3 | 簽收單列印 | 輸入日期 → 產生 PDF 預覽 → 下載 / 列印 |

---

## 開發環境

| 工具 | 版本 |
|------|------|
| Python | 3.12 |
| PySide6 | 6.x（`pip show PySide6`） |
| PyInstaller | 6.20.0 |

```bash
pip install PySide6 pandas openpyxl pyinstaller matplotlib
```

---

## 目錄結構

```
├── main.py               # 進入點 + DocumentManager + MainMenu + Loading 流程
├── loading_screen.py     # Loading 畫面（LoadingScreen + LoadWorker）
├── theme.py              # Apple HIG QSS 樣式
├── base_tab.py           # 所有 Tab 的共用基礎類別（BaseTab）
├── db_utils.py           # DB / 資源工具（getResourcePath, loadUi, nextDocId）
│                         #   通用彈窗：msgInfo, msgWarning, msgCritical, confirmBox
│                         #   按鈕樣式常數：BTN_CONFIRM, BTN_DANGER, BTN_CANCEL
│                         #   測試開關：DEBUG_MODE
├── resources.qrc         # Qt Resource 設定（arrow.svg 內嵌用）
├── resources_rc.py       # 由 pyside6-rcc 產生，勿手動修改
├── data_sync_tool.py     # Excel 同步工具（獨立執行）
│
├── ui_utils/
│   ├── __init__.py       # 統一 re-export
│   ├── status.py         # 狀態/日期邏輯（calcOverdue, colorForStatus）
│   ├── widgets.py        # 元件行為（setupFilterCombo, setupDateEditToToday）
│   └── table.py          # 表格工具（setupPreviewTable, autoResizeTable,
│                         #   makeDeleteBtn, FIXED_COL_WIDTHS）
│                         #   支援 stretch_col / fixed_overrides / cap_mode 參數
│
├── tabs/
│   ├── __init__.py       # re-export 所有 Tab 類別
│   ├── tab_dispatch.py   # Tab 0：交辦單發文
│   ├── tab_receive.py    # Tab 1：交辦單收文
│   ├── tab_report.py     # Tab 2：案件陳報（刑案 + 一般）
│   └── tab_print.py      # Tab 3：簽收單列印
│
├── Layout1.ui            # 主視窗（tabWidget 外框，含交辦單發文 Tab 0 的欄位）
├── Layout2.ui            # 交辦單收文表單（含刪除按鈕欄）
├── Layout3.ui            # 案件陳報表單（含刪除按鈕欄）
├── Layout4.ui            # 簽收單列印
├── main_menu.ui          # 主選單
├── arrow.svg             # 下拉箭頭（透過 resources_rc 內嵌，不需外部存取）
├── police_badge.svg      # 應用程式 icon（視窗標題列用）
├── police_badge.ico      # 應用程式 icon（exe 打包用）
├── banner.png            # Loading 畫面橫幅圖（需與 exe 放在同層）
├── dbfile.db             # SQLite 資料庫（需與 exe 放在同層）
└── init_ref_tables.sql   # DB 初始化腳本（data_sync_tool 使用）
```

---

## 各檔案行數

| 檔案 | 行數 |
|------|------|
| main.py | 202 |
| loading_screen.py | 237 |
| db_utils.py | 106 |
| base_tab.py | 44 |
| ui_utils/status.py | 31 |
| ui_utils/widgets.py | 89 |
| ui_utils/table.py | 195 |
| ui_utils/\_\_init\_\_.py | 23 |
| tabs/tab_dispatch.py | 233 |
| tabs/tab_receive.py | 222 |
| tabs/tab_report.py | 481 |
| tabs/tab_print.py | 582 |
| tabs/\_\_init\_\_.py | 6 |
| **合計** | **2451** |

---

## 新增 Tab 的標準流程

**步驟 1** — 新增 `tabs/tab_xxx.py`
```python
class TabXxx(BaseTab):
    def setup(self, tab_index): ...
```

**步驟 2** — 在 `tabs/__init__.py` 加一行
```python
from .tab_xxx import TabXxx
```

**步驟 3** — 在 `main.py` 的 `TAB_CLASSES` 登記
```python
TAB_CLASSES = {
    0: TabDispatch,
    1: TabReceive,
    2: TabReport,
    3: TabXxx,   # ← 加這一行
}
```

**步驟 4** — 新增對應的 `LayoutN.ui`

> ⚠️ 每個 Tab 都必須有對應的 `.ui` 檔，無例外。
> `main.py` 本身只改 `TAB_CLASSES` 那一行，其餘不動。

---

## ui_utils 擴充規則

| 需求 | 做法 |
|------|------|
| 新欄位固定寬度 | 在 `table.py` 的 `FIXED_COL_WIDTHS` 加一行 |
| 同名欄位不同表格不同寬度 | 用 `fixed_overrides` 參數傳入，不改 `FIXED_COL_WIDTHS` |
| 欄位寬度隨內容縮，卡在上限 | 用 `cap_mode=True` 參數 |
| 新的狀態顏色邏輯 | 在 `status.py` 的 `colorForStatus` 加條件 |
| 新的元件行為 | 在 `widgets.py` 新增函式，並在 `__init__.py` export |

---

## 通用彈窗（db_utils.py）

所有彈窗統一從 `db_utils` import，確保按鈕樣式一致：

```python
from db_utils import msgInfo, msgWarning, msgCritical, confirmBox
```

| 函式 | 說明 | 按鈕 |
|------|------|------|
| `msgInfo(title, text)` | 一般訊息 | 確定（藍） |
| `msgWarning(title, text)` | 警告 | 確定（藍） |
| `msgCritical(title, text)` | 錯誤 | 確定（藍） |
| `confirmBox(title, text, confirm_text, cancel_text, confirm_danger, default_confirm)` | 確認對話框 | 自訂 |

**測試開關：**
```python
# db_utils.py
DEBUG_MODE = True  # 開啟所有 disable/greyout
```

---

## 刪除行為說明

Tab 1（交辦單收文）和 Tab 2（公文陳報）的刪除：
- **不是真的 DELETE**，而是清空該筆欄位（`doc_id` 保留）
- 流水號永久佔用，無法再被使用
- 彈窗提示：「本筆資料將被刪除，本文號（XXX）無法再被使用，確認刪除？」

---

## tab_report.py 特殊架構說明

### QStackedWidget

`Layout3.ui` 使用 `QStackedWidget`（名稱 `formStack`）切換刑案／一般欄位：

| index | 內容 |
|-------|------|
| 0 | 刑案欄位 |
| 1 | 一般欄位 |

### 發文分類 Radio Button

| 表單 | Radio | 顯示 | DB |
|------|-------|------|-----|
| 刑案 | radio_status_a | 現行 | CS01 |
| 刑案 | radio_status_b | 到案 | CS02 |
| 刑案 | radio_status_c | 未到 | CS03 |
| 一般 | radio_gen_cat_a | 業務 | GC01 |
| 一般 | radio_gen_cat_b | 其他 | GC03 |
| 一般 | radio_gen_cat_c | 相驗 | GC02 |

### ⚠️ 預覽顯示與 DB 差異（明年大修資料庫時需一起更新）

| 項目 | 預覽顯示 | DB 實際值 |
|------|---------|----------|
| 刑案狀態 | 現行 / 到案 / 未到 | A_現行犯 / B_到案 / B_未到案 |
| 一般分類 | 業務 / 其他 / 相驗 | D_業務陳報 / J_其他 / F_司法相驗 |
| 人名 | 王小明 | 王小明-19.06（去掉 `-` 後綴） |
| 日期 | MM-DD-YYYY | YYYY-MM-DD |

---

## 打包指令

### 主程式
```cmd
pyinstaller --clean --onefile --windowed --icon=police_badge.ico ^
  --add-data "*.ui;." --add-data "police_badge.svg;." --add-data "banner.png;." ^
  --exclude-module matplotlib.backends.backend_cairo ^
  --exclude-module matplotlib.backends.backend_gtk3 ^
  --exclude-module matplotlib.backends.backend_gtk3agg ^
  --exclude-module matplotlib.backends.backend_gtk3cairo ^
  --exclude-module matplotlib.backends.backend_gtk4 ^
  --exclude-module matplotlib.backends.backend_gtk4agg ^
  --exclude-module matplotlib.backends.backend_gtk4cairo ^
  --exclude-module matplotlib.backends.backend_macosx ^
  --exclude-module matplotlib.backends.backend_mixed ^
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

> PyInstaller 採黑名單機制（無白名單），只能用 `--exclude-module` 排除用不到的後端。
> 目前程式只用 `backend_agg`（PNG 預覽）和 `backend_pdf`（PDF 輸出），其餘全排除。

### 資料同步工具
```bash
pyinstaller --onefile --add-data "init_ref_tables.sql;." --name Data-Sync-Tool data_sync_tool.py
```

### 注意事項

- `dbfile.db` 不打包進 exe，需與 exe 放在同一資料夾
- `banner.png` 不打包進 exe，需與 exe 放在同一資料夾
- `arrow.svg` 已透過 `resources_rc.py` 內嵌，不需 `--add-data`
- GitHub release 上傳使用英文檔名（中文檔名會被 URL encode）
- 若修改 `arrow.svg`，需重新執行：
  ```bash
  pyside6-rcc resources.qrc -o resources_rc.py
  ```

---

## 資料庫結構

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
| is_electronic | BOOLEAN | 電子檔（稽核用，預設 0） |

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
| is_electronic | BOOLEAN | 電子檔（稽核用，預設 0） |

### 參照表

| 資料表 | 欄位 |
|--------|------|
| Ref_Personnel | staff_id / staff_name / is_active |
| Ref_Departments | dept_id / dept_name |
| Ref_CaseTypes | case_type_id / case_type_name（52種） |
| Ref_Case_Status | status_id / status_name（CS01~CS03） |
| Ref_General_Category | gen_cat_id / gen_cat_name（GC01~GC03） |
| Seq_DocId | table_name / last_id（由 nextDocId() 維護） |

### Views

| View | 說明 |
|------|------|
| View_Task_Full | 含狀態判斷邏輯（剩餘天數/逾期/已發文） |
| View_Criminal_Full | 刑案完整資訊（JOIN 所有參照表，案類 COALESCE 舊資料） |
| View_General_Full | 一般完整資訊（JOIN 所有參照表） |
