"""
PyInstaller entry point for OpenScenarioDrive.

When running from a frozen bundle (sys.frozen == True), sys._MEIPASS points to
the directory where PyInstaller extracted all bundled files.  We set the esmini
environment variables to that directory so the ctypes wrapper finds the native
libraries and the resources/ tree that were bundled alongside the Python code.
"""

from __future__ import annotations

import os
import sys


def _configure_frozen_paths() -> None:
    # sys._MEIPASS is the _internal/ subdirectory where PyInstaller 6+ places
    # all collected binaries and data.  We must override (not setdefault) because
    # AppRun exports ESMINI_LIB_DIR pointing at usr/bin/ which predates _internal/.
    base = sys._MEIPASS  # type: ignore[attr-defined]
    os.environ["ESMINI_LIB_DIR"] = base
    os.environ["ESMINI_RESOURCE_PATH"] = os.path.join(base, "resources")


if getattr(sys, "frozen", False):
    _configure_frozen_paths()

from gui.main import main  # noqa: E402 - must come after env setup

main()
