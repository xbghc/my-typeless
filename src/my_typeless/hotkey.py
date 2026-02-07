"""全局热键监听模块 - 使用 keyboard 库"""

import keyboard
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QObject, pyqtSignal

# Windows 低级键盘钩子常量
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# 虚拟键码 → keyboard 库名称
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
LRESULT = ctypes.c_ssize_t  # 64 位系统上为 8 字节
ULONG_PTR = ctypes.c_size_t
LowLevelKeyboardProc = ctypes.CFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

# 设置 CallNextHookEx 的参数/返回类型
_user32 = ctypes.windll.user32
_user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
]
_user32.CallNextHookEx.restype = LRESULT
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HotkeyListener(QObject):
    """
    全局热键监听器

    使用 Windows 低级键盘钩子拦截热键，防止 Alt 等键触发系统菜单。
    通过 Qt Signal 通知主线程热键事件：
    - key_pressed: 热键按下（开始录音）
    - key_released: 热键松开（停止录音）
    """

    key_pressed = pyqtSignal()
    key_released = pyqtSignal()

    def __init__(self, hotkey: str = "right alt"):
        super().__init__()
        self._hotkey = hotkey.lower()
        self._is_pressed = False
        self._hook_id = None
        # 必须保持回调引用防止被 GC
        self._hook_proc = LowLevelKeyboardProc(self._ll_keyboard_proc)

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def start(self) -> None:
        """注册 Windows 低级键盘钩子"""
        self._hook_id = _user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            None,
            0,
        )

    def stop(self) -> None:
        """取消低级键盘钩子"""
        if self._hook_id:
            _user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = None
        self._is_pressed = False

    def update_hotkey(self, new_hotkey: str) -> None:
        """更新热键配置"""
        was_running = self._hook_id is not None
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
                        self.key_pressed.emit()
                    return 1  # 吞掉事件，防止 Alt 激活菜单
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    if self._is_pressed:
                        self._is_pressed = False
                        self.key_released.emit()
                    return 1  # 吞掉事件

        return _user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)
