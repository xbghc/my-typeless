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
        self._segment_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()

    def update_config(self, config: AppConfig) -> None:
        """更新配置（在非录音状态下调用）"""
        self._config = config

    def start_recording(self) -> None:
        """开始录音，同时启动增量转录消费线程"""
        logger.debug("start_recording called")
        self._key_press_at = datetime.now().strftime(self._TIME_FMT)
        self.events.emit("state_changed", "recording")

        self._segment_queue = queue.Queue()
        self._text_queue = queue.Queue()
        self._recorder.start(on_segment=self._on_segment)

        # 启动音频处理线程（STT）
        t1 = threading.Thread(
            target=self._process_audio,
            args=(self._key_press_at, self._segment_queue, self._text_queue),
            daemon=True,
        )
        t1.start()

        # 启动文本处理线程（LLM）
        t2 = threading.Thread(
            target=self._process_text,
            args=(self._key_press_at, self._text_queue),
            daemon=True,
        )
        t2.start()

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
        self.events.emit("state_changed","processing")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _on_segment(self, wav_data: bytes) -> None:
        """Recorder 停顿检测回调 - 由录音线程调用"""
        logger.debug("Segment detected: %d bytes", len(wav_data))
        self._segment_queue.put(wav_data)

    def _process_audio(
        self, key_press_at: str, segment_queue: queue.Queue, text_queue: queue.Queue
    ) -> None:
        """音频处理线程（STT）：消费音频片段 → STT → 生产原始文本"""
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
                    break

                # STT prompt: 累积转录尾部 + 术语表
                if transcription_parts:
                    accumulated = "".join(transcription_parts)
                    if base_stt_prompt:
                        tail_budget = _MAX_PROMPT_CHARS - len(base_stt_prompt) - 1
                        tail = accumulated[-tail_budget:] if tail_budget > 0 else ""
                        stt_prompt = (
                            f"{tail} {base_stt_prompt}" if tail else base_stt_prompt
                        )
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
                text_queue.put(text)

            stt_done_at = datetime.now().strftime(self._TIME_FMT)
            raw_text = "".join(transcription_parts)
            # 发送哨兵：包含完整 raw_text 供最终历史记录使用
            text_queue.put((_SENTINEL, key_release_at, raw_text, stt_done_at))

        except Exception as e:
            self._handle_error(e)
            # 发生错误时发送特定哨兵让 LLM 线程退出，避免死锁
            # 使用 None 作为 key_release_at 标记异常退出
            try:
                text_queue.put((_SENTINEL, None, "", ""))
            except:
                pass

    def _process_text(self, key_press_at: str, text_queue: queue.Queue) -> None:
        """文本处理线程（LLM）：消费原始文本 → LLM 精修 → 注入文本"""
        try:
            llm = LLMClient(self._config.llm)
            llm_system_prompt = self._config.build_llm_system_prompt()
            refined_parts: list[str] = []

            while True:
                try:
                    item = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if isinstance(item, tuple) and item[0] is _SENTINEL:
                    key_release_at, full_raw_text, stt_done_at = (
                        item[1],
                        item[2],
                        item[3],
                    )
                    # 如果 key_release_at 为 None，说明上游出错，直接退出
                    if key_release_at is None:
                        return
                    break

                # item 是 raw_text 片段
                raw_text_segment = item
                llm_context = "".join(refined_parts)
                logger.debug("Refining segment...")
                refined = llm.refine(
                    raw_text_segment,
                    system_prompt=llm_system_prompt,
                    context=llm_context,
                )
                logger.debug("Segment LLM result: %r", refined)
                refined_parts.append(refined)

            llm_done_at = datetime.now().strftime(self._TIME_FMT)
            refined_text = "".join(refined_parts)

            logger.debug("Full STT result: %r", full_raw_text)
            logger.debug("Full LLM result: %r", refined_text)

            if not full_raw_text.strip():
                logger.debug("Empty STT result, skipping")
                self.events.emit("state_changed", "idle")
                return

            # 注入文本
            logger.debug("Injecting text...")
            inject_text(refined_text)
            logger.debug("Text injected successfully")

            # 记录历史
            add_history(
                full_raw_text,
                refined_text,
                key_press_at=key_press_at,
                key_release_at=key_release_at,
                stt_done_at=stt_done_at,
                llm_done_at=llm_done_at,
            )

            self.events.emit("result_ready", refined_text)

        except Exception as e:
            self._handle_error(e)

        finally:
            self.events.emit("state_changed", "idle")

    def _handle_error(self, e: Exception) -> None:
        """统一错误处理"""
        logger.error("Processing error: %s", e, exc_info=True)
        import openai

        if isinstance(e, openai.AuthenticationError):
            self.events.emit(
                "error_occurred",
                "API 密钥无效或已过期，请在设置中检查 API Key 是否正确。",
                True,
            )
        elif isinstance(e, openai.APIConnectionError):
            self.events.emit(
                "error_occurred",
                "无法连接到 API 服务器，请检查网络连接和 API 地址是否正确。",
                True,
            )
        elif isinstance(e, openai.NotFoundError):
            self.events.emit(
                "error_occurred",
                "API 模型或接口未找到，请检查模型名称和 API 地址是否正确。",
                True,
            )
        elif isinstance(e, openai.BadRequestError):
            try:
                msg = e.message
            except AttributeError:
                msg = str(e)
            self.events.emit("error_occurred", f"API 请求参数错误：{msg}", True)
        elif isinstance(e, openai.APITimeoutError):
            self.events.emit(
                "error_occurred", "API 请求超时，请检查网络连接或稍后重试。", False
            )
        elif isinstance(e, openai.RateLimitError):
            self.events.emit(
                "error_occurred",
                "API 请求过于频繁，请稍后再试或检查额度是否充足。",
                False,
            )
        elif isinstance(e, openai.APIStatusError):
            self.events.emit(
                "error_occurred",
                f"API 服务异常 (HTTP {e.status_code})，请稍后重试。",
                False,
            )
        else:
            self.events.emit("error_occurred", f"发生未知错误：{e}", False)

    def cleanup(self) -> None:
        """清理资源"""
        self._recorder.cleanup()
