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
          └─ DocumentManager（主視窗，建立 8 個 Tab）
```

- `DocumentManager.TAB_CLASSES` 是 `{index: TabClass}` 的字典，新增 Tab 在這裡登記
- 每個 Tab 繼承 `BaseTab`，必須實作 `setup(tab_index)`
- 可 override：`get_tables()`（回傳要 autoresize 的表格）、`get_focus_widget()`（進 Tab 時聚焦的元件）、`on_activated()`（被切到時刷新）
- ⚠️ **主選單拉到最前**：打包版偶因 Windows 前景鎖，`MainMenu` 的 `exec()` dialog 會被壓到別的視窗後面。修法是 `QTimer.singleShot(0, …)` 在 exec 進事件迴圈、dialog 顯示後 `raise_()`＋`activateWindow()`＋清最小化狀態（`main.py` `_on_data_ready`）。

### Tab 結構（共 8 個）

| index | 名稱 | 類別 | Layout |
|-------|------|------|--------|
| 0 | 交辦單發文 | TabDispatch | Layout1 |
| 1 | 交辦單收文 | TabReceive | Layout2 |
| 2 | 公文陳報 | TabReport | Layout3 |
| 3 | 簽收單列印 | TabPrint | Layout4 |
| 4 | 資料庫瀏覽 | TabDBBrowse | Layout5 |
| 5 | 檔案歸檔 | TabArchive | Layout6 |
| 6 | 資料庫設定 | TabSettings | Layout7 |
| 7 | 操作紀錄 | TabAudit | Layout8 |

> 主選單（`main_menu.ui`）為 2 欄圖示磚格（QToolButton 圖上字下），各功能圖示為 `res/buttons/menu_*.svg`（qrc 別名 `:/menu/`），於 `main.py` 程式內以 `QIcon` 套用（避開 QUiLoader 解析 .qrc resource 的問題）。

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

> **啟動預載建表（＋進度條）**：取消惰性載入。啟動順序為 `載入畫面 → 主選單 → 選功能秒進`：載入畫面期間，`LoadWorker` 背景執行緒先預讀三表完整資料（`queryBrowseRows`，純 SQL，可跨執行緒），再交主執行緒於 `DocumentManager.__init__` 以 `buildInitial` 分段建好整個主視窗，進度條全程顯示「讀取…／建立…清單」（`LOAD_STEPS`／`BUILD_STEPS` 見 `lib/loading_screen.py`）。主選單出現時主視窗已就緒。建完設 `_loaded=True`，之後沿用下列指紋／diff 機制；`on_activated` 首次分支降為 fallback（萬一未預建才補建）。
>
> **建表成本已大幅降低**：原本每列「刪除鈕＋編號連結」兩個 cellWidget 是先天成本。現改為**刪除欄（✕）、編號欄、無 PDF 的主旨欄一律純 `QTableWidgetItem`**，點擊以 `cellClicked` 攔截（`_onDeleteCell`／`_onLinkCell`）；只有刑案／一般陳報「有真實 PDF 檔名」的主旨列才保留 cellWidget（PDF 圖示鈕）。交辦單每列 0 個 cellWidget。⚠️ 建表發生在主視窗 show 之前（viewport 寬=0），欄寬靠 `autoResizeTable` 重試補正。

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

**三角色模型**：`user`（一般使用者，預設）／`archive`（歸檔管理）／`admin`（管理者，最高權限）。

- SHA-256 密碼存 `App_Settings`：`admin_password_hash`（預設 `admin`）、`archive_password_hash`（預設 `0000`）。**兩組密碼必須相異**——`login()` 先比 admin 再比 archive，若兩組同值則 archive 永遠登不進去。
- **登入**：`login(password, db_path)` 依序比對兩組 hash，中 admin → role=`admin`、中 archive → role=`archive`、都不中 → 失敗（並寫一筆登入失敗稽核，不記輸入的密碼）。
- 標題列顯示三態 `[一般使用者]`/`[歸檔管理]`/`[管理者模式]`，admin 與 archive 皆閒置 **10 分鐘**自動登出（降回一般使用者，程式不關）。
- **便捷判斷**：`is_admin()`（最高權限）／`is_archive()`／`is_manager()`（admin or archive，給「歸檔管理也能做」的功能用）／`actor_name()`（回中文身分名，稽核 operator 用）。**勿在各處寫字串比較**。
- **變更密碼**：`change_password()` 依「當前登入身分」改對應那組（admin→admin、archive→archive）；user 身分不得改（回 False）。變更密碼為高風險操作，**Enter 不送出**（防誤按），只能滑鼠點。

**權限矩陣**（歸檔管理 = 一般使用者權限 + 下列加項；空白＝同一般使用者）：

| Tab | admin | 歸檔管理 archive | 一般使用者 user |
|-----|-------|-----------------|----------------|
| 交辦單發文 Tab0 | 全可改（含已發文，編號恆可點） | 同一般使用者 | 只能改承辦人；**已發文禁止編輯** |
| 交辦單收文 Tab1 | 全可改 | 同一般使用者 | 開放輸入錯誤修正、開放刪除 |
| 公文陳報 Tab2（刑案／一般） | 全可改 | 同一般使用者 | 開放輸入錯誤修正、開放刪除 |
| 簽收單列印 Tab3 | 可使用 | 可使用 | 可使用 |
| 資料庫瀏覽 Tab4 | 全可改（含刪除） | 可**修改**、**無刪除**（刪除鈕仍僅 admin） | 不開放編輯 |
| 檔案歸檔 Tab5 | 可使用 | 可使用 | 無法使用 |
| 設定 Tab6 | 全可使用 | **可視**：變更密碼／歸檔資料夾設定／登出開放；參照表維護（新增／改名／儲存排序／拖拉）與跨年度重置 **disable 灰掉** | 無法使用 |
| 操作紀錄 Tab7 | 可檢視（唯讀／篩選／匯出 CSV） | 無法使用（顯示遮罩、導引設定頁登入） | 無法使用（顯示遮罩、導引設定頁登入） |

> 一般使用者限制由 `TaskEditDialog(restricted=…)` 控制（鎖定欄位顯示 DB 原值＋灰 `:disabled` 樣式，儲存只動承辦人）；身分變更時 `_onRolePerm` 重刷編號連結與刪除鈕。連結可點與否：收文／發文／陳報頁仍由 `setDocIdLinkCell(clickable=…)` 控制（cellWidget）；**瀏覽頁已改純 item**，`_onRolePerm` 只切編號欄 `setForeground`（藍＝可點）、`refreshDeleteBtns` 切 ✕ 字色，點擊一律走 `cellClicked`。
> 「歸檔管理也能做」的判斷（歸檔頁、Tab4 編輯、編輯彈窗歸檔狀態區塊）用 `is_manager()`；「僅 admin」的（Tab4 刪除鈕、Tab0 發文）維持 `is_admin()`。設定頁的參照表維護按鈕對 archive `setEnabled(False)`（需配 `:disabled` 樣式才會變灰，見 §2 雷）；雙擊參照表列會繞過按鈕 enabled，故 6 個 `_add*/_edit*` 方法首加 `_refEditable()`（僅 admin）guard。

### 閒置處理與多人使用（main.py）

兩個獨立的閒置計時器（皆在 `DocumentManager`，由全域事件過濾器 `_IdleFilter` 監聽滑鼠/鍵盤/滾輪重設）：

- **閒置自動登出**：`_idle_timer`，**10 分鐘**，**僅管理者／歸檔管理**計時，到點 `logout()` 降回一般使用者（程式不關）。
- **閒置自動關閉**：`_close_timer`，**20 分鐘**，**不分身分一律計時**，到點 `_onIdleClose` 以 **`os._exit(0)` 硬關**（靜默，僅 error.log 留一行；會丟掉未送出的暫存輸入）。順序上管理者離開會先 10 分自動登出、再到 20 分整支關閉。
  - ⚠️ **為何用 `os._exit` 而非 `app.quit()`**：到點當下若有 **modal `exec()`** 開著（HELP 視窗／`confirmBox`／編輯彈窗／原生 `QFileDialog` 等），`quit()` 只會退掉**最內層**那個對話框的事件迴圈、關不掉主程式（且 `_close_timer` 為 single-shot、已觸發就不再重啟＝自動關閉從此失效）。`os._exit` 不受巢狀事件迴圈影響，一定結束。代價是不走 Qt teardown（會在 console 印 `QThreadStorage ...` 收尾警告——無害，`--windowed` 打包版無 console 故使用者看不到），故**結束前先手動清鎖檔**（見下）。

**APP 層軟性互斥（`lib/app_lock.py`）**：DB 放網路磁碟機給多台機器同時跑時，SQLite 檔案鎖不保證跨機器生效、真同時寫入可能毀損。故在 `dbfile.db` 旁維護鎖檔 `dbfile.lock`（JSON：機器名/使用者/開啟時間/心跳/PID），開啟時讀它判斷是否已有人在用：

- 偵測到「新」的鎖檔（心跳未超過 `STALE_SECONDS=5 分鐘`）→ 跳 `confirmBox`：「○○○（電腦 X）自 HH:MM 起正在使用本系統」，灰字次要說明提醒「多人同時編輯可能造成資料毀損，建議稍後再開」＋「開啟後若閒置超過 20 分鐘，程式將自動關閉」（讓使用者知道何時可再回來），按鈕**仍要開啟 / 取消離開**（純勸導，預設取消）。心跳過舊＝視為當機殘留，可直接接管。
- 開啟後寫自己的鎖檔、每 `HEARTBEAT_MS=60 秒` 更新心跳。**清鎖檔三道**：`app.aboutToQuit`（蓋正常關窗）＋ `atexit`（補蓋主選單離開、建表失敗等 `sys.exit` 不經 Qt quit 的路徑）＋**閒置自動關閉的 `os._exit` 前手動呼叫**（`mgr._cleanup_lock_cb`；因 `os._exit` 不會觸發 aboutToQuit／atexit）；皆只刪屬於本實例者（比對機器名＋PID）、冪等靜默。**當機／強制結束／斷電**皆蓋不到，靠心跳停止後 `STALE_SECONDS` 失效自癒。
- ⚠️ **是勸導不是保證**：可按「仍要開啟」硬上，corruption 風險（SMB 鎖那層）仍在。**不做唯讀模式、不擋 DB 寫入**（寫入併發由 SQLite 自身忙線鎖處理，對應「資料庫忙線中」友善訊息）。讀寫鎖檔失敗一律靜默退讓，不阻擋開程式。
- 純邏輯（parse/format/is_stale/is_mine/lock_file_path）有單元測試 `tests/test_app_lock.py`。

### 平時自動備份（`lib/db_backup.py`）

單機程式平時零備份，硬碟外的損毀（檔案毀損、誤刪、DB malformed）一旦發生即無救。故於**程式啟動時**（鎖檔寫入後、建主視窗前，`main.py` 呼叫 `run_auto_backup`）做**常規祖孫式（GFS）輪替備份**，存放於 `dbfile.db` 同目錄的 `backups/` 子夾。做到每週為止（不做 monthly 那一層），兩層皆帶日期、各自輪替修剪：

- **每日** `dbfile_backup_day_YYYYMMDD.db`：每天第一次開啟時建一份（當天再開不重做），保留最近 `DAILY_KEEP=7` 份、較舊者刪除。最近一週有逐日粒度。
- **每週** `dbfile_backup_week_YYYYMMDD.db`：每週（ISO 週）第一次開啟時建一份，保留最近 `WEEKLY_KEEP=4` 份。涵蓋約一個月。誤刪當天靠每日救、過幾天才發現靠每週救。

- **備份方式**：用 sqlite3 backup API 取一致性快照（即使有並發寫入也安全），先寫 `.tmp` 再 `os.replace` 原子換上（中途失敗不毀既有好檔）。保留份數常數在 `lib/db_backup.py` 頂部，要調量改那裡。
- **容錯**：全程 `try/except`，失敗只記 `error.log`，**絕不拋例外、絕不阻擋程式開啟**（同 app_lock 哲學）。
- ⚠️ **本層只防本機檔案損毀／誤刪，救不了硬碟整顆故障**（備份與本體同碟）。防硬碟故障需異地備份（指定另一顆碟／網路碟／USB），為後續另一層、尚未實作。
- **手動還原**：關閉程式後，將 `backups/` 內要還原的那份**複製覆蓋** `dbfile.db`（覆蓋前建議先把現有 `dbfile.db` 另存留底），再重開程式。目前無還原 UI。
- 純邏輯（`is_daily_due`/`is_weekly_due`/`parse_daily_dates`/`parse_weekly_dates`/`prune_targets`）＋ sqlite backup round-trip 有單元測試 `tests/test_db_backup.py`。`backups/` 已加入 `.gitignore`。

### 全域錯誤處理與白話化訊息

未預期的例外由 `main.py` 的全域 handler（`_setup_error_handler` 設 `sys.excepthook`）統一接手，做三件事：

1. **寫 `error.log`**（exe／專案根目錄下，UTF-8，含完整 traceback）。
2. **寫 Windows 事件檢視器**（有 `pywin32` 時；無則靜默跳過）。
3. **彈白話錯誤視窗**（`QApplication` 存在時）：以 `db_utils.friendlyErrorMessage(exc_type, exc_value)` 把工程語言的例外轉成承辦看得懂、可行動的提示——**技術細節（traceback）只進 error.log，不丟給使用者**。

`friendlyErrorMessage` 依例外型別分類對應白話訊息（純邏輯、可單測，測試 `tests/test_error_msg.py`）：

- **SQLite**：忙線鎖定（locked/busy）→「資料庫忙線中…請關閉其他視窗」；缺表／損毀（malformed、DatabaseError 等）→「資料庫檔案可能損毀…請提供 error.log 與備份檔」。
- **檔案／權限／網路磁碟**：`PermissionError`（檔案被佔用／權限不足）、`FileNotFoundError`（找不到檔案／歸檔資料夾，導向設定頁）、`OSError`/`IOError`（網路磁碟機可能斷線）。
- 對照不到的型別 → 泛用訊息（已記錄至 error.log、請提供維護人員）。

> 與「資料庫忙線中」訊息呼應的是 APP 層軟性互斥（見上）：多機共用網路碟、真同時寫入時，SQLite 忙線鎖會丟 `OperationalError`，此處轉成白話提示使用者關閉其他視窗重試。

### 稽核 log（操作紀錄）

對關鍵操作寫不可竄改意圖的操作紀錄（單機環境本質無法防 admin 直接開 DB 改 log，已接受；程式內不提供刪 log UI）。

- **表**：`Audit_Log`（log_id/ts/role/action/target_table/target_id/operator/detail）。**不寫進啟動 DDL**（比照本專案不做啟動 migration 的慣例）。**自 v1.1.0 起，入庫／Release 的空殼已預先跑過 `fix_audit_setup.py`、內建本表＋兩組密碼**，故全新安裝免再跑；僅升級現場既有舊庫才需另跑 `fix_audit_setup.py` 補表。
- **helper（`lib/db_utils.py`）**：
  - `writeAudit(conn, *, role, action, detail, target_table, target_id, operator)`：用呼叫端**同一個 conn**寫入（與業務操作同 transaction，由呼叫端統一 commit）；ts 取 SQLite 本機時間。**缺 `Audit_Log` 表的舊 DB 靜默跳過**（`except: pass`），不中斷業務。
  - `buildDetail(類別, 動作, 內容)` → `[類別][動作]內容`。類別＝交辦／刑案／一般／人員／部門／案類／歸檔／系統。
  - `auditStaffName(conn, id)`：以 staff_id 解析當下姓名快照（operator 用）。
- **operator 取值規則**（幾經修訂的最終版）：
  - **admin 的刪除一律留空 operator**（admin 跨庫操作與資料列的人脫鉤，記了會誤導成「那個人刪的」）。
  - 非 admin（一般／歸檔管理）在業務頁刪除 → 記資料列的人（收文者／陳報人）。
  - 瀏覽頁刪除僅 admin → 一律留空。
  - 參照表／系統類 → 記登入身分（`actor_name()`）。
- **刪除取值時機**：清空式 UPDATE **之前**先 SELECT operator＋主旨（清空後拿不到）。
- **四處刪除共用一個 helper**：收文／陳報(刑案/一般)／瀏覽四處的「快照→回收筒→清空→稽核」收斂為 `db_utils.softDeleteDoc(conn, *, table, doc_id, role, is_admin, audit_operator=True)`（清空 SQL、主旨欄、對象人欄、operator 來源欄集中於該檔的 `_DELETE_CLEAR_SQL`／`_DELETE_META`）。業務頁照預設（非 admin 記資料列的人）；瀏覽頁僅 admin、傳 `audit_operator=False` 讓 operator 恆留空。⚠️ **收文／陳報頁一般使用者可刪**（更正剛輸入的錯列，符合 §3 權限矩陣）；舊版誤把這兩頁刪除擋成僅 admin（已移除過嚴守門與沒人用的 `AuthManager.can()`）。純邏輯測試 `tests/test_soft_delete.py`。
- **已接上的事件**：收文／刑案／一般／瀏覽頁刪除、發文改承辦（限 `source='dispatch'` 且 processor 變動）、參照表新增／改名／停用啟用（排序不記）、歸檔取消（電子／紙本；歸檔本身不記，只記取消）、跨年度重置、變更密碼（不記密碼內容）、歸檔路徑變更、登入失敗（不記輸入的密碼）。
- **Reset 與 log**：①先寫 Reset log（含清除筆數）②整庫自動備份（歷史 log 隨備份保存）③`performYearEndReset` 清空主表時**含 `Audit_Log`**（當前庫歸零、歷史在備份檔）。
- ⚠️ **DB 須含本表才會寫稽核**：自 v1.1.0 起**入庫／Release 的空殼已內建 `Audit_Log`＋兩組密碼**（建置時預跑 `fix_audit_setup.py` 烤入），全新安裝直接可用。**僅現場既有舊庫升級**才需另跑 `fix_audit_setup.py` 補表，否則程式照跑但稽核一筆都不寫（靜默退化成單一 admin、無 log）。`fix_audit_setup.py` 為一次性工具、**不入庫**。

**檢視 UI（操作紀錄 Tab7，`tabs/tab_audit.py`）**：唯讀、**僅 admin**（非 admin 顯示遮罩，導引至設定頁登入；牆同歸檔頁 `outer_stack` 機制，連 `role_changed`）。
- 全量載入 `Audit_Log`（`ORDER BY log_id DESC`）後以 `setRowHidden` 篩選（比照資料庫瀏覽頁）；`detail` 經 `parseDetail` 解析 `[類別][動作]內容` 拆「類別／動作/內容」三欄顯示。
- **欄位**：時間｜身分｜類別｜動作｜內容｜對象人。`role` 轉中文；刪除／重置／登入失敗動作以紅字＋紅「●」標示（`setForeground`，勿用 `::item{color}`）；身分 admin 鋼藍、archive 灰藍、空白灰。
- **表格樣式比照資料庫瀏覽頁**：固定列高 30、不換行（內容單行省略、完整內容入 tooltip）、無格線、`NoSelection`+`NoFocus`（唯讀不反白）。
- **篩選**：期間起迄（`QDateEdit`，留白＝不限，哨兵 `minimumDate`=2000-01-01）／身分／類別／關鍵字（比對內容＋對象人）；底部計數「顯示 N／共 M 筆」。身分／類別下拉**無外部標籤**，首項自述「全部身分」「全部類別」省版面；篩選列控件統一 12pt（用 stylesheet `font-size`，勿用 `setFont`——會被全域 14pt CSS 蓋回）。⚠️ 日期框寬度須容得下 14pt/12pt 的 10 位日期＋全域 `QDateEdit` 右內距 32px（讓位箭頭），尺寸先以 `QFontMetrics` 量測再設，勿憑猜。
- **手動重整**：`btn_reload`（「重整」，CSV 左邊）→ `_load(force=True)` 繞過指紋短路強制重查，供 admin 久停本頁時取最新紀錄。
- **匯出 CSV**：`btn_export` 匯出**目前篩選後**可見列（`utf-8-sig`，動作欄寫原文不含「●」）。
- **切頁免重建**：`on_activated` 比對資料指紋 `(COUNT, MAX(log_id))`（append-only＋Reset 清空皆能偵測變動），指紋未變且已載入過則不重建（比照資料庫瀏覽頁）；需重建時以 `preserveScroll` 保留捲動位置。
- 跨年度 Reset 會清 `Audit_Log`，故單庫紀錄量上限約一年，全量載入無虞。`parseDetail` 純邏輯有單元測試 `tests/test_audit_view.py`。

### 誤刪還原（資源回收筒）

主表「刪除」是清空欄位保留 doc_id（空殼列恆在）。為支援誤刪還原，**清空前先把整列快照存進回收筒**，還原時把快照寫回原 doc_id 那列。

- **表 `Trash_Documents`**（見 §6）：`payload` 存刪除前整列 JSON 快照；`subject`/`doc_person`（承辦人）/`deleted_ts`/`deleted_role` 供清單顯示。由 `ensureSchema` 啟動冪等建立。
- **helper（`lib/db_utils.py`，純邏輯可單測）**：`snapshotRow(conn, table, doc_id)` 清空前抓整列（table 走三主表 allowlist）；`writeTrash(...)` 寫回收筒（缺表靜默跳過，同 `writeAudit` 哲學）；`restoreFromTrash(conn, trash_id)` 把 payload 寫回原列＋刪該 trash 列（table allowlist 防注入）。測試 `tests/test_trash.py`。
- **4 個刪除點**（瀏覽頁三表／收文／刑案／一般）清空 `UPDATE` 前一律先 `snapshotRow`＋`writeTrash`，與業務刪除同一 transaction。
- **入口（設定 Tab6 子頁「資源回收筒」，僅 admin 可操作）**：唯讀單選表（刪除時間／文號／類別／主旨／對象人／刪除身分）＋關鍵字過濾（比對主旨＋對象人）＋「⟳ 重整」「↩ 還原」鈕。**歸檔管理（archive）看得到該 nav 鈕但反灰停用**（`setVisible(True)`＋`setEnabled(is_admin)`，配 `_NAV_INACTIVE` 的 `:disabled` 灰字樣式，與設定頁其他維護功能對 archive 的處理一致）；user 進不了設定頁故無此鈕。還原寫一筆「還原」稽核。
- **保留策略**：永久保留，跨年度 Reset 一併清空（`performYearEndReset` 含 `DELETE FROM Trash_Documents`）。
- **還原保留歸檔狀態**：快照含 `is_reported`／`is_electronic`，原本已歸檔的資料還原後仍為已歸檔、不回待歸清單。清空式刪除不刪實體 PDF，實體檔通常仍在；若刪除到還原間 PDF 被外部移除，還原的檔名會指到不存在的檔。
- ⚠️ **還原後刷新（踩雷）**：`restoreFromTrash` **必須排除 `last_modified`**，讓 update trigger（`WHEN NEW.last_modified IS OLD.last_modified`）自己蓋成當下時間；若寫回快照舊值，trigger 不觸發、瀏覽／歸檔頁的指紋偵測不到。另以旗標 `_pending_reload_keys` 通知瀏覽／歸檔頁，切過去時 `on_activated` 走 `_forceReload`（`runWithBusy` popup→全量重建），符合「先切過去→popup→刷新」慣例（`main.py` 給各 tab 加 `_manager` back-ref 供 sibling 取得）。

### 別名（alias）

- 別名是「人的屬性」，存在 `Ref_Personnel.alias` 欄，分隔符為**半形逗號**，多別名同欄（如 `王佐,所長,副座`）
- 否決新表 `Ref_Alias`：別名跟著人走，跨年度重編 id 時 alias 自動保留，無需額外關聯
- 歸檔比對（`lib/archive_text.py`）從 DB 讀別名後與正名一同納入 `_loadNameDict`；移除舊 `tab_archive._ALIAS` hardcode dict
- 欄位以一次性 `ALTER TABLE ADD COLUMN` 新增（見 §5「新增 DB 欄位」,v1.0.2 起內建於 `dbfile.db`）；讀寫前呼叫 `_has_alias_col(conn)` 做 PRAGMA 缺欄退路，避免舊 DB 報錯


### 資料庫瀏覽（Tab4）搜尋設計

**全量載入 + `setRowHidden` 模式**（非搜尋重建表格）：

- `_reload(key)`：DB 全量抓取，所有非軟刪除列全部 `insertRow`，存入 `_allRows[key]`（row dict 列表，與表格列 1:1 對應）+ `_docorder[key]`（doc_id 列表）。**不做關鍵字過濾**
- `_applyFilter(key)`：讀 `_allRows[key]`，對每列計算是否命中當前 kw/scope，結果存 `_matchedCols[key]`，呼叫 `_applyRowVisibility`
- `_applyRowVisibility(key)`：單一 pass，同時考慮搜尋 filter（`_matchedCols`）和逾期篩選（vertical header item `Qt.UserRole`），`setRowHidden` 決定每列可見；最後呼叫 `_updateFooter`
- `_applyOverdue(key)`：僅呼叫 `_applyRowVisibility`（不獨立重算）
- 搜尋框 / 範圍下拉觸發 `_applyFilter`，**不觸發 `_reload`**；`_reload` 只在 Tab 切換且指紋改變時呼叫（或 `_diffUpdate` fallback）

**比對方式**：`kw.lower() in str(值).lower()` 的**子字串包含、不分大小寫**（非模糊比對；中文不受 `.lower()` 影響，只惠及英數）；選了範圍下拉只比該欄，否則比所有 `search:True` 欄。

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
- **身分判斷**用 `AuthManager.instance()` 的便捷方法：`is_admin()`（最高權限）／`is_manager()`（admin or archive，歸檔管理也能做的功能用）／`is_archive()`／`actor_name()`（稽核 operator 用）；勿再各處寫 `current_role == '…'` 字串比較
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
│   ├── app_lock.py      APP 層軟性互斥（dbfile.lock 鎖檔讀寫/失效判斷，純邏輯可單測）
│   ├── db_backup.py     平時自動備份（啟動時 GFS 輪替：每日留 7＋每週留 4，本機 backups/，純邏輯可單測）
│   ├── db_schema.py     啟動冪等建表 ensureSchema（附加式結構：_TABLES 建表＋_COLUMNS 加欄，見 §5）
│   ├── archive_text.py  歸檔比對純文字/檔名工具（_tokenize/_parseDate/_pkOf/_sanitize/_trimName/_resolveNames/_parseSubject；自 tab_archive 抽出，可單測。承辦人/主旨解析需餵 DB 人名字典）
│   ├── theme.py         全域 QSS（Apple HIG 風格）
│   ├── version.py       版本號單一來源（__version__；進版只改這裡，主選單顯示自動同步）
│   └── loading_screen.py
├── layouts/             所有 .ui 檔（Layout1~7、main_menu）
├── res/                 圖片 / SVG / qrc（含 __init__.py，是 package）
│   ├── resources.qrc / resources_rc.py
│   ├── buttons/         所有圖片資產（qrc 內嵌：arrow/icon_*；HELP 真按鈕圖；
│   │                    及走 getResourcePath 的 banner.png / police_badge.*）
│   ├── tabs/            HELP 子頁籤圖（qrc 別名 :/tab/，gen_buttons.py 產出）
├── tabs/                各 Tab
├── ui_utils/            共用 UI 工具（table/widgets/status/sticky_scroll/edit_dialog/settings_dialogs/help_dialog/help_content；button_imgs 為 gen_buttons 產出對照表）
├── tools/               開發／維運工具腳本（入庫，皆從專案根目錄執行；不被核心模組 import）
│   ├── bump_version.py     進版（改 lib/version.py ＋產 version_info.txt，見 §8）
│   ├── gen_buttons.py      產 HELP 按鈕／子頁籤 SVG（見 §5）
│   └── gen_quickstart.py   產速查卡 PDF（見 §5）
└── tests/               純邏輯單元測試（unittest，見下「單元測試」節）
```

