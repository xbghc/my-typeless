"""单实例机制 - Windows Named Mutex + TCP 回环信号"""

import ctypes
import logging
import socket
import threading

logger = logging.getLogger(__name__)

_kernel32 = ctypes.windll.kernel32
_ERROR_ALREADY_EXISTS = 183

_MUTEX_NAME = "MyTypeless_SingleInstance"
_SIGNAL_PORT = 47891


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
    """TCP 回环服务器，监听来自第二实例的信号"""

    def __init__(self, on_signal: callable):
        self._on_signal = on_signal
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """在后台线程启动信号服务器"""
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止信号服务器"""
        self._running = False
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass

    def _serve(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server.bind(("127.0.0.1", _SIGNAL_PORT))
            self._server.listen(1)
            self._server.settimeout(1.0)
            while self._running:
                try:
                    conn, _ = self._server.accept()
                    conn.close()
                    self._on_signal()
                except socket.timeout:
                    continue
                except OSError:
                    break
        except OSError as e:
            logger.warning("Signal server bind failed: %s", e)
        finally:
            if self._server:
                try:
                    self._server.close()
                except OSError:
                    pass


def signal_existing_instance() -> None:
    """向已运行的实例发送信号（打开设置窗口）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(("127.0.0.1", _SIGNAL_PORT))
        s.close()
    except (ConnectionRefusedError, OSError):
        pass
