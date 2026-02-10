"""LLM 文本精修客户端 - 使用 OpenAI 兼容 API"""

from openai import OpenAI
from my_typeless.config import LLMConfig


class LLMClient:
    """LLM 文本精修客户端"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def refine(self, raw_text: str, system_prompt: str = "", context: str = "") -> str:
        """
        将口语文本精修为书面文字

        Args:
            raw_text: STT 产生的原始转录文本
            system_prompt: 可选的完整 system prompt（含术语表等），
                           未提供时回退到 config 中的基础 prompt
            context: 可选的前文已精修文本，用于增量精修时提供上下文连贯性，
                     LLM 将只精修 raw_text 部分而不重复输出 context

        Returns:
            精修后的书面文本
        """
        prompt = system_prompt or self._config.prompt

        if context:
            user_message = (
                f"前文（仅供参考上下文，请勿重复输出）：\n{context}\n\n"
                f"请精修以下新内容：\n{raw_text}"
            )
        else:
            user_message = raw_text

        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or raw_text
