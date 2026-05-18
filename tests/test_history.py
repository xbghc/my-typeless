"""测试历史记录的写入、分页、prune 与旧 JSON 迁移。"""

import json
from pathlib import Path

import pytest

from my_typeless import history as history_mod


@pytest.fixture
def tmp_history(monkeypatch, tmp_path: Path):
    """把 history 模块的全局路径与连接重定向到 tmp_path，每个测试隔离。"""
    monkeypatch.setattr(history_mod, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(history_mod, "HISTORY_DB", tmp_path / "history.db")
    monkeypatch.setattr(history_mod, "_LEGACY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(history_mod, "_conn", None)
    yield tmp_path
    # teardown：关闭连接，避免 Windows 文件锁影响 tmp_path 清理
    if history_mod._conn is not None:
        history_mod._conn.close()
        monkeypatch.setattr(history_mod, "_conn", None)


def test_add_and_query_single_entry(tmp_history):
    history_mod.add_history("raw text", "refined text")
    page = history_mod.get_history_page(offset=0, limit=10)

    assert page["has_more"] is False
    assert page["next_offset"] is None
    assert len(page["entries"]) == 1
    e = page["entries"][0]
    assert e["raw_input"] == "raw text"
    assert e["refined_output"] == "refined text"
    assert e["timestamp"]  # 应有非空时间戳


def test_pagination_returns_newest_first_with_has_more(tmp_history):
    for i in range(15):
        history_mod.add_history(f"raw{i}", f"refined{i}")

    page = history_mod.get_history_page(offset=0, limit=10)
    assert len(page["entries"]) == 10
    assert page["has_more"] is True
    assert page["next_offset"] == 10
    # 最新优先
    assert page["entries"][0]["raw_input"] == "raw14"
    assert page["entries"][9]["raw_input"] == "raw5"

    page2 = history_mod.get_history_page(offset=10, limit=10)
    assert len(page2["entries"]) == 5
    assert page2["has_more"] is False
    assert page2["next_offset"] is None
    assert page2["entries"][0]["raw_input"] == "raw4"


def test_prune_caps_at_max_entries(tmp_history, monkeypatch):
    """超出 MAX_HISTORY_ENTRIES 时 _prune_history 应保留最新的那批。"""
    monkeypatch.setattr(history_mod, "MAX_HISTORY_ENTRIES", 5)
    for i in range(8):
        history_mod.add_history(f"raw{i}", f"refined{i}")

    page = history_mod.get_history_page(offset=0, limit=20)
    assert len(page["entries"]) == 5
    # 最新 5 条应是 raw3..raw7
    assert [e["raw_input"] for e in page["entries"]] == [f"raw{i}" for i in range(7, 2, -1)]


def test_clear_history_empties_table(tmp_history):
    history_mod.add_history("a", "A")
    history_mod.add_history("b", "B")
    history_mod.clear_history()

    page = history_mod.get_history_page()
    assert page["entries"] == []
    assert page["has_more"] is False


def test_timing_columns_are_persisted(tmp_history):
    history_mod.add_history(
        "raw",
        "refined",
        key_press_at="12:00:00.000000",
        key_release_at="12:00:05.000000",
        stt_done_at="12:00:06.500000",
        llm_done_at="12:00:08.200000",
    )
    page = history_mod.get_history_page()
    e = page["entries"][0]
    assert e["key_press_at"] == "12:00:00.000000"
    assert e["key_release_at"] == "12:00:05.000000"
    assert e["stt_done_at"] == "12:00:06.500000"
    assert e["llm_done_at"] == "12:00:08.200000"


def test_legacy_json_migration(tmp_history: Path):
    legacy_data = [
        {
            "timestamp": "2026-01-01 12:00",
            "raw_input": "old raw",
            "refined_output": "old refined",
            "key_press_at": "12:00:00.000",
            "key_release_at": "12:00:03.000",
            "stt_done_at": "12:00:04.000",
            "llm_done_at": "12:00:05.000",
        },
        {
            "timestamp": "2026-01-02 09:00",
            "raw_input": "old raw 2",
            "refined_output": "old refined 2",
        },
    ]
    legacy_file = tmp_history / "history.json"
    legacy_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    # 触发 _get_conn → _maybe_migrate
    page = history_mod.get_history_page(offset=0, limit=10)

    assert len(page["entries"]) == 2
    raw_inputs = {e["raw_input"] for e in page["entries"]}
    assert raw_inputs == {"old raw", "old raw 2"}
    # 旧 JSON 文件应被删除
    assert not legacy_file.exists()


def test_legacy_migration_skips_when_file_absent(tmp_history):
    """无旧文件时不应报错。"""
    history_mod.add_history("raw", "refined")
    page = history_mod.get_history_page()
    assert len(page["entries"]) == 1
