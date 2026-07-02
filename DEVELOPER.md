# 公文管理系統

Windows 桌面應用，PySide6 + SQLite，管理警察單位公文（交辦單、刑案陳報、一般陳報）。

---

## 0. 給接手者

協作規定與偏好見 [CLAUDE.md](CLAUDE.md)（Claude 開新對話時會自動載入）。本檔為技術文件、按需查閱，每節開頭點明用途。

---

## 1. 架構心智模型

### 進入點與流程

```
main.py
  └─ loading_screen（載入 .ui、註冊 qrc）
      └─ MainMenu（主選單，選要進哪個 Tab）
          └─ DocumentManager（主視窗，建立 8 個 Tab）
```

- `DocumentManager.TAB_CLASSES`＝`{index: TabClass}`，新增 Tab 在此登記
- 每個 Tab 繼承 `BaseTab`，必須實作 `setup(tab_index)`；可 override `get_tables()`／`get_focus_widget()`／`on_activated()`
- **8 個大 Tab（index 0–7）**：交辦發文／交辦收文／公文陳報／簽收單列印／資料庫瀏覽／檔案歸檔／資料庫設定／操作紀錄；類別見 `tabs/`，各對應一個 `layouts/LayoutN.ui`
- **主選單**（`main_menu.ui`）為 2 欄圖示磚格（QToolButton），圖示 `res/buttons/menu_*.svg`（qrc 別名 `:/menu/`）於 `main.py` 以 `QIcon` 套用（避開 QUiLoader 解析 .qrc 的問題）
- ⚠️ **主選單拉到最前**：打包版偶因 Windows 前景鎖，`MainMenu` 的 `exec()` dialog 被壓到別視窗後。修法 `QTimer.singleShot(0, …)` 在 exec 進事件迴圈後 `raise_()`＋`activateWindow()`＋清最小化（`main.py` `_on_data_ready`）

### 資料流

- **三張主表**：`Document_Task`（交辦）、`Document_Criminal`（刑案）、`Document_General`（一般）
- **三個 View**：`View_Task_Full` 等，JOIN 參照表＋算狀態，給預覽／列印／瀏覽用
- **參照表**：人員／部門／案類／案件狀態／一般分類（見 §6）
- 主表存參照表的 **ID**（VARCHAR 字串，非真外鍵），顯示時 JOIN 出名稱

### Tab 切換與刷新（`main.py` `_onTabChanged`）

切換**後**做三件事：①從設定 Tab 切走→ `settings_tab._promptUnsaved(context="leave")` 處理未存排序，若 `_ref_dirty` 則對其他所有 Tab 設 `_ref_changed=True` 並 `on_activated()` 刷新下拉；②切到設定 Tab → `on_activated()` 重載當前子頁；③autoresize 表格＋設焦點。

> ⚠️ **Qt 限制**：`QTabWidget.currentChanged` 是「切換**後**」才發出，無法切換前攔截。離開大 Tab 的未存提醒只能「切過去後補跳」；設定 Tab 內部子頁切換（按鈕觸發）才攔得住、可「取消＝回原狀」。

### 瀏覽／歸檔頁的三層刷新（避免大表頓挫）

兩頁各約 700+ 列，重建 cellWidget 是成本所在。依「變動性質」分三條路徑：

1. **參照改名（人員／部門／案類）→ 就地輕量更新**：設定頁改參照表時 `_ref_changed=True`，`on_activated` 走 `_refreshRefCells`（瀏覽）／重載小清單（歸檔），只對標記欄 `setText`、不重建列（700 列 ~20ms）。⚠️ 指紋只看 `last_modified`、碰不到改名，故必走此旗標路徑（見 CLAUDE 踩雷表 #7）
2. **跨頁增／修／刪 → 指紋差異更新**：比對 `(COUNT, MAX(last_modified))`，變了才 `_diffUpdate`／`_diffDocs` 重建變動列；變動列數 `>= _BUSY_ROW_THRESHOLD`（預設 100）才跳「更新中」
3. **手動「重載」鈕**：強制整表重建（瀏覽）／重掃資料夾＋重比對（歸檔），是面對外部變動（外部新增／改名 PDF）的逃生口

> **啟動預載**：載入畫面期間 `LoadWorker` 背景預讀三表完整資料（`queryBrowseRows`，純 SQL 可跨執行緒），主執行緒於 `DocumentManager.__init__` 以 `buildInitial` 分段建好主視窗（進度條 `LOAD_STEPS`／`BUILD_STEPS`，見 `lib/loading_screen.py`），主選單出現時主視窗已就緒，建完設 `_loaded=True`，之後沿用上述指紋／diff 機制。
> **建表成本**：刪除欄（✕）、編號欄、無 PDF 的主旨欄一律純 `QTableWidgetItem`，點擊以 `cellClicked` 攔（`_onDeleteCell`／`_onLinkCell`）；只有刑案／一般「有真實 PDF 檔名」的主旨列保留 cellWidget（PDF 圖示鈕）。交辦單每列 0 個 cellWidget。⚠️ 建表在主視窗 show 之前（viewport 寬=0），欄寬靠 `autoResizeTable` 重試補正。
> 「更新中」提示走 `ui_utils.runWithBusy`（同步阻塞前 `show + repaint` 強制畫出，有最短顯示時間避免一閃即逝）。

---

## 2. 踩雷速查表

見 [CLAUDE.md](CLAUDE.md)（動手前必掃）。

---

## 3. 慣例與設計決策

### 軟刪除（is_active）

- **人員／部門／案類**用 `is_active` 軟刪除（停用不真刪），保留 ID 對應（歷史資料仍引用得到）、只是不出現在下拉
- 詞彙：人員「在職／離職」，部門／案類「啟用／停用」
- 設定 Tab 列表顯示停用項目（**灰字 `#aeaeb2`**），下拉排除（`WHERE is_active=1`）
- 停用／啟用一律進「修改」Dialog 勾 checkbox 切換，無獨立停用按鈕

### 排序（sort_order）

- 人員／部門／案類三表有 `sort_order`，**下拉與列表一律 `ORDER BY sort_order`**（非 ID），讓顯示順序跟 ID 脫鉤、可手調
- 設定 Tab 以**拖拉列**調整（`_RowDragFilter` 攔 `QEvent.Drop`、手動換列），hint label 提示可拖。⚠️ `QTableWidget.InternalMove` 只移 cell 不移 row，不可用
- **暫存模式**：排序在記憶體操作，「儲存排序」鈕初始 disabled、拖拉後才亮；儲存才寫回 DB（連續整數重編）並設 `_ref_dirty=True`
- 未存排序時切子頁／切大 Tab／按修改會跳確認；取消行為：按鈕觸發的（修改、子頁）回原狀，大 Tab（攔不住）放棄
- 新增項目放最前（`MIN-1`）
- 「儲存排序」成功不跳提示，按鈕反灰即代表已存（2026-07）

#### 指定位置（2026-07 新增，三條路徑共用一套搬移邏輯）

長清單拖到遠處費力，且新增只能固定塞最前。除拖拉外，再開兩條「打數字」路徑，三條都收斂到同一個 `tab_settings._moveRow(key, src, dst)`（記憶體 list 重排＋設 dirty＋亮儲存排序鈕＋重繪＋選列）：

1. **既有列「序號」欄改可編輯**：**單擊**框中數字即進編輯（`_onCellClicked`→`editItem`；`_SeqEditDelegate` editor 限定只能打數字），Enter/離焦套用。名稱等其餘欄維持**雙擊**開修改對話框（`_onCellDoubleClicked`）。兩條路徑皆有 `_refEditable()` guard。合法範圍 1～N（N＝目前筆數）；**不合法不跳警告，安靜跳回原數字**。視覺上欄位常駐淺底色＋虛線框提示可編輯，呼應 ⠿ 拖拉把手欄的既有手感
2. **新增/修改對話框加「順序」欄位**：新增時選填（留空＝沿用 `MIN-1` 塞最前，邏輯不變），合法範圍 1～(N+1)；修改時必填、預填目前位置，合法範圍 1～N。**打錯紅框＋擋確認**（比照姓名必填的既有驗證手法），跟既有列「打錯安靜跳回」不同——新增/修改走的是一次性表單送出，紅框比靜默更明確。欄位右側標合法範圍提示（新增「（選填，1～N）」、修改「（1～N）」），N 於 `_build` 查 `COUNT(*)` 得出，數字對齊上述驗證範圍
3. 兩個驗證函式（純邏輯，`tests/test_ref_sort.py`）都放在 **`ui_utils/settings_dialogs.py`**（`_parseSeqMoveTarget`／`_parseAddPosition`），不是 `tabs/tab_settings.py`——`tabs/` 本來就依賴 `ui_utils/`，反過來會循環 import

#### 參照項對話框（RefItemDialog，設定表驅動）

人員／部門／案類的「新增／修改」原本是六個各自複製的類別（`PersonnelAddDialog` 等），2026-07 收斂成單一 **`RefItemDialog(cfg, db_path, existing=None, parent=None)`**：

- 差異全數資料化成三份 module 級 config（`REF_PERSONNEL`／`REF_DEPT`／`REF_CASETYPE`）：資料表、PK 欄、名稱欄、自動編號前綴、標籤文字、停用勾選框字（人員「離職」其餘「停用」）、稽核分類名、額外欄位
- **Add/Edit 軸靠 `existing` 參數**：`None`＝新增（自動編號＋INSERT＋範圍 1～N+1），帶 `(pk, seq, name, is_active)`＝修改（UPDATE＋範圍 1～N）
- **人員別名是唯一特例，走 `cfg["extra_fields"]` 資料驅動**（建欄／預填／寫入都遍歷這個 list），不是 `if is_personnel` 分支；別名讀寫仍受 `_has_alias_col` 缺欄退路保護。日後新增第 4 種參照表只要多一份 config，帶專屬欄位就填 `extra_fields`，不必再寫類別
- 對外 API `get_result()`／`get_target_position()` 與舊六類別相容，`tab_settings` 六處呼叫點只換建構參數

