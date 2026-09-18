from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import (
    DiagnosticLevel,
    EnvironmentSnapshot,
    ProcessingMode,
    TaskRecord,
)
from secureocr_desktop.services.workspace_service import WorkspaceService
from secureocr_desktop.ui.widgets import DropZone, StatusCard


class WorkbenchPage(QWidget):
    start_requested = Signal(list, object)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.files: list[Path] = []
        self.snapshot: EnvironmentSnapshot | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        heading = QLabel("本地文档处理工作台")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)
        description = QLabel("选择文件和处理模式，任务将在本机独立工作区中运行。")
        description.setObjectName("pageSubtitle")
        root.addWidget(description)

        cards = QGridLayout()
        cards.setSpacing(10)
        self.toolchain_card = StatusCard("工具链")
        self.network_card = StatusCard("系统网络")
        self.workspace_card = StatusCard("工作区")
        self.cloud_card = StatusCard("云同步")
        cards.addWidget(self.toolchain_card, 0, 0)
        cards.addWidget(self.network_card, 0, 1)
        cards.addWidget(self.workspace_card, 0, 2)
        cards.addWidget(self.cloud_card, 0, 3)
        root.addLayout(cards)

        self.device_label = QLabel("计算环境：正在检测 Paddle…")
        self.device_label.setObjectName("deviceBanner")
        root.addWidget(self.device_label)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.add_files)
        root.addWidget(self.drop_zone)

        file_toolbar = QHBoxLayout()
        choose_button = QPushButton("选择文件")
        choose_button.clicked.connect(self.choose_files)
        clear_button = QPushButton("清空列表")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(self.clear_files)
        file_toolbar.addWidget(QLabel("待处理文件"))
        file_toolbar.addStretch()
        file_toolbar.addWidget(choose_button)
        file_toolbar.addWidget(clear_button)
        root.addLayout(file_toolbar)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(120)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        root.addWidget(self.file_list)

        mode_frame = QFrame()
        mode_frame.setObjectName("panel")
        mode_layout = QVBoxLayout(mode_frame)
        mode_title = QLabel("处理模式")
        mode_title.setObjectName("sectionTitle")
        mode_layout.addWidget(mode_title)
        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        for index, mode in enumerate(ProcessingMode):
            button = QPushButton(mode.display_name)
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.setProperty("mode", mode.value)
            button.toggled.connect(
                lambda checked, target=button, label=mode.display_name: target.setText(
                    f"✓  {label}" if checked else label
                )
            )
            if index == 0:
                button.setChecked(True)
            self.mode_group.addButton(button)
            mode_row.addWidget(button, 1)
        mode_layout.addLayout(mode_row)
        root.addWidget(mode_frame)

        action_row = QHBoxLayout()
        self.status_label = QLabel("请选择或拖入文件")
        self.status_label.setObjectName("mutedLabel")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(220)
        self.start_button = QPushButton("开始处理")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_requested)
        action_row.addWidget(self.status_label)
        action_row.addStretch()
        action_row.addWidget(self.progress)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.start_button)
        root.addLayout(action_row)

    def selected_mode(self) -> ProcessingMode:
        button = self.mode_group.checkedButton()
        return ProcessingMode(button.property("mode"))

    def choose_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self,
            "选择待处理文件",
            "",
            "支持的文件 (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.md *.txt)",
        )
        self.add_files([Path(name) for name in names])

    def add_files(self, paths: list[Path]) -> None:
        for path in paths:
            resolved = path.resolve()
            if resolved.is_file() and resolved not in self.files:
                self.files.append(resolved)
                self.file_list.addItem(str(resolved))
        self.status_label.setText(f"已选择 {len(self.files)} 个文件")

    def clear_files(self) -> None:
        self.files.clear()
        self.file_list.clear()
        self.status_label.setText("请选择或拖入文件")

    def set_environment(self, snapshot: EnvironmentSnapshot) -> None:
        self.snapshot = snapshot
        tool_items = [
            snapshot.get(key)
            for key in ("ollama_local", "ollama", "model", "cloud_disabled")
        ]
        if all(item and item.level is DiagnosticLevel.PASS for item in tool_items):
            self.toolchain_card.set_status(DiagnosticLevel.PASS, "本地运行")
        elif any(item and item.level is DiagnosticLevel.FAIL for item in tool_items):
            self.toolchain_card.set_status(DiagnosticLevel.FAIL, "本地工具链未就绪")
        else:
            self.toolchain_card.set_status(DiagnosticLevel.WARNING, "需要检查")
        for card, key in (
            (self.network_card, "network"),
            (self.workspace_card, "workspace"),
            (self.cloud_card, "cloud_sync"),
        ):
            item = snapshot.get(key)
            if item:
                card.set_status(item.level, item.summary)
        paddle = snapshot.get("paddle")
        device_state = paddle.summary if paddle else "检测失败"
        self.device_label.setText(f"计算环境：{snapshot.device_label}　｜　{device_state}")

    def set_running(self, running: bool, text: str = "") -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)
        if text:
            self.status_label.setText(text)

    def _start(self) -> None:
        if not self.files:
            QMessageBox.information(self, "未选择文件", "请先选择或拖入待处理文件。")
            return
        self.start_requested.emit(list(self.files), self.selected_mode())


class ResultsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_task: TaskRecord | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        header = QHBoxLayout()
        self.title = QLabel("处理结果")
        self.title.setObjectName("pageTitle")
        self.open_dir_button = QPushButton("打开输出目录")
        self.open_dir_button.clicked.connect(self.open_output_directory)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.open_dir_button)
        root.addLayout(header)
        self.banner = QLabel("等待任务完成")
        self.banner.setObjectName("resultBanner")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)

        splitter = QSplitter()
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(260)
        self.file_list.itemSelectionChanged.connect(self._preview_selected)
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        splitter.addWidget(self.file_list)
        splitter.addWidget(self.viewer)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        copy_button = QPushButton("复制当前文本")
        copy_button.clicked.connect(self.viewer.selectAll)
        copy_button.clicked.connect(self.viewer.copy)
        footer.addStretch()
        footer.addWidget(copy_button)
        root.addLayout(footer)

    @staticmethod
    def _priority(mode: ProcessingMode, path: Path) -> int:
        preferred = {
            ProcessingMode.OCR: ["ocr.md", "ocr.txt"],
            ProcessingMode.SUMMARY: ["summary.md", "partial_summaries.md", "ocr.md"],
            ProcessingMode.SECURE_REVIEW: [
                "02_redacted_draft_REVIEW_REQUIRED.md",
                "04_review_report_RESTRICTED.md",
                "03_redacted_corrected_draft_REVIEW_REQUIRED.md",
                "01_ocr_original_restricted.md",
                "00_manifest.json",
                "05_findings_index_RESTRICTED.json",
            ],
        }[mode]
        try:
            return preferred.index(path.name)
        except ValueError:
            return len(preferred) + 1

    def load_task(self, task: TaskRecord) -> None:
        self.current_task = task
        self.title.setText(f"处理结果 · {task.mode.display_name}")
        if task.mode is ProcessingMode.SECURE_REVIEW:
            self.banner.setText("此结果必须经过人工复核；自动输出不得直接作为外发依据。")
            self.banner.setProperty("risk", True)
        elif task.mode is ProcessingMode.SUMMARY:
            self.banner.setText("摘要由本地模型生成，请结合 OCR 原文核对。")
            self.banner.setProperty("risk", False)
        else:
            self.banner.setText("OCR 已完成，请检查低置信度内容和版面识别结果。")
            self.banner.setProperty("risk", False)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        self.file_list.clear()
        files = sorted(task.output_files, key=lambda path: self._priority(task.mode, path))
        for path in files:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)
        if self.file_list.count():
            self.file_list.setCurrentRow(0)
        else:
            self.viewer.setPlainText("未发现可预览的输出文件，请查看运行日志。")

    def _preview_selected(self) -> None:
        items = self.file_list.selectedItems()
        if not items:
            return
        path = Path(items[0].data(Qt.ItemDataRole.UserRole))
        if path.suffix.casefold() not in {".md", ".txt", ".json", ".log"}:
            self.viewer.setPlainText(f"该文件不支持内置文本预览：\n{path}")
            return
        try:
            self.viewer.setPlainText(path.read_text(encoding="utf-8", errors="replace"))
        except OSError as error:
            self.viewer.setPlainText(f"无法读取文件：{error}")

    def open_output_directory(self) -> None:
        if self.current_task:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_task.output_dir)))


