import importlib
import sys
import types
from queue import Queue

import pytest

from my_typeless.config import AppConfig


@pytest.fixture
def worker_module(monkeypatch: pytest.MonkeyPatch):
    """在隔离的依赖 stub 环境中导入 worker 模块，避免污染全局 sys.modules。"""
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=object))
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
    monkeypatch.setitem(sys.modules, "pyaudio", types.SimpleNamespace(PyAudio=object, paInt16=8))
    monkeypatch.setitem(sys.modules, "keyboard", types.SimpleNamespace(send=lambda *_a, **_k: None))
    monkeypatch.setitem(
        sys.modules,
        "win32clipboard",
        types.SimpleNamespace(
            OpenClipboard=lambda: None,
            IsClipboardFormatAvailable=lambda _fmt: False,
            GetClipboardData=lambda _fmt: "",
            CloseClipboard=lambda: None,
            EmptyClipboard=lambda: None,
            SetClipboardText=lambda _text, _fmt: None,
        ),
    )
    monkeypatch.setitem(sys.modules, "win32con", types.SimpleNamespace(CF_UNICODETEXT=13))

    module = importlib.import_module("my_typeless.worker")
    return importlib.reload(module)


def test_update_transcription_tail_keeps_only_recent_chars(worker_module):
    tail = ""
    tail = worker_module._update_transcription_tail(tail, "hello", 4)
    tail = worker_module._update_transcription_tail(tail, "world", 4)
    assert tail == "orld"


def test_build_stt_prompt_appends_glossary_after_tail(worker_module):
    prompt = worker_module._build_stt_prompt(tail="最近上下文", base_stt_prompt="术语A、术语B")
    assert prompt == "最近上下文 术语A、术语B"


def test_build_stt_prompt_without_glossary_uses_tail_only(worker_module):
    prompt = worker_module._build_stt_prompt(tail="only tail", base_stt_prompt="")
    assert prompt == "only tail"


def test_map_processing_error_handles_missing_openai_error_types(worker_module):
    message, is_fatal = worker_module._map_processing_error(
        RuntimeError("boom"), openai_module=types.SimpleNamespace()
    )
    assert message == "发生未知错误：boom"
    assert is_fatal is False


class _FakeRecorder:
    def start(self, on_segment=None):
        return None

    def stop(self):
        return b""

    def cleanup(self):
        return None


def _make_segment_queue(worker_module, segments: list[bytes], release_at: str = "10:00:00.000000"):
    q = Queue()
    for seg in segments:
        q.put(seg)
    q.put((worker_module._SENTINEL, release_at))
    return q


def test_incremental_process_with_injected_dependencies(worker_module):
    stt_prompts: list[str] = []
    inject_calls: list[str] = []
    history_calls: list[tuple[tuple, dict]] = []

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            stt_prompts.append(prompt)
            return "测试文本"

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            return f"[{text}]"

    cfg = AppConfig()
    cfg.glossary = ["MyTypeless"]

    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=inject_calls.append,
        history_adder=lambda *args, **kwargs: history_calls.append((args, kwargs)),
        candidates_recorder=lambda *a, **kw: None,
    )

    q = _make_segment_queue(worker_module, [b"segment-1"])
    w._incremental_process("09:00:00.000000", q)

    assert stt_prompts and "MyTypeless" in stt_prompts[0]
    assert inject_calls == ["[测试文本]"]
    assert history_calls
    assert history_calls[0][0][0] == "测试文本"
    assert history_calls[0][0][1] == "[测试文本]"


def test_llm_called_once_with_full_concatenated_text(worker_module):
    """核心回归：LLM 必须只在录音结束后被调用 1 次，且参数是拼接后的全文。

    早期实现是每段调一次 LLM，导致最终输出不通顺（双"比如"、段尾连接词丢失等）。
    改为整段精修后这条性质必须保持。
    """
    refine_calls: list[tuple[str, dict]] = []
    inject_calls: list[str] = []
    history_calls: list[tuple[tuple, dict]] = []

    stt_iter = iter(["第一段。", "第二段。", "第三段。"])

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            return next(stt_iter)

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            refine_calls.append((text, {"system_prompt": system_prompt, "context": context}))
            return "整段精修后的文本。"

    cfg = AppConfig()
    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=inject_calls.append,
        history_adder=lambda *a, **kw: history_calls.append((a, kw)),
        candidates_recorder=lambda *a, **kw: None,
    )

    q = _make_segment_queue(worker_module, [b"a1", b"a2", b"a3"])
    w._incremental_process("09:00:00.000000", q)

    # LLM 只调一次，且参数是拼接全文（不传 context，因为整段已经是全文）
    assert len(refine_calls) == 1
    assert refine_calls[0][0] == "第一段。第二段。第三段。"
    assert refine_calls[0][1]["context"] == ""

    # inject_text 一次拿到 LLM 输出
    assert inject_calls == ["整段精修后的文本。"]

    # 历史：raw = 拼接全文，refined = LLM 输出；stt_done/llm_done 都有
    assert len(history_calls) == 1
    args, kwargs = history_calls[0]
    assert args[0] == "第一段。第二段。第三段。"
    assert args[1] == "整段精修后的文本。"
    assert kwargs["stt_done_at"]
    assert kwargs["llm_done_at"]


