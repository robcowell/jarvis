import os
from dataclasses import dataclass
from pathlib import Path

from shared.memory.configuration import ConfigurationStore
from shared.memory.preferences import PreferencesStore
from shared.memory.storage import JsonStorage

_memory_service = None


@dataclass
class JarvisMemoryService:
    """Facade exposing separate preferences and configuration stores."""

    preferences: PreferencesStore
    configuration: ConfigurationStore


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _data_dir() -> Path:
    raw = os.getenv("JARVIS_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_project_root() / "data").resolve()


def get_memory_service() -> JarvisMemoryService:
    global _memory_service
    if _memory_service is not None:
        return _memory_service

    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    preferences = PreferencesStore(JsonStorage(data_dir / "preferences.json"))
    configuration = ConfigurationStore(JsonStorage(data_dir / "configuration.json"))

    preferences.initialize()
    configuration.initialize()

    _memory_service = JarvisMemoryService(
        preferences=preferences,
        configuration=configuration,
    )
    return _memory_service


def get_preference(key: str, default=None):
    return get_memory_service().preferences.get(key, default)


def set_preference(key: str, value):
    return get_memory_service().preferences.set(key, value)


def get_configuration(key: str, default=None):
    return get_memory_service().configuration.get(key, default)


def set_configuration(key: str, value):
    return get_memory_service().configuration.set(key, value)