class EnvironmentPage(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        header = QHBoxLayout()
        title = QLabel("环境检测")
        title.setObjectName("pageTitle")
        refresh = QPushButton("重新检测")
        refresh.clicked.connect(self.refresh_requested)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh)
        root.addLayout(header)
        note = QLabel("关键状态同时显示在工作台；这里提供详细原因和修复依据。")
        note.setObjectName("mutedLabel")
        root.addWidget(note)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["检查项", "状态", "说明"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.table)

    def set_snapshot(self, snapshot: EnvironmentSnapshot) -> None:
        labels = {
            DiagnosticLevel.PASS: "通过",
            DiagnosticLevel.WARNING: "注意",
            DiagnosticLevel.FAIL: "失败",
            DiagnosticLevel.CHECKING: "检查中",
        }
        self.table.setRowCount(len(snapshot.items))
        for row, item in enumerate(snapshot.items):
            self.table.setItem(row, 0, QTableWidgetItem(item.label))
            self.table.setItem(row, 1, QTableWidgetItem(labels[item.level]))
            detail = item.summary if not item.detail else f"{item.summary}\n{item.detail}"
            self.table.setItem(row, 2, QTableWidgetItem(detail))
        self.table.resizeRowsToContents()


class HistoryPage(QWidget):
    task_open_requested = Signal(dict)

    def __init__(self, workspace_service: WorkspaceService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.workspace_service = workspace_service
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        header = QHBoxLayout()
        title = QLabel("最近任务")
        title.setObjectName("pageTitle")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh)
        root.addLayout(header)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["创建时间", "模式", "文件", "设备", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_selected)
        root.addWidget(self.table)
        self.records: list[dict[str, object]] = []

    def refresh(self) -> None:
        self.records = self.workspace_service.recent_tasks()
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            mode = ProcessingMode(str(record.get("mode", "ocr")))
            values = [
                str(record.get("created_at", "")),
                mode.display_name,
                Path(str(record.get("input_path", ""))).name,
                str(record.get("device", "")),
                str(record.get("status", "")),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _open_selected(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.records):
            self.task_open_requested.emit(self.records[row])


class TextInfoPage(QWidget):
    def __init__(self, title: str, body: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        content = QLabel(body)
        content.setWordWrap(True)
        content.setAlignment(Qt.AlignmentFlag.AlignTop)
        content.setObjectName("infoPanel")
        root.addWidget(heading)
        root.addWidget(content, 1)


class RulesPage(QWidget):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        header = QHBoxLayout()
        title = QLabel("敏感规则")
        title.setObjectName("pageTitle")
        open_button = QPushButton("打开规则文件")
        open_button.clicked.connect(self._open_file)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(open_button)
        root.addLayout(header)
        warning = QLabel("内置规则由后端维护；此处显示组织自定义敏感词。修改后需人工复核。")
        warning.setObjectName("mutedLabel")
        root.addWidget(warning)
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        root.addWidget(self.viewer)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.viewer.setPlainText(self.config.sensitive_terms.read_text(encoding="utf-8"))
        except OSError as error:
            self.viewer.setPlainText(f"无法读取规则文件：{error}")

    def _open_file(self) -> None:
        if self.config.sensitive_terms.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.sensitive_terms)))


class LogsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        title = QLabel("运行日志")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        root.addWidget(self.viewer)

    def append(self, text: str) -> None:
        self.viewer.moveCursor(self.viewer.textCursor().MoveOperation.End)
        self.viewer.insertPlainText(text)
        self.viewer.ensureCursorVisible()


def task_from_payload(payload: dict[str, object]) -> TaskRecord:
    return TaskRecord(
        task_id=str(payload["task_id"]),
        created_at=str(payload["created_at"]),
        mode=ProcessingMode(str(payload["mode"])),
        source_path=Path(str(payload["source_path"])),
        input_path=Path(str(payload["input_path"])),
        task_dir=Path(str(payload["task_dir"])),
        output_dir=Path(str(payload["output_dir"])),
        log_dir=Path(str(payload["log_dir"])),
        input_sha256=str(payload["input_sha256"]),
        device=str(payload.get("device", "unknown")),
        status=str(payload.get("status", "unknown")),
        exit_code=payload.get("exit_code") if isinstance(payload.get("exit_code"), int) else None,
        output_files=[Path(str(path)) for path in payload.get("output_files", [])],
    )
