"""A restrained black and charcoal visual system for the desktop app."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

SURFACE_0 = "#151515"
SURFACE_1 = "#1d1d1d"
SURFACE_2 = "#252525"
INPUT_SURFACE = "#181818"
BORDER_SUBTLE = "#363636"
TEXT_PRIMARY = "#f3f3f3"
TEXT_SECONDARY = "#a4a4a4"
ACCENT = "#f0f0f0"
SUCCESS = "#70b887"
DANGER = "#d97878"

APP_STYLESHEET = """
* {
    font-family: "Helvetica Neue";
    color: #e8e8e8;
}

QMainWindow, QDialog, QWidget#mainWindow, QWidget#appShell,
QWidget#vaultLibraryPage, QWidget#unlockPage, QWidget#setupPage,
QWidget#vaultPage, QWidget#recoveryPage, QWidget#securityPage,
QWidget#securityContent, QWidget#vaultCardsContainer,
QScrollArea#securityScrollArea QWidget#qt_scrollarea_viewport,
QScrollArea#vaultLibraryScrollArea QWidget#qt_scrollarea_viewport {
    background: #191919;
}

QFrame#appSidebar {
    background: #111111;
    border: none;
    border-right: 1px solid #2a2a2a;
}
QLabel#sidebarBrandIcon { background: transparent; }
QLabel#sidebarBrandName { color: #f4f4f4; font-size: 17px; font-weight: 700; }
QLabel#sidebarBrandDetail { color: #777777; font-size: 11px; }
QLabel#sidebarSectionLabel {
    color: #666666;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 0 10px 6px 10px;
}
QPushButton#sidebarNavButton {
    color: #a9a9a9;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    min-height: 22px;
    padding: 9px 11px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#sidebarNavButton:hover { color: #eeeeee; background: #1e1e1e; }
QPushButton#sidebarNavButton[active="true"] {
    color: #ffffff;
    background: #292929;
    border-color: #3e3e3e;
    font-weight: 600;
}
QPushButton#sidebarNavButton:disabled {
    color: #4f4f4f;
    background: transparent;
    border-color: transparent;
}
QFrame#sidebarSessionCard {
    background: #181818;
    border: 1px solid #2d2d2d;
    border-radius: 9px;
}
QLabel#sidebarSessionName { color: #d5d5d5; font-size: 12px; font-weight: 600; }
QLabel#sidebarSessionState { color: #737373; font-size: 11px; }

QWidget#pageContent, QWidget#pageHeader, QWidget#pageHeaderActions,
QWidget#breadcrumbBar, QWidget#keyTableCell { background: transparent; }
QLabel#pageHeaderEyebrow {
    color: #737373;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}
QLabel#pageHeaderTitle { color: #f5f5f5; font-size: 30px; font-weight: 700; }
QLabel#pageHeaderDescription { color: #9b9b9b; font-size: 14px; padding-top: 3px; }
QLabel#pageHeaderContext { color: #707070; font-size: 12px; padding-top: 3px; }

QFrame#sectionCard, QFrame#authPanel, QFrame#toolbarSurface,
QFrame#vaultCard, QFrame#vaultSurface, QFrame#emptyState,
QFrame#formSurface, QFrame#waitSurface, QFrame#dialogSurface, QGroupBox {
    background: #212121;
    border: 1px solid #343434;
    border-radius: 11px;
}
QFrame#toolbarSurface { background: #202020; border-color: #303030; border-radius: 9px; }
QFrame#vaultCard { min-width: 300px; max-width: 400px; }
QFrame#vaultCard:hover { background: #272727; border-color: #484848; }
QFrame#vaultCard[available="false"] { background: #1c1c1c; border-color: #2b2b2b; }
QFrame#dangerSection {
    background: #241c1c;
    border: 1px solid #4a3030;
    border-radius: 9px;
}
QLabel#sectionTitle, QLabel#emptyStateTitle {
    color: #eeeeee;
    font-size: 18px;
    font-weight: 650;
}
QLabel#sectionDescription, QLabel#emptyStateDescription { color: #9a9a9a; font-size: 13px; }

