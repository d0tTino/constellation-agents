from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.finance_advisor import FinanceAdvisor, percentile, percentile_zscore
import pytest


@pytest.fixture()
def advisor() -> FinanceAdvisor:
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = FinanceAdvisor()
    agent.emit = MagicMock()
    return agent


def test_percentile() -> None:
    data = [1, 2, 3, 4, 5]
    assert percentile(data, 50) == 3
    assert percentile(data, 0) == 1
    assert percentile(data, 100) == 5


def test_percentile_empty_list() -> None:
    with pytest.raises(ValueError):
        percentile([], 50)


def test_percentile_negative_numbers() -> None:
    data = [-5, -2, -1]
    assert percentile(data, 50) == -2


def test_percentile_zscore() -> None:
    history = [10, 20, 30, 40, 50]
    value = 60
    score = percentile_zscore(history, value)
    assert score > 0


def test_percentile_zscore_empty_history() -> None:
    assert percentile_zscore([], 10) == 0.0


def test_percentile_zscore_negative_numbers() -> None:
    history = [-30, -20, -10]
    value = -5
    score = percentile_zscore(history, value)
    assert score > 0


def test_emit_on_high_zscore(advisor: FinanceAdvisor) -> None:
    normal = [100, 105, 95, 100, 102, 98, 101, 99, 103, 97]
    for amt in normal:
        advisor.handle_event({"amount": amt})
    advisor.emit.assert_not_called()

    advisor.handle_event({"amount": 1000})
    advisor.emit.assert_called_once()
    topic, payload = advisor.emit.call_args[0]
    assert topic == "ume.events.transaction.anomaly"
    assert payload["amount"] == 1000
    assert payload["z"] > 3


def test_emit_on_low_zscore(advisor: FinanceAdvisor) -> None:
    normal = [100, 105, 95, 100, 102, 98, 101, 99, 103, 97]
    for amt in normal:
        advisor.handle_event({"amount": amt})
    advisor.emit.assert_not_called()

    advisor.handle_event({"amount": -1000})
    advisor.emit.assert_called_once()
    topic, payload = advisor.emit.call_args[0]
    assert topic == "ume.events.transaction.anomaly"
    assert payload["amount"] == -1000
    assert payload["z"] < -3
