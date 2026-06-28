# ui_utils/__init__.py
# 統一對外介面：外部永遠只寫 `from ui_utils import xxx`
# 不論內部如何拆分，這裡都不需要改動外部呼叫端

from .ui_common import (
    msgInfo, msgWarning, msgCritical, confirmBox, loadUi,
    BTN_CONFIRM, BTN_DANGER, BTN_CANCEL,
)
from .status  import calcOverdue, colorForStatus
from .sticky_scroll import attachStickyScroll
from .widgets import (
    setupFilterCombo, setupDateEditToToday, setupDateEditCalendarOnly,
    refreshFilterCombo, runWithBusy, preserveScroll,
    RowHoverFilter, RowHoverDelegate, TwoLineElideLabel,
)
from .table   import (
    setupPreviewTable,
    autoResizeTable,
    makeDeleteBtn,
    refreshDeleteBtns,
    setDocIdLinkCell,
    applyLinkStyle,
    LINK_COLOR,
    FIXED_COL_WIDTHS,
)

from .help_dialog import helpDialog, attachHelpButton
from .edit_dialog import TaskEditDialog, CriminalEditDialog, GeneralEditDialog
from .settings_dialogs import (
    PersonnelAddDialog, PersonnelEditDialog,
    DeptAddDialog, DeptEditDialog,
    CaseTypeAddDialog, CaseTypeEditDialog,
    ChangePasswordDialog, ResetDialog, ArchiveRootDialog, PrintTitleDialog,
)

__all__ = [
    "msgInfo", "msgWarning", "msgCritical", "confirmBox", "loadUi",
    "BTN_CONFIRM", "BTN_DANGER", "BTN_CANCEL",
    "calcOverdue",
    "colorForStatus",
    "attachStickyScroll",
    "setupFilterCombo",
    "refreshFilterCombo",
    "setupDateEditToToday",
    "setupDateEditCalendarOnly",
    "runWithBusy",
    "preserveScroll",
    "RowHoverFilter",
    "RowHoverDelegate",
    "TwoLineElideLabel",
    "setupPreviewTable",
    "autoResizeTable",
    "makeDeleteBtn",
    "refreshDeleteBtns",
    "setDocIdLinkCell",
    "applyLinkStyle",
    "LINK_COLOR",
    "helpDialog",
    "attachHelpButton",
    "TaskEditDialog",
    "CriminalEditDialog",
    "GeneralEditDialog",
    "FIXED_COL_WIDTHS",
    "PersonnelAddDialog", "PersonnelEditDialog",
    "DeptAddDialog", "DeptEditDialog",
    "CaseTypeAddDialog", "CaseTypeEditDialog",
    "ChangePasswordDialog", "ResetDialog", "ArchiveRootDialog", "PrintTitleDialog",
]
