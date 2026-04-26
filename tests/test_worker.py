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


def test_incremental_process_with_injected_dependencies(worker_module):
    class FakeRecorder:
        def start(self, on_segment=None):
            return None

        def stop(self):
            return b""

        def cleanup(self):
            return None

    stt_prompts: list[str] = []
    llm_contexts: list[str] = []
    inject_calls: list[str] = []
    history_calls: list[tuple[tuple, dict]] = []

    class FakeSTT:
        def transcribe(self, _audio, prompt=""):
            stt_prompts.append(prompt)
            return "测试文本"

    class FakeLLM:
        def refine(self, text, system_prompt="", context=""):
            llm_contexts.append(context)
            return f"[{text}]"

    cfg = AppConfig()
    cfg.glossary = ["MyTypeless"]

    w = worker_module.Worker(
        cfg,
        recorder=FakeRecorder(),
        stt_client_factory=lambda _cfg: FakeSTT(),
        llm_client_factory=lambda _cfg: FakeLLM(),
        text_injector=inject_calls.append,
        history_adder=lambda *args, **kwargs: history_calls.append((args, kwargs)),
    )

    q = Queue()
    q.put(b"segment-1")
    q.put((worker_module._SENTINEL, "10:00:00.000000"))

    w._incremental_process("09:00:00.000000", q)

    assert stt_prompts == ["MyTypeless"]
    assert llm_contexts == [""]
    assert inject_calls == ["[测试文本]"]
    assert history_calls
    assert history_calls[0][0][0] == "测试文本"
    assert history_calls[0][0][1] == "[测试文本]"
