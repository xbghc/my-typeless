"""语音转文字客户端 - 使用 OpenAI 兼容 API (Whisper)"""

import io
from openai import OpenAI
from .config import STTConfig


class STTClient:
    """语音转文字客户端"""

    def __init__(self, config: STTConfig):
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def transcribe(self, audio_data: bytes) -> str:
        """
        将音频数据转录为文本

        Args:
            audio_data: WAV 格式的音频字节数据

        Returns:
            转录的原始文本
        """
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "recording.wav"

        response = self._client.audio.transcriptions.create(
            model=self._config.model,
            file=audio_file,
        )
        return response.text
