from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import ProcessingMode, TaskRecord


class ProcessRunner(QObject):
    output_received = Signal(str)
    started = Signal()
    finished = Signal(int, int)
    failed_to_start = Signal(str)

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.started.connect(self.started)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)

    def build_arguments(self, task: TaskRecord) -> tuple[Path, list[str]]:
        if task.mode is ProcessingMode.OCR:
            return self.config.ocr_script, [
                str(task.input_path),
                "--output",
                str(task.output_dir),
            ]
        if task.mode is ProcessingMode.SUMMARY:
            return self.config.summary_script, [
                str(task.input_path),
                "--output-root",
                str(task.output_dir),
            ]
        return self.config.secure_script, [
            str(task.input_path),
            "--output-root",
            str(task.output_dir),
            "--device",
            task.device,
            "--model",
            self.config.ollama_model,
            "--ollama-host",
            self.config.ollama_host,
        ]

    def start_task(self, task: TaskRecord) -> None:
        script, arguments = self.build_arguments(task)
        if not self.config.backend_python.is_file():
            self.failed_to_start.emit(f"找不到后端 Python：{self.config.backend_python}")
            return
        if not script.is_file():
            self.failed_to_start.emit(f"找不到处理脚本：{script}")
            return
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUTF8", "1")
        environment.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(script.parent))
        self.output_received.emit(f"启动：{task.mode.display_name}\n")
        self.process.start(
            str(self.config.backend_python),
            [str(script), *arguments],
        )

    def cancel(self) -> None:
        if self.process.state() is not QProcess.ProcessState.NotRunning:
            self.output_received.emit("正在取消任务……\n")
            self.process.terminate()

    def _read_stdout(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output_received.emit(data)

    def _read_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if data:
            self.output_received.emit(data)

    def _finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        self.finished.emit(exit_code, int(exit_status.value))

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error is QProcess.ProcessError.FailedToStart:
            self.failed_to_start.emit(self.process.errorString())
