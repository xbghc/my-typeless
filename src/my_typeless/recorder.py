"""麦克风录音模块 - 使用 pyaudio 录制音频，支持停顿检测与分段回调"""

import io
import math
import struct
import wave
import threading
from typing import Callable

import pyaudio


# Whisper 推荐参数
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16

# 停顿检测参数
SILENCE_THRESHOLD = 500   # RMS 阈值，低于此值视为静音
SILENCE_DURATION = 0.6    # 静音持续秒数，超过则认为是停顿
MIN_SPEECH_DURATION = 0.5  # 最短语音片段时长（秒），过短的片段不发送


class Recorder:
    """麦克风录音器，在独立线程中运行，支持停顿检测与分段回调"""

    def __init__(self):
        self._audio = pyaudio.PyAudio()
        self._stream: pyaudio.Stream | None = None
        self._frames: list[bytes] = []
        self._recording = False
        self._thread: threading.Thread | None = None

        # 增量转录相关
        self._on_segment: Callable[[bytes], None] | None = None
        self._segment_frames: list[bytes] = []
        self._in_speech = False
        self._silence_chunks = 0

    def start(self, on_segment: Callable[[bytes], None] | None = None) -> None:
        """开始录音（在新线程中运行）

        Args:
            on_segment: 可选回调，检测到停顿时以 WAV 字节数据调用。
                        传入 None 则退化为原始行为（stop 时返回全部音频）。
        """
        if self._recording:
            return
        self._frames = []
        self._segment_frames = []
        self._in_speech = False
        self._silence_chunks = 0
        self._on_segment = on_segment
        self._recording = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self) -> bytes:
        """停止录音并返回 WAV 格式的音频数据

        增量模式（on_segment 不为 None）下只返回尚未通过回调发出的剩余音频。
        原始模式下返回全部录音。
        """
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._on_segment is not None:
            # 增量模式：返回剩余未发送的音频
            remaining = self._segment_frames
            self._segment_frames = []
            if not remaining:
                return b""
            return self._build_wav(remaining)
        else:
            # 原始模式：返回全部音频
            if not self._frames:
                return b""
            return self._build_wav(self._frames)

    def _record_loop(self) -> None:
        """录音主循环，包含可选的停顿检测逻辑"""
        silence_chunks_needed = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)
        min_speech_chunks = int(MIN_SPEECH_DURATION * SAMPLE_RATE / CHUNK_SIZE)

        try:
            self._stream = self._audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
            while self._recording:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if self._on_segment is None:
                    # 仅在非增量模式下保存完整录音，避免增量模式下的内存泄漏
                    self._frames.append(data)
                    continue

                # --- 增量模式：停顿检测 ---
                self._segment_frames.append(data)
                rms = self._calculate_rms(data)

                if rms >= SILENCE_THRESHOLD:
                    # 语音活动
                    self._in_speech = True
                    self._silence_chunks = 0
                else:
                    # 静音
                    self._silence_chunks += 1

                    if (
                        self._in_speech
                        and self._silence_chunks >= silence_chunks_needed
                    ):
                        # 检测到停顿，发送语音片段
                        speech_end = len(self._segment_frames) - self._silence_chunks
                        if speech_end >= min_speech_chunks:
                            segment_wav = self._build_wav(
                                self._segment_frames[:speech_end]
                            )
                            self._on_segment(segment_wav)
                        # 保留尾部静音帧作为下一段的起始缓冲
                        self._segment_frames = list(
                            self._segment_frames[-self._silence_chunks :]
                        )
                        self._in_speech = False
                        self._silence_chunks = 0
        except Exception:
            pass
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

    @staticmethod
    def _calculate_rms(data: bytes) -> float:
        """计算一帧音频数据的 RMS（均方根）能量值"""
        count = len(data) // SAMPLE_WIDTH
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", data)
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / count)

    @staticmethod
    def _build_wav(frames: list[bytes]) -> bytes:
        """将录音帧列表转为 WAV 字节数据"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()

    def cleanup(self) -> None:
        """释放 pyaudio 资源"""
        self._audio.terminate()
