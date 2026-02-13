"""后台处理 - 录音 → 增量 STT → LLM → 文本注入"""

import logging
import queue
import threading
from datetime import datetime
from typing import Optional
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

    采用双线程流水线架构：
    1. STT 线程：从 audio queue 取音频 -> 转录 -> 放入 text queue
    2. LLM 线程：从 text queue 取文本 -> 精修 -> 累积 -> 最终注入

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
        self._text_queue: queue.Queue = queue.Queue()
        self._stt_thread: Optional[threading.Thread] = None
        self._llm_thread: Optional[threading.Thread] = None

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动流水线线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        self._segment_queue = queue.Queue()
        self._text_queue = queue.Queue()
        self._recorder.start(on_segment=self._on_segment)

        # 启动 STT 线程
        self._stt_thread = threading.Thread(
            target=self._stt_task,
            args=(self._segment_queue, self._text_queue),
            daemon=True,
        )
        self._stt_thread.start()

        # 启动 LLM 线程
        self._llm_thread = threading.Thread(
            target=self._llm_task,
            args=(self._key_press_at, self._text_queue),
            daemon=True,
        )
        self._llm_thread.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入队列并通知流水线结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._segment_queue.put(remaining)

        # 发送哨兵值（附带按键释放时间），告知 STT 线程录音结束
        self._segment_queue.put((_SENTINEL, key_release_at))
        self.state_changed.emit("processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    def _stt_task(self, segment_queue: queue.Queue, text_queue: queue.Queue) -> None:
        """STT 任务线程：消费音频片段，生产原始文本"""
        try:
            stt = STTClient(self._config.stt)
            base_stt_prompt = self._config.build_stt_prompt()
            transcription_parts: list[str] = []

            while True:
                try:
                    item = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    # 传递结束信号给 LLM 线程
                    # 携带 accumulated raw text 供 history 使用 (虽然 LLM 线程可以自己拼，但 STT 线程也可以传递)
                    # 为了简化，我们只传递 sentinel 和 key_release_at，raw_text 由 LLM 线程自己重组
                    # 实际上 LLM 线程收到的都是 raw_text 片段，它也有完整信息
                    text_queue.put((_SENTINEL, key_release_at))
                    break

                # STT Logic
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
                try:
                    text = stt.transcribe(item, prompt=stt_prompt)
                    logger.debug("Segment STT result: %r", text)

                    if text and text.strip():
                        transcription_parts.append(text)
                        text_queue.put(text)
                except Exception as e:
                    logger.error("STT error for segment: %s", e)
                    # 继续处理下一个片段，或者中断？通常继续尝试比较好
                    pass

        except Exception as e:
            logger.error("STT task loop error: %s", e, exc_info=True)
            self.error_occurred.emit(f"STT Error: {str(e)}")
            # 确保 LLM 线程也能结束
            text_queue.put((_SENTINEL, None))

    def _llm_task(self, key_press_at: str, text_queue: queue.Queue) -> None:
        """LLM 任务线程：消费原始文本，生产精修文本并注入"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []
            key_release_at: str | None = None

            while True:
                try:
                    item = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # Normal text segment
                raw_text = item
                raw_parts.append(raw_text)

                # LLM Logic
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                try:
                    refined = llm.refine(
                        raw_text,
                        system_prompt=llm_system_prompt,
                        context=llm_context,
                    )
                    logger.debug("Segment LLM result: %r", refined)
                    refined_parts.append(refined)
                except Exception as e:
                    logger.error("LLM error for segment: %s", e)
                    # Fallback: keep raw text as refined or just skip?
                    # Usually keeping raw text is safer if LLM fails
                    refined_parts.append(raw_text)

            # Finalization
            done_at = datetime.now().strftime(self._TIME_FMT)

            full_raw_text = "".join(raw_parts)
            full_refined_text = "".join(refined_parts)

            logger.debug("Full STT result: %r", full_raw_text)
            logger.debug("Full LLM result: %r", full_refined_text)

            if not full_raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.state_changed.emit("idle")
                return

            # Inject
            logger.debug("Injecting text...")
            inject_text(full_refined_text)
            logger.debug("Text injected successfully")

            # History
            if key_release_at: # Should be present if flow completed normally
                add_history(
                    full_raw_text, full_refined_text,
                    key_press_at=key_press_at,
                    key_release_at=key_release_at,
                    stt_done_at=done_at,
                    llm_done_at=done_at,
                )

            self.result_ready.emit(full_refined_text)

        except Exception as e:
            logger.error("LLM task loop error: %s", e, exc_info=True)
            self.error_occurred.emit(f"LLM Error: {str(e)}")

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
