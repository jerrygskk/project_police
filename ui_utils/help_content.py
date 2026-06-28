# ui_utils/help_content.py
# 程式內 HELP 內容單一來源。
#
# 設計：每頁以「結構化區塊」(HELP_PAGES) 描述，再由 _render_html() 產生 Dialog
# 用的 HTML、由 render_review_text() 產生 docs/help_text_review.txt 校稿檔。
# 改文字只動 HELP_PAGES，兩種輸出自動同步。
#
# 視覺走 Apple HIG 留白編排：段落標題用藍色短豎條（▍）＋細分隔線，只有警示用
# 色塊。內文用深黑 #1c1c1e（一般字重，維持紮實清楚），引言／次級說明用較淺灰。
# QTextBrowser（Qt rich-text）不支援圓角／陰影／flex／懸掛縮排，分隔線以 1px
# 表格列、條列縮排以 &nbsp; 達成。
#
# 頁索引對應 main.DocumentManager.TAB_CLASSES：
#   0 交辦單發文 / 1 交辦單收文 / 2 公文陳報 / 3 簽收單列印
#   4 資料庫瀏覽 / 5 檔案歸檔   / 6 資料庫設定

import re

from .button_imgs import BTN_IMG   # 自動產生：label → (qrc 路徑, 寬, 高)

HELP_TITLES = {
    0: "交辦單發文", 1: "交辦單收文", 2: "公文陳報", 3: "簽收單列印",
    4: "資料庫瀏覽", 5: "檔案歸檔", 6: "資料庫設定", 7: "操作紀錄",
}


# ── inline 重點（藍字），於資料字串中直接呼叫 ──────────────────
def _note(t):
    return f'<span style="color:#185FA5;">{t}</span>'


# ── 行內按鈕／按鍵／圖示示意（純展示、不可點）───────────────────
# 比照實際介面三種按鈕配色（見 lib/theme.py）：多數鈕白底深字、確認／歸檔類
# 墨藍 #a1b4cb 白字、刪除 ✕ 紅 #e74c3c 白字。QTextBrowser 行內樣式不吃 padding／
# border，水平內距靠 &nbsp; 撐、白底鈕用淺灰塊代理（純白在白底彈窗看不見）；
# 垂直內距無解（由行高決定）。樣式集中此處，要調鬆緊改這裡即可。
def _btn(t):
    # 按鈕示意：嵌 res/buttons/ 預烤圓角 SVG（配色已烤進圖，見 gen_buttons.py）。
    # <img> 用邏輯 w×h 顯示；SVG 檔 intrinsic 為 2×，QTextBrowser 點陣化後下採樣較清。
    # 四個別名保留語意、呼叫端不變；實際都查 BTN_IMG 回同型 <img>。
    src, w, h = BTN_IMG[t]
    return f'<img src="{src}" width="{w}" height="{h}">'

_btn_primary = _btn      # 確認／送出／歸檔類（圖已上墨藍）
_btn_danger = _btn       # 刪除 ✕（圖已上紅）
_btn_overdue = _btn      # 逾期未回 active（圖已上紅膠囊）
_tab = _btn              # 子頁籤（透明底＋底線，圖已上色），同走 BTN_IMG 查表

def _key(t):
    # 鍵盤按鍵：淺底深字
    return ('<span style="background-color:#E3E8EE; color:#1c1c1e; '
            f'font-weight:600;">&nbsp;{t}&nbsp;</span>')

def _icon(src, size=18):
    # 內嵌實際介面 qrc 圖示（與按鈕面同一張 SVG）
    return f'<img src="{src}" width="{size}" height="{size}">'


# 交辦單收文／公文陳報共用的「X 刪除」警示（單一來源，兩頁一致）
_DEL_WARN = ("這裡的 X 會真的刪除資料，且該文號直接作廢、不會再被使用，"
             "確認框會明白提示。確定登錯才刪。")


