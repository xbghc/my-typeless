"""测试录音模块的纯函数。

VAD 已切到 Silero（见 test_vad.py），这里只保留 WAV 封装这一纯静态逻辑。
"""

import io
import struct
import wave

from my_typeless.recorder import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH, Recorder


def _pack_samples(samples: list[int]) -> bytes:
    """把 16-bit 整数样本打包成 little-endian PCM 字节。"""
    return struct.pack(f"<{len(samples)}h", *samples)


def test_build_wav_produces_valid_wave():
    frames = [_pack_samples([0, 100, 200, 300, 400] * 100) for _ in range(3)]
    wav_bytes = Recorder._build_wav(frames)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == CHANNELS
        assert wf.getsampwidth() == SAMPLE_WIDTH
        assert wf.getframerate() == SAMPLE_RATE

        expected_total_bytes = sum(len(f) for f in frames)
        expected_frames = expected_total_bytes // SAMPLE_WIDTH
        assert wf.getnframes() == expected_frames

        # 数据完整性
        data = wf.readframes(expected_frames)
        assert data == b"".join(frames)


def test_build_wav_empty_frames_creates_zero_length_audio():
    wav_bytes = Recorder._build_wav([])
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnframes() == 0
        assert wf.getnchannels() == CHANNELS
