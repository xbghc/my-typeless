"""配置管理模块 - 读写 JSON 配置文件"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# 开发模式：每次启动强制使用代码中的最新提示词
# 生产模式：仅首次初始化时设置默认提示词，之后用户可自行修改
# 通过环境变量 MY_TYPELESS_DEV=0 可切换到生产模式
DEV_MODE = os.environ.get("MY_TYPELESS_DEV", "1") == "1"


CONFIG_DIR = Path.home() / ".my-typeless"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_LLM_PROMPT = (
    "你是一个语音转书面文字的精修助手。用户通过麦克风口述，STT 引擎转录后发给你。\n"
    "\n"
    "## 任务\n"
    "将口语转录文本精修为可直接使用的书面文字。\n"
    "\n"
    "## 规则\n"
    "1. **去噪**：删除口头禅（嗯、啊、那个、就是说）、无意义的重复、自我纠正（'不对，应该是……'只保留纠正后的内容）\n"
    "2. **保意**：忠实保留用户最终想表达的完整意图，不增删实质内容。注意区分'真正的重复'和'结构相似但含义不同的并列表述'，后者必须保留\n"
    "3. **语言**：保持原始语言不变（中文输入输出中文，英文输入输出英文，中英混合则保持混合）\n"
    "4. **标点**：补全标点符号，使用正确的中文/英文标点\n"
    "5. **格式**：如果内容包含列表、步骤等结构化信息，可适当用换行或编号整理\n"
    "6. **简短输入**：如果输入很短（几个词），直接输出修正后的词句，不要扩写\n"
    "7. **代码/专有名词**：保留技术术语、代码片段、人名、产品名的原始写法\n"
    "8. **句式**：保留原始句式——疑问句仍为疑问句，祈使句仍为祈使句，不要将问题改写为陈述\n"
    "\n"
    "## 输出\n"
    "只输出精修后的文本，不要解释、不要引号包裹、不要前缀。"
)


@dataclass
class ProviderConfig:
    id: str
    name: str
    base_url: str
    api_key: str
    models: list[str] = field(default_factory=list)
    provider_type: str = field(default="openai")


@dataclass
class STTConfig:
    providers: list[ProviderConfig] = field(
        default_factory=lambda: [
            ProviderConfig(
                id="default-stt",
                name="Groq",
                base_url="https://api.groq.com/openai/v1",
                api_key="",
                models=["whisper-large-v3"],
            )
        ]
    )
    active_provider_id: str = "default-stt"
    active_model: str = "whisper-large-v3"
    language: str = ""  # 语言代码（如 "zh"），留空则自动检测

    @property
    def active_provider(self) -> ProviderConfig | None:
        for p in self.providers:
            if p.id == self.active_provider_id:
                return p
        return self.providers[0] if self.providers else None


@dataclass
class LLMConfig:
    providers: list[ProviderConfig] = field(
        default_factory=lambda: [
            ProviderConfig(
                id="default-llm",
                name="DeepSeek",
                base_url="https://api.deepseek.com/v1",
                api_key="",
                models=["deepseek-chat"],
            )
        ]
    )
    active_provider_id: str = "default-llm"
    active_model: str = "deepseek-chat"
    prompt: str = field(default=DEFAULT_LLM_PROMPT)

    @property
    def active_provider(self) -> ProviderConfig | None:
        for p in self.providers:
            if p.id == self.active_provider_id:
                return p
        return self.providers[0] if self.providers else None


@dataclass
class AppConfig:
    hotkey: str = "right alt"
    start_with_windows: bool = False
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    glossary: list[str] = field(default_factory=list)

    def build_llm_system_prompt(self) -> str:
        """组装完整的 LLM system prompt（基础 prompt，预留扩展点）"""
        parts = [self.llm.prompt]
        # 未来可在此追加 user_context 等段落
        return "\n\n".join(parts)

    def build_stt_prompt(self) -> str:
        """组装 STT prompt（术语列表，帮助 Whisper 正确识别专有名词）

        Whisper 将 prompt 视为"此前已转录的文本"，用中文顿号连接术语
        使其更贴合中文转录上下文，避免使用指令性语句。
        """
        if not self.glossary:
            return ""
        return "、".join(self.glossary)

    def save(self) -> None:
        """保存配置到 JSON 文件"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls) -> "AppConfig":
        """从 JSON 文件加载配置，文件不存在则返回默认配置"""
        if not CONFIG_FILE.exists():
            config = cls()
            config.save()
            return config

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

            # Migration logic for STT
            stt_data = data.get("stt", {})
            stt_providers = []
            if "providers" in stt_data:
                stt_providers = [ProviderConfig(**p) for p in stt_data["providers"]]
            elif "base_url" in stt_data:
                # Migrate legacy STT config
                stt_providers = [
                    ProviderConfig(
                        id="migrated-stt",
                        name="Legacy STT",
                        base_url=stt_data.get("base_url", "https://api.groq.com/openai/v1"),
                        api_key=stt_data.get("api_key", ""),
                        models=[stt_data.get("model", "whisper-large-v3")],
                    )
                ]
            else:
                stt_providers = STTConfig().providers

            active_stt_id = stt_data.get(
                "active_provider_id",
                "migrated-stt"
                if "base_url" in stt_data and "providers" not in stt_data
                else "default-stt",
            )
            active_stt_model = stt_data.get(
                "active_model", stt_data.get("model", "whisper-large-v3")
            )
            stt = STTConfig(
                providers=stt_providers,
                active_provider_id=active_stt_id,
                active_model=active_stt_model,
                language=stt_data.get("language", ""),
            )

            # Migration logic for LLM
            llm_data = data.get("llm", {})
            llm_providers = []
            if "providers" in llm_data:
                llm_providers = [ProviderConfig(**p) for p in llm_data["providers"]]
            elif "base_url" in llm_data:
                # Migrate legacy LLM config
                llm_providers = [
                    ProviderConfig(
                        id="migrated-llm",
                        name="Legacy LLM",
                        base_url=llm_data.get("base_url", "https://api.deepseek.com/v1"),
                        api_key=llm_data.get("api_key", ""),
                        models=[llm_data.get("model", "deepseek-chat")],
                    )
                ]
            else:
                llm_providers = LLMConfig().providers

            active_llm_id = llm_data.get(
                "active_provider_id",
                "migrated-llm"
                if "base_url" in llm_data and "providers" not in llm_data
                else "default-llm",
            )
            active_llm_model = llm_data.get("active_model", llm_data.get("model", "deepseek-chat"))
            llm = LLMConfig(
                providers=llm_providers,
                active_provider_id=active_llm_id,
                active_model=active_llm_model,
                prompt=llm_data.get("prompt", DEFAULT_LLM_PROMPT),
            )

            glossary = data.get("glossary", [])
            if not isinstance(glossary, list):
                glossary = []

            config = cls(
                hotkey=data.get("hotkey", "right alt"),
                start_with_windows=data.get("start_with_windows", False),
                stt=stt,
                llm=llm,
                glossary=glossary,
            )
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            config = cls()

        # 开发模式下强制使用代码中的最新提示词
        if DEV_MODE:
            config.llm.prompt = DEFAULT_LLM_PROMPT

        config.save()
        return config

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            stt = STTConfig(**data.get("stt", {}))
            llm = LLMConfig(**data.get("llm", {}))
            glossary = data.get("glossary", [])
            if not isinstance(glossary, list):
                glossary = []
            config = cls(
                hotkey=data.get("hotkey", "right alt"),
                start_with_windows=data.get("start_with_windows", False),
                stt=stt,
                llm=llm,
                glossary=glossary,
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            config = cls()

        # 开发模式下强制使用代码中的最新提示词
        if DEV_MODE:
            config.llm.prompt = DEFAULT_LLM_PROMPT

        config.save()
        return config
