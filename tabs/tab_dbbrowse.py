from PySide6.QtWidgets import QVBoxLayout

from base_tab import BaseTab
from db_utils import getResourcePath, loadUi


class TabDBBrowse(BaseTab):
    """資料庫瀏覽（尚未實作，佔位用）"""

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        browse_widget = loadUi(getResourcePath("Layout5.ui"))
        if not browse_widget:
            return

        inner = browse_widget.centralWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)
