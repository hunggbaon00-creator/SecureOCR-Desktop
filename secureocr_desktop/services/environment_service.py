from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from secureocr_desktop.config import AppConfig
from secureocr_desktop.domain.models import (
    DiagnosticItem,
    DiagnosticLevel,
    EnvironmentSnapshot,
)


class EnvironmentService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @staticmethod
    def is_local_path(path: Path) -> bool:
        raw = str(path)
        if raw.startswith(("\\\\", "//")):
            return False
        if os.name == "nt" and path.drive:
            drive_root = f"{path.drive}\\"
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
            return drive_type != 4  # DRIVE_REMOTE
        return True

    @staticmethod
    def is_cloud_sync_path(path: Path) -> bool:
        resolved = str(path.resolve(strict=False)).casefold()
        sync_roots = {
            os.environ.get("OneDrive"),
            os.environ.get("OneDriveConsumer"),
            os.environ.get("OneDriveCommercial"),
            os.environ.get("Dropbox"),
            os.environ.get("GoogleDrive"),
        }
        for root in sync_roots:
            if root and resolved.startswith(str(Path(root).resolve(strict=False)).casefold()):
                return True
        suspicious_parts = {"onedrive", "dropbox", "google drive", "googledrive", "icloud drive"}
        return any(part.casefold() in suspicious_parts for part in path.parts)

    @staticmethod
    def internet_connected() -> bool:
        if os.name != "nt":
            return False
        flags = ctypes.c_ulong()
        return bool(ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0))

    def _inspect_paddle(self) -> tuple[DiagnosticItem, str, str]:
        if not self.config.backend_python.is_file():
            return (
                DiagnosticItem(
                    "paddle",
                    "Paddle 计算环境",
                    DiagnosticLevel.FAIL,
                    "后端 Python 不存在",
                ),
                "unknown",
                "",
            )
        probe = r"""
import json
import paddle
compiled = bool(paddle.is_compiled_with_cuda())
count = int(paddle.device.cuda.device_count()) if compiled else 0
device = "gpu:0" if compiled and count > 0 else "cpu"
paddle.set_device(device)
value = float(paddle.ones([1]).numpy()[0])
print(json.dumps({"version": paddle.__version__, "compiled_cuda": compiled,
                  "gpu_count": count, "device": device, "probe": value}))
"""
        try:
            result = subprocess.run(
                [str(self.config.backend_python), "-c", probe],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            data = json.loads(result.stdout.strip().splitlines()[-1])
            device = str(data["device"])
            version = str(data["version"])
            if device.startswith("gpu"):
                summary = f"GPU 可用 · Paddle {version} · {data['gpu_count']} 块 GPU"
            else:
                summary = f"CPU 可用 · Paddle {version}"
            return (
                DiagnosticItem("paddle", "Paddle 计算环境", DiagnosticLevel.PASS, summary),
                device,
                version,
            )
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError, KeyError) as error:
            return (
                DiagnosticItem(
                    "paddle",
                    "Paddle 计算环境",
                    DiagnosticLevel.FAIL,
                    "计算环境不可用",
                    str(error),
                ),
                "unknown",
                "",
            )

    def _inspect_ollama(self) -> tuple[DiagnosticItem, DiagnosticItem, bool]:
        request = Request(f"{self.config.ollama_host}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            names = {str(item.get("name", "")) for item in payload.get("models", [])}
            base_names = {name.split(":")[0] for name in names}
            wanted = self.config.ollama_model
            installed = wanted in names or wanted.split(":")[0] in base_names
            ollama = DiagnosticItem(
                "ollama",
                "Ollama 服务",
                DiagnosticLevel.PASS,
                "本机服务正在运行",
            )
            model = DiagnosticItem(
                "model",
                "本地模型",
                DiagnosticLevel.PASS if installed else DiagnosticLevel.FAIL,
                f"{wanted} 已安装" if installed else f"未找到 {wanted}",
            )
            return ollama, model, installed
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            return (
                DiagnosticItem(
                    "ollama",
                    "Ollama 服务",
                    DiagnosticLevel.FAIL,
                    "本机 Ollama 未响应",
                    str(error),
                ),
                DiagnosticItem(
                    "model",
                    "本地模型",
                    DiagnosticLevel.FAIL,
                    "无法检查模型",
                ),
                False,
            )

    def _cloud_disabled(self) -> bool:
        if os.environ.get("OLLAMA_NO_CLOUD") == "1":
            return True
        server_json = Path.home() / ".ollama" / "server.json"
        try:
            return json.loads(server_json.read_text(encoding="utf-8")).get(
                "disable_ollama_cloud"
            ) is True
        except (OSError, json.JSONDecodeError):
            return False

    def inspect(self) -> EnvironmentSnapshot:
        items: list[DiagnosticItem] = []
        gui_ok = sys.version_info[:2] == (3, 11)
        items.append(
            DiagnosticItem(
                "gui_python",
                "桌面应用 Python",
                DiagnosticLevel.PASS if gui_ok else DiagnosticLevel.FAIL,
                (
                    f"Python {sys.version_info.major}.{sys.version_info.minor}."
                    f"{sys.version_info.micro}"
                ),
                "本项目只允许使用 Python 3.11。",
            )
        )

        backend_exists = self.config.backend_python.is_file()
        items.append(
            DiagnosticItem(
                "backend_python",
                "OCR 后端 Python",
                DiagnosticLevel.PASS if backend_exists else DiagnosticLevel.FAIL,
                str(self.config.backend_python),
            )
        )

        paddle, device, paddle_version = self._inspect_paddle()
        items.append(paddle)

        parsed = urlparse(self.config.ollama_host)
        local_host = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        items.append(
            DiagnosticItem(
                "ollama_local",
                "工具链位置",
                DiagnosticLevel.PASS if local_host else DiagnosticLevel.FAIL,
                "Ollama 仅使用本机回环地址" if local_host else "检测到远程 Ollama 地址",
                self.config.ollama_host,
            )
        )

        ollama, model, installed = self._inspect_ollama()
        items.extend((ollama, model))

        cloud_disabled = self._cloud_disabled()
        items.append(
            DiagnosticItem(
                "cloud_disabled",
                "Ollama 云功能",
                DiagnosticLevel.PASS if cloud_disabled else DiagnosticLevel.FAIL,
                "已检测到禁用配置" if cloud_disabled else "未检测到 OLLAMA_NO_CLOUD=1",
            )
        )

        connected = self.internet_connected()
        items.append(
            DiagnosticItem(
                "network",
                "系统网络",
                DiagnosticLevel.WARNING if connected else DiagnosticLevel.PASS,
                "系统当前可能连接互联网" if connected else "未检测到互联网连接",
                "此状态读取 Windows 连接状态，不会主动访问外网。",
            )
        )

        workspace_local = self.is_local_path(self.config.workspace_root)
        items.append(
            DiagnosticItem(
                "workspace",
                "工作区",
                DiagnosticLevel.PASS if workspace_local else DiagnosticLevel.FAIL,
                "本地磁盘目录" if workspace_local else "网络或远程目录",
                str(self.config.workspace_root),
            )
        )

        cloud_sync = self.is_cloud_sync_path(self.config.workspace_root)
        items.append(
            DiagnosticItem(
                "cloud_sync",
                "云同步目录",
                DiagnosticLevel.FAIL if cloud_sync else DiagnosticLevel.PASS,
                "检测到常见云同步路径" if cloud_sync else "未检测到常见云同步路径",
                "该检查不能替代单位终端和同步软件管理策略。",
            )
        )

        label = "检测失败"
        if device.startswith("gpu"):
            label = "NVIDIA GPU · Paddle CUDA"
        elif device == "cpu":
            label = "CPU · Paddle CPU"
        return EnvironmentSnapshot(tuple(items), device, label, paddle_version, installed)