# ── 區塊資料模型 ───────────────────────────────────────────────
# 每頁 = block 串列。block：
#   ("lead",  text)              標題下引言（深灰）
#   ("muted", text)              次級灰說明（如「本頁僅管理者可用…」）
#   ("label", text)              獨立小標籤（其後常接 warn）
#   ("hint",  text)              小字補充（淺灰）
#   ("warn",  text)              橘色警示塊
#   ("sec",   label, content)    小標籤 + 灰卡片；content 為下列項目串列：
#       ("p",   html)            段落
#       ("ol",  [items])         有序（藍色 1. 2. …）
#       ("ul",  [items])         無序（藍色 ·）
#       ("map", [(k, v), …])     兩欄對照（左粗體）
HELP_PAGES = {
    0: [
        ("lead", "輸入所有交辦單編號後統一發文，並在資料庫加上發文日期與發文人員。"),
        ("sec", "操作流程", [
            ("ol", [
                "先選好<b>發文日期</b>（預設今天）與<b>發文人員</b>。",
                "點擊<b>文號輸入框</b>，輸入文號後按 " + _key("Enter") + "，該筆會加入下方清單，再繼續輸入下一筆 " + _key("Enter") + "。",
                "按 " + _btn_primary("確認發文") + "，確認框顯示日期、人員、筆數，確認後一次寫入。",
            ]),
        ]),
        ("sec", "注意事項", [
            ("ul", [
                "輸入錯誤想取消，按該列最左的 " + _btn_danger("✕") + " 移除。這只是把它從發文清單拿掉，<b>不會刪到資料</b>，放心按。",
                "發文日期欄有日期（橘字）代表這張先前發過，這次會<b>覆蓋</b>舊日期，確認框會告知幾筆被覆蓋。",
            ]),
        ]),
        ("warn", "若當初派錯承辦人，點擊「交辦單編號」開修改視窗更正；一般使用者僅能修改承辦人。"),
    ],

    1: [
        ("lead", "輸入一張新的交辦單並自動取得文號，出現在下方清單。"),
        ("sec", "操作流程", [
            ("ol", [
                "填寫<b>交辦事由、業務組、承辦人</b>等欄位，設定收文日期（預設今天）與限辦日期（免覆則勾「免覆」）。",
                "按 " + _btn_primary("確認收文") + "，出現在下方清單並由系統配發文號，接著輸入下一張。",
            ]),
        ]),
        ("sec", "主旨（交辦事由）要寫清楚", [
            ("p", "主旨會被搜尋到，請寫具體一點，日後在「資料庫瀏覽」比較好查。"
                  + _note("牽涉人名時建議寫進主旨，尤其那個人不是承辦人時，之後用人名也可搜尋到。")),
        ]),
        ("sec", "送出後還能補救", [
            ("ul", [
                "填錯想改，點該列<b>「交辦單編號」</b>（藍色可點）開修改視窗。",
                "整張錯登想刪掉，按該列最左 " + _btn_danger("✕") + "。",
            ]),
        ]),
        ("warn", _DEL_WARN),
    ],

    2: [
        ("lead", "登錄刑案陳報或一般案件陳報。上方頁籤切換 " + _tab("❐ 刑案陳報") + " "
                 + _tab("❏ 一般陳報")
                 + " 兩種表單，填完按 " + _btn_primary("確認陳報") + " 後自動取得文號，出現在下方清單。"),
        ("sec", "共通：主旨要寫清楚", [
            ("p", "陳報主旨寫具體些，牽涉人名建議寫入，日後在「資料庫瀏覽」比較好查。"),
        ]),
        ("sec", "哪些案類用刑案陳報", [
            ("p", "下列案類雖非刑法，但為配合系統分類，請使用刑案陳報："),
            ("p", _note("特殊分類") + "："),
            ("ul", [
                "通緝", "失聯移工", "汽機車／車牌相關（遺失、侵占、失竊、尋獲）",
                "社會秩序維護法",
            ]),
            ("p", _note("其他法規") + "："),
            ("cols", 3, [
                "毒品危害防制條例", "家庭暴力防治法", "個人資料保護法",
                "洗錢防制法", "跟蹤騷擾防治法", "性騷擾防治法",
                "菸害防制法", "醫療法", "人口販運防治法",
                "農田水利法", "廢棄物清理法",
            ]),
        ]),
        ("sec", "刑案陳報重點", [
            ("ul", [
                "為了減輕歸檔人員負擔，若有<b>報案人</b>強烈建議填寫。",
                "「查獲／受理日期」依案件狀態填入日期：",
            ]),
            ("ul", [
                "<b>現行犯</b>：陳報單日期",
                "<b>到案</b>：陳報單日期",
                "<b>未到案</b>：報案日期",
            ]),
            ("p", "發文分類、案類、承辦人、主旨、上面這個日期為<b>必填</b>。"),
        ]),
        ("sec", "一般陳報重點", [
            ("p", "選分類（業務／其他／相驗）、業務單位、承辦人、主旨即可，較單純。"),
        ]),
        ("sec", "送出後還能補救", [
            ("ul", [
                "填錯想改，點該列「編號」（藍色可點）開修改視窗。",
                "整筆錯登想刪，按該列最左 " + _btn_danger("✕") + "。",
            ]),
        ]),
        ("warn", _DEL_WARN),
    ],

    3: [
        ("lead", "依<b>發文日期</b>把當天所有發文（交辦／刑案／一般）整理成簽收表，供列印或存檔。"),
        ("sec", "操作流程", [
            ("ol", [
                "選<b>發文日期</b>（預設今天）。",
                "按 " + _btn("產生預覽") + "，下方顯示簽收表預覽（共幾頁會標示）。",
                "接著選一種："
                '<table width="100%" cellspacing="0" cellpadding="2">'
                '<tr><td width="20" valign="top" style="font-size:13pt; color:#1c1c1e;">·</td>'
                '<td valign="top" style="font-size:13pt; color:#1c1c1e; line-height:150%;">'
                + _btn("下載 PDF") + "：存成 PDF 檔留底或他用。</td></tr>"
                '<tr><td width="20" valign="top" style="font-size:13pt; color:#1c1c1e;">·</td>'
                '<td valign="top" style="font-size:13pt; color:#1c1c1e; line-height:150%;">'
                + _btn("列印表單") + "：跳出列印預覽視窗（預設彩色＋長邊雙面，可改），確認後送印。</td></tr></table>",
            ]),
        ]),
        ("hint", "該日期查無發文資料時會提示，不會產生空表。"),
    ],

    4: [
        ("lead", "查詢資料的地方。上方分 " + _tab("▤ 交辦單") + " "
                 + _tab("❐ 刑案陳報") + " " + _tab("❏ 一般陳報")
                 + " 三個子頁，各自整表瀏覽與搜尋。"),
        ("sec", "交辦單頁的「逾期未回」篩選", [
            ("p", "交辦單子頁左下角的 " + _btn_overdue("逾期未回") + " 鈕一按，只留下<b>已過限辦日期、卻還沒發文</b>的交辦單；"
                  "再按一次恢復全部。（交辦單頁專屬）"),
        ]),
        ("sec", "直接開啟已歸檔的 PDF", [
            ("p", "刑案／一般頁的主旨欄左側若有 " + _icon(":/icon_pdf.svg") + " 圖示鈕，代表該筆已歸電子檔，"
                  "<b>點圖示即可直接開啟檢視</b>，不必去資料夾翻找。"),
        ]),
        ("sec", "關鍵字搜尋", [
            ("ul", [
                "搜尋框輸入關鍵字，比對該頁所有資料欄位，<b>邊打邊自動比對</b>。",
                "想只比對某一欄，用旁邊的<b>範圍下拉</b>指定欄位。",
            ]),
        ]),
        ("sec", "精簡／完整切換", [
            ("p", "預設<b>精簡模式</b>只顯示重要欄位；按 " + _btn("完整") + " 顯示全部。"
                  "搜尋命中的欄位若在精簡模式被隱藏，下方會提示需切換到完整模式查看。"),
        ]),
    ],

    5: [
        ("muted", "本頁供管理者與歸檔管理使用。分 " + _tab("❐ 刑案歸檔") + " "
                  + _tab("❏ 一般歸檔") + " 兩子頁，各自獨立操作。"),
        ("label", "開始前：先確認歸檔資料夾"),
        ("warn", "資料夾路徑空白、或出現紅字「歸檔資料夾未設定」時，請先到「資料庫設定」頁"
                 "設定本年度歸檔資料夾，再回來歸檔。"),
        ("sec", "歸檔流程（請依序操作）", [
            ("ol", [
                "左側清單<b>點選一筆</b>待歸檔公文（整列選定、顯示藍邊）。",
                "中間候選 PDF 依<b>命中字數</b>排序，確認正確檔案（可點 " + _icon(":/icon_pdf.svg") + " 開啟）。",
                "點該列的 " + _icon(":/icon_archive.svg") + "（歸檔預覽）鈕，系統解析檔名填入下方欄位。",
                "<b>逐格核對</b> 日期／主旨／承辦人，有錯直接改，按 " + _btn("還原預設") + " 可復原。",
                "按 " + _btn_primary("檔案歸檔") + "，PDF 改名歸檔並退出清單。",
            ]),
            ("note", "欄位需全部填妥才可送出。"),
        ]),
        ("sec", "補充", [
            ("ul", [
                "只有紙本、沒有電子檔，選定公文後按 " + _btn_primary("只歸紙本") + "，僅在案由旁標記 " + _icon(":/icon_paper.svg") + " 紙本歸檔，公文續留清單等日後補 PDF。",
                "找不到對的 PDF，可用<b>檔名過濾</b>框縮小候選範圍，或按 " + _btn("重載") + " 重掃資料夾。",
                "重載按鈕會直接重整案件歸檔狀態與候選 PDF 列表。",
            ]),
        ]),
    ],

    6: [
        ("muted", "本頁供管理者維護人員／部門／案類等基礎資料，及歸檔資料夾、跨年度重置；"
                  "歸檔管理登入後僅能變更密碼、設定歸檔資料夾與登出。"
                  "進入需輸入密碼，閒置 10 分鐘自動登出。"),
        ("sec", "維護清單（人員管理／部門管理／案件類型）", [
            ("ul", [
                "<b>新增</b>：按 " + _btn("＋ 新增") + "。",
                "<b>修改</b>：選一列按 " + _btn("✎ 修改") + "，或直接<b>雙擊該列</b>（含停用／啟用、別名等）。",
                "<b>停用</b>的項目仍會在清單顯示（灰字），但不再出現於各頁下拉。",
            ]),
        ]),
        ("sec", "拖拉調整排序，記得存檔", [
            ("p", "<b>直接用滑鼠拖拉整列</b>即可調整顯示順序（決定各頁下拉的排列）。"),
        ]),
        ("warn", "拖拉後務必按 " + _btn("💾 儲存排序") + " 才會寫入。未存就切走會跳提示，排序沒存等於白拉。"),
        ("sec", "歸檔資料夾", [
            ("p", _btn("歸檔資料夾") + " 鈕設定本年度歸檔根目錄（供歸檔頁與資料庫瀏覽頁開啟 PDF 用）。"
                  "新年度或重置後須重新指定。"),
        ]),
        ("sec", "簽收表設定（僅管理者）", [
            ("p", _btn("簽收表設定") + " 鈕可自訂三張簽收表（交辦／刑案／一般）的"
                  "<b>標題文字</b>，以及刑案現行犯的<b>免簽收註記</b>，免改程式、免重新安裝。"),
            ("ul", [
                "通常填入<b>本單位名稱</b>與簽收表正式名稱即可。",
                "尚未設定時，列印頁頂端會紅字提醒，簽收表仍可產生（先以預設文字代替）。",
            ]),
            ("note", "此為單位的永久設定，跨年度重置不會清除。"),
        ]),
        ("sec", "資源回收筒（僅管理者）", [
            ("p", "各業務頁按 " + _btn_danger("✕") + " 刪除的公文<b>不會立即消失</b>，"
                  "會先暫存於資源回收筒，誤刪可在此還原。"),
            ("ul", [
                "點 " + _btn("資源回收筒") + " 進入，選一筆按<b>還原</b>，資料即回填原本的文號。",
                "還原會<b>保留刪除當下的歸檔狀態</b>，原本已歸檔者還原後仍為已歸檔。",
            ]),
            ("note", "回收筒於跨年度重置時一併清空。"),
        ]),
        ("sec", "跨年度重置（最高風險操作）", [
            ("p", "<b>這是把整個系統歸零、迎接新年度的操作，一旦執行不可復原。</b>"),
            ("p", "位於左側下方紅字鈕。執行後會："),
            ("ul", [
                "清空全部公文資料。",
                "刪除所有已停用的人員／部門／案類（要保留請先「啟用」）。",
                "流水號歸零。",
                "清空歸檔資料夾設定。",
            ]),
            ("p", "執行前須手動輸入「RESET」，並會自動備份一份到資料庫目錄，完成後自動重啟。"),
        ]),
        ("warn", "重置前務必先把當年度的程式（exe）與 dbfile.db 一起複製到獨立資料夾保留舊年度，"
                 "重置一旦執行就回不去。"),
    ],

    7: [
        ("muted", "本頁僅管理者可檢視，唯讀。系統會自動記錄關鍵操作（刪除、改承辦、"
                  "參照表異動、歸檔取消、跨年度重置、變更密碼、登入失敗等），供事後查核。"),
        ("sec", "欄位說明", [
            ("map", [
                ("時間", "操作發生的日期時間。"),
                ("身分", "執行當下的登入身分（管理者／歸檔管理／一般使用者）。"),
                ("類別", "操作所屬分類（交辦／刑案／一般／人員／部門／案類／歸檔／系統）。"),
                ("動作", "新增／修改／刪除／取消／重置等；刪除、重置、登入失敗以紅字標示。"),
                ("內容", "該筆操作的摘要（如主旨、新舊承辦人）。"),
                ("對象人", "與該列資料相關的人（如收文者／陳報人）；管理者的刪除不記對象人。"),
            ]),
        ]),
        ("sec", "篩選與匯出", [
            ("ul", [
                "可依<b>期間</b>（起／迄，留白為不限）、<b>身分</b>、<b>類別</b>篩選。",
                "<b>關鍵字</b>比對「內容」與「對象人」欄。",
                "按 " + _btn("匯出 CSV") + " 可將<b>目前篩選後</b>的紀錄存成 CSV 檔留存。",
            ]),
        ]),
        ("warn", "本系統為單機環境，紀錄僅供查核參考，無法防止具資料庫存取權者直接竄改；"
                 "程式內不提供刪除紀錄的功能。"),
    ],
}


