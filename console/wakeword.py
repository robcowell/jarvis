import os
import re

from shared.memory import get_memory_service

_memory = get_memory_service()


def _parse_bool(value: str, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _load_wake_words() -> list[str]:
    configured = os.getenv("WAKE_WORDS")
    if configured is None or configured.strip() == "":
        configured = _memory.configuration.get("wake.words", ["jarvis"])

    if isinstance(configured, list):
        words = [str(part).strip().lower() for part in configured if str(part).strip()]
    else:
        words = [part.strip().lower() for part in str(configured).split(",") if part.strip()]
    return words or ["jarvis"]


WAKE_WORD_ENABLED = _parse_bool(
    os.getenv("WAKE_WORD_ENABLED"),
    bool(_memory.configuration.get("wake.enabled", True)),
)
WAKE_WORDS = _load_wake_words()
WAKE_WORD_DISPLAY = WAKE_WORDS[0]


def contains_wake_word(text: str) -> bool:
    if not text:
        return False
    for word in WAKE_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE):
            return True
    return False


def strip_wake_word(text: str) -> str:
    if not text:
        return ""

    updated = text
    for word in WAKE_WORDS:
        candidate = re.sub(rf"\b{re.escape(word)}\b", "", updated, count=1, flags=re.IGNORECASE)
        if candidate != updated:
            updated = candidate
            break

    updated = re.sub(r"\s+", " ", updated)
    return updated.strip(" \t\r\n,.;:!?-")
