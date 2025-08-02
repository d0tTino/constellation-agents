from unittest.mock import ANY, MagicMock, patch
import pytest
import agents.sdk.base as base
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agents.sdk as sdk
from prometheus_client import CollectorRegistry, Counter, Histogram


@pytest.fixture(autouse=True)
def reset_metrics_started():
    base._METRICS_STARTED = False
    yield
    base._METRICS_STARTED = False


def test_emit_event_uses_kafka_producer():
    with patch("agents.sdk.KafkaProducer") as mock_producer_cls:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        sdk.emit_event("topic", {"a": 1})
        mock_producer.send.assert_called_once()
        mock_producer.flush.assert_called_once()
        mock_producer.close.assert_called_once()


def test_ume_query_posts_and_returns_json():
    with patch("agents.sdk.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": 1}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        assert sdk.ume_query("http://example", {"q": 1}) == {"result": 1}
        mock_post.assert_called_once()


def test_ume_query_uses_sidecar(monkeypatch):
    with patch("agents.sdk.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        monkeypatch.setenv("OPA_SIDECAR_URL", "http://sidecar")
        assert sdk.ume_query("http://example", {"a": 1}) == {"ok": True}
        mock_post.assert_called_once_with(
            "http://sidecar",
            json={"url": "http://example", "payload": {"a": 1}},
            timeout=10,
        )


def test_ume_query_sidecar_env(monkeypatch):
    """Ensure the sidecar URL from the environment is respected."""
    with patch("agents.sdk.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        monkeypatch.setenv("OPA_SIDECAR_URL", "http://proxy")
        sdk.ume_query("http://target", {"x": 2})
        mock_post.assert_called_once_with(
            "http://proxy",
            json={"url": "http://target", "payload": {"x": 2}},
            timeout=10,
        )


def test_base_agent_dispatches_messages():
    with patch("agents.sdk.base.KafkaConsumer") as mock_consumer_cls, \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer
        mock_consumer.__iter__.return_value = iter([MagicMock(value={"x": 1})])

        class TestAgent(sdk.BaseAgent):
            def __init__(self):
                super().__init__("topic", metrics_port=None)
                self.events = []

            def handle_event(self, event):
                self.events.append(event)

        agent = TestAgent()
        agent.run()
        assert agent.events == [{"x": 1}]


def test_metrics_increment_when_processing_events():
    with patch("agents.sdk.base.KafkaConsumer") as mock_consumer_cls, \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        mock_consumer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer
        mock_consumer.__iter__.return_value = iter([MagicMock(value={"x": 1})])

        registry = CollectorRegistry()
        counter = Counter("agent_messages_total", "desc", ["agent"], registry=registry)
        hist = Histogram(
            "agent_processing_seconds",
            "desc",
            ["agent"],
            registry=registry,
        )

        with patch("agents.sdk.base.MESSAGE_COUNTER", counter), patch(
            "agents.sdk.base.PROCESSING_TIME",
            hist,
        ):

            class TestAgent(sdk.BaseAgent):
                def __init__(self):
                    super().__init__("topic", metrics_port=None)

                def handle_event(self, event):
                    pass

            agent = TestAgent()
            agent.run()

        msg_val = registry.get_sample_value(
            "agent_messages_total", {"agent": "TestAgent"}
        )
        dur_count = registry.get_sample_value(
            "agent_processing_seconds_count", {"agent": "TestAgent"}
        )
        assert msg_val == 1.0
        assert dur_count == 1.0


def test_base_agent_accepts_multiple_topics():
    with patch("agents.sdk.base.KafkaConsumer") as mock_consumer_cls, \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"):
        mock_consumer_cls.return_value = MagicMock(__iter__=lambda self: iter([]))

        class TestAgent(sdk.BaseAgent):
            def __init__(self):
                super().__init__(["t1", "t2"], metrics_port=None)

            def handle_event(self, event):  # pragma: no cover - unused
                pass

        TestAgent()
        mock_consumer_cls.assert_called_once_with(
            "t1",
            "t2",
            bootstrap_servers="localhost:9092",
            group_id=None,
            value_deserializer=ANY,
        )
