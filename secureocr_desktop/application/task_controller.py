from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from secureocr_desktop.application.process_runner import ProcessRunner
from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import EnvironmentSnapshot, ProcessingMode, TaskRecord
from secureocr_desktop.services.workspace_service import WorkspaceError, WorkspaceService


class TaskController(QObject):
    queue_started = Signal(int)
    task_started = Signal(object)
    task_finished = Signal(object)
    queue_finished = Signal()
    log_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        workspace_service: WorkspaceService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.workspace_service = workspace_service
        self.runner = ProcessRunner(config, self)
        self.runner.output_received.connect(self._receive_output)
        self.runner.finished.connect(self._process_finished)
        self.runner.failed_to_start.connect(self._failed_to_start)
        self._queue: deque[TaskRecord] = deque()
        self._current: TaskRecord | None = None
        self._cancel_requested = False

    @property
    def is_running(self) -> bool:
        return self._current is not None or bool(self._queue)

    def start_queue(
        self,
        files: list[Path],
        mode: ProcessingMode,
        snapshot: EnvironmentSnapshot,
    ) -> None:
        if self.is_running:
            self.error_occurred.emit("已有任务正在运行")
            return
        records: list[TaskRecord] = []
        try:
            for source in files:
                self.workspace_service.validate_input(source.resolve(), mode)
            for source in files:
                records.append(
                    self.workspace_service.create_task(source, mode, snapshot.device)
                )
        except (WorkspaceError, OSError) as error:
            self.error_occurred.emit(str(error))
            return
        self._queue.extend(records)
        self._cancel_requested = False
        self.queue_started.emit(len(records))
        self._start_next()

    def cancel(self) -> None:
        self._queue.clear()
        self._cancel_requested = True
        self.runner.cancel()
        QTimer.singleShot(3000, self._force_kill_if_needed)

    def _force_kill_if_needed(self) -> None:
        if self.runner.process.state().value != 0:
            self.runner.process.kill()

    def _start_next(self) -> None:
        if not self._queue:
            self._current = None
            self.queue_finished.emit()
            return
        self._current = self._queue.popleft()
        self._current.status = "running"
        self.workspace_service.save_task(self._current)
        self.task_started.emit(self._current)
        self.runner.start_task(self._current)

    def _receive_output(self, text: str) -> None:
        self.log_received.emit(text)
        if self._current is None:
            return
        log_file = self._current.log_dir / "process.log"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(text)

    def _process_finished(self, exit_code: int, _exit_status: int) -> None:
        if self._current is None:
            return
        task = self._current
        task.exit_code = exit_code
        task.output_files = self.workspace_service.discover_outputs(task)
        if self._cancel_requested:
            task.status = "cancelled"
        elif exit_code == 0:
            task.status = (
                "pending_human_review"
                if task.mode is ProcessingMode.SECURE_REVIEW
                else "completed"
            )
        elif exit_code == 2 and task.mode is ProcessingMode.SECURE_REVIEW:
            task.status = "blocked_pending_human_review"
        else:
            task.status = "failed"
        self.workspace_service.save_task(task)
        self.task_finished.emit(task)
        self._current = None
        if self._cancel_requested:
            self.queue_finished.emit()
        else:
            self._start_next()

    def _failed_to_start(self, message: str) -> None:
        if self._current is not None:
            self._current.status = "failed_to_start"
            self._current.exit_code = -1
            self.workspace_service.save_task(self._current)
            self.task_finished.emit(self._current)
            self._current = None
        self.error_occurred.emit(message)
        self._queue.clear()
        self.queue_finished.emit()
