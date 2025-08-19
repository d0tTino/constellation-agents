from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.plaid_sync import (
    PlaidClient,
    PlaidSync,
    READ_ACTION,
    WRITE_ACTION,
)  # noqa: E402


@pytest.fixture()
def agent() -> PlaidSync:
    plaid = MagicMock(spec=PlaidClient)
    with patch("agents.sdk.base.KafkaConsumer"),          patch("agents.sdk.base.KafkaProducer"),          patch("agents.sdk.base.start_http_server"):
        ag = PlaidSync(plaid)
    ag.emit = MagicMock()
    ag.plaid = plaid
    return ag


def test_permission_checks_and_event_emission(agent: PlaidSync) -> None:
    order: list[tuple[str, str]] = []

    def cp_side_effect(user: str, action: str, group: str | None) -> bool:
        order.append(("cp", action))
        return True

    def fetch_side_effect(user: str) -> list[dict[str, str | int]]:
        order.append(("fetch", ""))
        return [{"id": "t1", "amount": 100, "account_id": "a1"}]

    agent.plaid.fetch_transactions.side_effect = fetch_side_effect
    with patch("agents.plaid_sync.check_permission", side_effect=cp_side_effect) as cp:
        agent.sync("u1", group_id="g1")
    assert order == [("cp", READ_ACTION), ("cp", WRITE_ACTION), ("fetch", "")]
    assert cp.call_args_list == [
        (("u1", READ_ACTION, "g1"),),
        (("u1", WRITE_ACTION, "g1"),),
    ]
    agent.plaid.fetch_transactions.assert_called_once_with("u1")
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args[1]
    assert topic == "plaid.transaction.synced"
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] == "g1"
    assert payload == {"id": "t1", "amount": 100, "account_id": "a1"}
    assert "user_id" not in payload
    assert "group_id" not in payload


def test_permission_denied(agent: PlaidSync) -> None:
    metric = MagicMock()
    with patch("agents.plaid_sync.PERMISSION_DENIALS", metric), patch(
        "agents.plaid_sync.check_permission", return_value=False
    ) as cp:
        agent.sync("u1")
    cp.assert_called_once_with("u1", READ_ACTION, None)
    metric.labels.assert_called_once_with(action="read")
    metric.labels.return_value.inc.assert_called_once_with()
    agent.plaid.fetch_transactions.assert_not_called()
    agent.emit.assert_not_called()


def test_write_permission_denied(agent: PlaidSync) -> None:
    agent.plaid.fetch_transactions.return_value = [{"id": "t1"}]
    metric = MagicMock()
    with patch("agents.plaid_sync.PERMISSION_DENIALS", metric), patch(
        "agents.plaid_sync.check_permission", side_effect=[True, False]
    ) as cp:
        result = agent.sync("u1")
    assert cp.call_args_list == [
        (("u1", READ_ACTION, None),),
        (("u1", WRITE_ACTION, None),),
    ]
    metric.labels.assert_called_once_with(action="write")
    metric.labels.return_value.inc.assert_called_once_with()
    agent.plaid.fetch_transactions.assert_not_called()
    agent.emit.assert_not_called()
    assert result == []


def test_fetch_transactions_error(agent: PlaidSync) -> None:
    agent.plaid.fetch_transactions.side_effect = Exception("boom")
    with patch(
        "agents.plaid_sync.check_permission", return_value=True
    ) as cp, patch("agents.plaid_sync.logger") as log:
        result = agent.sync("u1")
    assert cp.call_args_list == [
        (("u1", READ_ACTION, None),),
        (("u1", WRITE_ACTION, None),),
    ]
    log.exception.assert_called_once()
    agent.emit.assert_not_called()
    assert result == []


def test_handle_event_permission_denied(agent: PlaidSync) -> None:
    event = {"user_id": "u1", "group_id": "g1"}
    metric = MagicMock()
    with patch("agents.plaid_sync.PERMISSION_DENIALS", metric), patch(
        "agents.plaid_sync.check_permission", return_value=False
    ) as cp:
        agent.handle_event(event)
    cp.assert_called_once_with("u1", READ_ACTION, "g1")
    metric.labels.assert_called_once_with(action="read")
    metric.labels.return_value.inc.assert_called_once_with()
    agent.plaid.fetch_transactions.assert_not_called()
    agent.emit.assert_not_called()


def test_handle_event_write_permission_denied(agent: PlaidSync) -> None:
    event = {"user_id": "u1", "group_id": "g1"}
    metric = MagicMock()
    with patch("agents.plaid_sync.PERMISSION_DENIALS", metric), patch(
        "agents.plaid_sync.check_permission", side_effect=[True, False]
    ) as cp:
        agent.handle_event(event)
    assert cp.call_args_list == [
        (("u1", READ_ACTION, "g1"),),
        (("u1", WRITE_ACTION, "g1"),),
    ]
    metric.labels.assert_called_once_with(action="write")
    metric.labels.return_value.inc.assert_called_once_with()
    agent.plaid.fetch_transactions.assert_not_called()
    agent.emit.assert_not_called()


def test_handle_event_missing_user_id(agent: PlaidSync) -> None:
    event = {"group_id": "g1"}
    with patch("agents.plaid_sync.check_permission") as cp:
        agent.handle_event(event)
    cp.assert_not_called()
    agent.plaid.fetch_transactions.assert_not_called()
    agent.emit.assert_not_called()
