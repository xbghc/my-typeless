"""后台处理 - 录音 → STT → LLM → 文本注入"""

import logging
import threading
from PyQt6.QtCore import QObject, pyqtSignal

from my_typeless.config import AppConfig
from my_typeless.recorder import Recorder
from my_typeless.stt_client import STTClient
from my_typeless.llm_client import LLMClient
from my_typeless.text_injector import inject_text
from my_typeless.history import add_history

logger = logging.getLogger(__name__)


class Worker(QObject):
    """
    后台工作控制器，负责处理完整的语音→文本流水线

    每次处理启动一个新的 daemon 线程（QThread 不支持重复 start）

    Signals:
        state_changed(str): 状态变化 ("idle" / "recording" / "processing")
        result_ready(str): 精修文本就绪
        error_occurred(str): 发生错误
    """

    state_changed = pyqtSignal(str)
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self._config = config
        self._recorder = Recorder()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音"""
        logger.debug("start_recording called")
        self.state_changed.emit("recording")
        self._recorder.start()

    def stop_recording_and_process(self) -> None:
        """停止录音并在新线程中启动处理流程"""
        logger.debug("stop_recording_and_process called")
        audio_data = self._recorder.stop()
        if not audio_data:
            logger.debug("No audio data recorded")
            self.state_changed.emit("idle")
            return

        logger.debug("Got %d bytes of audio", len(audio_data))
        self.state_changed.emit("processing")

        # 每次用新的 daemon 线程处理 API 调用
        t = threading.Thread(
            target=self._process, args=(audio_data,), daemon=True
        )
        t.start()

    def _process(self, audio_data: bytes) -> None:
        """在后台线程中执行：STT → LLM → 注入文本"""
        try:
            # 1. 语音转文字
            logger.debug("Starting STT...")
            stt = STTClient(self._config.stt)
            stt_prompt = self._config.build_stt_prompt()
            raw_text = stt.transcribe(audio_data, prompt=stt_prompt)
            logger.debug("STT result: %r", raw_text)

            if not raw_text or not raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.state_changed.emit("idle")
                return

            # 2. LLM 精修
            logger.debug("Starting LLM refinement...")
            llm = LLMClient(self._config.llm)
            system_prompt = self._config.build_llm_system_prompt()
            refined_text = llm.refine(raw_text, system_prompt=system_prompt)
            logger.debug("LLM result: %r", refined_text)

            # 3. 注入文本
            logger.debug("Injecting text...")
            inject_text(refined_text)
            logger.debug("Text injected successfully")

            # 4. 记录历史
            add_history(raw_text, refined_text)

            self.result_ready.emit(refined_text)

        except Exception as e:
            logger.error("Processing error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
