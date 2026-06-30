# 給接手者（Claude 請先讀這節）

這節讓你在新對話中快速進入協作狀態。

## 這是什麼

- **技術棧**：Python + PySide6（Qt）+ SQLite，純桌面單機程式
- **使用者**：警察單位承辦人員
- **目標環境**：Windows，顯示縮放 **125%**，全域字體 **14pt**
- **打包**：PyInstaller 打成單一 exe（`--onefile`）
- **資料**：軟刪除（清空欄位、保留 `doc_id`），不做真 DELETE
- **文件分工**（2026-06-28 起）：`README.md`＝**使用者門面**（簡介／省時／功能／部署／FAQ，含 `docs/img/` 截圖）；`DEVELOPER.md`＝**技術文件**（架構／踩雷／打包／DB 結構／版本記錄，即原 README 內容）；`CLAUDE.md`＝協作規則（本檔）；`docs/handover.md`＝跨對話交接（不入庫）

## README 撰寫定義（使用者門面）

README 寫給**完全不懂程式、也不懂運作原理的新使用者**，純粹從介面「說故事」。改 README 一律遵守這五點：

1. **看畫面說故事**：假定讀者只看得懂介面、不懂技術與原理。用截圖＋情境帶過，不解釋程式怎麼運作。
2. **價值先行**：先讓使用者知道「這程式能做什麼」「幫他省下哪些時間成本」，而非先講功能清單。
3. **快速上手＋導流**：給得出能照做的使用情境，讓使用者快速部署；想深入的，導向 `Quick_Start` 速查卡或 User Manual（使用手冊）取得細節，README 本身不塞滿。
4. **白話功能說明＋術語 TIP**：功能說明淺顯易懂；非用術語不可時，**在該段落下方加 TIP／💡 註解**白話解釋，不讓術語擋路。
5. **精簡、列點、業界風**：別為了講一個功能長篇大論；**能列點就列點**，排版與口吻參考業界 README 慣例。

- **語調**：簡潔專業型（不口語、不浮誇、不過度親切；資訊密度高、句子短）。
- **截圖工作流**：Claude 在容器內**開不了 GUI、截不了圖**。需要畫面時，**列出明確截圖清單（畫面／要框的重點／檔名）請維護者截給**，存 `docs/img/`（`.gitignore` 已放行此夾）。現有截圖：`01-main-menu` / `02-browse-overdue` / `03-dispatch` / `04-archive` / `05-print-preview` / `06-recycle-bin` / `07-archive-folder`。

## 動手前先做這幾件事

0. **開新對話先讀 [DEVELOPER.md](DEVELOPER.md)**（至少第 1～3 節）— 進入任何任務前的第一動作，不要略過。⚠️ [README.md](README.md) 自此改為**給使用者看的門面**（簡介／部署／操作），技術內容全在 DEVELOPER.md
1. **讀 DEVELOPER.md 第 1 節**（架構心智模型）— 了解程式怎麼跑起來、資料怎麼流
2. **掃 DEVELOPER.md 第 2 節**（踩雷速查表）— 不看就會踩，而且有些踩過還會再踩
3. **對齊 DEVELOPER.md 第 3 節**（慣例與設計決策）— 為什麼這樣寫，不要自作主張改掉

## 協作偏好（務必遵守）

這是維護者最看重的部分。違反這些會直接消耗他的信任與時間。

### A. 跟他互動（溝通與節奏）

#### 動手節奏

- **先思考再動手**：任何寫 code 的任務，先思考、發想多個方案、整理成計畫給他看，經他核可後才開始寫 code。不要做完才說「其實有更好做法」。重大改動先給示意圖 / 大綱 / 影響範圍清單，等他點頭再寫
- 複雜或破壞性的改動（牽動多檔、改結構、改資料），**先盤點影響範圍列清單**給他看
- 要 Claude **基於專業判斷給建議，且適時提供業界或主流修改方式**。反感「見風轉舵」他說 A 你立刻倒向 A、還拿他的話包裝成你的判斷，這會被點名。有不同意見就誠實講，講完理由讓他決定

#### 找得到就別問

- README / DEVELOPER.md / code / dbfile 裡找得到答案的不要問
- 但**沒寫進文件的設計決策**（例如「歸檔 Tab 要做什麼」）一定要問，不要憑空假設

