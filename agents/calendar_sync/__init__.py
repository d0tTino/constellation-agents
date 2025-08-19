from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import requests
import time

from ..sdk import BaseAgent, check_permission
from ..config import Config

logger = logging.getLogger(__name__)


class CalendarSync(BaseAgent):
    """Synchronize Cal.com webhooks with UME appointment nodes."""

    topic_subscriptions = ["ume.nodes.appointment"]

    def __init__(self, cal_endpoint: str, *, bootstrap_servers: str = "localhost:9092") -> None:
        super().__init__(
            self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id="calendar-sync",
        )
        self.cal_endpoint = cal_endpoint
        self._webhook_server: ThreadingHTTPServer | None = None
        self._webhook_thread: threading.Thread | None = None

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        """Handle appointment updates from UME."""
        appointment_id = event.get("id")
        start = event.get("time")
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        if appointment_id is None or start is None or not user_id:
            logger.debug("Invalid UME event: %s", event)
            return
        if not check_permission(user_id, "calendar:read", group_id):
            logger.info("Read permission denied for %s", user_id)
            return
        payload = {"id": appointment_id, "time": start, "user_id": user_id}
        if group_id is not None:
            payload["group_id"] = group_id
        backoff = 1
        for attempt in range(3):
            try:
                response = requests.post(
                    self.cal_endpoint, json=payload, timeout=10
                )
            except requests.RequestException as exc:  # pragma: no cover - network errors
                logger.error("Failed to sync to Cal.com: %s", exc)
                return
            if 200 <= response.status_code < 300:
                logger.info("Synced appointment %s to Cal.com", appointment_id)
                return
            logger.error(
                "Cal.com sync failed (status %s) for appointment %s",
                response.status_code,
                appointment_id,
            )
            if attempt < 2:
                time.sleep(backoff)
                backoff *= 2

    def handle_cal_event(self, event: dict[str, Any]) -> None:
        """Process a webhook payload from Cal.com."""
        appointment_id = event.get("id")
        start = event.get("time")
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        if appointment_id is None or start is None or not user_id:
            logger.debug("Invalid Cal.com event: %s", event)
            return
        if not check_permission(user_id, "calendar:write", group_id):
            logger.info("Write permission denied for %s", user_id)
            return
        payload = {"id": appointment_id, "time": start, "user_id": user_id}
        if group_id is not None:
            payload["group_id"] = group_id
        self.emit(
            "ume.events.task.reschedule",
            payload,
            user_id=user_id,
            group_id=group_id,
        )
        logger.info("Emitted TaskReschedule for %s", appointment_id)

    def start_webhook_server(self, host: str = "0.0.0.0", port: int = 8001) -> None:
        """Start an HTTP server to receive Cal.com webhooks."""

        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler: BaseHTTPRequestHandler) -> None:  # type: ignore[override]
                length = int(handler.headers.get("Content-Length", "0"))
                data = handler.rfile.read(length)
                try:
                    payload = json.loads(data.decode("utf-8"))
                except Exception:  # pragma: no cover - malformed body
                    handler.send_response(400)
                    handler.end_headers()
                    return
                self.handle_cal_event(payload)
                handler.send_response(200)
                handler.end_headers()

            def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - quiet
                return

        self._webhook_server = ThreadingHTTPServer((host, port), Handler)
        self._webhook_thread = threading.Thread(
            target=self._webhook_server.serve_forever, daemon=True
        )
        self._webhook_thread.start()

    def stop_webhook_server(self) -> None:
        """Stop the webhook HTTP server if running."""
        if self._webhook_server:
            self._webhook_server.shutdown()
            self._webhook_server.server_close()
        if self._webhook_thread:
            self._webhook_thread.join()


async def main(config: Config | None = None) -> None:
    """Entry point for running ``CalendarSync`` asynchronously."""
    section = config.get("calendar_sync", {}) if config else {}
    endpoint = section.get("cal_endpoint", "http://localhost/api/cal")
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    agent = CalendarSync(endpoint, bootstrap_servers=bootstrap)
    agent.start_webhook_server()
    try:
        await asyncio.to_thread(agent.run)
    finally:
        agent.stop_webhook_server()


__all__ = ["CalendarSync", "main"]