def test_empty_segments_are_skipped(worker_module):
    """STT 返回空串或空白串的段应被忽略，不进入 raw_text。"""
    inject_calls: list[str] = []
    stt_iter = iter(["有效内容", "", "   ", "更多内容"])

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            return next(stt_iter)

    refine_args: list[str] = []

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            refine_args.append(text)
            return "精修结果"

    cfg = AppConfig()
    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=inject_calls.append,
        history_adder=lambda *a, **kw: None,
        candidates_recorder=lambda *a, **kw: None,
    )

    q = _make_segment_queue(worker_module, [b"a", b"b", b"c", b"d"])
    w._incremental_process("t0", q)

    assert refine_args == ["有效内容更多内容"]
    assert inject_calls == ["精修结果"]


def test_all_empty_stt_skips_llm_inject_and_history(worker_module):
    """所有段都空时应跳过 LLM、不注入、不写历史。"""
    inject_calls: list[str] = []
    history_calls: list = []
    refine_calls: list = []

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            return ""

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            refine_calls.append(text)
            return "should not be called"

    cfg = AppConfig()
    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=inject_calls.append,
        history_adder=lambda *a, **kw: history_calls.append((a, kw)),
        candidates_recorder=lambda *a, **kw: None,
    )

    q = _make_segment_queue(worker_module, [b"a", b"b"])
    w._incremental_process("t0", q)

    assert refine_calls == []
    assert inject_calls == []
    assert history_calls == []


def test_stt_traditional_chinese_is_converted_to_simplified(worker_module):
    """Whisper 输出繁体时，worker 应用 zhconv 转简体再交给 LLM。"""
    stt_iter = iter(["組件之間的衝突。", "解決方案。"])

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            return next(stt_iter)

    refine_args: list[str] = []

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            refine_args.append(text)
            return "out"

    cfg = AppConfig()
    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=lambda _t: None,
        history_adder=lambda *a, **kw: None,
        candidates_recorder=lambda *a, **kw: None,
    )

    q = _make_segment_queue(worker_module, [b"s1", b"s2"])
    w._incremental_process("t0", q)

    assert len(refine_args) == 1
    raw = refine_args[0]
    assert "组件" in raw and "之间" in raw and "冲突" in raw and "解决方案" in raw
    assert "組件" not in raw and "衝突" not in raw


def test_candidates_hook_called_with_refined_text_and_glossary(worker_module):
    """精修完成后应调用 candidates_recorder(refined, glossary)。"""

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            return "内容。"

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            return "整段精修使用 DOM 和 API。"

    record_calls: list[tuple[str, list[str]]] = []
    cfg = AppConfig()
    cfg.glossary = ["CSS"]

    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=lambda _t: None,
        history_adder=lambda *a, **kw: None,
        candidates_recorder=lambda text, glossary: record_calls.append((text, list(glossary))),
    )

    q = _make_segment_queue(worker_module, [b"s1"])
    w._incremental_process("t0", q)

    assert record_calls == [("整段精修使用 DOM 和 API。", ["CSS"])]


def test_candidates_hook_failure_does_not_break_pipeline(worker_module):
    """候选记录失败时主流程（注入、历史）应仍然完成。"""
    inject_calls: list[str] = []
    history_calls: list = []

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            return "内容。"

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            return "精修。"

    def _raise(*_a, **_kw):
        raise RuntimeError("simulated candidates failure")

    cfg = AppConfig()
    w = worker_module.Worker(
        cfg,
        recorder=_FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=inject_calls.append,
        history_adder=lambda *a, **kw: history_calls.append((a, kw)),
        candidates_recorder=_raise,
    )

    q = _make_segment_queue(worker_module, [b"s1"])
    w._incremental_process("t0", q)

    assert inject_calls == ["精修。"]
    assert len(history_calls) == 1
