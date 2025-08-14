from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import requests

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
    assert mock_perm.call_args_list == [
        call("user1", "analysis:read", None),
        call("user1", "analysis:write", None),
        call("user1", "analysis:write", None),
    ]

    mock_get.assert_called_once_with(
        "http://engine/analysis/123/actions",
        params={"user_id": "user1"},
        timeout=10,
    )
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
         patch("agents.explainability_agent.requests.get", return_value=mock_resp) as mock_get, \
         patch("agents.explainability_agent.check_permission", return_value=True):
        agent = ExplainabilityAgent("http://engine")
        agent.handle_event({"analysis_id": "123", "user_id": "u1"})
    mock_get.assert_called_once_with(
        "http://engine/analysis/123/actions",
        params={"user_id": "u1"},
        timeout=10,
    )
    downstream.assert_called_once()
    topic, payload = downstream.call_args[0]
    assert topic == "finance.explain.result"
    assert payload["analysis_id"] == "123"
    assert payload["user_id"] == "u1"


def test_group_id_propagates() -> None:
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
         patch("agents.explainability_agent.requests.get", return_value=mock_resp) as mock_get, \
         patch("agents.explainability_agent.check_permission", return_value=True) as mock_perm:
        agent = ExplainabilityAgent("http://engine")
        agent.handle_event({"analysis_id": "123", "user_id": "u1", "group_id": "g1"})
    assert mock_perm.call_args_list == [
        call("u1", "analysis:read", "g1"),
        call("u1", "analysis:write", "g1"),
        call("u1", "analysis:write", "g1"),
    ]

    mock_get.assert_called_once_with(
        "http://engine/analysis/123/actions",
        params={"user_id": "u1", "group_id": "g1"},
        timeout=10,
    )
    downstream.assert_called_once()
    topic, payload = downstream.call_args[0]
    assert topic == "finance.explain.result"
    assert payload["analysis_id"] == "123"
    assert payload["user_id"] == "u1"
    assert payload["group_id"] == "g1"


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
    mock_perm.assert_called_once_with("user1", "analysis:read", None)
    mock_get.assert_not_called()
    agent.emit.assert_not_called()


def test_write_permission_denied(
    agent: ExplainabilityAgent, caplog: pytest.LogCaptureFixture
) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    with patch("agents.explainability_agent.check_permission", side_effect=[True, False]) as mock_perm, \
         patch("agents.explainability_agent.requests.get") as mock_get, \
         caplog.at_level(logging.INFO):
        agent.handle_event(event)
    assert mock_perm.call_args_list == [
        call("user1", "analysis:read", None),
        call("user1", "analysis:write", None),
    ]
    mock_get.assert_not_called()
    agent.emit.assert_not_called()
    assert "Write permission denied" in caplog.text


def test_request_exception_logged(
    agent: ExplainabilityAgent, caplog: pytest.LogCaptureFixture
) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    with patch("agents.explainability_agent.check_permission", return_value=True), \
         patch(
             "agents.explainability_agent.requests.get",
             side_effect=requests.RequestException("boom"),
         ) as mock_get, \
         patch("agents.explainability_agent.time.sleep") as mock_sleep:
        with caplog.at_level(logging.ERROR):
            agent.handle_event(event)
    assert mock_get.call_count == 3
    mock_sleep.assert_has_calls([call(1), call(2)])
    assert "Failed to fetch actions" in caplog.text
    assert "boom" in caplog.text
    agent.emit.assert_not_called()


def test_request_retries_then_succeeds(agent: ExplainabilityAgent) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    response = {
        "actions": [
            {"name": "invest", "pros": ["growth"], "cons": ["risk"]}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status.return_value = None
    side_effects = [
        requests.RequestException("boom1"),
        requests.RequestException("boom2"),
        mock_resp,
    ]
    with patch("agents.explainability_agent.check_permission", return_value=True), \
         patch("agents.explainability_agent.requests.get", side_effect=side_effects) as mock_get, \
         patch("agents.explainability_agent.time.sleep") as mock_sleep:
        agent.handle_event(event)
    assert mock_get.call_count == 3
    mock_sleep.assert_has_calls([call(1), call(2)])
    agent.emit.assert_called_once()


def test_invalid_json_no_emit(
    agent: ExplainabilityAgent, caplog: pytest.LogCaptureFixture
) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.side_effect = ValueError("invalid json")
    with patch("agents.explainability_agent.check_permission", return_value=True), \
         patch("agents.explainability_agent.requests.get", return_value=mock_resp):
        with caplog.at_level(logging.ERROR):
            agent.handle_event(event)
    assert "Failed to parse JSON" in caplog.text
    agent.emit.assert_not_called()


def test_missing_pros_cons_defaults(agent: ExplainabilityAgent) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    response = {"actions": [{"name": "invest", "pros": "growth", "cons": None}]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status.return_value = None
    with patch("agents.explainability_agent.requests.get", return_value=mock_resp), \
         patch("agents.explainability_agent.check_permission", return_value=True):
        agent.handle_event(event)
    explanation = agent.emit.call_args[0][1]["explanations"][0]
    assert explanation["pros"] == ""
    assert explanation["cons"] == ""


def test_invalid_entries_skipped(agent: ExplainabilityAgent) -> None:
    event = {"analysis_id": "123", "user_id": "user1"}
    response = {
        "actions": [
            {"name": "invest", "pros": ["growth"], "cons": ["risk"]},
            {"pros": ["missing name"]},
            "not a dict",
            {"name": 123, "pros": ["bad"], "cons": ["bad"]},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status.return_value = None
    with patch("agents.explainability_agent.requests.get", return_value=mock_resp), \
         patch("agents.explainability_agent.check_permission", return_value=True):
        agent.handle_event(event)
    payload = agent.emit.call_args[0][1]
    assert len(payload["explanations"]) == 1
    assert payload["explanations"][0]["action"] == "invest"

