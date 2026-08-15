"""Card-based home screen for known encrypted vaults."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.components import (
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
    SPACE_8,
    ElidedLabel,
    PageHeader,
    ResponsivePage,
    StatusBadge,
)
from usb_vault.ui.icons import app_icon
from usb_vault.ui.vault_library import VaultLibraryEntry


class VaultCard(QFrame):
    """One compact, fully clickable known-vault card."""

    open_requested = Signal(bytes)
    rename_requested = Signal(bytes)
    remove_requested = Signal(bytes)

    def __init__(
        self,
        entry: VaultLibraryEntry,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(entry, VaultLibraryEntry):
            raise TypeError("entry must be VaultLibraryEntry")

        super().__init__(parent)
        self._entry = entry
        self.setObjectName("vaultCard")
        self.setProperty("available", entry.is_available)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if entry.is_available else Qt.CursorShape.ArrowCursor
        )

        icon_label = QLabel()
        icon_label.setPixmap(app_icon("lock", "#d2d2d2").pixmap(22, 22))

        title = QLabel(entry.display_name)
        title.setObjectName("vaultCardTitle")

        self.menu_button = QToolButton()
        self.menu_button.setObjectName("vaultCardMenuButton")
        self.menu_button.setIcon(app_icon("more"))
        self.menu_button.setIconSize(QSize(18, 18))
        self.menu_button.setToolTip("Vault card actions")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(self.menu_button)
        self.rename_action = QAction(app_icon("edit"), "Rename", menu)
        self.remove_action = QAction(app_icon("trash", "#f199a1"), "Remove from list", menu)
        self.rename_action.triggered.connect(self._emit_rename)
        self.remove_action.triggered.connect(self._emit_remove)
        menu.addAction(self.rename_action)
        menu.addSeparator()
        menu.addAction(self.remove_action)
        self.menu_button.setMenu(menu)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(SPACE_2)
        header.addWidget(icon_label)
        header.addWidget(title, 1)
        header.addWidget(self.menu_button)

        status_text = "Available" if entry.is_available else "Vault file unavailable"
        self.status_badge = StatusBadge(
            status_text,
            tone="success" if entry.is_available else "warning",
        )

        self.path_label = ElidedLabel(str(entry.vault_path))
        self.path_label.setObjectName("vaultCardPath")

        metadata = QLabel(f"Last opened {_format_last_opened(entry.last_opened_at)}")
        metadata.setObjectName("vaultCardMeta")

        security_hint = ElidedLabel("Password + registered USB key required")
        security_hint.setObjectName("vaultCardHint")

        self.open_button = QPushButton("Open vault")
        self.open_button.setObjectName("ghostButton")
        self.open_button.setIcon(app_icon("chevron_right"))
        self.open_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.open_button.setEnabled(entry.is_available)
        self.open_button.clicked.connect(self._emit_open)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(security_hint, 1)
        footer.addWidget(self.open_button, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_4, SPACE_6, SPACE_4)
        layout.setSpacing(SPACE_3)
        layout.addLayout(header)
        layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.path_label)
        layout.addWidget(metadata)
        layout.addLayout(footer)

    @property
    def entry(self) -> VaultLibraryEntry:
        return self._entry

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        clicked_widget = self.childAt(event.position().toPoint())
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._entry.is_available
            and clicked_widget not in {self.open_button, self.menu_button}
        ):
            self._emit_open()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._entry.is_available:
            self._emit_open()
            event.accept()
            return
        super().keyPressEvent(event)

    def _emit_open(self) -> None:
        self.open_requested.emit(self._entry.vault_id)

    def _emit_rename(self) -> None:
        self.rename_requested.emit(self._entry.vault_id)

    def _emit_remove(self) -> None:
        self.remove_requested.emit(self._entry.vault_id)


class VaultLibraryPage(ResponsivePage):
    """Display and manage locally registered vault cards."""

    create_requested = Signal()
    add_existing_requested = Signal()
    refresh_requested = Signal()
    open_requested = Signal(bytes)
    rename_requested = Signal(bytes)
    remove_requested = Signal(bytes)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("vaultLibraryPage", parent=parent)

        self._entries: tuple[VaultLibraryEntry, ...] = ()
        self._cards: dict[bytes, VaultCard] = {}

        header = PageHeader(
            "KEYHOLD",
            "Your vaults",
            "Choose a vault, enter its password, then authenticate with a registered USB key.",
        )

        self.create_button = QPushButton("Create vault")
        self.create_button.setObjectName("createVaultFromLibraryButton")
        self.create_button.setIcon(app_icon("plus", "#181818"))
        self.create_button.clicked.connect(self.create_requested.emit)

        self.add_existing_button = QPushButton("Add existing vault")
        self.add_existing_button.setObjectName("addExistingVaultButton")
        self.add_existing_button.setIcon(app_icon("folder"))
        self.add_existing_button.clicked.connect(self.add_existing_requested.emit)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshVaultLibraryButton")
        self.refresh_button.setIcon(app_icon("refresh"))
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        toolbar = QFrame()
        toolbar.setObjectName("toolbarSurface")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        toolbar_layout.setSpacing(SPACE_2)
        toolbar_layout.addWidget(self.create_button)
        toolbar_layout.addWidget(self.add_existing_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.refresh_button)

        self.error_label = QLabel()
        self.error_label.setObjectName("vaultLibraryErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self._cards_widget = QWidget()
        self._cards_widget.setObjectName("vaultCardsContainer")
        self._cards_layout = QGridLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setHorizontalSpacing(SPACE_4)
        self._cards_layout.setVerticalSpacing(SPACE_4)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("vaultLibraryScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self._cards_widget)

        self.content_layout.setSpacing(SPACE_6)
        self.content_layout.addWidget(header)
        self.content_layout.addWidget(toolbar)
        self.content_layout.addWidget(self.error_label)
        self.content_layout.addWidget(scroll_area, 1)
        self.set_entries(())

    @property
    def entries(self) -> tuple[VaultLibraryEntry, ...]:
        return self._entries

    def card_for_vault_id(self, vault_id: bytes) -> VaultCard | None:
        if not isinstance(vault_id, bytes):
            raise TypeError("vault_id must be bytes")
        return self._cards.get(vault_id)

    def set_entries(self, entries: Sequence[VaultLibraryEntry]) -> None:
        normalized_entries = tuple(entries)
        if not all(isinstance(entry, VaultLibraryEntry) for entry in normalized_entries):
            raise TypeError("every entry must be VaultLibraryEntry")

        self._clear_cards()
        self._entries = normalized_entries

        if not normalized_entries:
            empty_state = QFrame()
            empty_state.setObjectName("emptyState")
            empty_state.setMaximumWidth(620)

            empty_icon = QLabel()
            empty_icon.setPixmap(app_icon("folder", "#bdbdbd").pixmap(40, 40))
            empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_title = QLabel("Your encrypted space starts here")
            empty_title.setObjectName("emptyStateTitle")
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_description = QLabel(
                "Create a new vault, or add an encrypted vault that already exists on this Mac."
            )
            empty_description.setObjectName("emptyStateDescription")
            empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_description.setWordWrap(True)

            empty_create = QPushButton("Create vault")
            empty_create.setObjectName("primaryButton")
            empty_create.setIcon(app_icon("plus", "#181818"))
            empty_create.clicked.connect(self.create_requested.emit)
            empty_add = QPushButton("Add existing vault")
            empty_add.setIcon(app_icon("folder"))
            empty_add.clicked.connect(self.add_existing_requested.emit)
            empty_actions = QHBoxLayout()
            empty_actions.addStretch()
            empty_actions.addWidget(empty_create)
            empty_actions.addWidget(empty_add)
            empty_actions.addStretch()

            empty_layout = QVBoxLayout(empty_state)
            empty_layout.setContentsMargins(SPACE_8, SPACE_8, SPACE_8, SPACE_8)
            empty_layout.setSpacing(SPACE_3)
            empty_layout.addWidget(empty_icon)
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_description)
            empty_layout.addSpacing(SPACE_2)
            empty_layout.addLayout(empty_actions)

            legacy_empty_label = QLabel()
            legacy_empty_label.setObjectName("emptyVaultLibraryLabel")
            legacy_empty_label.hide()
            empty_layout.addWidget(legacy_empty_label)

            self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cards_layout.addWidget(empty_state, 0, 0, 1, 3)
            return

        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for index, entry in enumerate(normalized_entries):
            card = VaultCard(entry)
            card.open_requested.connect(self._forward_open)
            card.rename_requested.connect(self._forward_rename)
            card.remove_requested.connect(self._forward_remove)
            self._cards[entry.vault_id] = card
            self._cards_layout.addWidget(card, index // 3, index % 3)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message.strip() or "Unable to update the vault library.")
        self.error_label.show()

    def clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def _clear_cards(self) -> None:
        self._cards.clear()
        while self._cards_layout.count() > 0:
            item = self._cards_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _forward_open(self, vault_id: bytes) -> None:
        self.open_requested.emit(vault_id)

    def _forward_rename(self, vault_id: bytes) -> None:
        self.rename_requested.emit(vault_id)

    def _forward_remove(self, vault_id: bytes) -> None:
        self.remove_requested.emit(vault_id)


def _format_last_opened(value: datetime) -> str:
    local_value = value.astimezone()
    return local_value.strftime("%b %-d, %Y · %-I:%M %p")
