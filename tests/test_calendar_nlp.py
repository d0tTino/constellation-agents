from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.calendar_nlp import CalendarNLPAgent


@pytest.fixture()
def agent() -> tuple[CalendarNLPAgent, MagicMock]:
    llm = MagicMock(return_value={
        "title": "Lunch",
        "start_time": "2024-01-01T12:00:00+00:00",
        "end_time": "2024-01-01T13:00:00+00:00",
        "location": "Cafe",
        "description": "Lunch with Sam",
        "is_all_day": False,
        "recurrence": None,
    })
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarNLPAgent(llm, default_timezone=None)
    agent.emit = MagicMock(wraps=agent.emit)
    return agent, llm


def test_parses_and_emits_event(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    event = {"user_id": "u1", "text": "Lunch with Sam at noon"}

    with patch("agents.calendar_nlp.check_permission", return_value=True) as mock_perm:
        agent_instance.handle_event(event)
    mock_perm.assert_called_once_with("u1", "calendar:create", None)

    llm.assert_called_once()
    payload = llm.call_args[0][0]
    assert payload["text"] == "Lunch with Sam at noon"
    assert payload["timezone"] == "UTC"
    assert payload["current_datetime"].endswith("+00:00")
    agent_instance.emit.assert_called_once()
    topic, payload = agent_instance.producer.send.call_args[0]
    kwargs = agent_instance.emit.call_args[1]
    assert topic == "calendar.event.create_request"
    assert payload["event"]["title"] == "Lunch"
    assert payload["event"]["start_time"] == "2024-01-01T12:00:00+00:00"
    assert payload["event"]["end_time"] == "2024-01-01T13:00:00+00:00"
    assert payload["user_id"] == "u1"
    assert "group_id" not in payload
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] is None


