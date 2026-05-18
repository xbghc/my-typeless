"""Silero VAD - 神经网络语音活动检测，替代纯 RMS 静音检测。

为什么用 Silero：
- RMS 阈值在中文气口、低音量、含背景噪声场景下表现差（要么误切、要么把噪声当语音）。
- Silero VAD 是 16 kHz 上 32 ms 一帧的小神经网络（~2 MB onnx），CPU 推理 <5 ms/帧。
- Handy（github.com/cjpais/Handy）等同类产品已采用相同方案。

接口：流式逐帧调用 `SileroVAD(pcm_bytes_of_512_samples) -> speech_prob ∈ [0, 1]`。
"""

import logging
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

# Silero VAD v5 在 16 kHz 下每次推理必须接受正好 512 个 sample（≈32 ms）。
VAD_CHUNK_SAMPLES = 512
VAD_SAMPLE_RATE = 16000

# Silero 推荐的语音/静音判定阈值（开源仓 README 默认值）。
SPEECH_THRESHOLD = 0.5


def _resolve_model_path() -> Path:
    """定位 silero_vad.onnx，兼容源码运行与 PyInstaller --onefile 打包。"""
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / "silero_vad.onnx"]

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle = Path(sys.__dict__["_MEIPASS"])
        candidates.insert(0, bundle / "my_typeless" / "silero_vad.onnx")
        candidates.append(bundle / "silero_vad.onnx")

    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        "silero_vad.onnx not found; tried: " + ", ".join(str(p) for p in candidates)
    )


class SileroVAD:
    """流式 Silero VAD。每次调用喂入正好 VAD_CHUNK_SAMPLES (512) 个 16-bit PCM samples。"""

    def __init__(self, model_path: Path | None = None):
        path = model_path or _resolve_model_path()
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3  # 静默 ORT 自身日志
        self._session = ort.InferenceSession(
            str(path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._sr = np.array(VAD_SAMPLE_RATE, dtype=np.int64)
        self.reset()

    def reset(self) -> None:
        """重置 LSTM hidden state。新的录音段开始时调用。"""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def __call__(self, pcm_bytes: bytes) -> float:
        """返回该帧（512 samples / 16-bit PCM）的语音概率 ∈ [0, 1]。"""
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.shape[0] != VAD_CHUNK_SAMPLES:
            raise ValueError(
                f"SileroVAD expects {VAD_CHUNK_SAMPLES} samples per call, got {samples.shape[0]}"
            )
        inputs = {
            "input": samples.reshape(1, -1),
            "state": self._state,
            "sr": self._sr,
        }
        out, new_state = self._session.run(None, inputs)
        self._state = new_state
        # onnxruntime 返回类型联合体含 SparseTensor；运行时这里一定是 dense ndarray
        prob = np.asarray(out).flatten()[0]
        return float(prob)
