from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests

from ..sdk import BaseAgent

logger = logging.getLogger(__name__)


class CalendarSync(BaseAgent):
    """Synchronize Cal.com webhooks with UME appointment nodes."""

    def __init__(self, cal_endpoint: str, *, bootstrap_servers: str = "localhost:9092") -> None:
        super().__init__(
            "ume.nodes.appointment",
            bootstrap_servers=bootstrap_servers,
            group_id="calendar-sync",
        )
        self.cal_endpoint = cal_endpoint

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        """Handle appointment updates from UME."""
        appointment_id = event.get("id")
        start = event.get("time")
        if appointment_id is None or start is None:
            logger.debug("Invalid UME event: %s", event)
            return
        try:
            requests.post(
                self.cal_endpoint,
                json={"id": appointment_id, "time": start},
                timeout=10,
            )
            logger.info("Synced appointment %s to Cal.com", appointment_id)
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Failed to sync to Cal.com: %s", exc)

    def handle_cal_event(self, event: dict[str, Any]) -> None:
        """Process a webhook payload from Cal.com."""
        appointment_id = event.get("id")
        start = event.get("time")
        if appointment_id is None or start is None:
            logger.debug("Invalid Cal.com event: %s", event)
            return
        self.emit(
            "ume.events.task.reschedule",
            {"id": appointment_id, "time": start},
        )
        logger.info("Emitted TaskReschedule for %s", appointment_id)


async def main() -> None:
    """Entry point for running ``CalendarSync`` asynchronously."""
    agent = CalendarSync(cal_endpoint="http://localhost/api/cal")
    await asyncio.to_thread(agent.run)


__all__ = ["CalendarSync", "main"]