> `tools/` 各腳本錨定 repo 根（`bump_version` 與 CWD 脫鉤、`gen_*` 抓 `__file__` 上一層），但**一律從專案根目錄執行**（`python tools/bump_version.py …`）。皆不 import 核心模組。
> 一次性／現場交付腳本（`fix_audit_setup.py`／`fix_cat_status.py`／`seed_*.py`）刻意**不入庫、留根目錄**：`fix_*` 會打包成 exe 發給現場放 `dbfile.db` 旁執行（靠「找腳本旁的 db」邏輯，不可改），`seed_*` 為本機壓測／塞假料丟棄腳本。

> 核心模組（db_utils、base_tab、auth_manager、theme、loading_screen）在 `lib/`，本文其餘章節為精簡仍以簡稱（如「db_utils」）指稱，實際 import 路徑為 `from lib.db_utils import ...`。`main.py`（入口）與上述獨立工具留根目錄，互不 import 核心模組。

### 路徑解析（getResourcePath，打包相容）

- `db_utils.getResourcePath(rel)`：開發時從當前目錄找，打包後從 `sys._MEIPASS` 找
- `dbfile.db` 特殊：永遠從 exe 所在目錄讀（真實資料，不打包進 exe）
- `.ui` 用 `getResourcePath("layouts/Layout1.ui")`、圖片用 `getResourcePath("res/buttons/banner.png")`
- `arrow.svg` 走 qrc 虛擬路徑 `:/arrow.svg`，**不經過 getResourcePath**
- ⚠️ `res/` 是 package（有 `__init__.py`），`resources_rc` 用 `from res import resources_rc`
- ⚠️ `lib/` 是 package（有 `__init__.py`），核心模組用 `from lib.db_utils import ...` 等
- ⚠️ `getResourcePath` 用「當前工作目錄」（`os.path.abspath('.')`）找 dbfile.db，**不是** `__file__`，所以 **程式務必從專案根目錄啟動**（`python main.py`），打包後則是 exe 所在目錄
- ⚠️ 改了任何 qrc 內的 SVG，要重編：`cd res && pyside6-rcc resources.qrc -o resources_rc.py`

