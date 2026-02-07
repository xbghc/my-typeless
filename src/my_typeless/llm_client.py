"""LLM 文本精修客户端 - 使用 OpenAI 兼容 API"""

from openai import OpenAI
from .config import LLMConfig


class LLMClient:
    """LLM 文本精修客户端"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def refine(self, raw_text: str) -> str:
        """
        将口语文本精修为书面文字

        Args:
            raw_text: STT 产生的原始转录文本

        Returns:
            精修后的书面文本
        """
        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": self._config.prompt},
                {"role": "user", "content": raw_text},
            ],
        )
        return response.choices[0].message.content or raw_text
