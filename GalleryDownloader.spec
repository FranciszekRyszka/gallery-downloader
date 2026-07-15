# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Gallery Downloader.

Produces a single-file, console-mode Windows executable. Console mode is
required: the app is a Textual TUI and needs a terminal to render into, so
double-clicking the .exe opens a console window and runs the UI inside it.

Build:  pyinstaller GalleryDownloader.spec   (or run build.ps1)
Output: dist/GalleryDownloader.exe
"""

from PyInstaller.utils.hooks import collect_all

# Textual ships CSS/theme data files and dynamically imported widgets that
# static analysis misses; collect everything so the frozen app renders.
datas, binaries, hiddenimports = [], [], []
for _pkg in ("textual",):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# `sqlite3` (used by db/history.py) loads the `_sqlite3` C-extension, which
# PyInstaller's static analysis can miss — leaving the app to crash on launch
# with "No module named '_sqlite3'". Naming it explicitly pulls in the .pyd
# and, via its link dependency, the sqlite3.dll it needs.
hiddenimports += ["_sqlite3"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GalleryDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # TUI: keep the console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
