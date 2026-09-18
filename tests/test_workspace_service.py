import json
from pathlib import Path

from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import ProcessingMode
from secureocr_desktop.services.workspace_service import WorkspaceService


def make_config(tmp_path: Path) -> AppConfig:
    backend = tmp_path / "backend"
    return AppConfig(
        backend_root=backend,
        backend_python=backend / "python.exe",
        workspace_root=tmp_path / "workspace",
        ocr_script=backend / "ocr.py",
        summary_script=backend / "workflow.py",
        secure_script=backend / "secure_redact.py",
        sensitive_terms=backend / "sensitive_terms.txt",
    )


def test_create_task_copies_and_hashes_input(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"synthetic test document")
    service = WorkspaceService(make_config(tmp_path))

    task = service.create_task(source, ProcessingMode.OCR, "gpu:0")

    assert task.input_path.read_bytes() == source.read_bytes()
    assert len(task.input_sha256) == 64
    payload = json.loads((task.task_dir / "task.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "ocr"
    assert payload["device"] == "gpu:0"
    assert payload["status"] == "queued"


def test_secure_mode_accepts_text_input(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.txt"
    source.write_text("synthetic only", encoding="utf-8")
    service = WorkspaceService(make_config(tmp_path))
    task = service.create_task(source, ProcessingMode.SECURE_REVIEW, "gpu:0")
    assert task.input_path.suffix == ".txt"

