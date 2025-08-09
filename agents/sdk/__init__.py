from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

try:  # pragma: no cover - optional dependency
    from kafka import KafkaProducer  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - kafka library not installed
    KafkaProducer = None  # type: ignore[assignment]

from .base import BaseAgent, _inject_identifiers

logging.basicConfig(
    level=logging.INFO,
    format=(
        "{\"time\":\"%(asctime)s\",\"level\":\"%(levelname)s\"," \
        "\"name\":\"%(name)s\",\"message\":\"%(message)s\"}"
    ),
)

logger = logging.getLogger(__name__)


def emit_event(
    topic: str,
    event: dict[str, Any],
    *,
    user_id: str,
    group_id: str | None = None,
    bootstrap_servers: str = "localhost:9092",
) -> None:
    """Emit a JSON event to a Kafka topic.

    ``user_id`` is required and will be injected into the event payload. A
    ``ValueError`` is raised when it is missing or falsy. ``group_id`` is
    optional and, if provided, included in the payload.
    """
    payload = _inject_identifiers(event, user_id=user_id, group_id=group_id)
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    logger.debug("Emitting event to %s: %s", topic, payload)
    producer.send(topic, payload)
    producer.flush()
    producer.close()


def ume_query(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a query to a UME endpoint and return the JSON response.

    When the ``OPA_SIDECAR_URL`` environment variable is defined, the request
    is sent to that URL with the original endpoint and payload nested in the
    JSON body. Otherwise the request is sent directly to ``endpoint``.
    """

    logger.debug("Querying UME at %s with payload %s", endpoint, payload)

    sidecar_url = os.getenv("OPA_SIDECAR_URL")
    if sidecar_url:
        logger.debug("Routing request through OPA sidecar %s", sidecar_url)
        url = sidecar_url
        data = {"url": endpoint, "payload": payload}
    else:
        url = endpoint
        data = payload

    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("UME query failed: %s", exc)
        return False


def check_permission(user_id: str, action: str, group_id: str | None = None) -> bool:
    """Return whether a user is allowed to perform an action.

    The permission service is queried via :func:`ume_query`.  The endpoint is
    taken from the ``UME_PERMISSION_ENDPOINT`` environment variable and
    defaults to ``"http://localhost:8000/permissions/check"``.  When the
    ``OPA_SIDECAR_URL`` variable is set, requests are routed through that
    sidecar as described in :func:`ume_query`.
    """

    endpoint = os.getenv(
        "UME_PERMISSION_ENDPOINT", "http://localhost:8000/permissions/check"
    )
    payload: dict[str, Any] = {"user_id": user_id, "action": action}
    if group_id is not None:
        payload["group_id"] = group_id
    try:
        response = ume_query(endpoint, payload)
    except requests.RequestException as exc:  # pragma: no cover - ume_query handles
        logger.error("Permission check request failed: %s", exc)
        return False
    if not response:
        logger.error("Permission check failed due to network error")
        return False
    return bool(response.get("allow"))


__all__ = ["emit_event", "ume_query", "check_permission", "BaseAgent"]
