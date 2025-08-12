from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.finance_advisor import (
    FinanceAdvisor,
    percentile,
    percentile_zscore,
    READ_ACTION,
    WRITE_ACTION,
)
import pytest


@pytest.fixture()
def advisor() -> tuple[FinanceAdvisor, MagicMock]:
    with (
        patch("agents.sdk.base.KafkaConsumer"),
        patch("agents.sdk.base.KafkaProducer"),
        patch("agents.sdk.base.start_http_server"),
    ):
        agent = FinanceAdvisor()
    agent.producer.send = MagicMock()
    agent.emit = MagicMock(wraps=agent.emit)
    return agent, agent.producer.send


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


def test_emit_on_high_zscore(advisor: tuple[FinanceAdvisor, MagicMock]) -> None:
    agent, send_mock = advisor
    normal = [100, 105, 95, 100, 102, 98, 101, 99, 103, 97]
    with patch("agents.finance_advisor.check_permission", return_value=True) as cp:
        for amt in normal:
            agent.handle_event({"amount": amt, "user_id": "u1", "group_id": "g1"})
        agent.emit.assert_not_called()
        agent.handle_event({"amount": 1000, "user_id": "u1", "group_id": "g1"})
    assert cp.call_count == len(normal) + 2
    assert cp.call_args_list[-2:] == [
        call("u1", READ_ACTION, "g1"),
        call("u1", WRITE_ACTION, "g1"),
    ]
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args[1]
    assert topic == "ume.events.transaction.anomaly"
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] == "g1"
    assert payload["amount"] == 1000
    assert payload["z"] > 3
    assert "user_id" not in payload
    assert "group_id" not in payload
    send_topic, send_payload = send_mock.call_args[0]
    assert send_topic == "ume.events.transaction.anomaly"
    assert send_payload["user_id"] == "u1"
    assert send_payload["group_id"] == "g1"
    assert send_payload["amount"] == 1000
    assert send_payload["z"] > 3


def test_emit_on_low_zscore(advisor: tuple[FinanceAdvisor, MagicMock]) -> None:
    agent, send_mock = advisor
    normal = [100, 105, 95, 100, 102, 98, 101, 99, 103, 97]
    with patch("agents.finance_advisor.check_permission", return_value=True) as cp:
        for amt in normal:
            agent.handle_event({"amount": amt, "user_id": "u1"})
        agent.emit.assert_not_called()
        agent.handle_event({"amount": -1000, "user_id": "u1"})
    assert cp.call_count == len(normal) + 2
    assert cp.call_args_list[-2:] == [
        call("u1", READ_ACTION, None),
        call("u1", WRITE_ACTION, None),
    ]
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args[1]
    assert topic == "ume.events.transaction.anomaly"
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] is None
    assert payload["amount"] == -1000
    assert payload["z"] < -3
    assert "user_id" not in payload
    assert "group_id" not in payload
    send_topic, send_payload = send_mock.call_args[0]
    assert send_topic == "ume.events.transaction.anomaly"
    assert send_payload["user_id"] == "u1"
    assert "group_id" not in send_payload
    assert send_payload["amount"] == -1000
    assert send_payload["z"] < -3


def test_permission_denied(advisor: tuple[FinanceAdvisor, MagicMock]) -> None:
    agent, _ = advisor
    with patch("agents.finance_advisor.check_permission", return_value=False) as cp:
        agent.handle_event({"amount": 10, "user_id": "u1"})
    cp.assert_called_once_with("u1", READ_ACTION, None)
    agent.emit.assert_not_called()


def test_history_cap(advisor: tuple[FinanceAdvisor, MagicMock]) -> None:
    agent, _ = advisor
    with patch("agents.finance_advisor.check_permission", return_value=True):
        total = FinanceAdvisor.HISTORY_SIZE + 100
        for i in range(total):
            agent.handle_event({"amount": i, "user_id": "u1"})
    assert len(agent.amounts) == FinanceAdvisor.HISTORY_SIZE
    assert agent.amounts[0] == total - FinanceAdvisor.HISTORY_SIZE
