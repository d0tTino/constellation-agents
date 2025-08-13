"""FinRL-based strategist with weekly scheduling and 30-day backtests."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from ..sdk import BaseAgent, check_permission
from ..config import Config

logger = logging.getLogger(__name__)


class FinRLStrategist(BaseAgent):
    """Run FinRL policies on a weekly schedule with 30-day backtests."""

    topic_subscriptions = ["finrl.schedule", "finrl.trigger"]

    def __init__(
        self,
        tickers: list[str],
        *,
        user_id: str,
        group_id: str | None = None,
        bootstrap_servers: str = "localhost:9092",
    ) -> None:
        super().__init__(
            self.topic_subscriptions, bootstrap_servers=bootstrap_servers, group_id="finrl-strategist"
        )
        self.tickers = tickers
        self.user_id = user_id
        self.group_id = group_id

    def _load_data(self, start: date, end: date):
        """Load historical data using FinRL's YahooDownloader."""
        try:
            from finrl.marketdata.yahoodownloader import YahooDownloader
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("FinRL is required for data loading") from exc
        downloader = YahooDownloader(
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            ticker_list=self.tickers,
        )
        return downloader.fetch_data()

    def backtest_last_30d(self, as_of: date | None = None) -> Any:
        """Back-test the strategy on the last 30 days of data."""
        as_of = as_of or date.today()
        start = as_of - timedelta(days=30)
        data = self._load_data(start, as_of)
        try:
            from finrl.agents.stablebaselines3.models import DRLAgent
            from finrl.meta.env_stock_trading.env_stocktrading import StockTradingEnv
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("FinRL full installation required") from exc
        env = StockTradingEnv(
            df=data,
            stock_dim=len(self.tickers),
            hmax=100,
            initial_amount=1_000_000,
            buy_cost_pct=0.001,
            sell_cost_pct=0.001,
            state_space=8 * len(self.tickers),
            tech_indicator_list=[],
            action_space=len(self.tickers),
            reward_scaling=1,
        )
        agent = DRLAgent(env=env)
        model = agent.get_model("ppo")
        trained = agent.train_model(model)
        return agent.DRL_prediction(model=trained, environment=env)

    def run_weekly(
        self, *, user_id: str | None = None, group_id: str | None = None
    ) -> Any | None:
        """Run ``backtest_last_30d`` every Monday and emit trade signals.

        ``user_id`` and ``group_id`` may be provided to override the defaults
        from the constructor, allowing callers to specify the user context at
        runtime. When omitted, the values from ``self.user_id`` and
        ``self.group_id`` are used.
        """
        today = date.today()
        if today.weekday() != 0:
            logger.info("FinRLStrategist: not Monday, skipping run")
            return None

        user_id = user_id or self.user_id
        group_id = self.group_id if group_id is None else group_id

        if not check_permission(user_id, "trade", group_id):
            logger.info("Permission denied for %s", user_id)
            return None
        logger.info("Running FinRLStrategist backtest for %s", today.isoformat())
        result = self.backtest_last_30d(today)
        if isinstance(result, dict):
            signals = {"buy": "BuySignal", "sell": "SellSignal"}
            for ticker, action in result.items():
                topic = signals.get(action)
                if topic:
                    payload = {"ticker": ticker}
                    self.emit(topic, payload, user_id=user_id, group_id=group_id)
        self.producer.close()
        return result

    def handle_event(self, event: dict[str, Any]) -> None:  # type: ignore[override]
        """Consume schedule or trigger events to run backtests.

        ``user_id`` and ``group_id`` provided in the event take precedence over
        the defaults supplied to the constructor, allowing callers to specify the
        user context dynamically. Missing values fall back to the constructor
        arguments.
        """
        self.run_weekly(
            user_id=event.get("user_id", self.user_id),
            group_id=event.get("group_id", self.group_id),
        )


async def main(config: Config | None = None) -> None:
    section = config.get("finrl_strategist", {}) if config else {}
    tickers = section.get("tickers", ["SPY"])
    bootstrap = section.get("bootstrap_servers", "localhost:9092")
    user_id = section.get("user_id", "finrl")
    group_id = section.get("group_id")
    strategist = FinRLStrategist(
        list(tickers),
        user_id=user_id,
        group_id=group_id,
        bootstrap_servers=bootstrap,
    )
    await asyncio.to_thread(strategist.run)


__all__ = ["FinRLStrategist", "main"]
