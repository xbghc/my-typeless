"""语音转文字客户端 - 使用 OpenAI 兼容 API (Whisper)"""

import io
from openai import OpenAI
from my_typeless.config import STTConfig


class STTClient:
    """语音转文字客户端"""

    def __init__(self, config: STTConfig):
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def transcribe(self, audio_data: bytes, prompt: str = "") -> str:
        """
        将音频数据转录为文本

        Args:
            audio_data: WAV 格式的音频字节数据
            prompt: 可选的提示词，用于帮助 Whisper 正确识别专有名词
                    以及在增量转录时引导上下文连贯性

        Returns:
            转录的原始文本
        """
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "recording.wav"

        kwargs = {
            "model": self._config.model,
            "file": audio_file,
        }
        if prompt:
            kwargs["prompt"] = prompt
        if self._config.language:
            kwargs["language"] = self._config.language

        response = self._client.audio.transcriptions.create(**kwargs)
        return response.text

    def check_connection(self) -> None:
        """
        检查 API 连接是否正常
        通过尝试获取模型信息来验证 Base URL 和 API Key

        Raises:
            Exception: 如果连接失败或鉴权失败
        """
        self._client.models.retrieve(self._config.model)