### 單元測試（tests/）

純邏輯回歸測試，**不碰 GUI**（容器無法跑 Qt 視窗，故只測無視窗依賴的純邏輯）。

- **跑法**（專案根目錄）：`python -m unittest discover -s tests`
- **命名**：檔案 `test_*.py`（unittest 自動探索的預設規則，勿改名）
- **環境**：`test_db_utils` / `test_status` / `test_auth_manager` / `test_error_msg`（受測 `db_utils`）/ `test_audit`（受測 `db_utils`）/ `test_audit_view` 的受測模組 import 時會載入 PySide6，故**執行環境需裝 PySide6**；`test_archive_text` / `test_app_lock` / `test_db_backup` 是純 stdlib
- **涵蓋**：歸檔檔名解析（`archive_text`：日期/PK/斷詞，含 PK 撞號雷）、流水號/跨年度重置/設定/歸檔定位（`db_utils`）、逾期計算與狀態色（`status`）、權限與密碼（`auth_manager`）、錯誤訊息白話化（`db_utils.friendlyErrorMessage`，`test_error_msg`）、稽核寫入 helper（`db_utils` 的 `buildDetail`／`auditStaffName`／`writeAudit` round-trip，`test_audit`）、操作紀錄解析（`tab_audit.parseDetail`，`test_audit_view`）、軟性互斥鎖檔（`app_lock`：parse/is_stale/is_mine）、平時自動備份（`db_backup`：每日/每週到期/修剪＋backup round-trip）。另有 `test_no_pii` 防個資外洩（見 CLAUDE）
- **紀律**：動到可單測的純邏輯（解析、SQL round-trip、狀態計算、權限判斷）時，**一併新增/更新對應測試**；GUI 互動部分仍須上機驗證

