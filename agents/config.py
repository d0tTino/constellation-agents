from __future__ import annotations

import signal
import tomllib
from pathlib import Path
from typing import Any


class Config:
    """Simple TOML configuration parser with reload on SIGHUP."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        self.load()
        signal.signal(signal.SIGHUP, self._handle_sighup)

    def load(self) -> None:
        """Load configuration from ``self.path``."""
        with self.path.open("rb") as f:
            self.data = tomllib.load(f)

    def reload(self) -> None:
        """Reload configuration from disk."""
        self.load()

    def _handle_sighup(self, signum: int, frame: object) -> None:  # pragma: no cover - signal handler
        self.reload()

    def get(self, key: str, default: Any | None = None) -> Any:
        """Retrieve a value from the configuration."""
        return self.data.get(key, default)
