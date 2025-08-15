from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests
import time

from ..sdk import BaseAgent, check_permission
from ..config import Config

logger = logging.getLogger(__name__)


class ExplainabilityAgent(BaseAgent):
    """Agent that provides explanations for finance analyses."""

    topic_subscriptions = ["finance.explain.request"]

    def __init__(
        self,
        engine_url: str,
        *,
        bootstrap_servers: str = "localhost:9092",
    ) -> None:
        super().__init__(
            self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id="explainability-agent",
        )
        self.engine_url = engine_url.rstrip("/")

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        analysis_id = event.get("analysis_id")
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        if not analysis_id or not user_id:
            logger.debug("Missing analysis_id or user_id: %s", event)
            return
        if not check_permission(user_id, "analysis:read", group_id):
            logger.info("Permission denied for user %s", user_id)
            return
        params = {"user_id": user_id}
        if group_id:
            params["group_id"] = group_id
        for attempt in range(3):
            try:
                resp = requests.get(
                    f"{self.engine_url}/analysis/{analysis_id}/actions",
                    params=params,
                    timeout=10,
                )
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt < 2:  # retry with exponential backoff
                    time.sleep(2**attempt)
                    continue
                logger.error("Failed to fetch actions: %s", exc)
                return
        try:
            data = resp.json()
        except ValueError as exc:
            logger.error("Failed to parse JSON: %s", exc)
            return
        actions = data.get("actions", [])
        explanations = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            name = action.get("name")
            if not isinstance(name, str):
                continue
            pros_items = action.get("pros")
            if not isinstance(pros_items, list):
                pros_items = []
            cons_items = action.get("cons")
            if not isinstance(cons_items, list):
                cons_items = []
            pros = "; ".join(str(p) for p in pros_items if isinstance(p, str))
            cons = "; ".join(str(c) for c in cons_items if isinstance(c, str))
            explanations.append({"action": name, "pros": pros, "cons": cons})
        # Verify write permissions before emitting the result
        if not check_permission(user_id, "analysis:write", group_id):
            logger.info("Write permission denied for user %s", user_id)
            return
        payload = {"analysis_id": analysis_id, "explanations": explanations}
        self.emit(
            "finance.explain.result",
            payload,
            user_id=user_id,
            group_id=group_id,
        )


async def main(config: Config | None = None) -> None:
    """Asynchronous entrypoint for the explainability agent."""
    section = config.get("explainability_agent", {}) if config else {}
    engine_url = section.get("engine_url", "http://localhost:8000")
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    agent = ExplainabilityAgent(engine_url, bootstrap_servers=bootstrap)
    await asyncio.to_thread(agent.run)


__all__ = ["ExplainabilityAgent", "main"]
