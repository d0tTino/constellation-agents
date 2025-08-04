from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.explainability_agent import ExplainabilityAgent


@pytest.fixture()
def agent() -> ExplainabilityAgent:
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        ag = ExplainabilityAgent("http://engine")
    ag.emit = MagicMock()
    return ag


def test_explainability_agent_emits(agent: ExplainabilityAgent) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    response = {
        "actions": [
            {"name": "invest", "pros": ["growth"], "cons": ["risk"]}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status.return_value = None
    with patch("agents.explainability_agent.requests.get", return_value=mock_resp) as mock_get, \
         patch("agents.explainability_agent.check_permission", return_value=True) as mock_perm:
        agent.handle_event(event)
    mock_perm.assert_called_once_with("user1", "analysis:read")
    mock_get.assert_called_once_with("http://engine/analysis/123/actions", timeout=10)
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args.kwargs
    assert topic == "finance.explain.result"
    assert payload["analysis_id"] == "123"
    assert payload["explanations"][0]["action"] == "invest"
    assert kwargs["user_id"] == "user1"


def test_event_consumed_by_downstream() -> None:
    downstream = MagicMock()

    class MockProducer:
        def send(self, topic, event):  # type: ignore[no-untyped-def]
            downstream(topic, event)

        def flush(self):  # type: ignore[no-untyped-def]
            pass

    response = {
        "actions": [{"name": "invest", "pros": ["growth"], "cons": ["risk"]}]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status.return_value = None

    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer", return_value=MockProducer()), \
         patch("agents.sdk.base.start_http_server"), \
         patch("agents.explainability_agent.requests.get", return_value=mock_resp), \
         patch("agents.explainability_agent.check_permission", return_value=True):
        agent = ExplainabilityAgent("http://engine")
        agent.handle_event({"analysis_id": "123", "user_id": "u1"})
    downstream.assert_called_once()
    topic, payload = downstream.call_args[0]
    assert topic == "finance.explain.result"
    assert payload["analysis_id"] == "123"
    assert payload["user_id"] == "u1"


def test_explainability_agent_missing_analysis_id(agent: ExplainabilityAgent) -> None:
    event = {"user_id": "user1"}
    with patch("agents.explainability_agent.requests.get") as mock_get, \
         patch("agents.explainability_agent.check_permission") as mock_perm:
        agent.handle_event(event)
    mock_perm.assert_not_called()
    mock_get.assert_not_called()
    agent.emit.assert_not_called()


def test_permission_denied(agent: ExplainabilityAgent) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    with patch("agents.explainability_agent.check_permission", return_value=False) as mock_perm, \
         patch("agents.explainability_agent.requests.get") as mock_get:
        agent.handle_event(event)
    mock_perm.assert_called_once_with("user1", "analysis:read")
    mock_get.assert_not_called()
    agent.emit.assert_not_called()

