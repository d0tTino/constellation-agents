from __future__ import annotations

import logging
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.calendar_sync import CalendarSync


def test_handle_event_posts_to_cal():
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarSync("http://api")
    with patch("agents.calendar_sync.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        agent.handle_event({"id": "1", "time": "t"})
        mock_post.assert_called_once_with(
            "http://api",
            json={"id": "1", "time": "t"},
            timeout=10,
        )


def test_handle_event_retries_on_failure(caplog):
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarSync("http://api")
    bad = MagicMock(status_code=500)
    good = MagicMock(status_code=200)
    with patch(
        "agents.calendar_sync.requests.post", side_effect=[bad, good]
    ) as mock_post:
        with caplog.at_level(logging.ERROR):
            agent.handle_event({"id": "1", "time": "t"})
    assert mock_post.call_count == 2
    assert any(
        "Cal.com sync failed" in record.message for record in caplog.records
    )


def test_handle_cal_event_emits_task_reschedule():
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarSync("http://api")
    agent.emit = MagicMock()
    agent.handle_cal_event({"id": "2", "time": "t"})
    agent.emit.assert_called_once_with(
        "ume.events.task.reschedule",
        {"id": "2", "time": "t"},
    )


def test_webhook_server_processes_post():
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarSync("http://api")

    agent.start_webhook_server(host="127.0.0.1", port=0)
    try:
        with patch.object(agent, "handle_cal_event") as mock_handle:
            url = f"http://{agent._webhook_server.server_address[0]}:{agent._webhook_server.server_port}"
            requests.post(url, json={"id": "3", "time": "t"})
            mock_handle.assert_called_once_with({"id": "3", "time": "t"})
    finally:
        agent.stop_webhook_server()
