from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.eureka_watcher import EurekaWatcher, cosine_similarity


def test_cosine_similarity() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0


def test_watcher_emits_for_similar_doc() -> None:
    event = {"id": "idea1", "vector": [1.0, 0.0]}
    docs = {"docs": [{"id": "doc1", "vector": [1.0, 0.0]}, {"id": "doc2", "vector": [0, 1]}]}
    with patch("agents.eureka_watcher.ume_query", return_value=docs), \
         patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"), \
         patch.object(EurekaWatcher, "emit") as mock_emit, \
         patch("agents.eureka_watcher.check_permission", return_value=True) as cp:
        watcher = EurekaWatcher("http://example", user_id="u1")
        watcher.handle_event(event)
        cp.assert_called_once_with("u1", "suggest", None)
        mock_emit.assert_called_once()
        args, kwargs = mock_emit.call_args
        assert args[0] == "ume.events.suggested_task"
        payload = args[1]
        assert payload["idea"] == "idea1"
        assert payload["doc"] == "doc1"
        assert "user_id" not in payload
        assert "group_id" not in payload
        assert kwargs["user_id"] == "u1"
        assert kwargs["group_id"] is None


def test_watcher_ignores_dissimilar_doc() -> None:
    """Watcher should not emit events when similarity is below the threshold."""
    event = {"id": "idea1", "vector": [1.0, 0.0]}
    docs = {"docs": [{"id": "doc1", "vector": [0.1, 0.9]}]}
    with patch("agents.eureka_watcher.ume_query", return_value=docs), \
         patch("agents.sdk.base.KafkaConsumer"), \
         patch("agents.sdk.base.KafkaProducer"), \
         patch("agents.sdk.base.start_http_server"), \
         patch.object(EurekaWatcher, "emit") as mock_emit, \
         patch("agents.eureka_watcher.check_permission", return_value=True) as cp:
        watcher = EurekaWatcher("http://example", user_id="u1")
        watcher.handle_event(event)
        cp.assert_called_once_with("u1", "suggest", None)
        mock_emit.assert_not_called()


def test_watcher_event_identifiers_override_defaults() -> None:
    event = {
        "id": "idea1",
        "vector": [1.0, 0.0],
        "user_id": "u2",
        "group_id": "g1",
    }
    docs = {"docs": [{"id": "doc1", "vector": [1.0, 0.0]}]}
    with (
        patch("agents.eureka_watcher.ume_query", return_value=docs),
        patch("agents.sdk.base.KafkaConsumer"),
        patch("agents.sdk.base.KafkaProducer"),
        patch("agents.sdk.base.start_http_server"),
        patch.object(EurekaWatcher, "emit") as mock_emit,
        patch("agents.eureka_watcher.check_permission", return_value=True) as cp,
    ):
        watcher = EurekaWatcher("http://example", user_id="u1", group_id="g0")
        watcher.handle_event(event)
        cp.assert_called_once_with("u2", "suggest", "g1")
        mock_emit.assert_called_once()
        _, kwargs = mock_emit.call_args
        assert kwargs["user_id"] == "u2"
        assert kwargs["group_id"] == "g1"


def test_watcher_handles_none_response() -> None:
    event = {"id": "idea1", "vector": [1.0, 0.0]}
    with (
        patch("agents.eureka_watcher.ume_query", return_value=None),
        patch("agents.sdk.base.KafkaConsumer"),
        patch("agents.sdk.base.KafkaProducer"),
        patch("agents.sdk.base.start_http_server"),
        patch.object(EurekaWatcher, "emit") as mock_emit,
        patch("agents.eureka_watcher.check_permission", return_value=True) as cp,
        patch("agents.eureka_watcher.logger") as mock_logger,
    ):
        watcher = EurekaWatcher("http://example", user_id="u1")
        watcher.handle_event(event)
        cp.assert_called_once_with("u1", "suggest", None)
        mock_emit.assert_not_called()
        mock_logger.error.assert_called_once()


def test_watcher_skips_emit_without_permission() -> None:
    """Watcher should not emit events when permission is denied."""
    event = {"id": "idea1", "vector": [1.0, 0.0]}
    with (
        patch("agents.eureka_watcher.ume_query") as mock_query,
        patch("agents.sdk.base.KafkaConsumer"),
        patch("agents.sdk.base.KafkaProducer"),
        patch("agents.sdk.base.start_http_server"),
        patch.object(EurekaWatcher, "emit") as mock_emit,
        patch("agents.eureka_watcher.check_permission", return_value=False) as cp,
    ):
        watcher = EurekaWatcher("http://example", user_id="u1")
        watcher.handle_event(event)
        cp.assert_called_once_with("u1", "suggest", None)
        mock_query.assert_not_called()
        mock_emit.assert_not_called()
