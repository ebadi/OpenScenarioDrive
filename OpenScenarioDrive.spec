# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for OpenScenarioDrive.

Before running pyinstaller, stage the esmini native libraries into
the esmini_libs/ directory at the repo root (see .github/workflows/build.yml).

  esmini_libs/
    libesminiLib.so      (Linux)
    libesminiRMLib.so
    esminiLib.dll        (Windows)
    esminiRMLib.dll
    libesminiLib.dylib   (macOS)
    libesminiRMLib.dylib
    scenarios/           (esmini bundled assets - xosc, xodr, models, …)
"""

import platform
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# ---------------------------------------------------------------------------
# Collect PyQt6 - plugins, Qt shared libs, translations
# ---------------------------------------------------------------------------
pyqt6_datas, pyqt6_binaries, pyqt6_hidden = collect_all("PyQt6")

# ---------------------------------------------------------------------------
# Stage esmini native libraries
# ---------------------------------------------------------------------------
_lib_dir = Path("esmini_libs")

_system = platform.system()
if _system == "Windows":
    _lib_patterns = ["*.dll"]
elif _system == "Darwin":
    _lib_patterns = ["*.dylib", "*.so"]
else:
    _lib_patterns = ["*.so", "*.so.*"]

esmini_binaries = []
for pat in _lib_patterns:
    for lib in _lib_dir.glob(pat):
        esmini_binaries.append((str(lib), "."))

esmini_datas = []
_res = _lib_dir / "scenarios"
if _res.exists():
    esmini_datas.append((str(_res), "scenarios"))

# ---------------------------------------------------------------------------
# Linux - bundle xcb libs required by Qt 6.5+ xcb platform plugin.
# They must live inside the PyInstaller bundle so the dynamic linker finds
# them when libqxcb.so (collected by collect_all) opens them at runtime.
# ---------------------------------------------------------------------------
import glob as _glob

xcb_binaries = []
if _system == "Linux":
    _xcb_patterns = [
        "libxcb-cursor.so*",
        "libxcb-icccm.so*",
        "libxcb-image.so*",
        "libxcb-keysyms.so*",
        "libxcb-randr.so*",
        "libxcb-render-util.so*",
        "libxcb-shape.so*",
        "libxcb-xinerama.so*",
        "libxcb-xkb.so*",
        "libxkbcommon.so*",
        "libxkbcommon-x11.so*",
    ]
    _seen = set()
    for _pat in _xcb_patterns:
        for _candidate in (
            _glob.glob(f"/usr/lib/x86_64-linux-gnu/{_pat}") +
            _glob.glob(f"/usr/lib/{_pat}")
        ):
            _name = Path(_candidate).name
            if _name not in _seen:
                _seen.add(_name)
                xcb_binaries.append((_candidate, "."))

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["main_entry.py"],
    pathex=["."],
    binaries=esmini_binaries + pyqt6_binaries + xcb_binaries,
    datas=esmini_datas + pyqt6_datas,
    hiddenimports=pyqt6_hidden + [
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtPrintSupport",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Strip heavy optional Qt modules we don't use
    excludes=[
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngine",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtBluetooth",
        "PyQt6.QtNfc",
        "PyQt6.QtSerialPort",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpenScenarioDrive",
    debug=False,
    strip=False,
    upx=True,
    console=False,          # no console window on Windows / macOS
    icon="installer/icon.ico" if _system == "Windows" else "installer/icon.png",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OpenScenarioDrive",
)

# macOS - wrap the collected folder into a proper .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="OpenScenarioDrive.app",
        icon="installer/icon.icns",
        bundle_identifier="se.Hamid.OpenScenarioDrive",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleName": "OpenScenarioDrive",
        },
        target_arch=os.environ.get("PYINSTALLER_TARGET_ARCH") or None,
    )
