"""The shared visual language for the USB Vault desktop application."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# Semantic color tokens. QSS does not expose custom properties, so these names
# document the shared palette used throughout the component rules below.
SURFACE_0 = "#08111f"
SURFACE_1 = "#101b2b"
SURFACE_2 = "#152338"
INPUT_SURFACE = "#0b1625"
BORDER_SUBTLE = "#22334a"
TEXT_PRIMARY = "#f4f8ff"
TEXT_SECONDARY = "#aabbd0"
ACCENT = "#49c8b6"
SUCCESS = "#55c98f"
DANGER = "#e87982"

APP_STYLESHEET = """
* {
    font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    color: #eaf2ff;
}
QMainWindow, QDialog, QWidget#mainWindow {
    background: #0b1220;
}
QWidget#vaultLibraryPage, QWidget#unlockPage, QWidget#setupPage,
QWidget#vaultPage, QWidget#recoveryPage, QWidget#securityPage {
    background: #0b1220;
}
QWidget#securityContent, QWidget#vaultCardsContainer,
QScrollArea#securityScrollArea QWidget#qt_scrollarea_viewport,
QScrollArea#vaultLibraryScrollArea QWidget#qt_scrollarea_viewport {
    background: #0b1220;
}
QLabel#brandEyebrow, QLabel#vaultLibraryEyebrow, QLabel#unlockEyebrow,
QLabel#setupEyebrow, QLabel#vaultEyebrow, QLabel#recoveryEyebrow,
QLabel#securityEyebrow {
    color: #61d7c5;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.3px;
}
QLabel#vaultLibraryTitle, QLabel#unlockTitle, QLabel#setupTitle,
QLabel#vaultTitle, QLabel#recoveryPageTitle, QLabel#securityPageTitle,
QLabel#recoveryCodeTitle {
    color: #f8fbff;
    font-size: 30px;
    font-weight: 700;
}
QLabel#vaultLibrarySubtitle, QLabel#pageSubtitle, QLabel#openedVaultPathLabel,
QLabel#vaultCardMeta, QLabel#formHint, QLabel#keyWaitDetail,
QLabel#emptyStateDescription, QLabel#recoveryCodeExplanation {
    color: #9baec7;
    font-size: 13px;
}
QFrame#vaultCard, QFrame#formSurface, QFrame#waitSurface, QFrame#vaultSurface,
QFrame#emptyState, QFrame#dialogSurface, QGroupBox {
    background: #121d2e;
    border: 1px solid #24344b;
    border-radius: 16px;
}
QFrame#vaultCard:hover {
    background: #16253a;
    border: 1px solid #3b5976;
}
QFrame#vaultCard[available="false"] {
    background: #111a29;
    border-color: #293647;
}
QLabel#vaultCardStatus {
    color: #61d7c5;
    font-size: 12px;
    font-weight: 600;
}
QLabel#vaultCardStatus[available="false"] { color: #f1ad72; }
QLabel#emptyStateTitle {
    color: #f2f7ff;
    font-size: 18px;
    font-weight: 650;
}
QLabel#selectedVaultLabel {
    color: #80e5d5;
    background: #133438;
    border: 1px solid #245c60;
    border-radius: 8px;
    padding: 9px 11px;
}
QLineEdit, QComboBox, QPlainTextEdit, QListWidget, QTableWidget {
    background: #0d1726;
    border: 1px solid #2b3d55;
    border-radius: 9px;
    padding: 9px 11px;
    selection-background-color: #245e69;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {
    border: 1px solid #5ad4c3;
}
QLineEdit:disabled, QComboBox:disabled { color: #7890ad; background: #101927; }
QComboBox { min-height: 20px; padding-right: 35px; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    background: #142238;
    border-left: 1px solid #2b3d55;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}
QComboBox::drop-down:hover { background: #1d3048; }
QComboBox QAbstractItemView {
    background: #142238;
    border: 1px solid #3c536f;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #245e69;
    selection-color: #f8fbff;
    outline: 0;
}
QPushButton, QCommandLinkButton {
    background: #1a2a40;
    border: 1px solid #304762;
    border-radius: 9px;
    min-height: 20px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover, QCommandLinkButton:hover { background: #223650; border-color: #4e6987; }
QPushButton:pressed, QCommandLinkButton:pressed { background: #15243a; }
QPushButton:disabled, QCommandLinkButton:disabled {
    color: #6f8299; background: #152033; border-color: #26364b;
}
QPushButton#primaryButton, QPushButton#createVaultFromLibraryButton,
QPushButton#createVaultButton, QPushButton#unlockButton, QPushButton#recoverVaultButton,
QPushButton#addFileButton, QPushButton#changeSecurityPasswordButton,
QPushButton#finishRecoveryCodeButton {
    background: #43cbb8;
    border-color: #55dac8;
    color: #09201f;
}
QPushButton#primaryButton:hover, QPushButton#createVaultFromLibraryButton:hover,
QPushButton#createVaultButton:hover, QPushButton#unlockButton:hover,
QPushButton#recoverVaultButton:hover, QPushButton#addFileButton:hover,
QPushButton#changeSecurityPasswordButton:hover,
QPushButton#finishRecoveryCodeButton:hover { background: #68decf; }
QPushButton#dangerButton, QPushButton#deleteFileButton, QPushButton#removeVaultCardButton,
QPushButton#revokeSecurityKeyButton { color: #ffb2b2; }
QPushButton#lockVaultButton { background: #2d405b; }
QPushButton#openVaultCardButton {
    border: none;
    background: transparent;
    text-align: left;
    padding: 3px 3px 3px 1px;
    color: #f6f9ff;
    font-size: 18px;
}
QPushButton#openVaultCardButton:hover { background: transparent; color: #70e1d0; }
QCheckBox { color: #b7c7dc; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #506883;
    border-radius: 4px; background: #0d1726;
}
QCheckBox::indicator:checked { background: #48cdbb; border-color: #48cdbb; }
QTableWidget { gridline-color: #25364c; padding: 2px; }
QTableWidget::item { padding: 8px 10px; border-bottom: 1px solid #1d2c40; }
QTableWidget::item:selected { background: #1c3d4b; color: #ffffff; }
QHeaderView { background: #142238; }
QHeaderView::section, QTableCornerButton::section {
    background: #142238; color: #91a7c1; border: none;
    border-bottom: 1px solid #30445e; padding: 0 12px; font-weight: 700;
}
QGroupBox {
    margin-top: 16px; padding: 18px 12px 12px 12px;
    font-size: 15px; font-weight: 700; color: #f2f6fb;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { border: none; background: transparent; width: 10px; margin: 6px; }
QScrollBar::handle:vertical { background: #31445d; min-height: 28px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenuBar { background: #0b1220; color: #b8c8db; padding: 4px 8px; }
QMenuBar::item:selected, QMenu::item:selected { background: #1d3048; border-radius: 5px; }
QMenu { background: #142238; border: 1px solid #30445e; padding: 5px; }
QMenu::item { padding: 7px 24px 7px 12px; }
QStatusBar { background: #0b1220; color: #8ea5c0; border-top: 1px solid #1b2a3d; }
QProgressBar {
    background: #17253a;
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar::chunk { background: #4ed4c1; border-radius: 3px; }
QToolTip {
    color: #eaf2ff;
    background: #1a2a40;
    border: 1px solid #3c536f;
    padding: 5px;
}
QLabel#unlockErrorLabel, QLabel#setupErrorLabel, QLabel#recoveryPageErrorLabel,
QLabel#securityPageErrorLabel, QLabel#vaultLibraryErrorLabel {
    color: #ffc1c1;
    background: #3a2029;
    border: 1px solid #703746;
    border-radius: 8px;
    padding: 9px;
}
QLabel#recoveryCodeWarning, QLabel#recoveryRotationWarning {
    color: #f2c48f;
    background: #30271d;
    border: 1px solid #5b4630;
    border-radius: 8px;
    padding: 9px;
}
QPlainTextEdit#recoveryCodeEdit {
    font-family: "Menlo", monospace;
    font-size: 14px;
    color: #d9fff9;
}
QLabel#vaultEntryCount { color: #8fa5bd; padding-right: 4px; }
QStackedWidget#vaultContentStack { background: transparent; }

/* Shared component system */
QWidget#pageContent { background: transparent; }
QWidget#pageHeader { background: transparent; }
QLabel#pageHeaderEyebrow {
    color: #62d2c1; font-size: 12px; font-weight: 700; letter-spacing: 1.2px;
}
QLabel#pageHeaderTitle {
    color: #f6f9ff; font-size: 30px; font-weight: 700;
}
QLabel#pageHeaderDescription {
    color: #aabbd0; font-size: 14px; padding-top: 2px;
}
QLabel#pageHeaderContext {
    color: #7f95ae; font-size: 13px; padding-top: 2px;
}
QFrame#sectionCard, QFrame#authPanel, QFrame#toolbarSurface,
QFrame#vaultCard, QFrame#vaultSurface, QFrame#emptyState {
    background: #101b2b;
    border: 1px solid #203047;
    border-radius: 12px;
}
QFrame#dangerSection {
    background: #1b1722;
    border: 1px solid #49303d;
    border-radius: 12px;
}
QLabel#sectionTitle { color: #f2f6fc; font-size: 19px; font-weight: 650; }
QLabel#sectionDescription { color: #a4b5ca; font-size: 14px; }
QFrame#toolbarSurface { background: #0e1929; border-radius: 10px; }

QLineEdit, QComboBox, QPlainTextEdit, QListWidget, QTableWidget {
    background: #0b1625;
    border-color: #23364e;
    border-radius: 8px;
    font-size: 14px;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus,
QTableWidget:focus {
    border: 2px solid #4fc8b5;
}
QLineEdit[error="true"] { border-color: #ef707b; background: #151b2a; }
QLineEdit[error="true"]:focus { border: 2px solid #ef707b; }
QLabel#formLabel { color: #c6d3e2; font-size: 12px; font-weight: 650; }
QLabel#formHelp, QLabel#metadataText, QLabel#selectionStatus {
    color: #8fa3bb; font-size: 13px;
}

QPushButton, QCommandLinkButton, QToolButton {
    min-height: 22px;
    border-radius: 8px;
    padding: 8px 13px;
    font-size: 13px;
}
QToolButton {
    background: transparent; border: none; padding: 7px;
}
QToolButton:hover { background: #1c2c42; }
QPushButton#ghostButton { background: transparent; border-color: transparent; }
QPushButton#ghostButton:hover { background: #19283c; }
QPushButton#dangerButton, QPushButton#deleteFileButton,
QPushButton#revokeSecurityKeyButton {
    color: #f199a1; border-color: #56313d; background: #221923;
}
QPushButton#dangerButton:hover, QPushButton#deleteFileButton:hover,
QPushButton#revokeSecurityKeyButton:hover {
    color: #ffc0c5; border-color: #8a4452; background: #301c27;
}

QFrame#statusBadge { background: transparent; border: none; }
QFrame#statusDot { border: none; border-radius: 4px; background: #55c98f; }
QFrame#statusDot[tone="warning"] { background: #e7ad68; }
QFrame#statusDot[tone="danger"] { background: #e87982; }
QLabel#statusBadgeLabel { color: #b8c8d8; font-size: 13px; font-weight: 600; }

QFrame#toastBanner {
    background: #18283c; border: 1px solid #34506c; border-radius: 10px;
}
QLabel#toastText { color: #eaf2ff; font-size: 13px; font-weight: 600; }

QFrame#vaultCard { min-width: 300px; max-width: 420px; }
QFrame#vaultCard:hover { background: #15243a; border-color: #38516d; }
QLabel#vaultCardTitle { color: #f4f8ff; font-size: 19px; font-weight: 650; }
QLabel#vaultCardPath { color: #8095ad; font-size: 13px; }
QLabel#vaultCardMeta { color: #91a5bd; font-size: 13px; }
QLabel#vaultCardHint { color: #6f849d; font-size: 12px; }
QWidget#keyTableCell { background: transparent; }
QLabel#keyTableLabel { color: #e7eef8; font-size: 13px; font-weight: 600; }
QLabel#keyTableId { color: #7f94ac; font-size: 12px; }

QTableWidget { border: none; border-radius: 8px; }
QTableWidget::item { min-height: 40px; }
QHeaderView::section {
    color: #9fb0c4; font-size: 12px; background: #142237;
    border-bottom-color: #26394f;
}
QTableWidget::item:selected { background: #193c47; }

QLabel#authStepActive {
    color: #dffbf6; background: #17373b; border: 1px solid #2a6666;
    border-radius: 8px; padding: 7px 10px; font-size: 12px; font-weight: 650;
}
QLabel#authStepPending {
    color: #8296ad; background: #0d1726; border: 1px solid #213248;
    border-radius: 8px; padding: 7px 10px; font-size: 12px;
}
QLabel#passwordStrength { color: #8fa4bc; font-size: 12px; }
QLabel#passwordStrength[level="strong"] { color: #70d49e; }
QLabel#passwordStrength[level="medium"] { color: #e7b873; }
QLabel#passwordStrength[level="weak"] { color: #e89aa1; }
"""


def apply_application_theme(application: QApplication) -> None:
    """Apply the app-wide dark, low-distraction desktop theme."""
    application.setStyle("Fusion")
    application.setFont(QFont("Avenir Next", 14))
    application.setStyleSheet(APP_STYLESHEET)