def test_parses_and_emits_event_with_group(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    event = {
        "user_id": "u1",
        "text": "Lunch with Sam at noon",
        "group_id": "g1",
        "timezone": "UTC",
    }
    with patch("agents.calendar_nlp.check_permission", return_value=True) as mock_perm:
        agent_instance.handle_event(event)
    mock_perm.assert_called_once_with("u1", "calendar:create", "g1")
    llm.assert_called_once()
    payload = llm.call_args[0][0]
    assert payload["text"] == "Lunch with Sam at noon"
    assert payload["timezone"] == "UTC"
    assert payload["current_datetime"].endswith("+00:00")
    agent_instance.emit.assert_called_once()
    topic, payload = agent_instance.producer.send.call_args[0]
    kwargs = agent_instance.emit.call_args[1]
    assert topic == "calendar.event.create_request"
    assert payload["event"]["title"] == "Lunch"
    assert payload["user_id"] == "u1"
    assert payload["group_id"] == "g1"
    assert kwargs["user_id"] == "u1"

    assert kwargs["group_id"] == "g1"


def test_parses_event_with_group_and_timezone(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    event = {
        "user_id": "u1",
        "text": "Lunch with Sam at noon",
        "group_id": "g1",
        "timezone": "America/New_York",
    }
    with patch("agents.calendar_nlp.check_permission", return_value=True) as mock_perm:
        agent_instance.handle_event(event)
    mock_perm.assert_called_once_with("u1", "calendar:create", "g1")
    llm.assert_called_once_with({
        "text": "Lunch with Sam at noon",
        "current_datetime": ANY,
        "timezone": "America/New_York",
    })
    agent_instance.emit.assert_called_once()
    topic, payload = agent_instance.producer.send.call_args[0]
    kwargs = agent_instance.emit.call_args[1]
    assert topic == "calendar.event.create_request"
    assert payload["event"]["title"] == "Lunch"
    assert payload["user_id"] == "u1"
    assert payload["group_id"] == "g1"
    assert kwargs["user_id"] == "u1"
    assert kwargs["group_id"] == "g1"


def test_invalid_timezone(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    event = {"user_id": "u1", "text": "Lunch", "timezone": "Invalid/Zone"}
    with patch("agents.calendar_nlp.check_permission", return_value=True):
        agent_instance.handle_event(event)
    llm.assert_not_called()
    agent_instance.emit.assert_not_called()


def test_emitted_event_consumed_by_downstream() -> None:
    """Integration-style test verifying downstream consumption of events."""

    downstream = MagicMock()

    class MockProducer:
        def send(self, topic, event):  # type: ignore[no-untyped-def]
            downstream(topic, event)

        def flush(self):  # type: ignore[no-untyped-def]
            pass

    llm = MagicMock(
        return_value={
            "title": "Lunch",
            "start_time": "2024-01-01T12:00:00+00:00",
            "end_time": "2024-01-01T13:00:00+00:00",
        }
    )
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer", return_value=MockProducer()), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarNLPAgent(llm, default_timezone=None)

    with patch("agents.calendar_nlp.check_permission", return_value=True):
        agent.handle_event({"user_id": "u1", "group_id": "g1", "text": "Lunch"})

    downstream.assert_called_once()
    topic, payload = downstream.call_args[0]
    assert topic == "calendar.event.create_request"
    assert payload["event"]["title"] == "Lunch"
    assert payload["user_id"] == "u1"
    assert payload["group_id"] == "g1"



def test_missing_fields(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    with patch("agents.calendar_nlp.check_permission") as mock_perm:
        agent_instance.handle_event({"text": "No user"})
    mock_perm.assert_not_called()
    llm.assert_not_called()
    agent_instance.emit.assert_not_called()


def test_permission_denied(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    with patch("agents.calendar_nlp.check_permission", return_value=False) as mock_perm:
        agent_instance.handle_event({"user_id": "u1", "text": "Lunch"})
    mock_perm.assert_called_once_with("u1", "calendar:create", None)

    llm.assert_not_called()
    agent_instance.emit.assert_not_called()


def test_uses_default_timezone_when_missing() -> None:
    llm = MagicMock(return_value={
        "title": "Lunch",
        "start_time": "2024-01-01T12:00:00+00:00",
        "end_time": "2024-01-01T13:00:00+00:00",
        "location": "Cafe",
        "description": "Lunch with Sam",
        "is_all_day": False,
        "recurrence": None,
    })
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarNLPAgent(llm, default_timezone="UTC")
    agent.emit = MagicMock(wraps=agent.emit)

    event = {"user_id": "u1", "text": "Lunch"}
    with patch("agents.calendar_nlp.check_permission", return_value=True):
        agent.handle_event(event)
    llm.assert_called_once()
    payload = llm.call_args[0][0]
    assert payload["text"] == "Lunch"
    assert payload["timezone"] == "UTC"
    assert payload["current_datetime"].endswith("+00:00")


def test_rejects_naive_llm_datetimes(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    llm.return_value["start_time"] = "2024-01-01T12:00:00"
    llm.return_value["end_time"] = "2024-01-01T13:00:00"
    event = {"user_id": "u1", "text": "Lunch"}
    with patch("agents.calendar_nlp.check_permission", return_value=True):
        agent_instance.handle_event(event)
    llm.assert_called_once()
    agent_instance.emit.assert_not_called()


def test_llm_request_exception(agent: tuple[CalendarNLPAgent, MagicMock]) -> None:
    agent_instance, llm = agent
    llm.side_effect = requests.RequestException("boom")
    event = {"user_id": "u1", "text": "Lunch"}
    with patch("agents.calendar_nlp.check_permission", return_value=True), \
         patch("agents.calendar_nlp.logger") as mock_logger:
        agent_instance.handle_event(event)
    llm.assert_called_once()
    mock_logger.exception.assert_called_once()
    agent_instance.emit.assert_not_called()


def test_invalid_datetime_fields_skip_emission(
    agent: tuple[CalendarNLPAgent, MagicMock]
) -> None:
    agent_instance, llm = agent
    llm.return_value = {
        "title": "Lunch",
        "start_time": "invalid",
        "end_time": "2024-01-01T13:00:00+00:00",
    }
    with patch("agents.calendar_nlp.check_permission", return_value=True), \
         patch("agents.calendar_nlp.logger") as mock_logger:
        agent_instance.handle_event({"user_id": "u1", "text": "Lunch"})
    llm.assert_called_once()
    mock_logger.warning.assert_called_once()
    agent_instance.emit.assert_not_called()


def test_missing_datetime_fields_skip_emission(
    agent: tuple[CalendarNLPAgent, MagicMock]
) -> None:
    agent_instance, llm = agent
    llm.return_value = {
        "title": "Lunch",
        "start_time": "2024-01-01T12:00:00+00:00",
    }
    with patch("agents.calendar_nlp.check_permission", return_value=True), \
         patch("agents.calendar_nlp.logger") as mock_logger:
        agent_instance.handle_event({"user_id": "u1", "text": "Lunch"})
    llm.assert_called_once()
    mock_logger.warning.assert_called_once()
    agent_instance.emit.assert_not_called()
