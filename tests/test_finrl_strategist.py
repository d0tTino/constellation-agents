from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.finrl_strategist import FinRLStrategist


class Monday(date):
    @classmethod
    def today(cls):
        return cls(2024, 1, 1)


class Tuesday(date):
    @classmethod
    def today(cls):
        return cls(2024, 1, 2)


def test_run_weekly_emits_signals():
    predictions = {"SPY": "buy", "AAPL": "sell"}
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer") as mock_producer_cls, \
         patch("agents.finrl_strategist.date", Monday), \
         patch.object(FinRLStrategist, "backtest_last_30d", return_value=predictions), \
         patch("agents.finrl_strategist.check_permission", return_value=True) as cp, \
         patch.object(FinRLStrategist, "emit", wraps=FinRLStrategist.emit, autospec=True) as mock_emit:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        strategist = FinRLStrategist(["SPY", "AAPL"], user_id="u1")
        result = strategist.run_weekly()
        cp.assert_called_once_with("u1", "trade", None)
        assert result == predictions
        assert mock_producer.send.call_count == 2
        assert mock_producer.flush.call_count == 2
        mock_producer.close.assert_called_once()
        expected_emit_calls = [
            call(strategist, "BuySignal", {"ticker": "SPY"}, user_id="u1", group_id=None),
            call(strategist, "SellSignal", {"ticker": "AAPL"}, user_id="u1", group_id=None),
        ]
        assert mock_emit.call_args_list == expected_emit_calls
        send_calls = [
            call("BuySignal", {"ticker": "SPY", "user_id": "u1"}),
            call("SellSignal", {"ticker": "AAPL", "user_id": "u1"}),
        ]
        assert mock_producer.send.call_args_list == send_calls


def test_run_weekly_emits_signals_with_group_id():
    predictions = {"SPY": "buy", "AAPL": "sell"}
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer") as mock_producer_cls, \
         patch("agents.finrl_strategist.date", Monday), \
         patch.object(FinRLStrategist, "backtest_last_30d", return_value=predictions), \
         patch("agents.finrl_strategist.check_permission", return_value=True) as cp, \
         patch.object(FinRLStrategist, "emit", wraps=FinRLStrategist.emit, autospec=True) as mock_emit:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        strategist = FinRLStrategist(["SPY", "AAPL"], user_id="u1", group_id="g1")
        result = strategist.run_weekly()
        cp.assert_called_once_with("u1", "trade", "g1")
        assert result == predictions
        assert mock_producer.send.call_count == 2
        assert mock_producer.flush.call_count == 2
        mock_producer.close.assert_called_once()
        expected_emit_calls = [
            call(strategist, "BuySignal", {"ticker": "SPY"}, user_id="u1", group_id="g1"),
            call(strategist, "SellSignal", {"ticker": "AAPL"}, user_id="u1", group_id="g1"),
        ]
        assert mock_emit.call_args_list == expected_emit_calls
        send_calls = [
            call("BuySignal", {"ticker": "SPY", "user_id": "u1", "group_id": "g1"}),
            call("SellSignal", {"ticker": "AAPL", "user_id": "u1", "group_id": "g1"}),
        ]
        assert mock_producer.send.call_args_list == send_calls


def test_run_weekly_no_permission_emits_nothing():
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer") as mock_producer_cls, \
         patch("agents.finrl_strategist.date", Monday), \
         patch("agents.finrl_strategist.check_permission", return_value=False), \
         patch.object(FinRLStrategist, "backtest_last_30d") as backtest, \
         patch.object(FinRLStrategist, "emit") as mock_emit:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        strategist = FinRLStrategist(["SPY"], user_id="u1")
        result = strategist.run_weekly()
        assert result is None
        backtest.assert_not_called()
        mock_emit.assert_not_called()
        mock_producer.send.assert_not_called()
        mock_producer.flush.assert_not_called()
        mock_producer.close.assert_not_called()


def test_run_weekly_not_monday_emits_nothing():
    with (
        patch("agents.sdk.base.KafkaConsumer"),
        patch("agents.sdk.base.KafkaProducer") as mock_producer_cls,
        patch("agents.finrl_strategist.date", Tuesday),
        patch.object(FinRLStrategist, "backtest_last_30d") as backtest,
        patch.object(FinRLStrategist, "emit") as mock_emit,
        patch("agents.finrl_strategist.check_permission") as cp,
    ):
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        strategist = FinRLStrategist(["SPY"], user_id="u1")
        result = strategist.run_weekly()
        assert result is None
        backtest.assert_not_called()
        mock_emit.assert_not_called()
        cp.assert_not_called()
        mock_producer.send.assert_not_called()
        mock_producer.flush.assert_not_called()
        mock_producer.close.assert_not_called()


def test_handle_event_passes_user_context():
    with patch("agents.sdk.base.KafkaConsumer"), patch(
        "agents.sdk.base.KafkaProducer"
    ), patch.object(FinRLStrategist, "run_weekly", autospec=True) as run_weekly:
        strategist = FinRLStrategist(["SPY"], user_id="default", group_id="g-default")
        event = {"user_id": "u-event", "group_id": "g-event"}
        strategist.handle_event(event)
        run_weekly.assert_called_once_with(strategist, user_id="u-event", group_id="g-event")


def test_handle_event_falls_back_to_constructor_context():
    with patch("agents.sdk.base.KafkaConsumer"), patch(
        "agents.sdk.base.KafkaProducer"
    ), patch.object(FinRLStrategist, "run_weekly", autospec=True) as run_weekly:
        strategist = FinRLStrategist(["SPY"], user_id="u1", group_id="g1")
        strategist.handle_event({})
        run_weekly.assert_called_once_with(strategist, user_id="u1", group_id="g1")
