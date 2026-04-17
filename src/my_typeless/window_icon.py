"""Win32 helpers to set HWND icon for the PyWebView window on Windows."""

import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

from my_typeless.icon_builder import ensure_app_ico

logger = logging.getLogger(__name__)

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_SHARED = 0x00008000
SM_CXICON = 11
SM_CXSMICON = 49


def _load_hicon(ico_path: Path, size: int):
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    return user32.LoadImageW(
        None,
        str(ico_path),
        IMAGE_ICON,
        size,
        size,
        LR_LOADFROMFILE | LR_SHARED,
    )


def apply_window_icon(window) -> None:
    """为 pywebview 窗口的 HWND 设置应用图标"""
    if sys.platform != "win32":
        return
    ico_path = ensure_app_ico()
    if ico_path is None:
        logger.info("app_icon.ico unavailable; skipping HWND icon")
        return
    try:
        hwnd = int(getattr(window, "native_handle", 0) or 0)
        if not hwnd:
            # 兼容某些 pywebview 构建：通过窗口标题查找
            hwnd = ctypes.windll.user32.FindWindowW(None, "My Typeless")
        if not hwnd:
            logger.warning("Failed to obtain HWND for window icon")
            return
        user32 = ctypes.windll.user32
        big = user32.GetSystemMetrics(SM_CXICON) or 32
        small = user32.GetSystemMetrics(SM_CXSMICON) or 16
        h_big = _load_hicon(ico_path, big)
        h_small = _load_hicon(ico_path, small)
        if h_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
        if h_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
    except Exception as e:
        logger.warning("Failed to set window icon: %s", e)
