import io
import sqlite3
from datetime import date

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QDateEdit, QFileDialog,
)
from PySide6.QtCore import Qt, QDate, QThread, Signal
from PySide6.QtGui  import QPixmap, QImage, QPainter, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog

from lib.base_tab import BaseTab
from lib.db_utils import getResourcePath, loadUi, msgInfo, msgWarning

# ── 字型（跨平台）────────────────────────────────────────
def _find_cjk_fonts():
    import os
    candidates = {
        'reg': [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',  # Linux
            '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
            r'C:\Windows\Fonts\msjh.ttc',      # Windows 微軟正黑體
            r'C:\Windows\Fonts\mingliu.ttc',
            r'C:\Windows\Fonts\kaiu.ttf',
            r'C:\Windows\Fonts\simsun.ttc',
            '/System/Library/Fonts/PingFang.ttc',  # macOS
        ],
        'bold': [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc',
            r'C:\Windows\Fonts\msjhbd.ttc',
            r'C:\Windows\Fonts\msjh.ttc',
            r'C:\Windows\Fonts\kaiu.ttf',
            '/System/Library/Fonts/PingFang.ttc',
        ],
    }
    reg  = next((p for p in candidates['reg']  if os.path.exists(p)), None)
    bold = next((p for p in candidates['bold'] if os.path.exists(p)), None)
    if reg is None:
        raise FileNotFoundError(
            '找不到中文字型，請確認系統已安裝微軟正黑體（msjh.ttc）')
    return reg, bold or reg

_REG, _BOLD = _find_cjk_fonts()

def fp(size, bold=False):
    return fm.FontProperties(fname=_BOLD if bold else _REG, size=size)

# ── A4 直向（inch）────────────────────────────────────────
A4_W, A4_H = 8.27, 11.69

# ── 版面常數（normalized 0~1）────────────────────────────
R        = 0.03
TOP      = 0.95
BOT      = 0.03
TITLE_H  = 0.050
HDR_H    = 0.038
ROW_H    = 0.052
DATE_H   = 0.030
PAD      = 0.008
TABLE_L  = 0.03
TABLE_W  = 1 - TABLE_L - R

NOTE = '＜現行犯已隨案移送免簽收＞'


# ── 工具函式 ──────────────────────────────────────────────
def _fmt_date(d):
    if not d: return ''
    try:
        y, m, day = d.split('-')
        return f'{y}/{m}/{day}'
    except: return d

def _today():
    return date.today().strftime('%Y/%m/%d')

def _wrap_clamp(text, col_width_norm, max_lines=2, pad=PAD, fixed_size=None):
    """
    fixed_size=None（預設）：12pt先試，超過縮10pt，還超過截斷加…
    fixed_size=N：固定N pt不縮小，超過直接截斷加…
    回傳 (wrapped_text, font_prop)
    """
    if not text:
        return '', fp(fixed_size or 12)

    A4_PT    = 595.3
    max_w_pt = (col_width_norm - pad * 2) * A4_PT * 0.86

    def wrap(t, size):
        def cw(ch): return size if ord(ch) > 0x2E80 else size * 0.6
        lines, line, lw = [], '', 0.0
        for ch in t:
            w = cw(ch)
            if lw + w > max_w_pt and line:
                lines.append(line); line, lw = ch, w
            else:
                line += ch; lw += w
        if line: lines.append(line)
        return lines

    def truncate(lines, size):
        lines = lines[:max_lines]
        def cw(ch): return size if ord(ch) > 0x2E80 else size * 0.6
        last = lines[-1]
        while last and sum(cw(c) for c in last + '…') > max_w_pt:
            last = last[:-1]
        lines[-1] = last + '…'
        return '\n'.join(lines), fp(size)

    if fixed_size:
        # 固定字體，只截斷不縮小
        lines = wrap(text, fixed_size)
        if len(lines) <= max_lines:
            return '\n'.join(lines), fp(fixed_size)
        return truncate(lines, fixed_size)

    # 試 12pt
    lines = wrap(text, 12)
    if len(lines) <= max_lines:
        return '\n'.join(lines), fp(12)

    # 縮到 10pt
    lines = wrap(text, 10)
    if len(lines) <= max_lines:
        return '\n'.join(lines), fp(10)

    # 還超過：截斷
    return truncate(lines, 10)


