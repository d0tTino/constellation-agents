from __future__ import annotations

import json
import logging
import time
from typing import Any

from prometheus_client import Counter, Histogram, start_http_server
from kafka import KafkaConsumer, KafkaProducer

# Track which metric ports have been initialized to avoid conflicts when
# multiple agent instances are created. Using a set allows metrics servers to
# run on different ports concurrently.
_METRICS_STARTED: set[int] = set()

logger = logging.getLogger(__name__)

MESSAGE_COUNTER = Counter(
    "agent_messages_total",
    "Total number of processed messages",
    ["agent"],
)
PROCESSING_TIME = Histogram(
    "agent_processing_seconds",
    "Time spent processing a message",
    ["agent"],
)


class BaseAgent:
    """Base agent that subscribes to a Kafka topic and dispatches events."""

    def __init__(
        self,
        topic_subscriptions: str | list[str] | tuple[str, ...],
        *,
        bootstrap_servers: str = "localhost:9092",
        group_id: str | None = None,
        metrics_port: int | None = 8000,
    ) -> None:
        if isinstance(topic_subscriptions, str):
            self.topic_subscriptions = [topic_subscriptions]
        else:
            self.topic_subscriptions = list(topic_subscriptions)
        # Keep the legacy ``topic`` attribute for backward compatibility.
        self.topic = self.topic_subscriptions[0]
        self.consumer = KafkaConsumer(
            *self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        self._labels = {"agent": self.__class__.__name__}
        global _METRICS_STARTED
        if metrics_port is not None and metrics_port not in _METRICS_STARTED:
            start_http_server(metrics_port)
            _METRICS_STARTED.add(metrics_port)

    def emit(
        self,
        topic: str,
        event: dict[str, Any],
        *,
        user_id: str,
        group_id: str | None = None,
    ) -> None:
        """Emit an event to a Kafka topic.

        The ``user_id`` is required; a ``ValueError`` is raised when it is
        missing or falsy. ``group_id`` is accepted for future use.
        """
        if not user_id:
            raise ValueError("user_id is required")

        if group_id is not None:  # pragma: no cover - reserved for future use
            logger.debug("group_id provided: %s", group_id)

        logger.debug("Emitting event to %s for user %s: %s", topic, user_id, event)
        self.producer.send(topic, event)
        self.producer.flush()

    def dispatch(self, event: dict[str, Any]) -> None:
        """Dispatch an event to the handler."""
        logger.debug("Dispatching event: %s", event)
        start = time.monotonic()
        try:
            self.handle_event(event)
        except Exception:  # noqa: BLE001 - broad exception is intentional
            logger.exception("Error handling event: %s", event)
        finally:
            duration = time.monotonic() - start
            MESSAGE_COUNTER.labels(**self._labels).inc()
            PROCESSING_TIME.labels(**self._labels).observe(duration)

    def handle_event(self, event: dict[str, Any]) -> None:
        """Handle an event from the subscribed topic. Override in subclasses."""
        raise NotImplementedError

    def run(self) -> None:
        """Start consuming events and dispatching them."""
        topics = ", ".join(self.topic_subscriptions)
        logger.info("Starting agent on topics %s", topics)
        for message in self.consumer:
            logger.debug("Received message: %s", message.value)
            self.dispatch(message.value)
