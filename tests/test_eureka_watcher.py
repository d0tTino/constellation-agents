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
         patch.object(EurekaWatcher, "emit") as mock_emit:
        watcher = EurekaWatcher("http://example")
        watcher.handle_event(event)
        mock_emit.assert_called_once()
        args, _ = mock_emit.call_args
        assert args[0] == "ume.events.suggested_task"
        assert args[1]["idea"] == "idea1"
        assert args[1]["doc"] == "doc1"
