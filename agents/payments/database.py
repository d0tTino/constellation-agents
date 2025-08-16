"""Simple in-memory database interface for payment settings."""

from __future__ import annotations

from typing import Any, Dict

# In a real application this would interface with an actual database. For the
# purposes of these agents and tests we store settings in a module-level
# dictionary that can be patched in tests.
_SETTINGS: Dict[str, Any] = {
    "payment_gateways": {
        "stripe": {
            "api_key": "",  # Placeholder to be overridden in tests
        }
    }
}


def get_setting(name: str) -> Any:
    """Return a setting by *name* from the in-memory database."""
    return _SETTINGS.get(name)
