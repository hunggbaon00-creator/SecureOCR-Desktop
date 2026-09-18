from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ProcessingMode(StrEnum):
    OCR = "ocr"
    SUMMARY = "summary"
    SECURE_REVIEW = "secure_review"

    @property
    def display_name(self) -> str:
        return {
            self.OCR: "仅 OCR",
            self.SUMMARY: "OCR 与内容总结",
            self.SECURE_REVIEW: "OCR、敏感检查与脱敏",
        }[self]

    @property
    def supported_extensions(self) -> set[str]:
        image_document = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
        if self is self.SECURE_REVIEW:
            return image_document | {".md", ".txt"}
        return image_document


class DiagnosticLevel(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    CHECKING = "checking"


@dataclass(frozen=True, slots=True)
class DiagnosticItem:
    key: str
    label: str
    level: DiagnosticLevel
    summary: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    items: tuple[DiagnosticItem, ...]
    device: str = "unknown"
    device_label: str = "检测中"
    paddle_version: str = ""
    model_installed: bool = False

    def get(self, key: str) -> DiagnosticItem | None:
        return next((item for item in self.items if item.key == key), None)

    @property
    def can_process(self) -> bool:
        required = {"gui_python", "backend_python", "paddle", "workspace"}
        return all(
            item.level is not DiagnosticLevel.FAIL
            for item in self.items
            if item.key in required
        )

    @property
    def can_use_ollama(self) -> bool:
        required = {"ollama", "model", "ollama_local"}
        found = {item.key: item for item in self.items if item.key in required}
        return required <= found.keys() and all(
            found[key].level is DiagnosticLevel.PASS for key in required
        )

    @property
    def can_secure_review(self) -> bool:
        if not self.can_process or not self.can_use_ollama:
            return False
        blocking = {"workspace", "cloud_sync", "ollama_local", "cloud_disabled"}
        return all(
            item.level is DiagnosticLevel.PASS
            for item in self.items
            if item.key in blocking
        )


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    created_at: str
    mode: ProcessingMode
    source_path: Path
    input_path: Path
    task_dir: Path
    output_dir: Path
    log_dir: Path
    input_sha256: str
    device: str
    status: str = "queued"
    exit_code: int | None = None
    output_files: list[Path] = field(default_factory=list)
