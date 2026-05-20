"""My Typeless - AI 智能语音输入法入口"""

import logging
import os
import sys
import threading
from pathlib import Path

import webview

from my_typeless.config import AppConfig
from my_typeless.hotkey import HotkeyListener
from my_typeless.single_instance import (
    SignalServer,
    SingleInstance,
    signal_existing_instance,
)
from my_typeless.tray import TrayManager
from my_typeless.updater import UpdateChecker, apply_update
from my_typeless.webview_api import SettingsAPI
from my_typeless.window_icon import apply_window_icon
from my_typeless.worker import Worker

logger = logging.getLogger(__name__)


def _resolve_web_dir() -> Path:
    """Return the bundled web UI directory in both source and PyInstaller builds."""
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / "web"]

    # In one-file PyInstaller builds, the entry script may live directly under
    # sys._MEIPASS while package data is unpacked under sys._MEIPASS/my_typeless.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_dir = Path(sys.__dict__["_MEIPASS"])
        candidates.insert(0, bundle_dir / "my_typeless" / "web")
        candidates.append(bundle_dir / "web")

    for web_dir in candidates:
        if (web_dir / "index.html").exists():
            return web_dir

    logger.error("Web UI not found. Tried: %s", ", ".join(str(p) for p in candidates))
    return candidates[0]


_WEB_DIR = _resolve_web_dir()


class MyTypelessApp:
    """应用主控制器"""

    def __init__(self):
        self._config = AppConfig.load()

        # 初始化组件
        self._worker = Worker(self._config)
        self._hotkey = HotkeyListener(self._config.hotkey)
        self._tray = TrayManager()
        self._updater = UpdateChecker()
        self._single_instance = SingleInstance()

        # 单实例信号服务器
        self._signal_server = SignalServer(on_signal=self._open_window)

        # WebView 设置窗口（在 run() 中创建）
        self._api = SettingsAPI(self._config, on_save=self._on_config_saved)
        self._window = None
        self._allow_close = False

        # 连接事件
        self._connect_events()

    def _connect_events(self) -> None:
        """连接事件回调"""
        # 热键 → 录音控制
        self._hotkey.events.on("key_pressed", self._worker.start_recording)
        self._hotkey.events.on("key_released", self._worker.stop_recording_and_process)

        # Worker 状态 → 托盘图标
        self._worker.events.on("state_changed", self._tray.set_state)
        self._worker.events.on("error_occurred", self._on_error)

        # 更新检查
        self._updater.events.on("update_available", self._on_update_available)
        self._updater.events.on("update_downloaded", self._on_update_downloaded)
        self._updater.events.on("update_error", lambda msg: self._on_error(msg, False))

        # 托盘菜单
        self._tray.on_show_window = self._open_window
        self._tray.on_quit = self._quit

    def _open_window(self) -> None:
        """显示设置窗口（重新加载页面以获取最新配置）"""
        if self._window:
            self._window.load_url(str(_WEB_DIR / "index.html"))
            self._window.show()

    def _on_window_closing(self):
        """拦截窗口关闭，改为隐藏"""
        if not self._allow_close:
            if self._window:
                self._window.hide()
            return False

    def _on_config_saved(self, config: AppConfig) -> None:
        """设置保存后更新各组件"""
        self._config = config
        self._worker.update_config(config)
        self._hotkey.update_hotkey(config.hotkey)

    def _on_error(self, msg: str, critical: bool) -> None:
        """处理错误通知"""
        self._tray.show_error(msg, critical)

    def _on_update_available(self, release) -> None:
        """发现新版本时通过托盘通知用户"""
        size_mb = release.size / (1024 * 1024) if release.size else 0
        self._tray.show_notification(
            "My Typeless 更新",
            f"发现新版本: {release.name} (v{release.version})\n"
            f"文件大小: {size_mb:.1f} MB\n"
            f"正在后台下载，完成后将自动安装并退出当前实例。",
        )
        # 自动开始下载
        self._updater.download(release)

    def _on_update_downloaded(self, path: str) -> None:
        """更新下载完成，启动安装程序并退出"""
        if apply_update(Path(path)):
            self._quit()

    def _quit(self) -> None:
        """退出应用"""
        logger.info("Shutting down...")
        self._updater.stop()
        self._hotkey.stop()
        self._worker.cleanup()
        self._signal_server.stop()
        self._tray.stop()
        self._single_instance.release()
        # 允许窗口真正关闭，webview.start() 随之返回
        self._allow_close = True
        if self._window:
            self._window.destroy()

    def run(self) -> int:
        """启动应用"""
        # 单实例检查
        if not self._single_instance.try_acquire():
            signal_existing_instance()
            return 0

        # 创建隐藏的设置窗口（pywebview 需要主线程）
        window = webview.create_window(
            "My Typeless",
            url=str(_WEB_DIR / "index.html"),
            js_api=self._api,
            width=820,
            height=540,
            resizable=False,
            hidden=True,
        )
        assert window is not None, "webview.create_window 返回空"
        self._window = window
        self._api.set_window(window)
        window.events.closing += self._on_window_closing
        window.events.shown += lambda: apply_window_icon(window)

        def _start_services():
            """webview 就绪后启动后台服务"""
            self._signal_server.start()
            self._hotkey.start()
            self._updater.start(immediate=True)
            self._tray.run_detached()

        # 主线程运行 webview 事件循环（阻塞直到窗口被销毁）
        webview.start(func=_start_services)
        return 0