def _fit_font(text, col_width_norm, max_size=14, min_size=8, pad=PAD):
    """自動縮小字體，讓文字剛好放進欄寬（不換行）"""
    if not text:
        return fp(max_size)
    A4_PT    = 595.3
    max_w_pt = (col_width_norm - pad * 2) * A4_PT * 0.86

    for size in range(max_size, min_size - 1, -1):
        def char_w(ch):
            return size if ord(ch) > 0x2E80 else size * 0.6
        w = sum(char_w(c) for c in text)
        if w <= max_w_pt:
            return fp(size)
    return fp(min_size)



def _rows_per_page():
    avail = TOP - DATE_H - TITLE_H - HDR_H - BOT
    return max(1, int(avail / ROW_H))


# ── 畫單頁 ────────────────────────────────────────────────
# 色彩配置：(標題背景, 表頭背景, 奇數列背景, 外框/欄線, 標題文字)
SCHEMES = {
    'task':     ('#B3C6E6', '#C9D9EE', '#DDEBF7', '#4472C4', '#1F3864'),
    'criminal': ('#6B8E4E', '#A8C68F', '#EEF5E8', '#4A6A32', '#1E3B12'),
    'general':  ('#F4B183', '#F8CBAD', '#FCE4D6', '#C05000', '#3D1500'),
}

def _draw_page(side_label, table_title, print_date, disp_date,
               headers, col_ratios, rows, fill_to, is_crim=False,
               page_num=1, total_pages=1, scheme='task'):
    fig = plt.figure(figsize=(A4_W, A4_H))
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')
    c_title, c_hdr, c_row_odd, c_border, c_text = SCHEMES[scheme]

    # 列印日期（左）
    ax.text(TABLE_L + PAD, TOP - DATE_H/2,
            f'列印日期　{print_date}',
            fontproperties=fp(8), ha='left', va='center',
            transform=ax.transAxes, color='#333333')
    # 發文日期（右，粗體）
    ax.text(1-R-PAD, TOP - DATE_H/2,
            f'發文日期：{disp_date}',
            fontproperties=fp(10, bold=True), ha='right', va='center',
            transform=ax.transAxes, color=c_text)
    cy = TOP - DATE_H

    # 大標題
    ax.add_patch(patches.FancyBboxPatch(
        (TABLE_L, cy-TITLE_H), TABLE_W, TITLE_H,
        boxstyle='square,pad=0', lw=0, fc=c_title,
        transform=ax.transAxes, zorder=1))
    ax.text(TABLE_L + TABLE_W/2, cy - TITLE_H/2, table_title,
            fontproperties=fp(14, bold=True), ha='center', va='center',
            transform=ax.transAxes, color=c_text)
    cy -= TITLE_H

    # 欄 x 位置
    col_xs = [TABLE_L]
    for r in col_ratios[:-1]:
        col_xs.append(col_xs[-1] + TABLE_W * r)

    # 表頭
    # 表頭上方粗分隔線
    ax.plot([TABLE_L, TABLE_L+TABLE_W], [cy]*2,
            color=c_border, lw=0.8, transform=ax.transAxes, zorder=4)

    ax.add_patch(patches.FancyBboxPatch(
        (TABLE_L, cy-HDR_H), TABLE_W, HDR_H,
        boxstyle='square,pad=0', lw=0, fc=c_hdr,
        transform=ax.transAxes, zorder=1))
    CENTER_HDRS = {0, 1, 2, 3, 5}   # 編號、日期、業務/案類、承辦人、簽收 置中
    for hidx, (hdr, cx) in enumerate(zip(headers, col_xs)):
        if hidx in CENTER_HDRS:
            x_pos = cx + TABLE_W * col_ratios[hidx] / 2
            ha = 'center'
        else:
            x_pos = cx + PAD
            ha = 'left'
        ax.text(x_pos, cy-HDR_H/2, hdr,
                fontproperties=fp(12, bold=True), ha=ha, va='center',
                transform=ax.transAxes, color=c_text)
    ax.plot([TABLE_L, TABLE_L+TABLE_W], [cy-HDR_H]*2,
            color=c_border, lw=0.8, transform=ax.transAxes)
    cy -= HDR_H

    # 資料列
    sign_idx = len(headers) - 1
    for ridx in range(fill_to):
        if ridx < len(rows):
            row = rows[ridx]
            if is_crim:
                is_current = str(row[-1]) == 'A_現行犯'
                display = list(row[:-1]) + ['']
            else:
                is_current = False
                display = list(row)
        else:
            display    = [''] * len(headers)
            is_current = False

        bg = c_row_odd if ridx % 2 == 0 else '#FFFFFF'
        ax.add_patch(patches.FancyBboxPatch(
            (TABLE_L, cy-ROW_H), TABLE_W, ROW_H,
            boxstyle='square,pad=0', lw=0, fc=bg,
            transform=ax.transAxes, zorder=1))

        for cidx, (val, cx, ratio) in enumerate(zip(display, col_xs, col_ratios)):
            # 各欄設定
            # 0=編號, 1=日期, 2=類型/業務, 3=承辦人, 4=主旨, 5=簽收
            if cidx == sign_idx and is_current:
                text  = NOTE
                color = '#C00000'
                font  = fp(10)
                ha    = 'center'
            elif cidx == 0:         # 編號：自動縮放，不切字
                text  = str(val) if val else ''
                color = '#111111'
                font  = _fit_font(text, TABLE_W * ratio, max_size=20, min_size=8)
                ha    = 'center'
            elif cidx == 1:         # 日期
                text  = str(val) if val else ''
                color = '#111111'
                font  = fp(10)
                ha    = 'center'
            elif cidx == 3:         # 承辦人
                text  = str(val) if val else ''
                color = '#111111'
                font  = fp(12)
                ha    = 'center'
            elif cidx == sign_idx:  # 簽收空白
                text  = str(val) if val else ''
                color = '#111111'
                font  = fp(12)
                ha    = 'center'
            else:
                text  = str(val) if val else ''
                color = '#111111'
                font  = fp(12)
                ha    = 'left'

            # 長文字欄：業務/案類(2) 超2行縮10pt再截斷；主旨(4) 直接12pt截斷
            if cidx in (2, 4) and not (cidx == sign_idx and is_current):
                if cidx == 2:
                    text, font = _wrap_clamp(text, TABLE_W * ratio, max_lines=2)
                    ha = 'center'   # 業務/案類置中
                else:  # cidx == 4 主旨
                    text, font = _wrap_clamp(text, TABLE_W * ratio, max_lines=2, fixed_size=12)

            # 置中欄用欄位中心 x
            x_pos = cx + TABLE_W * ratio / 2 if ha == 'center' else cx + PAD
            ax.text(x_pos, cy - ROW_H/2, text,
                    fontproperties=font, ha=ha, va='center',
                    transform=ax.transAxes, color=color, clip_on=True,
                    multialignment='left', linespacing=1.3)

        ax.plot([TABLE_L, TABLE_L+TABLE_W], [cy-ROW_H]*2,
                color=c_border, lw=0.5, transform=ax.transAxes)
        cy -= ROW_H

    # 外框
    box_top = TOP - DATE_H
    box_h   = box_top - cy
    ax.add_patch(patches.FancyBboxPatch(
        (TABLE_L, cy), TABLE_W, box_h,
        boxstyle='square,pad=0', lw=1.2,
        ec=c_border, fc='none',
        transform=ax.transAxes, zorder=3))

    # 欄線
    for cx in col_xs[1:]:
        ax.plot([cx, cx], [cy, box_top - TITLE_H],
                color=c_border, lw=0.5, transform=ax.transAxes)

    # 左側直排大字已移除

    # 頁碼（底部置中）
    ax.text(0.5, BOT/2,
            str(page_num),
            fontproperties=fp(9), ha='center', va='center',
            transform=ax.transAxes, color='#555555')
    return fig


