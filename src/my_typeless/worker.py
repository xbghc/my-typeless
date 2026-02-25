"""后台处理 - 录音 → 增量 STT → LLM → 文本注入"""

import logging
import queue
import threading
from datetime import datetime

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

    采用双线程流水线设计：
    1. _process_audio: 消费音频片段 → STT 转录 → 放入文本队列
    2. _process_text: 消费 STT 文本 → LLM 精修 → 最终注入

    这种并行处理显著降低了长语音输入的总延迟。

    Events:
        state_changed(str): 状态变化 ("idle" / "recording" / "processing")
        result_ready(str): 精修文本就绪
        error_occurred(str, bool): 发生错误 (消息, 是否严重)
    """

    _TIME_FMT = "%H:%M:%S.%f"

    def __init__(self, config: AppConfig):
        self.events = EventEmitter()
        self._config = config
        self._recorder = Recorder()
        self._key_press_at: str = ""
        self._segment_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动流水线线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.events.emit("state_changed", "recording")

        # 初始化新队列
        self._segment_queue = queue.Queue()
        self._text_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动音频处理线程 (STT)
        t_audio = threading.Thread(
            target=self._process_audio,
            args=(self._segment_queue, self._text_queue),
            daemon=True,
        )
        t_audio.start()

        # 启动文本处理线程 (LLM)
        t_text = threading.Thread(
            target=self._process_text,
            args=(self._key_press_at, self._text_queue),
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

        # 发送哨兵值（附带按键释放时间）给音频线程
        # 音频线程处理完所有音频后，会将此哨兵传递给文本线程
        self._segment_queue.put((_SENTINEL, key_release_at))
        self.events.emit("state_changed", "processing")

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    # ------------------------------------------------------------------
    # 流水线线程
    # ------------------------------------------------------------------

    def _process_audio(self, segment_queue: queue.Queue, text_queue: queue.Queue) -> None:
        """线程 1：消费音频 → STT → 生产文本"""
        transcription_parts: list[str] = []

        try:
            stt = STTClient(self._config.stt)
            base_stt_prompt = self._config.build_stt_prompt()

            while True:
                try:
                    item = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 检查哨兵
                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    # 将哨兵透传给文本线程
                    text_queue.put(item)
                    break

                # STT Prompt 构建
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
            # 发生错误也需要通知下游结束，避免下游无限等待
            # 使用当前时间作为 release_time 的降级方案
            fallback_release = datetime.now().strftime(self._TIME_FMT)
            text_queue.put((_SENTINEL, fallback_release))

    def _process_text(self, key_press_at: str, text_queue: queue.Queue) -> None:
        """线程 2：消费文本 → LLM → 注入 & 历史"""
        transcription_parts: list[str] = [] # 用于最终记录历史
        refined_parts: list[str] = []
        key_release_at = None

        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            while True:
                try:
                    item = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 检查哨兵
                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # 收到的是 STT 文本片段
                raw_segment = item
                transcription_parts.append(raw_segment)

                # LLM 精修
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    raw_segment,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            # --- 循环结束，进行最终汇总 ---

            done_at = datetime.now().strftime(self._TIME_FMT)
            raw_text = "".join(transcription_parts)
            refined_text = "".join(refined_parts)

            logger.debug("Full STT result: %r", raw_text)
            logger.debug("Full LLM result: %r", refined_text)

            if not raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.events.emit("state_changed", "idle")
                return

            # 注入文本
            logger.debug("Injecting text...")
            inject_text(refined_text)
            logger.debug("Text injected successfully")

            # 记录历史
            add_history(
                raw_text, refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at or done_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.events.emit("result_ready", refined_text)

        except Exception as e:
            self._handle_error(e)

        finally:
            # 只有文本线程结束，整个流程才算真正回到 idle
            self.events.emit("state_changed", "idle")

    def _handle_error(self, e: Exception) -> None:
        """统一错误处理"""
        logger.error("Processing error: %s", e, exc_info=True)
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

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
