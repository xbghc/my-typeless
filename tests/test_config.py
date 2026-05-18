import json
from pathlib import Path

import pytest

from my_typeless import config as config_module
from my_typeless.config import AppConfig


def test_load_migrates_legacy_provider_fields(isolated_config_file: Path) -> None:
    # Arrange: old schema stores provider fields directly under stt/llm.
    isolated_config_file.parent.mkdir(parents=True, exist_ok=True)
    isolated_config_file.write_text(
        json.dumps(
            {
                "hotkey": "f8",
                "start_with_windows": True,
                "stt": {
                    "base_url": "https://legacy-stt.example/v1",
                    "api_key": "stt-key",
                    "model": "whisper-legacy",
                    "language": "zh",
                },
                "llm": {
                    "base_url": "https://legacy-llm.example/v1",
                    "api_key": "llm-key",
                    "model": "legacy-chat",
                    "prompt": "custom prompt",
                },
                "glossary": ["MyTypeless", "Whisper"],
            }
        ),
        encoding="utf-8",
    )

    # Act
    cfg = config_module.AppConfig.load()

    # Assert: legacy fields are migrated into provider list + active ids.
    assert cfg.hotkey == "f8"
    assert cfg.start_with_windows is True

    assert cfg.stt.active_provider_id == "migrated-stt"
    assert cfg.stt.active_model == "whisper-legacy"
    assert cfg.stt.active_provider is not None
    assert cfg.stt.active_provider.base_url == "https://legacy-stt.example/v1"
    assert cfg.stt.active_provider.models == ["whisper-legacy"]
    assert cfg.stt.language == "zh"

    assert cfg.llm.active_provider_id == "migrated-llm"
    assert cfg.llm.active_model == "legacy-chat"
    assert cfg.llm.active_provider is not None
    assert cfg.llm.active_provider.base_url == "https://legacy-llm.example/v1"
    assert cfg.llm.prompt == "custom prompt"

    # build_stt_prompt 现在用自然句嵌入术语（OpenAI cookbook 推荐），不再是裸顿号列表
    stt_prompt = cfg.build_stt_prompt()
    assert "MyTypeless" in stt_prompt
    assert "Whisper" in stt_prompt


def test_load_falls_back_to_defaults_on_invalid_json(isolated_config_file: Path) -> None:
    # Arrange: corrupt file content should not crash loading.
    isolated_config_file.parent.mkdir(parents=True, exist_ok=True)
    isolated_config_file.write_text("{ invalid json", encoding="utf-8")

    # Act
    cfg = config_module.AppConfig.load()

    # Assert: returns defaults and rewrites file to normalized valid JSON.
    assert cfg.hotkey == "right alt"
    assert cfg.stt.active_provider_id == "default-stt"
    assert cfg.llm.active_provider_id == "default-llm"
    assert cfg.llm.prompt == config_module.DEFAULT_LLM_PROMPT

    saved = json.loads(isolated_config_file.read_text(encoding="utf-8"))
    assert saved["hotkey"] == "right alt"


def test_load_creates_default_config_when_file_missing(isolated_config_file: Path) -> None:
    # Arrange: no config file exists.
    assert not isolated_config_file.exists()

    # Act
    cfg = config_module.AppConfig.load()

    # Assert: default config is returned and file is created.
    assert cfg.hotkey == "right alt"
    assert isolated_config_file.exists()

    saved = json.loads(isolated_config_file.read_text(encoding="utf-8"))
    assert saved["hotkey"] == "right alt"


def test_save_and_reload_roundtrip(isolated_config_file: Path) -> None:
    cfg = AppConfig()
    cfg.hotkey = "f12"
    cfg.glossary = ["CSS", "DOM", "Shadow DOM"]
    cfg.save()

    reloaded = AppConfig.load()
    assert reloaded.hotkey == "f12"
    assert reloaded.glossary == ["CSS", "DOM", "Shadow DOM"]