# ── 產生所有頁（回傳 figures + pdf_bytes）────────────────
def generate_pages(db_path, date_str):
    """
    回傳 (png_list, pdf_bytes, print_pngs)
      png_list   — list of PNG bytes，每頁一個（200 dpi，螢幕預覽用）
      pdf_bytes  — 完整 PDF bytes（另存用）
      print_pngs — list of PNG bytes，每頁一個（300 dpi 全頁，列印用）
    查無資料回傳 (None, None, None)
    """
    conn = sqlite3.connect(db_path)
    task = conn.execute(
        "SELECT 編號, 發文日期, 業務組, 所承辦人, 交辦事由 "
        "FROM View_Task_Full WHERE 發文日期=? "
        "ORDER BY 紀錄時間 IS NULL, 紀錄時間, CAST(編號 AS INT)",
        (date_str,)).fetchall()
    crim = conn.execute(
        "SELECT 送文編號, 陳報日期, 案類, 主承辦人, 嫌疑人_案由, 發文分類 "
        "FROM View_Criminal_Full WHERE 陳報日期=? ORDER BY CAST(送文編號 AS INT)",
        (date_str,)).fetchall()
    gen  = conn.execute(
        "SELECT 送文編號, 陳報日期, 業務單位, 陳報人, 陳報主旨 "
        "FROM View_General_Full WHERE 陳報日期=? ORDER BY CAST(送文編號 AS INT)",
        (date_str,)).fetchall()
    conn.close()

    if not task and not crim and not gen:
        return None, None, None

    print_date = _today()
    disp_date  = _fmt_date(date_str)
    per        = _rows_per_page()

    def fmt(rows):
        out = []
        for r in rows:
            r = list(r); r[1] = _fmt_date(r[1]); out.append(tuple(r))
        return out

    sections = []
    if task:
        sections.append(('交辦單發文', '龍興派出所交辦單發文簽收表',
            ['編號','陳報日期','業務單位','承辦人','陳報主旨','簽收'],
            [0.07, 0.146, 0.13, 0.15, 0.234, 0.27], fmt(task), False))
    if crim:
        sections.append(('刑案陳報單發文', '龍興派出所刑案陳報單發文簽收表',
            ['編號','陳報日期','刑案類型','承辦人','陳報主旨','簽收'],
            [0.07, 0.146, 0.13, 0.15, 0.234, 0.27], fmt(crim), True))
    if gen:
        sections.append(('一般陳報單發文', '龍興派出所一般陳報單發文簽收表',
            ['編號','陳報日期','業務單位','承辦人','陳報主旨','簽收'],
            [0.07, 0.146, 0.13, 0.15, 0.234, 0.27], fmt(gen), False))

    def _blank_page():
        """產生一頁空白頁（雙面印用）"""
        fig = plt.figure(figsize=(A4_W, A4_H))
        fig.patch.set_facecolor('white')
        return fig

    # 各 section 獨立頁碼
    section_page_counts = []
    for side, title, headers, ratios, rows, is_crim in sections:
        n = max(1, -(-len(rows) // per))  # ceil division
        section_page_counts.append(n)

    figs = []
    scheme_map = {s[0]: sk for s, sk in zip(sections, ['task','criminal','general'][:len(sections)])}

    for (side, title, headers, ratios, rows, is_crim), section_total in zip(sections, section_page_counts):
        sk = scheme_map[side]
        section_figs = []
        for page_num, start in enumerate(range(0, max(len(rows), 1), per), start=1):
            chunk = rows[start:start+per]
            fig = _draw_page(side, title, print_date, disp_date,
                             headers, ratios, chunk, per, is_crim,
                             page_num=page_num, total_pages=section_total,
                             scheme=sk)
            section_figs.append(fig)

        figs.extend(section_figs)

        # 若此 section 為奇數頁，插入空白頁
        if section_total % 2 == 1:
            figs.append(_blank_page())

    # PNG bytes（用於預覽，不需 poppler）
    png_list = []
    for fig in figs:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=200, bbox_inches='tight',
                    facecolor='white')
        buf.seek(0)
        png_list.append(buf.read())

    # PNG bytes（用於另存 / 列印）
    pdf_buf = io.BytesIO()
    with PdfPages(pdf_buf) as pdf:
        for fig in figs:
            pdf.savefig(fig, dpi=150)
    pdf_buf.seek(0)
    pdf_bytes = pdf_buf.read()

    # 列印用全頁影像（300 dpi，不裁切，維持 A4 比例對齊紙張）
    print_pngs = []
    for fig in figs:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=300, facecolor='white')
        buf.seek(0)
        print_pngs.append(buf.read())

    for fig in figs:
        plt.close(fig)

    return png_list, pdf_bytes, print_pngs


