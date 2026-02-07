"""文本注入模块 - 通过剪贴板粘贴方式注入文本"""

import time
import keyboard
import win32clipboard
import win32con


def _get_clipboard_text() -> str | None:
    """获取当前剪贴板文本内容"""
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return data
        return None
    except Exception:
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _set_clipboard_text(text: str) -> None:
    """设置剪贴板文本内容"""
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()


def inject_text(text: str) -> None:
    """
    通过剪贴板粘贴方式注入文本到当前光标位置
    
    流程：备份剪贴板 → 写入文本 → 模拟 Ctrl+V → 还原剪贴板
    """
    # 1. 备份当前剪贴板
    original = _get_clipboard_text()

    # 2. 写入精修文本
    _set_clipboard_text(text)

    # 3. 模拟 Ctrl+V（用 keyboard 库，比 ctypes SendInput 可靠）
    time.sleep(0.05)
    keyboard.send("ctrl+v")

    # 4. 延迟后还原剪贴板
    time.sleep(0.2)
    if original is not None:
        try:
            _set_clipboard_text(original)
        except Exception:
            pass
