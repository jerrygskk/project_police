# 公文管理系統

Windows 桌面應用，PySide6 + SQLite，管理警察單位公文（交辦單、刑案陳報、一般陳報）。

---

## 0. 給接手者（請先讀這節）

你（Claude）是這份文件的主要讀者。這節讓你在新對話中快速進入協作狀態。

### 這是什麼

- **技術棧**：Python + PySide6（Qt）+ SQLite，純桌面單機程式
- **使用者**：警察單位承辦人員
- **目標環境**：Windows，顯示縮放 **125%**，全域字體 **14pt**
- **打包**：PyInstaller 打成單一 exe（`--onefile`）
- **資料**：軟刪除（清空欄位、保留 `doc_id`），不做真 DELETE

### 動手前先做這三件事

1. **讀第 1 節**（架構心智模型）— 了解程式怎麼跑起來、資料怎麼流
2. **掃第 2 節**（踩雷速查表）— 不看就會踩，而且有些踩過還會再踩
3. **對齊第 3 節**（慣例與設計決策）— 為什麼這樣寫，不要自作主張改掉

### 協作偏好（務必遵守）

這是維護者最看重的部分。違反這些會直接消耗他的信任與時間。

**動手節奏**
- **先討論方案再動手**，不要做完才說「其實有更好做法」。重大改動先給示意圖 / 大綱 / 影響範圍清單，等他點頭再寫
- 複雜或破壞性的改動（牽動多檔、改結構、改資料），**先盤點影響範圍列清單**給他看
- 要 Claude **基於專業判斷給建議，且適時提供業界或主流修改方式**。反感「見風轉舵」他說 A 你立刻倒向 A、還拿他的話包裝成你的判斷，這會被點名。有不同意見就誠實講，講完理由讓他決定

**提供產出**
- **需要檔案直接給**，不用問「要不要給你檔案」
- 改完檔案要**給可下載的檔案**（present_files），不要只貼 code
- **code 不主動整段貼出來**，他要看才給；要給時**只給被修改的前後片段**，不完整重寫整支檔案或未變動的函數
- **不用跟維護者告知改了什麼function**，遇到同檔名檔案(如__init__.py)須告知放在哪個資料夾，產出文字只需簡單說明不長篇大論。
- **git 指令不主動給**，他要才給。要給時用 **Windows CMD 格式**（多行 commit 用多個 `-m`，不要多行字串）
- **README 不主動改**，他要才改

**寫 code 的紀律**
- **省 token**：先讀完相關檔案再動手，`str_replace` 範圍要精準
- ⚠️ **`str_replace` 容易吃掉相鄰的 `def`**：改完後務必 `grep` 確認上下相鄰的函式定義還在（這個錯在開發時犯過多次，每次都害他重新測試）。尤其是「在某方法前後插入新方法」「刪除某方法」時最容易發生
- 改完檔案**先 compile（`py_compile`）驗證語法**，能模擬測試的邏輯（演算法、SQL round-trip）就模擬測一下再給。容器沒有 PySide6，GUI 行為無法實跑，這點要主動告知他、請他上機測
- ⚠️ **動手前對照第 2 節踩雷表**。README 寫過的雷再踩會被直接點名

**版本號**
- 版本號定義於 `lib/version.py`（目前 `v1.0.0`），進版時只進第三碼
- 進位與否他決定，不要自己跳版號

**用語約定（他會用簡稱，要對上）**
- **「進版」** = 改版本號（改 `lib/version.py` 的 `__version__`）+ 打 git tag（`v{版本號}`）+ 在 README 第 9 節補一列版本記錄
- **「給我 git」** = 把當前所有變動 commit + push（Windows CMD 格式，多 `-m`）
- **release note** = **一律給 `.md` 檔案**（present_files），讓他直接複製貼上 GitHub Release。**不要把 release note 直接打在對話裡**（會被聊天介面渲染成排版效果，無法複製原始碼），務必給檔案。內容寫給使用者看（功能 / 改進 / 修正），技術細節留 README 踩雷表

**打包（PyInstaller）**
- **只用 onefile**，不要問要哪種打包方式
- 習慣**每次砍掉 spec 全新 build**（不信任殘留 spec 會帶過期設定）。打包指令見第 7 節，開頭已含 `del spec & rmdir build dist`
- 容器無法跑 PyInstaller，打包相關只能給指令 / 改 code，請他上機 build 測

