"""Tests for the translation helper.

Re-patches `lawtracker.translate.translate` in each test so the live
default conftest no-op doesn't interfere.
"""

from typing import Any

import httpx
import pytest

from lawtracker import translate as translate_mod

# Capture the real `translate` function at module-import time, before conftest's
# autouse fixture replaces it with a no-op. Each test re-restores it.
_REAL_TRANSLATE = translate_mod.translate


@pytest.fixture(autouse=True)
def _restore_real_translate(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Undo the conftest auto-mock so we can exercise the real translate fn.

    Also points the disk-cache at a fresh tmp path so each test starts with
    an empty cache and no leakage from a real `data/scout/.cache/...`.
    """
    monkeypatch.setattr(translate_mod, "translate", _REAL_TRANSLATE)
    monkeypatch.setenv("LAWTRACKER_TRANSLATE_CACHE", str(tmp_path / "translations.json"))


def _patch_httpx_get(
    monkeypatch: pytest.MonkeyPatch,
    response_factory: Any,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, *, params: dict[str, Any] | None = None, timeout: float = 10) -> Any:
        calls.append({"url": url, "params": params or {}})
        return response_factory(params or {})

    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


def _ok_response(translated_text: str) -> Any:
    class _Resp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "responseData": {"translatedText": translated_text},
                "quotaFinished": False,
                "responseStatus": 200,
            }

    return _Resp()


def test_empty_input_returns_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()
    calls = _patch_httpx_get(monkeypatch, lambda p: _ok_response(""))
    assert translate_mod.translate("") == ""
    assert translate_mod.translate("   ") == "   "
    assert calls == []


def test_same_lang_returns_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()
    calls = _patch_httpx_get(monkeypatch, lambda p: _ok_response("ignored"))
    assert translate_mod.translate("hola", source_lang="es", target_lang="es") == "hola"
    assert calls == []


def test_translates_short_text(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()
    _patch_httpx_get(monkeypatch, lambda p: _ok_response("Hello world"))
    assert translate_mod.translate("Hola mundo") == "Hello world"


def test_caches_repeat_translations(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()
    calls = _patch_httpx_get(monkeypatch, lambda p: _ok_response("Hello"))
    translate_mod.translate("Hola")
    translate_mod.translate("Hola")
    assert len(calls) == 1, "second call should be served from cache"


def test_chunks_long_text_and_joins_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()
    sentence = "Una oración corta de prueba. " * 30  # > 500 chars
    counter = {"i": 0}

    def factory(params: dict[str, Any]) -> Any:
        counter["i"] += 1
        return _ok_response(f"chunk-{counter['i']}")

    _patch_httpx_get(monkeypatch, factory)
    result = translate_mod.translate(sentence)
    assert "chunk-1" in result
    assert counter["i"] >= 2, "long text should chunk into multiple requests"


def test_returns_original_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()

    def boom(url: str, *, params: dict[str, Any] | None = None, timeout: float = 10) -> Any:
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx, "get", boom)
    assert translate_mod.translate("hola") == "hola"


def test_returns_original_on_quota_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()

    class _QuotaResp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "responseData": {"translatedText": "should not be used"},
                "quotaFinished": True,
                "responseStatus": 200,
            }

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _QuotaResp())
    assert translate_mod.translate("hola") == "hola"


def test_long_punctuationless_sentence_is_word_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a single sentence longer than the limit must be word-split,
    not passed whole. Real-world trigger: Consejo summaries that arrive as one
    long sentence with no internal .!? — MyMemory rejected them with
    'QUERY LENGTH LIMIT EXCEEDED. MAX ALLOWED QUERY : 500 CHARS'."""
    translate_mod._reset_cache_for_tests()
    long_text = " ".join(["palabra"] * 100)  # ~800 chars, no .!?
    counter = {"i": 0}
    sent_lengths: list[int] = []

    def factory(params: dict[str, Any]) -> Any:
        counter["i"] += 1
        q = params.get("q", "") or ""
        sent_lengths.append(len(q))
        return _ok_response(f"chunk-{counter['i']}")

    _patch_httpx_get(monkeypatch, factory)
    result = translate_mod.translate(long_text)
    assert counter["i"] >= 2, "long sentence must split into multiple chunks"
    assert all(n <= 450 for n in sent_lengths), (
        f"every chunk must be ≤ 450 chars; got {sent_lengths}"
    )
    assert "chunk-1" in result


def test_returns_original_on_non_200_status(monkeypatch: pytest.MonkeyPatch) -> None:
    translate_mod._reset_cache_for_tests()

    class _ErrResp:
        status_code = 503

        def json(self) -> dict[str, Any]:
            return {}

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _ErrResp())
    assert translate_mod.translate("hola") == "hola"
