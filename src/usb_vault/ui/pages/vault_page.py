"""Unlocked vault browser page."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usb_vault.core.vault.operations import (
    VaultEntrySummary,
)
from usb_vault.ui.formatting import (
    format_file_size,
)


class VaultPage(QWidget):
    """Display encrypted entries and expose vault actions."""

    add_requested = Signal()
    extract_requested = Signal(str)
    delete_requested = Signal(str)
    lock_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("vaultPage")

        title = QLabel("USB Vault")
        title.setObjectName("vaultTitle")

        self.vault_path_label = QLabel()
        self.vault_path_label.setObjectName("openedVaultPathLabel")
        self.vault_path_label.setWordWrap(True)

        self.table = QTableWidget(
            0,
            2,
        )
        self.table.setObjectName("vaultEntriesTable")
        self.table.setHorizontalHeaderLabels(
            (
                "Name",
                "Size",
            )
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.add_button = QPushButton("Add File…")
        self.add_button.setObjectName("addFileButton")
        self.add_button.clicked.connect(self.add_requested.emit)

        self.extract_button = QPushButton("Export…")
        self.extract_button.setObjectName("extractFileButton")
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self._emit_extract)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("deleteFileButton")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._emit_delete)

        self.lock_button = QPushButton("Lock")
        self.lock_button.setObjectName("lockVaultButton")
        self.lock_button.clicked.connect(self.lock_requested.emit)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.extract_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(self.lock_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.vault_path_label)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.table.itemSelectionChanged.connect(self._update_selection_actions)

    def set_vault_path(
        self,
        vault_path: str,
    ) -> None:
        """Display the currently opened vault path."""
        self.vault_path_label.setText(vault_path)

    def set_entries(
        self,
        entries: Sequence[VaultEntrySummary],
    ) -> None:
        """Replace the entry table contents."""
        self.table.setRowCount(0)

        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(entry.name)
            size_item = QTableWidgetItem(format_file_size(entry.size))

            self.table.setItem(
                row,
                0,
                name_item,
            )
            self.table.setItem(
                row,
                1,
                size_item,
            )

        self.table.clearSelection()
        self._update_selection_actions()

    def clear_entries(self) -> None:
        """Remove all unlocked metadata from the view."""
        self.table.clearContents()
        self.table.setRowCount(0)
        self.vault_path_label.clear()
        self._update_selection_actions()

    def selected_name(self) -> str | None:
        """Return the selected stored filename."""
        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows:
            return None

        row = selected_rows[0].row()
        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return None

        return item.text()

    def _update_selection_actions(
        self,
    ) -> None:
        has_selection = self.selected_name() is not None
        self.extract_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _emit_extract(self) -> None:
        selected_name = self.selected_name()

        if selected_name is not None:
            self.extract_requested.emit(selected_name)

    def _emit_delete(self) -> None:
        selected_name = self.selected_name()

        if selected_name is not None:
            self.delete_requested.emit(selected_name)
