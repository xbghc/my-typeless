"""配置管理模块 - 读写 JSON 配置文件"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

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
class STTConfig:
    base_url: str = "https://api.groq.com/openai/v1"
    api_key: str = ""
    model: str = "whisper-large-v3"


@dataclass
class LLMConfig:
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    prompt: str = field(default=DEFAULT_LLM_PROMPT)


@dataclass
class AppConfig:
    hotkey: str = "right alt"
    start_with_windows: bool = False
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    glossary: List[str] = field(default_factory=list)

    def build_llm_system_prompt(self) -> str:
        """组装完整的 LLM system prompt（基础 prompt + 术语表）"""
        parts = [self.llm.prompt]
        if self.glossary:
            terms = "\n".join(f"- {t}" for t in self.glossary)
            parts.append(
                "## 术语表\n"
                "以下是用户领域的专用术语，当它们出现在输入中时必须原样保留，"
                "不要替换为同音/近音词（如『制伏』不要改为『制服』）：\n"
                f"{terms}"
            )
        return "\n\n".join(parts)

    def build_stt_prompt(self) -> str:
        """组装 STT prompt（术语列表，帮助 Whisper 正确识别专有名词）"""
        if not self.glossary:
            return ""
        return ", ".join(self.glossary)

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
