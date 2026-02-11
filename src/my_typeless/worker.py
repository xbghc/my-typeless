"""后台处理 - 录音 → 增量 STT → LLM → 文本注入"""

import logging
import queue
import threading
from datetime import datetime
from typing import Optional, Tuple, Union

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

    采用并行流水线架构：
    Thread 1 (STT): 录音片段 -> STT -> 中间队列
    Thread 2 (LLM): 中间队列 -> LLM -> 累积结果 -> 最终注入

    从而在处理片段 N 的 LLM 精修时，并行处理片段 N+1 的 STT 转录，
    显著降低总延迟。

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
        self._stt_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动流水线处理线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        # 初始化队列
        self._segment_queue = queue.Queue()
        self._stt_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动 STT 线程
        t_stt = threading.Thread(
            target=self._stt_task,
            args=(self._segment_queue, self._stt_queue),
            daemon=True,
        )
        t_stt.start()

        # 启动 LLM 线程
        t_llm = threading.Thread(
            target=self._llm_task,
            args=(self._key_press_at, self._stt_queue),
            daemon=True,
        )
        t_llm.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入队列并通知消费线程结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._segment_queue.put(remaining)

        # 发送哨兵值（附带按键释放时间），告知 STT 线程不再有新片段
        self._segment_queue.put((_SENTINEL, key_release_at))
        self.state_changed.emit("processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    def _stt_task(self, segment_queue: queue.Queue, stt_queue: queue.Queue) -> None:
        """STT 工作线程：消费音频片段，生产原始文本"""
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
                    # 传递哨兵给 LLM 线程
                    stt_queue.put((_SENTINEL, key_release_at))
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
                    stt_queue.put((text, None))

        except Exception as e:
            logger.error("STT task error: %s", e, exc_info=True)
            self.error_occurred.emit(f"STT Error: {e}")
            # 发生错误时也要确保下游 LLM 线程能退出
            stt_queue.put((_SENTINEL, None))

    def _llm_task(self, key_press_at: str, stt_queue: queue.Queue) -> None:
        """LLM 工作线程：消费原始文本，生产精修文本并注入"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            transcription_parts: list[str] = []
            refined_parts: list[str] = []
            key_release_at: Optional[str] = None

            while True:
                try:
                    item = stt_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                content, meta = item
                if content is _SENTINEL:
                    key_release_at = meta
                    break

                raw_text = content
                transcription_parts.append(raw_text)

                # LLM 精修
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    raw_text,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            done_at = datetime.now().strftime(self._TIME_FMT)

            # 拼接全部结果
            full_raw_text = "".join(transcription_parts)
            full_refined_text = "".join(refined_parts)
            logger.debug("Full STT result: %r", full_raw_text)
            logger.debug("Full LLM result: %r", full_refined_text)

            if not full_raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.state_changed.emit("idle")
                return

            # 注入文本
            logger.debug("Injecting text...")
            inject_text(full_refined_text)
            logger.debug("Text injected successfully")

            # 记录历史
            add_history(
                full_raw_text, full_refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.result_ready.emit(full_refined_text)

        except Exception as e:
            logger.error("LLM task error: %s", e, exc_info=True)
            self.error_occurred.emit(f"LLM/Injector Error: {e}")

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
