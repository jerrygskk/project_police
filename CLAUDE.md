# 給接手者（Claude 請先讀這節）

這節讓你在新對話中快速進入協作狀態。

## 這是什麼

- **技術棧**：Python + PySide6（Qt）+ SQLite，純桌面單機程式
- **使用者**：警察單位承辦人員
- **目標環境**：Windows，顯示縮放 **125%**，全域字體 **14pt**
- **打包**：PyInstaller 打成單一 exe（`--onefile`）
- **資料**：軟刪除（清空欄位、保留 `doc_id`），不做真 DELETE

## 動手前先做這三件事

0. **開新對話先讀 [README.md](README.md)**（至少第 1～3 節）— 進入任何任務前的第一動作，不要略過
1. **讀 README 第 1 節**（架構心智模型）— 了解程式怎麼跑起來、資料怎麼流
2. **掃 README 第 2 節**（踩雷速查表）— 不看就會踩，而且有些踩過還會再踩
3. **對齊 README 第 3 節**（慣例與設計決策）— 為什麼這樣寫，不要自作主張改掉

## 協作偏好（務必遵守）

這是維護者最看重的部分。違反這些會直接消耗他的信任與時間。

## A. 跟他互動（溝通與節奏）

### 動手節奏

- **先思考再動手**：任何寫 code 的任務，先思考、發想多個方案、整理成計畫給他看，經他核可後才開始寫 code。不要做完才說「其實有更好做法」。重大改動先給示意圖 / 大綱 / 影響範圍清單，等他點頭再寫
- 複雜或破壞性的改動（牽動多檔、改結構、改資料），**先盤點影響範圍列清單**給他看
- 要 Claude **基於專業判斷給建議，且適時提供業界或主流修改方式**。反感「見風轉舵」他說 A 你立刻倒向 A、還拿他的話包裝成你的判斷，這會被點名。有不同意見就誠實講，講完理由讓他決定

### 找得到就別問

- README / code / dbfile 裡找得到答案的不要問
- 但**沒寫進文件的設計決策**（例如「歸檔 Tab 要做什麼」）一定要問，不要憑空假設

### 回覆風格（對他說話時）

- **直接切入重點**：不說客套話（「好的」「沒問題」「這是個好問題」）
- **免除前言後語**：直接輸出核心答案，不要開場白（「以下是為您整理的…」）與結尾總結（「希望以上對您有幫助」）
- **精簡文字**：列點、短句、精準詞彙，在不影響理解與準確度下用最少字數
- **主動提醒斷點**：對話累積過長時，回覆結尾加「[提示：對話已長，建議備份摘要並開啟新對話]」

## B. 產出（程式與檔案）

### 提供產出

- 直接修改本地端 code
- **code 不主動整段貼出來**，他要看才給
- **不用跟維護者告知改了什麼 function**，遇到同檔名檔案（如 `__init__.py`）須告知放在哪個資料夾，產出文字只需簡單說明不長篇大論
- **README 不主動改**，他要才改（「發布版本」流程除外）
- git add / commit / push 規則見下方 C 群「用語約定」

### 寫 code 的紀律

- **省 token**：先讀完相關檔案再動手，`str_replace` 範圍要精準
- ⚠️ **`str_replace` 容易吃掉相鄰的 `def`**：改完後務必 `grep` 確認上下相鄰的函式定義還在（這個錯在開發時犯過多次，每次都害他重新測試）。尤其是「在某方法前後插入新方法」「刪除某方法」時最容易發生
- 改完檔案**先 compile（`py_compile`）驗證語法**，並**主動自我迭代驗證**：能寫單元測試就寫單元測試、能模擬的邏輯（演算法、SQL round-trip）就模擬跑一輪，依結果自行修正再給他，不要把未驗證的 code 直接丟給他。容器**有 PySide6 可 import**（能跑非 GUI 的純邏輯單元測試），但**無法開 GUI 視窗 / 截圖**（等同無 puppeteer / 模擬器可截圖）——Tab 互動、Dialog、表格渲染這類主動告知他、請他上機測
- **單元測試在 `tests/`**（已入庫，純邏輯回歸測試）：跑法 `python -m unittest discover -s tests`，檔名 `test_*.py`（unittest 探索預設，勿改名）。**動到可單測的純邏輯**（檔名/文字解析、SQL round-trip、狀態/逾期計算、權限判斷）時，**一併新增或更新對應測試**再交付。詳見 README §4「單元測試」
- ⚠️ **動手前對照踩雷表**。寫過的雷再踩會被直接點名