⚠️ **編輯框塞進固定列高格子，數字下緣被裁切**（雙擊序號欄進編輯時發生）→ 全域 `theme.py` 對所有 `QLineEdit` 套 `padding: 6px 10px`，疊上編輯時 focus 的 2px 邊框，在固定 36px 列高裡擠掉太多空間。`_SeqEditDelegate.createEditor()` 的 editor 要顯式 `padding: 0px; margin: 0px;`（border 不覆寫，沿用 theme.py 原值，否則編輯時邊框消失看起來不像輸入框）。離線（無 GUI）量測這類問題會失準——容器跑的 `QFontMetrics`/`sizeHint` 沒有套用真實 Windows 125% 縮放與全域 stylesheet，算出來「應該塞得下」不代表實機真的塞得下，這類視覺裁切問題最終仍要上機才能定案

### 權限（AuthManager，單例）

**三角色**：`user`（一般，預設）／`archive`（歸檔管理）／`admin`（最高）。

- SHA-256 密碼存 `App_Settings`：`admin_password_hash`（預設 `admin`）、`archive_password_hash`（預設 `0000`）。**兩組必須相異**——`login()` 先比 admin 再比 archive，同值則 archive 永遠登不進
- 登入比對兩組 hash：中 admin→`admin`、中 archive→`archive`、都不中→失敗（寫一筆登入失敗稽核，不記輸入的密碼）
- 標題列顯示三態；admin 與 archive 皆閒置自動登出（預設 **10 分鐘**，可於「系統設定」子頁調整、0＝停用；降回一般使用者，程式不關）
- **便捷判斷**（勿在各處寫字串比較）：`is_admin()`／`is_archive()`／`is_manager()`（admin or archive，給「歸檔管理也能做」用）／`actor_name()`（稽核 operator 用）
- **變更密碼**：`change_password()` 依當前登入身分改對應那組（admin→admin、archive→archive）；user 不得改。高風險，**Enter 不送出**（防誤按）、只能滑鼠點。**變更成功後即 `logout()` 降回一般使用者**（`tab_settings._changePassword`），要求以新密碼重新登入（避免舊 session 沿用、確認新密碼可用）

**權限矩陣**（歸檔管理＝一般使用者＋下列加項；空白＝同一般使用者）：

| Tab | admin | 歸檔管理 archive | 一般使用者 user |
|-----|-------|-----------------|----------------|
| 交辦發文 Tab0 | 全可改（編號恆可點） | 同一般 | 只能改承辦人；已發文禁編 |
| 交辦收文 Tab1 | 全可改 | 同一般 | 開放更正、開放刪除 |
| 公文陳報 Tab2 | 全可改 | 同一般 | 開放更正、開放刪除 |
| 簽收單列印 Tab3 | 可用 | 可用 | 可用 |
| 資料庫瀏覽 Tab4 | 全可改（含刪除） | 可修改、無刪除（刪除鈕僅 admin） | 不開放編輯 |
| 檔案歸檔 Tab5 | 可用 | 可用 | 無法使用 |
| 設定 Tab6 | 全可用 | 可視：變更密碼／登出／系統設定子頁（僅歸檔資料夾面板可改，簽收表標題／閒置逾時面板整塊反灰）；參照維護＋跨年度重置 disable 灰掉 | 無法使用 |
| 操作紀錄 Tab7 | 可檢視（唯讀／篩選／匯出 CSV） | 無法使用（遮罩導引登入） | 無法使用（遮罩導引登入） |

> 一般使用者限制由 `TaskEditDialog(restricted=…)` 控制（鎖定欄顯示 DB 原值＋灰 `:disabled` 樣式，儲存只動承辦人）；身分變更時 `_onRolePerm` 重刷編號連結與刪除鈕。瀏覽頁已改純 item，`_onRolePerm` 只切編號欄 `setForeground`（藍＝可點）、`refreshDeleteBtns` 切 ✕ 字色，點擊走 `cellClicked`；收/發/陳報頁仍由 `setDocIdLinkCell(clickable=…)`（cellWidget）控制。
> 「歸檔管理也能做」用 `is_manager()`；「僅 admin」（Tab4 刪除、Tab0 發文）維持 `is_admin()`。設定頁參照維護按鈕對 archive `setEnabled(False)`（需配 `:disabled` 樣式，見踩雷表）；雙擊參照列會繞過按鈕 enabled，故 `_add*/_edit*`（現已收斂為 `_addRef`／`_editRef`）皆有 `_refEditable()`（僅 admin）guard。⚠️ **排序的替代路徑也要 gate**：拖拉在 `_applyRolePermissions` 以 `NoDragDrop` 關閉；**序號欄雙擊行內編輯**曾漏 gate（archive 可雙擊改序號→ `_moveRow` 把已反灰的「儲存排序」鈕重新點亮→ 存回 DB＝權限繞過），已於 `_onCellDoubleClicked` 開頭與 `_onSeqItemChanged` 補 `_refEditable()` guard。凡新增「受限身分不可做」的功能，務必檢查**每一條**觸發路徑（按鈕／雙擊／行內編輯／Enter／拖拉），見 CLAUDE.md「寫 code 的紀律」。

#### 三表新增鎖（唯讀設定，v1.1.6）

單位級「跨年度後唯讀」開關：管理者於「系統設定 → 唯讀設定」（`InputLockPanel`）逐一停用三張公文主表的**新增**，被停用者一般使用者只能瀏覽。

- **儲存**：`App_Settings` 三 key `input_lock_task`／`input_lock_crim`／`input_lock_gen`（`"1"`＝鎖）；讀取端 fallback，預設不鎖。常數 `INPUT_LOCK_KEYS`＋便捷 `isInputLocked(db_path, kind)`（kind ∈ task/crim/gen）皆在 `lib/db_utils.py`。純邏輯測試 `tests/test_input_lock.py`。
- **只擋新增、只擋一般使用者**：不擋修改／刪除；admin／archive（`is_manager()`）不受限。跨年度重置不動這三 key（`performYearEndReset` 不清 `App_Settings`），重置後保留現值。
- **硬 gate（真正防線）**：`if not is_manager() and isInputLocked(...): return`——`tab_receive._submit`(task／收文 INSERT)／`tab_report._submitCriminal`(crim)／`_submitGeneral`(gen)／`tab_dispatch.handleDispatch`(task／發文 UPDATE)。涵蓋送出鈕與 Enter。**`task` 鎖同時涵蓋交辦單收文（新增）與交辦單發文（Tab0 確認發文，屬同一交辦流程，跨年度後一併凍結）**——這是刻意的範圍決定，`task` 一個開關管收發文兩頁。
- **唯讀 UI（輔助提示）**：一般使用者進到被鎖分頁 → 該表單所有可填欄位＋送出/清除鈕 `setEnabled(False)`、頂端顯示紅色橫幅「唯讀模式：本功能目前無法使用，僅供瀏覽」；預覽表維持可讀。三頁（收文／發文／陳報）各有 `_applyInputLock()`。`tab_report` 依當前刑案/一般模式（`_currentLockKind()`）只鎖對應那種，`type_tabbar` 不反灰（可切到未鎖模式），`_switchFormType` 末尾亦重套。
- ⚠️ **刷新時機（易踩）**：`main._onTabChanged` **只對設定頁與瀏覽頁**呼叫 `on_activated`，切入收文/發文/陳報頁不會觸發。故這三頁各自 `setup()` 內自掛 `self.tab_widget.currentChanged.connect(self._onShown)`（比照 `tab_print`）來重套 `_applyInputLock`（切入分頁時反灰＋橫幅），不能只靠 `on_activated`。
- **登出處理**：三頁另掛 `AuthManager.role_changed → _onRoleClearList`，登出降回一般使用者時**清空該頁預覽/發文清單**（`setRowCount(0)`），刻意**不**在原頁做即時反灰（維持最小處理，反灰於下次切入分頁時由 `_onShown` 補上）。
- ⚠️ 即時生效（送出當下讀設定），不需重啟。

### 閒置處理與多人使用（main.py）

兩個獨立計時器（全域事件過濾器 `_IdleFilter` 監聽滑鼠/鍵盤/滾輪重設）。**兩值自 v1.1.6 起可由「系統設定」子頁調整**（存 `App_Settings`：`idle_logout_min`／`idle_close_min`，分為單位、**0＝停用該機制**；啟動時 `getIdleTimeoutsMs` 讀一次、改值重啟生效，讀不到／壞值退預設，見 `db_utils.parseIdleMinutes`）：

- **閒置自動登出** `_idle_timer`，預設 **10 分鐘**，僅 admin／archive 計時，到點 `logout()` 降回一般使用者（程式不關）
- **閒置自動關閉** `_close_timer`，預設 **14 分半**，不分身分一律計時，到點 `_onIdleClose` 以 **`os._exit(0)` 硬關**（靜默，僅 error.log 留一行）。⚠️ **預設刻意設在 Windows（AD 部署）15 分鐘鎖螢幕之前**：DB／鎖檔在 SMB 網路碟，程式須趕在系統把畫面切回登入前先關並清 `dbfile.lock`；否則鎖螢幕後 A 的程式仍在背景續跑、續更新心跳，會一直卡住別台電腦的 B 登入（鎖螢幕≠暫停行程）。**現場調整（或設 0 停用）時務必維持低於該單位鎖螢幕時間——此約束是維護者層級默契，刻意不放 UI**；UI 只驗證「兩者皆非 0 時關閉 > 登出」
  - ⚠️ **為何用 `os._exit` 而非 `app.quit()`**：到點當下若有 modal `exec()` 開著（HELP／`confirmBox`／編輯彈窗／`QFileDialog`），`quit()` 只退最內層那個事件迴圈、關不掉主程式（且 `_close_timer` single-shot 已觸發＝自動關閉從此失效）。`os._exit` 不受巢狀事件迴圈影響、一定結束。代價是不走 Qt teardown（印無害收尾警告，`--windowed` 無 console 看不到），故**結束前先手動清鎖檔**

