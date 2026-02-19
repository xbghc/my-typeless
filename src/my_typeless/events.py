"""轻量级线程安全事件发射器 - 替代 Qt 信号/槽"""

import threading
from typing import Callable, Any


class EventEmitter:
    """
    线程安全的事件发射器。回调在调用 emit() 的线程上同步执行。

    用法:
        emitter = EventEmitter()
        emitter.on("state_changed", my_callback)
        emitter.emit("state_changed", "recording")
    """

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()

    def on(self, event: str, callback: Callable) -> None:
        """注册事件监听器"""
        with self._lock:
            self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """取消事件监听器"""
        with self._lock:
            if event in self._listeners:
                self._listeners[event] = [
                    cb for cb in self._listeners[event] if cb is not callback
                ]

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """触发事件，同步调用所有已注册的回调"""
        with self._lock:
            listeners = list(self._listeners.get(event, []))
        for cb in listeners:
            cb(*args, **kwargs)
