"""LLM 文本精修客户端 - 使用 OpenAI 兼容 API"""

from __future__ import annotations
from typing import TYPE_CHECKING

from openai import OpenAI
from .config import LLMConfig

if TYPE_CHECKING:
    from .history import CorrectionEntry


class LLMClient:
    """LLM 文本精修客户端"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def refine(self, raw_text: str, corrections: list[CorrectionEntry] | None = None) -> str:
        """
        将口语文本精修为书面文字

        Args:
            raw_text: STT 产生的原始转录文本
            corrections: 用户修正记录，作为 few-shot 示例引导输出风格

        Returns:
            精修后的书面文本
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._config.prompt},
        ]

        # 将用户修正作为 few-shot 示例（倒序排列，最旧的在前）
        if corrections:
            for c in reversed(corrections):
                messages.append({"role": "user", "content": c.raw_input})
                messages.append({"role": "assistant", "content": c.corrected_output})

        messages.append({"role": "user", "content": raw_text})

        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=messages,
        )
        return response.choices[0].message.content or raw_text
