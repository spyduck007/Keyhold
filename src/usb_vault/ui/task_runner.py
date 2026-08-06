"""Single-operation Qt thread-pool runner."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
)

TaskFunction = Callable[[], object]
TaskSuccessHandler = Callable[[object], None]
TaskFailureHandler = Callable[[str], None]


class TaskSignals(QObject):
    """Signals emitted by one background task."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class BackgroundTask(QRunnable):
    """Run one callable outside the Qt GUI thread."""

    def __init__(
        self,
        operation: TaskFunction,
    ) -> None:
        super().__init__()

        if not callable(operation):
            raise TypeError("operation must be callable")

        self._operation = operation
        self.signals = TaskSignals()

    @Slot()
    def run(self) -> None:
        """Execute the callable and report its result."""
        try:
            result = self._operation()
        except Exception as error:
            message = str(error).strip()

            if not message:
                message = "Operation failed."

            self.signals.failed.emit(message)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class TaskRunner(QObject):
    """Allow at most one background operation at a time."""

    busy_changed = Signal(bool)

    def __init__(
        self,
        *,
        thread_pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._thread_pool = thread_pool if thread_pool is not None else QThreadPool.globalInstance()
        self._worker: BackgroundTask | None = None
        self._busy = False

    @property
    def is_busy(self) -> bool:
        """Return whether an operation is currently running."""
        return self._busy

    def start(
        self,
        operation: TaskFunction,
        *,
        succeeded: TaskSuccessHandler,
        failed: TaskFailureHandler,
    ) -> None:
        """Start one task or reject overlapping work."""
        if self._busy:
            raise RuntimeError("another vault operation is already in progress")

        if not callable(succeeded):
            raise TypeError("succeeded must be callable")

        if not callable(failed):
            raise TypeError("failed must be callable")

        worker = BackgroundTask(operation)
        worker.signals.succeeded.connect(succeeded)
        worker.signals.failed.connect(failed)
        worker.signals.finished.connect(self._finish_task)

        self._worker = worker
        self._busy = True
        self.busy_changed.emit(True)

        try:
            self._thread_pool.start(worker)
        except Exception:
            self._worker = None
            self._busy = False
            self.busy_changed.emit(False)
            raise

    @Slot()
    def _finish_task(self) -> None:
        self._worker = None
        self._busy = False
        self.busy_changed.emit(False)