#### 回覆風格（對他說話時）

- **直接切入重點**：不說客套話（「好的」「沒問題」「這是個好問題」）
- **免除前言後語**：直接輸出核心答案，不要開場白（「以下是為您整理的…」）與結尾總結（「希望以上對您有幫助」）
- **精簡文字**：列點、短句、精準詞彙，在不影響理解與準確度下用最少字數
- **主動提醒斷點**：對話累積過長時，回覆結尾加「[提示：對話已長，建議備份摘要並開啟新對話]」

### B. 產出（程式與檔案）

#### 提供產出

- 直接修改本地端 code
- **code 不主動整段貼出來**，他要看才給
- **不用跟維護者告知改了什麼 function**，遇到同檔名檔案（如 `__init__.py`）須告知放在哪個資料夾，產出文字只需簡單說明不長篇大論
- **README（使用者門面）與 DEVELOPER.md（技術文件）都不主動改**，他要才改；DEVELOPER.md 在「發布版本」流程除外（該流程要更新技術章節與 §8 版本記錄）
- git add / commit / push 規則見下方 C 群「用語約定」

#### 寫 code 的紀律

- **省 token**：先讀完相關檔案再動手，`str_replace` 範圍要精準
- ⚠️ **`str_replace` 容易吃掉相鄰的 `def`**：改完後務必 `grep` 確認上下相鄰的函式定義還在（這個錯在開發時犯過多次，每次都害他重新測試）。尤其是「在某方法前後插入新方法」「刪除某方法」時最容易發生
- 改完檔案**先 compile（`py_compile`）驗證語法**，並**主動自我迭代驗證**：能寫單元測試就寫單元測試、能模擬的邏輯（演算法、SQL round-trip）就模擬跑一輪，依結果自行修正再給他，不要把未驗證的 code 直接丟給他。容器**有 PySide6 可 import**（能跑非 GUI 的純邏輯單元測試），但**無法開 GUI 視窗 / 截圖**（等同無 puppeteer / 模擬器可截圖）——Tab 互動、Dialog、表格渲染這類主動告知他、請他上機測
- **單元測試在 `tests/`**（已入庫，純邏輯回歸測試）：跑法 `python -m unittest discover -s tests`，檔名 `test_*.py`（unittest 探索預設，勿改名）。**動到可單測的純邏輯**（檔名/文字解析、SQL round-trip、狀態/逾期計算、權限判斷）時，**一併新增或更新對應測試**再交付。詳見 DEVELOPER.md §4「單元測試」
- ⚠️ **動手前對照踩雷表**。寫過的雷再踩會被直接點名

#### 文字風格（UI 用語）

- UI 上給使用者看的提示文字要**正式**，不要口語（例如不要寫「排序未儲存，要存嗎？」，要寫「儲存目前排序後繼續編輯？」）
- **一律用台灣用語**（對話、文件、UI 皆然），不用大陸用語：軟體、程式、預設、滑鼠、檔案、資料夾、登入/登出、視窗、按鈕、回傳、字串、迴圈、品質、網路、硬碟……等

### C. 版本 / Git / 發布 / 打包

#### 版本號

- 版本號定義於 `lib/version.py`，進版時只進第三碼
- 進位與否他決定，不要自己跳版號
- **進版一律跑 `python tools/bump_version.py <版號>`**（從專案根目錄執行；版號自帶、不自動進位；會先印出目前版號），它會同時改 `version.py`、產出 `version_info.txt`（exe 檔案資訊）、並同步 `README.md` 門面兩處「目前版本」版號。**勿手改 `version.py`**，否則 `version_info.txt` 不同步

#### 用語約定（他會用簡稱，要對上）

