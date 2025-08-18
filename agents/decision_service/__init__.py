from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..sdk import BaseAgent, check_permission
from ..config import Config

logger = logging.getLogger(__name__)


class DecisionService(BaseAgent):
    """Agent that handles finance decision requests."""

    topic_subscriptions = ["finance.decision.request"]

    def __init__(self, *, bootstrap_servers: str = "localhost:9092") -> None:
        super().__init__(
            self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id="decision-service",
        )

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        analysis_id = event.get("analysis_id")
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        if not analysis_id or not user_id:
            logger.debug("Missing analysis_id or user_id: %s", event)
            return
        if not check_permission(user_id, "analysis:decision", group_id):
            logger.info("Permission denied for user %s", user_id)
            return
        decision = event.get("decision")
        payload: dict[str, Any] = {"analysis_id": analysis_id}
        if decision is not None:
            payload["decision"] = decision
        self.emit(
            "finance.decision.result",
            payload,
            user_id=user_id,
            group_id=group_id,
        )


async def main(config: Config | None = None) -> None:
    """Run the decision service from configuration."""
    section = config.get("decision_service", {}) if config else {}
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    agent = DecisionService(bootstrap_servers=bootstrap)
    await asyncio.to_thread(agent.run)


__all__ = ["DecisionService", "main"]
