"""热键捕获按钮 - 点击后进入监听状态，使用 keyboard 库捕获按键以区分左右修饰键"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, pyqtSignal


class HotkeyButton(QPushButton):

    hotkey_changed = pyqtSignal(str)

    # 允许作为热键的键名集合（keyboard 库的名称）
    _ALLOWED_KEYS = {
        "left alt", "right alt", "alt",
        "left ctrl", "right ctrl", "ctrl",
        "left shift", "right shift", "shift",
        "left windows", "right windows",
        "caps lock", "tab", "space",
        "f1", "f2", "f3", "f4", "f5", "f6",
        "f7", "f8", "f9", "f10", "f11", "f12",
    }

    def __init__(self, current_hotkey: str = "right alt"):
        super().__init__()
        self._hotkey = current_hotkey
        self._listening = False
        self._kb_hook = None
        self._update_display()
        self.clicked.connect(self._start_listening)
        self.setFixedHeight(32)
        self.setMinimumWidth(100)

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def _update_display(self) -> None:
        if self._listening:
            self.setText("⌨  Press a key...")
            self.setStyleSheet("""
                QPushButton {
                    background: #EFF6FF; border: 2px solid #2b8cee;
                    border-radius: 4px; padding: 4px 12px; color: #2b8cee;
                    font-size: 12px; font-weight: 500;
                }
            """)
        else:
            self.setText(f"⌨  {self._hotkey.title()}")
            self.setStyleSheet("""
                QPushButton {
                    background: #f3f4f6; border: 1px solid #d1d5db;
                    border-radius: 4px; padding: 4px 12px; color: #1a1a1a;
                    font-size: 12px; font-weight: 500;
                }
                QPushButton:hover { background: #e5e7eb; }
            """)

    def _start_listening(self) -> None:
        self._listening = True
        self._update_display()
        # 使用 keyboard 库全局 hook 捕获按键，可正确区分左右修饰键
        import keyboard as kb
        self._kb_hook = kb.hook(self._on_kb_event, suppress=False)

    def _stop_listening(self) -> None:
        if self._kb_hook is not None:
            import keyboard as kb
            kb.unhook(self._kb_hook)
            self._kb_hook = None
        self._listening = False
        self._update_display()

    def _on_kb_event(self, event) -> None:
        """keyboard 库的回调，在后台线程中执行，通过 QTimer 切回主线程"""
        import keyboard as kb
        if event.event_type != kb.KEY_DOWN:
            return

        key_name = event.name
        if not key_name:
            return

        # ESC 取消
        if key_name == "esc":
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._stop_listening)
            return

        # 仅接受白名单中的键
        if key_name.lower() not in self._ALLOWED_KEYS:
            return

        self._hotkey = key_name.lower()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._finish_capture)

    def _finish_capture(self) -> None:
        """主线程中完成捕获流程"""
        self._stop_listening()
        self.hotkey_changed.emit(self._hotkey)

    def keyPressEvent(self, event) -> None:
        """监听模式下吞掉 Qt 按键事件，防止 Alt 触发菜单激活"""
        if self._listening:
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event) -> bool:
        """拦截 ShortcutOverride，防止 Alt 按下导致窗口失焦"""
        from PyQt6.QtCore import QEvent
        if self._listening and event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)
