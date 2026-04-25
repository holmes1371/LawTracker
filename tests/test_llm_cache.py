"""Tests for the disk-backed JSON cache used for LLM-generated content."""

from __future__ import annotations

import json
from pathlib import Path

from lawtracker.llm_cache import JsonCache


def test_empty_cache_returns_none(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "c.json")
    assert cache.get("missing") is None
    assert "missing" not in cache


def test_put_and_get_roundtrip(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "c.json")
    cache.put("k1", {"summary": "hello"})
    assert cache.get("k1") == {"summary": "hello"}
    assert "k1" in cache


def test_cache_persists_to_disk(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    cache = JsonCache(path)
    cache.put("k", {"summary": "value"})

    # New instance reads the same file
    cache2 = JsonCache(path)
    assert cache2.get("k") == {"summary": "value"}


def test_cache_writes_indented_utf8_json(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    cache = JsonCache(path)
    cache.put("k", {"summary": "Título con acentos"})
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed["k"]["summary"] == "Título con acentos"
    # Non-ASCII should land as actual characters, not \uXXXX escapes
    assert "Título" in raw


def test_corrupt_cache_reads_empty(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text("not json", encoding="utf-8")
    cache = JsonCache(path)
    assert len(cache) == 0
    assert cache.get("anything") is None


def test_len_reflects_entries(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "c.json")
    assert len(cache) == 0
    cache.put("a", "x")
    cache.put("b", "y")
    assert len(cache) == 2
