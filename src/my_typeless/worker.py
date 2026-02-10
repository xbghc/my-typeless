"""后台处理 - 录音 → 增量 STT → LLM → 文本注入"""

import logging
import queue
import threading
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

from my_typeless.config import AppConfig
from my_typeless.recorder import Recorder
from my_typeless.stt_client import STTClient
from my_typeless.llm_client import LLMClient
from my_typeless.text_injector import inject_text
from my_typeless.history import add_history

logger = logging.getLogger(__name__)

# 队列哨兵值，表示录音结束、不再有新片段
_SENTINEL = object()

# Whisper prompt 上限约 224 tokens；对中文约 400 字符，取尾部以保留最近上下文
_MAX_PROMPT_CHARS = 400


class Worker(QObject):
    """
    后台工作控制器，负责处理完整的语音→文本流水线

    录音过程中检测停顿，将已有的音频片段立即提交转录，
    从而在用户松开按键时大部分音频已完成转录，显著降低延迟。

    Signals:
        state_changed(str): 状态变化 ("idle" / "recording" / "processing")
        result_ready(str): 精修文本就绪
        error_occurred(str): 发生错误
    """

    state_changed = pyqtSignal(str)
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    _TIME_FMT = "%H:%M:%S.%f"

    def __init__(self, config: AppConfig):
        super().__init__()
        self._config = config
        self._recorder = Recorder()
        self._key_press_at: str = ""
        self._segment_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动增量转录消费线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        self._segment_queue = queue.Queue()
        self._recorder.start(on_segment=self._on_segment)

        # 启动增量转录消费线程（录音期间即开始转录）
        # 将队列作为参数传入，避免与后续录音会话的队列混淆
        t = threading.Thread(
            target=self._incremental_process,
            args=(self._key_press_at, self._segment_queue),
            daemon=True,
        )
        t.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入队列并通知消费线程结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._segment_queue.put(remaining)

        # 发送哨兵值（附带按键释放时间），告知消费线程不再有新片段
        self._segment_queue.put((_SENTINEL, key_release_at))
        self.state_changed.emit("processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    def _incremental_process(self, key_press_at: str, segment_queue: queue.Queue) -> None:
        """增量处理消费线程：逐段 STT → LLM 精修 → 拼接 → 注入文本"""
        try:
            stt = STTClient(self._config.stt)
            llm = LLMClient(self._config.llm)
            base_stt_prompt = self._config.build_stt_prompt()
            llm_system_prompt = self._config.build_llm_system_prompt()

            transcription_parts: list[str] = []
            refined_parts: list[str] = []

            # 持续从队列中取出音频片段，逐段完成 STT + LLM
            while True:
                try:
                    item = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # STT prompt: 累积转录尾部 + 术语表（Whisper 从前截断，术语放尾部确保保留）
                if transcription_parts:
                    accumulated = "".join(transcription_parts)
                    if base_stt_prompt:
                        tail_budget = _MAX_PROMPT_CHARS - len(base_stt_prompt) - 1
                        tail = accumulated[-tail_budget:] if tail_budget > 0 else ""
                        stt_prompt = f"{tail} {base_stt_prompt}" if tail else base_stt_prompt
                    else:
                        stt_prompt = accumulated[-_MAX_PROMPT_CHARS:]
                else:
                    stt_prompt = base_stt_prompt

                logger.debug("Transcribing segment (%d bytes)...", len(item))
                text = stt.transcribe(item, prompt=stt_prompt)
                logger.debug("Segment STT result: %r", text)

                if not text or not text.strip():
                    continue

                transcription_parts.append(text)

                # LLM 精修：将已精修的前文作为上下文
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    text,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            done_at = datetime.now().strftime(self._TIME_FMT)

            # 拼接全部结果
            raw_text = "".join(transcription_parts)
            refined_text = "".join(refined_parts)
            logger.debug("Full STT result: %r", raw_text)
            logger.debug("Full LLM result: %r", refined_text)

            if not raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.state_changed.emit("idle")
                return

            # 注入文本
            logger.debug("Injecting text...")
            inject_text(refined_text)
            logger.debug("Text injected successfully")

            # 记录历史（增量模式下 STT 和 LLM 交替进行，完成时间相同）
            add_history(
                raw_text, refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.result_ready.emit(refined_text)

        except Exception as e:
            logger.error("Processing error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