---

## 5. 操作手冊（要改特定東西時查）

### 結構變更原則（附加式走 ensureSchema、破壞式才手動）

結構變更分兩類，界線分明：

- **附加式（建表／加欄，只增不改）→ 啟動時冪等 `ensureSchema`**（`lib/db_schema.py`）：開程式時自動 `CREATE TABLE IF NOT EXISTS`／「缺欄才 `ADD COLUMN`」，各語句獨立 try、失敗只記 error.log、絕不擋開程式。新表／新欄登記進 `db_schema._TABLES`／`_COLUMNS`，**全新安裝與舊庫第一次開都自動長齊，現場免再發 fix 腳本**。目前註冊 `Audit_Log`、`Trash_Documents`。在 `main.py` 啟動序列（鎖檔後、自動備份前）呼叫一次。**forward-only**：只前瞻維護結構，不做回溯自愈（不補密碼、不改舊資料）。
- **破壞式（改型別／改既有資料／改 View）→ 一次性手動**（不自動跑）：`ALTER TABLE` 改欄、資料修補、`DROP VIEW IF EXISTS … CREATE VIEW …` 仍走手動腳本對 `dbfile.db` 執行，不寫進啟動流程。

> 為何不全交給啟動 migration：重型版本化 migration 對單機自管版本價值不成立；但「冪等建表／加欄」零風險又便宜，交給 `ensureSchema` 反而比「忘了跑 fix → 功能靜默退化」更安全。破壞式變更才需謹慎、維持手動。