### 文字風格（UI 用語）

- UI 上給使用者看的提示文字要**正式**，不要口語（例如不要寫「排序未儲存，要存嗎？」，要寫「儲存目前排序後繼續編輯？」）

## C. 版本 / Git / 發布 / 打包

### 版本號

- 版本號定義於 `lib/version.py`，進版時只進第三碼
- 進位與否他決定，不要自己跳版號
- **進版一律跑 `python bump_version.py <版號>`**（版號自帶、不自動進位；會先印出目前版號），它會同時改 `version.py` 與產出 `version_info.txt`（exe 檔案資訊）。**勿手改 `version.py`**，否則 `version_info.txt` 不同步

### 用語約定（他會用簡稱，要對上）

- **「進版」** = 跑 `python bump_version.py <版號>`（機制見上「版本號」節）+ 打 git tag `v{版本號}` + README §8 補一列版本記錄
- **「push上去」、「推上去」** = 把改動 commit + push。**逐檔 add**（當輪或上次 push 後改動的檔案逐一 add，**不要一次全加**，跳過 `dbfile.db`）；**叫你推才推**，沒說不要問「要推嗎？」
- ⚠️ **push 前必確認無真實人名／個資**：要 commit／push 的內容（含測試 fixture 檔名、文件範例、`dbfile.db`）不得含真實人名，有則先替換成虛構佔位名才能推。`dbfile.db` 只能是**乾淨空殼**（人員僅佔位、無公文），且提交前先 `VACUUM`（刪除的資料會殘留在 slack space，strings 掃得到）。
  - 自動防呆：`tests/test_no_pii.py` 會比對本機 `tests/pii_denylist.local.txt`（真名清單，已 gitignore 不入庫）掃描 git 追蹤內容＋已提交的 `dbfile.db` blob，命中即 fail。**push 前跑一次 `python -m unittest tests.test_no_pii`**；有新進真名就補進該清單。
- **release note** = 給 `.md` 檔（`release_note_v{版號}.md`，比照前版**不入庫**，留著貼 GitHub Release）。**不要直接打在對話裡**（會被渲染、無法複製原始碼）；內容寫給使用者看（功能 / 改進 / 修正），技術細節留 README
- **「發布版本」、「出一版」** = 見下方標準流程

### 發布版本標準流程（他講「發布版本」「出一版」時，照順序；各步用語見上「用語約定」）

1. **寫 README 內文**：這版新功能 / 行為改動補進對應章節（不只 §8 版本記錄列）
2. **寫 handover**（跨對話需交接才寫，否則略過）
3. **寫 release note**
4. **進版**（README §8 版本記錄列在這步補）
5. **推上去** + 打 tag `v{版號}` + push tag
6. **build**：onefile 全新 build（見 README §7），回報成功 / 失敗
7. **發 GitHub Release**（三個 asset，比照歷版 v1.0.6）：
   - **要上傳的檔案（共 3 個）**：
     1. `Police-Document-Manager.exe`（本次 build 的 onefile，在 `dist/`）
     2. `dbfile.db`（**乾淨空殼**——⚠️ 一律從 git HEAD 取，**不要用工作區那份**，工作區常被測試蓋掉。導出：`git show HEAD:dbfile.db > 暫存/dbfile.db`，二進位用 Bash 導出才安全；可 `git hash-object` 對 `git rev-parse HEAD:dbfile.db` 驗證一致）
     3. `PACKED.zip`（= 上面 exe + dbfile.db **兩檔扁平放根目錄**，無子資料夾）
   - **打包 zip（PowerShell）**：`Compress-Archive -Path 暫存\dbfile.db,暫存\Police-Document-Manager.exe -DestinationPath 暫存\PACKED.zip -Force`
   - **建 Release + 一次傳三檔**：
     ```
     gh release create v{版號} --title "v{版號}" --notes-file release_note_v{版號}.md \
       "dist/Police-Document-Manager.exe" "暫存/dbfile.db" "暫存/PACKED.zip"
     ```
     （asset 多於一個時直接列在 create 後；或先 create 再 `gh release upload v{版號} <檔> --clobber`）
   - 收尾刪暫存資料夾。
   - **gh 環境**：已裝（本機 `C:\Program Files\GitHub CLI\gh.exe`，新 shell PATH 沒帶到就用全路徑），帳號 `jerrygskk` 已登入（token 存 keyring）。`gh auth login` 是互動式、非互動 shell driver 不了——若日後登出需重登，由維護者本機自己跑

