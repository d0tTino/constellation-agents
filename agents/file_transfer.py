from __future__ import annotations

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def upload_file(url: str, path: Path) -> bool:
    """Upload a file to the given *url* using HTTP PUT.

    Returns ``True`` on success, ``False`` if the request fails for any
    reason.
    """
    try:
        with path.open("rb") as fh:
            response = requests.put(url, data=fh, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logger.error("File upload failed: %s", exc)
        return False


def download_file(url: str, dest: Path) -> bool:
    """Download *url* and write the content to ``dest``.

    Returns ``True`` when the download succeeds, ``False`` otherwise.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dest.write_bytes(response.content)
        return True
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logger.error("File download failed: %s", exc)
        return False


__all__ = ["upload_file", "download_file"]
