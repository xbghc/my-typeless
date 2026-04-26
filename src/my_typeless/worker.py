"""后台处理 - 录音 → 增量 STT → LLM → 文本注入"""

import logging
import queue
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from my_typeless.config import AppConfig
from my_typeless.events import EventEmitter
from my_typeless.history import add_history
from my_typeless.llm_client import LLMClient
from my_typeless.recorder import Recorder
from my_typeless.stt_client import STTClient
from my_typeless.text_injector import inject_text

logger = logging.getLogger(__name__)

# 队列哨兵值，表示录音结束、不再有新片段
_SENTINEL = object()

# Whisper prompt 上限约 224 tokens；对中文约 400 字符，取尾部以保留最近上下文
_MAX_PROMPT_CHARS = 400


def _update_transcription_tail(current_tail: str, new_text: str, max_chars: int) -> str:
    """维护 STT 上下文尾部，始终只保留最近 max_chars 个字符。"""
    if max_chars <= 0:
        return ""
    merged = f"{current_tail}{new_text}"
    return merged[-max_chars:]


def _build_stt_prompt(tail: str, base_stt_prompt: str) -> str:
    """根据已累积尾部和术语表组装 Whisper prompt。"""
    if base_stt_prompt:
        return f"{tail} {base_stt_prompt}" if tail else base_stt_prompt
    return tail


def _map_processing_error(e: Exception, openai_module: Any | None = None) -> tuple[str, bool]:
    """将异常映射为 (用户可读消息, 是否严重)。"""
    openai = openai_module
    if openai is None:
        try:
            import openai as _openai
        except Exception:
            _openai = None
        openai = _openai

    if openai is not None:
        auth_error = getattr(openai, "AuthenticationError", None)
        conn_error = getattr(openai, "APIConnectionError", None)
        not_found_error = getattr(openai, "NotFoundError", None)
        bad_req_error = getattr(openai, "BadRequestError", None)
        timeout_error = getattr(openai, "APITimeoutError", None)
        rate_limit_error = getattr(openai, "RateLimitError", None)
        status_error = getattr(openai, "APIStatusError", None)

        if auth_error and isinstance(e, auth_error):
            return ("API 密钥无效或已过期，请在设置中检查 API Key 是否正确。", True)
        if conn_error and isinstance(e, conn_error):
            return ("无法连接到 API 服务器，请检查网络连接和 API 地址是否正确。", True)
        if not_found_error and isinstance(e, not_found_error):
            return ("API 模型或接口未找到，请检查模型名称和 API 地址是否正确。", True)
        if bad_req_error and isinstance(e, bad_req_error):
            return (f"API 请求参数错误：{e}", True)
        if timeout_error and isinstance(e, timeout_error):
            return ("API 请求超时，请检查网络连接或稍后重试。", False)
        if rate_limit_error and isinstance(e, rate_limit_error):
            return ("API 请求过于频繁，请稍后再试或检查额度是否充足。", False)
        if status_error and isinstance(e, status_error):
            status_code = e.__dict__.get("status_code")
            status = f"HTTP {status_code}" if status_code is not None else "HTTP 状态未知"
            return (f"API 服务异常 ({status})，请稍后重试。", False)

    return (f"发生未知错误：{e}", False)


class Worker:
    """
    后台工作控制器，负责处理完整的语音→文本流水线

    录音过程中检测停顿，将已有的音频片段立即提交转录，
    从而在用户松开按键时大部分音频已完成转录，显著降低延迟。

    Events:
        state_changed(str): 状态变化 ("idle" / "recording" / "processing")
        result_ready(str): 精修文本就绪
        error_occurred(str, bool): 发生错误 (消息, 是否严重)
    """

    _TIME_FMT = "%H:%M:%S.%f"

    def __init__(
        self,
        config: AppConfig,
        recorder: Recorder | None = None,
        stt_client_factory: Callable[..., Any] = STTClient,
        llm_client_factory: Callable[..., Any] = LLMClient,
        text_injector: Callable[[str], None] = inject_text,
        history_adder: Callable[..., None] = add_history,
    ):
        self.events = EventEmitter()
        self._config = config
        self._recorder = recorder or Recorder()
        self._stt_client_factory = stt_client_factory
        self._llm_client_factory = llm_client_factory
        self._text_injector = text_injector
        self._history_adder = history_adder
        self._key_press_at: str = ""
        self._segment_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动增量转录消费线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.events.emit("state_changed", "recording")

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
        self.events.emit("state_changed", "processing")

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
            stt = self._stt_client_factory(self._config.stt)
            llm = self._llm_client_factory(self._config.llm)
            base_stt_prompt = self._config.build_stt_prompt()
            llm_system_prompt = self._config.build_llm_system_prompt()

            transcription_parts: list[str] = []
            transcription_tail = ""
            accumulated_refined = ""
            tail_budget = (
                _MAX_PROMPT_CHARS - len(base_stt_prompt) - 1
                if base_stt_prompt
                else _MAX_PROMPT_CHARS
            )

            # 持续从队列中取出音频片段，逐段完成 STT + LLM
            while True:
                try:
                    item = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple):
                    # 队列中元组只会是 (_SENTINEL, key_release_at) 哨兵值
                    key_release_at = item[1]
                    break

                # STT prompt: 累积转录尾部 + 术语表（Whisper 从前截断，术语放尾部确保保留）
                stt_prompt = _build_stt_prompt(transcription_tail, base_stt_prompt)

                logger.debug("Transcribing segment (%d bytes)...", len(item))
                text = stt.transcribe(item, prompt=stt_prompt)
                logger.debug("Segment STT result: %r", text)

                if not text or not text.strip():
                    continue

                transcription_parts.append(text)
                transcription_tail = _update_transcription_tail(
                    transcription_tail, text, tail_budget
                )

                # LLM 精修：将已精修的前文作为上下文
                logger.debug("Refining segment...")
                refined = llm.refine(
                    text,
                    system_prompt=llm_system_prompt,
                    context=accumulated_refined,
                )
                logger.debug("Segment LLM result: %r", refined)
                accumulated_refined += refined

            done_at = datetime.now().strftime(self._TIME_FMT)

            # 拼接全部结果
            raw_text = "".join(transcription_parts)
            refined_text = accumulated_refined
            logger.debug("Full STT result: %r", raw_text)
            logger.debug("Full LLM result: %r", refined_text)

            if not raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.events.emit("state_changed", "idle")
                return

            # 注入文本
            logger.debug("Injecting text...")
            self._text_injector(refined_text)
            logger.debug("Text injected successfully")

            # 记录历史（增量模式下 STT 和 LLM 交替进行，完成时间相同）
            self._history_adder(
                raw_text,
                refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.events.emit("result_ready", refined_text)

        except Exception as e:
            logger.error("Processing error: %s", e, exc_info=True)
            message, is_fatal = _map_processing_error(e)
            self.events.emit("error_occurred", message, is_fatal)

        finally:
            self.events.emit("state_changed", "idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
