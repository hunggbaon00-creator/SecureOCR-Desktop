from pathlib import Path

from secureocr_desktop.application.process_runner import ProcessRunner
from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import ProcessingMode, TaskRecord


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        backend_root=tmp_path,
        backend_python=tmp_path / "python.exe",
        workspace_root=tmp_path / "workspace",
        ocr_script=tmp_path / "ocr.py",
        summary_script=tmp_path / "workflow.py",
        secure_script=tmp_path / "secure_redact.py",
        sensitive_terms=tmp_path / "terms.txt",
    )


def make_task(tmp_path: Path, mode: ProcessingMode) -> TaskRecord:
    return TaskRecord(
        task_id="task-1",
        created_at="2026-09-18T00:00:00+08:00",
        mode=mode,
        source_path=tmp_path / "source.pdf",
        input_path=tmp_path / "input" / "source.pdf",
        task_dir=tmp_path,
        output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        input_sha256="0" * 64,
        device="gpu:0",
    )


def test_secure_arguments_include_detected_device(qapp, tmp_path: Path) -> None:
    runner = ProcessRunner(make_config(tmp_path))
    script, arguments = runner.build_arguments(make_task(tmp_path, ProcessingMode.SECURE_REVIEW))
    assert script.name == "secure_redact.py"
    assert arguments[arguments.index("--device") + 1] == "gpu:0"
    assert "--ollama-host" in arguments


def test_ocr_arguments_use_task_output(qapp, tmp_path: Path) -> None:
    runner = ProcessRunner(make_config(tmp_path))
    _, arguments = runner.build_arguments(make_task(tmp_path, ProcessingMode.OCR))
    assert arguments[-2] == "--output"
    assert Path(arguments[-1]).name == "output"

