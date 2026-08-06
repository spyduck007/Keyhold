"""The shared visual language for the USB Vault desktop application."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

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
"""


def apply_application_theme(application: QApplication) -> None:
    """Apply the app-wide dark, low-distraction desktop theme."""
    application.setStyle("Fusion")
    application.setFont(QFont("Avenir Next", 13))
    application.setStyleSheet(APP_STYLESHEET)
