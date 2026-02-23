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

    录音过程中检测停顿，将已有的音频片段立即提交转录，
    从而在用户松开按键时大部分音频已完成转录，显著降低延迟。

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
        self._audio_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config
        # 配置更新时清空客户端缓存，以便下次重建时应用新配置
        # 注意：STTClient 和 LLMClient 是在处理线程中临时创建的，
        # 所以这里不需要额外操作，只需确保 _config 更新即可。

    def start_recording(self) -> None:
        """开始录音，同时启动增量处理流水线"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.events.emit("state_changed", "recording")

        # 初始化队列
        self._audio_queue = queue.Queue()
        self._text_queue = queue.Queue()

        self._recorder.start(on_segment=self._on_segment)

        # 启动 STT 线程 (Audio -> Text)
        t_audio = threading.Thread(
            target=self._process_audio,
            args=(self._key_press_at, self._audio_queue, self._text_queue),
            daemon=True,
        )
        t_audio.start()

        # 启动 LLM 线程 (Text -> Final)
        t_text = threading.Thread(
            target=self._process_text,
            args=(self._key_press_at, self._text_queue),
            daemon=True,
        )
        t_text.start()

    def stop_recording_and_process(self) -> None:
        """停止录音，将剩余音频送入队列并通知流水线结束"""
        logger.debug("stop_recording_and_process called")
        remaining = self._recorder.stop()
        key_release_at = datetime.now().strftime(self._TIME_FMT)

        if remaining:
            logger.debug("Remaining audio: %d bytes", len(remaining))
            self._audio_queue.put(remaining)

        # 发送哨兵值给第一个队列
        self._audio_queue.put((_SENTINEL, key_release_at))
        self.events.emit("state_changed", "processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._audio_queue.put(wav_data)

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
            self.events.emit("error_occurred", f"API 请求参数错误：{e.message}", True)
        elif isinstance(e, openai.APITimeoutError):
            self.events.emit("error_occurred", "API 请求超时，请检查网络连接或稍后重试。", False)
        elif isinstance(e, openai.RateLimitError):
            self.events.emit("error_occurred", "API 请求过于频繁，请稍后再试或检查额度是否充足。", False)
        elif isinstance(e, openai.APIStatusError):
            self.events.emit("error_occurred", f"API 服务异常 (HTTP {e.status_code})，请稍后重试。", False)
        else:
            self.events.emit("error_occurred", f"发生未知错误：{e}", False)

    def _process_audio(self, key_press_at: str, audio_queue: queue.Queue, text_queue: queue.Queue) -> None:
        """STT 线程：消费音频 -> STT -> 生产文本"""
        try:
            stt = STTClient(self._config.stt)
            base_stt_prompt = self._config.build_stt_prompt()
            transcription_parts: list[str] = []
            key_release_at = None

            while True:
                try:
                    item = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
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

                if text and text.strip():
                    transcription_parts.append(text)
                    text_queue.put(text)

        except Exception as e:
            self._handle_error(e)
        finally:
            # 无论成功还是异常，都要向下一级传递结束信号，避免下游死锁
            # 如果异常导致 key_release_at 未知，则使用当前时间
            final_release_at = key_release_at or datetime.now().strftime(self._TIME_FMT)
            text_queue.put((_SENTINEL, final_release_at))

    def _process_text(self, key_press_at: str, text_queue: queue.Queue) -> None:
        """LLM 线程：消费文本 -> LLM -> 最终结果"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()

            raw_parts: list[str] = []
            refined_parts: list[str] = []
            key_release_at = None

            while True:
                try:
                    item = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at = item[1]
                    break

                # 处理文本片段
                raw_text_segment = item
                raw_parts.append(raw_text_segment)

                # LLM 精修：将已精修的前文作为上下文
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    raw_text_segment,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            # 全部处理完成
            done_at = datetime.now().strftime(self._TIME_FMT)
            full_raw = "".join(raw_parts)
            full_refined = "".join(refined_parts)

            logger.debug("Full STT result: %r", full_raw)
            logger.debug("Full LLM result: %r", full_refined)

            if not full_raw.strip():
                logger.debug("Empty STT result, skipping")
                return # finally 块会负责 emit idle

            # 注入文本
            logger.debug("Injecting text...")
            inject_text(full_refined)
            logger.debug("Text injected successfully")

            # 记录历史
            add_history(
                full_raw, full_refined,
                key_press_at=key_press_at,
                key_release_at=key_release_at or done_at,
                stt_done_at=done_at,
                llm_done_at=done_at,
            )

            self.events.emit("result_ready", full_refined)

        except Exception as e:
            self._handle_error(e)
        finally:
            self.events.emit("state_changed", "idle")

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