# ── HTML 渲染（Dialog 用）─────────────────────────────────────
# 風格：留白編排。段落標題用藍色短豎條（▍）前綴，相鄰段落間插細分隔線，
# 只有警示用色塊。QTextBrowser 不支援圓角／flex，故分隔線用 1px 表格列、
# 條列縮排用 &nbsp;（換行續行不會懸掛對齊，影響甚微）。

def _h_lead(t):
    return f'<p style="font-size:13pt; color:#1c1c1e; line-height:138%; margin:4px 2px 12px;">{t}</p>'

def _h_muted(t):
    return f'<p style="font-size:12pt; color:#8e8e93; line-height:145%; margin:4px 2px 10px;">{t}</p>'

def _h_hint(t):
    return f'<p style="font-size:11pt; color:#8e8e93; margin:8px 2px 2px;">{t}</p>'

def _h_header(t):
    # 鋼藍細豎條 + 標題，下方細分隔線（取代滿版色帶，留白更清爽，對齊速查卡）
    return ('<p style="margin:0; font-size:6pt; line-height:6pt;">&#160;</p>'   # 段落上方留白
            '<table cellspacing="0" cellpadding="0"><tr>'
            '<td bgcolor="#4977b1" width="4" style="font-size:13pt; line-height:140%;">&#160;</td>'
            '<td width="9" style="font-size:13pt;">&#160;</td>'
            f'<td style="font-size:13pt;"><b><font color="#1c1c1e">{t}</font></b></td>'
            '</tr></table>'
            # 細分隔線（1pt 高鋼藍淺色橫條）
            '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
            '<td bgcolor="#DCE5EF" style="font-size:1pt; line-height:1pt;">&#160;</td>'
            '</tr></table>'
            '<p style="margin:0; font-size:5pt; line-height:5pt;">&#160;</p>')