QLineEdit, QComboBox, QPlainTextEdit, QListWidget {
    color: #ededed;
    background: #181818;
    border: 1px solid #393939;
    border-radius: 8px;
    min-height: 20px;
    padding: 9px 11px;
    selection-background-color: #505050;
    selection-color: #ffffff;
    font-size: 13px;
}
QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover, QListWidget:hover {
    border-color: #4b4b4b;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {
    border: 2px solid #8b8b8b;
}
QLineEdit:disabled, QComboBox:disabled {
    color: #5e5e5e;
    background: #171717;
    border-color: #292929;
}
QLineEdit[error="true"] { border-color: #b75f5f; background: #211919; }
QLineEdit[error="true"]:focus { border: 2px solid #cf6c6c; }
QComboBox { padding-right: 34px; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 31px;
    background: #222222;
    border: none;
    border-left: 1px solid #353535;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}
QComboBox::drop-down:hover { background: #2b2b2b; }
QComboBox QAbstractItemView {
    color: #e8e8e8;
    background: #222222;
    border: 1px solid #424242;
    selection-background-color: #3a3a3a;
    selection-color: #ffffff;
    outline: 0;
    padding: 4px;
}
QLabel#formLabel { color: #c4c4c4; font-size: 11px; font-weight: 650; }
QLabel#formHelp, QLabel#metadataText, QLabel#selectionStatus {
    color: #858585;
    font-size: 12px;
}
QCheckBox { color: #a9a9a9; spacing: 8px; font-size: 13px; }
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #555555;
    border-radius: 4px;
    background: #181818;
}
QCheckBox::indicator:hover { border-color: #888888; }
QCheckBox::indicator:checked { background: #e9e9e9; border-color: #e9e9e9; }

QPushButton, QCommandLinkButton {
    color: #dedede;
    background: #2a2a2a;
    border: 1px solid #414141;
    border-radius: 8px;
    min-height: 20px;
    padding: 8px 13px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover, QCommandLinkButton:hover { background: #333333; border-color: #5a5a5a; }
QPushButton:pressed, QCommandLinkButton:pressed { background: #242424; }
QPushButton:disabled, QCommandLinkButton:disabled {
    color: #5d5d5d;
    background: #202020;
    border-color: #303030;
}
QPushButton#primaryButton, QPushButton#createVaultFromLibraryButton,
QPushButton#createVaultButton, QPushButton#unlockButton, QPushButton#recoverVaultButton,
QPushButton#addFileButton, QPushButton#changeSecurityPasswordButton,
QPushButton#finishRecoveryCodeButton {
    color: #151515;
    background: #eeeeee;
    border-color: #eeeeee;
}
QPushButton#primaryButton:hover, QPushButton#createVaultFromLibraryButton:hover,
QPushButton#createVaultButton:hover, QPushButton#unlockButton:hover,
QPushButton#recoverVaultButton:hover, QPushButton#addFileButton:hover,
QPushButton#changeSecurityPasswordButton:hover,
QPushButton#finishRecoveryCodeButton:hover {
    background: #ffffff;
    border-color: #ffffff;
}
QPushButton#ghostButton { background: transparent; border-color: transparent; }
QPushButton#ghostButton:hover { background: #2b2b2b; color: #ffffff; }
QPushButton#lockVaultButton { background: #262626; }
QPushButton#dangerButton, QPushButton#deleteFileButton,
QPushButton#revokeSecurityKeyButton {
    color: #d98686;
    background: #271d1d;
    border-color: #503333;
}
QPushButton#dangerButton:hover, QPushButton#deleteFileButton:hover,
QPushButton#revokeSecurityKeyButton:hover {
    color: #f0a0a0;
    background: #312121;
    border-color: #744242;
}
QToolButton {
    color: #bdbdbd;
    background: transparent;
    border: none;
    border-radius: 7px;
    min-height: 20px;
    padding: 7px;
}
QToolButton:hover { background: #303030; }
QToolButton::menu-indicator { image: none; width: 0; height: 0; }

QFrame#statusBadge { background: transparent; border: none; }
QFrame#statusDot { background: #70b887; border: none; border-radius: 4px; }
QFrame#statusDot[tone="warning"] { background: #c6a367; }
QFrame#statusDot[tone="danger"] { background: #d97878; }
QLabel#statusBadgeLabel { color: #a7a7a7; font-size: 12px; font-weight: 600; }
QFrame#selectedVaultLabel {
    color: #cfcfcf;
    background: #262626;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
    padding: 8px 10px;
}
QLabel#authStepActive {
    color: #f0f0f0;
    background: #303030;
    border: 1px solid #4b4b4b;
    border-radius: 7px;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 650;
}
QLabel#authStepPending {
    color: #6f6f6f;
    background: #1b1b1b;
    border: 1px solid #303030;
    border-radius: 7px;
    padding: 7px 10px;
    font-size: 11px;
}

QLabel#vaultCardTitle { color: #f0f0f0; font-size: 18px; font-weight: 650; }
QLabel#vaultCardPath, QLabel#vaultCardMeta { color: #7f7f7f; font-size: 12px; }
QLabel#vaultCardHint { color: #626262; font-size: 11px; }
QLabel#vaultEntryCount { color: #858585; padding-right: 4px; }
QStackedWidget#vaultContentStack { background: transparent; }
QPushButton#breadcrumbLink, QPushButton#breadcrumbCurrent {
    background: transparent;
    border: none;
    padding: 2px 4px;
    min-height: 0;
    font-size: 12px;
}
QPushButton#breadcrumbLink { color: #797979; font-weight: 500; }
QPushButton#breadcrumbLink:hover { color: #d5d5d5; }
QPushButton#breadcrumbCurrent { color: #dedede; font-weight: 650; }
QPushButton#breadcrumbCurrent:disabled { color: #dedede; }

QTableWidget {
    color: #dedede;
    background: #1b1b1b;
    border: none;
    border-radius: 7px;
    gridline-color: #2b2b2b;
    padding: 0;
    selection-background-color: #343434;
}
QTableWidget::item { padding: 8px 10px; border-bottom: 1px solid #2a2a2a; }
QTableWidget::item:hover { background: #252525; }
QTableWidget::item:selected { background: #343434; color: #ffffff; }
QHeaderView, QHeaderView::section, QTableCornerButton::section {
    color: #858585;
    background: #202020;
    border: none;
    border-bottom: 1px solid #343434;
    padding: 0 11px;
    font-size: 11px;
    font-weight: 650;
}
QLabel#keyTableLabel { color: #dedede; font-size: 12px; font-weight: 600; }
QLabel#keyTableId { color: #737373; font-size: 11px; }

QLabel#unlockErrorLabel, QLabel#setupErrorLabel, QLabel#recoveryPageErrorLabel,
QLabel#securityPageErrorLabel, QLabel#vaultLibraryErrorLabel {
    color: #e3a0a0;
    background: #281e1e;
    border: 1px solid #543333;
    border-left: 3px solid #bd6666;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#recoveryCodeWarning, QLabel#recoveryRotationWarning {
    color: #ceb58e;
    background: #27231d;
    border: 1px solid #4a4030;
    border-left: 3px solid #a88757;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
}
QFrame#toastBanner { background: #2a2a2a; border: 1px solid #484848; border-radius: 8px; }
QLabel#toastText { color: #eeeeee; font-size: 12px; font-weight: 600; }
QProgressBar {
    background: #303030;
    border: none;
    border-radius: 2px;
    min-height: 4px;
    max-height: 4px;
}
QProgressBar::chunk { background: #bdbdbd; border-radius: 2px; }
QStatusBar { background: #111111; color: #777777; border: none; }

QMenuBar { color: #bcbcbc; background: #151515; padding: 3px 6px; }
QMenuBar::item:selected, QMenu::item:selected { background: #303030; border-radius: 5px; }
QMenu {
    color: #dedede;
    background: #222222;
    border: 1px solid #404040;
    padding: 5px;
}
QMenu::item { padding: 7px 24px 7px 11px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { border: none; background: transparent; width: 9px; margin: 5px; }
QScrollBar::handle:vertical { background: #444444; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { color: #eeeeee; background: #2b2b2b; border: 1px solid #4a4a4a; padding: 5px; }
QLabel#passwordStrength { color: #808080; font-size: 11px; }
QLabel#passwordStrength[level="strong"] { color: #79b98d; }
QLabel#passwordStrength[level="medium"] { color: #c5a66e; }
QLabel#passwordStrength[level="weak"] { color: #cf8080; }
"""


def apply_application_theme(application: QApplication) -> None:
    """Apply the app-wide neutral desktop theme."""
    application.setStyle("Fusion")
    application.setFont(QFont("Helvetica Neue", 14))
    application.setStyleSheet(APP_STYLESHEET)
