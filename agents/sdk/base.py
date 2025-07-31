from __future__ import annotations

import json
import logging
from typing import Any

from kafka import KafkaConsumer, KafkaProducer

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base agent that subscribes to a Kafka topic and dispatches events."""

    def __init__(
        self,
        topic: str,
        *,
        bootstrap_servers: str = "localhost:9092",
        group_id: str | None = None,
    ) -> None:
        self.topic = topic
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

    def emit(self, topic: str, event: dict[str, Any]) -> None:
        """Emit an event to a Kafka topic."""
        logger.debug("Emitting event to %s: %s", topic, event)
        self.producer.send(topic, event)
        self.producer.flush()

    def dispatch(self, event: dict[str, Any]) -> None:
        """Dispatch an event to the handler."""
        logger.debug("Dispatching event: %s", event)
        self.handle_event(event)

    def handle_event(self, event: dict[str, Any]) -> None:
        """Handle an event from the subscribed topic. Override in subclasses."""
        raise NotImplementedError

    def run(self) -> None:
        """Start consuming events and dispatching them."""
        logger.info("Starting agent on topic %s", self.topic)
        for message in self.consumer:
            logger.debug("Received message: %s", message.value)
            self.dispatch(message.value)