def _h_warn(t):
    # 單格琥珀框：cellpadding 給均勻內距。QTextBrowser 對巢狀表格／rowspan 背景
    # 渲染不穩（會多塞留白、版面跑掉），故警示框維持最單純的單格。
    return ('<table width="100%" cellspacing="0" cellpadding="10"><tr>'
            f'<td bgcolor="#FBF1DC" style="font-size:13pt; color:#7a5b16; '
            f'line-height:142%;"><b>⚠</b>&nbsp; {t}</td>'
            '</tr></table>'
            '<p style="margin:0; font-size:5pt; line-height:5pt;">&#160;</p>')

def _h_body(items):
    parts = []
    for it in items:
        kind = it[0]
        if kind == "p":
            parts.append(f'<p style="font-size:13pt; color:#1c1c1e; line-height:138%; margin:0 2px 6px;">{it[1]}</p>')
        elif kind == "note":
            parts.append(f'<p style="font-size:11pt; color:#8e8e93; line-height:150%; margin:2px 2px 6px;">{it[1]}</p>')
        elif kind == "ol":
            # 兩欄表格＝懸掛縮排：序號用實心鋼藍方塊（內嵌單格表格、置頂不撐高），
            # 文字一欄、續行對齊文字欄
            rows = ""
            for i, t in enumerate(it[1]):
                badge = ('<table cellspacing="0" cellpadding="0"><tr>'
                         '<td bgcolor="#4977b1" width="20" height="20" align="center" '
                         'valign="middle" style="font-size:11pt; color:#FFFFFF; '
                         f'font-weight:600; line-height:100%;">{i+1}</td>'
                         '</tr></table>')
                rows += (f'<tr><td width="27" valign="top">{badge}</td>'
                         f'<td valign="top" style="font-size:13pt; color:#1c1c1e; '
                         f'line-height:142%;">{t}</td></tr>')
            parts.append(f'<table width="100%" cellspacing="0" cellpadding="4">{rows}</table>'
                         '<p style="margin:0; font-size:3pt; line-height:3pt;">&#160;</p>')
        elif kind == "ul":
            rows = "".join(
                '<tr><td width="18" valign="top" style="font-size:13pt; color:#1c1c1e;">·</td>'
                f'<td valign="top" style="font-size:13pt; color:#1c1c1e; line-height:142%;">{t}</td></tr>'
                for t in it[1])
            parts.append(f'<table width="100%" cellspacing="0" cellpadding="4">{rows}</table>'
                         '<p style="margin:0; font-size:3pt; line-height:3pt;">&#160;</p>')
        elif kind == "map":
            inner = "<br>".join(
                f'<span style="font-weight:600;">{k}</span>&nbsp;&nbsp;{v}' for k, v in it[1])
            parts.append(f'<p style="font-size:13pt; color:#1c1c1e; line-height:140%; margin:0 12px 6px;">{inner}</p>')
        elif kind == "table":
            heads, rows = it[1], it[2]
            hcells = "".join(
                f'<td bgcolor="#4977b1" style="font-size:12pt; color:#FFFFFF; '
                f'font-weight:600;">&nbsp;{x}&nbsp;</td>' for x in heads)
            body = ""
            for a, b in rows:
                body += (f'<tr><td bgcolor="#EEF3F8" style="font-size:13pt; '
                         f'color:#1c1c1e; font-weight:600;">&nbsp;{a}&nbsp;</td>'
                         f'<td style="font-size:13pt; color:#1c1c1e;">&nbsp;{b}&nbsp;</td></tr>')
            parts.append('<table border="1" cellspacing="0" cellpadding="6">'
                         f'<tr>{hcells}</tr>{body}</table>'
                         '<p style="margin:0; font-size:6pt; line-height:6pt;">&#160;</p>')
        elif kind == "cols":
            n, items = it[1], it[2]
            w = 100 // n
            rows = []
            for r in range(0, len(items), n):
                chunk = items[r:r + n]
                tds = "".join(
                    f'<td width="{w}%" style="font-size:13pt; color:#1c1c1e;">'
                    f'<font color="#4977b1">·</font> {x}</td>' for x in chunk)
                tds += '<td></td>' * (n - len(chunk))
                rows.append(f"<tr>{tds}</tr>")
            parts.append('<table width="100%" cellspacing="0" cellpadding="4">'
                         + "".join(rows) + "</table>"
                         + '<p style="margin:0; font-size:5pt; line-height:5pt;">&#160;</p>')
    return "".join(parts)

