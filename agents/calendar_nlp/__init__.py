from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import requests

from ..sdk import BaseAgent, check_permission
from ..config import Config

logger = logging.getLogger(__name__)


class CalendarNLPAgent(BaseAgent):
    """Agent that converts natural language requests into calendar events."""

    topic_subscriptions = ["calendar.nl.request"]

    def __init__(
        self,
        llm: Callable[[str], dict[str, Any]],
        *,
        bootstrap_servers: str = "localhost:9092",
    ) -> None:
        super().__init__(
            self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id="calendar-nlp",
        )
        self.llm = llm

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        """Handle a natural language calendar request."""
        text = event.get("text")
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        if not text or not user_id or not group_id:
            logger.debug("Invalid event: %s", event)
            return
        if not check_permission(user_id, "calendar:create", group_id):
            logger.info("Permission denied for user %s", user_id)
            return
        result = self.llm(text)
        calendar_event = {
            "title": result.get("title"),
            "start_time": result.get("start_time"),
            "end_time": result.get("end_time"),
            "location": result.get("location"),
            "description": result.get("description"),
            "is_all_day": result.get("is_all_day"),
            "recurrence": result.get("recurrence"),
        }
        self.emit(
            "calendar.event.create_request",
            {"event": calendar_event},
            user_id=user_id,
            group_id=group_id,
        )
        logger.info("Emitted calendar event for user %s", user_id)


async def main(config: Config | None = None) -> None:
    """Run the :class:`CalendarNLPAgent` from configuration."""
    section = config.get("calendar_nlp", {}) if config else {}
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    endpoint = section.get("llm_endpoint", "http://localhost:8000/parse")

    def llm_call(text: str) -> dict[str, Any]:
        response = requests.post(endpoint, json={"text": text}, timeout=30)
        response.raise_for_status()
        return response.json()

    agent = CalendarNLPAgent(llm_call, bootstrap_servers=bootstrap)
    await asyncio.to_thread(agent.run)


__all__ = ["CalendarNLPAgent", "main"]
