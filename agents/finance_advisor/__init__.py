from __future__ import annotations

import asyncio
import logging
from typing import Sequence
import math

from ..sdk import BaseAgent
from ..config import Config

logger = logging.getLogger(__name__)


def percentile(data: Sequence[float], p: float) -> float:
    """Return the ``p``th percentile of ``data`` (``p`` between 0 and 100)."""
    if not data:
        raise ValueError("data must not be empty")
    if not 0 <= p <= 100:
        raise ValueError("percentile must be between 0 and 100")
    s = sorted(data)
    k = (len(s) - 1) * (p / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def percentile_zscore(history: Sequence[float], value: float) -> float:
    """Compute the percentile z-score for ``value`` given ``history``."""
    if not history:
        return 0.0
    p50 = percentile(history, 50)
    p90 = percentile(history, 90)
    p10 = percentile(history, 10)
    scale = p90 - p10
    if scale == 0:
        return 0.0
    return (value - p50) / scale


class FinanceAdvisor(BaseAgent):
    """Agent that flags anomalous transactions using percentile z-scores."""

    def __init__(self, *, bootstrap_servers: str = "localhost:9092") -> None:
        super().__init__(
            "ume.events.transaction.created",
            bootstrap_servers=bootstrap_servers,
            group_id="finance-advisor",
        )
        self.amounts: list[float] = []

    def handle_event(self, event: dict[str, float]) -> None:  # type: ignore[override]
        amount = event.get("amount")
        if amount is None:
            logger.debug("Received event without amount: %s", event)
            return
        self.amounts.append(float(amount))
        score = percentile_zscore(self.amounts, float(amount))
        logger.info("Transaction %s has z-score %.2f", amount, score)
        if abs(score) > 3:
            self.emit(
                "ume.events.transaction.anomaly",
                {"amount": amount, "z": score},
            )


async def main(config: Config | None = None) -> None:
    """Asynchronous entrypoint for the finance advisor agent."""
    section = config.get("finance_advisor", {}) if config else {}
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    agent = FinanceAdvisor(bootstrap_servers=bootstrap)
    await asyncio.to_thread(agent.run)


__all__ = ["FinanceAdvisor", "percentile", "percentile_zscore", "main"]
