"""历史记录管理 - SQLite 存储 STT→LLM 精修的输入输出对"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_DIR = Path.home() / ".my-typeless"
HISTORY_DB = HISTORY_DIR / "history.db"
_LEGACY_FILE = HISTORY_DIR / "history.json"
MAX_HISTORY_ENTRIES = 200

_conn: sqlite3.Connection | None = None


@dataclass
class HistoryEntry:
    timestamp: str
    raw_input: str
    refined_output: str
    key_press_at: str | None = field(default=None)
    key_release_at: str | None = field(default=None)
    stt_done_at: str | None = field(default=None)
    llm_done_at: str | None = field(default=None)

    @staticmethod
    def now(
        raw_input: str,
        refined_output: str,
        *,
        key_press_at: str | None = None,
        key_release_at: str | None = None,
        stt_done_at: str | None = None,
        llm_done_at: str | None = None,
    ) -> "HistoryEntry":
        return HistoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            raw_input=raw_input,
            refined_output=refined_output,
            key_press_at=key_press_at,
            key_release_at=key_release_at,
            stt_done_at=stt_done_at,
            llm_done_at=llm_done_at,
        )


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(HISTORY_DB), check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_input TEXT NOT NULL,
            refined_output TEXT NOT NULL,
            key_press_at TEXT,
            key_release_at TEXT,
            stt_done_at TEXT,
            llm_done_at TEXT
        )
    """)
    _conn.commit()
    _maybe_migrate()
    return _conn


def _prune_history(conn: sqlite3.Connection) -> None:
    """保留最近的历史记录，删除超出上限的旧记录。"""
    conn.execute(
        """
        DELETE FROM history
        WHERE id NOT IN (
            SELECT id FROM history ORDER BY id DESC LIMIT ?
        )
        """,
        (MAX_HISTORY_ENTRIES,),
    )


def _maybe_migrate() -> None:
    if not _LEGACY_FILE.exists():
        return
    try:
        data = json.loads(_LEGACY_FILE.read_text(encoding="utf-8"))
        if not data:
            _LEGACY_FILE.unlink(missing_ok=True)
            return
        conn = _get_conn()
        conn.executemany(
            "INSERT INTO history (timestamp, raw_input, refined_output, key_press_at, key_release_at, stt_done_at, llm_done_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    e.get("timestamp", ""),
                    e.get("raw_input", ""),
                    e.get("refined_output", ""),
                    e.get("key_press_at"),
                    e.get("key_release_at"),
                    e.get("stt_done_at"),
                    e.get("llm_done_at"),
                )
                for e in data
            ],
        )
        _prune_history(conn)
        conn.commit()
        _LEGACY_FILE.unlink(missing_ok=True)
        logger.info("Migrated %d history entries from JSON to SQLite", len(data))
    except Exception:
        logger.exception("Failed to migrate history from JSON to SQLite")


def add_history(
    raw_input: str,
    refined_output: str,
    *,
    key_press_at: str | None = None,
    key_release_at: str | None = None,
    stt_done_at: str | None = None,
    llm_done_at: str | None = None,
) -> None:
    """新增一条历史记录"""
    entry = HistoryEntry.now(
        raw_input,
        refined_output,
        key_press_at=key_press_at,
        key_release_at=key_release_at,
        stt_done_at=stt_done_at,
        llm_done_at=llm_done_at,
    )
    conn = _get_conn()
    conn.execute(
        "INSERT INTO history (timestamp, raw_input, refined_output, key_press_at, key_release_at, stt_done_at, llm_done_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            entry.timestamp,
            entry.raw_input,
            entry.refined_output,
            entry.key_press_at,
            entry.key_release_at,
            entry.stt_done_at,
            entry.llm_done_at,
        ),
    )
    _prune_history(conn)
    conn.commit()


def get_history_page(offset: int = 0, limit: int = 20) -> dict:
    """分页查询历史记录（最新在前）"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, timestamp, raw_input, refined_output, key_press_at, key_release_at, stt_done_at, llm_done_at FROM history ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit + 1, offset),
    ).fetchall()

    has_more = len(rows) > limit
    entries = [
        {
            "id": r[0],
            "timestamp": r[1],
            "raw_input": r[2],
            "refined_output": r[3],
            "key_press_at": r[4],
            "key_release_at": r[5],
            "stt_done_at": r[6],
            "llm_done_at": r[7],
        }
        for r in rows[:limit]
    ]

    return {
        "entries": entries,
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
    }


def clear_history() -> None:
    """清空所有历史记录"""
    conn = _get_conn()
    conn.execute("DELETE FROM history")
    conn.commit()
