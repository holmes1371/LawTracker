"""Disk-backed JSON key-value cache for LLM-generated content.

Keeps cost down and makes re-runs idempotent: an article that was
already summarized in a previous scout run hits the cache and skips the
(stubbed or real) LLM call entirely.

Cache keys are stamped with the LLM mode (`stub|...`, `anthropic|...`)
so flipping modes doesn't reuse stub placeholders as if they were real
analyses.

Single file per cache (one for summaries, one for analyses if we ever
add that). Atomic-ish writes via `write_text`; concurrent scout runs
aren't a concern at pilot scale.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonCache:
    """Loaded once; written through after every put."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = self._load()

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def __len__(self) -> int:
        return len(self._data)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Cache failure shouldn't block the scout.
            pass
