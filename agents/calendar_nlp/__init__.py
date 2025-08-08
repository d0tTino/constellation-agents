from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from ..config import Config
from ..sdk import BaseAgent, check_permission

logger = logging.getLogger(__name__)


class CalendarNLPAgent(BaseAgent):
    """Agent that converts natural language requests into calendar events."""

    topic_subscriptions = ["calendar.nl.request"]

    def __init__(
        self,
        llm: Callable[[dict[str, Any]], dict[str, Any]],
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
        timezone = event.get("timezone")
        if not text or not user_id:

            logger.debug("Invalid event: %s", event)
            return
        if not check_permission(user_id, "calendar:create", group_id):
            logger.info("Permission denied for user %s", user_id)
            return
        if timezone:
            try:
                now = datetime.now(ZoneInfo(timezone))
            except ZoneInfoNotFoundError:
                logger.exception("Failed to find timezone %s", timezone)
                return
        else:
            now = datetime.utcnow()
        payload = {
            "text": text,
            "current_datetime": now.isoformat(),
            "timezone": timezone,
        }
        result = self.llm(payload)
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

    def llm_call(payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    agent = CalendarNLPAgent(llm_call, bootstrap_servers=bootstrap)
    await asyncio.to_thread(agent.run)


__all__ = ["CalendarNLPAgent", "main"]
