"""LLM 文本精修客户端 - 支持 OpenAI 兼容 API 和 Anthropic API"""

from anthropic import Anthropic
from openai import OpenAI

from my_typeless.config import LLMConfig


class LLMClient:
    """LLM 文本精修客户端"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._provider_type = (
            config.active_provider.provider_type if config.active_provider else "openai"
        )

        base_url = config.active_provider.base_url if config.active_provider else ""
        api_key = config.active_provider.api_key if config.active_provider else ""

        if self._provider_type == "anthropic":
            self._client = Anthropic(api_key=api_key, base_url=base_url if base_url else None)
        else:
            self._client = OpenAI(base_url=base_url, api_key=api_key)

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

        if self._provider_type == "anthropic":
            response = self._client.messages.create(
                model=self._config.active_model,
                system=prompt,
                messages=[
                    {"role": "user", "content": user_message},
                ],
                max_tokens=4096,
            )
            return response.content[0].text or raw_text
        else:
            response = self._client.chat.completions.create(
                model=self._config.active_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return response.choices[0].message.content or raw_text