def _set_app_user_model_id():
    """设置 Windows AppUserModelID 以便任务栏正确显示应用图标"""
    if sys.platform == "win32":
        try:
            import ctypes

            # 这是一个任意但全局唯一的字符串
            app_id = "xbghc.mytypeless.app.1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception as e:
            logger.warning(f"Failed to set AppUserModelID: {e}")


class _FsyncFileHandler(logging.FileHandler):
    """每条日志写入后 fsync，使 NTFS mtime 实时反映最近写入时间。

    Windows 在文件句柄长期打开时不会刷新 LastWriteTime（lazy writing），
    导致从外部观察会误以为日志停止写入。fsync 强制元数据落盘可避免这一误判。
    """

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        if self.stream is not None:
            try:
                os.fsync(self.stream.fileno())
            except (OSError, ValueError):
                pass


# httpcore / httpx / openai 的 DEBUG 输出会把控制台刷屏（每次 API 调用几十行）。
# 文件日志保留它们便于排查网络问题；控制台只屏蔽到 WARNING 以上。
_CONSOLE_NOISY_PREFIXES = ("httpx", "httpcore", "urllib3", "openai._base_client")


class _DropNoisyForConsole(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name.startswith(_CONSOLE_NOISY_PREFIXES) and record.levelno < logging.WARNING
        )


def _install_threading_excepthook() -> None:
    """抑制 pywebview 5.x 已知的 "Main window failed to start" race 异常。

    JS 端 pywebviewready 事件触发后立即调 Python API 时，pywebview 内部
    window._initialized 可能尚未 set，evaluate_js 回调线程抛此异常。
    不影响主功能（API 调用本身已成功），但 traceback 会刷控制台。
    这里把它降级为 DEBUG 日志，其它异常仍走默认处理。
    """
    original = threading.excepthook

    def _hook(args: threading.ExceptHookArgs) -> None:
        exc = args.exc_value
        if (
            exc is not None
            and type(exc).__name__ == "WebViewException"
            and "Main window failed to start" in str(exc)
        ):
            logger.debug("Suppressed pywebview init race: %s", exc)
            return
        original(args)

    threading.excepthook = _hook


def main():
    _set_app_user_model_id()
    _install_threading_excepthook()

    from my_typeless.config import CONFIG_DIR

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    file_handler = _FsyncFileHandler(str(CONFIG_DIR / "app.log"), encoding="utf-8")
    file_handler.setFormatter(fmt)
    handlers: list[logging.Handler] = [file_handler]

    # 有控制台时（python -m my_typeless / 终端运行的 dev 启动）同时输出到 stderr。
    # PyInstaller GUI 模式（console=False）下 sys.stderr 为 None，跳过 console handler。
    if sys.stderr is not None:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        console_handler.addFilter(_DropNoisyForConsole())
        handlers.append(console_handler)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers)
    app = MyTypelessApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
