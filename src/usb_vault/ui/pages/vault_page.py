"""Unlocked vault file explorer page, with real folder navigation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
)
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

from usb_vault.core.vault.manifest import FOLDER_MARKER_NAME
from usb_vault.core.vault.operations import VaultEntrySummary
from usb_vault.ui.components import (
    SPACE_1,
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


class _RowItem(QTableWidgetItem):
    """A table cell that keeps folders sorted ahead of files."""

    def __init__(
        self,
        text: str,
        *,
        is_folder: bool,
        icon: QIcon | None = None,
    ) -> None:
        if icon is not None:
            super().__init__(icon, text)
        else:
            super().__init__(text)

        self.is_folder = is_folder

    def __lt__(self, other: QTableWidgetItem) -> bool:
        # Deliberately does not call super().__lt__(): PySide6's virtual dispatch
        # re-enters this same override for QTableWidgetItem subclasses and recurses
        # forever, so the comparison is implemented directly instead.
        if isinstance(other, _RowItem) and self.is_folder != other.is_folder:
            return self.is_folder

        self_value = self.data(Qt.ItemDataRole.UserRole)
        other_value = other.data(Qt.ItemDataRole.UserRole)

        if isinstance(self_value, (int, float)) and isinstance(other_value, (int, float)):
            return self_value < other_value

        return self.text() < other.text()


_ENTRY_MIME_TYPE = "application/x-usb-vault-entry"


def _encode_drag_payload(kind: str, identifier: str) -> QMimeData:
    mime = QMimeData()
    mime.setData(_ENTRY_MIME_TYPE, f"{kind}:{identifier}".encode())
    return mime


def _decode_drag_payload(mime: QMimeData) -> tuple[str, str] | None:
    if not mime.hasFormat(_ENTRY_MIME_TYPE):
        return None

    raw = bytes(mime.data(_ENTRY_MIME_TYPE).data()).decode("utf-8", errors="strict")
    kind, separator, identifier = raw.partition(":")

    if not separator or kind not in {"file", "folder"} or not identifier:
        return None

    return (kind, identifier)


class _ExplorerTable(QTableWidget):
    """A file table that can drag rows onto folder rows to move entries."""

    entry_dropped = Signal(str, str, str)

    def __init__(self, rows: int, columns: int, parent: QWidget | None = None) -> None:
        super().__init__(rows, columns, parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        del supportedActions
        name_item = self.item(self.currentRow(), 0)
        data = name_item.data(Qt.ItemDataRole.UserRole) if name_item is not None else None

        if not isinstance(data, tuple) or len(data) != 2:
            return

        kind, identifier = data
        drag = QDrag(self)
        drag.setMimeData(_encode_drag_payload(kind, identifier))
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _decode_drag_payload(event.mimeData()) is not None:
            event.acceptProposedAction()
            return

        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        target = self._folder_target_at(event.position().toPoint())

        if target is not None and _decode_drag_payload(event.mimeData()) is not None:
            event.acceptProposedAction()
            return

        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        payload = _decode_drag_payload(event.mimeData())
        target = self._folder_target_at(event.position().toPoint())

        if payload is None or target is None:
            event.ignore()
            return

        kind, identifier = payload

        if identifier == target:
            event.ignore()
            return

        event.acceptProposedAction()
        self.entry_dropped.emit(kind, identifier, target)

    def _folder_target_at(self, point: QPoint) -> str | None:
        item = self.itemAt(point)

        if item is None:
            return None

        name_item = self.item(item.row(), 0)
        data = name_item.data(Qt.ItemDataRole.UserRole) if name_item is not None else None

        if isinstance(data, tuple) and len(data) == 2 and data[0] == "folder":
            return str(data[1])

        return None


class _BreadcrumbButton(QPushButton):
    """A breadcrumb segment that accepts a dropped file or folder row."""

    entry_dropped = Signal(str, str)

    def __init__(self, label: str, target_path: str) -> None:
        super().__init__(label)
        self._target_path = target_path
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _decode_drag_payload(event.mimeData()) is not None:
            event.acceptProposedAction()
            return

        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if _decode_drag_payload(event.mimeData()) is not None:
            event.acceptProposedAction()
            return

        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        payload = _decode_drag_payload(event.mimeData())

        if payload is None:
            event.ignore()
            return

        kind, identifier = payload

        if identifier == self._target_path:
            event.ignore()
            return

        event.acceptProposedAction()
        self.entry_dropped.emit(kind, identifier)


class VaultPage(ResponsivePage):
    """Display encrypted entries as a navigable folder tree."""

    add_requested = Signal()
    extract_requested = Signal(str)
    delete_requested = Signal(str)
    create_folder_requested = Signal()
    delete_folder_requested = Signal(str)
    move_requested = Signal(str, str)
    move_folder_requested = Signal(str, str)
    lock_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("vaultPage", parent=parent)

        self._entries: tuple[VaultEntrySummary, ...] = ()
        self._path: tuple[str, ...] = ()
        self._root_label = "Files"

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

        self.breadcrumb_bar = QWidget()
        self.breadcrumb_bar.setObjectName("breadcrumbBar")
        self._breadcrumb_layout = QHBoxLayout(self.breadcrumb_bar)
        self._breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self._breadcrumb_layout.setSpacing(SPACE_1)

        self.table = _ExplorerTable(0, 3)
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
        self.new_folder_button = QPushButton("New folder")
        self.new_folder_button.setObjectName("newFolderButton")
        self.new_folder_button.setIcon(app_icon("folder"))
        self.new_folder_button.clicked.connect(self.create_folder_requested.emit)
        self.extract_button = QPushButton("Export")
        self.extract_button.setObjectName("extractFileButton")
        self.extract_button.setIcon(app_icon("download"))
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self._emit_extract)
        self.delete_button = QPushButton("Delete file")
        self.delete_button.setObjectName("deleteFileButton")
        self.delete_button.setIcon(app_icon("trash", "#f199a1"))
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip("Permanently remove the selected encrypted item")
        self.delete_button.clicked.connect(self._emit_delete)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("vaultSearchEdit")
        self.search_edit.setPlaceholderText("Search this folder")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(280)
        self.search_edit.addAction(app_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.textChanged.connect(self._filter_rows)
        self.search_edit.hide()

        self.selection_label = QLabel()
        self.selection_label.setObjectName("selectionStatus")
        self.selection_label.hide()
        self.entry_count_label = QLabel("0 items")
        self.entry_count_label.setObjectName("vaultEntryCount")

        toolbar = QFrame()
        toolbar.setObjectName("toolbarSurface")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        toolbar_layout.setSpacing(SPACE_2)
        toolbar_layout.addWidget(self.add_button)
        toolbar_layout.addWidget(self.new_folder_button)
        toolbar_layout.addWidget(self.extract_button)
        toolbar_layout.addWidget(self.delete_button)
        toolbar_layout.addWidget(self.selection_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.search_edit)
        toolbar_layout.addWidget(self.entry_count_label)

        self.empty_icon = QLabel()
        self.empty_icon.setPixmap(app_icon("file", "#61d7c5").pixmap(44, 44))
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel("This vault is empty")
        self.empty_title.setObjectName("emptyStateTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_description = QLabel(
            "Add files or create a folder to start organizing this vault."
        )
        self.empty_description.setObjectName("emptyStateDescription")
        self.empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_description.setWordWrap(True)
        empty_add = QPushButton("Add files")
        empty_add.setObjectName("primaryButton")
        empty_add.setIcon(app_icon("plus", "#09201f"))
        empty_add.clicked.connect(self.add_requested.emit)
        empty_new_folder = QPushButton("New folder")
        empty_new_folder.setIcon(app_icon("folder"))
        empty_new_folder.clicked.connect(self.create_folder_requested.emit)
        empty_actions = QHBoxLayout()
        empty_actions.addStretch()
        empty_actions.addWidget(empty_add)
        empty_actions.addWidget(empty_new_folder)
        empty_actions.addStretch()

        empty_state = QFrame()
        empty_state.setObjectName("emptyState")
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setContentsMargins(SPACE_8, SPACE_8, SPACE_8, SPACE_8)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(SPACE_3)
        empty_layout.addWidget(self.empty_icon)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_description)
        empty_layout.addSpacing(SPACE_2)
        empty_layout.addLayout(empty_actions)

        table_panel = QWidget()
        table_panel_layout = QVBoxLayout(table_panel)
        table_panel_layout.setContentsMargins(0, 0, 0, 0)
        table_panel_layout.setSpacing(SPACE_2)
        table_panel_layout.addWidget(self.table)
        drop_hint = QLabel("Drop files anywhere in this window to add them securely")
        drop_hint.setObjectName("formHelp")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_panel_layout.addWidget(drop_hint)
        table_panel_layout.addStretch()

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
        self.content_layout.addWidget(self.breadcrumb_bar)
        self.content_layout.addWidget(toolbar)
        self.content_layout.addWidget(table_surface, 1)

        self.table.itemSelectionChanged.connect(self._update_selection_actions)
        self.table.itemDoubleClicked.connect(self._on_row_activated)
        self.table.entry_dropped.connect(self._handle_drop)

        self._render_current_level()

    @property
    def root_label(self) -> str:
        """Return the display name shown for the vault root in the breadcrumb."""
        return self._root_label

    @property
    def current_folder(self) -> str:
        """Return the '/'-delimited path of the folder currently open."""
        return "/".join(self._path)

    def set_vault_path(self, vault_path: str) -> None:
        display_path = Path(vault_path)
        self._root_label = display_path.stem or "Files"
        self._path = ()
        self.header.set_title(self._root_label)
        self.header.set_description("Encrypted files in this unlocked vault.")
        self.header.set_context(vault_path)
        self._render_current_level()

    def set_entries(self, entries: Sequence[VaultEntrySummary]) -> None:
        self._entries = tuple(entries)
        self._ensure_valid_path()
        self._render_current_level()

    def clear_entries(self) -> None:
        self._entries = ()
        self._path = ()
        self._root_label = "Files"
        self.header.set_title("Files")
        self.header.set_context("")
        self._render_current_level()

    def selected_name(self) -> str | None:
        """Return the selected FILE's full stored name, or None."""
        kind, value = self._selected_row()
        return value if kind == "file" else None

    def selected_folder_path(self) -> str | None:
        """Return the selected folder's full path, or None."""
        kind, value = self._selected_row()
        return value if kind == "folder" else None

    def _render_current_level(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        folder_names, files = self._current_level()

        for folder_name in folder_names:
            full_path = "/".join((*self._path, folder_name))
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_count = self._folder_item_count(full_path)
            noun = "item" if item_count == 1 else "items"

            name_item = _RowItem(
                folder_name,
                is_folder=True,
                icon=app_icon("folder", "#61d7c5"),
            )
            name_item.setData(Qt.ItemDataRole.UserRole, ("folder", full_path))
            size_item = _RowItem(f"{item_count} {noun}", is_folder=True)
            size_item.setData(Qt.ItemDataRole.UserRole, item_count)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            type_item = _RowItem("Folder", is_folder=True)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, size_item)
            self.table.setItem(row, 2, type_item)

        for entry in files:
            display_name = entry.name.rsplit("/", 1)[-1]
            row = self.table.rowCount()
            self.table.insertRow(row)
            file_type, icon_name = _file_type(display_name)

            name_item = _RowItem(
                display_name,
                is_folder=False,
                icon=app_icon(icon_name, "#9fb4cc"),
            )
            name_item.setData(Qt.ItemDataRole.UserRole, ("file", entry.name))
            size_item = _RowItem(format_file_size(entry.size), is_folder=False)
            size_item.setData(Qt.ItemDataRole.UserRole, entry.size)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            type_item = _RowItem(file_type, is_folder=False)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, size_item)
            self.table.setItem(row, 2, type_item)

        self.table.setSortingEnabled(True)
        self.table.clearSelection()

        row_count = self.table.rowCount()
        folder_count = len(folder_names)
        file_count = len(files)
        self.entry_count_label.setText(_count_label(folder_count, file_count))
        self.search_edit.setVisible(row_count >= 10)
        self.search_edit.clear()
        self.content_stack.setCurrentIndex(1 if row_count else 0)
        self.table.setFixedHeight(min(420, max(200, 42 + row_count * 44)))

        if self._path:
            self.empty_title.setText("This folder is empty")
            self.empty_description.setText(
                "Add files or create another folder inside this one."
            )
        else:
            self.empty_title.setText("This vault is empty")
            self.empty_description.setText(
                "Add files or create a folder to start organizing this vault."
            )

        self._rebuild_breadcrumb()
        self._update_selection_actions()

    def _current_level(
        self,
    ) -> tuple[list[str], list[VaultEntrySummary]]:
        prefix = self.current_folder
        prefix_slash = f"{prefix}/" if prefix else ""
        folder_names: dict[str, None] = {}
        files: list[VaultEntrySummary] = []

        for entry in self._entries:
            if prefix_slash:
                if not entry.name.startswith(prefix_slash):
                    continue
                relative = entry.name[len(prefix_slash) :]
            else:
                relative = entry.name

            segments = relative.split("/")

            if len(segments) > 1:
                folder_names.setdefault(segments[0], None)
            elif relative != FOLDER_MARKER_NAME:
                files.append(entry)

        return (
            sorted(folder_names, key=str.casefold),
            sorted(files, key=lambda entry: entry.name.casefold()),
        )

    def _folder_item_count(self, folder_path: str) -> int:
        prefix = f"{folder_path}/"
        return sum(
            1
            for entry in self._entries
            if entry.name.startswith(prefix) and not entry.name.endswith(f"/{FOLDER_MARKER_NAME}")
        )

    def _path_exists(self, path: tuple[str, ...]) -> bool:
        prefix = "/".join(path)
        prefix_slash = f"{prefix}/"
        marker = f"{prefix}/{FOLDER_MARKER_NAME}"

        return any(
            entry.name == marker or entry.name.startswith(prefix_slash) for entry in self._entries
        )

    def _ensure_valid_path(self) -> None:
        while self._path and not self._path_exists(self._path):
            self._path = self._path[:-1]

    def _rebuild_breadcrumb(self) -> None:
        while self._breadcrumb_layout.count():
            item = self._breadcrumb_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        self._add_breadcrumb_segment(self._root_label, ())

        for index in range(len(self._path)):
            chevron = QLabel()
            chevron.setPixmap(app_icon("chevron_right", "#5a6f89").pixmap(12, 12))
            self._breadcrumb_layout.addWidget(chevron)
            self._add_breadcrumb_segment(self._path[index], self._path[: index + 1])

        self._breadcrumb_layout.addStretch()

    def _add_breadcrumb_segment(
        self,
        label: str,
        path: tuple[str, ...],
    ) -> None:
        is_current = path == self._path
        target_path = "/".join(path)
        button = _BreadcrumbButton(label, target_path)
        button.setObjectName("breadcrumbCurrent" if is_current else "breadcrumbLink")
        button.setFlat(True)
        button.setEnabled(not is_current)
        button.setCursor(
            Qt.CursorShape.ArrowCursor if is_current else Qt.CursorShape.PointingHandCursor
        )
        button.clicked.connect(lambda _checked=False, target=path: self._navigate_to(target))
        button.entry_dropped.connect(
            lambda kind, identifier, target=target_path: self._handle_drop(
                kind, identifier, target
            )
        )
        self._breadcrumb_layout.addWidget(button)

    def _navigate_to(self, path: tuple[str, ...]) -> None:
        self._path = path
        self._render_current_level()

    def _on_row_activated(self, item: QTableWidgetItem) -> None:
        name_item = self.table.item(item.row(), 0)
        data = name_item.data(Qt.ItemDataRole.UserRole) if name_item is not None else None

        if isinstance(data, tuple) and len(data) == 2 and data[0] == "folder":
            self._navigate_to(tuple(data[1].split("/")))
            return

        self._emit_extract()

    def _selected_row(self) -> tuple[str | None, str | None]:
        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows:
            return (None, None)

        item = self.table.item(selected_rows[0].row(), 0)

        if item is None:
            return (None, None)

        data = item.data(Qt.ItemDataRole.UserRole)

        if not isinstance(data, tuple) or len(data) != 2:
            return (None, None)

        return data

    def _update_selection_actions(self) -> None:
        kind, value = self._selected_row()
        is_file = kind == "file"
        is_folder = kind == "folder"

        self.extract_button.setEnabled(is_file)
        self.delete_button.setEnabled(is_file or is_folder)
        self.delete_button.setText("Delete folder" if is_folder else "Delete file")

        if is_file:
            self.selection_label.setText(f"Selected: {value}")
        elif is_folder and value is not None:
            self.selection_label.setText(f"Selected: {value.rsplit('/', 1)[-1]} (folder)")
        else:
            self.selection_label.setText("")

        self.selection_label.setVisible(is_file or is_folder)

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
        kind, value = self._selected_row()
        if kind == "file" and value is not None:
            self.delete_requested.emit(value)
        elif kind == "folder" and value is not None:
            self.delete_folder_requested.emit(value)

    def _handle_drop(
        self,
        kind: str,
        identifier: str,
        target_folder_path: str,
    ) -> None:
        """Translate a dropped file or folder into a move request."""
        if kind == "file":
            leaf_name = identifier.rsplit("/", 1)[-1]
            new_name = f"{target_folder_path}/{leaf_name}" if target_folder_path else leaf_name

            if new_name == identifier:
                return

            self.move_requested.emit(identifier, new_name)
        elif kind == "folder":
            if target_folder_path == identifier or f"{target_folder_path}/".startswith(
                f"{identifier}/"
            ):
                return

            self.move_folder_requested.emit(identifier, target_folder_path)


def _count_label(folder_count: int, file_count: int) -> str:
    parts: list[str] = []

    if folder_count:
        parts.append(f"{folder_count} folder{'s' if folder_count != 1 else ''}")

    if file_count or not parts:
        parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")

    return ", ".join(parts)


def _file_type(name: str) -> tuple[str, str]:
    suffix = Path(name).suffix.casefold()
    if suffix == ".pdf":
        return "PDF", "pdf"
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}:
        return "Image", "image"
    if suffix in {".txt", ".md", ".rtf", ".log"}:
        return "Text", "text"
    return (suffix[1:].upper() if suffix else "File"), "file"
