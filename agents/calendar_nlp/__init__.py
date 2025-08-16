from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from ..config import Config
from ..sdk import BaseAgent, check_permission


SUPPORTED_RECURRENCES = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}

logger = logging.getLogger(__name__)


class CalendarNLPAgent(BaseAgent):
    """Agent that converts natural language requests into calendar events."""

    topic_subscriptions = ["calendar.nl.request"]

    def __init__(
        self,
        llm: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        bootstrap_servers: str = "localhost:9092",
        default_timezone: str | None = None,
    ) -> None:
        super().__init__(
            self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id="calendar-nlp",
        )
        self.llm = llm
        self.default_timezone = default_timezone

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
        if not timezone:
            timezone = self.default_timezone
        if timezone:
            try:
                now = datetime.now(ZoneInfo(timezone))
            except ZoneInfoNotFoundError:
                logger.exception("Failed to find timezone %s", timezone)
                return
        else:
            timezone = "UTC"
            now = datetime.now(ZoneInfo("UTC"))
        payload = {
            "text": text,
            "current_datetime": now.isoformat(),
            "timezone": timezone,
        }
        try:
            result = self.llm(payload)
        except requests.RequestException:
            logger.exception("LLM request failed")
            return
        title = result.get("title")
        start_time = result.get("start_time")
        end_time = result.get("end_time")
        if not title or not start_time or not end_time:
            logger.warning("Missing required fields in LLM result: %s", result)
            return
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
        except ValueError:
            logger.warning("Invalid datetime format in LLM result: %s", result)
            return
        if (
            start_dt.tzinfo is None
            or start_dt.tzinfo.utcoffset(start_dt) is None
            or end_dt.tzinfo is None
            or end_dt.tzinfo.utcoffset(end_dt) is None
        ):
            logger.warning("Naive datetime in LLM result: %s", result)
            return
        if end_dt <= start_dt:
            logger.warning(
                "End time %s is not after start time %s", end_dt, start_dt
            )
            return
        recurrence = result.get("recurrence")
        normalized_recurrence: str | None = None
        if recurrence:
            normalized_recurrence = str(recurrence).strip().upper()
            if normalized_recurrence not in SUPPORTED_RECURRENCES:
                logger.warning(
                    "Unsupported recurrence format in LLM result: %s", recurrence
                )
                return
        calendar_event = {
            "title": title,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "location": result.get("location"),
            "description": result.get("description"),
            "is_all_day": result.get("is_all_day"),
            "recurrence": normalized_recurrence,
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
    if config is None:
        cfg_path = os.getenv("CONFIG_PATH", "config.toml")
        if Path(cfg_path).exists():
            config = Config(cfg_path)

    section = config.get("calendar_nlp", {}) if config else {}
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    endpoint = section.get("llm_endpoint", "http://localhost:8000/parse")
    default_timezone = config.get("default_timezone") if config else None

    def llm_call(payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    agent = CalendarNLPAgent(
        llm_call,
        bootstrap_servers=bootstrap,
        default_timezone=default_timezone,
    )
    await asyncio.to_thread(agent.run)


__all__ = ["CalendarNLPAgent", "main"]
