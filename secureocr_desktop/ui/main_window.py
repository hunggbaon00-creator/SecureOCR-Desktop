from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from secureocr_desktop.application.task_controller import TaskController
from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import DiagnosticLevel, EnvironmentSnapshot, ProcessingMode
from secureocr_desktop.services.environment_service import EnvironmentService
from secureocr_desktop.services.workspace_service import WorkspaceService
from secureocr_desktop.ui.pages import (
    EnvironmentPage,
    HistoryPage,
    LogsPage,
    ResultsPage,
    RulesPage,
    TextInfoPage,
    WorkbenchPage,
    task_from_payload,
)


class DiagnosticsWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, service: EnvironmentService) -> None:
        super().__init__()
        self.service = service

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.service.inspect())
        except Exception as error:  # Keep the UI available for diagnostics.
            self.failed.emit(f"环境检测异常：{type(error).__name__}: {error}")


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        self.environment_service = EnvironmentService(self.config)
        self.workspace_service = WorkspaceService(self.config)
        self.controller = TaskController(self.config, self.workspace_service, self)
        self.snapshot: EnvironmentSnapshot | None = None
        self._diagnostic_thread: QThread | None = None
        self._diagnostic_worker: DiagnosticsWorker | None = None

        self.setWindowTitle("SecureOCR Desktop")
        self.resize(1240, 820)
        self.setMinimumSize(1000, 680)
        self._build_ui()
        self._connect_signals()
        QTimer.singleShot(0, self.refresh_environment)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 22, 16, 18)
        brand = QLabel("SecureOCR\nDesktop")
        brand.setObjectName("brand")
        side_layout.addWidget(brand)
        subtitle = QLabel("本地文档处理工作台")
        subtitle.setObjectName("sidebarMuted")
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(24)

        self.pages = QStackedWidget()
        self.workbench_page = WorkbenchPage()
        self.results_page = ResultsPage()
        self.history_page = HistoryPage(self.workspace_service)
        self.rules_page = RulesPage(self.config)
        self.environment_page = EnvironmentPage()
        self.settings_page = TextInfoPage(
            "设置",
            (
                "初阶段使用固定且可审计的本地配置。\n\n"
                f"OCR 后端 Python：{self.config.backend_python}\n"
                f"工作区：{self.config.workspace_root}\n"
                f"Ollama：{self.config.ollama_host}\n"
                f"本地模型：{self.config.ollama_model}\n\n"
                "设备由已安装的唯一 Paddle 环境决定，界面不提供 CPU/GPU 切换。"
            ),
        )
        self.logs_page = LogsPage()
        page_items = [
            ("工作台", self.workbench_page),
            ("处理结果", self.results_page),
            ("最近任务", self.history_page),
            ("敏感规则", self.rules_page),
            ("环境检测", self.environment_page),
            ("设置", self.settings_page),
            ("日志", self.logs_page),
        ]
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for index, (name, page) in enumerate(page_items):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setObjectName("navButton")
            button.clicked.connect(lambda _checked=False, i=index: self.pages.setCurrentIndex(i))
            if index == 0:
                button.setChecked(True)
            if name == "处理结果":
                button.setEnabled(False)
            self.nav_group.addButton(button)
            self.nav_buttons[name] = button
            side_layout.addWidget(button)
            self.pages.addWidget(page)
        side_layout.addStretch()
        version = QLabel("v0.1.0 · Python 3.11")
        version.setObjectName("sidebarMuted")
        side_layout.addWidget(version)

        layout.addWidget(sidebar)
        layout.addWidget(self.pages, 1)

    def _connect_signals(self) -> None:
        self.workbench_page.start_requested.connect(self._start_tasks)
        self.workbench_page.cancel_requested.connect(self.controller.cancel)
        self.environment_page.refresh_requested.connect(self.refresh_environment)
        self.history_page.task_open_requested.connect(self._open_history_task)
        self.controller.queue_started.connect(self._queue_started)
        self.controller.task_started.connect(self._task_started)
        self.controller.task_finished.connect(self._task_finished)
        self.controller.queue_finished.connect(self._queue_finished)
        self.controller.log_received.connect(self.logs_page.append)
        self.controller.error_occurred.connect(self._show_error)

    @Slot()
    def refresh_environment(self) -> None:
        if self._diagnostic_thread and self._diagnostic_thread.isRunning():
            return
        self.workbench_page.device_label.setText("计算环境：正在检测 Paddle…")
        thread = QThread(self)
        worker = DiagnosticsWorker(self.environment_service)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._environment_ready)
        worker.failed.connect(self._diagnostics_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_diagnostic_refs)
        self._diagnostic_thread = thread
        self._diagnostic_worker = worker
        thread.start()

    @Slot()
    def _clear_diagnostic_refs(self) -> None:
        self._diagnostic_thread = None
        self._diagnostic_worker = None

    @Slot(object)
    def _environment_ready(self, snapshot: EnvironmentSnapshot) -> None:
        self.snapshot = snapshot
        self.workbench_page.set_environment(snapshot)
        self.environment_page.set_snapshot(snapshot)

    @Slot(str)
    def _diagnostics_failed(self, message: str) -> None:
        self.logs_page.append(message + "\n")
        QMessageBox.critical(self, "环境检测失败", message)

    @Slot(list, object)
    def _start_tasks(self, files: list[Path], mode: ProcessingMode) -> None:
        if self.snapshot is None:
            QMessageBox.information(self, "正在检测", "请等待环境检测完成。")
            return
        if not self.snapshot.can_process:
            QMessageBox.critical(self, "无法启动", "Python、Paddle 或工作区检查未通过。")
            return
        if mode in {ProcessingMode.SUMMARY, ProcessingMode.SECURE_REVIEW}:
            if not self.snapshot.can_use_ollama:
                QMessageBox.critical(self, "本地模型不可用", "Ollama 或本地模型检查未通过。")
                return
        if mode is ProcessingMode.SECURE_REVIEW and not self.snapshot.can_secure_review:
            QMessageBox.critical(
                self,
                "安全检查未通过",
                "远程服务、云功能或工作区检查未通过，已阻止敏感审查。",
            )
            return
        network = self.snapshot.get("network")
        if mode is ProcessingMode.SECURE_REVIEW and network:
            if network.level is DiagnosticLevel.WARNING:
                answer = QMessageBox.warning(
                    self,
                    "系统仍可能联网",
                    "检测到系统可能连接互联网。工具仍只调用本机服务，但建议先断开网络。\n\n"
                    "是否继续本地敏感审查？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer is not QMessageBox.StandardButton.Yes:
                    return
        if self.snapshot.device == "cpu" and mode in {
            ProcessingMode.OCR,
            ProcessingMode.SUMMARY,
        }:
            QMessageBox.critical(
                self,
                "现有脚本尚未支持 CPU 参数",
                "当前 legacy OCR 和总结脚本固定为 GPU。本次版本不会偷偷切换环境；"
                "请等待后端参数统一后再在 CPU 部署中使用。",
            )
            return
        self.controller.start_queue(files, mode, self.snapshot)

    @Slot(int)
    def _queue_started(self, count: int) -> None:
        self.workbench_page.set_running(True, f"已创建 {count} 个独立任务")
        self.logs_page.append(f"\n任务队列已启动，共 {count} 个文件。\n")

    @Slot(object)
    def _task_started(self, task: object) -> None:
        record = task
        self.workbench_page.set_running(True, f"正在处理：{record.input_path.name}")

    @Slot(object)
    def _task_finished(self, task: object) -> None:
        record = task
        self.results_page.load_task(record)
        self.nav_buttons["处理结果"].setEnabled(True)
        self.nav_buttons["处理结果"].setChecked(True)
        self.pages.setCurrentWidget(self.results_page)
        self.history_page.refresh()
        self.logs_page.append(f"任务结束：{record.status}，退出码 {record.exit_code}\n")
        if record.status == "failed":
            QMessageBox.warning(self, "任务失败", "处理失败，请查看日志中的具体错误。")

    @Slot()
    def _queue_finished(self) -> None:
        self.workbench_page.set_running(False, "任务队列已结束")

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self.workbench_page.set_running(False, "启动失败")
        self.logs_page.append(message + "\n")
        QMessageBox.critical(self, "错误", message)

    @Slot(dict)
    def _open_history_task(self, payload: dict[str, object]) -> None:
        try:
            task = task_from_payload(payload)
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(self, "无法打开任务", str(error))
            return
        existing = [path for path in task.output_files if path.exists()]
        task.output_files = existing or self.workspace_service.discover_outputs(task)
        self.results_page.load_task(task)
        self.nav_buttons["处理结果"].setEnabled(True)
        self.nav_buttons["处理结果"].setChecked(True)
        self.pages.setCurrentWidget(self.results_page)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.controller.is_running:
            answer = QMessageBox.question(
                self,
                "任务仍在运行",
                "关闭应用会终止当前任务，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.controller.cancel()
        event.accept()

