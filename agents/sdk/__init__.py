from __future__ import annotations

import json
import logging
from typing import Any

from kafka import KafkaProducer
import requests

from .base import BaseAgent

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
    bootstrap_servers: str = "localhost:9092",
) -> None:
    """Emit a JSON event to a Kafka topic."""
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    logger.debug("Emitting event to %s: %s", topic, event)
    producer.send(topic, event)
    producer.flush()
    producer.close()


def ume_query(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a query to a UME endpoint and return the JSON response."""
    logger.debug("Querying UME at %s with payload %s", endpoint, payload)
    response = requests.post(endpoint, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


__all__ = ["emit_event", "ume_query", "BaseAgent"]
