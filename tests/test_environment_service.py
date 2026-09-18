from pathlib import Path

from secureocr_desktop.services.environment_service import EnvironmentService


def test_cloud_sync_path_detects_onedrive(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "OneDrive - Example"
    target = root / "SecureOCR"
    monkeypatch.setenv("OneDrive", str(root))
    assert EnvironmentService.is_cloud_sync_path(target)


def test_normal_local_path_is_not_cloud_sync(monkeypatch, tmp_path: Path) -> None:
    for name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial", "Dropbox"):
        monkeypatch.delenv(name, raising=False)
    assert not EnvironmentService.is_cloud_sync_path(tmp_path / "secureocr_workspace")

