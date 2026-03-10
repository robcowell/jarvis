from copy import deepcopy
from typing import Any

from shared.memory.storage import JsonStorage

DEFAULT_CONFIGURATION: dict[str, Any] = {
    "core": {
        "url": "",
        "host": "0.0.0.0",
        "port": 8000,
        "timeout_seconds": 20.0,
        "tts_timeout_seconds": 20.0,
    },
    "command": {
        "model": "gpt-5",
    },
    "transcribe": {
        "model": "gpt-4o-mini-transcribe",
    },
    "tts_engine": {
        "mode": "core_only",
        "provider": "openai",
        "model": "gpt-4o-mini-tts",
        "voice": "ballad",
        "instructions": "Speak in clear British English with a consistent, natural assistant tone.",
        "sample_rate": 22050,
        "aplay_path": "aplay",
    },
    "piper": {
        "executable_path": "/home/robcowell/piper/build/piper",
        "model_path": "/home/robcowell/piper/voices/en_US-lessac-medium.onnx",
    },
    "registered_consoles": [
        {
            "device_id": "pi-console",
            "location": "unknown",
            "preferred": True,
        }
    ],
    "voice": {
        "max_duration": 6.0,
        "sample_rate": 16000,
        "chunk_size": 1024,
        "speech_threshold": 0.012,
        "silence_duration": 0.75,
        "min_speech_duration": 0.35,
        "no_speech_timeout": 2.0,
        "pre_roll_chunks": 2,
        "audio_device_index": -1,
    },
    "wake": {
        "enabled": True,
        "words": ["jarvis"],
        "always_listen_enabled": False,
        "detection_cooldown": 1.5,
        "porcupine": {
            "keywords": ["jarvis"],
            "sensitivity": 0.6,
            "audio_device_index": None,
            "access_key": "",
            "restart_retries": 8,
            "restart_delay": 0.15,
        },
    },
    "integrations": {
        "home_assistant": {"enabled": False, "url": ""},
        "calendar": {"enabled": False},
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


class ConfigurationStore:
    """Runtime configuration access layer backed by JSON."""

    def __init__(self, storage: JsonStorage, defaults: dict[str, Any] | None = None) -> None:
        self._storage = storage
        self._defaults = deepcopy(defaults or DEFAULT_CONFIGURATION)

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
