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
# 错误哨兵，表示上游任务出错
_ERROR_SENTINEL = object()

# Whisper prompt 上限约 224 tokens；对中文约 400 字符，取尾部以保留最近上下文
_MAX_PROMPT_CHARS = 400


class Worker(QObject):
    """
    后台工作控制器，负责处理完整的语音→文本流水线

    采用流水线并行架构：
    1. STT 线程：逐个处理音频片段，结果存入中间队列
    2. LLM 线程：从中间队列取 STT 结果进行精修

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

        # 两个队列实现流水线
        self._stt_queue: queue.Queue = queue.Queue()  # Audio chunks
        self._llm_queue: queue.Queue = queue.Queue()  # STT text results

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动 STT 和 LLM 线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        # 重置队列
        self._stt_queue = queue.Queue()
        self._llm_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动 STT 线程 (Producer for LLM)
        t_stt = threading.Thread(
            target=self._stt_task,
            args=(self._stt_queue, self._llm_queue),
            daemon=True,
        )
        t_stt.start()

        # 启动 LLM 线程 (Consumer)
        t_llm = threading.Thread(
            target=self._llm_task,
            args=(self._key_press_at, self._llm_queue),
            daemon=True,
        )
        t_llm.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入 STT 队列"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._stt_queue.put(remaining)

        # 发送哨兵值给 STT 线程
        self._stt_queue.put((_SENTINEL, key_release_at))
        self.state_changed.emit("processing")

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._stt_queue.put(wav_data)

    # ------------------------------------------------------------------
    # 任务线程
    # ------------------------------------------------------------------

    def _stt_task(self, in_queue: queue.Queue, out_queue: queue.Queue) -> None:
        """STT 线程：消费音频 -> 生产文本"""
        try:
            stt = STTClient(self._config.stt)
            base_stt_prompt = self._config.build_stt_prompt()
            transcription_parts: list[str] = []

            while True:
                item = in_queue.get()

                # 检查哨兵
                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    # 将哨兵透传给 LLM 线程
                    out_queue.put((_SENTINEL, key_release_at))
                    break

                # STT prompt 逻辑
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

                if text and text.strip():
                    transcription_parts.append(text)
                    out_queue.put(text)

        except Exception as e:
            logger.error("STT task error: %s", e, exc_info=True)
            self.error_occurred.emit(f"STT Error: {str(e)}")
            out_queue.put(_ERROR_SENTINEL)

    def _llm_task(self, key_press_at: str, in_queue: queue.Queue) -> None:
        """LLM 线程：消费文本 -> 精修 -> 注入"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []

            while True:
                item = in_queue.get()

                if item is _ERROR_SENTINEL:
                    logger.warning("LLM task received error sentinel, aborting.")
                    return

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # item is text
                text = item
                raw_parts.append(text)

                # LLM Context
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    text,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            # 所有分段处理完毕
            done_at = datetime.now().strftime(self._TIME_FMT)

            raw_text = "".join(raw_parts)
            refined_text = "".join(refined_parts)
            logger.debug("Full STT result: %r", raw_text)
            logger.debug("Full LLM result: %r", refined_text)

            if not raw_text.strip():
                logger.debug("Empty result, skipping")
                self.state_changed.emit("idle")
                return

            logger.debug("Injecting text...")
            inject_text(refined_text)
            logger.debug("Text injected successfully")

            add_history(
                raw_text, refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.result_ready.emit(refined_text)

        except Exception as e:
            logger.error("LLM task error: %s", e, exc_info=True)
            self.error_occurred.emit(f"LLM Error: {str(e)}")

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
