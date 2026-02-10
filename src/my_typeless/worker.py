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

    采用 STT 和 LLM 双线程流水线架构：
    1. STT 线程：消费音频片段，生成 STT 原始文本，送入中间队列。
    2. LLM 线程：消费 STT 原始文本，结合上下文精修，累积结果。

    这样当第 N 段音频在 STT 时，第 N-1 段文本可以并行进行 LLM 精修，
    显著降低多段语音输入的总延迟。

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
        # 两个队列构成流水线
        self._stt_queue: queue.Queue = queue.Queue()
        self._llm_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动流水线线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        # 初始化新会话的队列
        self._stt_queue = queue.Queue()
        self._llm_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动流水线线程
        # 1. STT 消费者（生产 raw_text 给 LLM）
        t_stt = threading.Thread(
            target=self._stt_loop,
            args=(self._stt_queue, self._llm_queue),
            daemon=True,
        )
        t_stt.start()

        # 2. LLM 消费者（生产最终 refined_text）
        t_llm = threading.Thread(
            target=self._llm_loop,
            args=(self._llm_queue, self._key_press_at),
            daemon=True,
        )
        t_llm.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入 STT 队列并通知流水线结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._stt_queue.put(remaining)

        # 发送哨兵值给 STT 队列，告知不再有新音频
        self._stt_queue.put((_SENTINEL, key_release_at))
        self.state_changed.emit("processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._stt_queue.put(wav_data)

    def _stt_loop(self, stt_queue: queue.Queue, llm_queue: queue.Queue) -> None:
        """STT 线程：音频 -> 原始文本 -> LLM 队列"""
        try:
            stt = STTClient(self._config.stt)
            base_stt_prompt = self._config.build_stt_prompt()
            transcription_parts: list[str] = []

            while True:
                try:
                    item = stt_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 检查哨兵：(_SENTINEL, key_release_at)
                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    # 转发结束信号给 LLM 队列
                    # 格式：(raw_text, is_last, key_release_at)
                    llm_queue.put(("", True, key_release_at))
                    break

                # 处理音频
                # STT prompt: 累积转录尾部 + 术语表
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
                    # 发送中间结果给 LLM 队列
                    llm_queue.put((text, False, None))

        except Exception as e:
            logger.error("STT loop error: %s", e, exc_info=True)
            self.error_occurred.emit(f"STT Error: {str(e)}")
            # 确保 LLM 队列也能解除阻塞
            llm_queue.put(("", True, None))

    def _llm_loop(self, llm_queue: queue.Queue, key_press_at: str) -> None:
        """LLM 线程：原始文本 -> 精修文本 -> 最终处理"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []

            while True:
                try:
                    # 格式：(raw_text, is_last, key_release_at)
                    item = llm_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                raw_text, is_last, key_release_at = item

                if raw_text:
                    raw_parts.append(raw_text)

                    # LLM 精修：使用已精修的前文作为上下文
                    llm_context = "".join(refined_parts)
                    logger.debug("Refining segment...")
                    refined = llm.refine(
                        raw_text,
                        system_prompt=llm_system_prompt,
                        context=llm_context,
                    )
                    logger.debug("Segment LLM result: %r", refined)
                    refined_parts.append(refined)

                if is_last:
                    done_at = datetime.now().strftime(self._TIME_FMT)

                    full_raw = "".join(raw_parts)
                    full_refined = "".join(refined_parts)

                    logger.debug("Full STT result: %r", full_raw)
                    logger.debug("Full LLM result: %r", full_refined)

                    if not full_raw.strip():
                        logger.debug("Empty result, skipping")
                        self.state_changed.emit("idle")
                        return

                    # 注入文本
                    logger.debug("Injecting text...")
                    inject_text(full_refined)
                    logger.debug("Text injected successfully")

                    # 记录历史
                    # 注意：key_release_at 可能为 None（如果异常导致提前结束）
                    add_history(
                        full_raw, full_refined,
                        key_press_at=key_press_at,
                        key_release_at=key_release_at or done_at,
                        stt_done_at=done_at,
                        llm_done_at=done_at,
                    )

                    self.result_ready.emit(full_refined)
                    break

        except Exception as e:
            logger.error("LLM loop error: %s", e, exc_info=True)
            self.error_occurred.emit(f"LLM Error: {str(e)}")

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
