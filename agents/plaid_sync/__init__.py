from __future__ import annotations

import asyncio
import logging
from typing import Any

try:  # pragma: no cover - optional metrics dependency
    from prometheus_client import Counter
except ModuleNotFoundError:  # pragma: no cover - prometheus not installed
    class _NullMetric:  # pylint: disable=too-few-public-methods
        def labels(self, **kwargs):  # type: ignore[unused-argument]
            return self

        def inc(self, *args, **kwargs):  # type: ignore[unused-argument]
            pass

    def Counter(*args, **kwargs):  # type: ignore
        return _NullMetric()

from ..sdk import BaseAgent, check_permission
from ..config import Config

logger = logging.getLogger(__name__)

READ_ACTION = "plaid:transactions:read"
WRITE_ACTION = "plaid:transactions:write"

PERMISSION_DENIALS = Counter(
    "plaid_permission_denials_total",
    "Number of permission denials in Plaid sync",
    ["action"],
)


class PlaidClient:
    """Minimal Plaid client placeholder used for transaction sync."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def fetch_transactions(self, user_id: str) -> list[dict[str, Any]]:
        """Return a list of transactions for ``user_id``.

        This is a stub implementation. Real implementations should call the
        Plaid API and return transaction dictionaries.
        """

        return []


class PlaidSync(BaseAgent):
    """Agent that syncs transactions from Plaid and emits events."""

    topic_subscriptions = ["plaid.transactions.sync"]

    def __init__(
        self,
        plaid_client: PlaidClient,
        *,
        bootstrap_servers: str = "localhost:9092",
    ) -> None:
        super().__init__(
            self.topic_subscriptions,
            bootstrap_servers=bootstrap_servers,
            group_id="plaid-sync",
        )
        self.plaid = plaid_client
        self.bootstrap_servers = bootstrap_servers

    def sync(self, user_id: str, group_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch transactions and emit ``plaid.transaction.synced`` events."""

        if not check_permission(user_id, READ_ACTION, group_id):
            logger.info("Read permission denied for %s", user_id)
            PERMISSION_DENIALS.labels(action="read").inc()
            return []
        if not check_permission(user_id, WRITE_ACTION, group_id):
            logger.info("Write permission denied for %s", user_id)
            PERMISSION_DENIALS.labels(action="write").inc()
            return []
        try:
            transactions = self.plaid.fetch_transactions(user_id)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to fetch transactions for %s", user_id)
            return []
        for tx in transactions:
            payload = tx.copy()
            self.emit(
                "plaid.transaction.synced",
                payload,
                user_id=user_id,
                group_id=group_id,
            )
        return transactions

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        if not user_id:
            logger.debug("Event missing user_id: %s", event)
            return
        self.sync(user_id, group_id)


async def main(config: Config | None = None) -> None:
    """Entry point for running ``PlaidSync`` asynchronously."""

    section = config.get("plaid_sync", {}) if config else {}
    client_id = section.get("client_id", "")
    client_secret = section.get("client_secret", "")
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    plaid_client = PlaidClient(client_id, client_secret)
    agent = PlaidSync(plaid_client, bootstrap_servers=bootstrap)
    await asyncio.to_thread(agent.run)


__all__ = [
    "PlaidClient",
    "PlaidSync",
    "main",
    "READ_ACTION",
    "WRITE_ACTION",
    "PERMISSION_DENIALS",
]
