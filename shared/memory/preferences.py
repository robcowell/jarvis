from copy import deepcopy
from typing import Any

from shared.memory.storage import JsonStorage

DEFAULT_PREFERENCES: dict[str, Any] = {
    "verbosity": "normal",
    "preferred_voice": "ballad",
    "preferred_console": "pi-console",
    "proactive_announcements_enabled": True,
    "briefing": {
        "enabled": True,
        "time_of_day": "morning",
        "include_weather": True,
        "include_calendar": True,
    },
}


def _deep_merge(defaults: Any, overrides: Any) -> Any:
    if isinstance(defaults, dict) and isinstance(overrides, dict):
        merged = deepcopy(defaults)
        for key, value in overrides.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    return deepcopy(overrides)


def _nested_get(source: dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    current: Any = source
    for part in dotted_key.split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return default
            if index < 0 or index >= len(current):
                return default
            current = current[index]
            continue
        return default
    return current


def _nested_set(target: dict[str, Any], dotted_key: str, value: Any) -> dict[str, Any]:
    current = target
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value
    return target


class PreferencesStore:
    """Preference access layer that avoids ad hoc JSON reads/writes."""

    def __init__(self, storage: JsonStorage, defaults: dict[str, Any] | None = None) -> None:
        self._storage = storage
        self._defaults = deepcopy(defaults or DEFAULT_PREFERENCES)

    def initialize(self) -> None:
        if not self._storage.path.is_file():
            self._storage.save(self._defaults)

    def all(self) -> dict[str, Any]:
        current = self._storage.load(default=self._defaults)
        return _deep_merge(self._defaults, current)

    def get(self, key: str, default: Any = None) -> Any:
        return _nested_get(self.all(), key, default)

    def set(self, key: str, value: Any) -> dict[str, Any]:
        updated = _nested_set(self.all(), key, value)
        self._storage.save(updated)
        return updated
