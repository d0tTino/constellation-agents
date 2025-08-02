from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import requests

from ..sdk import BaseAgent
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