- **「進版」** = ⚠️ 維護者說「進版」＝**要求走完整發布流程，直到 GitHub Release 上架（4 asset）才算結束**（等同「發布版本」，見下方標準流程，含 build＋發 Release）。**別只做「bump＋tag＋§8」就回報完成**——那只是流程中的一步。其中「跑 `python tools/bump_version.py <版號>`（機制見上「版本號」節）＋打 git tag `v{版本號}`＋DEVELOPER.md §8 補一列版本記錄」這組機械動作另稱「**版號進版**」（流程第 4 步）
- **「push上去」、「推上去」** = 把改動 commit + push。**逐檔 add**（當輪或上次 push 後改動的檔案逐一 add，**不要一次全加**，跳過 `dbfile.db`）；**叫你推才推**，沒說不要問「要推嗎？」
  - ⚠️ 根目錄 `fix_*.py`／`seed_*.py` 刻意**不入庫**（現場交付 / 壓測丟棄腳本），逐檔 add 時跳過、勿 git add、勿誤刪。
  - ⚠️ **多行 commit 訊息用 Bash tool 的 heredoc**（`git commit -F - <<'EOF' … EOF`），**不要用 PowerShell here-string `@'…'@`**——它在 Bash 不被解析，`@` 會被當訊息第一行黏進 subject。（這個雷踩過多次）
- ⚠️ **push 前必確認無真實人名／個資**：要 commit／push 的內容（含測試 fixture 檔名、文件範例、`dbfile.db`）不得含真實人名，有則先替換成虛構佔位名才能推。`dbfile.db` 只能是**乾淨空殼**（人員僅佔位、無公文），且提交前先 `VACUUM`（刪除的資料會殘留在 slack space，strings 掃得到）。
  - 自動防呆：`tests/test_no_pii.py` 會比對本機 `tests/pii_denylist.local.txt`（真名清單，已 gitignore 不入庫）掃描 git 追蹤內容＋已提交的 `dbfile.db` blob，命中即 fail。**push 前跑一次 `python -m unittest tests.test_no_pii`**；有新進真名就補進該清單。
- **release note** = 給 `.md` 檔（`release_note_v{版號}.md`，比照前版**不入庫**，留著貼 GitHub Release）。**不要直接打在對話裡**（會被渲染、無法複製原始碼）；內容寫給使用者看（功能 / 改進 / 修正），技術細節留 DEVELOPER.md
- **「發布版本」、「出一版」、「進版」** = 見下方標準流程（三者同義，皆走完整流程到 GitHub Release 上架才算結束）

#### 發布版本標準流程（他講「發布版本」「出一版」「進版」時，照順序做到底；各步用語見上「用語約定」）

1. **寫文件內文**：技術章節補進 **DEVELOPER.md** 對應章節（不只 §8 版本記錄列）；若是使用者有感的功能 / 操作改動，**README**（使用者門面）也一併同步
2. **寫 handover**（跨對話需交接才寫，否則略過）
3. **寫 release note**
4. **版號進版**（跑 `python tools/bump_version.py <版號>`；DEVELOPER.md §8 版本記錄列在這步補）
5. **推上去** + 打 tag `v{版號}` + push tag
6. **build**：onefile 全新 build（見 DEVELOPER.md §7），回報成功 / 失敗
7. **發 GitHub Release**（4 個 asset：exe／乾淨空殼 `dbfile.db`／`PACKED.zip`／`Quick_Start.pdf`）。**完整指令、各 asset 取得方式（`dbfile.db` 改用 `python tools/gen_shell_db.py <暫存路徑>` 產生——schema／種子唯一來源在 `lib/db_schema.py`＋`lib/db_seed.py`；`Quick_Start.pdf` 先跑 `gen_quickstart.py`）、`Compress-Archive` 打包與 gh 環境，見 [DEVELOPER.md](DEVELOPER.md) §7「發 GitHub Release」。**

> ⚠️ **順序鐵則**：DEVELOPER.md（及有改到的 README）/ release note 要在「版號進版 commit」**之前**寫好，tag 才會直接指向含完整文件的 commit。別先進版打 tag、事後才補 DEVELOPER.md——那樣得退版重做。
> ⚠️ tag 已 push 後要移動：本地 `git tag -f` 後，遠端**先刪再推**（`git push origin :refs/tags/v{版號}` 再 `git push origin v{版號}`），否則遠端 tag 仍指舊 commit。

#### 打包（PyInstaller）

- **只用 onefile**，不要問要哪種打包方式
- 習慣**每次砍掉 spec 全新 build**（不信任殘留 spec 會帶過期設定）。打包指令見 DEVELOPER.md 第 7 節，開頭已含清除步驟
- **build 一律用 PowerShell tool**（不用 Bash tool）：`del /q` / `rmdir /s /q` 是 CMD 語法，Bash tool（Git Bash）不識別會靜默失敗，spec 和 dist 不會被清掉
- Claude 可直接在本機執行 build，完成後只回報成功/失敗（失敗才貼錯誤末段）

