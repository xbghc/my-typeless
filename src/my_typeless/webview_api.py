"""pywebview API 桥接 - 将 Python 后端暴露给前端 JS"""

import logging
from dataclasses import asdict

import keyboard

from openai import OpenAI

from my_typeless.config import AppConfig
from my_typeless.history import get_history_page, clear_history, add_history
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
            self._config.stt.active_provider_id = stt.get("active_provider_id", self._config.stt.active_provider_id)
            self._config.stt.active_model = stt.get("active_model", self._config.stt.active_model)
            self._config.stt.language = stt.get("language", self._config.stt.language)

            if "providers" in stt:
                from my_typeless.config import ProviderConfig
                self._config.stt.providers = [ProviderConfig(**p) for p in stt["providers"]]

            llm = data.get("llm", {})
            self._config.llm.active_provider_id = llm.get("active_provider_id", self._config.llm.active_provider_id)
            self._config.llm.active_model = llm.get("active_model", self._config.llm.active_model)
            self._config.llm.prompt = llm.get("prompt", self._config.llm.prompt)

            if "providers" in llm:
                from my_typeless.config import ProviderConfig
                self._config.llm.providers = [ProviderConfig(**p) for p in llm["providers"]]

            self._config.glossary = data.get("glossary", [])

            self._config.save()
            if self._on_save:
                self._on_save(self._config)
            return {"success": True}
        except Exception as e:
            logger.error("Save config failed: %s", e)
            return {"success": False, "error": str(e)}

    def get_history(self, offset: int = 0, limit: int = 20) -> dict:
        """返回历史记录（分页）"""
        return get_history_page(offset, limit)

    def clear_history(self) -> dict:
        """清空历史记录"""
        clear_history()
        return {"success": True}

    def run_test(self, raw_text: str, llm_override: dict = None) -> dict:
        """测试 LLM 精修"""
        try:
            llm_config = self._config.llm
            active_provider = llm_config.active_provider
            if not active_provider:
                return {"success": False, "error": "No active LLM provider configured"}

            base_url = active_provider.base_url
            api_key = active_provider.api_key
            model = llm_config.active_model
            prompt = llm_config.prompt

            if llm_override:
                base_url = llm_override.get("base_url", base_url)
                api_key = llm_override.get("api_key", api_key)
                model = llm_override.get("model", model)
                prompt = llm_override.get("prompt", prompt)

            glossary = self._config.glossary
            temp_config = AppConfig(glossary=glossary)
            temp_config.llm.prompt = prompt
            system_prompt = temp_config.build_llm_system_prompt()

            # We need to temporarily modify the active provider details for LLMClient
            # Since LLMClient just expects an LLMConfig, we can build a temp one.
            from my_typeless.config import LLMConfig as ConfigLLMConfig, ProviderConfig

            temp_provider = ProviderConfig(id="temp", name="temp", base_url=base_url, api_key=api_key, models=[model])
            temp_llm_config = ConfigLLMConfig(providers=[temp_provider], active_provider_id="temp", active_model=model, prompt=prompt)

            client = LLMClient(temp_llm_config)
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

    def test_stt_connection(self, provider_config: dict | None = None) -> dict:
        """测试 STT API 连接"""
        try:
            if not provider_config:
                return {"success": False, "error": "No credentials provided for testing"}

            base_url = provider_config.get("base_url")
            api_key = provider_config.get("api_key")
            model = provider_config.get("model")

            if not base_url or not api_key or not model:
                return {"success": False, "error": "Base URL, API Key, and Model are required for testing"}

            client = OpenAI(base_url=base_url, api_key=api_key)
            client.models.retrieve(model)
            return {"success": True}
        except Exception as e:
            logger.error("STT connection test failed: %s", e)
            return {"success": False, "error": str(e)}

    def test_llm_connection(self, provider_config: dict | None = None) -> dict:
        """测试 LLM API 连接"""
        try:
            if not provider_config:
                return {"success": False, "error": "No credentials provided for testing"}

            base_url = provider_config.get("base_url")
            api_key = provider_config.get("api_key")
            model = provider_config.get("model")

            if not base_url or not api_key or not model:
                return {"success": False, "error": "Base URL, API Key, and Model are required for testing"}

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
