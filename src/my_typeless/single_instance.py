"""单实例机制 - Windows Named Mutex + Named Pipe 信号"""

import ctypes
import logging
import threading

import pywintypes
import win32file
import win32pipe
import winerror

logger = logging.getLogger(__name__)

_kernel32 = ctypes.windll.kernel32
_ERROR_ALREADY_EXISTS = 183

_MUTEX_NAME = "MyTypeless_SingleInstance"
_PIPE_NAME = r"\\.\pipe\MyTypeless_SingleInstance"


class SingleInstance:
    """通过 Windows Named Mutex 确保单实例运行"""

    def __init__(self):
        self._handle = None

    def try_acquire(self) -> bool:
        """尝试获取互斥锁。返回 True 表示当前是第一个实例。"""
        self._handle = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        return _kernel32.GetLastError() != _ERROR_ALREADY_EXISTS

    def release(self) -> None:
        """释放互斥锁"""
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None


class SignalServer:
    """Named Pipe 服务器，监听来自第二实例的信号"""

    def __init__(self, on_signal: callable):
        self._on_signal = on_signal
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """在后台线程启动信号服务器"""
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止信号服务器

        通过自连接 pipe 唤醒阻塞的 ConnectNamedPipe。
        """
        self._running = False
        try:
            handle = win32file.CreateFile(
                _PIPE_NAME,
                win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            win32file.CloseHandle(handle)
        except pywintypes.error:
            # pipe 可能正处于两次创建之间，下次循环会检查 _running 并退出
            pass

    def _serve(self) -> None:
        while self._running:
            try:
                handle = win32pipe.CreateNamedPipe(
                    _PIPE_NAME,
                    win32pipe.PIPE_ACCESS_INBOUND,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_WAIT,
                    1,  # 同一时刻只允许 1 个 pipe instance
                    0,
                    0,
                    0,
                    None,
                )
            except pywintypes.error as e:
                logger.warning("CreateNamedPipe failed: %s", e)
                return

            try:
                try:
                    win32pipe.ConnectNamedPipe(handle, None)
                except pywintypes.error as e:
                    # ERROR_PIPE_CONNECTED: 客户端在 ConnectNamedPipe 调用前已连接，视为成功
                    if e.winerror != winerror.ERROR_PIPE_CONNECTED:
                        raise

                if self._running:
                    self._on_signal()
            except pywintypes.error as e:
                logger.debug("Pipe connection error: %s", e)
            finally:
                try:
                    win32pipe.DisconnectNamedPipe(handle)
                except pywintypes.error:
                    pass
                try:
                    win32file.CloseHandle(handle)
                except pywintypes.error:
                    pass


def signal_existing_instance() -> None:
    """向已运行的实例发送信号（打开设置窗口）"""
    try:
        handle = win32file.CreateFile(
            _PIPE_NAME,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        win32file.CloseHandle(handle)
    except pywintypes.error:
        pass
