from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from secureocr_desktop.domain.models import DiagnosticLevel


class StatusCard(QFrame):
    COLORS = {
        DiagnosticLevel.PASS: ("#E7F7EE", "#16794B", "●"),
        DiagnosticLevel.WARNING: ("#FFF4D6", "#9A6700", "●"),
        DiagnosticLevel.FAIL: ("#FDE8E7", "#B42318", "●"),
        DiagnosticLevel.CHECKING: ("#E9EEF5", "#52606D", "●"),
    }

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statusTitle")
        self.value_label = QLabel("正在检查…")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        self.set_status(DiagnosticLevel.CHECKING, "正在检查…")

    def set_status(self, level: DiagnosticLevel, text: str) -> None:
        background, foreground, dot = self.COLORS[level]
        self.value_label.setText(f"{dot} {text}")
        self.setStyleSheet(
            f"QFrame#statusCard {{background:{background}; border:1px solid {foreground}33; "
            f"border-radius:10px;}} QFrame#statusCard QLabel {{color:{foreground};}}"
        )


class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(145)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("将文件拖到这里")
        title.setObjectName("dropTitle")
        subtitle = QLabel("支持 PDF、PNG、JPG、JPEG、BMP、TIF、TIFF、MD、TXT")
        subtitle.setObjectName("mutedLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        files = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self.files_dropped.emit(files)
            event.acceptProposedAction()

