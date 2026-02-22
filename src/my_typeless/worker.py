"""后台处理 - 录音 → 增量 STT → LLM → 文本注入"""

import logging
import queue
import threading
from datetime import datetime
from typing import Optional

from my_typeless.config import AppConfig
from my_typeless.events import EventEmitter
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


class Worker:
    """
    后台工作控制器，负责处理完整的语音→文本流水线

    采用双线程流水线架构：
    Thread 1 (Audio): 录音片段 -> STT -> 原始文本 -> 文本队列
    Thread 2 (Text):  文本队列 -> LLM -> 精修文本 -> 注入 & 历史

    优势：STT 和 LLM 的 IO 等待时间并行化，显著降低总延迟。
    """

    _TIME_FMT = "%H:%M:%S.%f"

    def __init__(self, config: AppConfig):
        self.events = EventEmitter()
        self._config = config
        self._recorder = Recorder()
        self._key_press_at: str = ""
        self._segment_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()

        # 缓存客户端实例，避免重复初始化
        self._stt_client: Optional[STTClient] = None
        self._llm_client: Optional[LLMClient] = None

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config
        # 配置变更后失效缓存
        self._stt_client = None
        self._llm_client = None

    def _get_stt_client(self) -> STTClient:
        if self._stt_client is None:
            self._stt_client = STTClient(self._config.stt)
        return self._stt_client

    def _get_llm_client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient(self._config.llm)
        return self._llm_client

    def start_recording(self) -> None:
        """开始录音，同时启动流水线线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.events.emit("state_changed", "recording")

        self._segment_queue = queue.Queue()
        self._text_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动音频处理线程 (Producer)
        t_audio = threading.Thread(
            target=self._process_audio,
            args=(self._segment_queue, self._text_queue),
            daemon=True,
        )
        t_audio.start()

        # 启动文本处理线程 (Consumer)
        t_text = threading.Thread(
            target=self._process_text,
            args=(self._text_queue, self._key_press_at),
            daemon=True,
        )
        t_text.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入队列并通知消费线程结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._segment_queue.put(remaining)

        # 发送哨兵值给音频线程
        self._segment_queue.put((_SENTINEL, key_release_at))
        self.events.emit("state_changed", "processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    def _handle_error(self, e: Exception) -> None:
        """统一错误处理"""
        logger.error("Processing error: %s", e, exc_info=True)
        try:
            import openai
            if isinstance(e, openai.AuthenticationError):
                self.events.emit("error_occurred", "API 密钥无效或已过期，请在设置中检查 API Key 是否正确。", True)
            elif isinstance(e, openai.APIConnectionError):
                self.events.emit("error_occurred", "无法连接到 API 服务器，请检查网络连接和 API 地址是否正确。", True)
            elif isinstance(e, openai.NotFoundError):
                self.events.emit("error_occurred", "API 模型或接口未找到，请检查模型名称和 API 地址是否正确。", True)
            elif isinstance(e, openai.BadRequestError):
                self.events.emit("error_occurred", f"API 请求参数错误：{e.message if hasattr(e, 'message') else str(e)}", True)
            elif isinstance(e, openai.APITimeoutError):
                self.events.emit("error_occurred", "API 请求超时，请检查网络连接或稍后重试。", False)
            elif isinstance(e, openai.RateLimitError):
                self.events.emit("error_occurred", "API 请求过于频繁，请稍后再试或检查额度是否充足。", False)
            elif isinstance(e, openai.APIStatusError):
                self.events.emit("error_occurred", f"API 服务异常 (HTTP {e.status_code})，请稍后重试。", False)
            else:
                self.events.emit("error_occurred", f"发生未知错误：{e}", False)
        except Exception:
             self.events.emit("error_occurred", f"发生未知错误：{e}", False)

    def _process_audio(self, segment_queue: queue.Queue, text_queue: queue.Queue) -> None:
        """Pipeline Stage 1: Audio -> STT -> Raw Text"""
        try:
            stt = self._get_stt_client()
            base_stt_prompt = self._config.build_stt_prompt()
            transcription_parts: list[str] = []

            while True:
                try:
                    item = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    # Pass sentinel to Stage 2
                    text_queue.put((_SENTINEL, key_release_at))
                    break

                # STT prompt construction
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
                    text_queue.put(text)

        except Exception as e:
            self._handle_error(e)
            # Propagate error shutdown to next stage
            text_queue.put((_SENTINEL, None))

    def _process_text(self, text_queue: queue.Queue, key_press_at: str) -> None:
        """Pipeline Stage 2: Raw Text -> LLM -> Inject"""
        try:
            llm = self._get_llm_client()
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []
            key_release_at: Optional[str] = None

            while True:
                try:
                    item = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # item is raw text string
                text = item
                raw_parts.append(text)

                # LLM refinement
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    text,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            # Pipeline finished
            done_at = datetime.now().strftime(self._TIME_FMT)

            raw_text = "".join(raw_parts)
            refined_text = "".join(refined_parts)
            logger.debug("Full STT result: %r", raw_text)
            logger.debug("Full LLM result: %r", refined_text)

            if not raw_text.strip():
                logger.debug("Empty STT result, skipping")
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

            self.events.emit("result_ready", refined_text)

        except Exception as e:
            self._handle_error(e)

        finally:
            self.events.emit("state_changed", "idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