def test_modern_providers_format_is_preserved(isolated_config_file: Path) -> None:
    modern = {
        "hotkey": "f12",
        "stt": {
            "providers": [
                {
                    "id": "groq",
                    "name": "Groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "api_key": "k1",
                    "models": ["whisper-large-v3"],
                    "provider_type": "openai",
                }
            ],
            "active_provider_id": "groq",
            "active_model": "whisper-large-v3",
            "language": "zh",
        },
        "llm": {
            "providers": [
                {
                    "id": "anthropic",
                    "name": "Anthropic",
                    "base_url": "",
                    "api_key": "k2",
                    "models": ["claude-sonnet-4-6"],
                    "provider_type": "anthropic",
                }
            ],
            "active_provider_id": "anthropic",
            "active_model": "claude-sonnet-4-6",
            "prompt": "custom user prompt",
        },
        "glossary": ["CSS", "DOM"],
    }
    isolated_config_file.parent.mkdir(parents=True, exist_ok=True)
    isolated_config_file.write_text(json.dumps(modern), encoding="utf-8")

    cfg = AppConfig.load()
    assert cfg.stt.active_provider_id == "groq"
    assert cfg.stt.providers[0].provider_type == "openai"
    assert cfg.llm.active_provider_id == "anthropic"
    assert cfg.llm.providers[0].provider_type == "anthropic"
    assert cfg.llm.prompt == "custom user prompt"
    assert cfg.glossary == ["CSS", "DOM"]


def test_dev_mode_overrides_user_prompt(
    isolated_config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEV_MODE=1 时用户在 config 里改过的 prompt 应被代码中的 DEFAULT_LLM_PROMPT 覆盖。"""
    monkeypatch.setattr(config_module, "DEV_MODE", True)
    isolated_config_file.parent.mkdir(parents=True, exist_ok=True)
    isolated_config_file.write_text(
        json.dumps({"llm": {"prompt": "用户自定义 prompt"}}),
        encoding="utf-8",
    )

    cfg = AppConfig.load()
    assert cfg.llm.prompt == config_module.DEFAULT_LLM_PROMPT


def test_default_stt_language_is_zh(isolated_config_file: Path) -> None:
    """默认语言应为 'zh'，避免 Whisper auto-detect 输出繁体/误判语言。"""
    cfg = AppConfig.load()
    assert cfg.stt.language == "zh"


def test_build_stt_prompt_embeds_glossary_in_natural_sentence(isolated_config_file: Path) -> None:
    """STT prompt 应以自然句包含所有 glossary 术语（OpenAI cookbook 推荐格式）。"""
    cfg = AppConfig()
    cfg.glossary = ["CSS", "DOM", "Shadow DOM"]
    prompt = cfg.build_stt_prompt()
    assert "CSS" in prompt
    assert "DOM" in prompt
    assert "Shadow DOM" in prompt
    # 应是自然句而非纯顿号列表
    assert "术语" in prompt or "句子" in prompt


def test_build_stt_prompt_empty_when_no_glossary(isolated_config_file: Path) -> None:
    cfg = AppConfig()
    assert cfg.build_stt_prompt() == ""


def test_build_llm_system_prompt_appends_glossary_section(isolated_config_file: Path) -> None:
    """glossary 非空时应作为 '## 用户术语表' 段落追加到 LLM system prompt。"""
    cfg = AppConfig()
    cfg.glossary = ["CSS", "DOM"]
    prompt = cfg.build_llm_system_prompt()
    assert cfg.llm.prompt in prompt
    assert "用户术语表" in prompt
    assert "CSS" in prompt
    assert "DOM" in prompt


def test_build_llm_system_prompt_no_glossary_section_when_empty(
    isolated_config_file: Path,
) -> None:
    cfg = AppConfig()
    assert cfg.glossary == []
    assert cfg.build_llm_system_prompt() == cfg.llm.prompt


def test_invalid_glossary_type_falls_back_to_empty_list(isolated_config_file: Path) -> None:
    """config.json 里 glossary 非 list 时应回退为空列表而非抛错。"""
    isolated_config_file.parent.mkdir(parents=True, exist_ok=True)
    isolated_config_file.write_text(
        json.dumps({"glossary": "not a list"}),
        encoding="utf-8",
    )
    cfg = AppConfig.load()
    assert cfg.glossary == []
