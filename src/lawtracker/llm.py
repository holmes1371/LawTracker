"""LLM helper — Claude / Anthropic API for prose interpretation.

Modes:

- **stub** (default) — returns the caller's `stub` argument verbatim. No
  API spend. Used during design iteration, in CI, and in tests. Tom
  picked this 2026-04-25 specifically because we'll iterate heavily on
  prompt design and output formats before flipping to live calls.
- **anthropic** — calls the real Claude API. Lazy-imports `anthropic`
  so the SDK is only required when this mode is selected. Reads
  `ANTHROPIC_API_KEY` from env; the SDK handles the rest.
- **off** — returns an empty string. Useful for measuring how the rest
  of the pipeline behaves with no LLM contribution.

Toggle the mode with the `LAWTRACKER_LLM_MODE` env var (the CLI sets
this from `--llm-mode`). Defaults to `stub` when unset.

Each caller passes a context-specific `stub` string so the placeholder
content is plausible for the surface where it'll be displayed (analysis
markdown, JSON record list, etc.). The orchestrator code (analysis
writer, SEC adapter) can keep working against stub responses while Tom
iterates on prompts.
"""

from __future__ import annotations

import os
from typing import Final

DEFAULT_MODEL: Final[str] = "claude-sonnet-4-5"


def complete(
    *,
    system: str,
    user: str,
    stub: str = "[STUB LLM RESPONSE]",
    max_tokens: int = 2048,
    model: str = DEFAULT_MODEL,
) -> str:
    """Call the configured LLM. Returns text content.

    In stub mode (default), returns `stub` verbatim — never touches the
    network. In `anthropic` mode, calls Claude. In `off` mode, returns
    an empty string.

    Fail-soft: if `anthropic` mode is set but the SDK or API key is
    unavailable, raises a clear RuntimeError (vs. silently returning
    stub) so callers know the configuration is wrong.
    """
    mode = os.environ.get("LAWTRACKER_LLM_MODE", "stub").lower()
    if mode == "off":
        return ""
    if mode == "anthropic":
        return _complete_anthropic(system, user, max_tokens, model)
    return stub


def _complete_anthropic(system: str, user: str, max_tokens: int, model: str) -> str:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "LAWTRACKER_LLM_MODE=anthropic but the anthropic SDK is not installed. "
            "Run `pip install anthropic` (or set the mode back to stub for design "
            "iteration)."
        ) from exc

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "LAWTRACKER_LLM_MODE=anthropic but ANTHROPIC_API_KEY is not set. "
            "In PowerShell:  $env:ANTHROPIC_API_KEY = \"sk-ant-...\"  "
            "(persistent: [Environment]::SetEnvironmentVariable("
            "\"ANTHROPIC_API_KEY\", \"sk-ant-...\", \"User\")). "
            "Or set --llm-mode=stub for design iteration without API spend."
        )

    client = Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    blocks = getattr(message, "content", []) or []
    parts: list[str] = []
    for block in blocks:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)
