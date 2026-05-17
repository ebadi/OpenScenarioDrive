"""
Entry point - reads environment and launches the Qt application.

Run inside the container:
    python3 -m gui

Run locally (with esmini libs built):
    ESMINI_LIB_DIR=.../esmini ESMINI_RESOURCE_PATH=.../resources python3 -m gui
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    from .main_window import MainWindow

    lib_dir = os.environ.get("ESMINI_LIB_DIR", "")
    resource_root = os.environ.get("ESMINI_RESOURCE_PATH", "")
    scenario = os.environ.get("SCENARIO", "")

    app = QApplication(sys.argv)
    app.setApplicationName("esmini Controller")
    app.setStyle("Fusion")

    window = MainWindow(lib_dir=lib_dir, resource_root=resource_root)
    window.showMaximized()

    if scenario:
        window.load_scenario(scenario)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
