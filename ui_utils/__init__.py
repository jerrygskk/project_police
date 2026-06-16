# ui_utils/__init__.py
# 統一對外介面：外部永遠只寫 `from ui_utils import xxx`
# 不論內部如何拆分，這裡都不需要改動外部呼叫端

from .status  import calcOverdue, colorForStatus
from .sticky_scroll import attachStickyScroll
from .widgets import (
    setupFilterCombo, setupDateEditToToday, refreshFilterCombo,
    RowHoverFilter, RowHoverDelegate,
)
from .table   import (
    setupPreviewTable,
    autoResizeTable,
    makeDeleteBtn,
    refreshDeleteBtns,
    setDocIdLinkCell,
    FIXED_COL_WIDTHS,
)

from .edit_dialog import TaskEditDialog, CriminalEditDialog, GeneralEditDialog
from .settings_dialogs import (
    PersonnelAddDialog, PersonnelEditDialog,
    DeptAddDialog, DeptEditDialog,
    CaseTypeAddDialog, CaseTypeEditDialog,
    ChangePasswordDialog, ResetDialog,
)

__all__ = [
    "calcOverdue",
    "colorForStatus",
    "attachStickyScroll",
    "setupFilterCombo",
    "refreshFilterCombo",
    "setupDateEditToToday",
    "RowHoverFilter",
    "RowHoverDelegate",
    "setupPreviewTable",
    "autoResizeTable",
    "makeDeleteBtn",
    "refreshDeleteBtns",
    "setDocIdLinkCell",
    "TaskEditDialog",
    "CriminalEditDialog",
    "GeneralEditDialog",
    "FIXED_COL_WIDTHS",
    "PersonnelAddDialog", "PersonnelEditDialog",
    "DeptAddDialog", "DeptEditDialog",
    "CaseTypeAddDialog", "CaseTypeEditDialog",
    "ChangePasswordDialog", "ResetDialog",
]
