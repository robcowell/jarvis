"""J.A.R.V.I.S. Console package."""

import os


def _read_metadata(name: str, fallback: str) -> str:
    value = os.getenv(name, fallback)
    normalized = str(value).strip()
    return normalized or fallback


__version__ = _read_metadata("JARVIS_CONSOLE_VERSION", "0.1.0")
__build_datetime__ = _read_metadata(
    "JARVIS_CONSOLE_BUILD_DATETIME",
    _read_metadata("JARVIS_BUILD_DATETIME", "unknown"),
)