def _render_html(blocks):
    out = []
    prev = None
    for b in blocks:
        kind = b[0]
        if kind == "lead":
            out.append(_h_lead(b[1]))
        elif kind == "muted":
            out.append(_h_muted(b[1]))
        elif kind == "label":
            out.append(_h_header(b[1]))
        elif kind == "hint":
            out.append(_h_hint(b[1]))
        elif kind == "warn":
            out.append(_h_warn(b[1]))
        elif kind == "sec":
            out.append(_h_header(b[1]) + _h_body(b[2]))
        prev = kind
    return "".join(out)


HELP_HTML = {i: _render_html(HELP_PAGES[i]) for i in HELP_PAGES}


# ── 純文字渲染（docs/help_text_review.txt 校稿檔用）──────────────
def _strip(s):
    return re.sub(r"<[^>]+>", "", s).replace("&nbsp;", " ").replace("&#160;", " ").replace("&amp;", "&")

def render_review_text(idx):
    out = []
    for b in HELP_PAGES[idx]:
        kind = b[0]
        if kind in ("lead", "muted", "hint"):
            out.append(_strip(b[1]))
        elif kind == "label":
            out.append("## " + _strip(b[1]))
        elif kind == "warn":
            out.append("[警示] ⚠ " + _strip(b[1]))
        elif kind == "sec":
            out.append("## " + _strip(b[1]))
            for it in b[2]:
                if it[0] in ("p", "note"):
                    out.append(_strip(it[1]))
                elif it[0] == "ol":
                    out += [f"{i+1}. " + _strip(t) for i, t in enumerate(it[1])]
                elif it[0] == "ul":
                    out += ["- " + _strip(t) for t in it[1]]
                elif it[0] == "map":
                    out += [f"  {k} ｜ {v}" for k, v in it[1]]
                elif it[0] == "table":
                    out.append("  " + " ｜ ".join(it[1]))
                    out += [f"  {a} ｜ {b}" for a, b in it[2]]
                elif it[0] == "cols":
                    out += [f"- {x}" for x in it[2]]
            out.append("")
    return "\n".join(out).strip()


