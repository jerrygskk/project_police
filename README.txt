================================================================
  公文管理系統 — 重構說明
  對應原始版本：main.py（806行，單一檔案）
================================================================

【重構目標】
  原始 main.py 共 806 行，工具函式、資料庫、UI、Tab 邏輯全部混在一起。
  重構後 main.py 只剩 ~75 行，職責清晰，未來新增 Tab 不需動到核心。

----------------------------------------------------------------
目錄結構
----------------------------------------------------------------

  main.py                ← 進入點 + DocumentManager + MainMenu
  theme.py               ← Apple HIG QSS 樣式（不動）
  base_tab.py            ← 所有 Tab 的共用基礎類別（BaseTab）
  db_utils.py            ← DB / 資源工具（getResourcePath, loadUi, nextDocId）

  ui_utils/              ← UI 工具套件（package，有 __init__.py 統一 export）
  ├── __init__.py        ← 統一 re-export，外部只需寫 from ui_utils import xxx
  ├── status.py          ← 狀態/日期邏輯（calcOverdue, colorForStatus）
  ├── widgets.py         ← 單一元件行為（setupFilterCombo, setupDateEditToToday）
  └── table.py           ← 表格工具（setupPreviewTable, autoResizeTable,
                                      makeDeleteBtn, FIXED_COL_WIDTHS）

  tabs/                  ← 各功能 Tab（package）
  ├── __init__.py        ← re-export 所有 Tab 類別
  ├── tab_dispatch.py    ← Tab 0：交辦單發文
  └── tab_receive.py     ← Tab 1：交辦單收文

  Layout1.ui             ← 主視窗（不動）
  Layout2.ui             ← 交辦單收文表單（不動）
  公文輸入系統.ui         ← 主選單（不動）
  arrow.svg              ← 下拉箭頭圖示（不動）
  dbfile.db              ← SQLite 資料庫（不動）
  data_sync_tool.py      ← Excel 同步工具（不動）
  init_ref_tables.sql    ← DB 初始化腳本（不動）

----------------------------------------------------------------
各檔案行數對比
----------------------------------------------------------------

  【重構前】
    main.py                806 行（全部混在一起）

  【重構後】
    main.py                 75 行
    base_tab.py             40 行
    db_utils.py             35 行
    ui_utils/status.py      30 行
    ui_utils/widgets.py     70 行
    ui_utils/table.py      105 行
    ui_utils/__init__.py    18 行
    tabs/tab_dispatch.py   165 行
    tabs/tab_receive.py    155 行
    tabs/__init__.py         4 行
    ─────────────────────────────
    合計                   697 行（比原本少 109 行，且每檔職責單一）

----------------------------------------------------------------
新增 Tab 的標準流程（例如：刑案 Tab）
----------------------------------------------------------------

  步驟 1：新增 tabs/tab_criminal.py
          class TabCriminal(BaseTab):
              def setup(self, tab_index): ...

  步驟 2：在 tabs/__init__.py 加一行
          from .tab_criminal import TabCriminal

  步驟 3：在 main.py 的 TAB_CLASSES 登記
          TAB_CLASSES = {
              0: TabDispatch,
              1: TabReceive,
              2: TabCriminal,   ← 加這一行
          }

  步驟 4：在 Layout1.ui 確認對應 tab index 的頁籤存在

  → main.py 本身只改 TAB_CLASSES 那一行，其餘不動。

----------------------------------------------------------------
ui_utils 擴充規則
----------------------------------------------------------------

  - 新欄位固定寬度   → 在 table.py 的 FIXED_COL_WIDTHS 加一行
  - 新的狀態顏色邏輯 → 在 status.py 的 colorForStatus 加條件
  - 新的元件行為     → 在 widgets.py 新增函式，並在 __init__.py export
  - 不論如何擴充，外部呼叫 from ui_utils import xxx 永遠不需要修改

----------------------------------------------------------------
已修正的原始 bug
----------------------------------------------------------------

  1. setupDateEditToToday 中 _EventFilter._scroll_fn 從未被呼叫
     → 已移除死碼

  2. setupPreviewTable 中 from PySide6.QtCore import QTimer 重複 import 兩次
     → 已整理為單一 import

  3. _confirmDialog 邏輯在原 TabReceive._submit 中重複出現兩次
     → 已抽出為 TabReceive._confirmDialog() 共用

================================================================
