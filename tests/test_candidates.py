"""测试 glossary 候选机制：提取、累加、过滤、accept/dismiss。"""

from pathlib import Path

import pytest

from my_typeless import candidates as candidates_mod
from my_typeless import history as history_mod
from my_typeless.candidates import (
    _extract_acronyms,
    accept_candidate,
    clear_candidates,
    dismiss_candidate,
    get_candidates,
    record_from_refined,
)


@pytest.fixture
def tmp_candidates(monkeypatch, tmp_path: Path):
    """把候选 + history 用的 db 重定向到 tmp_path。"""
    monkeypatch.setattr(history_mod, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(history_mod, "HISTORY_DB", tmp_path / "history.db")
    monkeypatch.setattr(history_mod, "_LEGACY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(history_mod, "_conn", None)
    monkeypatch.setattr(candidates_mod, "_conn", None)
    yield tmp_path
    if candidates_mod._conn is not None:
        candidates_mod._conn.close()
        monkeypatch.setattr(candidates_mod, "_conn", None)
    if history_mod._conn is not None:
        history_mod._conn.close()
        monkeypatch.setattr(history_mod, "_conn", None)


def test_extract_acronyms_basic():
    text = "我们用 CSS 和 DOM 实现 BEM 命名，调用 API 走 HTTP 协议。"
    assert _extract_acronyms(text) == {"CSS", "DOM", "BEM", "API", "HTTP"}


def test_extract_acronyms_filters_single_letters_and_lowercase():
    text = "A simple test with css and dom should not match."
    assert _extract_acronyms(text) == set()


def test_extract_acronyms_skips_common_stopwords():
    text = "OK 我们在 USA 测试，结果 PM 出问题。"
    extracted = _extract_acronyms(text)
    assert "OK" not in extracted
    assert "USA" not in extracted
    assert "PM" not in extracted


def test_extract_acronyms_allows_trailing_digits():
    text = "用 S3 存储，IPv4 走 HTTP2 协议。"
    extracted = _extract_acronyms(text)
    assert "S3" in extracted


def test_record_and_get_candidates_basic_flow(tmp_candidates):
    record_from_refined("讨论 CSS 和 DOM。", existing_glossary=[])

    # 首次只出现 1 次，不应达到默认 min_count=3
    assert get_candidates(min_count=3) == []
    # 用 min_count=1 应能看到
    cands = get_candidates(min_count=1)
    terms = {c.term for c in cands}
    assert terms == {"CSS", "DOM"}
    assert all(c.count == 1 for c in cands)


def test_count_accumulates_across_calls(tmp_candidates):
    for _ in range(3):
        record_from_refined("使用 CSS 处理样式", existing_glossary=[])
    record_from_refined("DOM 出现一次", existing_glossary=[])

    cands = get_candidates(min_count=3)
    assert len(cands) == 1
    assert cands[0].term == "CSS"
    assert cands[0].count == 3


def test_glossary_terms_are_excluded(tmp_candidates):
    """已在 glossary 中的词不应进入候选表。"""
    record_from_refined("CSS DOM API", existing_glossary=["CSS", "DOM"])
    cands = get_candidates(min_count=1)
    terms = {c.term for c in cands}
    assert "CSS" not in terms
    assert "DOM" not in terms
    assert "API" in terms


def test_glossary_match_is_case_insensitive(tmp_candidates):
    """glossary 里写小写 'css'，也应阻止 'CSS' 进入候选。"""
    record_from_refined("CSS DOM", existing_glossary=["css"])
    cands = get_candidates(min_count=1)
    terms = {c.term for c in cands}
    assert "CSS" not in terms
    assert "DOM" in terms


def test_accept_candidate_removes_from_table(tmp_candidates):
    record_from_refined("API", existing_glossary=[])
    record_from_refined("API", existing_glossary=[])

    assert {c.term for c in get_candidates(min_count=1)} == {"API"}

    accept_candidate("API")

    assert get_candidates(min_count=1) == []


def test_dismiss_candidate_hides_by_default_but_keeps_record(tmp_candidates):
    record_from_refined("API CSS", existing_glossary=[])
    dismiss_candidate("API")

    # 默认查询应只剩 CSS
    visible = {c.term for c in get_candidates(min_count=1)}
    assert visible == {"CSS"}

    # 包含 ignored 时仍可看到 API
    all_terms = {c.term for c in get_candidates(min_count=1, include_ignored=True)}
    assert "API" in all_terms


def test_results_ordered_by_count_descending(tmp_candidates):
    for _ in range(5):
        record_from_refined("CSS", existing_glossary=[])
    for _ in range(3):
        record_from_refined("DOM", existing_glossary=[])
    record_from_refined("API", existing_glossary=[])

    cands = get_candidates(min_count=1)
    assert [c.term for c in cands] == ["CSS", "DOM", "API"]


def test_clear_candidates_empties_table(tmp_candidates):
    record_from_refined("CSS DOM API", existing_glossary=[])
    clear_candidates()
    assert get_candidates(min_count=1) == []


def test_empty_text_is_noop(tmp_candidates):
    record_from_refined("", existing_glossary=[])
    record_from_refined("纯中文没有缩写", existing_glossary=[])
    assert get_candidates(min_count=1) == []
