"""历史记录管理 - 存储 STT→LLM 精修的输入输出对"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

HISTORY_DIR = Path.home() / ".my-typeless"
HISTORY_FILE = HISTORY_DIR / "history.json"
CORRECTIONS_FILE = HISTORY_DIR / "corrections.json"
MAX_HISTORY = 200  # 最多保留条数
MAX_CORRECTIONS = 5  # few-shot 示例数量


@dataclass
class HistoryEntry:
    timestamp: str
    raw_input: str
    refined_output: str

    @staticmethod
    def now(raw_input: str, refined_output: str) -> "HistoryEntry":
        return HistoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            raw_input=raw_input,
            refined_output=refined_output,
        )


def load_history() -> List[HistoryEntry]:
    """从磁盘加载历史记录（最新在前）"""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return [HistoryEntry(**e) for e in data]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def save_history(entries: List[HistoryEntry]) -> None:
    """保存历史记录到磁盘"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    data = [asdict(e) for e in entries[:MAX_HISTORY]]
    HISTORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_history(raw_input: str, refined_output: str) -> None:
    """新增一条历史记录（最新在前）"""
    entries = load_history()
    entries.insert(0, HistoryEntry.now(raw_input, refined_output))
    save_history(entries)


def clear_history() -> None:
    """清空所有历史记录"""
    save_history([])


# ---- 修正记录（用于 LLM few-shot 优化） ----

@dataclass
class CorrectionEntry:
    raw_input: str        # STT 原始文本（LLM 的输入）
    corrected_output: str  # 用户修正后的文本（期望的 LLM 输出）


def load_corrections() -> List[CorrectionEntry]:
    """加载修正记录"""
    if not CORRECTIONS_FILE.exists():
        return []
    try:
        data = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
        return [CorrectionEntry(**e) for e in data]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def add_correction(raw_input: str, corrected_output: str) -> None:
    """新增一条修正记录（最新在前，仅保留最近几条）"""
    entries = load_corrections()
    entries.insert(0, CorrectionEntry(raw_input, corrected_output))
    entries = entries[:MAX_CORRECTIONS]
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    data = [asdict(e) for e in entries]
    CORRECTIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
