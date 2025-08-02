from __future__ import annotations

import asyncio
import logging
from math import sqrt
from typing import Any, Sequence

from ..sdk import BaseAgent, ume_query, check_permission
from ..config import Config

logger = logging.getLogger(__name__)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must be of equal length")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EurekaWatcher(BaseAgent):
    """Watch IdeaSeed events and suggest tasks for similar docs."""

    topic_subscriptions = ["ume.events.ideaseed"]

    def __init__(
        self,
        docs_endpoint: str,
        *,
        user_id: str,
        group_id: str | None = None,
        bootstrap_servers: str = "localhost:9092",
    ) -> None:
        super().__init__(
            self.topic_subscriptions, bootstrap_servers=bootstrap_servers, group_id="eureka-watcher"
        )
        self.docs_endpoint = docs_endpoint
        self.user_id = user_id
        self.group_id = group_id

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        vector = event.get("vector")
        if not isinstance(vector, Sequence):
            logger.debug("Event missing vector: %s", event)
            return
        if not check_permission(self.user_id, "suggest", self.group_id):
            logger.info("Permission denied for %s", self.user_id)
            return
        try:
            docs = ume_query(self.docs_endpoint, {"vector": vector}).get("docs", [])
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("UME query failed: %s", exc)
            return
        for doc in docs:
            doc_vec = doc.get("vector")
            if not isinstance(doc_vec, Sequence):
                continue
            sim = cosine_similarity([float(x) for x in vector], [float(x) for x in doc_vec])
            logger.debug("Similarity with doc %s: %.2f", doc.get("id"), sim)
            if sim > 0.75:
                payload = {
                    "idea": event.get("id"),
                    "doc": doc.get("id"),
                    "similarity": sim,
                    "user_id": self.user_id,
                }
                if self.group_id is not None:
                    payload["group_id"] = self.group_id
                self.emit(
                    "ume.events.suggested_task",
                    payload,
                    user_id=self.user_id,
                    group_id=self.group_id,
                )


async def main(config: Config | None = None) -> None:
    section = config.get("eureka_watcher", {}) if config else {}
    endpoint = section.get("docs_endpoint", "http://localhost:8000/docs")
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    user_id = section.get("user_id", "eureka")
    group_id = section.get("group_id")
    watcher = EurekaWatcher(
        endpoint,
        user_id=user_id,
        group_id=group_id,
        bootstrap_servers=bootstrap,
    )
    await asyncio.to_thread(watcher.run)


__all__ = ["EurekaWatcher", "cosine_similarity", "main"]