# ── 背景執行緒 ────────────────────────────────────────────
class _PdfWorker(QThread):
    done   = Signal(object, bytes, object)   # (png_list, pdf_bytes, print_pngs)
    failed = Signal(str)

    def __init__(self, db_path, date_str):
        super().__init__()
        self.db_path  = db_path
        self.date_str = date_str

    def run(self):
        try:
            png_list, pdf_bytes, print_pngs = generate_pages(self.db_path, self.date_str)
            if png_list is None:
                self.failed.emit('查無資料')
            else:
                self.done.emit(png_list, pdf_bytes, print_pngs)
        except Exception as e:
            self.failed.emit(str(e))


# ── Tab 3 UI ──────────────────────────────────────────────
class TabPrint(BaseTab):

    def setup(self, tab_index):
        page = self.tab_widget.widget(tab_index)
        if page is None:
            return

        # 載入 UI（與 tab_report 相同模式）
        ui = loadUi(getResourcePath('layouts/Layout4.ui'))
        if not ui:
            return
        inner = ui.centralWidget()

        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)

        # 取得 UI 元件
        self.date_edit    = inner.findChild(QDateEdit,    'print_date')
        self.btn_gen      = inner.findChild(QPushButton,  'btn_generate')
        self.status_lbl   = inner.findChild(QLabel,       'lbl_status')
        self.btn_download = inner.findChild(QPushButton,  'btn_download')
        self.btn_print    = inner.findChild(QPushButton,  'btn_print')
        self.scroll       = inner.findChild(QScrollArea,  'scroll_preview')

        # 初始化日期
        if self.date_edit:
            self.date_edit.setDate(QDate.currentDate())

        # 按鈕樣式與信號
        _btn_style = """
            QPushButton { color: #111111; }
            QPushButton:disabled { color: #AAAAAA; background-color: #E0E0E0; border: 1px solid #CCCCCC; }
        """
        if self.btn_download:
            self.btn_download.setStyleSheet(_btn_style)
            self.btn_download.clicked.connect(self._on_download)
        if self.btn_print:
            self.btn_print.setStyleSheet(_btn_style)
            self.btn_print.clicked.connect(self._on_print)
        if self.btn_gen:
            self.btn_gen.clicked.connect(self._on_generate)

        # 捲動預覽容器
        self._container = inner.findChild(QWidget, 'scroll_contents')
        self._layout    = self._container.layout() if self._container else QVBoxLayout()
        if self._layout:
            self._layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self._worker     = None
        self._pdf_bytes  = None
        self._print_pngs = None

    def _on_generate(self):
        if self._worker and self._worker.isRunning():
            return
        date_str = self.date_edit.date().toString('yyyy-MM-dd')
        self.btn_gen.setEnabled(False)
        self.status_lbl.setText('產生中…')
        self._clear()

        self._worker = _PdfWorker(self.db_path, date_str)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, png_list, pdf_bytes, print_pngs):
        self._pdf_bytes  = pdf_bytes
        self._print_pngs = print_pngs
        self.btn_gen.setEnabled(True)
        self.btn_download.setEnabled(True)
        self.btn_print.setEnabled(True)
        self._render(png_list)

    def _on_fail(self, msg):
        self.btn_gen.setEnabled(True)
        self.btn_download.setEnabled(False)
        self.btn_print.setEnabled(False)
        self.status_lbl.setText('')
        if msg == '查無資料':
            msgInfo('提示', '此日期查無發文資料')
        else:
            msgWarning('錯誤', f'產生失敗：{msg}')

    def _render(self, png_list):
        self._clear()
        scroll_w = self.scroll.viewport().width() - 32
        for png_bytes in png_list:
            qimg = QImage.fromData(png_bytes)
            pix  = QPixmap.fromImage(qimg)
            if pix.width() > scroll_w > 0:
                pix = pix.scaledToWidth(scroll_w, Qt.SmoothTransformation)
            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setAlignment(Qt.AlignHCenter)
            lbl.setStyleSheet('background:white; border:1px solid #BBBBBB;')
            self._layout.addWidget(lbl)
        self.status_lbl.setText(f'共 {len(png_list)} 頁')

    def _on_download(self):
        if not self._pdf_bytes:
            return
        date_str = self.date_edit.date().toString('yyyy-MM-dd')
        path, _ = QFileDialog.getSaveFileName(
            None, '儲存 PDF', f'簽收表_{date_str}.pdf', 'PDF 檔案 (*.pdf)')
        if path:
            with open(path, 'wb') as f:
                f.write(self._pdf_bytes)

    def _on_print(self):
        if not self._print_pngs:
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        dlg = QPrintPreviewDialog(printer, self.tab_widget)
        dlg.setWindowTitle('列印預覽')
        dlg.resize(900, 1000)
        dlg.paintRequested.connect(self._paint_pages)
        dlg.exec()

    def _paint_pages(self, printer):
        """把 300 dpi 全頁影像逐頁畫到印表機頁面（等比置中填滿）"""
        painter = QPainter(printer)
        first = True
        for png_bytes in self._print_pngs:
            img = QImage.fromData(png_bytes)
            if img.isNull():
                continue
            if not first:
                printer.newPage()
            first = False
            # viewport = 當前可列印區域（device pixel），避開 enum 命名空間差異
            vp = painter.viewport()
            scaled = img.scaled(
                vp.width(), vp.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = vp.x() + (vp.width()  - scaled.width())  // 2
            y = vp.y() + (vp.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        painter.end()

    def _clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.status_lbl.setText('')
