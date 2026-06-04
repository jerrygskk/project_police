================================================================
  公文管理系統 — 專案說明
  版本：115年度
================================================================

【系統功能】
  Tab 0：交辦單發文   — 掃入文號 → 預覽清單 → 批次發文
  Tab 1：交辦單收文   — 填表 → 立即寫入 DB → 預覽
  Tab 2：案件陳報     — 刑案 / 一般陳報，左右並列預覽
  Tab 3：簽收單列印   — 尚未開放

----------------------------------------------------------------
開發環境
----------------------------------------------------------------

  Python      3.12
  PySide6     6.x（確認版本：pip show PySide6）
  PyInstaller 6.20.0

  依賴套件（pip install）：
    PySide6, pandas, openpyxl, pyinstaller

----------------------------------------------------------------
目錄結構
----------------------------------------------------------------

  main.py                ← 進入點 + DocumentManager + MainMenu
  theme.py               ← Apple HIG QSS 樣式
  base_tab.py            ← 所有 Tab 的共用基礎類別（BaseTab）
  db_utils.py            ← DB / 資源工具（getResourcePath, loadUi, nextDocId）
  resources.qrc          ← Qt Resource 設定（arrow.svg 內嵌用）
  resources_rc.py        ← 由 pyside6-rcc 產生，勿手動修改
                           重新產生：pyside6-rcc resources.qrc -o resources_rc.py
  data_sync_tool.py      ← Excel 同步工具（獨立執行）

  ui_utils/              ← UI 工具套件
  ├── __init__.py        ← 統一 re-export
  ├── status.py          ← 狀態/日期邏輯（calcOverdue, colorForStatus）
  ├── widgets.py         ← 元件行為（setupFilterCombo, setupDateEditToToday）
  └── table.py           ← 表格工具（setupPreviewTable, autoResizeTable,
                                      makeDeleteBtn, FIXED_COL_WIDTHS）
                           setupPreviewTable 支援 stretch_col 與 fixed_overrides 參數

  tabs/                  ← 各功能 Tab
  ├── __init__.py        ← re-export 所有 Tab 類別
  ├── tab_dispatch.py    ← Tab 0：交辦單發文
  ├── tab_receive.py     ← Tab 1：交辦單收文
  └── tab_report.py      ← Tab 2：案件陳報（刑案 + 一般）

  Layout1.ui             ← 主視窗（tabWidget 外框，含交辦單發文 Tab 0 的欄位）
  Layout2.ui             ← 交辦單收文表單
  Layout3.ui             ← 案件陳報表單
  main_menu.ui           ← 主選單
  arrow.svg              ← 下拉箭頭（透過 resources_rc 內嵌，不需外部存取）
  police_badge.svg       ← 應用程式 icon（視窗標題列用）
  police_badge.ico       ← 應用程式 icon（exe 打包用）
  dbfile.db              ← SQLite 資料庫（需與 exe 放在同層）
  init_ref_tables.sql    ← DB 初始化腳本（data_sync_tool 使用）

----------------------------------------------------------------
各檔案行數
----------------------------------------------------------------

  main.py                135 行
  db_utils.py             49 行
  base_tab.py             43 行
  ui_utils/status.py      31 行
  ui_utils/widgets.py     89 行
  ui_utils/table.py      189 行
  ui_utils/__init__.py    23 行
  tabs/tab_dispatch.py   206 行
  tabs/tab_receive.py    181 行
  tabs/tab_report.py     410 行
  tabs/__init__.py         4 行
  ─────────────────────────────
  合計                  1360 行

----------------------------------------------------------------
新增 Tab 的標準流程
----------------------------------------------------------------

  步驟 1：新增 tabs/tab_xxx.py
          class TabXxx(BaseTab):
              def setup(self, tab_index): ...

  步驟 2：在 tabs/__init__.py 加一行
          from .tab_xxx import TabXxx

  步驟 3：在 main.py 的 TAB_CLASSES 登記
          TAB_CLASSES = {
              0: TabDispatch,
              1: TabReceive,
              2: TabReport,
              3: TabXxx,   ← 加這一行
          }

  步驟 4：在 Layout1.ui 確認對應 tab index 的頁籤存在

  → main.py 本身只改 TAB_CLASSES 那一行，其餘不動。

----------------------------------------------------------------
ui_utils 擴充規則
----------------------------------------------------------------

  - 新欄位固定寬度   → 在 table.py 的 FIXED_COL_WIDTHS 加一行
                       若同名欄位在不同表格需要不同寬度，改用 fixed_overrides 參數
                       例：setupPreviewTable(table, headers, fixed_overrides={"欄位名": 寬度})
  - 新的狀態顏色邏輯 → 在 status.py 的 colorForStatus 加條件
  - 新的元件行為     → 在 widgets.py 新增函式，並在 __init__.py export
  - 不論如何擴充，外部呼叫 from ui_utils import xxx 永遠不需要修改

