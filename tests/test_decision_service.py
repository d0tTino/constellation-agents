from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.decision_service import DecisionService


@pytest.fixture()
def agent() -> DecisionService:
    with (
        patch("agents.sdk.base.KafkaConsumer"),
        patch("agents.sdk.base.KafkaProducer"),
        patch("agents.sdk.base.start_http_server"),
    ):
        ag = DecisionService()
    ag.emit = MagicMock()
    return ag


def test_emits_result(agent: DecisionService) -> None:
    event = {"analysis_id": "a1", "decision": {"action": "buy"}, "user_id": "u1"}
    with patch("agents.decision_service.check_permission", return_value=True) as mock_perm:
        agent.handle_event(event)
    mock_perm.assert_called_once_with("u1", "analysis:decision", None)
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args.kwargs
    assert topic == "finance.decision.result"
    assert payload == {"analysis_id": "a1", "decision": {"action": "buy"}}
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] is None


def test_group_id_propagates(agent: DecisionService) -> None:
    event = {"analysis_id": "a1", "user_id": "u1", "group_id": "g1"}
    with patch("agents.decision_service.check_permission", return_value=True) as mock_perm:
        agent.handle_event(event)
    mock_perm.assert_called_once_with("u1", "analysis:decision", "g1")
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args.kwargs
    assert topic == "finance.decision.result"
    assert payload == {"analysis_id": "a1"}
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] == "g1"


def test_permission_denied(agent: DecisionService) -> None:
    event = {"analysis_id": "a1", "user_id": "u1"}
    with patch("agents.decision_service.check_permission", return_value=False) as mock_perm:
        agent.handle_event(event)
    mock_perm.assert_called_once_with("u1", "analysis:decision", None)
    agent.emit.assert_not_called()


def test_missing_fields(agent: DecisionService) -> None:
    agent.handle_event({"user_id": "u1"})
    agent.handle_event({"analysis_id": "a1"})
    agent.emit.assert_not_called()
