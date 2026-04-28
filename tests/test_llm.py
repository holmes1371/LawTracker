"""Tests for the LLM helper.

Each test sets `LAWTRACKER_LLM_MODE` directly to override the conftest
default. We don't actually hit the Anthropic API — `anthropic`-mode tests
patch `_complete_anthropic` to a fake.
"""

from __future__ import annotations

import pytest

from lawtracker import llm


def test_stub_mode_returns_stub_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    out = llm.complete(system="sys", user="user", stub="canned response")
    assert out == "canned response"


def test_off_mode_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "off")
    out = llm.complete(system="sys", user="user", stub="ignored")
    assert out == ""


def test_default_mode_is_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAWTRACKER_LLM_MODE", raising=False)
    out = llm.complete(system="sys", user="user", stub="default-stub")
    assert out == "default-stub"


def test_anthropic_mode_calls_real_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")
    captured: dict[str, object] = {}

    def fake_anthropic(system: str, user: str, max_tokens: int, model: str) -> str:
        captured["system"] = system
        captured["user"] = user
        captured["model"] = model
        captured["max_tokens"] = max_tokens
        return "real-response"

    monkeypatch.setattr(llm, "_complete_anthropic", fake_anthropic)
    out = llm.complete(system="sys", user="user", stub="should-not-show", model="claude-x")
    assert out == "real-response"
    assert captured["system"] == "sys"
    assert captured["user"] == "user"
    assert captured["model"] == "claude-x"


def test_anthropic_mode_without_sdk_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If anthropic mode is set but the SDK isn't installed, callers get a
    helpful RuntimeError, not a silent fallback."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")

    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("simulated missing anthropic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="anthropic SDK is not installed"):
        llm.complete(system="sys", user="user", stub="ignored")


def test_anthropic_mode_without_api_key_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If anthropic mode is set but ANTHROPIC_API_KEY is missing, callers
    get a clear RuntimeError up front — not a buried SDK auth stack trace
    after we've already loaded events and built the prompt.

    CI does not have `anthropic` installed (it's a runtime-optional dep),
    so we inject a stub module via sys.modules so the import succeeds and
    the API-key check is what raises."""
    import sys
    import types

    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        llm.complete(system="sys", user="user", stub="ignored")