----------------------------------------------------------------
tab_report.py 特殊架構說明
----------------------------------------------------------------

  Layout3.ui 使用 QStackedWidget（名稱 formStack）切換刑案/一般欄位：
    page 0 → 刑案欄位
    page 1 → 一般欄位
  切換時呼叫 form_stack.setCurrentIndex(0 or 1)，版面高度固定不跳動。

  發文分類改用 Radio Button（不用 ComboBox）：
    刑案：radio_status_a（現行）/ radio_status_b（到案）/ radio_status_c（未到）
          對應 DB：CS01 / CS02 / CS03
    一般：radio_gen_cat_a（業務）/ radio_gen_cat_b（其他）/ radio_gen_cat_c（相驗）
          對應 DB：GC01 / GC03 / GC02

  互填按鈕：
    btn_copy_to_receiver  → 同承辦：把承辦人員值填入受理人員
    btn_copy_to_processor → 同受理：把受理人員值填入承辦人員

  預覽表格欄位：
    刑案：編號 / 狀態 / 案類 / 陳報主旨（固定） / 承辦人 / 受理人 / 日期 / 報案人（stretch）
    一般：編號 / 業務單位 / 陳報主旨（固定） / 承辦人 / 分類（stretch）

  ⚠️ 預覽顯示名稱與 DB 不同，明年大修資料庫時需一起更新：
    刑案狀態：現行（DB: A_現行犯）/ 到案（DB: B_到案）/ 未到（DB: B_未到案）
    一般分類：業務（DB: D_業務陳報）/ 其他（DB: J_其他）/ 相驗（DB: F_司法相驗）
    人名顯示：去掉 - 後面的編號，例如 匿名-19.06 → 匿名
    日期顯示：MM-DD-YYYY 格式（DB 存 YYYY-MM-DD）

----------------------------------------------------------------
打包指令
----------------------------------------------------------------

  【主程式】
  pyinstaller --clean --onefile --windowed --icon=police_badge.ico ^
    --add-data "*.ui;." --add-data "police_badge.svg;." ^
    --name Police-Document-Manager main.py

  【資料同步工具】
  pyinstaller --onefile ^
    --add-data "init_ref_tables.sql;." ^
    --name Data-Sync-Tool data_sync_tool.py

  注意事項：
  - dbfile.db 不打包進 exe，需與 exe 放在同一資料夾
  - arrow.svg 已透過 resources_rc.py 內嵌，不需 --add-data
  - 若修改 arrow.svg，需重新執行：
      pyside6-rcc resources.qrc -o resources_rc.py
  - GitHub release 上傳檔名為英文（中文檔名會被 URL encode）

----------------------------------------------------------------
arrow.svg 修改流程（Qt Resource 方案）
----------------------------------------------------------------

  此專案採用 Qt Resource System 內嵌 arrow.svg。
  修改箭頭圖示步驟：
    1. 修改 arrow.svg
    2. 執行：pyside6-rcc resources.qrc -o resources_rc.py
    3. 重新打包

----------------------------------------------------------------
資料庫結構
----------------------------------------------------------------

  Document_Task（交辦單）
    doc_id          VARCHAR(50)   PK 流水號
    receive_date    DATE          收文日期
    receive_id      VARCHAR(10)   收文人員 → Ref_Personnel
    dept_id         VARCHAR(10)   業務組   → Ref_Departments
    subject         TEXT          交辦事由
    processor_id    VARCHAR(10)   承辦人   → Ref_Personnel
    deadline        DATE          限辦日期（NULL = 免覆）
    dispatch_date   DATE          發文日期（NULL = 未發）
    sender_id       VARCHAR(10)   送文人員 → Ref_Personnel
    timestamp       DATETIME      紀錄時間

  Document_Criminal（刑案陳報）
    doc_id          VARCHAR(50)   PK 流水號
    report_date     DATE          陳報日期
    sender_id       VARCHAR(10)   發文人員 → Ref_Personnel
    case_type       VARCHAR(10)   案件分類 → Ref_CaseTypes
    case_status     VARCHAR(10)   發文分類 → Ref_Case_Status
    processor_id    VARCHAR(10)   承辦人員 → Ref_Personnel
    subject_summary TEXT          陳報主旨
    occurrence_date DATE          查獲/受理日期
    reporter_name   VARCHAR(50)   報案人（純文字）
    receiver_id     VARCHAR(10)   受理人員 → Ref_Personnel
    is_reported     BOOLEAN       紙本（稽核用，預設 0）
    is_electronic   BOOLEAN       電子檔（稽核用，預設 0）

  Document_General（一般陳報）
    doc_id          VARCHAR(50)   PK 流水號
    report_date     DATE          陳報日期
    sender_id       VARCHAR(10)   發文人員 → Ref_Personnel
    dept_id         VARCHAR(10)   業務單位 → Ref_Departments
    gen_cat_id      VARCHAR(10)   發文分類 → Ref_General_Category
    subject         TEXT          陳報主旨
    processor_id    VARCHAR(10)   承辦人   → Ref_Personnel
    is_reported     BOOLEAN       紙本（稽核用，預設 0）
    is_electronic   BOOLEAN       電子檔（稽核用，預設 0）

  Ref_Personnel        staff_id / staff_name / is_active
  Ref_Departments      dept_id / dept_name
  Ref_CaseTypes        case_type_id / case_type_name（52種）
  Ref_Case_Status      status_id / status_name（CS01~CS03）
  Ref_General_Category gen_cat_id / gen_cat_name（GC01~GC03）
  Seq_DocId            table_name / last_id（各表流水號，由 nextDocId() 維護）

  View_Task_Full     ← 含狀態判斷邏輯（剩餘天數/逾期/已發文）
  View_Criminal_Full ← 刑案完整資訊（JOIN 所有參照表）
  View_General_Full  ← 一般完整資訊（JOIN 所有參照表）

================================================================
