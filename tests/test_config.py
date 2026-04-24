import json
from pathlib import Path

from my_typeless import config as config_module


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

    assert cfg.llm.active_provider_id == "migrated-llm"
    assert cfg.llm.active_model == "legacy-chat"
    assert cfg.llm.active_provider is not None
    assert cfg.llm.active_provider.base_url == "https://legacy-llm.example/v1"
    assert cfg.llm.prompt == "custom prompt"

    assert cfg.build_stt_prompt() == "MyTypeless、Whisper"


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