---

## 踩雷速查表（動手前必掃）

依主題分組；每條為「**症狀** → 解法（必要時括註原因）」。寫過的雷再踩會被點名。

#### 1. `.ui` 載入
- **`Unable to open/read ui device`** → margin 改用 `leftMargin`/`topMargin`/`rightMargin`/`bottomMargin` 四獨立 property，勿用 `contentsMargins`+`<rect>`。
- **`centralWidget()` 回 None** → central widget 物件名必須全小寫 `centralwidget`。

#### 2. Qt 樣式／顏色
- **狀態色（紅/橘/綠）、停用灰字失效** → `QTableWidget::item` 只設 padding/border，文字色一律交 `setForeground()`（`::item{color}` 優先級會蓋過它；`:selected` 的 color 可留）。⚠ 動表格樣式前先查這條。
- **顏色被 stylesheet 蓋掉** → 用 `QColor("#hex")`，勿用 `Qt.red` 等列舉。
- **新 Dialog/Widget 文字看不見（深色底）** → 每個新 `QDialog`/`QWidget` 明設背景+文字色（繼承全域深色所致，範例見 DEVELOPER.md §5）。
- **`setEnabled(False)` 按鈕沒變灰** → 該按鈕的 stylesheet 要含 `QPushButton:disabled { ... }`。
- **設灰字連月曆／下拉清單也變灰** → 用型別選擇器 `QDateEdit { color: ... }` / `QComboBox { color: ... }`，避免裸 `color:` 繼承到子元件。

#### 3. Qt 元件行為
- **`clicked` callback 首參變成 `False`** → lambda 吃掉 Qt 多塞的 `checked`：`lambda _=False, k=key: ...`（否則 `dict[False]` KeyError）。
- **`QTableWidget`/`QAbstractScrollArea` 滾輪攔不到** → 滾輪事件在 `viewport()`：於 `table.viewport()` `installEventFilter` 攔 `QEvent.Wheel`，filter 存成屬性防 GC（覆寫 `wheelEvent` 無效）。
- **confirmBox 確認/取消鈕被左右調換** → 兩鈕都用 `ActionRole`（`AcceptRole`/`RejectRole` 會依 OS 慣例調換），手動 `setDefaultButton`+`setEscapeButton`。
- **`QDateEdit` 月曆打開停在 1752／空白哨兵相關亂象** → minimumDate 哨兵所致。**必填**日期欄（預設今天、不需空白）用 `setupDateEditToToday` 捲到今月即可。**可留空又要手打的欄位千萬別用 QDateEdit**——拿分段遮罩 spinbox 當可空白欄會反覆出包（空白時鍵盤打不動、亂點冒 `1752/1753` 殘值、整格清空後手打半成品被 fixup 還原）。改用 `NullableDateEdit`（QLineEdit 子類，治本，見 DEVELOPER.md §5「可空白日期框」）。

#### 4. 版面／模式切換抖動（多見於 `tab_report._switchFormType`）
- **隱藏列幽靈間距、兩模式下方表格高度不一** → `verticalSpacing=0`、列距改 `setRowMinimumHeight`；兩模式 form 總高設成相同固定值（如刑案 4×45、一般 3×60＝180）。
- **show/hide 時整排左右跳、同欄兩模式寬度不同** → `setColumnMinimumWidth` 鎖結構性欄寬；col0 寬取最寬標籤 `sizeHint().width()`（勿寫死）。QGridLayout 欄寬只按當前可見 widget 算。
- **切 tab 共用列上的按鈕上下跳** → 共用列兩模式設相同 row min height。
- **`setupPreviewTable` 的 200ms autoResize 覆蓋手設欄寬** → 要自控欄寬就別用它；彈性欄 `QHeaderView.Stretch`、固定欄 `Fixed`+`setColumnWidth`。
- **浮貼按鈕（絕對定位）在非當前頁重複/錯位** → 改放 GroupBox 內 HBox 標題列走正規 layout（非可見頁 layout 寬=0 所致）。