# ── tooltip 候選（各 Tab 欄位／按鈕，setToolTip 用）──────────────
HELP_TIPS = {
    0: {
        "btn_input_docnum": "輸入或掃描文號後按 Enter 加入清單",
        "btn_clear_all":    "清空目前待發清單，不會刪除資料",
        "btn_send":         "依所選發文日期與人員，將清單一次全部發文",
    },
    1: {
        "btn_recv_submit": "確認收文並取得文號",
        "btn_recv_clear":  "清空目前輸入欄位",
    },
    2: {
        "btn_rpt_submit": "確認陳報並取得文號",
        "btn_rpt_clear":  "清空目前輸入欄位",
    },
    3: {
        "btn_generate": "依所選發文日期產生簽收表預覽",
        "btn_download": "將簽收表另存為 PDF 檔",
        "btn_print":    "開啟列印預覽並送出列印（預設彩色＋長邊雙面，可改）",
    },
    4: {
        "task_overdue":  "僅顯示已逾限辦日期且尚未發文之交辦單",
        "task_seg_full": "顯示全部欄位，含精簡模式隱藏之欄位",
        "crim_seg_full": "顯示全部欄位，含精簡模式隱藏之欄位",
        "gen_seg_full":  "顯示全部欄位，含精簡模式隱藏之欄位",
    },
    5: {
        "crim_paper_only": "僅標記紙本歸檔，不需電子檔",
        "gen_paper_only":  "僅標記紙本歸檔，不需電子檔",
    },
    6: {},
}