舊式「PRAGMA 缺欄退路」仍可用於程式碼讀寫可能尚未存在的欄位（現行 alias 欄即如此，見 `ui_utils/settings_dialogs.py`）：

- 程式碼讀寫可能尚未存在的欄位前，用 **PRAGMA 缺欄退路**保護，確保未套用變更的舊 DB 不會報錯（現行 alias 欄即如此，見 `ui_utils/settings_dialogs.py`）：

```python
def _has_alias_col(conn):
    """欄位是否存在。未加欄的舊 DB 跳過讀寫。"""
    return any(r[1] == "alias"
               for r in conn.execute("PRAGMA table_info(Ref_Personnel)"))
```

### 新增 Tab 的標準流程

1. 新增 `tabs/tab_xxx.py`，`class TabXxx(BaseTab)` 實作 `setup(tab_index)`
2. `tabs/__init__.py` 加 `from .tab_xxx import TabXxx`
3. `main.py` 的 `TAB_CLASSES` 登記一行（其餘不動）
4. 新增對應 `layouts/LayoutN.ui`（**每個大 Tab 都必須有 .ui，無例外**；彈窗 / Dialog 才用 code 動態建）
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
| 重建/差異更新表格時保留捲動位置 | `widgets.py` 的 `preserveScroll(table, func)`：執行 func 前記下 `verticalScrollBar().value()`，func 後以 `QTimer.singleShot(0,…)` 還原並 clamp 到當下 maximum。已用於瀏覽 `_diffUpdate`/`_reload`、歸檔 `_diffDocs`/`_loadDocs`/`_rematch`、設定 `_renderSortTable`、操作紀錄 `_populate`。輸入暫存預覽表（交辦發/收文、陳報）刻意維持 `attachStickyScroll` 捲到底，不套此 helper |

### 通用彈窗（db_utils）

```python
from db_utils import msgInfo, msgWarning, msgCritical, confirmBox
```

| 函式 | 按鈕 |
|------|------|
| `msgInfo / msgWarning / msgCritical(title, text)` | 確定 |
| `confirmBox(title, text, confirm_text, cancel_text, confirm_danger, default_confirm, informative, min_width)` | 自訂，回傳 True=確認 |

> `confirmBox` 的 `informative`：次要說明，呈現 Apple HIG 兩層式（主訊息深色＋次要灰字 `#6b6b6e`，同為 14pt）。⚠️ Windows 的 `QMessageBox` 不會自動把 `informativeText` 縮小／變灰（那是 macOS 原生行為），故內部改用 rich text 自排版。`min_width`：撐出最小內容寬度(px)供長檔名等不換行用（於 grid layout 末列塞 spacer；超長仍會自動換行，不會無限拉寬），內容短的彈窗不要設、用自動寬度。

### 修改功能（EditDialog）

- 在 `ui_utils/edit_dialog.py`，動態產生表單，不用 .ui
- `TaskEditDialog`（Tab0/1）、`CriminalEditDialog`（Tab2 刑案）、`GeneralEditDialog`（Tab2 一般）
- 觸發：點預覽表編號欄超連結
- 三彈窗共同繼承 `_BaseEditDialog`，版面常數集中於基底：`_LABEL_W=120` / `_FIELD_W=340` / `_MARGIN=40`，`setMinimumWidth = LABEL_W+FIELD_W+MARGIN = 580`
- 刪除列後需重新綁定刪除鈕與編號 QLabel 的 row index（參考 `_rebindDocIdCell`）
- **歸檔狀態區塊（僅 admin）**：`CriminalEditDialog`/`GeneralEditDialog` 表單末端、儲存鈕上方有「歸檔狀態」分組框（`_build_archive_group`；dbbrowse 與 archive 兩頁共用同一 dialog，一改兩頁生效）。紙本 `is_reported` 用 checkbox 雙向可勾消；電子檔 `is_electronic` 只能「清除」（popup 產不出 PDF，故僅提供退回未歸，清空後該筆自動回歸檔頁待歸清單），不動實體 PDF（留孤兒檔，重歸時 rename 覆蓋）。長檔名用 `_ElidingLabel`（`ElideMiddle` 隨寬度中段省略）不撐破版面。清除為標記 pending，按「儲存」才真寫 `is_electronic=''`、取消（reject）則還原；儲存同時寫回 `is_reported`。非 admin 不建立區塊（`self.w_arch_reported=None`，save 跳過這兩欄）

