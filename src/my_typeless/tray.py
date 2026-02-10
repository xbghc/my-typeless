"""系统托盘图标 - 三种状态切换 + 右键菜单"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal

from my_typeless.icons import load_svg_icon
from my_typeless.version import __version__ as APP_VERSION


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标 - 三种状态切换 + 右键菜单"""

    show_settings = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons = {
            "idle": load_svg_icon("icon_idle.svg", hidpi=False),
            "recording": load_svg_icon("icon_recording.svg", hidpi=False),
            "processing": load_svg_icon("icon_processing.svg", hidpi=False),
        }
        self.setIcon(self._icons["idle"])
        self.setToolTip("My Typeless - Ready")

        # 右键菜单
        menu = QMenu()
        settings_action = QAction("Settings...", menu)
        settings_action.triggered.connect(self.show_settings.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        about_action = QAction("About", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # 双击托盘图标打开设置
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings.emit()

    def set_state(self, state: str) -> None:
        """切换托盘图标状态 (idle / recording / processing)"""
        tooltips = {
            "idle": "My Typeless - Ready",
            "recording": "My Typeless - Recording...",
            "processing": "My Typeless - Processing...",
        }
        if state in self._icons:
            self.setIcon(self._icons[state])
            self.setToolTip(tooltips.get(state, "My Typeless"))

    def _show_about(self) -> None:
        QMessageBox.information(
            None,
            "About My Typeless",
            f"My Typeless v{APP_VERSION}\n\n"
            "AI-powered voice dictation for Windows.\n"
            "Hold hotkey to speak, release to get polished text.",
        )
