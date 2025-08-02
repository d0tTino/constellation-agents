from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config import Config
from ..sdk import emit_event, check_permission

logger = logging.getLogger(__name__)


class CryptoBot:
    """Simple wrapper around the Freqtrade engine."""

    def __init__(
        self, config: Config, *, user_id: str, group_id: str | None = None
    ) -> None:
        self.config = config
        self.user_id = user_id
        self.group_id = group_id
        self.strategy: dict[str, Any] = {}
        self.exchange: Any | None = None
        self.engine: Any | None = None

    def load_strategy(self) -> None:
        """Load strategy YAML defined in the ``crypto_bot.strategy`` config key."""
        import yaml
        path = self.config.get("crypto_bot", {}).get("strategy")
        if not path:
            raise ValueError("Strategy path not configured")
        with Path(path).open("r") as f:
            self.strategy = yaml.safe_load(f)
        logger.info("Loaded strategy from %s", path)

    def connect_exchange(self) -> None:
        """Connect to the exchange defined in the strategy."""
        import ccxt
        name = self.strategy.get("exchange")
        if not name:
            raise ValueError("Strategy missing 'exchange' field")
        name = name.lower()
        if name == "binance":
            cls = ccxt.binance
        elif name == "kraken":
            cls = ccxt.kraken
        else:
            raise ValueError(f"Unsupported exchange: {name}")
        self.exchange = cls({"enableRateLimit": True})
        logger.info("Connected to %s", name)

    def init_engine(self) -> None:
        """Initialize the Freqtrade engine."""
        try:
            from freqtrade.worker import Worker  # type: ignore
            from freqtrade.configuration import Configuration  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Freqtrade is not installed") from exc

        ft_config = Configuration(self.config.data, None).get_config()
        self.engine = Worker({}, config=ft_config)
        logger.info("Freqtrade engine initialized")

    def run(self) -> None:
        """Run the bot."""
        if not check_permission(self.user_id, "trade", self.group_id):
            logger.info("Permission denied for %s", self.user_id)
            return

        self.load_strategy()
        self.connect_exchange()
        self.init_engine()
        if not self.engine:
            raise RuntimeError("Engine failed to initialize")

        # Execute the Freqtrade engine. ``Worker`` may expose ``run`` or
        # ``start`` depending on the installed version. Call whichever exists.
        try:
            if hasattr(self.engine, "run"):
                self.engine.run()
            elif hasattr(self.engine, "start"):
                self.engine.start()

            # After execution publish basic metrics.
            positions = getattr(self.engine, "positions", [])
            profit = getattr(self.engine, "profit", 0.0)
            payload = {"positions": positions, "profit": profit}
            kwargs: dict[str, Any] = {"user_id": self.user_id}
            if self.group_id is not None:
                kwargs["group_id"] = self.group_id
            emit_event("TradeSummary", payload, **kwargs)
        finally:
            # Ensure the engine shuts down cleanly even if execution fails.
            shutdown = getattr(self.engine, "stop", None) or getattr(
                self.engine, "close", None
            )
            if shutdown:
                shutdown()