# ── 速查卡濃縮母本（gen_quickstart.py 產 PDF 用）────────────────
# 與 HELP_PAGES 同檔但各自合身：HELP 是完整說明，速查卡只留「用途一句＋
# 關鍵步驟」，供新進承辦快速上手，細節仍回程式內 HELP。改速查卡只動這裡。
# 結構：idx -> (用途一句, [步驟…], 提示 or None)
QUICKSTART = {
    0: ("批次把交辦單發文，並寫入發文日期與發文人員。按下 {X} 可從發文清單移除該列。",
        ["先選發文日期（預設今天）與發文人員。",
         "文號輸入框輸入文號後按 Enter 加入清單，連續輸入下一筆。",
         "按「確認發文」，確認筆數後一次寫入。"],
        "發文日期顯示橘字，代表該筆先前已發過，這次會覆蓋舊日期。"),
    1: ("登錄一張新交辦單，由系統自動配發文號。按下 {X} 可刪除該筆，該文號將作廢。",
        ["填交辦事由、業務組、承辦人，設定收文日期與限辦日期（免覆則勾「免覆」）。",
         "按「確認收文」取得文號，接著輸入下一張。"],
        "主旨寫具體些，牽涉人名建議寫入，日後在「資料庫瀏覽」較好查。"),
    2: ("登錄刑案與業務案件，由系統自動配發文號。按下 {X} 可刪除該筆，該文號將作廢。",
        ["上方頁籤切換「刑案／一般」表單。",
         "填妥對應欄位。",
         "按「確認陳報」取得文號。"],
        ["刑案若有報案人強烈建議填寫，可減輕歸檔人員負擔。",
         ["查獲／受理日期依案件狀態填：",
          "現行犯：陳報單日期", "到案：陳報單日期", "未到案：報案日期"],
         ["下列案類請使用刑案陳報：",
          "通緝", "失聯移工", "汽機車／車牌相關（遺失、侵占、失竊、尋獲）", "社會秩序維護法"]]),
    3: ("依發文日期彙整當天所有發文，整理成簽收表。",
        ["選發文日期（預設今天）。",
         "按「產生預覽」顯示簽收表預覽。",
         "按「下載 PDF」存檔，或按「列印表單」送印（預設彩色＋長邊雙面）。"],
        None),
    4: ("查詢資料。上方分交辦單／刑案／一般三個子頁。",
        ["搜尋框輸入關鍵字，邊打邊自動比對。",
         "用範圍下拉可限定只比某一欄。",
         "按「完整」顯示全部欄位（預設精簡只顯示重要欄位）。"],
        "交辦單頁左下篩選鈕可只看逾期未回；主旨欄左側 PDF 圖示可直接開檔。"),
    5: ("把電子檔 PDF 歸檔並改名。本頁供管理者與歸檔管理使用。",
        ["左側清單點選一筆待歸檔公文。",
         "中間候選 PDF 依命中字數排序，確認正確檔案。",
         "按「歸檔預覽」解析檔名，逐格核對日期／主旨／承辦人。",
         "按「檔案歸檔」完成。"],
        "開始前先確認歸檔資料夾已設定；只有紙本按「只歸紙本」。"),
    6: ("維護人員／部門／案類等基礎資料、歸檔資料夾與跨年度重置。本頁供管理者使用；歸檔管理僅能變更密碼與設定歸檔資料夾。",
        ["新增或修改清單項目（雙擊整列可修改，含停用／啟用、別名）。",
         "拖拉整列調整顯示順序，務必按「儲存排序」才會寫入。",
         "按「歸檔資料夾」設定本年度歸檔根目錄。"],
        "跨年度重置會清空全部資料且不可復原，執行前務必另存當年度程式與資料庫。"),
}
