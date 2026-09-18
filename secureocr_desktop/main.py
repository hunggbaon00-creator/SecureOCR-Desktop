from __future__ import annotations

import sys
from pathlib import Path


def _require_python_311() -> None:
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(
            "SecureOCR Desktop 必须使用 Python 3.11 运行；"
            f"当前解释器为 Python {sys.version_info.major}.{sys.version_info.minor}。"
        )


def main() -> int:
    _require_python_311()
    from PySide6.QtWidgets import QApplication

    from secureocr_desktop.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("SecureOCR Desktop")
    app.setOrganizationName("SecureOCR")
    app.setStyle("Fusion")
    stylesheet = Path(__file__).with_name("resources") / "style.qss"
    if stylesheet.is_file():
        app.setStyleSheet(stylesheet.read_text(encoding="utf-8"))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

