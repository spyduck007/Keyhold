"""Recovery-code presentation dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RecoveryCodeDialog(QDialog):
    """Display a newly generated recovery code once."""

    def __init__(
        self,
        recovery_code: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        if not isinstance(
            recovery_code,
            str,
        ):
            raise TypeError("recovery_code must be a string")

        if not recovery_code:
            raise ValueError("recovery_code must not be empty")

        self._recovery_code = recovery_code

        self.setObjectName("recoveryCodeDialog")
        self.setWindowTitle("Save Recovery Code")
        self.setModal(True)
        self.resize(
            620,
            300,
        )

        title = QLabel("Save your recovery code")
        title.setObjectName("recoveryCodeTitle")

        explanation = QLabel(
            "Store this code offline in a safe place. "
            "It can restore USB access when used with "
            "the vault password. It will not be shown again."
        )
        explanation.setWordWrap(True)

        self.code_edit = QPlainTextEdit()
        self.code_edit.setObjectName("recoveryCodeEdit")
        self.code_edit.setPlainText(recovery_code)
        self.code_edit.setReadOnly(True)
        self.code_edit.setMaximumHeight(100)

        self.copy_button = QPushButton("Copy Code")
        self.copy_button.setObjectName("copyRecoveryCodeButton")
        self.copy_button.clicked.connect(self._copy_code)

        self.copy_status_label = QLabel()
        self.copy_status_label.setObjectName("recoveryCopyStatusLabel")
        self.copy_status_label.setWordWrap(True)

        self.acknowledgement_checkbox = QCheckBox("I have saved the recovery code.")
        self.acknowledgement_checkbox.setObjectName("recoveryAcknowledgementCheckbox")

        self.done_button = QPushButton("Continue")
        self.done_button.setObjectName("finishRecoveryCodeButton")
        self.done_button.setEnabled(False)
        self.done_button.clicked.connect(self.accept)

        self.acknowledgement_checkbox.toggled.connect(self.done_button.setEnabled)

        buttons = QHBoxLayout()
        buttons.addWidget(self.copy_button)
        buttons.addStretch()
        buttons.addWidget(self.done_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(self.code_edit)
        layout.addWidget(self.copy_status_label)
        layout.addWidget(self.acknowledgement_checkbox)
        layout.addLayout(buttons)

    def reject(self) -> None:
        """Prevent dismissal before the user acknowledges saving it."""
        if not self.acknowledgement_checkbox.isChecked():
            self.copy_status_label.setText(
                "Save the recovery code and confirm the checkbox before continuing."
            )
            return

        super().reject()

    def _copy_code(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._recovery_code)
        self.copy_status_label.setText(
            "Recovery code copied. The clipboard will retain it until it is replaced."
        )


def show_recovery_code(
    parent: QWidget,
    recovery_code: str,
) -> None:
    """Display the recovery code in a modal dialog."""
    dialog = RecoveryCodeDialog(
        recovery_code,
        parent,
    )
    dialog.exec()
