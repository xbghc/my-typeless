"""My Typeless - AI 智能语音输入法入口"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

from .config import AppConfig
from .hotkey import HotkeyListener
from .worker import Worker
from .tray import TrayIcon, SettingsWindow, QuickPopup
from .history import add_correction


class MyTypelessApp:
    """应用主控制器"""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("My Typeless")

        # 设置应用图标
        icon_path = Path(__file__).parent / "resources" / "app_icon.ico"
        if icon_path.exists():
            self._app.setWindowIcon(QIcon(str(icon_path)))

        # 加载配置
        self._config = AppConfig.load()

        # 初始化组件
        self._worker = Worker(self._config)
        self._hotkey = HotkeyListener(self._config.hotkey)
        self._tray = TrayIcon()
        self._settings_window: SettingsWindow | None = None
        self._quick_popup: QuickPopup | None = None
        self._last_raw: str = ""
        self._last_refined: str = ""

        self._connect_signals()

    def _connect_signals(self) -> None:
        """连接信号与槽"""
        # 热键 → 录音控制
        self._hotkey.key_pressed.connect(self._worker.start_recording)
        self._hotkey.key_released.connect(self._worker.stop_recording_and_process)
        self._hotkey.double_clicked.connect(self._show_quick_popup)

        # Worker 结果 → 存储 + 同步弹窗
        self._worker.result_ready.connect(self._on_result)

        # Worker 状态 → 托盘图标
        self._worker.state_changed.connect(self._tray.set_state)
        self._worker.error_occurred.connect(self._on_error)

        # 托盘菜单
        self._tray.show_settings.connect(self._open_settings)
        self._tray.quit_app.connect(self._quit)

    def _on_result(self, raw_text: str, refined_text: str) -> None:
        """Worker 完成处理后：存储最新结果 + 同步到弹窗"""
        self._last_raw = raw_text
        self._last_refined = refined_text
        # 如果弹窗正在显示，实时同步新内容
        if self._quick_popup is not None and self._quick_popup.isVisible():
            self._quick_popup.update_text(raw_text, refined_text)

    def _show_quick_popup(self) -> None:
        """双击热键时弹出快捷窗口"""
        if self._quick_popup is None:
            self._quick_popup = QuickPopup()
            self._quick_popup.correction_submitted.connect(self._on_correction)
        self._quick_popup.refresh_and_show(self._last_raw, self._last_refined)

    def _on_correction(self, raw_input: str, corrected_output: str) -> None:
        """用户提交修正 → 保存为 few-shot 示例"""
        add_correction(raw_input, corrected_output)

    def _open_settings(self) -> None:
        """打开设置窗口"""
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self._config)
            self._settings_window.settings_saved.connect(self._on_settings_saved)
        else:
            self._settings_window.update_config(self._config)

        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _on_settings_saved(self, config: AppConfig) -> None:
        """设置保存后更新各组件"""
        self._config = config
        self._worker.update_config(config)
        self._hotkey.update_hotkey(config.hotkey)

    def _on_error(self, msg: str) -> None:
        """处理错误通知"""
        self._tray.showMessage(
            "My Typeless Error",
            msg,
            self._tray.MessageIcon.Warning,
            3000,
        )

    def _quit(self) -> None:
        """退出应用"""
        self._hotkey.stop()
        self._worker.cleanup()
        self._tray.hide()
        self._app.quit()

    def run(self) -> int:
        """启动应用"""
        self._hotkey.start()
        self._tray.show()
        return self._app.exec()


def main():
    app = MyTypelessApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
