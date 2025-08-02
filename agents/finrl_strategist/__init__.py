"""FinRL-based strategist with weekly scheduling and 30-day backtests."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from ..sdk import emit_event
from ..config import Config

logger = logging.getLogger(__name__)


class FinRLStrategist:
    """Run FinRL policies on a weekly schedule with 30-day backtests."""

    def __init__(self, tickers: list[str]):
        self.tickers = tickers

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

    def run_weekly(self) -> Any | None:
        """Run ``backtest_last_30d`` every Monday and emit trade signals."""
        today = date.today()
        if today.weekday() != 0:
            logger.info("FinRLStrategist: not Monday, skipping run")
            return None
        logger.info("Running FinRLStrategist backtest for %s", today.isoformat())
        result = self.backtest_last_30d(today)
        if isinstance(result, dict):
            signals = {"buy": "BuySignal", "sell": "SellSignal"}
            for ticker, action in result.items():
                topic = signals.get(action)
                if topic:
                    emit_event(topic, {"ticker": ticker})
        return result


async def main(config: Config | None = None) -> None:
    section = config.get("finrl_strategist", {}) if config else {}
    tickers = section.get("tickers", ["SPY"])
    strategist = FinRLStrategist(list(tickers))
    await asyncio.to_thread(strategist.run_weekly)


__all__ = ["FinRLStrategist", "main"]
