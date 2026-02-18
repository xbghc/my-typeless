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

# 队列哨兵值，表示录音/处理结束
_SENTINEL = object()

# Whisper prompt 上限约 224 tokens；对中文约 400 字符，取尾部以保留最近上下文
_MAX_PROMPT_CHARS = 400


class Worker(QObject):
    """
    后台工作控制器，负责处理完整的语音→文本流水线

    采用并行流水线架构：
    1. Recorder 线程：采集音频，通过 _on_segment 推送至 _segment_queue
    2. STT 线程 (_stt_loop)：消费音频片段，转录后推送至 _text_queue
    3. LLM 线程 (_llm_loop)：消费转录文本，进行精修，最终注入文本并记录历史

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
        # 队列在 start_recording 时初始化
        self._segment_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动 STT 和 LLM 处理线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.state_changed.emit("recording")

        # 初始化队列
        self._segment_queue = queue.Queue()
        self._text_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动 STT 线程（消费音频，生产文本）
        t_stt = threading.Thread(
            target=self._stt_loop,
            args=(self._segment_queue, self._text_queue),
            daemon=True,
        )
        t_stt.start()

        # 启动 LLM 线程（消费文本，生产最终结果）
        t_llm = threading.Thread(
            target=self._llm_loop,
            args=(self._key_press_at, self._text_queue),
            daemon=True,
        )
        t_llm.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入队列并通知处理线程结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._segment_queue.put(remaining)

        # 发送哨兵值（附带按键释放时间）到 STT 队列
        # STT 线程处理完哨兵后，会将哨兵传递给 LLM 队列
        self._segment_queue.put((_SENTINEL, key_release_at))
        self.state_changed.emit("processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    def _stt_loop(self, segment_queue: queue.Queue, text_queue: queue.Queue) -> None:
        """STT 线程：从 segment_queue 获取音频，转录后放入 text_queue"""
        try:
            stt = STTClient(self._config.stt)
            base_stt_prompt = self._config.build_stt_prompt()
            transcription_parts: list[str] = []

            while True:
                try:
                    item = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 检查哨兵
                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    # 将哨兵传递给下一级队列，附带 STT 完成时间（近似）
                    stt_done_at = datetime.now().strftime(self._TIME_FMT)
                    text_queue.put((_SENTINEL, key_release_at, stt_done_at))
                    break

                # STT 处理逻辑
                # 构建 prompt：累积转录尾部 + 术语表
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
                    # 即使单个片段出错，也不中断整个流程，继续处理下一个
                    continue

        except Exception as e:
            logger.error("STT loop critical error: %s", e, exc_info=True)
            # 发生严重错误时，仍需发送哨兵以防 LLM 线程挂起
            # 使用当前时间作为 release time 的后备
            fallback_time = datetime.now().strftime(self._TIME_FMT)
            text_queue.put((_SENTINEL, fallback_time, fallback_time))
            self.error_occurred.emit(f"STT Error: {str(e)}")

    def _llm_loop(self, key_press_at: str, text_queue: queue.Queue) -> None:
        """LLM 线程：从 text_queue 获取文本，精修后汇总处理"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []
            key_release_at = ""
            stt_done_at = ""

            while True:
                try:
                    item = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 检查哨兵
                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    stt_done_at = item[2]
                    break

                # LLM 处理逻辑
                text = item # item is raw text string
                raw_parts.append(text)

                # LLM 精修：将已精修的前文作为上下文
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")

                try:
                    refined = llm.refine(
                        text,
                        system_prompt=llm_system_prompt,
                        context=llm_context,
                    )
                    logger.debug("Segment LLM result: %r", refined)
                    refined_parts.append(refined)
                except Exception as e:
                    logger.error("LLM error for segment: %s", e)
                    # 如果 LLM 失败，保留原文以确保内容不丢失
                    refined_parts.append(text)

            llm_done_at = datetime.now().strftime(self._TIME_FMT)

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
            try:
                inject_text(refined_text)
                logger.debug("Text injected successfully")
            except Exception as e:
                logger.error("Injection failed: %s", e)
                self.error_occurred.emit(f"Injection Error: {str(e)}")
                # 即使注入失败，也尝试记录历史

            # 记录历史
            try:
                # 如果 stt_done_at 为空（例如异常退出），使用 llm_done_at
                final_stt_at = stt_done_at if stt_done_at else llm_done_at
                final_release_at = key_release_at if key_release_at else llm_done_at

                add_history(
                    raw_text, refined_text,
                    key_press_at=key_press_at,
                    key_release_at=final_release_at,
                    stt_done_at=final_stt_at,
                    llm_done_at=llm_done_at,
                )
            except Exception as e:
                logger.error("History save failed: %s", e)

            self.result_ready.emit(refined_text)

        except Exception as e:
            logger.error("LLM loop critical error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))

        finally:
            self.state_changed.emit("idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
