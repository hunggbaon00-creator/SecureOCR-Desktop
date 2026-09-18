from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import ProcessingMode, TaskRecord
from secureocr_desktop.services.environment_service import EnvironmentService


class WorkspaceError(RuntimeError):
    pass


class WorkspaceService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def sanitize_name(name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
        return cleaned[:120] or "document"

    def validate_input(self, path: Path, mode: ProcessingMode) -> None:
        if not path.is_file():
            raise WorkspaceError(f"找不到文件：{path}")
        if path.suffix.casefold() not in mode.supported_extensions:
            raise WorkspaceError(f"{mode.display_name} 不支持 {path.suffix or '无扩展名'} 文件")
        if not EnvironmentService.is_local_path(path):
            raise WorkspaceError("禁止直接处理网络或远程路径中的文件")
        if EnvironmentService.is_cloud_sync_path(path):
            raise WorkspaceError("输入文件位于常见云同步目录，请先移动到本地非同步目录")

    def create_task(self, source: Path, mode: ProcessingMode, device: str) -> TaskRecord:
        source = source.resolve()
        self.validate_input(source, mode)
        self.config.workspace_root.mkdir(parents=True, exist_ok=True)
        now = datetime.now().astimezone()
        task_id = f"{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        stem = self.sanitize_name(source.stem)
        task_dir = self.config.workspace_root / f"{task_id}_{stem}"
        input_dir = task_dir / "input"
        output_dir = task_dir / "output"
        log_dir = task_dir / "logs"
        for directory in (input_dir, output_dir, log_dir):
            directory.mkdir(parents=True, exist_ok=False)
        input_path = input_dir / self.sanitize_name(source.name)
        shutil.copy2(source, input_path)
        record = TaskRecord(
            task_id=task_id,
            created_at=now.isoformat(),
            mode=mode,
            source_path=source,
            input_path=input_path,
            task_dir=task_dir,
            output_dir=output_dir,
            log_dir=log_dir,
            input_sha256=self.sha256_file(input_path),
            device=device,
        )
        self.save_task(record)
        return record

    def save_task(self, task: TaskRecord) -> None:
        payload = asdict(task)
        payload["mode"] = task.mode.value
        for key in ("source_path", "input_path", "task_dir", "output_dir", "log_dir"):
            payload[key] = str(payload[key])
        payload["output_files"] = [str(path) for path in task.output_files]
        target = task.task_dir / "task.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(target)

    def discover_outputs(self, task: TaskRecord) -> list[Path]:
        return sorted(
            (path for path in task.output_dir.rglob("*") if path.is_file()),
            key=lambda item: str(item).casefold(),
        )

    def recent_tasks(self, limit: int = 100) -> list[dict[str, object]]:
        if not self.config.workspace_root.exists():
            return []
        records: list[dict[str, object]] = []
        task_files = sorted(
            self.config.workspace_root.glob("*/task.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for task_file in task_files[:limit]:
            try:
                records.append(json.loads(task_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return records

