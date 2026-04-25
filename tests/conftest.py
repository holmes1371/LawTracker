"""Test fixtures applied across the suite.

Disables the real translation API and forces stub LLM mode by default.
Tests that want to verify the real behavior should re-patch the relevant
function locally inside the test.
"""

import pytest


@pytest.fixture(autouse=True)
def _disable_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lawtracker.translate.translate",
        lambda text, **kwargs: text,
    )


@pytest.fixture(autouse=True)
def _stub_llm_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force stub mode for the LLM during tests so no anthropic-mode call
    can sneak through even if env happens to be set."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
