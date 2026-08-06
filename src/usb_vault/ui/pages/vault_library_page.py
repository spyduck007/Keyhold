"""Card-based home screen for known encrypted vaults."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import (
    Signal,
)
from PySide6.QtWidgets import (
    QCommandLinkButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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
        self.setFrameShadow(QFrame.Shadow.Raised)

        availability_text = (
            "Available" if entry.is_available else ("Unavailable — vault file not found")
        )

        description = (
            f"{availability_text}\n"
            f"{entry.vault_path}\n"
            "Last opened: "
            f"{_format_last_opened(entry.last_opened_at)}"
        )

        self.open_button = QCommandLinkButton(entry.display_name)
        self.open_button.setObjectName("openVaultCardButton")
        self.open_button.setDescription(description)
        self.open_button.setEnabled(entry.is_available)
        self.open_button.clicked.connect(self._emit_open)

        self.rename_button = QPushButton("Rename…")
        self.rename_button.setObjectName("renameVaultCardButton")
        self.rename_button.clicked.connect(self._emit_rename)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("removeVaultCardButton")
        self.remove_button.clicked.connect(self._emit_remove)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.rename_button)
        actions.addWidget(self.remove_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.open_button)
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

        title = QLabel("Your Vaults")
        title.setObjectName("vaultLibraryTitle")

        subtitle = QLabel(
            "Choose a vault, enter its password, and use a registered USB key to unlock it."
        )
        subtitle.setObjectName("vaultLibrarySubtitle")
        subtitle.setWordWrap(True)

        self.create_button = QPushButton("Create New Vault")
        self.create_button.setObjectName("createVaultFromLibraryButton")
        self.create_button.clicked.connect(self.create_requested.emit)

        self.add_existing_button = QPushButton("Add Existing Vault…")
        self.add_existing_button.setObjectName("addExistingVaultButton")
        self.add_existing_button.clicked.connect(self.add_existing_requested.emit)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshVaultLibraryButton")
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

        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self._cards_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("vaultLibraryScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self._cards_widget)

        layout = QVBoxLayout(self)
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
            empty_label = QLabel(
                "No vaults have been added yet.\n\n"
                "Create a new vault or add an "
                "existing encrypted vault."
            )
            empty_label.setObjectName("emptyVaultLibraryLabel")
            empty_label.setWordWrap(True)

            self._cards_layout.addWidget(empty_label)
            self._cards_layout.addStretch()
            return

        for entry in normalized_entries:
            card = VaultCard(entry)
            card.open_requested.connect(self._forward_open)
            card.rename_requested.connect(self._forward_rename)
            card.remove_requested.connect(self._forward_remove)

            self._cards[entry.vault_id] = card
            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()

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
            widget = item.widget()

            if widget is not None:
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
