"""Entry point for the gallery downloader."""

from __future__ import annotations

import os
import sys

APP_TITLE = "Gallery Downloader"


def _relaunch_in_windows_terminal() -> bool:
    """Re-open the frozen app in Windows Terminal for much better rendering.

    Double-clicking a console ``.exe`` opens the legacy console (conhost),
    where Textual's colours and box-drawing look poor. Windows Terminal renders
    it properly, so when we're a frozen build started outside Windows Terminal
    and ``wt.exe`` is available, relaunch there and let this process exit.

    Set ``GDL_NO_RELAUNCH=1`` to opt out. Returns True if a relaunch started.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    # Already inside Windows Terminal, or explicitly disabled.
    if os.environ.get("WT_SESSION") or os.environ.get("GDL_NO_RELAUNCH"):
        return False

    import shutil
    import subprocess

    wt = shutil.which("wt")
    if not wt:
        return False
    env = dict(os.environ, GDL_NO_RELAUNCH="1")
    try:
        # `wt --title <name> -- <exe>` opens Windows Terminal running our exe.
        subprocess.Popen(
            [wt, "--title", APP_TITLE, "--", sys.executable],
            env=env,
            close_fds=True,
        )
    except OSError:
        return False
    return True


def _configure_windows_console() -> None:
    """Give the console a real title and turn on UTF-8 + ANSI rendering.

    Without this the window title is the full ``.exe`` path, and box-drawing /
    check-mark glyphs and colours render as garbage in the legacy console.
    """
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    # Window title (otherwise Windows shows the whole .exe path).
    kernel32.SetConsoleTitleW(APP_TITLE)
    # UTF-8 code pages so Unicode glyphs render.
    try:
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except OSError:
        pass
    # Enable virtual-terminal processing (ANSI colours / cursor control).
    enable_vt = 0x0004
    std_output_handle = -11
    try:
        handle = kernel32.GetStdHandle(std_output_handle)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | enable_vt)
    except OSError:
        pass
    _use_truetype_console_font()


def _use_truetype_console_font() -> None:
    """Switch the legacy console to a TrueType font (Consolas).

    Textual pads button labels with non-breaking spaces (U+00A0). The classic
    console's default *raster* font has no glyph for it, so it renders as a box
    or ``?`` around every button. A TrueType font renders it as a normal blank.
    Harmless / ignored in Windows Terminal.
    """
    import ctypes
    from ctypes import wintypes

    lf_facesize = 32
    std_output_handle = -11

    class _COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class _CONSOLE_FONT_INFOEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("nFont", ctypes.c_ulong),
            ("dwFontSize", _COORD),
            ("FontFamily", ctypes.c_uint),
            ("FontWeight", ctypes.c_uint),
            ("FaceName", ctypes.c_wchar * lf_facesize),
        ]

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
        proto = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(_CONSOLE_FONT_INFOEX),
        ]
        kernel32.GetCurrentConsoleFontEx.argtypes = proto
        kernel32.SetCurrentConsoleFontEx.argtypes = proto

        handle = kernel32.GetStdHandle(std_output_handle)
        font = _CONSOLE_FONT_INFOEX()
        font.cbSize = ctypes.sizeof(_CONSOLE_FONT_INFOEX)
        kernel32.GetCurrentConsoleFontEx(handle, False, ctypes.byref(font))
        font.FaceName = "Consolas"
        font.FontFamily = 54  # FF_MODERN | TMPF_TRUETYPE | TMPF_VECTOR
        font.FontWeight = 400
        if font.dwFontSize.Y <= 0:
            font.dwFontSize = _COORD(0, 16)
        kernel32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(font))
    except (OSError, AttributeError, ValueError):
        pass


def main() -> None:
    if _relaunch_in_windows_terminal():
        return
    _configure_windows_console()
    from app import GalleryDownloaderApp

    GalleryDownloaderApp().run()


if __name__ == "__main__":
    main()
