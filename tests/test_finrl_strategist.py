from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.finrl_strategist import FinRLStrategist


class Monday(date):
    @classmethod
    def today(cls):
        return cls(2024, 1, 1)


def test_run_weekly_emits_signals():
    predictions = {"SPY": "buy", "AAPL": "sell"}
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer") as mock_producer_cls, \
         patch("agents.finrl_strategist.date", Monday), \
         patch.object(FinRLStrategist, "backtest_last_30d", return_value=predictions), \
         patch("agents.finrl_strategist.check_permission", return_value=True) as cp:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        strategist = FinRLStrategist(["SPY", "AAPL"], user_id="u1")
        result = strategist.run_weekly()
        cp.assert_called_once_with("u1", "trade", None)
        assert result == predictions
        assert mock_producer.send.call_count == 2
        assert mock_producer.flush.call_count == 2
        mock_producer.close.assert_called_once()
        calls = [
            (("BuySignal", {"ticker": "SPY", "user_id": "u1"}),),
            (("SellSignal", {"ticker": "AAPL", "user_id": "u1"}),),
        ]
        assert mock_producer.send.call_args_list == calls