> ⚠️ 歸檔頁 `_doArchive` 寫入 PDF 檔名時**一併設 `is_reported=1`**（`SET is_electronic=?, is_reported=1`）：電子檔歸了，紙本必然也已歸，故連帶標記，免使用者再手動補勾（v1.0.7 修正，原本只寫 `is_electronic`）。

### 程式內 HELP（各頁說明鈕，v1.0.8）

每個大 Tab 右上角一顆 help 線圖示鈕，點開該頁「使用說明」彈窗；各欄位／按鈕另附 tooltip。

- **內容單一來源** `ui_utils/help_content.py`：七頁說明以**結構化區塊** `HELP_PAGES` 描述（block 型別：`lead`/`muted`/`label`/`hint`/`warn`/`sec`，`sec` 內含 `p`/`ol`/`ul`/`map`/`table`/`cols`/`note`），由 `_render_html()` 產出彈窗 HTML、`render_review_text()` 產出純文字校稿（`docs/help_text_review.txt`，未入庫）。改說明文字只動 `HELP_PAGES`，兩種輸出自動同步。tooltip 候選存 `HELP_TIPS`。
- **彈窗元件** `ui_utils/help_dialog.py`：`helpDialog(parent, tab_index)` 以 `QTextBrowser` 顯示（白底、Enter/Esc 關、右上警徽 LOGO + 全寬鋼藍橫線）；`attachHelpButton(tab_widget, window)` 於 `main.py` tabs 建完後呼叫一次，掛上分頁列右上角 `setCornerWidget` 說明鈕（依 `currentIndex()` 開對應頁）並套 tooltip。
- **版面**：Apple HIG 留白編排，段落標題用**鋼藍細豎條＋下細分隔線**（`_h_header`，非滿版色帶），步驟序號用**實心鋼藍方塊白字**（`ol`），內文深黑 `#1c1c1e`。內文字距 `_LETTER_SPACING=92`（`help_dialog.py`）——⚠️ `QTextBrowser` 不吃 CSS `letter-spacing`，設在 `QFont` 上。⚠️ `QTextBrowser` 是 Qt rich-text 子集，**不支援圓角／陰影／flex／懸掛縮排**：色塊用單格表格 `bgcolor`、清單懸掛縮排用兩欄表格（標號欄 + 文字欄）達成。
- **按鈕／子頁籤示意圖**：說明文字裡的按鈕（如「確認發文」）與子頁籤（如「❐ 刑案陳報」）用**預烤圓角 SVG**（`<img>` 內嵌），因 `QTextBrowser` inline 樣式做不出圓角。SVG 由 `python tools/gen_buttons.py` 依 `BUTTONS`／`TABS` 清單批次產出至 `res/buttons/`（別名 `:/btn/`）與 `res/tabs/`（`:/tab/`），配色比照 `lib/theme.py` 烤進圖；對照表 `ui_utils/button_imgs.py`（label→路徑/寬高，入庫）供 `help_content` 查表。改標籤／配色改該腳本重跑、重編 qrc。⚠️ `QTextBrowser` 圖片點陣化解析度有上限（intrinsic 取 2× 已封頂），圖片**不會跟內文一樣銳利**；`font-family` 須用裸字型名（逗號清單會被 QtSvg 當成不存在字型 fallback）。
- **速查卡**：母本 `QUICKSTART`（`help_content.py`，七 Tab 濃縮，與 `HELP_PAGES` 同檔各自合身）；`python tools/gen_quickstart.py`（reportlab 嵌微軟正黑體，含 `_check_glyphs` 字形覆蓋率檢查）產 `docs/Quick_Start.pdf`（A4 直式 2 頁，`docs/` 未入庫）。改說明同時動到速查卡時，`QUICKSTART` 要一併同步。
- 圖示 `res/buttons/icon_help.svg`（鋼藍 #4977b1）走 qrc 內嵌（`:/icon_help.svg`），改了要重編 qrc。

### tab_report.py 特殊架構

- `Layout3.ui` 用 `QStackedWidget`（`formStack`）切換：index 0 刑案、index 1 一般
- 發文分類 radio 對應：刑案 `radio_status_a/b/c` → CS01/CS02/CS03；一般 `radio_gen_cat_a/b/c` → GC01/GC03/GC02
- ⚠️ **部分預覽顯示 ≠ DB 值**（現行行為，刷新時務必轉換，見下）：

| 項目 | 預覽 | DB |
|------|------|-----|
| 人名 | 王小明 | 王小明-19.06（去 `-` 後綴） |
| 日期 | MM-DD-YYYY | YYYY-MM-DD |

> 刑案發文分類／一般分類**已正規化**：`Ref_Case_Status.status_name`／`Ref_General_Category.gen_cat_name` 直接存兩字顯示名（現行/到案/未到、業務/其他/相驗），View 撈出即可顯示，不再經對照表轉換（舊 `_STATUS_MAP`／`_CAT_MAP` 已移除）。EditDialog `get_updated()` 回的分類欄即顯示名，直接套用。
> 現行犯判斷（簽收單列印「免簽收」註記）改以 `case_status` ID（`CS01`）比對，與顯示名脫鉤（見 `tab_print._build_*`）。

### 列印（tab_print.py）

- **簽收表產生走前景＋modal「產生中」popup**（`runWithBusy`），非背景執行緒。matplotlib 靠全域狀態運作，在背景 `QThread` 與主執行緒搶用會偶發崩潰／圖面錯亂，故 `generate_pages` 一律於主執行緒同步畫、期間以 popup 擋互動（單機 1～2 秒可接受）。⚠️ 勿改回背景執行緒跑 matplotlib。
- 用 **`QPrintPreviewDialog`**（PySide6.QtPrintSupport）跳原生預覽 + 列印選項視窗
- 不碰 PDF 檔案關聯（避免 WinError 1155），頁面以 **300 DPI 點陣化**送印（`_paint_pages` 把 PNG 畫到 QPrinter）
- 「儲存 PDF」按鈕仍走 matplotlib `backend_pdf`（向量），與列印獨立
- 跨版本相容：`setPageSize` 用 `QPageSize` 物件、頁面範圍用 `painter.viewport()`（避開 6.x enum 命名空間差異）
- **預設彩色＋長邊雙面**（v1.0.7）：開列印預覽前對 `QPrinter` 設 `setColorMode(QPrinter.Color)` + `setDuplex(QPrinter.DuplexLongSide)`，使用者仍可於預覽視窗改；實際支援取決於印表機
- **欄內文字換行用真實字型度量**（`_text_width_pt`，dpi=72 的 `RendererAgg`，像素即點）：`_wrap_clamp` 不再用「中文字當滿格 size＋0.86 經驗係數」估算——該估算偏窄，會害欄寬還夠的主旨／案類**提早折行**（臨界長度最明顯）。可用寬＝欄寬扣約 1.2×PAD。⚠️ 編號欄的 `_fit_font` 仍用舊估算（單行自動縮字、影響小，未在此改）。
- **刑案類型欄固定 10pt**（`_draw_page` 中 `is_crim and cidx==2`）：刑案案類名稱長短不一，短的 12pt／長的縮 10pt 會大小參差又壓迫，故刑案此欄一律 10pt（長案類縮後大小當天花板）。**一般陳報「業務單位」欄與交辦不受影響**，維持 12→10 自動縮。

### 簽收表標題自訂（tab_print／tab_settings／settings_dialogs）

