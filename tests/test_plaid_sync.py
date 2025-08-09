from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.plaid_sync import PlaidSync, PlaidClient  # noqa: E402


@pytest.fixture()
def agent() -> PlaidSync:
    plaid = MagicMock(spec=PlaidClient)
    with patch("agents.sdk.base.KafkaConsumer"),          patch("agents.sdk.base.KafkaProducer"),          patch("agents.sdk.base.start_http_server"):
        ag = PlaidSync(plaid)
    ag.emit = MagicMock()
    ag.plaid = plaid
    return ag


def test_permission_checks_and_event_emission(agent: PlaidSync) -> None:
    agent.plaid.fetch_transactions.return_value = [{"id": "t1"}]
    with patch("agents.plaid_sync.check_permission", side_effect=[True, True]) as cp:
        agent.sync("u1", group_id="g1")
    assert cp.call_args_list == [
        (("u1", "read", "g1"),),
        (("u1", "write", "g1"),),
    ]
    agent.plaid.fetch_transactions.assert_called_once_with("u1")
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args[1]
    assert topic == "plaid.transaction.synced"
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] == "g1"
    assert "user_id" not in payload
    assert "group_id" not in payload


def test_permission_denied(agent: PlaidSync) -> None:
    with patch("agents.plaid_sync.check_permission", return_value=False) as cp:
        agent.sync("u1")
    cp.assert_called_once_with("u1", "read", None)
    agent.plaid.fetch_transactions.assert_not_called()
    agent.emit.assert_not_called()


def test_write_permission_denied(agent: PlaidSync) -> None:
    agent.plaid.fetch_transactions.return_value = [{"id": "t1"}]
    with patch("agents.plaid_sync.check_permission", side_effect=[True, False]) as cp:
        result = agent.sync("u1")
    assert cp.call_args_list == [
        (("u1", "read", None),),
        (("u1", "write", None),),
    ]
    agent.emit.assert_not_called()
    assert result == []
