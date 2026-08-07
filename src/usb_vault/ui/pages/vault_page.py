"""Unlocked vault file explorer page."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usb_vault.core.vault.operations import VaultEntrySummary
from usb_vault.ui.components import (
    SPACE_2,
    SPACE_3,
    SPACE_6,
    SPACE_8,
    PageHeader,
    ResponsivePage,
    StatusBadge,
)
from usb_vault.ui.formatting import format_file_size
from usb_vault.ui.icons import app_icon


class VaultPage(ResponsivePage):
    """Display encrypted entries and expose contextual vault actions."""

    add_requested = Signal()
    extract_requested = Signal(str)
    delete_requested = Signal(str)
    lock_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("vaultPage", parent=parent)

        self.header = PageHeader(
            "OPEN VAULT",
            "Files",
            "Encrypted files available in this vault.",
        )
        self.title = self.header.title_label
        self.vault_path_label = self.header.context_label

        self.security_badge = StatusBadge("Unlocked · USB authenticated", tone="success")
        self.lock_button = QPushButton("Lock vault")
        self.lock_button.setObjectName("lockVaultButton")
        self.lock_button.setIcon(app_icon("lock"))
        self.lock_button.setToolTip("Lock immediately and clear credentials (⌘L)")
        self.lock_button.clicked.connect(self.lock_requested.emit)
        self.header.add_action(self.security_badge)
        self.header.add_action(self.lock_button)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("vaultEntriesTable")
        self.table.setHorizontalHeaderLabels(("Name", "Size", "Type"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setMinimumHeight(200)
        self.table.setMaximumHeight(420)

        table_header = self.table.horizontalHeader()
        table_header.setFixedHeight(40)
        table_header.setSectionsClickable(True)
        table_header.setSortIndicatorShown(True)
        table_header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.add_button = QPushButton("Add files")
        self.add_button.setObjectName("addFileButton")
        self.add_button.setIcon(app_icon("plus", "#09201f"))
        self.add_button.clicked.connect(self.add_requested.emit)
        self.extract_button = QPushButton("Export")
        self.extract_button.setObjectName("extractFileButton")
        self.extract_button.setIcon(app_icon("download"))
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self._emit_extract)
        self.delete_button = QPushButton("Delete file")
        self.delete_button.setObjectName("deleteFileButton")
        self.delete_button.setIcon(app_icon("trash", "#f199a1"))
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip("Permanently remove the selected encrypted file")
        self.delete_button.clicked.connect(self._emit_delete)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("vaultSearchEdit")
        self.search_edit.setPlaceholderText("Search files")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(280)
        self.search_edit.addAction(app_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.textChanged.connect(self._filter_rows)
        self.search_edit.hide()

        self.selection_label = QLabel()
        self.selection_label.setObjectName("selectionStatus")
        self.selection_label.hide()
        self.entry_count_label = QLabel("0 files")
        self.entry_count_label.setObjectName("vaultEntryCount")

        toolbar = QFrame()
        toolbar.setObjectName("toolbarSurface")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        toolbar_layout.setSpacing(SPACE_2)
        toolbar_layout.addWidget(self.add_button)
        toolbar_layout.addWidget(self.extract_button)
        toolbar_layout.addWidget(self.delete_button)
        toolbar_layout.addWidget(self.selection_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.search_edit)
        toolbar_layout.addWidget(self.entry_count_label)

        empty_state = QFrame()
        empty_state.setObjectName("emptyState")
        empty_icon = QLabel()
        empty_icon.setPixmap(app_icon("file", "#61d7c5").pixmap(44, 44))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title = QLabel("This vault is empty")
        empty_title.setObjectName("emptyStateTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_description = QLabel("Add files or drop them here to encrypt them into this vault.")
        empty_description.setObjectName("emptyStateDescription")
        empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_description.setWordWrap(True)
        empty_add = QPushButton("Add files")
        empty_add.setObjectName("primaryButton")
        empty_add.setIcon(app_icon("plus", "#09201f"))
        empty_add.clicked.connect(self.add_requested.emit)
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setContentsMargins(SPACE_8, SPACE_8, SPACE_8, SPACE_8)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(SPACE_3)
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_description)
        empty_layout.addWidget(empty_add, 0, Qt.AlignmentFlag.AlignCenter)

        table_panel = QWidget()
        table_panel_layout = QVBoxLayout(table_panel)
        table_panel_layout.setContentsMargins(0, 0, 0, 0)
        table_panel_layout.setSpacing(SPACE_2)
        table_panel_layout.addWidget(self.table)
        drop_hint = QLabel("Drop files anywhere in this window to add them securely")
        drop_hint.setObjectName("formHelp")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_panel_layout.addWidget(drop_hint)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("vaultContentStack")
        self.content_stack.addWidget(empty_state)
        self.content_stack.addWidget(table_panel)

        table_surface = QFrame()
        table_surface.setObjectName("vaultSurface")
        table_layout = QVBoxLayout(table_surface)
        table_layout.setContentsMargins(SPACE_3, SPACE_3, SPACE_3, SPACE_3)
        table_layout.addWidget(self.content_stack)

        self.content_layout.setSpacing(SPACE_6)
        self.content_layout.addWidget(self.header)
        self.content_layout.addWidget(toolbar)
        self.content_layout.addWidget(table_surface)
        self.content_layout.addStretch()

        self.table.itemSelectionChanged.connect(self._update_selection_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self._emit_extract())

    def set_vault_path(self, vault_path: str) -> None:
        display_path = Path(vault_path)
        self.header.set_title(display_path.stem or "Files")
        self.header.set_description("Encrypted files in this unlocked vault.")
        self.header.set_context(vault_path)

    def set_entries(self, entries: Sequence[VaultEntrySummary]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            file_type, icon_name = _file_type(entry.name)
            name_item = QTableWidgetItem(app_icon(icon_name, "#9fb4cc"), entry.name)
            size_item = QTableWidgetItem(format_file_size(entry.size))
            size_item.setData(Qt.ItemDataRole.UserRole, entry.size)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            type_item = QTableWidgetItem(file_type)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, size_item)
            self.table.setItem(row, 2, type_item)

        self.table.setSortingEnabled(True)
        self.table.clearSelection()
        entry_count = self.table.rowCount()
        noun = "file" if entry_count == 1 else "files"
        self.entry_count_label.setText(f"{entry_count} {noun}")
        self.search_edit.setVisible(entry_count >= 10)
        self.search_edit.clear()
        self.content_stack.setCurrentIndex(1 if entry_count else 0)
        self.table.setFixedHeight(min(420, max(200, 42 + entry_count * 44)))
        self._update_selection_actions()

    def clear_entries(self) -> None:
        self.table.clearContents()
        self.table.setRowCount(0)
        self.header.set_title("Files")
        self.header.set_context("")
        self.entry_count_label.setText("0 files")
        self.search_edit.hide()
        self.content_stack.setCurrentIndex(0)
        self._update_selection_actions()

    def selected_name(self) -> str | None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        item = self.table.item(selected_rows[0].row(), 0)
        return item.text() if item is not None else None

    def _update_selection_actions(self) -> None:
        selected_name = self.selected_name()
        has_selection = selected_name is not None
        self.extract_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.selection_label.setText(f"Selected: {selected_name}" if selected_name else "")
        self.selection_label.setVisible(has_selection)

    def _filter_rows(self, query: str) -> None:
        normalized = query.strip().casefold()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            self.table.setRowHidden(
                row,
                bool(normalized) and (item is None or normalized not in item.text().casefold()),
            )

    def _emit_extract(self) -> None:
        selected_name = self.selected_name()
        if selected_name is not None:
            self.extract_requested.emit(selected_name)

    def _emit_delete(self) -> None:
        selected_name = self.selected_name()
        if selected_name is not None:
            self.delete_requested.emit(selected_name)


def _file_type(name: str) -> tuple[str, str]:
    suffix = Path(name).suffix.casefold()
    if suffix == ".pdf":
        return "PDF", "pdf"
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}:
        return "Image", "image"
    if suffix in {".txt", ".md", ".rtf", ".log"}:
        return "Text", "text"
    return (suffix[1:].upper() if suffix else "File"), "file"
