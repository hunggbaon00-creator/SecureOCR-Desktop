from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    backend_root: Path
    backend_python: Path
    workspace_root: Path
    ocr_script: Path
    summary_script: Path
    secure_script: Path
    sensitive_terms: Path
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:4b"

    @classmethod
    def load(cls) -> AppConfig:
        backend_root = Path(os.environ.get("SECUREOCR_BACKEND_ROOT", r"C:\SecureOCR"))
        backend_python = Path(
            os.environ.get(
                "SECUREOCR_BACKEND_PYTHON",
                str(backend_root / "app" / ".venv" / "Scripts" / "python.exe"),
            )
        )
        workspace_root = Path(
            os.environ.get("SECUREOCR_WORKSPACE", str(backend_root / "workspace"))
        )
        app_root = backend_root / "app"
        return cls(
            backend_root=backend_root,
            backend_python=backend_python,
            workspace_root=workspace_root,
            ocr_script=app_root / "ocr.py",
            summary_script=app_root / "workflow.py",
            secure_script=app_root / "secure_redact.py",
            sensitive_terms=backend_root / "config" / "sensitive_terms.txt",
        )