簽收表 PDF 的三張表標題與現行犯註記**可由管理者自訂**，免改 code、免重 build。

- **存** `App_Settings` 四個 key：`print_title_task`／`print_title_crim`／`print_title_gen`／`print_note_current`（不需新表）。常數與預設集中在 `db_utils.PRINT_TITLE_KEYS`／`PRINT_TITLE_DEFAULTS`；列印一律 `db_utils.printTitle(db_path, which)`，**未設定回 `○○…` 預設**（舊庫零升級、空殼免改、PDF 不致空白）。預設機關名以 **`○○`** 佔位，不留真名。
- **入口**：設定頁（Tab6）左側 nav「**簽收表設定**」鈕 → `PrintTitleDialog`（四格整句可編輯＋「恢復預設」＋儲存）。**僅 admin**（`_onSetPrintTitles` 內 `is_admin` guard；`_applyRolePermissions` 對 archive `setEnabled(False)`，按鈕樣式含 `:disabled` 才會反灰，見 §2 雷）。儲存有變寫一筆 `CONFIG` 稽核。
- **字數上限**（`PrintTitleDialog._TITLE_MAX=36`／`_NOTE_MAX=14`）：實量 PDF 版面得出——標題列寬→36；現行犯註記在窄的簽收欄→14（註記 14 字已是版面極限）。配合「換行用真實字型度量」一起，標題不溢出頁面。
- **未設定警示**：任一 key 為空＝未設定（`db_utils.printTitlesUnset`）。列印頁（Tab3）頂部紅字「⚠ 簽收表標題未設定…」（`_refresh_title_warn`，`on_activated` 切入時刷新），純勸導、不擋產生（同歸檔哲學）。
- **跨年度重置不清這四個 key**（機關名稱是單位永久設定，`performYearEndReset` 只清 `archive_*`）。
- 純邏輯測試 `tests/test_print_titles.py`（預設 fallback／round-trip／未設定旗標）。

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

### 其他表

| 資料表 | 欄位 / 說明 |
|--------|------|
| App_Settings | key / value。權限相關 key：`admin_password_hash`（管理者密碼 SHA-256，預設 `admin`）、`archive_password_hash`（歸檔管理密碼 SHA-256，預設 `0000`；v1.1.0 起入庫空殼已內建，舊 DB 缺此 key 才須跑 `fix_audit_setup.py` 補）。另有 `archive_root`/`archive_subdir_crim`/`archive_subdir_gen`（歸檔路徑，Reset 時清空） |
| Audit_Log | log_id（PK AUTOINCREMENT）/ ts / role / action / target_table / target_id / operator / detail。操作紀錄；由 `ensureSchema` 啟動冪等建立（缺表時 `writeAudit` 靜默跳過）。詳見 §3「稽核 log」 |
| Trash_Documents | trash_id（PK AUTOINCREMENT）/ table_name / doc_id / payload（刪除前整列 JSON 快照）/ subject / doc_person / deleted_ts / deleted_role。誤刪還原回收筒；由 `ensureSchema` 啟動冪等建立（缺表時相關 helper 靜默跳過）。詳見 §3「誤刪還原」 |

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
del /q Police-Document-Manager.spec 2>nul & rmdir /s /q build dist 2>nul & pyinstaller --clean --onefile --windowed --icon=res/buttons/police_badge.ico ^
  --version-file version_info.txt ^
  --add-data "layouts/*.ui;layouts" ^
  --add-data "res/buttons/police_badge.svg;res/buttons" ^
  --add-data "res/buttons/banner.png;res/buttons" ^
  --hidden-import PySide6.QtPrintSupport ^
  --hidden-import lib.db_utils ^
  --hidden-import lib.base_tab ^
  --hidden-import lib.auth_manager ^
  --hidden-import lib.app_lock ^
  --hidden-import lib.db_backup ^
  --hidden-import lib.db_schema ^
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
- `arrow.svg` / `icon_pdf.svg` / `icon_archive.svg` / `icon_paper.svg` / `icon_help.svg`（共用 icon）及 `res/buttons/*.svg`（HELP 真按鈕圖，別名 `:/btn/`）、`res/tabs/*.svg`（HELP 子頁籤圖，別名 `:/tab/`）已透過 `resources_rc.py` 內嵌，不需 `--add-data`；改了要重編 qrc（`pyside6-rcc res/resources.qrc -o res/resources_rc.py`）
- `res/buttons/*.svg`（真按鈕）與 `res/tabs/*.svg`（子頁籤）由 `python tools/gen_buttons.py` 依 `BUTTONS`／`TABS` 清單批次產出（同時更新對照表 `ui_utils/button_imgs.py`）；改了標籤／配色改該腳本重跑，再重編 qrc
- 列印用 `QtPrintSupport`，加 `--hidden-import PySide6.QtPrintSupport` 保險
- matplotlib 只用 `backend_agg`（PNG）+ `backend_pdf`（存 PDF），其餘 backend 全排除
- 結構重組後 `.ui` 進 `layouts/`、圖片進 `res/`，`--add-data` 路徑要對應第二參數（解壓目標目錄）
- 指令開頭 `del ...spec & rmdir build dist` 是刻意的：開發期不信任殘留 spec（會用到上次的過期設定），每次砍掉 spec / build / dist 用乾淨 CLI 參數全新生成。`2>nul` 讓首次執行（檔案不存在）不報錯
- **跨年度重置的自動重啟**：onefile 版重啟新程序前必設環境變數 `PYINSTALLER_RESET_ENVIRONMENT=1`（PyInstaller 6.10+ 官方機制），否則新程序沿用舊 `_MEI` 環境、到已刪除的暫存目錄找 `python3xx.dll`/標準庫而崩潰（`Failed to load Python DLL` / `unicodedata` 缺失）。`_restartApp()` 已處理。詳見第 2 節踩雷表與第 5 節 Reset 子節
- 若打包後報 `No module named res`，加 `--hidden-import res.resources_rc`
- 核心模組在 `lib/`，主程式打包已列 `--hidden-import lib.*` 十個（含 `lib.archive_text`、`lib.app_lock`、`lib.db_backup`、`lib.db_schema`）；若仍報 `No module named lib.xxx`，補對應的 hidden-import
- GitHub release 上傳用英文檔名
- **exe 檔案資訊（右鍵→內容→詳細資料）**：由 `--version-file version_info.txt` 帶入。`version_info.txt` 不在 build 時生成，而是**進版時由 `tools/bump_version.py` 連同版號一起產生**（見 §8 進版），已收進 git。打包只需引用、不用多做。要改顯示文字（公司/產品名）改 `tools/bump_version.py` 頂部常數

---

## 8. 版本記錄

> 版本號單一來源為 `lib/version.py` 的 `__version__`。**進版一律用 `python tools/bump_version.py <版號>`**（版號自帶，不自動進位；執行前會先印出目前版號），它會同時改 `version.py` 與產出 `version_info.txt`（exe 檔案資訊）；標題列與主選單顯示自動同步。本表與 git tag（`v{__version__}`）需手動對齊。⚠️ 勿手改 `version.py`，否則 `version_info.txt` 不同步。

