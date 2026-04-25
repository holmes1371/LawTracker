"""Translation helper for non-English sources.

Pilot strategy: HTTP call to MyMemory's free translation API, with
disk-backed caching so repeat scout runs don't re-translate the same
strings.

Adapters opt in by setting `translate_summary_from = "es"` (or "fr",
"pt", etc.) on the class. The base class translates `title` and
`summary` on every emitted record before returning, storing the
originals in metadata as `title_<lang>` and `summary_<lang>`.

Caching:
- In-memory dict during a single process run.
- Disk-backed at `data/scout/.cache/translations.json` (gitignored).
- Loaded once on first call; written through after every successful
  translation. Survives across scout runs so the same Consejo /
  Fiscalía entries are translated exactly once ever.
- To invalidate, delete the file (or set `LAWTRACKER_TRANSLATE_CACHE`
  to a different path).

Free-tier rate limit:
- Without `de` param: 5000 chars/day per IP.
- With `de=<some-address>`: 50,000 chars/day.
- The default `de` is `lawtracker-pilot@example.com` (an obvious
  project-y placeholder; MyMemory doesn't validate addresses).
- Set `LAWTRACKER_TRANSLATE_EMAIL` to override.

Fail-soft: if translation fails (network error, quota exhausted, parse
error), the original text is returned so the scout doesn't break.
"""

import json
import os
import re
from pathlib import Path

import httpx

_API_URL = "https://api.mymemory.translated.net/get"
_MAX_CHARS_PER_REQUEST = 450
_DEFAULT_EMAIL = "lawtracker-pilot@example.com"
_DEFAULT_CACHE_PATH = Path("data/scout/.cache/translations.json")

_MEMORY_CACHE: dict[str, str] = {}
_DISK_LOADED = False


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

    _ensure_disk_cache_loaded()
    key = _cache_key(text, source_lang, target_lang)
    if key in _MEMORY_CACHE:
        return _MEMORY_CACHE[key]

    chunks = _chunk(text, _MAX_CHARS_PER_REQUEST)
    translated_chunks: list[str] = []
    for chunk in chunks:
        translated = _translate_chunk(chunk, source_lang, target_lang)
        if translated is None:
            return text
        translated_chunks.append(translated)

    result = " ".join(translated_chunks).strip() or text
    if result != text:
        _MEMORY_CACHE[key] = result
        _persist_cache()
    return result


def _translate_chunk(text: str, source_lang: str, target_lang: str) -> str | None:
    email = os.environ.get("LAWTRACKER_TRANSLATE_EMAIL", _DEFAULT_EMAIL).strip()
    params: dict[str, str] = {
        "q": text,
        "langpair": f"{source_lang}|{target_lang}",
    }
    if email:
        params["de"] = email

    try:
        response = httpx.get(_API_URL, params=params, timeout=10)
    except httpx.RequestError:
        return None

    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None

    response_data = data.get("responseData") or {}
    translated = response_data.get("translatedText")
    if not isinstance(translated, str) or not translated.strip():
        return None
    if "MYMEMORY WARNING" in translated.upper():
        # Free-tier quota exhausted; the response masquerades as a
        # translation but is actually the warning string. Fail-soft —
        # caller falls back to the original text.
        return None
    if data.get("quotaFinished") is True:
        return None
    return translated


def _cache_key(text: str, source_lang: str, target_lang: str) -> str:
    return f"{source_lang}|{target_lang}|{text}"


def _cache_path() -> Path:
    override = os.environ.get("LAWTRACKER_TRANSLATE_CACHE")
    return Path(override) if override else _DEFAULT_CACHE_PATH


def _ensure_disk_cache_loaded() -> None:
    global _DISK_LOADED
    if _DISK_LOADED:
        return
    path = _cache_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str):
                        _MEMORY_CACHE[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    _DISK_LOADED = True


def _persist_cache() -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_MEMORY_CACHE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


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
    """Test-only: clear the in-memory cache and reset disk-load flag."""
    global _DISK_LOADED
    _MEMORY_CACHE.clear()
    _DISK_LOADED = False
