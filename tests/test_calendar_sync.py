from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.calendar_sync import CalendarSync


def test_handle_event_posts_to_cal():
    with patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        agent = CalendarSync("http://api")
    with patch("agents.calendar_sync.requests.post") as mock_post:
        agent.handle_event({"id": "1", "time": "t"})
        mock_post.assert_called_once_with(
            "http://api",
            json={"id": "1", "time": "t"},
            timeout=10,
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
