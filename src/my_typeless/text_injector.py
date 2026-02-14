"""文本注入模块 - 通过剪贴板粘贴方式注入文本"""

import time
import threading
import keyboard
import win32clipboard
import win32con

# 全局状态：用于异步还原剪贴板，避免阻塞 UI 线程，并防止快速连续注入时的冲突
_lock = threading.Lock()
_restore_timer: threading.Timer | None = None
_original_clipboard: str | None = None
_restore_id = 0


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
    
    流程：备份剪贴板 → 写入文本 → 模拟 Ctrl+V → 异步延迟还原剪贴板
    """
    global _restore_timer, _original_clipboard, _restore_id

    with _lock:
        # 如果有待执行的还原任务，取消它（防抖：连续注入时只还原最后一次前的原始内容）
        if _restore_timer:
            _restore_timer.cancel()
            _restore_timer = None

        # 仅当尚未备份时备份当前剪贴板（保留最初的原始内容）
        if _original_clipboard is None:
            _original_clipboard = _get_clipboard_text()

        # 写入精修文本
        _set_clipboard_text(text)

        # 模拟 Ctrl+V（用 keyboard 库，比 ctypes SendInput 可靠）
        # 等待剪贴板写入生效
        time.sleep(0.05)
        keyboard.send("ctrl+v")

        # 启动异步任务延迟还原剪贴板
        _restore_id += 1
        current_id = _restore_id

        # 定义还原任务
        def restore_task():
            global _restore_timer, _original_clipboard
            with _lock:
                # 检查是否已有新任务插队（ID 不匹配则放弃还原）
                if _restore_id != current_id:
                    return

                if _original_clipboard is not None:
                    try:
                        _set_clipboard_text(_original_clipboard)
                    except Exception:
                        pass
                    _original_clipboard = None

                _restore_timer = None

        # 0.2秒后执行还原（给系统处理 Ctrl+V 的时间）
        _restore_timer = threading.Timer(0.2, restore_task)
        _restore_timer.daemon = True
        _restore_timer.start()
