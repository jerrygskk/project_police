# 給接手者（Claude 請先讀這節）

這節讓你在新對話中快速進入協作狀態。

## 這是什麼

- **技術棧**：Python + PySide6（Qt）+ SQLite，純桌面單機程式
- **使用者**：警察單位承辦人員
- **目標環境**：Windows，顯示縮放 **125%**，全域字體 **14pt**
- **打包**：PyInstaller 打成單一 exe（`--onefile`）
- **資料**：軟刪除（清空欄位、保留 `doc_id`），不做真 DELETE

## 動手前先做這三件事

1. **讀 README 第 1 節**（架構心智模型）— 了解程式怎麼跑起來、資料怎麼流
2. **掃 README 第 2 節**（踩雷速查表）— 不看就會踩，而且有些踩過還會再踩
3. **對齊 README 第 3 節**（慣例與設計決策）— 為什麼這樣寫，不要自作主張改掉

## 協作偏好（務必遵守）

這是維護者最看重的部分。違反這些會直接消耗他的信任與時間。

### 動手節奏

- **先討論方案再動手**，不要做完才說「其實有更好做法」。重大改動先給示意圖 / 大綱 / 影響範圍清單，等他點頭再寫
- 複雜或破壞性的改動（牽動多檔、改結構、改資料），**先盤點影響範圍列清單**給他看
- 要 Claude **基於專業判斷給建議，且適時提供業界或主流修改方式**。反感「見風轉舵」他說 A 你立刻倒向 A、還拿他的話包裝成你的判斷，這會被點名。有不同意見就誠實講，講完理由讓他決定

### 提供產出

- 直接修改本地端 code
- **code 不主動整段貼出來**，他要看才給
- **不用跟維護者告知改了什麼 function**，遇到同檔名檔案（如 `__init__.py`）須告知放在哪個資料夾，產出文字只需簡單說明不長篇大論
- 維護者說要push後把當輪改動的檔案或上次push後改動的檔案逐一ADD到git，不要使用一次全加入指令
- **README 不主動改**，他要才改

### 寫 code 的紀律

- **省 token**：先讀完相關檔案再動手，`str_replace` 範圍要精準
- ⚠️ **`str_replace` 容易吃掉相鄰的 `def`**：改完後務必 `grep` 確認上下相鄰的函式定義還在（這個錯在開發時犯過多次，每次都害他重新測試）。尤其是「在某方法前後插入新方法」「刪除某方法」時最容易發生
- 改完檔案**先 compile（`py_compile`）驗證語法**，能模擬測試的邏輯（演算法、SQL round-trip）就模擬測一下再給。容器沒有 PySide6，GUI 行為無法實跑，這點要主動告知他、請他上機測
- ⚠️ **動手前對照踩雷表**。寫過的雷再踩會被直接點名

### 版本號

- 版本號定義於 `lib/version.py`，進版時只進第三碼
- 進位與否他決定，不要自己跳版號

### 用語約定（他會用簡稱，要對上）

- **「進版」** = 改版本號（改 `lib/version.py` 的 `__version__`）+ 打 git tag（`v{版本號}`）+ 在 README 第 9 節補一列版本記錄
- **「push上去」、「推上去」** = 把當前所有變動 commit + push
- **release note** = **一律給 `.md` 檔案**（present_files），讓他直接複製貼上 GitHub Release。**不要把 release note 直接打在對話裡**（會被聊天介面渲染成排版效果，無法複製原始碼），務必給檔案。內容寫給使用者看（功能 / 改進 / 修正），技術細節留 README 或 Claude 踩雷表

### 打包（PyInstaller）

- **只用 onefile**，不要問要哪種打包方式
- 習慣**每次砍掉 spec 全新 build**（不信任殘留 spec 會帶過期設定）。打包指令見 README 第 7 節，開頭已含清除步驟
- **build 一律用 PowerShell tool**（不用 Bash tool）：`del /q` / `rmdir /s /q` 是 CMD 語法，Bash tool（Git Bash）不識別會靜默失敗，spec 和 dist 不會被清掉
- Claude 可直接在本機執行 build，完成後只回報成功/失敗（失敗才貼錯誤末段）

### 找得到就別問

- README / code / dbfile 裡找得到答案的不要問
- 但**沒寫進文件的設計決策**（例如「歸檔 Tab 要做什麼」）一定要問，不要憑空假設

### 文字風格

- UI 上給使用者看的提示文字要**正式**，不要口語（例如不要寫「排序未儲存，要存嗎？」，要寫「儲存目前排序後繼續編輯？」）

### 回覆風格（對他說話時）

- **直接切入重點**：不說客套話（「好的」「沒問題」「這是個好問題」）
- **免除前言後語**：直接輸出核心答案，不要開場白（「以下是為您整理的…」）與結尾總結（「希望以上對您有幫助」）
- **精簡文字**：列點、短句、精準詞彙，在不影響理解與準確度下用最少字數
- **主動提醒斷點**：對話累積過長時，回覆結尾加「[提示：對話已長，建議備份摘要並開啟新對話]」

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