| 版本 | 摘要 |
|------|------|
| v1.1.1 | **誤刪還原（資源回收筒）**：主表刪除（清空保留 doc_id）前先把整列快照存入 `Trash_Documents`，設定頁新增「資源回收筒」子頁（僅 admin）可單選還原，把快照寫回原文號、保留刪除當下歸檔狀態，並寫一筆「還原」稽核；跨年度 Reset 一併清空回收筒。**啟動冪等建表 `ensureSchema`**（`lib/db_schema.py`）：附加式結構（建表／加欄）改於啟動時自動套用，新增資料表不再需要發 fix 工具叫現場手動跑（破壞式變更仍走一次性手動）。**操作紀錄頁介面整理**：新增「重整」鈕（強制重查）、身分／類別下拉去除外部標籤改首項自述、篩選列字級收斂。**主選單顯示修正**：打包版偶因 Windows 前景鎖被其他視窗壓住，改在顯示後強制拉到最前。另含一輪 code review 修正（DB 連線改 `finally` 釋放、刪除入口補權限檢查、`_trimName` 收斂單一實作）。 |
| v1.1.0 | **稽核大版本（特別版，含現場升級工具）**。**三角色權限＋操作稽核**：新增 `user`／`archive`（歸檔管理）／`admin` 三角色（兩組密碼），關鍵操作寫 `Audit_Log` 操作紀錄，新增「操作紀錄」檢視 Tab7（僅 admin、可篩選／匯出 CSV）。**效能**：瀏覽頁 cellWidget 改純 item＋啟動預載建表（載入畫面進度條，主選單出現時主視窗已就緒）。**安全性**：錯誤訊息白話化（全域 handler 套 `friendlyErrorMessage`）、搜尋不分大小寫、閒置 10 分自動登出＋閒置 20 分自動關閉、APP 層軟性互斥（`dbfile.lock` 勸導，多機共用網路碟時提醒）。**平時自動備份**：啟動時 GFS 輪替（每日留 7／每週留 4，本機 `backups/`，`lib/db_backup.py`）。**主選單**改 2 欄圖示磚格；dev 工具收進 `tools/`。⚠️ 升級舊庫前置：先 `fix_cat_status`（未套過 v1.0.9 者）再 `fix_audit_setup`（建 `Audit_Log`＋設兩組密碼），否則稽核不寫、退化為單一 admin。 |
| v1.0.9 | **發文分類／案件狀態正規化**：`Ref_Case_Status`／`Ref_General_Category` 的顯示名去除歷史字母前綴、縮為兩字（A_現行犯→現行、D_業務陳報→業務…），View 撈出即顯示，移除程式端 `_STATUS_MAP`／`_CAT_MAP` 兩層轉換；簽收單列印「現行犯免簽收」判斷改以 `case_status` ID（`CS01`）比對、與顯示名脫鉤。收編 5 筆未正規化的 `H_核銷` 孤兒分類（併入「業務」GC01、業務單位補「行政組」）。一次性資料修補 `fix_cat_status.py`（執行前自動備份、不入庫）。**HELP 視覺優化**：說明內按鈕／子頁籤改用預烤圓角 SVG（`gen_buttons.py` 產出、對照表 `ui_utils/button_imgs.py`）、文字校正；`res/` 圖片資產集中到 `res/buttons/`＋`res/tabs/`。 |
| v1.0.8 | **程式內 HELP**：每個大 Tab 右上角新增 help 說明鈕（線圖示），點開該頁「使用說明」彈窗（七頁內容，Apple HIG 留白編排、鋼藍色帶標題、右上警徽 LOGO）；各欄位／按鈕加 tooltip。內容單一來源 `ui_utils/help_content.py`（結構化 `HELP_PAGES`，同時產彈窗 HTML 與純文字校稿）；彈窗元件 `ui_utils/help_dialog.py`。新增圖示 `res/icon_help.svg`（qrc 內嵌）。**協作文件**：CLAUDE.md 補「一律台灣用語」。 |
| v1.0.7 | **歸檔頁**：PDF 電子檔歸檔成功時連帶標記紙本已歸（`_doArchive` 一併寫 `is_reported=1`，原本只寫 `is_electronic`）；「待歸檔公文」清單選取列改藍底深藍字＋列首單條藍 bar，消焦點黑框，候選 PDF 表游標維持箭頭（不顯示 I-beam）。**簽收單列印**：開列印預覽前預設彩色（`setColorMode(Color)`）＋長邊雙面（`setDuplex(DuplexLongSide)`），使用者仍可改。 |
| v1.0.6 | **歸檔頁**：修正承辦人解析會把案由詞（如「竊盜案」）與括號內報案人誤判成承辦人之 bug。承辦人界定改為「從檔名尾端往前、能對到 DB 人名字典（含去姓 2 字／別名）才收為承辦人，對不到即停」，不再用「3 字以內一律當人名」猜測；主旨剝承辦人改字典迴圈（修正多個 `-` 分隔承辦人只剝最後一段、前段人名殘留主旨之 bug）。承辦人／主旨解析純邏輯抽進 `lib/archive_text.py`（`_resolveNames`/`_parseSubject`），新增單元測試（含真實檔名語料去識別化案例）。 |
| v1.0.5 | **歸檔頁**：確認歸檔／只歸紙本後不再清空 PK 編號搜尋（改為刷新待歸檔清單＋候選 PDF，保留搜尋狀態）；歸檔成功不再跳提示（僅失敗才提示）；確認彈窗改 Apple HIG 兩層式（主訊息＋灰字次要說明）、文字精修，確認歸檔加寬以容長檔名；修正「只歸紙本」確認框誤顯示承辦人而非主旨之 bug。**全頁**：所有捲動表格在資料新增／刪除／修改後保留捲動位置，不再跳回頂端（瀏覽 Tab4、歸檔 Tab5 待歸檔＋候選 PDF、設定 Tab6 參照表）；輸入暫存預覽表維持原本捲到底行為。**協作文件**：CLAUDE.md 補「開新對話先讀 README」。 |
| v1.0.4 | **瀏覽／歸檔頁**：新增「重載」鈕（強制重掃資料夾＋整表重建）；設定改參照表名稱後自動就地反映（零重建成本）；重載與大量差異更新顯示「更新中」提示（`runWithBusy`）；歸檔頁關鍵字改為檔名過濾；搜尋 `setUpdatesEnabled` 改 try/finally 避免凍結；精簡／完整改單顆切換鈕（預設精簡）。**設定頁**：三表與修改彈窗改顯示序號（隱藏內部 PK，並修正修改誤用序號當 PK 之 bug）；歸檔資料夾設定白話化、子夾下拉提示；`toUncPath` 以 `WNetGetConnection` 解析網路磁碟機代號為 UNC；重置後首登提示歸檔未設定；ResetDialog 停用清單可捲動。**其他**：標題列＋exe 內容頁顯示版本號（`bump_version.py` 進版工具）；瀏覽頁空表浮水印 viewport size=0 修正；歸檔檔名解析強化（黏連日期、車牌連字號、承辦括號）；陳報子頁籤多餘基準線移除。 |
| v1.0.3 | 公文陳報頁（Tab3）改版：刑案／一般陳報合併為單一表單版面，切換時欄位位置、寬度、高度一致不跳動；下方左右預覽表高度對齊；輸入欄與下拉欄高度統一；案件分類／查獲受理日期灰字不再影響下拉清單與月曆。 |
| v1.0.2 | 設定頁拖拉排序（移除四顆排序鈕）；人員別名欄（`Ref_Personnel.alias`，歸檔比對一併納入）；歸檔根目錄未設定三層警示；瀏覽 Tab4 搜尋改為全量載入＋`setRowHidden`，大幅提升搜尋速度。 |
| v1.0.1 | 人員別名初版（alias 欄）；設定頁人員清單加別名欄；歸檔比對從 DB 讀取別名。 |
| v1.0.0 | 正式版。瀏覽頁（Tab4）有歸檔檔名者顯示圖示鈕可直接開 PDF；歸檔資料夾設定存 UNC 路徑（Tab6）；歸檔頁（Tab5）自動帶入預設資料夾。 |
