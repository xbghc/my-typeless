"""麦克风录音模块 - 使用 pyaudio 录制音频"""

import io
import wave
import threading
import pyaudio


# Whisper 推荐参数
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16


class Recorder:
    """麦克风录音器，在独立线程中运行"""

    def __init__(self):
        self._audio = pyaudio.PyAudio()
        self._stream: pyaudio.Stream | None = None
        self._frames: list[bytes] = []
        self._recording = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """开始录音（在新线程中运行）"""
        if self._recording:
            return
        self._frames = []
        self._recording = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self) -> bytes:
        """停止录音并返回 WAV 格式的音频数据"""
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if not self._frames:
            return b""

        return self._frames_to_wav()

    def _record_loop(self) -> None:
        """录音主循环"""
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
                self._frames.append(data)
        except Exception:
            pass
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

    def _frames_to_wav(self) -> bytes:
        """将录音帧转为 WAV 字节数据"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(self._frames))
        return buf.getvalue()

    def cleanup(self) -> None:
        """释放 pyaudio 资源"""
        self._audio.terminate()