**找得到就別問**
- zip / README / code / dbfile 裡找得到答案的不要問
- 但**沒寫進文件的設計決策**（例如「歸檔 Tab 要做什麼」）一定要問，不要憑空假設

**文字風格**
- UI 上給使用者看的提示文字要**正式**，不要口語（例如不要寫「排序未儲存，要存嗎？」，要寫「儲存目前排序後繼續編輯？」）

**回覆風格（對他說話時）**
- **直接切入重點**：不說客套話（「好的」「沒問題」「這是個好問題」）
- **免除前言後語**：直接輸出核心答案，不要開場白（「以下是為您整理的…」）與結尾總結（「希望以上對您有幫助」）
- **精簡文字**：列點、短句、精準詞彙，在不影響理解與準確度下用最少字數
- **主動提醒斷點**：對話累積過長時，回覆結尾加「[提示：對話已長，建議備份摘要並開啟新對話]」

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

## 2. 踩雷速查表（動手前必掃）

| 症狀 | 原因 | 解法 |
|------|------|------|
| `.ui` 載入報 `Unable to open/read ui device` | `.ui` 用了 `contentsMargins` + `<rect>` 寫 margin | 改用 `leftMargin`/`topMargin`/`rightMargin`/`bottomMargin` 四個獨立 property |
| `widget.centralWidget()` 回傳 None | central widget 物件名稱不是全小寫 | 名稱必須是 `centralwidget`（全小寫） |
| 狀態色（紅/橘/綠）失效、停用列灰字不出現 | stylesheet 寫死 `QTableWidget::item { color }`，優先級蓋過 `setForeground()` | `::item` 只設 padding/border，文字色一律交給 `setForeground()`。`:selected` 的 color 可留。**這個雷開發時踩過不只一次，動表格樣式前先檢查** |
| 顏色被 stylesheet 蓋掉 | 用了 `Qt.red` 等列舉 | 用 `QColor("#hex")` |
| 新 Dialog/Widget 文字看不見（深色底） | 沒明確設背景色與文字色，繼承到全域深色 | 每個新 `QDialog`/`QWidget` 都要明確設背景 + 文字色（見第 5 節範例） |
| 按鈕 `clicked` 連接的 callback 第一個參數變成 `False` | Qt 的 `clicked` signal 會自動多塞一個 `checked` 布林 | lambda 要吃掉它：`lambda _=False, k=key: ...`，否則像 `_REF_CFG[False]` 會 KeyError。**這個雷踩過多次** |
| `setEnabled(False)` 了按鈕但外觀沒變灰 | 套用的 stylesheet（如 `BTN_CONFIRM`）沒定義 `:disabled` 狀態 | 需要灰掉的按鈕用含 `QPushButton:disabled { ... }` 的自訂 stylesheet |
| `QTableWidget` / `QAbstractScrollArea` 滾輪事件攔不到 | 滾輪事件由 `viewport()` 接收，覆寫 `table.wheelEvent` 不會被觸發 | 在 `table.viewport()` 上 `installEventFilter` 攔 `QEvent.Wheel`；filter 要存成屬性防 GC |
| `ORDER BY sort_order` 時新項目跑到最前面 | 新列 `sort_order` 是 NULL，SQLite 把 NULL 排最前 | 新增時務必給 `sort_order` 值（本專案規則：新項目放最前 = `MIN(sort_order)-1`，空表 fallback 1） |
| 從設定 Tab 切走想攔截「未存」攔不住 | `currentChanged` 切換後才觸發（見第 1 節 Qt 限制） | 大 Tab 只能切過去後補跳提示；子頁切換（按鈕）才能攔住回原狀 |
| 重置後自動重啟，打包(onefile)版跳 `Failed to load Python DLL ..._MEIxxxxx\python3xx.dll` 或 `ModuleNotFoundError: unicodedata` | PyInstaller 6.x bootloader 把經 `sys.executable` 啟動的新程序當成同一 app 的 worker 子程序，沿用繼承的 `_MEI` 環境（指向舊程序正在清掉的 `_MEIxxxxx`），新程序到已刪除的舊目錄找 DLL/標準庫 | 啟動新程序前設環境變數 **`PYINSTALLER_RESET_ENVIRONMENT=1`**（PyInstaller 6.10+ 官方機制），令新程序解壓全新 `_MEI`。見 `tab_settings.py` 的 `_restartApp()`。**別用 cmd ping 延遲那種歪招**（延遲無效，根因是環境變數沒重設）。開發(非 frozen)無此問題，沿用 `QProcess` 帶 argv 即可 |
| `setupPreviewTable` 的 200ms 延遲 autoResize 覆蓋欄寬 | `setupPreviewTable` 內建 200ms `QTimer` 重算欄寬，導致手動設完欄寬後又被拉回 | 需自行控制欄寬的表格**不要用 `setupPreviewTable`**，自行初始化 + 彈性欄用 `QHeaderView.Stretch`（Qt 自動吃剩餘空間、elide 切字），固定欄用 `Fixed` + `setColumnWidth`。歸檔待歸檔表即此做法 |
| 浮貼按鈕(絕對定位)在非當前分頁出現重複/錯位 | QTabWidget 中非可見頁面的 widget layout 未撐開（寬=0），且不同頁的浮貼鈕可能被 Qt 渲染到當前頁 | 不用絕對定位浮貼，**改在 GroupBox 內部 layout 的 HBox 標題列放鈕**（label + spacer + toggle 鈕），走正規 layout 管理、不依賴 resizeEvent 定位 |
| confirmBox 確認/取消鈕被 Qt 平台慣例重排左右 | `QMessageBox` 的 `AcceptRole`/`RejectRole` 會被 Qt 依作業系統慣例調換位置 | 兩顆鈕都用 **`ActionRole`**（同 role 不會被重排），按 `addButton` 順序就是視覺左右順序。手動設 `setDefaultButton`(Enter) + `setEscapeButton`(Esc) 保留快捷鍵 |
| Material Icons SVG 在小鈕上白邊太多 | viewBox `0 -960 960 960` 是 960px 座標系，圖案只佔中央約 70% | 裁切 viewBox 到圖案實際 bounding box（如 pdf `100 -870 760 760`、archive `80 -890 800 800`），width/height 統一 512px |
| SVG icon 在按鈕裡看起來偏一邊（如 pdf 偏右上） | path 含非對稱裝飾（如後景文件陰影 `M140-80`），把主圖視覺重心推往一側；或 viewBox 留白不對稱 | 移除非對稱裝飾，viewBox 以主圖 bounding box 置中（pdf 移除後景後改 `150 -890 760 760`）。並排多個 icon 時務必比對視覺重心一致 |
| 斷詞比對漏字：檔名「日期黏主旨」（如 `1150101匿名竊盜案`）比不到 | `_tokenize` 舊版用 `re.fullmatch([\\u4e00-\\u9fff]+)` 判斷整個片段是否純中文才做滑動切詞，但日期與中文黏連的片段含數字→不符→中文完全沒切出來 | 改成對每個片段用 `re.findall([\\u4e00-\\u9fff]+)` 抽出**所有中文連續段**再做 2 字滑動切詞，不要求整段純中文 |
| 公文「軟刪除」後仍出現在歸檔待歸檔清單（空白列） | 刪除是清空式 UPDATE（案由/主旨設 NULL + `is_electronic=''`），歸檔頁待歸檔判定只看 `is_electronic` 空 → 空殼符合條件被撈出 | `_queryUnarchived` 與 `_tableSignature` 都要加排除：底層案由欄（crim `subject_summary` / gen `subject`）為 NULL 或空即視為已刪除空殼，不列入。**任何「未歸檔/待處理」查詢都要記得排除軟刪除空殼** |
| 編號欄同格同時出現「超連結數字」與「純文字數字」（admin↔user 來回切後疊現） | `QTableWidget` 同一格的 `item`（`setItem`）與 `cellWidget`（`setCellWidget`）是兩套獨立儲存、可並存；`setDocIdLinkCell` 切換 clickable 時只寫新表示、沒清舊表示，QLabel 連結背景透明致後方 item 文字透出 | `setDocIdLinkCell` 切換前互清：進連結分支先 `takeItem`、進純文字分支先 `removeCellWidget`。修在 helper，dbbrowse 三表初建與 `_onRolePerm` 一併受惠。**同格切換 item↔cellWidget 一律先清舊表示** |

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
| v1.0.0 | **正式版：歸檔電子檔快速檢視 ＋ 歸檔資料夾設定（脫離 beta）**。**瀏覽頁（Tab4）**：刑案／一般列的主旨欄前，凡有真實歸檔檔名者顯示電子檔圖示鈕，點圖即以系統預設軟體開啟該筆 PDF（唯讀檢視，一般使用者亦可，行為比照歸檔頁；用 item→cellWidget 改寫主旨欄，不踩同格切換雷）。**檔名定位**：DB 僅存 `is_electronic` 檔名，開檔時由設定的「歸檔根（年度層 UNC）」＋對應刑案／一般子夾遞迴建索引、`is_electronic` 整串 NFC 比對命中（記憶體快取、miss 重建一次）；只走對應類別子夾，避開刑案／一般獨立發號（PK 各自從 1）造成的跨類同名。**與磁碟機代號脫鉤**：net use 代號浮動、UNC 固定，故一律存 UNC（`db_utils.toUncPath` 以 `QStorageInfo` 由代號還原 UNC，轉不出則手動輸入）。**設定頁（Tab6）**：左側 nav 新增「歸檔資料夾」鈕＋`ArchiveRootDialog`（選年度層→自動轉 UNC＋可手動覆寫→列出子夾、猜刑案／一般並確認），存 `App_Settings` 三 key（`archive_root`/`archive_subdir_crim`/`archive_subdir_gen`，schema 不變、年度重置不清）；年度重置完成後提示更新歸檔根。**歸檔頁（Tab5）**：選 PDF 資料夾預設起點＝歸檔根；進頁自動帶入並顯示資料夾名稱（`_loadFolder`/`_autoloadDefault`，已選過不覆蓋、手動選優先）。**新增**：`db_utils.getSetting/setSetting/archiveSubdir/archiveDefaultDir/resolveArchivedPdf/clearPdfIndexCache/toUncPath`。靜態驗證（py_compile＋定位邏輯模擬＋三表 `_query` 對真 DB）PASS，GUI／onefile 待上機 |
| v0.9.0-beta.12 | **交辦單編輯權限細化 ＋ 內部重構**。**權限**（完整矩陣見 §3）：admin 解除「已發文編號鎖定」（可開 popup 全可改，一般使用者仍只能改承辦人且已發文鎖住）；`tab_dispatch._onRolePerm` 改為即時重刷編號連結（身分變更不必重查）；確立收文 Tab1／陳報 Tab2 編輯 popup 對一般使用者全開（誤輸更正屬正常作業）。**內部重構（無行為變更，見 §3/§4/§5）**：`lib/archive_text.py` 抽出比對純函式（§7 補 `--hidden-import`）、`AuthManager.is_admin()`、`db_utils.getConn` 統一連線、hover 元件移入 `ui_utils`、`table.refreshDeleteBtns` 共用、`_BaseEditDialog` 基底。靜態驗證（py_compile＋import 名稱解析＋邏輯等價）PASS，GUI／onefile 打包待上機 |
| v0.9.0-beta.11 | **分頁權限控管 ＋ 兩處顯示修正**。權限：交辦單發文（Tab0）一般使用者僅可改承辦人（TaskEditDialog `restricted` 模式，其餘欄位鎖定並顯示 DB 原值，儲存只動承辦人）、刪除 X 鈕停用變灰；資料庫瀏覽（Tab4）一般使用者無修改權限（編號不可點、刪除 X 灰）；檔案歸檔（Tab5）一般使用者顯示登入提示頁（Layout6.ui 包 `outer_stack`）；三頁皆監聽 `role_changed` 即時生效；收文/陳報/列印維持全開。修正：TaskEditDialog `restricted` 鎖定欄位補 `:disabled` 灰樣式（先前只 setEnabled 未 greyout）；歸檔頁 PDF/歸檔操作 icon 視覺重心對齊（icon_pdf/icon_archive viewBox 緊貼 bbox 對稱置中，先前 PDF 偏高一格）。`theme.py` 補 `#deleteBtn:disabled` 灰樣式。關閉 DEBUG_MODE 恢復正式行為（已發文編號鎖定、送出後清表）；修 tab_dbbrowse 點編號超連結 AttributeError（`_rowOf` def 修復）。**後續修補**：修 dbbrowse 編號欄連結與純文字並存重複（`setDocIdLinkCell` 切換前互清 item/cellWidget，user↔admin 來回切不再殘留）；刑案/一般陳報編輯 popup 新增「歸檔狀態」區塊（僅 admin，`CriminalEditDialog`/`GeneralEditDialog`，dbbrowse 與 archive 共用）：紙本 `is_reported` checkbox 雙向、電子檔 `is_electronic` 顯示檔名＋清除鈕（僅退回未歸、不動實體 PDF，長檔名 `ElideMiddle` 省略），儲存才寫回、取消還原 |
| v0.9.0-beta.10 | **歸檔「只歸紙本」＋ 逾期未回篩選 ＋ 比對演算法修正**。歸檔頁：新增「只歸紙本」鈕（is_reported=1，不需 PDF、續留清單等補 PDF，案由前顯示靛藍紙圖示 icon_paper.svg）；自訂關鍵字修復（_rematch 未選公文不再 return，可純關鍵字比對）；`_tokenize` 修正日期黏主旨檔名（如 `1150101匿名竊盜案`）中文無法切詞問題（真實資料 310/1317 筆受影響）；已歸檔遭刪除的空殼不再殘留待歸檔（_queryUnarchived/_tableSignature 排除底層案由/主旨為 NULL 者）；icon_pdf.svg 移除後景陰影+viewBox 置中修偏移；只歸紙本/檔案歸檔鈕套墨藍。資料庫瀏覽：交辦單頁「逾期未回」篩選（限辦日<今天且未發文，setRowHidden 不重建、與精簡完整/搜尋交集，逾期旗標存 vertical header UserRole）。刑案 popup 案件分類改可搜尋下拉（setupFilterCombo）。三大送出鈕統一墨藍（#a1b4cb/#4977b1/#39649a），發文鈕更名「確認發文」 |
| v0.9.0-beta.9 | **資料庫瀏覽（Tab4）＋ 檔案歸檔（Tab5）完成**。歸檔頁：精簡/完整模式（Stretch 欄寬 + setColumnHidden + toggle 膠囊鈕）、候選過濾（顯示已歸檔 toggle）、演算法優化 14x（斷詞快取）、預覽案由填 PDF 檔名主旨、候選欄位改操作\|符合\|檔名、Material Icons SVG 操作鈕（icon_pdf/icon_archive，裁切 viewBox 降白邊）、歸檔提示字改「歸檔刑案編號xxx：」、Enter 預設歸檔、編號超連結開編輯視窗 + dirty flag 差異更新（_diffDocs/_tableSignature/_lastLoad/_docorder）。全系統 popup 統一左確認右取消（confirmBox 改 ActionRole）。code review：清 9 個未用 import、_dbNow 上移 BaseTab、移除冗餘 _rowDoc、集中 inline import。init_ref_tables.sql 內嵌進 data_sync_tool.py、新增 backfill_archive_names.py |
| v0.9.0-beta.8 | 設定 Tab 改用 Layout7.ui 建靜態骨架（密碼頁 + 左側 nav + 三子頁，比照其他 Layout）；新增跨年度重置（清主表 + 兩段式重編參照表 ID + 刪停用項目 + 歸零流水號，確認彈窗 + 自動備份 + 可另存 + 重置後自動重啟）；重啟改用 `PYINSTALLER_RESET_ENVIRONMENT` 官方機制（解 onefile `_MEI` 重啟 DLL 載入失敗）；版本號集中至 `lib/version.py` 單一來源，主選單動態顯示 |
| v0.9.0-beta.7 | is_active 軟刪除擴及部門/案類、sort_order 排序功能（設定 Tab 四向排序鈕 + 暫存模式）、列印改 QPrintPreviewDialog（解 WinError 1155）、檔案結構重組（layouts/ + res/ + lib/）、排序鈕 SVG 圖示、黏底捲動修正、變更密碼防誤按 |
| v0.9.0-beta.6 | 設定 Tab（人員/部門/案類維護 + 變更密碼）、AuthManager、參照表連動、黏底捲動、狀態色 |
