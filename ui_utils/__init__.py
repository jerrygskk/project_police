# ui_utils/__init__.py
# 統一對外介面：外部永遠只寫 `from ui_utils import xxx`
# 不論內部如何拆分，這裡都不需要改動外部呼叫端

from .status  import calcOverdue, colorForStatus
from .widgets import setupFilterCombo, setupDateEditToToday
from .table   import (
    setupPreviewTable,
    autoResizeTable,
    makeDeleteBtn,
    setDocIdLinkCell,
    FIXED_COL_WIDTHS,
)

from .edit_dialog import TaskEditDialog, CriminalEditDialog, GeneralEditDialog

__all__ = [
    "calcOverdue",
    "colorForStatus",
    "setupFilterCombo",
    "setupDateEditToToday",
    "setupPreviewTable",
    "autoResizeTable",
    "makeDeleteBtn",
    "setDocIdLinkCell",
    "TaskEditDialog",
    "CriminalEditDialog",
    "GeneralEditDialog",
    "FIXED_COL_WIDTHS",
]
