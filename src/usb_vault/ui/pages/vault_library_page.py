"""Card-based home screen for known encrypted vaults."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import (
    QSize,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from usb_vault.ui.icons import app_icon
from usb_vault.ui.vault_library import (
    VaultLibraryEntry,
)


class VaultCard(QFrame):
    """One clickable known-vault card."""

    open_requested = Signal(bytes)
    rename_requested = Signal(bytes)
    remove_requested = Signal(bytes)

    def __init__(
        self,
        entry: VaultLibraryEntry,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(
            entry,
            VaultLibraryEntry,
        ):
            raise TypeError("entry must be VaultLibraryEntry")

        super().__init__(parent)

        self._entry = entry

        self.setObjectName("vaultCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setProperty("available", entry.is_available)

        availability_text = (
            "Available" if entry.is_available else ("Unavailable — vault file not found")
        )

        self.open_button = QPushButton(entry.display_name)
        self.open_button.setObjectName("openVaultCardButton")
        self.open_button.setIcon(app_icon("lock", "#70e1d0"))
        self.open_button.setIconSize(QSize(20, 20))
        self.open_button.setEnabled(entry.is_available)
        self.open_button.clicked.connect(self._emit_open)

        status = QLabel(availability_text)
        status.setObjectName("vaultCardStatus")
        status.setProperty("available", entry.is_available)

        metadata = QLabel(
            f"{entry.vault_path}\nLast opened {_format_last_opened(entry.last_opened_at)}"
        )
        metadata.setObjectName("vaultCardMeta")
        metadata.setWordWrap(True)

        self.rename_button = QPushButton("Rename")
        self.rename_button.setObjectName("renameVaultCardButton")
        self.rename_button.setIcon(app_icon("edit"))
        self.rename_button.clicked.connect(self._emit_rename)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("removeVaultCardButton")
        self.remove_button.setIcon(app_icon("trash", "#ffb2b2"))
        self.remove_button.clicked.connect(self._emit_remove)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self.rename_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 17, 18, 15)
        layout.setSpacing(8)
        layout.addWidget(self.open_button)
        layout.addWidget(status)
        layout.addWidget(metadata)
        layout.addSpacing(4)
        layout.addLayout(actions)

    @property
    def entry(
        self,
    ) -> VaultLibraryEntry:
        """Return the registry entry displayed by this card."""
        return self._entry

    def _emit_open(self) -> None:
        self.open_requested.emit(self._entry.vault_id)

    def _emit_rename(self) -> None:
        self.rename_requested.emit(self._entry.vault_id)

    def _emit_remove(self) -> None:
        self.remove_requested.emit(self._entry.vault_id)


class VaultLibraryPage(QWidget):
    """Display and manage locally registered vault cards."""

    create_requested = Signal()
    add_existing_requested = Signal()
    refresh_requested = Signal()

    open_requested = Signal(bytes)
    rename_requested = Signal(bytes)
    remove_requested = Signal(bytes)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("vaultLibraryPage")

        self._entries: tuple[
            VaultLibraryEntry,
            ...,
        ] = ()
        self._cards: dict[
            bytes,
            VaultCard,
        ] = {}

        eyebrow = QLabel("USB VAULT")
        eyebrow.setObjectName("vaultLibraryEyebrow")

        title = QLabel("Your vaults")
        title.setObjectName("vaultLibraryTitle")

        subtitle = QLabel(
            "Choose a vault to enter its password. Your registered USB key completes the unlock."
        )
        subtitle.setObjectName("vaultLibrarySubtitle")
        subtitle.setWordWrap(True)

        self.create_button = QPushButton("Create vault")
        self.create_button.setObjectName("createVaultFromLibraryButton")
        self.create_button.setIcon(app_icon("plus", "#09201f"))
        self.create_button.clicked.connect(self.create_requested.emit)

        self.add_existing_button = QPushButton("Add existing vault")
        self.add_existing_button.setObjectName("addExistingVaultButton")
        self.add_existing_button.setIcon(app_icon("folder"))
        self.add_existing_button.clicked.connect(self.add_existing_requested.emit)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshVaultLibraryButton")
        self.refresh_button.setIcon(app_icon("refresh"))
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        actions = QHBoxLayout()
        actions.addWidget(self.create_button)
        actions.addWidget(self.add_existing_button)
        actions.addStretch()
        actions.addWidget(self.refresh_button)

        self.error_label = QLabel()
        self.error_label.setObjectName("vaultLibraryErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self._cards_widget = QWidget()
        self._cards_widget.setObjectName("vaultCardsContainer")

        self._cards_layout = QGridLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self._cards_layout.setHorizontalSpacing(14)
        self._cards_layout.setVerticalSpacing(14)
        self._cards_layout.setColumnStretch(0, 1)
        self._cards_layout.setColumnStretch(1, 1)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("vaultLibraryScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self._cards_widget)
        scroll_area.viewport().setStyleSheet("background: #0b1220;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 28)
        layout.setSpacing(8)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addLayout(actions)
        layout.addWidget(self.error_label)
        layout.addWidget(scroll_area)

        self.set_entries(())

    @property
    def entries(
        self,
    ) -> tuple[
        VaultLibraryEntry,
        ...,
    ]:
        """Return the entries currently displayed."""
        return self._entries

    def card_for_vault_id(
        self,
        vault_id: bytes,
    ) -> VaultCard | None:
        """Return one displayed card by public vault ID."""
        if not isinstance(
            vault_id,
            bytes,
        ):
            raise TypeError("vault_id must be bytes")

        return self._cards.get(vault_id)

    def set_entries(
        self,
        entries: Sequence[VaultLibraryEntry],
    ) -> None:
        """Replace the displayed library cards."""
        normalized_entries = tuple(entries)

        if not all(
            isinstance(
                entry,
                VaultLibraryEntry,
            )
            for entry in normalized_entries
        ):
            raise TypeError("every entry must be VaultLibraryEntry")

        self._clear_cards()
        self._entries = normalized_entries

        if not normalized_entries:
            empty_state = QFrame()
            empty_state.setObjectName("emptyState")
            empty_state.setMaximumHeight(230)

            empty_icon = QLabel()
            empty_icon.setPixmap(app_icon("folder", "#61d7c5").pixmap(42, 42))
            empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            empty_title = QLabel("Your encrypted space starts here")
            empty_title.setObjectName("emptyStateTitle")
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

            empty_description = QLabel(
                "Create a new vault, or add one that already exists on this Mac."
            )
            empty_description.setObjectName("emptyStateDescription")
            empty_description.setWordWrap(True)
            empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)

            empty_layout = QVBoxLayout(empty_state)
            empty_layout.setContentsMargins(28, 30, 28, 30)
            empty_layout.setSpacing(9)
            empty_layout.addWidget(empty_icon)
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_description)

            legacy_empty_label = QLabel()
            legacy_empty_label.setObjectName("emptyVaultLibraryLabel")
            legacy_empty_label.hide()
            empty_layout.addWidget(legacy_empty_label)

            self._cards_layout.addWidget(empty_state, 0, 0, 1, 2)
            self._cards_layout.setRowStretch(1, 1)
            return

        for index, entry in enumerate(normalized_entries):
            card = VaultCard(entry)
            card.open_requested.connect(self._forward_open)
            card.rename_requested.connect(self._forward_rename)
            card.remove_requested.connect(self._forward_remove)

            self._cards[entry.vault_id] = card
            self._cards_layout.addWidget(card, index // 2, index % 2)

        self._cards_layout.setRowStretch((len(normalized_entries) + 1) // 2, 1)

    def show_error(
        self,
        message: str,
    ) -> None:
        """Show a library loading or mutation error."""
        normalized_message = message.strip()

        if not normalized_message:
            normalized_message = "Unable to update the vault library."

        self.error_label.setText(normalized_message)
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear the current library error."""
        self.error_label.clear()
        self.error_label.hide()

    def _clear_cards(self) -> None:
        self._cards.clear()

        while self._cards_layout.count() > 0:
            item = self._cards_layout.takeAt(0)
            if item is None:
                continue

            widget = item.widget()

            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _forward_open(
        self,
        vault_id: bytes,
    ) -> None:
        self.open_requested.emit(vault_id)

    def _forward_rename(
        self,
        vault_id: bytes,
    ) -> None:
        self.rename_requested.emit(vault_id)

    def _forward_remove(
        self,
        vault_id: bytes,
    ) -> None:
        self.remove_requested.emit(vault_id)


def _format_last_opened(
    value: datetime,
) -> str:
    """Format a timestamp in the user's current timezone."""
    local_value = value.astimezone()

    return local_value.strftime("%b %d, %Y at %I:%M %p")
