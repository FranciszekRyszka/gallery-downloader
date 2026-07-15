"""Runtime filesystem locations.

Resolves where the app reads/writes data so it works both when run from
source (``python main.py``) and when frozen into a single-file executable
with PyInstaller. When frozen, ``__file__`` points inside PyInstaller's
temporary extraction directory, which is read-only-ish and wiped on exit — so
we instead anchor writable data next to the ``.exe`` itself.
"""

from __future__ import annotations

import sys
from pathlib import Path


def base_dir() -> Path:
    """Folder to anchor writable runtime data (downloads, logs).

    Frozen: the directory containing the executable (so ``downloads/`` and
    ``logs/`` sit next to the ``.exe``). From source: the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = base_dir()
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
