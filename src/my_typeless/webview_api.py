"""pywebview API 桥接 - 将 Python 后端暴露给前端 JS"""

import logging
import threading
from dataclasses import asdict

import keyboard

from openai import OpenAI

from my_typeless.config import AppConfig, LLMConfig
from my_typeless.history import load_history, clear_history, add_history
from my_typeless.llm_client import LLMClient
from my_typeless.version import __version__

logger = logging.getLogger(__name__)

# 允许的热键列表
ALLOWED_HOTKEYS = [
    "left alt", "right alt", "alt",
    "left ctrl", "right ctrl", "ctrl",
    "left shift", "right shift", "shift",
    "left windows", "right windows",
    "caps lock", "tab", "space",
    "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "f10", "f11", "f12",
]


class SettingsAPI:
    """暴露给 pywebview 前端的 API（通过 window.pywebview.api 调用）"""

    def __init__(self, config: AppConfig, on_save: callable = None):
        self._config = config
        self._on_save = on_save
        self._window = None

    def set_window(self, window):
        """设置 webview 窗口引用（用于 evaluate_js 回调）"""
        self._window = window

    def get_config(self) -> dict:
        """返回当前配置"""
        return asdict(self._config)

    def save_config(self, data: dict) -> dict:
        """保存前端提交的配置"""
        try:
            self._config.hotkey = data.get("hotkey", self._config.hotkey)
            self._config.start_with_windows = data.get("start_with_windows", False)

            stt = data.get("stt", {})
            self._config.stt.base_url = stt.get("base_url", "")
            self._config.stt.api_key = stt.get("api_key", "")
            self._config.stt.model = stt.get("model", "")
            self._config.stt.language = stt.get("language", "")

            llm = data.get("llm", {})
            self._config.llm.base_url = llm.get("base_url", "")
            self._config.llm.api_key = llm.get("api_key", "")
            self._config.llm.model = llm.get("model", "")
            self._config.llm.prompt = llm.get("prompt", "")

            self._config.glossary = data.get("glossary", [])

            self._config.save()
            if self._on_save:
                self._on_save(self._config)
            return {"success": True}
        except Exception as e:
            logger.error("Save config failed: %s", e)
            return {"success": False, "error": str(e)}

    def get_history(self) -> list:
        """返回历史记录"""
        entries = load_history()
        return [asdict(e) for e in entries]

    def clear_history(self) -> dict:
        """清空历史记录"""
        clear_history()
        return {"success": True}

    def run_test(self, raw_text: str, llm_override: dict = None) -> dict:
        """测试 LLM 精修"""
        try:
            if llm_override:
                llm_config = LLMConfig(
                    base_url=llm_override.get("base_url", self._config.llm.base_url),
                    api_key=llm_override.get("api_key", self._config.llm.api_key),
                    model=llm_override.get("model", self._config.llm.model),
                    prompt=llm_override.get("prompt", self._config.llm.prompt),
                )
            else:
                llm_config = self._config.llm

            glossary = self._config.glossary
            temp_config = AppConfig(llm=llm_config, glossary=glossary)
            system_prompt = temp_config.build_llm_system_prompt()

            client = LLMClient(llm_config)
            result = client.refine(raw_text, system_prompt=system_prompt)

            if raw_text.strip() and result:
                add_history(raw_text, result)

            return {"success": True, "result": result}
        except Exception as e:
            logger.error("Test refinement failed: %s", e)
            return {"success": False, "error": str(e)}

    def get_version(self) -> str:
        """返回应用版本号"""
        return __version__

    def get_allowed_hotkeys(self) -> list:
        """返回允许的热键列表"""
        return ALLOWED_HOTKEYS

    def start_hotkey_capture(self) -> None:
        """开始捕获热键按键，结果通过 evaluate_js 回调"""
        def on_key(event):
            if event.event_type != keyboard.KEY_DOWN:
                return
            name = event.name
            if not name:
                return
            if name.lower() == "esc":
                keyboard.unhook(hook)
                if self._window:
                    self._window.evaluate_js("onHotkeyCaptured(null)")
                return
            if name.lower() in [k.lower() for k in ALLOWED_HOTKEYS]:
                keyboard.unhook(hook)
                if self._window:
                    self._window.evaluate_js(f"onHotkeyCaptured('{name.lower()}')")

        hook = keyboard.hook(on_key, suppress=False)

    def test_stt_connection(self, stt_override: dict | None = None) -> dict:
        """测试 STT API 连接"""
        try:
            cfg = stt_override or {}
            base_url = cfg.get("base_url") or self._config.stt.base_url
            api_key = cfg.get("api_key") or self._config.stt.api_key
            model = cfg.get("model") or self._config.stt.model
            if not api_key:
                return {"success": False, "error": "API key is empty"}
            client = OpenAI(base_url=base_url, api_key=api_key)
            client.models.retrieve(model)
            return {"success": True}
        except Exception as e:
            logger.error("STT connection test failed: %s", e)
            return {"success": False, "error": str(e)}

    def test_llm_connection(self, llm_override: dict | None = None) -> dict:
        """测试 LLM API 连接"""
        try:
            cfg = llm_override or {}
            base_url = cfg.get("base_url") or self._config.llm.base_url
            api_key = cfg.get("api_key") or self._config.llm.api_key
            model = cfg.get("model") or self._config.llm.model
            if not api_key:
                return {"success": False, "error": "API key is empty"}
            client = OpenAI(base_url=base_url, api_key=api_key)
            client.models.retrieve(model)
            return {"success": True}
        except Exception as e:
            logger.error("LLM connection test failed: %s", e)
            return {"success": False, "error": str(e)}

    def close_window(self) -> None:
        """隐藏设置窗口（窗口保持存活供下次打开）"""
        if self._window:
            self._window.hide()