**APP 層軟性互斥（`lib/app_lock.py`）**：DB 放網路碟給多機同跑時 SQLite 檔案鎖不保證跨機生效、真同時寫入可能毀損。故在 `dbfile.db` 旁維護鎖檔 `dbfile.lock`（JSON：機器名/使用者/開啟時間/心跳/PID）：

- 偵測到「新」鎖檔（心跳未超 `STALE_SECONDS=5 分鐘`）→ 跳 `confirmBox`（「○○○（電腦 X）自 HH:MM 起正在使用本系統」＋灰字勸導「多人同時編輯可能造成資料毀損」「閒置約 15 分鐘程式將自動關閉」），按鈕**仍要開啟／取消**（純勸導，預設取消）。心跳過舊＝當機殘留可直接接管
- 開啟後寫自己的鎖檔、每 `HEARTBEAT_MS=60 秒`更新心跳。**清鎖檔三道**：`app.aboutToQuit`＋`atexit`（補蓋主選單離開、建表失敗等 `sys.exit` 不經 Qt quit 的路徑）＋`os._exit` 前手動呼叫（`mgr._cleanup_lock_cb`）；皆只刪屬於本實例者（機器名＋PID）、冪等靜默。當機／斷電蓋不到，靠心跳停後 `STALE_SECONDS` 失效自癒
- ⚠️ **是勸導不是保證**：可按「仍要開啟」硬上，corruption 風險仍在。不做唯讀模式、不擋 DB 寫入（併發由 SQLite 忙線鎖處理，對應「資料庫忙線中」訊息）。讀寫鎖檔失敗一律靜默退讓
- 純邏輯（parse/format/is_stale/is_mine/lock_file_path）有測試 `tests/test_app_lock.py`

### 平時自動備份（`lib/db_backup.py`）

單機平時零備份，硬碟外的損毀一旦發生即無救。故於**程式啟動時**（鎖檔後、建主視窗前，`main.py` 呼叫 `run_auto_backup`）做 **GFS 輪替備份**至 `dbfile.db` 同目錄 `backups/`：

- **每日** `dbfile_backup_day_YYYYMMDD.db`：每天第一次開啟建一份，保留最近 `DAILY_KEEP=7`
- **每週** `dbfile_backup_week_YYYYMMDD.db`：每 ISO 週第一次開啟建一份，保留最近 `WEEKLY_KEEP=4`（涵蓋約一個月）
- **方式**：sqlite3 backup API 取一致性快照（並發寫入也安全），先寫 `.tmp` 再 `os.replace` 原子換上（中途失敗不毀既有好檔）。保留份數常數在檔頂
- **容錯**：全程 try/except，失敗只記 `error.log`、絕不拋例外、絕不阻擋開程式
- ⚠️ **只防本機檔案損毀／誤刪，救不了硬碟整顆故障**（備份與本體同碟）。異地備份尚未實作
- **手動還原**：關程式→ 將 `backups/` 那份複製覆蓋 `dbfile.db`（覆蓋前先把現有 db 另存留底）→ 重開。無還原 UI
- 純邏輯＋backup round-trip 有測試 `tests/test_db_backup.py`；`backups/` 已 gitignore

### 全域錯誤處理與白話化訊息

未預期例外由 `main.py` 全域 handler（`sys.excepthook`）統一接手：①寫 `error.log`（含完整 traceback）②寫 Windows 事件檢視器（有 pywin32 時，無則靜默）③彈白話錯誤視窗（`db_utils.friendlyErrorMessage(exc_type, exc_value)` 把例外轉成承辦看得懂、可行動的提示——技術細節只進 error.log）。

`friendlyErrorMessage` 依例外型別分類（純邏輯可單測 `tests/test_error_msg.py`）：

- **SQLite**：忙線鎖（locked/busy）→「資料庫忙線中…請關閉其他視窗」；損毀（malformed 等）→「檔案可能損毀…請提供 error.log 與備份」
- **檔案／權限／網路碟**：`PermissionError`／`FileNotFoundError`（導向設定頁）／`OSError`（網路碟可能斷線）
- 對照不到 → 泛用訊息（已記錄、請提供維護人員）

> ⚠️ **被 `except` 接住的例外要用 `ui_common.reportError(title, exc, parent=None)`**（門面 `from ui_utils import reportError`），別再寫 `msgCritical(title, str(e))`。`reportError` 同時①寫完整 traceback 進 error.log ②彈白話訊息（內部走 `friendlyErrorMessage`）。舊寫法既漏記 log、又把 SQLite 英文原文丟給使用者（如 `attempt to write a readonly database`）。全域 `excepthook` 只接「未被接住」的例外，caught 的不會自動進 log，故要靠 `reportError` 補。

### 稽核 log（操作紀錄）

對關鍵操作寫操作紀錄（單機環境本質無法防 admin 直接改 DB，已接受；程式內不提供刪 log UI）。

- **表 `Audit_Log`**（log_id/ts/role/action/target_table/target_id/operator/detail），由 `ensureSchema` 啟動冪等建立。**自 v1.1.0 起入庫／Release 空殼已內建本表＋兩組密碼**，全新安裝免再跑；僅舊庫升級才需另跑 `fix_audit_setup.py` 補表
- **helper（`lib/db_utils.py`）**：`writeAudit(conn, *, role, action, detail, target_table, target_id, operator)`（用呼叫端同一 conn、同 transaction，缺表靜默跳過）；`buildDetail(類別, 動作, 內容)`→`[類別][動作]內容`（類別＝交辦／刑案／一般／人員／部門／案類／歸檔／系統）；`auditStaffName(conn, id)` 解析姓名快照；**`writeAuditSafe(db_path, *, role, action, detail, ...)`＝獨立稽核事件**（自開連線寫一筆→commit→close→吞例外），給 PWD／CONFIG／LOGIN_FAIL 這類「與業務操作不同 transaction、單獨記一筆」用（免各處重抄 getConn→writeAudit→commit→close→try/except）。需與業務操作同 transaction 者仍直接用 `writeAudit(conn, ...)`
- **operator 取值規則**（最終版）：admin 的刪除一律留空（admin 跨庫操作與資料列的人脫鉤）；非 admin 在業務頁刪除→記資料列的人（收文者／陳報人）；瀏覽頁刪除僅 admin→留空；參照表／系統類→記登入身分（`actor_name()`）。**刪除取值時機**：清空式 UPDATE **之前**先 SELECT operator＋主旨（清空後拿不到）
- **四處刪除共用 helper**：`db_utils.softDeleteDoc(conn, *, table, doc_id, role, is_admin, audit_operator=True)`（清空 SQL／主旨欄／對象人欄／operator 來源集中於 `_DELETE_CLEAR_SQL`／`_DELETE_META`）。業務頁照預設、瀏覽頁傳 `audit_operator=False` 讓 operator 恆留空。⚠️ 收文／陳報頁一般使用者可刪（更正剛輸入的錯列，符合權限矩陣）。測試 `tests/test_soft_delete.py`
- **Reset 與 log**：①先寫 Reset log（含清除筆數）②整庫自動備份（歷史 log 隨備份保存）③`performYearEndReset` 清主表時含 `Audit_Log`（當前庫歸零、歷史在備份）
- ⚠️ **DB 須含本表才寫稽核**：舊庫未跑 `fix_audit_setup.py` 則程式照跑但稽核一筆不寫（靜默退化成單一 admin、無 log）。`fix_audit_setup.py` 一次性、不入庫

**檢視 UI（Tab7，`tabs/tab_audit.py`）**：唯讀、**僅 admin**（非 admin 顯示遮罩導引設定頁登入，牆同歸檔頁 `outer_stack`、連 `role_changed`）。

- 全量載入（`ORDER BY log_id DESC`）後 `setRowHidden` 篩選；`detail` 經 `parseDetail` 拆「類別／動作／內容」三欄
- 欄位：時間｜身分｜類別｜動作｜內容｜對象人。刪除／重置／登入失敗動作紅字＋紅「●」（`setForeground`，勿用 `::item{color}`）；身分 admin 鋼藍、archive 灰藍、空白灰
- 樣式比照瀏覽頁（固定列高 30、不換行、完整入 tooltip、`NoSelection`+`NoFocus`）
- 篩選：期間起迄（哨兵 `minimumDate`=2000-01-01）／身分／類別／關鍵字＋底部計數；下拉首項自述「全部身分／類別」省版面；篩選列控件 12pt（用 stylesheet `font-size`，勿用 `setFont`）。⚠️ 日期框寬須容 10 位日期＋右內距 32px，以 `QFontMetrics` 量測再設
- 「重整」`btn_reload` 強制重查；「匯出 CSV」匯目前篩選後可見列（`utf-8-sig`，動作欄不含「●」）；`on_activated` 比對指紋 `(COUNT, MAX(log_id))` 免重建、`preserveScroll` 保留捲動
- `parseDetail` 純邏輯有測試 `tests/test_audit_view.py`

### 誤刪還原（資源回收筒）

主表「刪除」是清空欄位保留 doc_id。為支援還原，**清空前先把整列快照存進回收筒**。

