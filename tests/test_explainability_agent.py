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
    with patch("agents.explainability_agent.requests.get", return_value=mock_resp) as mock_get:
        agent.handle_event(event)
    mock_get.assert_called_once_with("http://engine/analysis/123/actions", timeout=10)
    agent.emit.assert_called_once()
    topic, payload = agent.emit.call_args[0]
    kwargs = agent.emit.call_args.kwargs
    assert topic == "finance.explain.result"
    assert payload["analysis_id"] == "123"
    assert payload["explanations"][0]["action"] == "invest"
    assert kwargs["user_id"] == "user1"


def test_explainability_agent_missing_analysis_id(agent: ExplainabilityAgent) -> None:
    event = {"user_id": "user1"}
    with patch("agents.explainability_agent.requests.get") as mock_get:
        agent.handle_event(event)
    mock_get.assert_not_called()
    agent.emit.assert_not_called()
