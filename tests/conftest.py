"""Test fixtures applied across the suite.

Disables the real translation API by default — tests that want to verify
translation behavior should re-patch `lawtracker.translate.translate`
locally inside the test.
"""

import pytest


@pytest.fixture(autouse=True)
def _disable_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lawtracker.translate.translate",
        lambda text, **kwargs: text,
    )
