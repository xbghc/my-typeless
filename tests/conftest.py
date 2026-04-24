from pathlib import Path

import pytest

from my_typeless import config as config_module


@pytest.fixture
def isolated_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config read/write to a temp file for each test."""
    config_dir = tmp_path / ".my-typeless"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_file)
    monkeypatch.setattr(config_module, "DEV_MODE", False)
    return config_file
