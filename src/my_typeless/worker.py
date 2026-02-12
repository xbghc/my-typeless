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
_ERROR_SENTINEL = object()

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
        """开始录音，同时启动 STT 和 LLM 消费线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        self._segment_queue = queue.Queue()
        self._stt_queue = queue.Queue()
        self._recorder.start(on_segment=self._on_segment)

        # 启动 STT 线程（Audio -> Text）
        t_stt = threading.Thread(
            target=self._stt_task,
            args=(self._segment_queue, self._stt_queue),
            daemon=True,
        )
        t_stt.start()

        # 启动 LLM 线程（Text -> Refined Text）
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

    def _stt_task(self, segment_queue: queue.Queue, stt_queue: queue.Queue) -> None:
        """STT 消费者线程：音频 -> 文本"""
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
                    # item[1] is key_release_at
                    # 转发哨兵给 LLM 线程
                    stt_queue.put(item)
                    break

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

                if not text or not text.strip():
                    continue

                transcription_parts.append(text)
                stt_queue.put(text)

        except Exception as e:
            logger.error("STT processing error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))
            stt_queue.put(_ERROR_SENTINEL)

    def _llm_task(self, key_press_at: str, stt_queue: queue.Queue) -> None:
        """LLM 消费者线程：文本 -> 精修文本 -> 注入"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []

            key_release_at = ""

            while True:
                try:
                    item = stt_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if item is _ERROR_SENTINEL:
                    # 上游发生错误，中止
                    self.state_changed.emit("idle")
                    return

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # 收到文本片段
                raw_text = item
                raw_parts.append(raw_text)

                # LLM 精修：将已精修的前文作为上下文
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
            raw_text = "".join(raw_parts)
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

            # 记录历史
            add_history(
                raw_text, refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.result_ready.emit(refined_text)
            self.state_changed.emit("idle")

        except Exception as e:
            logger.error("LLM processing error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
