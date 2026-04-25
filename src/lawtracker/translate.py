"""Translation helper for non-English sources.

Pilot strategy: HTTP call to MyMemory's free translation API. No API key,
no Python dependency beyond httpx (already in the project). Fail-soft —
if translation fails for any reason, the original text is returned so
the scout doesn't break.

Adapters opt in by setting `translate_summary_from = "es"` (or "fr",
"pt", etc.) on the class. The base class translates `title` and
`summary` on every emitted record before returning, storing the
originals in metadata as `title_<lang>` and `summary_<lang>`.

Caching: in-memory across a single scout run to avoid retranslating
duplicate phrases. Reset between runs (no persistence).

Quality / cost notes for Tom + Ellen:
- Free tier ~5000 chars/day per IP without an email param.
- Quality is community-contributed memory plus machine translation —
  okay for general prose, occasionally clumsy on legal terminology.
- If we outgrow it during pilot review (item 18), swap options:
    1. argostranslate (offline, ~250MB model, fully deterministic).
    2. DeepL API (paid, best quality for legal text).
    3. Google Cloud Translate API (paid, well-supported).
  Each is a `translate()` swap; adapters don't need to change.
"""

import re

import httpx

_CACHE: dict[tuple[str, str, str], str] = {}
_API_URL = "https://api.mymemory.translated.net/get"
# MyMemory's stated limit is 500 chars; use 450 as a safety margin for
# URL-encoding inflation (accented chars become %XX sequences) in their
# server-side length check.
_MAX_CHARS_PER_REQUEST = 450


def translate(
    text: str,
    *,
    source_lang: str = "es",
    target_lang: str = "en",
) -> str:
    """Translate `text` from source_lang to target_lang. Fail-soft.

    Empty / blank input returns unchanged. If source == target, returns
    the input unchanged. On any HTTP / parse / quota failure, returns
    the original text.
    """
    if not text or not text.strip():
        return text
    if source_lang == target_lang:
        return text

    key = (text, source_lang, target_lang)
    if key in _CACHE:
        return _CACHE[key]

    chunks = _chunk(text, _MAX_CHARS_PER_REQUEST)
    translated_chunks: list[str] = []
    for chunk in chunks:
        translated = _translate_chunk(chunk, source_lang, target_lang)
        if translated is None:
            return text
        translated_chunks.append(translated)

    result = " ".join(translated_chunks).strip()
    _CACHE[key] = result
    return result or text


def _translate_chunk(text: str, source_lang: str, target_lang: str) -> str | None:
    try:
        response = httpx.get(
            _API_URL,
            params={"q": text, "langpair": f"{source_lang}|{target_lang}"},
            timeout=10,
        )
    except httpx.RequestError:
        return None

    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if data.get("quotaFinished") is True:
        return None
    response_data = data.get("responseData") or {}
    translated = response_data.get("translatedText")
    if not isinstance(translated, str) or not translated.strip():
        return None
    return translated


def _chunk(text: str, max_chars: int) -> list[str]:
    """Split text into chunks each ≤ max_chars.

    Tries sentence boundaries (.!?) first; falls back to word boundaries
    when a single sentence is itself too long. Pathological case (a
    single word longer than max_chars) is hard-truncated.
    """
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_word_split(sentence, max_chars))
            continue
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
    if current:
        chunks.append(current.strip())
    return chunks


def _word_split(text: str, max_chars: int) -> list[str]:
    """Hard-split on word boundaries when a sentence exceeds max_chars."""
    chunks: list[str] = []
    current = ""
    for word in text.split():
        if len(word) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(word[:max_chars])
            continue
        if current and len(current) + len(word) + 1 > max_chars:
            chunks.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        chunks.append(current)
    return chunks


def _reset_cache_for_tests() -> None:
    """Test-only: clear the in-memory cache."""
    _CACHE.clear()