- **表 `Trash_Documents`**（見 §6）：`payload` 存整列 JSON 快照；由 `ensureSchema` 建立
- **helper（`lib/db_utils.py`，可單測 `tests/test_trash.py`）**：`snapshotRow(conn, table, doc_id)`（清空前抓整列，table 走三主表 allowlist）／`writeTrash(...)`（缺表靜默跳過）／`restoreFromTrash(conn, trash_id)`（寫回原列＋刪該 trash 列，table allowlist 防注入）
- **4 個刪除點**（瀏覽三表／收文／刑案／一般）清空前先 `snapshotRow`＋`writeTrash`，同一 transaction
- **入口（設定 Tab6 子頁「資源回收筒」，僅 admin）**：唯讀單選表（刪除時間／文號／類別／主旨／對象人／刪除身分）＋關鍵字過濾＋「⟳ 重整」「↩ 還原」。archive 看得到鈕但反灰（`setVisible(True)`＋`setEnabled(is_admin)`）；user 進不了設定頁。還原寫一筆「還原」稽核
- **保留**：永久，跨年度 Reset 一併清空。**還原保留歸檔狀態**（快照含 `is_reported`／`is_electronic`，原已歸檔者還原後仍為已歸檔、不回待歸清單）；清空式刪除不刪實體 PDF
- ⚠️ **還原後刷新**：`restoreFromTrash` **必須排除 `last_modified`**，讓 update trigger（`WHEN NEW.last_modified IS OLD.last_modified`）自己蓋成當下時間；若寫回快照舊值，trigger 不觸發、指紋偵測不到。另以 `_pending_reload_keys` 通知瀏覽／歸檔頁，切過去時 `on_activated` 走 `_forceReload`（`runWithBusy` popup→全量重建）

### 別名（alias）

- 別名是「人的屬性」，存 `Ref_Personnel.alias`，分隔符**半形逗號**，多別名同欄（如 `王佐,所長,副座`）
- 否決新表 `Ref_Alias`：別名跟著人走，跨年度重編 id 時自動保留，無需額外關聯
- 歸檔比對（`lib/archive_text.py`）從 DB 讀別名與正名一同納入 `_loadNameDict`
- 欄位以一次性 `ALTER TABLE ADD COLUMN` 新增；讀寫前 `_has_alias_col(conn)` 做 PRAGMA 缺欄退路，避免舊 DB 報錯

### 歸檔檔名解析的雷（`lib/archive_text.py`）

> ⚠️ 動斷詞／日期／主旨解析前先看這節（原 CLAUDE 踩雷表 #8 詳述搬來此；CLAUDE 只留指標）。

- **斷詞漏字（日期黏主旨如 `1150101匿名竊盜案`）** → 用 `re.findall([^一-鿿]+)` 抽中文段再 2 字滑動切詞（`_tokenize` 含數字片段不符純中文判斷會整段漏切）
- **PK 為 1xx 時日期解析空白** → 日期 token 用 `(?<!\d)(1\d{2})(\d{2})(\d{2})(?!\d)`（舊正則把 PK「103」當民國年）
- **歸檔預覽主旨退回 DB 主旨（檔名無 `-`）** → `_parseSubject` 補「無 `-`」分支：去開頭日期＋從尾端剝人名，中間即主旨

### 資料庫瀏覽（Tab4）搜尋

**全量載入 + `setRowHidden`**（非搜尋重建表格）：

- `_reload(key)`：DB 全量抓取，所有非軟刪除列 `insertRow`、存入 `_allRows[key]`（row dict 列表）＋`_docorder[key]`（doc_id 列表），不做關鍵字過濾
- `_applyFilter(key)`：對每列算是否命中 kw/scope，結果存 `_matchedCols[key]`，呼叫 `_applyRowVisibility`
- `_applyRowVisibility(key)`：單一 pass 同時考慮搜尋 filter 與逾期篩選，`setRowHidden` 決定可見；最後 `_updateFooter`
- 搜尋框／範圍下拉只觸發 `_applyFilter`，**不觸發 `_reload`**（`_reload` 只在切 Tab 且指紋改變時呼叫）
- **比對**：`kw.lower() in str(值).lower()` 子字串、不分大小寫；選範圍只比該欄，否則比所有 `search:True` 欄
- **差異更新 `_diffUpdate`**：查 `last_modified > since` 維護 `_allRows`／`_docorder`／表格列，再 `_applyFilter`；變動列 `>= _BUSY_ROW_THRESHOLD` 時重建段以 `runWithBusy` 包
- **精簡/完整**：單顆「完整」切換鈕（預設精簡），`_applyMode` 做 `setColumnHidden` 再 `_applyRowVisibility`
- ⚠️ 兩個雷（`_allRows`/`_docorder` 1:1 對應、`setUpdatesEnabled` 須 try/finally）見 CLAUDE 踩雷表 #7

### 歸檔頁「檔名過濾」（Tab5）

候選 PDF 的關鍵字框（`{key}_kw`，標籤「檔名過濾」）做**檔名子字串過濾、不分大小寫**：`_rematch` 只保留 `os.path.basename(fp)` 含該串者（非重排、非斷詞）。關鍵字不混入評分；評分排序仍照 `match_cols` 斷詞交集。觸發為 Enter 或「比對」鈕。

### 其他慣例

- 所有彈窗加 Enter 確認（高風險如變更密碼除外）
- 跨年度 Reset 重編所有 ID，**不需要**流水號機制；`Seq_DocId` 等 Reset 一起歸零
- 主表「刪除」清空保留 doc_id，流水號永久佔用，彈窗提示「本文號（XXX）無法再被使用」
- **身分判斷**用 `AuthManager.instance()` 便捷方法，勿各處寫 `current_role == '…'` 字串比較
- **DB 連線**統一走 `db_utils.getConn(db_path)`（單一來源，要加 PRAGMA/timeout 集中改一處）；`base_tab._getConn`、`edit_dialog._get_conn` 皆委派它
- 三個編輯彈窗共同繼承 `_BaseEditDialog`，版面常數 `_LABEL_W/_FIELD_W/_MARGIN` 集中於基底

---

## 4. 目錄結構與路徑

```
專案根/
├── main.py          進入點（從專案根目錄啟動）
├── lib/             核心模組（package）：db_utils／base_tab／auth_manager／app_lock／
│                    db_backup／db_schema／db_seed／archive_text／theme／version／loading_screen
├── layouts/         所有 .ui（Layout1~7、main_menu）
├── res/             圖片／SVG／qrc（package）：resources.qrc／resources_rc.py／buttons／tabs
├── tabs/            各 Tab
├── ui_utils/        共用 UI 工具（table／widgets／status／sticky_scroll／edit_dialog／
│                    settings_dialogs／help_dialog／help_content／ui_common／button_imgs）
├── tools/           開發／維運工具（入庫，從專案根執行；不被核心模組 import）：
│                    bump_version／gen_buttons／gen_quickstart／gen_shell_db
└── tests/           純邏輯單元測試（unittest）
```

- ⚠️ 一次性／現場交付腳本（`fix_audit_setup.py`／`fix_cat_status.py`／`seed_*.py`）刻意**不入庫、留根目錄**：`fix_*` 打包成 exe 發給現場放 `dbfile.db` 旁執行（靠「找腳本旁的 db」邏輯，不可改），`seed_*` 為本機壓測／塞假料丟棄腳本（git add 時跳過，見 CLAUDE）
- `lib/`、`res/` 都是 package（有 `__init__.py`）：用 `from lib.db_utils import …`／`from res import resources_rc`
- `tools/` 各腳本錨定 repo 根但**一律從專案根目錄執行**；皆不 import 核心模組

### 路徑解析（getResourcePath，打包相容）

- `db_utils.getResourcePath(rel)`：開發從當前目錄找，打包後從 `sys._MEIPASS`
- `dbfile.db` 特殊：永遠從 exe 所在目錄讀（真實資料，不打包進 exe）
- `.ui` 用 `getResourcePath("layouts/Layout1.ui")`、圖片用 `getResourcePath("res/buttons/banner.png")`；`arrow.svg` 走 qrc 虛擬路徑 `:/arrow.svg`，**不經** getResourcePath
- ⚠️ `getResourcePath` 用「當前工作目錄」找 dbfile.db、**不是** `__file__`，故**程式務必從專案根目錄啟動**（`python main.py`），打包後則 exe 所在目錄
- ⚠️ 改了 qrc 內任何 SVG，要重編：`pyside6-rcc res/resources.qrc -o res/resources_rc.py`

### 單元測試（tests/）

純邏輯回歸測試，**不碰 GUI**（容器無法跑 Qt 視窗，故只測無視窗依賴的純邏輯）。

- **跑法**（專案根）：`python -m unittest discover -s tests`；檔名 `test_*.py`（探索預設，勿改名）
- **需 PySide6 的測試**（受測模組 import 時載入 PySide6）：`test_db_utils`／`test_status`／`test_auth_manager`／`test_error_msg`／`test_audit`／`test_audit_view`／`test_ref_sort`；純 stdlib：`test_archive_text`／`test_app_lock`／`test_db_backup`
- **涵蓋**：歸檔解析（含 PK 撞號雷）、流水號／重置／設定／歸檔定位、逾期與狀態色、權限與密碼、錯誤白話化、稽核 helper、操作紀錄解析、軟性互斥、自動備份、閒置逾時解析（`test_idle_timeouts`，0＝停用／壞值退預設）；另 `test_no_pii` 防個資外洩（見 CLAUDE）
- **紀律**：動到可單測純邏輯時一併新增／更新測試；GUI 互動仍須上機驗證

---

## 5. 操作手冊（要改特定東西時查）

### 結構變更原則（schema 程式碼為唯一來源；附加式走 ensureSchema、破壞式才手動）

