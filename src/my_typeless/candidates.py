"""自动 glossary 候选：从精修结果里提取英文缩写，反复出现的提示用户加入 glossary。

为什么用这个简化策略而不是真正的"用户编辑学习"：
我们没有"用户事后修改"的信号（不像 Wispr Flow），所以退而取其次——
精修后的英文缩写大概率是用户常用的技术术语（CSS / DOM / API / Shadow DOM 等），
按累计出现次数排序作为候选展示给用户即可。
"""

import logging
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from my_typeless import history as _history

logger = logging.getLogger(__name__)

# 抓全大写至少 2 字符的 token，允许后缀数字：CSS / DOM / API / HTTP / IO / S3 / HTTP2 / IPv4 不匹配
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]+\b")

# 这些缩写太常见、几乎不是用户特有术语，跳过避免噪声
_STOPWORDS = frozenset({"OK", "TV", "PC", "USA", "UK", "EU", "AM", "PM"})

_conn: sqlite3.Connection | None = None


@dataclass
class Candidate:
    term: str
    count: int
    last_seen: str
    ignored: bool


def _get_conn() -> sqlite3.Connection:
    """返回到 history.db 的连接（与 history 模块共用文件，但表独立）。

    通过 history 模块属性间接读路径，便于测试 monkeypatch history.HISTORY_DB。
    """
    global _conn
    if _conn is not None:
        return _conn

    _history.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(_history.HISTORY_DB), check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS glossary_candidates (
            term TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT NOT NULL,
            ignored INTEGER NOT NULL DEFAULT 0
        )
    """)
    _conn.commit()
    return _conn


def _extract_acronyms(text: str) -> set[str]:
    out: set[str] = set()
    for match in ACRONYM_RE.findall(text):
        if match in _STOPWORDS:
            continue
        out.add(match)
    return out


def record_from_refined(refined_text: str, existing_glossary: Iterable[str]) -> None:
    """从精修文本中累加英文缩写候选；已在 glossary 中的词跳过。"""
    existing = {g.upper() for g in existing_glossary}
    terms = _extract_acronyms(refined_text) - existing
    if not terms:
        return

    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for term in terms:
        conn.execute(
            """
            INSERT INTO glossary_candidates (term, count, last_seen) VALUES (?, 1, ?)
            ON CONFLICT(term) DO UPDATE SET
                count = count + 1,
                last_seen = excluded.last_seen
            """,
            (term, now),
        )
    conn.commit()


def get_candidates(min_count: int = 3, include_ignored: bool = False) -> list[Candidate]:
    """返回累计出现次数 >= min_count 的候选词，按出现频率降序。"""
    conn = _get_conn()
    query = "SELECT term, count, last_seen, ignored FROM glossary_candidates WHERE count >= ?"
    if not include_ignored:
        query += " AND ignored = 0"
    query += " ORDER BY count DESC, last_seen DESC"
    rows = conn.execute(query, (min_count,)).fetchall()
    return [Candidate(term=r[0], count=r[1], last_seen=r[2], ignored=bool(r[3])) for r in rows]


def accept_candidate(term: str) -> None:
    """用户已接受该候选；从候选表移除（前端再把它加进 glossary 配置）。"""
    conn = _get_conn()
    conn.execute("DELETE FROM glossary_candidates WHERE term = ?", (term,))
    conn.commit()


def dismiss_candidate(term: str) -> None:
    """用户拒绝该候选；标记为 ignored，以后默认查询不再返回。"""
    conn = _get_conn()
    conn.execute("UPDATE glossary_candidates SET ignored = 1 WHERE term = ?", (term,))
    conn.commit()


def clear_candidates() -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM glossary_candidates")
    conn.commit()
