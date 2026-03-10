import json
import threading
from pathlib import Path
from typing import Any


class JsonStorage:
    """Small JSON persistence helper with atomic writes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        fallback = dict(default or {})
        if not self._path.is_file():
            return fallback

        with self._lock:
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return fallback

        if not isinstance(payload, dict):
            return fallback
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=True)
        temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        with self._lock:
            temp_path.write_text(f"{text}\n", encoding="utf-8")
            temp_path.replace(self._path)
