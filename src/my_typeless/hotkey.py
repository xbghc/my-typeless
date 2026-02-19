"""全局热键监听模块 - 使用 Windows 低级键盘钩子 + 自带消息泵线程"""

import ctypes
import threading
from ctypes import wintypes

from my_typeless.events import EventEmitter

# Windows 低级键盘钩子常量
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# 虚拟键码 → 键名
_VK_TO_NAME = {
    0xA4: "left alt",
    0xA5: "right alt",
    0xA0: "left shift",
    0xA1: "right shift",
    0xA2: "left ctrl",
    0xA3: "right ctrl",
    0x12: "alt",
    0x10: "shift",
    0x11: "ctrl",
}

# C 类型定义（64 位兼容）
LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
LowLevelKeyboardProc = ctypes.CFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

# 设置 Win32 API 类型
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
]
_user32.CallNextHookEx.restype = LRESULT
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

_user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint
]
_user32.GetMessageW.restype = wintypes.BOOL

_user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
]
_user32.PostThreadMessageW.restype = wintypes.BOOL

_kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WM_QUIT = 0x0012


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HotkeyListener:
    """
    全局热键监听器

    使用 Windows 低级键盘钩子拦截热键，防止 Alt 等键触发系统菜单。
    在专用线程中运行自己的消息泵，通过 EventEmitter 通知事件：
    - key_pressed: 热键按下（开始录音）
    - key_released: 热键松开（停止录音）
    """

    def __init__(self, hotkey: str = "right alt"):
        self.events = EventEmitter()
        self._hotkey = hotkey.lower()
        self._is_pressed = False
        self._hook_id = None
        # 必须保持回调引用防止被 GC
        self._hook_proc = LowLevelKeyboardProc(self._ll_keyboard_proc)
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def start(self) -> None:
        """在专用线程中启动热键监听（含消息泵）"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """线程入口：安装钩子 + 运行消息泵"""
        self._thread_id = _kernel32.GetCurrentThreadId()

        self._hook_id = _user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            None,
            0,
        )

        # 消息泵（WH_KEYBOARD_LL 回调需要消息泵才能被调度）
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        # 消息泵退出后清理钩子
        if self._hook_id:
            _user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = None

    def stop(self) -> None:
        """停止热键监听"""
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread_id = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._is_pressed = False

    def update_hotkey(self, new_hotkey: str) -> None:
        """更新热键配置（停止后重启）"""
        was_running = self._thread is not None
        if was_running:
            self.stop()
        self._hotkey = new_hotkey.lower()
        if was_running:
            self.start()

    def _ll_keyboard_proc(self, nCode: int, wParam: int, lParam: int) -> int:
        """低级键盘钩子回调"""
        if nCode >= 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            key_name = _VK_TO_NAME.get(vk)

            if key_name and key_name == self._hotkey:
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if not self._is_pressed:
                        self._is_pressed = True
                        self.events.emit("key_pressed")
                    return 1  # 吞掉事件，防止 Alt 激活菜单
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    if self._is_pressed:
                        self._is_pressed = False
                        self.events.emit("key_released")
                    return 1  # 吞掉事件

        return _user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)