- **schema 唯一來源 = `lib/db_schema.py`**：全部資料表（`_TABLES`）、三 View（`_VIEWS`）、六 trigger（`_TRIGGERS`）的 DDL 都集中在此，皆 `CREATE … IF NOT EXISTS`。三方共用：①啟動 `ensureSchema`（既有庫＝no-op）②`tools/gen_shell_db.py` 產乾淨空殼 ③單元測試 `test_db_utils._build_schema` 直接 `applySchema(conn)` 建表。**不再有第二份手刻 schema**（舊測試假 schema 已移除），徹底消除走鐘
- **種子資料唯一來源 = `lib/db_seed.py`**：參照資料（人員佔位／部門／案類／案件狀態／一般分類）＋預設密碼 hash＋Seq 歸零＋簽收表四 key（空值）。`seedFreshDb()` 走 `INSERT OR IGNORE`，**只由 `gen_shell_db.py` 在建空殼時呼叫**，刻意不掛進啟動 `ensureSchema`（避免對既有庫重塞參照資料）
- **附加式（建表／加欄，只增不改）→ 登記進 `db_schema._TABLES`／`_COLUMNS`**：開程式時 `ensureSchema` 自動套用（`CREATE TABLE IF NOT EXISTS`／「缺欄才 `ADD COLUMN`」），各語句獨立 try、失敗只記 log、絕不擋開程式。在 `main.py`（鎖檔後、自動備份前）呼叫一次。**forward-only**：不回溯自愈
- **破壞式（改型別／改既有資料／改 View 定義）→ 一次性手動**：`IF NOT EXISTS` 不會更新既有 View／表，故改 View 定義要 `DROP VIEW…CREATE VIEW`、改型別要 `ALTER`／資料修補，走手動腳本對現場 `dbfile.db` 執行，不寫進啟動流程（同時也要更新 `db_schema.py` 的對應 DDL，讓新空殼一致）
- ⚠️ **動過 schema／種子後**：跑 `python tools/gen_shell_db.py` 重產空殼，並由維護者重新 commit 根目錄 `dbfile.db`（git HEAD 空殼是 no-pii 測試掃描對象，須與程式碼同步）
- 程式碼讀寫可能尚未存在的欄位前，用 **PRAGMA 缺欄退路**保護（現行 alias 欄即如此，見 `ui_utils/settings_dialogs.py` 的 `_has_alias_col`）

### 新增 Tab 的標準流程

1. 新增 `tabs/tab_xxx.py`，`class TabXxx(BaseTab)` 實作 `setup(tab_index)`
2. `tabs/__init__.py` 加 `from .tab_xxx import TabXxx`
3. `main.py` 的 `TAB_CLASSES` 登記一行
4. 新增對應 `layouts/LayoutN.ui`（**每個大 Tab 都必須有 .ui**；彈窗才用 code 動態建）
5. 若有人員/部門/案類下拉，override `on_activated()` 刷新（`refreshFilterCombo` 保留當前選值、值已不存在則清空）；觸發為從設定 Tab 切出＋`_ref_dirty=True`

> ⚠️ **預覽表名稱不會自動跟 rename 更新**：預覽表存「當下抓的字串」，rename 後顯示舊名。新 Tab 若預覽表有參照字串欄，須仿 `tab_dispatch._refreshPreviewNames()` 寫刷新方法並在 `on_activated()` 末尾呼叫

### .ui 撰寫規則

見踩雷表前兩條（margin 四獨立 property、centralwidget 全小寫）。

### 新增 UI 元件注意

- 所有新 `QDialog`/`QWidget` 明確設背景色＋文字色（見下）
- 字體 14pt、縮放 125%，寬度基準：全型字 `24×1.8=43px`、半型 `24×0.65=16px`、ComboBox/DateEdit 加 36px、CheckBox indicator 25px

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

> dialog 的 `QDateEdit` 是 `border-radius: 4px`，主視窗 theme.py 是 `8px`。

### ui_utils 擴充規則

| 需求 | 做法 |
|------|------|
| 新欄位固定寬度 | `table.py` 的 `FIXED_COL_WIDTHS` 加一行 |
| 同名欄位不同表格不同寬度 | `fixed_overrides` 參數 |
| 欄寬隨內容縮、卡上限 | `cap_mode=True` |
| 新狀態顏色 | `status.py` 的 `colorForStatus` 加條件，回 `QColor("#hex")` |
| 新元件行為 | `widgets.py` 新增函式＋`__init__.py` export |
| 身分變更重設刪除鈕 | `table.py` 的 `refreshDeleteBtns(table, enabled, col=0)` |
| 表格整排 hover 反白 | `widgets.py` 的 `RowHoverFilter` + `RowHoverDelegate` |
| 必填日期欄、月曆捲到今天 | `widgets.py` 的 `setupDateEditToToday`（QDateEdit，預設今天） |
| 可空白日期欄（手打／月曆／非法紅框） | `widgets.py` 的 `NullableDateEdit`（QLineEdit 子類，見下方「可空白日期框」） |
| 固定 N 行、超長尾端省略標籤 | `widgets.py` 的 `TwoLineElideLabel`（以 `actions.replaceWidget` 換掉 .ui 的 QLabel） |
| 預覽表黏底捲動 | `setupPreviewTable` 後 `attachStickyScroll(table)` |
| 重建/差異更新時保留捲動位置 | `widgets.py` 的 `preserveScroll(table, func)`（func 前記 `verticalScrollBar().value()`、func 後 `QTimer.singleShot(0,…)` 還原並 clamp）。輸入暫存預覽表刻意維持捲到底、不套此 helper |

### 可空白日期框（NullableDateEdit）

「查獲日期」這類**可留空、又要能鍵盤手打**的欄位，**不**用 QDateEdit。QDateEdit 是分段遮罩 spinbox，硬以 `minimumDate`＋`specialValueText` 假裝空白會反覆出包——史上踩過：①空白時鍵盤打不動；②滑鼠亂點冒 `1752/1753` 殘值（minimumDate 被步進）；③整格清空後手打半成品被 fixup 還原成舊值。每補一個哨兵的洞就冒下一個，**根因是拿 QDateEdit 當可空白欄**。

治本＝改用 **`ui_utils.widgets.NullableDateEdit(QLineEdit)`**：底層純文字框，天生支援「整格清空 → 自由手打 `2025-01-30`」，無哨兵、無殘值、無 fixup 還原。

- **輸入正規化** `normalizeDateText`：離開欄位時把 `20250130`／`2026-0125`／`2026/01/25`／`2026-1-5` 等寫法補成 `yyyy-MM-dd`（先試「年-月-日」三段補零，否則抽出全部數字、剛好 8 碼才拆）。
- **三態判定** `classifyNullableDate` → `empty`／`valid`／`invalid`（純函式，測試 `tests/test_nullable_date.py`）。空字串＝合法未填。
- **驗證時機**：`editingFinished`（離開欄位／Enter）即驗；非空但非法 → 亮紅框並擋送出（各頁送出前再 `validateNow()` 補驗一次）。編輯中（`textEdited`）收紅框、不嘮叨。
- **鍵盤鎖**：`QRegularExpressionValidator` 只放行數字與 `-`／`/`，英文字母與其他符號打不進來（只擋使用者按鍵；`setText`／月曆挑日不過 validator）。
- **月曆**：右側 `addAction` 箭頭開 `QCalendarWidget` popup（`Qt.Popup`）；不設格線、`NoVerticalHeader`（去掉週數欄），與其他 QDateEdit 月曆長相一致。
- **對外 API**：`getDate()→QDate|None`、`isBlank()`、`hasError()`、`setDate(QDate|None)`、`clear()`、`validateNow()`、`changed` 訊號。錯誤紅框與呼叫端注入的基底樣式（稽核頁 12pt）以 `setBaseCss` 共存、互不洗掉。
- **.ui 用法**：`<widget class="NullableDateEdit" name="...">`（`loadUi` 內 `registerCustomWidget` 註冊）；勿留 `calendarPopup`／`displayFormat` 等 QDateEdit 專屬 property（QLineEdit 子類無此屬性，QUiLoader 會報設不上）。
- `setupNullableDateEdit(widget, placeholder)` 退化成只設灰字提示（保留舊簽名相容呼叫端）。

用處：陳報頁查獲日期 `crim_occdate`、刑案編輯對話框 `w_occ_date`、稽核查詢頁 `_from`／`_to`。

> `setupDateEditToToday`／`setupDateEditCalendarOnly` 仍保留給**必填**的 QDateEdit（陳報日期 `rpt_date`、收文／期限日期等，預設帶今天、不需可空白）。

### 通用彈窗（ui_utils）

> ⚠️ v1.1.2 起通用 UI（訊息／確認彈窗、`.ui` 載入、按鈕樣式常數）已從 `db_utils` 搬到 **`ui_utils/ui_common.py`**，`db_utils` 回歸純資料層。外部走門面 `from ui_utils import …`；套件內部用相對匯入。搬出符號：`msgInfo`／`msgWarning`／`msgCritical`／`confirmBox`／`loadUi`／`BTN_CONFIRM`／`BTN_DANGER`／`BTN_CANCEL`。

```python
from ui_utils import msgInfo, msgWarning, msgCritical, confirmBox, loadUi
```

| 函式 | 按鈕 |
|------|------|
| `msgInfo / msgWarning / msgCritical(title, text)` | 確定 |
| `confirmBox(title, text, confirm_text, cancel_text, confirm_danger, default_confirm, informative, min_width)` | 自訂，回 True=確認 |

> `informative`：次要說明，Apple HIG 兩層式（主訊息深色＋次要灰字 `#6b6b6e`，同 14pt）。⚠️ Windows `QMessageBox` 不自動把 informativeText 縮小／變灰，故內部改用 rich text 自排版。`min_width`：撐長檔名用（grid 末列塞 spacer）；內容短的別設。