> ⚠️ **順序鐵則**：README / release note 要在「進版 commit」**之前**寫好，tag 才會直接指向含完整文件的 commit。別先進版打 tag、事後才補 README——那樣得退版重做。
> ⚠️ tag 已 push 後要移動：本地 `git tag -f` 後，遠端**先刪再推**（`git push origin :refs/tags/v{版號}` 再 `git push origin v{版號}`），否則遠端 tag 仍指舊 commit。

### 打包（PyInstaller）

- **只用 onefile**，不要問要哪種打包方式
- 習慣**每次砍掉 spec 全新 build**（不信任殘留 spec 會帶過期設定）。打包指令見 README 第 7 節，開頭已含清除步驟
- **build 一律用 PowerShell tool**（不用 Bash tool）：`del /q` / `rmdir /s /q` 是 CMD 語法，Bash tool（Git Bash）不識別會靜默失敗，spec 和 dist 不會被清掉
- Claude 可直接在本機執行 build，完成後只回報成功/失敗（失敗才貼錯誤末段）

---

## 踩雷速查表（動手前必掃）

| 症狀 | 原因 | 解法 |
|------|------|------|
| `.ui` 載入報 `Unable to open/read ui device` | `.ui` 用了 `contentsMargins` + `<rect>` 寫 margin | 改用 `leftMargin`/`topMargin`/`rightMargin`/`bottomMargin` 四個獨立 property |
| `widget.centralWidget()` 回傳 None | central widget 物件名稱不是全小寫 | 名稱必須是 `centralwidget`（全小寫） |
| 狀態色（紅/橘/綠）失效、停用列灰字不出現 | stylesheet 寫死 `QTableWidget::item { color }`，優先級蓋過 `setForeground()` | `::item` 只設 padding/border，文字色一律交給 `setForeground()`。`:selected` 的 color 可留。**這個雷開發時踩過不只一次，動表格樣式前先檢查** |
| 顏色被 stylesheet 蓋掉 | 用了 `Qt.red` 等列舉 | 用 `QColor("#hex")` |
| 新 Dialog/Widget 文字看不見（深色底） | 沒明確設背景色與文字色，繼承到全域深色 | 每個新 `QDialog`/`QWidget` 都要明確設背景 + 文字色（見 README 第 5 節範例） |
| 按鈕 `clicked` 連接的 callback 第一個參數變成 `False` | Qt 的 `clicked` signal 會自動多塞一個 `checked` 布林 | lambda 要吃掉它：`lambda _=False, k=key: ...`，否則像 `_REF_CFG[False]` 會 KeyError。**這個雷踩過多次** |
| `setEnabled(False)` 了按鈕但外觀沒變灰 | 套用的 stylesheet（如 `BTN_CONFIRM`）沒定義 `:disabled` 狀態 | 需要灰掉的按鈕用含 `QPushButton:disabled { ... }` 的自訂 stylesheet |
| `QTableWidget` / `QAbstractScrollArea` 滾輪事件攔不到 | 滾輪事件由 `viewport()` 接收，覆寫 `table.wheelEvent` 不會被觸發 | 在 `table.viewport()` 上 `installEventFilter` 攔 `QEvent.Wheel`；filter 要存成屬性防 GC |
| `ORDER BY sort_order` 時新項目跑到最前面 | 新列 `sort_order` 是 NULL，SQLite 把 NULL 排最前 | 新增時務必給 `sort_order` 值（本專案規則：新項目放最前 = `MIN(sort_order)-1`，空表 fallback 1） |
| 從設定 Tab 切走想攔截「未存」攔不住 | `currentChanged` 切換後才觸發 | 大 Tab 只能切過去後補跳提示；子頁切換（按鈕）才能攔住回原狀 |
| 重置後自動重啟，打包版跳 `Failed to load Python DLL` 或 `unicodedata` 缺失 | PyInstaller 6.x 新程序沿用舊 `_MEI` 環境，到已刪除目錄找 DLL | 啟動新程序前設 **`PYINSTALLER_RESET_ENVIRONMENT=1`**。別用 cmd ping 延遲歪招。見 `tab_settings.py` 的 `_restartApp()` |
| `setupPreviewTable` 的 200ms 延遲 autoResize 覆蓋欄寬 | 內建 `QTimer` 重算欄寬，把手動設的拉回 | 需自行控制欄寬的表格不要用 `setupPreviewTable`；彈性欄用 `QHeaderView.Stretch`，固定欄用 `Fixed` + `setColumnWidth` |
| 浮貼按鈕（絕對定位）在非當前分頁重複/錯位 | 非可見頁 widget layout 寬=0，不同頁浮貼鈕可能渲染到當前頁 | 改在 GroupBox 內 HBox 標題列放鈕，走正規 layout 管理 |
| confirmBox 確認/取消鈕被 Qt 重排左右 | `AcceptRole`/`RejectRole` 依 OS 慣例調換 | 兩顆鈕都用 **`ActionRole`**，`addButton` 順序即視覺順序；手動設 `setDefaultButton` + `setEscapeButton` |
| Material Icons SVG 白邊太多 | viewBox `0 -960 960 960` 圖案只佔中央 70% | 裁切 viewBox 到圖案實際 bounding box，width/height 統一 512px |
| SVG icon 在按鈕裡偏一邊 | path 含非對稱裝飾把視覺重心推偏；或 viewBox 留白不對稱 | 移除非對稱裝飾，viewBox 以主圖 bounding box 置中 |
| 斷詞比對漏字（日期黏主旨檔名如 `1150101匿名竊盜案`） | `_tokenize` 含數字的片段不符純中文判斷，中文全部漏切 | 改用 `re.findall([^一-鿿]+)` 抽中文段再 2 字滑動切詞 |
| 軟刪除公文仍出現在歸檔待歸檔清單 | 歸檔判定只看 `is_electronic` 空，空殼也符合 | `_queryUnarchived` / `_tableSignature` 排除底層案由欄為 NULL 者；**任何「待處理」查詢都要排除軟刪除空殼** |
| 編號欄同格出現超連結＋純文字重疊 | `item` 與 `cellWidget` 兩套獨立儲存，切換時只寫新未清舊 | `setDocIdLinkCell` 切換前互清：連結分支先 `takeItem`、純文字分支先 `removeCellWidget` |
| `QDateEdit` 月曆打開停在最小年（1752）而非今天 | 空白哨兵 = minimumDate，QDateEdit 開月曆時導到 1752 | 事件過濾器裝在 `dateedit.calendarWidget()`，空白狀態時用 `QTimer.singleShot(0,…) setCurrentPage(今年,今月)`；封裝為 `setupDateEditCalendarOnly` |
| 歸檔候選 PK 為 1xx 時日期解析空白 | `_parseDate` 舊正則把 PK「103」當民國年 | 日期 token 改 `(?<!\d)(1\d{2})(\d{2})(\d{2})(?!\d)` 完整 7 碼前後不接數字 |
| 歸檔預覽主旨退回 DB 主旨（檔名無 `-`） | `_parseSubject` 只用 `-` 分段，無 `-` 整串成單段被剝空 | 補「無 `-`」分支：去開頭日期＋從尾端剝人名，中間即主旨 |
| 多區塊合併進單一 QGridLayout 後，隱藏列出現幽靈間距、兩模式下方表格高度不一 | `verticalSpacing` 對隱藏（高 0）列仍保留間距；form 區高度隨模式列數變動，Expanding 表格吃剩餘空間 | `verticalSpacing=0`，列距全用 `setRowMinimumHeight` 控制；兩模式 form 總高設成**相同固定值**（如刑案 4×45、一般 3×60＝180），下方表格高度才一致（見 `tab_report._switchFormType`） |
| show/hide 切換欄位時整排左右跳動／同一欄位兩模式寬度不同 | QGridLayout 欄寬只按「當前可見」widget 計算；col0 最寬標籤或右欄寬度錨點若是某模式專屬，另一模式該欄縮水 | 用 `setColumnMinimumWidth` 鎖死結構性欄寬；col0 取最寬標籤 `sizeHint().width()`（自適應字體/縮放，勿寫死） |
| 切 tab 時共用列上的按鈕上下跳動 | 共用列（含按鈕）在兩模式 row min height 不同，按鈕垂直置中跟著變 | 共用列兩模式設**相同** row min height |
| `QDateEdit`/`QComboBox` 設灰字結果月曆／下拉清單文字也變灰 | 裸 `color:` stylesheet 會繼承到子元件（月曆 QCalendarWidget、下拉 QAbstractItemView） | 用型別選擇器 `QDateEdit { color: ... }` / `QComboBox { color: ... }`，只染欄位本體 |
