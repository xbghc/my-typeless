"""测试 Silero VAD 包装：模型能加载、概率在 [0,1]、错误长度报错、reset 工作。

这些测试实际加载 onnx 模型——需要 src/my_typeless/silero_vad.onnx 存在。
"""

import struct

import numpy as np
import pytest

from my_typeless.vad import SPEECH_THRESHOLD, VAD_CHUNK_SAMPLES, SileroVAD


@pytest.fixture(scope="module")
def vad() -> SileroVAD:
    """整个 module 共用一个 VAD 实例（避免反复加载 onnx 模型）。"""
    return SileroVAD()


def _silence_frame() -> bytes:
    """生成 VAD_CHUNK_SAMPLES 个 16-bit 0 sample（完全静音）。"""
    return struct.pack(f"<{VAD_CHUNK_SAMPLES}h", *([0] * VAD_CHUNK_SAMPLES))


def _noise_frame(seed: int = 0) -> bytes:
    """生成 VAD_CHUNK_SAMPLES 个 ±16000 范围的随机 sample（白噪声）。"""
    rng = np.random.default_rng(seed)
    samples = rng.integers(-16000, 16000, size=VAD_CHUNK_SAMPLES, dtype=np.int16)
    return samples.tobytes()


def test_silence_returns_low_speech_probability(vad: SileroVAD):
    """连续静音帧的语音概率应远低于 SPEECH_THRESHOLD。"""
    vad.reset()
    # 喂多帧让 LSTM state 收敛
    probs = [vad(_silence_frame()) for _ in range(20)]
    # 至少最后几帧（state 已稳定）应明显低于阈值
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert min(probs[-5:]) < SPEECH_THRESHOLD


def test_probability_is_in_valid_range(vad: SileroVAD):
    vad.reset()
    for seed in range(5):
        p = vad(_noise_frame(seed))
        assert 0.0 <= p <= 1.0


def test_wrong_chunk_size_raises(vad: SileroVAD):
    """喂入长度不是 VAD_CHUNK_SAMPLES 的数据应抛 ValueError。"""
    too_short = struct.pack("<256h", *([0] * 256))
    with pytest.raises(ValueError):
        vad(too_short)

    too_long = struct.pack("<1024h", *([0] * 1024))
    with pytest.raises(ValueError):
        vad(too_long)


def test_reset_restores_initial_state(vad: SileroVAD):
    """reset 后第一帧静音的概率应与全新实例的第一帧静音概率一致。"""
    vad.reset()
    first_prob = vad(_silence_frame())

    # 跑几帧让 state 变化
    for _ in range(10):
        vad(_noise_frame())

    # reset 后再跑同样输入应得到同样结果
    vad.reset()
    after_reset_prob = vad(_silence_frame())
    assert abs(first_prob - after_reset_prob) < 1e-5


def test_model_file_resolution_finds_packaged_model():
    """默认构造（不传 model_path）应能从 my_typeless 包目录定位模型文件。"""
    vad_instance = SileroVAD()
    # 能成功构造即说明模型加载成功
    p = vad_instance(_silence_frame())
    assert 0.0 <= p <= 1.0