### 修改功能（EditDialog）

- 在 `ui_utils/edit_dialog.py`，動態產生表單，不用 .ui
- `TaskEditDialog`（Tab0/1）、`CriminalEditDialog`（Tab2 刑案）、`GeneralEditDialog`（Tab2 一般），共同繼承 `_BaseEditDialog`（`_LABEL_W=120`／`_FIELD_W=340`／`_MARGIN=40`，`setMinimumWidth=580`）
- 觸發：點預覽表編號欄超連結；刪除列後須重綁刪除鈕與編號 QLabel 的 row index（參考 `_rebindDocIdCell`）
- **歸檔狀態區塊（僅 admin）**：刑案/一般 dialog 末端「歸檔狀態」分組框（`_build_archive_group`；dbbrowse 與 archive 共用同 dialog，一改兩頁生效）。紙本 `is_reported` checkbox 雙向可勾消；電子檔 `is_electronic` 只能「清除」（popup 產不出 PDF，清空後該筆自動回待歸清單），不動實體 PDF（留孤兒檔，重歸時 rename 覆蓋）。清除為 pending，按「儲存」才真寫 `is_electronic=''`、取消則還原。非 admin 不建此區塊（`save` 跳過這兩欄）

> ⚠️ 歸檔頁 `_doArchive` 寫 PDF 檔名時**一併設 `is_reported=1`**（電子檔歸了紙本必然也歸，免使用者再手動補勾）

### 程式內 HELP（各頁說明鈕）

- **內容單一來源** `ui_utils/help_content.py`：七頁說明以結構化 `HELP_PAGES` 描述，`_render_html()` 產彈窗 HTML、`render_review_text()` 產純文字校稿；tooltip 候選存 `HELP_TIPS`。改說明只動 `HELP_PAGES`
- **彈窗** `ui_utils/help_dialog.py`：`helpDialog(parent, tab_index)` 以 `QTextBrowser` 顯示；`attachHelpButton` 於 `main.py` tabs 建完後呼叫一次，掛分頁列右上角 `setCornerWidget` 說明鈕（依 `currentIndex()` 開對應頁）
- ⚠️ `QTextBrowser` 是 Qt rich-text 子集：**不吃 CSS `letter-spacing`**（設在 `QFont`，`_LETTER_SPACING`）、**不支援圓角／陰影／flex／懸掛縮排**（色塊用單格表格 `bgcolor`、懸掛縮排用兩欄表格）；`font-family` 須用裸字型名（逗號清單會被當不存在字型）
- **按鈕／子頁籤示意圖**：用預烤圓角 SVG（`<img>` 內嵌），由 `python tools/gen_buttons.py` 依 `BUTTONS`／`TABS` 批次產至 `res/buttons/`（`:/btn/`）與 `res/tabs/`（`:/tab/`），對照表 `ui_utils/button_imgs.py`。**新增按鈕完整步驟見 CLAUDE 踩雷表 #6**（漏登記 qrc 會破圖）
- **速查卡**：母本 `QUICKSTART`（同檔），`python tools/gen_quickstart.py`（reportlab 嵌微軟正黑體、`_check_glyphs` 字形檢查）產 `docs/Quick_Start.pdf`（A4 直式 2 頁，`docs/` 未入庫）。改說明同時動到速查卡時 `QUICKSTART` 要一併同步

### tab_report.py 特殊架構

- `Layout3.ui` 用 `QStackedWidget`（`formStack`）切換 index 0 刑案／1 一般
- 發文分類 radio：刑案 `radio_status_a/b/c`→CS01/CS02/CS03；一般 `radio_gen_cat_a/b/c`→GC01/GC03/GC02
- ⚠️ **部分預覽顯示 ≠ DB 值**（刷新時務必轉換）：人名 預覽`王小明`/DB`王小明-19.06`（去 `-` 後綴）；日期 預覽`MM-DD-YYYY`/DB`YYYY-MM-DD`
- 刑案發文分類／一般分類**已正規化**：`status_name`／`gen_cat_name` 直接存兩字顯示名（現行/到案/未到、業務/其他/相驗），View 撈出即顯示（舊 `_STATUS_MAP`／`_CAT_MAP` 已移除）。現行犯判斷改以 `case_status` ID（`CS01`）比對、與顯示名脫鉤（見 `tab_print._build_*`）

### 列印（tab_print.py）

- ⚠️ **簽收表產生走前景＋modal「產生中」popup**（`runWithBusy`），非背景執行緒：matplotlib 靠全域狀態，在背景 `QThread` 與主執行緒搶用會偶發崩潰／圖面錯亂，故 `generate_pages` 一律主執行緒同步畫（單機 1～2 秒可接受）。**勿改回背景執行緒跑 matplotlib**
- 用 **`QPrintPreviewDialog`** 跳原生預覽＋列印選項；不碰 PDF 檔案關聯（避 WinError 1155），頁面 **300 DPI 點陣化**送印（`_paint_pages` 把 PNG 畫到 QPrinter）。「儲存 PDF」走 matplotlib `backend_pdf`（向量），與列印獨立
- 跨版本相容：`setPageSize` 用 `QPageSize` 物件、頁面範圍用 `painter.viewport()`（避 6.x enum 命名空間差異）
- **預設彩色＋長邊雙面**：開預覽前對 `QPrinter` 設 `setColorMode(Color)`＋`setDuplex(DuplexLongSide)`，使用者仍可改（實際支援取決於印表機）
- **欄內換行用真實字型度量**（`_text_width_pt`，dpi=72 `RendererAgg`）：`_wrap_clamp` 不再用「中文當滿格＋0.86 係數」估算（偏窄，會害欄寬還夠的主旨／案類提早折行）。可用寬＝欄寬扣約 1.2×PAD。⚠️ 編號欄 `_fit_font` 仍用舊估算（單行縮字、影響小）
- **刑案類型欄固定 10pt**（`_draw_page` 中 `is_crim and cidx==2`）：案類名長短不一，固定避免參差又壓迫。一般「業務單位」與交辦不受影響、維持 12→10 自動縮

### 簽收表標題自訂（tab_print／tab_settings／settings_dialogs）

簽收表三張表標題與現行犯註記**可由管理者自訂**，免改 code、免重 build。

- **存** `App_Settings` 四 key：`print_title_task`／`_crim`／`_gen`／`print_note_current`。常數與預設集中在 `db_utils.PRINT_TITLE_KEYS`／`PRINT_TITLE_DEFAULTS`；列印走 `db_utils.printTitle(db_path, which)`，**未設定回 `○○…` 預設**（舊庫零升級、PDF 不空白）。預設機關名以 `○○` 佔位、不留真名
- **入口**：設定頁「系統設定」子頁的 `PrintTitlePanel`（2×2 四格整句＋即時字數＋「恢復預設」＋儲存；v1.1.6 前為 nav 鈕開 `PrintTitleDialog`），**僅 admin**（archive 整塊 `setEnabled(False)`，配 `:disabled` 樣式）。儲存有變寫一筆 `CONFIG` 稽核
- **字數上限**（`_TITLE_MAX=36`／`_NOTE_MAX=14`，實量 PDF 版面得出）
- **未設定警示**：列印頁頂部紅字「⚠ 簽收表標題未設定…」（`_refresh_title_warn`，`on_activated` 刷新），純勸導不擋產生
- **跨年度重置不清這四 key**（機關名是單位永久設定，`performYearEndReset` 只清 `archive_*`）。純邏輯測試 `tests/test_print_titles.py`

### 系統設定子頁（settings_panels.py，v1.1.6）

設定 Tab6 第 5 個 nav 子頁「系統設定」（`inner_stack` index 4，`_PAGE_SYSTEM`），QScrollArea 內直排四個嵌入面板（`ui_utils/settings_panels.py`，QGroupBox）。取代原 nav 兩顆鈕＋兩個 Dialog（`ArchiveRootDialog`／`PrintTitleDialog` 已刪，邏輯原樣搬入面板）：

| 面板 | 內容 | 權限 |
|------|------|------|
| `ArchiveRootPanel` | 年度層 UNC 路徑＋刑案/一般子夾（兩欄並排固定寬） | admin／archive 皆可改 |
| `PrintTitlePanel` | 簽收表四格（2×2 等寬撐滿）＋恢復預設 | 僅 admin，archive 整塊反灰 |
| `IdleTimeoutPanel` | 閒置自動登出／強制關閉（NoButtons spinbox，0＝停用） | 僅 admin，archive 整塊反灰 |
| `InputLockPanel` | 唯讀設定：三個勾選框停用一般使用者對交辦收文／刑案陳報／一般陳報的**新增**（存 `App_Settings`，即時生效） | 僅 admin，archive 整塊反灰 |

> `tab_settings` 掛載處（建立、`_applyRolePermissions` 反灰、`_loadSystem` reload、`_dirtyPanels` dirty）四份清單都要含新面板；面板由 `ui_utils/__init__.py` 匯出。

- **儲存鈕 UX**：各面板獨立「儲存」（墨藍樣式）。**未變動反灰、改值即亮、存檔成功直接回灰**＝完成回饋，無成功彈窗。回灰前先 `clearFocus()`——Qt 停用「持有焦點的元件」時會把焦點塞給 tab 順序下一個輸入欄（游標亂跳、QScrollArea 跟著捲）
- **dirty 追蹤**：`reload()` 存值快照 `_loaded`，`isDirty()` 比對畫面值。切子頁／切出大 Tab 沿用 `_promptUnsaved`（併入面板 dirty，噪音字依來源顯示「排序／設定」）；按「儲存」批次呼叫 `panel._save()`（回 bool，被擋則留在頁面）；登出＝放棄（`_onRoleChanged` reload）
- **權限 gate**：面板整塊 `setEnabled` 之外，各 `_save()` 開頭都有 `is_admin()`／`is_manager()` guard 保底（防替代觸發路徑，見 CLAUDE.md 紀律）
- **下游刷新免處理**：列印頁（`_onShown` 重算紅字＋標題指紋）、歸檔頁（`_onShown` 重讀根目錄）、瀏覽頁（開檔時讀）皆顯示時重讀；PDF 索引快取由 `_save` 內 `clearPdfIndexCache()` 清

