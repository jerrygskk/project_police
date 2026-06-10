from PySide6.QtWidgets import QVBoxLayout

from base_tab import BaseTab
from db_utils import getResourcePath, loadUi


class TabArchive(BaseTab):
    """檔案歸檔（尚未實作，佔位用）"""

    def setup(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            return

        archive_widget = loadUi(getResourcePath("Layout6.ui"))
        if not archive_widget:
            return

        inner = archive_widget.centralWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(inner)
