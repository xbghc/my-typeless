"""系统托盘图标 - 三种状态切换 + 菜单（pystray 实现）"""

import ctypes
import threading

import pystray
from pystray import Menu, MenuItem

from my_typeless.icons import load_tray_icon
from my_typeless.version import __version__ as APP_VERSION


class TrayManager:
    """系统托盘图标管理器 - 三种状态 + 右键菜单"""

    def __init__(self):
        self._icons = {
            "idle": load_tray_icon("icon_idle"),
            "recording": load_tray_icon("icon_recording"),
            "processing": load_tray_icon("icon_processing"),
        }
        self._state = "idle"

        # 回调（由 main.py 设置）
        self.on_show_window: callable = lambda: None
        self.on_quit: callable = lambda: None

        self._icon = pystray.Icon(
            name="my-typeless",
            icon=self._icons["idle"],
            title="My Typeless - Ready",
            menu=Menu(
                MenuItem(
                    "Open",
                    lambda: self.on_show_window(),
                    default=True,  # 左键单击触发
                ),
                Menu.SEPARATOR,
                MenuItem(
                    f"About (v{APP_VERSION})",
                    lambda: self._show_about(),
                ),
                Menu.SEPARATOR,
                MenuItem(
                    "Quit",
                    lambda: self.on_quit(),
                ),
            ),
        )

    def run(self) -> None:
        """在当前线程启动托盘（阻塞）"""
        self._icon.run()

    def run_detached(self) -> None:
        """在后台线程启动托盘"""
        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def stop(self) -> None:
        """停止托盘图标"""
        self._icon.stop()

    def set_state(self, state: str) -> None:
        """切换托盘图标状态 (idle / recording / processing)"""
        tooltips = {
            "idle": "My Typeless - Ready",
            "recording": "My Typeless - Recording...",
            "processing": "My Typeless - Processing...",
        }
        if state in self._icons:
            self._state = state
            self._icon.icon = self._icons[state]
            self._icon.title = tooltips.get(state, "My Typeless")

    def show_notification(self, title: str, message: str) -> None:
        """显示 Windows 通知气泡"""
        self._icon.notify(message, title)

    def show_error(self, msg: str, critical: bool) -> None:
        """显示错误通知"""
        self.show_notification("My Typeless", msg)

    def _show_about(self) -> None:
        """显示关于信息（Win32 MessageBox，独立线程避免阻塞托盘消息泵）"""

        def _show():
            text = (
                f"My Typeless v{APP_VERSION}\n\n"
                "AI-powered voice dictation for Windows.\n"
                "Hold hotkey to speak, release to get polished text."
            )
            MB_OK = 0x00000000
            MB_ICONINFORMATION = 0x00000040
            ctypes.windll.user32.MessageBoxW(
                None,
                text,
                "About My Typeless",
                MB_OK | MB_ICONINFORMATION,
            )

        threading.Thread(target=_show, daemon=True).start()
