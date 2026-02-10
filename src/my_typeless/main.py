"""My Typeless - AI 智能语音输入法入口"""

import ctypes
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from my_typeless.config import AppConfig
from my_typeless.hotkey import HotkeyListener
from my_typeless.worker import Worker
from my_typeless.tray import TrayIcon, SettingsWindow, _load_svg_icon
from my_typeless.updater import UpdateChecker, apply_update, prompt_and_apply_update

_SERVER_NAME = "MyTypeless_SingleInstance"


class MyTypelessApp:
    """应用主控制器"""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("My Typeless")

        # 单实例服务器：监听来自新启动实例的连接
        self._server = QLocalServer()
        self._server.newConnection.connect(self._on_new_connection)
        QLocalServer.removeServer(_SERVER_NAME)
        self._server.listen(_SERVER_NAME)

        # 设置应用图标（优先使用 SVG 以获得高 DPI 清晰度）
        svg_path = Path(__file__).parent / "resources" / "app_icon.svg"
        ico_path = Path(__file__).parent / "resources" / "app_icon.ico"
        if svg_path.exists():
            self._app.setWindowIcon(_load_svg_icon("app_icon.svg", size=128))
        elif ico_path.exists():
            self._app.setWindowIcon(QIcon(str(ico_path)))

        # 加载配置
        self._config = AppConfig.load()

        # 初始化组件
        self._worker = Worker(self._config)
        self._hotkey = HotkeyListener(self._config.hotkey)
        self._tray = TrayIcon()
        self._settings_window: SettingsWindow | None = None

        # 自动更新检查
        self._updater = UpdateChecker()
        self._updater.update_available.connect(self._on_update_available)
        self._updater.update_downloaded.connect(self._on_update_downloaded)
        self._updater.update_error.connect(self._on_error)

        self._connect_signals()

    def _connect_signals(self) -> None:
        """连接信号与槽"""
        # 热键 → 录音控制
        self._hotkey.key_pressed.connect(self._worker.start_recording)
        self._hotkey.key_released.connect(self._worker.stop_recording_and_process)

        # Worker 状态 → 托盘图标
        self._worker.state_changed.connect(self._tray.set_state)
        self._worker.error_occurred.connect(self._on_error)

        # 托盘菜单
        self._tray.show_settings.connect(self._open_settings)
        self._tray.quit_app.connect(self._quit)

    def _on_new_connection(self) -> None:
        """收到其他实例的连接，打开设置窗口"""
        conn = self._server.nextPendingConnection()
        if conn:
            conn.close()
            self._open_settings()

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
        # 由第二个实例授权后，直接调用 SetForegroundWindow 即可生效
        ctypes.windll.user32.SetForegroundWindow(int(self._settings_window.winId()))

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

    def _on_update_available(self, release) -> None:
        """发现新版本时提示用户"""
        prompt_and_apply_update(release, self._updater)

    def _on_update_downloaded(self, path: str) -> None:
        """更新下载完成，启动安装程序并干净退出当前实例"""
        if apply_update(Path(path)):
            self._quit()

    def _quit(self) -> None:
        """退出应用"""
        self._updater.stop()
        self._hotkey.stop()
        self._worker.cleanup()
        self._server.close()
        self._tray.hide()
        self._app.quit()

    def run(self) -> int:
        """启动应用"""
        self._hotkey.start()
        self._tray.show()
        self._updater.start(immediate=True)
        return self._app.exec()


def main():
    # 尝试连接已运行的实例
    socket = QLocalSocket()
    socket.connectToServer(_SERVER_NAME)
    if socket.waitForConnected(500):
        # 第二个实例是用户刚点击的前台进程，有权授权其他进程设置前台窗口
        ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
        socket.disconnectFromServer()
        sys.exit(0)

    app = MyTypelessApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