### 跨年度重置（Reset，tab_settings.py）

設定 Tab nav 底部「跨年度重置」（紅字，admin 才可操作）。**破壞性操作**。

流程（`_doReset()`）：① `ResetDialog` 列出將清除的停用項目、要求手輸 `RESET`、防誤按（確認鈕非 default、輸入框不綁 Enter）② 自動備份 `dbfile.db`→ 同目錄 `dbfile_backup_YYYYMMDD_HHMMSS.db`（失敗中止）③ 詢問是否另存一份至指定位置 ④ `performYearEndReset()`（單一 transaction，失敗 rollback）⑤ 完成訊息（提示重啟後至「系統設定」重設歸檔資料夾；v1.1.6 起不再於重置後直接開設定流程——重啟後首次登入設定頁的三層警示會導頁）→ `_restartApp()` 重啟。

`performYearEndReset()`：清三主表＋`Audit_Log`＋`Trash_Documents`；**刪除**停用（is_active=0）項目（dialog 事前列出讓使用者有機會先啟用保留）；依 sort_order **重編參照表 id**（連續，維持原前綴位數，如 P01/D01/CT01）；sort_order 重設連續整數；歸零 `Seq_DocId`；清空歸檔根目錄設定（`archive_*`，強制新年度重新指定）；**commit 後 `VACUUM`**。

> ⚠️ **重置必 VACUUM**：`DELETE` 只把資料頁列入 free-list、檔案不縮，且被刪的舊年度公文（含個資）實體殘留在空閒頁（`strings` 掃得到）。故 commit 後跑 `VACUUM` 重建整庫→ 縮檔並清除殘留。VACUUM **不可在 transaction 內執行**，置於 `conn.commit()` 之後。（`tools/gen_shell_db.py` 產空殼是全新建立、無 DELETE，本就乾淨且結尾亦 VACUUM，非同一問題。）

> ⚠️ 重編 id 採**兩段式**避撞 PK：先把所有列改成暫時前綴（`__TMP__P0001`…）再編回正式 id。**別改成單段直接 UPDATE**，舊新 id 集合有交集會撞 PRIMARY KEY

### 歸檔根目錄未設定警示

重置後／首次安裝歸檔根目錄為空，三層提醒：① 瀏覽 Tab4（`on_activated`）篩選列右側紅字 ② 歸檔 Tab5（`on_activated`/`_onShown`）資料夾列右側紅字 ③ 設定 Tab6（`on_activated`）每次登入首次進入彈一次確認框（`_arch_warn_shown` flag 控制，重新登入後重置），按「前往設定」導航到「系統設定」子頁（v1.1.6 前為直接開 `ArchiveRootDialog`）。

> **重啟（`_restartApp()`）**：⚠️ **打包版啟動新程序前必設 `PYINSTALLER_RESET_ENVIRONMENT=1`**（PyInstaller 6.10+ 官方機制），否則新程序沿用舊 `_MEI`、載入已刪 DLL 而崩潰（見踩雷表 #9）。重置後資料全變，故用整程序重啟取代逐一刷新 Tab，最乾淨

---

## 6. 資料庫結構

> 主表欄位以 `lib/db_schema.py` 與 `PRAGMA table_info` 為準（此處只記關係與關鍵語意，避免與 code 不同步）。

- **三主表**：`Document_Task`（交辦）／`Document_Criminal`（刑案）／`Document_General`（一般），PK `doc_id`（VARCHAR 流水號）。各參照欄存對應參照表 ID
- ⚠️ **關鍵語意**：`receive_date`／`report_date` 為 **NULL＝已刪除**（軟刪除空殼）；`is_reported`（紙本稽核用，預設 0）；`is_electronic`（**空字串＝未歸、填檔名＝已歸**，預設 `''`）

### 參照表

| 資料表 | 欄位 |
|--------|------|
| Ref_Personnel | staff_id / staff_name / **alias** / is_active / **sort_order** |
| Ref_Departments | dept_id / dept_name / is_active / sort_order |
| Ref_CaseTypes | case_type_id / case_type_name / is_active / sort_order（52 種） |
| Ref_Case_Status | status_id / status_name（CS01~CS03，hardcode 不動） |
| Ref_General_Category | gen_cat_id / gen_cat_name（GC01~GC03，hardcode 不動） |
| Seq_DocId | table_name / last_id（nextDocId() 維護，Reset 歸零） |

### 其他表

| 資料表 | 說明 |
|--------|------|
| App_Settings | key / value。權限 key：`admin_password_hash`（預設 `admin`）／`archive_password_hash`（預設 `0000`，v1.1.0 起空殼內建）；另 `archive_root`／`archive_subdir_crim`／`archive_subdir_gen`（Reset 清空）、簽收表四 key（見 §5）、閒置逾時 `idle_logout_min`／`idle_close_min`（v1.1.6，分為單位、0＝停用、Reset 不清） |
| Audit_Log | log_id(PK AUTOINCREMENT) / ts / role / action / target_table / target_id / operator / detail。由 `ensureSchema` 建立，詳見 §3 |
| Trash_Documents | trash_id(PK AUTOINCREMENT) / table_name / doc_id / payload(整列 JSON) / subject / doc_person / deleted_ts / deleted_role。由 `ensureSchema` 建立，詳見 §3 |

### Views

| View | 說明 |
|------|------|
| View_Task_Full | 含狀態判斷（剩餘天數/逾期/已發文，DB 端算） |
| View_Criminal_Full | JOIN 所有參照表，案類 COALESCE 舊資料 |
| View_General_Full | JOIN 所有參照表 |

---

## 7. 打包（PyInstaller 6.20.0）

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
- 共用 icon（`arrow`／`icon_pdf`／`icon_archive`／`icon_paper`／`icon_help`）及 `res/buttons/*.svg`（`:/btn/`）、`res/tabs/*.svg`（`:/tab/`）已透過 `resources_rc.py` 內嵌、不需 `--add-data`；改了要重編 qrc（`pyside6-rcc res/resources.qrc -o res/resources_rc.py`）。`res/buttons/*.svg`／`res/tabs/*.svg` 由 `tools/gen_buttons.py` 產出
- matplotlib 只用 `backend_agg`（PNG）+ `backend_pdf`（存 PDF），其餘全排除
- 指令開頭 `del ...spec & rmdir build dist` 是刻意的（不信任殘留 spec 的過期設定，每次砍掉全新生成）；`2>nul` 讓首次執行不報錯
- ⚠️ **跨年度重啟**：onefile 版重啟新程序前必設 `PYINSTALLER_RESET_ENVIRONMENT=1`（否則 `Failed to load Python DLL`／`unicodedata` 缺，`_restartApp()` 已處理，見踩雷表 #9）
- 打包報 `No module named res`／`lib.xxx` → 補對應 `--hidden-import`
- **exe 檔案資訊**由 `--version-file version_info.txt` 帶入；該檔由 `tools/bump_version.py` 進版時連同版號產生（已收進 git），改顯示文字改該腳本頂部常數
- GitHub release 上傳用英文檔名

### 發 GitHub Release（4 個 asset，比照歷版）

CLAUDE.md 發布流程第 7 步的執行細節。4 個 asset：

1. `Police-Document-Manager.exe`（本次 build 的 onefile，在 `dist/`）
2. `dbfile.db`（**乾淨空殼**——⚠️ 自此**改用 `python tools/gen_shell_db.py <暫存路徑>` 產生**，不再從 git HEAD 取二進位。schema 來自 `lib/db_schema.py`、種子來自 `lib/db_seed.py`，兩者是唯一來源，產出即與程式碼一致。例：`python tools/gen_shell_db.py 暫存/dbfile.db --force`。**不要用工作區根目錄那份**（真實測試資料）。⚠️ 動過 schema／種子後，git HEAD 的 `dbfile.db` 也要由維護者用本腳本重產並重新 commit，讓 no-pii 測試掃描的空殼與程式碼同步）
3. `PACKED.zip`（= exe + dbfile.db **兩檔扁平放根目錄**，無子資料夾）
4. `Quick_Start.pdf`（速查卡）——⚠️ `docs/` 已 gitignore，發版前先跑 `python tools/gen_quickstart.py` 重產到 `docs/Quick_Start.pdf` 再上傳（內容單一來源 `ui_utils/help_content.py` 的 `QUICKSTART`）

- **打包 zip（PowerShell）**：`Compress-Archive -Path 暫存\dbfile.db,暫存\Police-Document-Manager.exe -DestinationPath 暫存\PACKED.zip -Force`
- **建 Release + 一次傳四檔**：
  ```
  gh release create v{版號} --title "v{版號}" --notes-file release_note_v{版號}.md \
    "dist/Police-Document-Manager.exe" "暫存/dbfile.db" "暫存/PACKED.zip" "docs/Quick_Start.pdf"
  ```
  （asset 多於一個直接列在 create 後；或先 create 再 `gh release upload v{版號} <檔> --clobber`）。收尾刪暫存資料夾
- **gh 環境**：已裝（本機 `C:\Program Files\GitHub CLI\gh.exe`，新 shell PATH 沒帶到用全路徑），帳號 `jerrygskk` 已登入（token 存 keyring）。`gh auth login` 互動式、非互動 shell driver 不了——日後登出需重登由維護者本機自己跑