#### 5. Tab 切換攔截
- **從設定 Tab 切走時攔不住「未存」** → `currentChanged` 是切換後才觸發：大 Tab 只能切過去後補跳提示；子頁切換（按鈕觸發）才攔得住、可「取消＝回原狀」。

#### 6. SVG／icon
- **Material icon 白邊太多／在按鈕裡偏一邊** → 裁 viewBox 到圖案實際 bounding box 並置中、移除非對稱裝飾，width/height 統一 512px（`0 -960 960 960` 圖案只佔中央 70%）。
- **HELP 新增按鈕顯示破圖佔位符** → `tools/gen_buttons.py` 只產 SVG、**不會自動登記 qrc**；新增 key 後須手動在 `res/resources.qrc` 補 `<file alias="btn/<key>.svg">buttons/<key>.svg</file>` 再 `pyside6-rcc res/resources.qrc -o res/resources_rc.py` 重編。

#### 7. 資料／SQL
- **`ORDER BY sort_order` 新項跑到最前** → 新增時給 `sort_order = MIN(sort_order)-1`（空表 fallback 1）；NULL 會被 SQLite 排最前。
- **軟刪除空殼出現在待歸檔清單** → `_queryUnarchived`/`_tableSignature` 排除底層案由欄為 NULL 者；**任何「待處理」查詢都要排除軟刪除空殼**。
- **可空下拉的 NULL 舊資料被靜默改成清單第一項** → 建檔可為 NULL 的下拉，建時與編輯時都 `addItem("", None)` 空白哨兵（見 `edit_dialog.py`）；否則 `_set_combo_value(None)` 停在第一項、存回真 id 連必填都騙過。
- **編號欄超連結＋純文字重疊** → `setDocIdLinkCell` 切換前互清：連結分支先 `takeItem`、純文字分支先 `removeCellWidget`（item 與 cellWidget 兩套獨立儲存）。
- **瀏覽頁搜尋整個沒反應／取到錯列** → ① `_allRows[key]`／`_docorder[key]` 必須與表格列嚴格 1:1（`_diffUpdate` 每次 pop/append 兩者同步維護）；② `_applyRowVisibility`／歸檔 `_rematch` 的 `setUpdatesEnabled(False…True)` **必用 try/finally**（中途丟例外會把表格卡在不更新＝所有 `setRowHidden` 失效，持續到下次整表重建）。
- **參照表 rename 後瀏覽／歸檔頁不更新** → 指紋只看公文表 `last_modified`，碰不到參照改名；rename 必走 `_ref_changed` 旗標路徑（`_refreshRefCells`／重載小清單），不能靠指紋偵測。

#### 8. 歸檔檔名解析（`lib/archive_text.py`）
- **動斷詞／日期／主旨解析前** → 三條解析雷（斷詞漏字、PK 1xx 日期、無 `-` 主旨）詳述已搬至 **DEVELOPER.md §3「歸檔檔名解析的雷」**，動 `archive_text.py` 前先翻。

#### 9. 打包／重啟
- **重置後重啟、打包版跳 `Failed to load Python DLL`／`unicodedata` 缺** → 啟動新程序前設 `PYINSTALLER_RESET_ENVIRONMENT=1`（新程序沿用舊 `_MEI` 所致；見 `tab_settings._restartApp()`，別用 cmd ping 延遲歪招）。
- **C 槽空間不足時 onefile 解壓階段失敗（已知無法攔截）** → onefile 開機會先把整包解壓到 C 槽 `%TEMP%`（實測峰值約 216~250MB，視 exe 大小而定），這發生在 `main.py` 任何程式碼執行**之前**（PyInstaller bootloader 階段），我們自己的 `error.log` 機制與 2026-07 加的開機磁碟空間檢查（`lib/db_utils.diskSpaceThreshold` + `main.py` 開頭 `confirmBox`）都攔不到、也留不下紀錄。已與維護者議定不處理（不想為此動 `--runtime-tmpdir` 改打包設定），剩餘風險留給維護者自行注意 C 槽可用空間。執行期間（`main.py` 已開始跑之後）的磁碟空間不足，已用上述檢查＋`LoadWorker` try/except＋`friendlyErrorMessage` 的 `isDiskFullError` 專屬訊息攔住。