---

## 8. 版本記錄

> 版本號單一來源 `lib/version.py` 的 `__version__`。**進版用 `python tools/bump_version.py <版號>`**（版號自帶不自動進位；同時改 `version.py` 與產 `version_info.txt`）。本表與 git tag（`v{__version__}`）手動對齊。⚠️ 勿手改 `version.py`，否則 `version_info.txt` 不同步。

| 版本 | 摘要 |
|------|------|
| v1.1.5 | **多機共用穩定性**：閒置強制關閉由 20 分改 **14 分半**——DB／`dbfile.lock` 在 SMB 網路碟，須搶在 Windows（AD）15 分鎖螢幕**之前** `os._exit` 並清鎖檔，否則 A 鎖螢幕後程式仍在背景續更新心跳，會卡住別台電腦的 B 登入。**權限修正**：歸檔管理（archive）唯讀身分可經**序號欄雙擊行內編輯**改排序、再把已反灰的「儲存排序」鈕點亮存回 DB＝權限繞過，於 `_onCellClicked`／`_onSeqItemChanged` 補 `_refEditable()` guard。**設定頁排序**：序號欄改**單擊**進行內編輯（原雙擊），呼應框中數字的可點提示；名稱欄維持雙擊開修改對話框。**UI 一致性**：資料庫瀏覽表格改 `NoSelection`＋`NoFocus`（點擊不再留黑框與選取反白，統一為操作紀錄／回收筒行為）；歸檔候選 PDF 操作鈕加手指游標。**重構（使用者無感）**：設定頁六個參照項 add/edit 收斂為 `_addRef`／`_editRef`＋`_REF_DIALOG` 對照表；資源回收筒自 `tab_settings` 抽成 `ui_utils/trash_panel.py` 的 `TrashPanel`（tab_settings 由 1175 行降至約 960 行）。 |
| v1.1.4 | **安全性**：登入密碼比對改 `secrets.compare_digest` 常數時間（防時序攻擊）；歸檔 `os.rename` 前以 `os.path.commonpath` 二次驗證落點仍在歸檔夾內（防禦縱深）。**變更密碼後自動登出**，要求以新密碼重新登入。**可空白日期框治本**：查獲日期等「可留空又要手打」欄位由 `QDateEdit`＋`minimumDate` 哨兵改為 `NullableDateEdit(QLineEdit)`——可整格清空自由手打、離開即驗證亮紅框並擋送出、validator 只放行數字與 `-`/`/`、月曆無格線無週數欄（套陳報頁查獲日期／刑案編輯框／稽核起迄）。**重構（使用者無感）**：錯誤彈窗統一走 `ui_common.reportError`（寫完整 traceback 進 error.log＋彈白話訊息），取代直接把 SQLite 英文原文丟給使用者；獨立稽核事件抽 `db_utils.writeAuditSafe`（自開連線寫一筆）；設定頁小去重。 |
| v1.1.3 | **內部重構為主，無使用者新功能。** **schema／種子改為程式碼唯一來源**：全部資料表＋3 View＋6 trigger 的 DDL 收進 `lib/db_schema.py`（`_TABLES`／`_VIEWS`／`_TRIGGERS`，新增 `applySchema()`），種子資料（參照／預設密碼／Seq 歸零／簽收表四 key 空值）收進新檔 `lib/db_seed.py`；新增 `tools/gen_shell_db.py` 由這兩者產乾淨空殼，取代發版「從 git HEAD 取二進位」。單元測試改用同一份 schema（移除手刻假 schema），消除測試與正式 schema 走鐘的隱患。**UI 修正**：tab 切換的延遲 `resize`／`setFocus` callback 加守門，快速連續換頁不再作用到舊 tab。**Repo 維護**：`dbfile.db` 改為不入庫（gitignored，schema／種子已在程式碼）；以 `git filter-repo` 將歷史中含資料／識別資訊的舊檔（DB／Excel／初始化 SQL 等）自全歷史抹除。 |
| v1.1.2 | **簽收表標題可自訂**：設定頁新增「簽收表設定」鈕（僅 admin、歸檔管理反灰）→ `PrintTitleDialog`，可自訂三張簽收表標題與現行犯免簽收註記，存 `App_Settings` 四 key、未設定走 `○○` 預設＋列印頁紅字提醒、跨年度重置不清（單位永久設定）。**簽收表排版修正**：欄內換行改用 matplotlib 真實字型度量（修主旨／案類欄寬還夠卻提早折行）、刑案類型欄固定 10pt。**權限修正**：收文／陳報頁刪除誤擋成僅 admin，改為一般使用者可刪（與權限矩陣一致）；移除無用的 `AuthManager.can()`。**刪除流程合併**：四處「快照→回收筒→清空→稽核」收斂為 `db_utils.softDeleteDoc`。**簽收表 PDF 改前景產生**＋「產生中」popup（消除偶發崩潰）。**閒置自動關閉改 `os._exit` 硬關**（穿透 modal）。**重構**：通用 UI 自 `db_utils` 搬至 `ui_utils/ui_common.py`，`db_utils` 回歸純資料層。速查卡改版、HELP 權限／法規用語修正。 |
| v1.1.1 | **誤刪還原（資源回收筒）**：主表刪除前先把整列快照存入 `Trash_Documents`，設定頁新增「資源回收筒」子頁（僅 admin）可單選還原，把快照寫回原文號、保留刪除當下歸檔狀態，並寫一筆「還原」稽核；跨年度 Reset 一併清空。**啟動冪等建表 `ensureSchema`**（`lib/db_schema.py`）：附加式結構改於啟動時自動套用，新增資料表不再需要發 fix 工具（破壞式仍走手動）。**操作紀錄頁介面整理**：新增「重整」鈕、身分／類別下拉去外部標籤改首項自述、篩選列字級收斂。**主選單顯示修正**：打包版偶被其他視窗壓住，改顯示後強制拉到最前。另含一輪 code review 修正（DB 連線改 `finally` 釋放、刪除入口補權限檢查、`_trimName` 收斂單一實作）。 |
| v1.1.0 | **稽核大版本（特別版，含現場升級工具）**。**三角色權限＋操作稽核**：新增 `user`／`archive`／`admin` 三角色（兩組密碼），關鍵操作寫 `Audit_Log`，新增「操作紀錄」檢視 Tab7（僅 admin、可篩選／匯出 CSV）。**效能**：瀏覽頁 cellWidget 改純 item＋啟動預載建表（載入畫面進度條）。**安全性**：錯誤訊息白話化、搜尋不分大小寫、閒置 10 分自動登出＋20 分自動關閉、APP 層軟性互斥（`dbfile.lock` 勸導）。**平時自動備份**：啟動時 GFS 輪替（每日 7／每週 4，本機 `backups/`）。**主選單**改 2 欄圖示磚格；dev 工具收進 `tools/`。⚠️ 升級舊庫前置：先 `fix_cat_status`（未套過 v1.0.9 者）再 `fix_audit_setup`（建 `Audit_Log`＋設兩組密碼）。 |
| v1.0.9 | **發文分類／案件狀態正規化**：`Ref_Case_Status`／`Ref_General_Category` 顯示名去字母前綴、縮為兩字，View 撈出即顯示，移除程式端 `_STATUS_MAP`／`_CAT_MAP`；現行犯免簽收判斷改以 `case_status` ID（`CS01`）比對。收編 5 筆未正規化的孤兒分類。一次性修補 `fix_cat_status.py`（執行前自動備份、不入庫）。**HELP 視覺優化**：說明內按鈕／子頁籤改用預烤圓角 SVG、文字校正；`res/` 圖片集中到 `res/buttons/`＋`res/tabs/`。 |
| v1.0.8 | **程式內 HELP**：每個大 Tab 右上角新增 help 說明鈕，點開該頁「使用說明」彈窗（七頁，Apple HIG 編排、鋼藍色帶、警徽 LOGO）；各欄位／按鈕加 tooltip。內容單一來源 `ui_utils/help_content.py`；彈窗元件 `ui_utils/help_dialog.py`。新增 `res/icon_help.svg`。**協作文件**：CLAUDE.md 補「一律台灣用語」。 |
| v1.0.7 | **歸檔頁**：PDF 電子檔歸檔成功時連帶標記紙本已歸（`_doArchive` 一併寫 `is_reported=1`）；待歸清單選取列改藍底深藍字、消焦點黑框。**簽收單列印**：開預覽前預設彩色（`setColorMode(Color)`）＋長邊雙面（`setDuplex(DuplexLongSide)`）。 |
| v1.0.6 | **歸檔頁**：修正承辦人解析會把案由詞（如「竊盜案」）與括號內報案人誤判成承辦人之 bug。承辦人界定改為「從檔名尾端往前、能對到 DB 人名字典（含去姓 2 字／別名）才收，對不到即停」；主旨剝承辦人改字典迴圈。承辦人／主旨解析純邏輯抽進 `lib/archive_text.py`（`_resolveNames`/`_parseSubject`），新增單元測試（含去識別化真實檔名語料）。 |
| v1.0.0–1.0.5 | 早期版本：正式版（瀏覽頁 PDF 圖示鈕、歸檔資料夾 UNC、歸檔頁帶入預設夾）→ 別名初版（alias 欄）→ 拖拉排序、歸檔未設定三層警示、瀏覽搜尋改全量載入＋`setRowHidden` → 陳報頁刑案/一般合併單一版面 → 重載鈕、設定改名就地反映、「更新中」提示、檔名過濾、搜尋 try/finally、精簡/完整單顆切換鈕；標題列＋exe 顯示版本號（`bump_version.py`）。詳見 git tag。 |
