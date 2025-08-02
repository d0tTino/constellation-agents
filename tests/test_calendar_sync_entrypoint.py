from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_calendar_sync_entrypoint(tmp_path: Path) -> None:
    """Run ``python -m agents.calendar_sync`` and ensure webhook server lifecycle."""
    # Stub external Kafka and Prometheus dependencies
    (tmp_path / "kafka").mkdir()
    (tmp_path / "kafka" / "__init__.py").write_text(
        "class KafkaConsumer:\n"
        "    def __init__(self,*a,**k):\n        pass\n"
        "    def __iter__(self):\n        return iter([])\n"
        "class KafkaProducer:\n"
        "    def __init__(self,*a,**k):\n        pass\n"
        "    def send(self,*a,**k):\n        pass\n"
        "    def flush(self):\n        pass\n"
        "    def close(self):\n        pass\n"
    )
    (tmp_path / "prometheus_client").mkdir()
    (tmp_path / "prometheus_client" / "__init__.py").write_text(
        "def start_http_server(*a, **k):\n    pass\n"
        "class Counter:\n"
        "    def __init__(self,*a,**k):\n        pass\n"
        "    def labels(self, **k):\n"
        "        class L:\n"
        "            def inc(self,*a,**k):\n                pass\n"
        "        return L()\n"
        "class Histogram:\n"
        "    def __init__(self,*a,**k):\n        pass\n"
        "    def labels(self, **k):\n"
        "        class L:\n"
        "            def observe(self,*a,**k):\n                pass\n"
        "        return L()\n"
    )

    events = tmp_path / "events.txt"
    events.touch()
    (tmp_path / "sitecustomize.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "import agents.sdk.base as base\n"
        "base.start_http_server = lambda *a, **k: None\n"
        "from agents import calendar_sync as cs\n"
        "events = Path(os.environ['EVENT_FILE'])\n"
        "def record(msg):\n"
        "    with events.open('a') as f:\n"
        "        f.write(msg + '\\n')\n"
        "class DummyServer:\n"
        "    def __init__(self, *a, **k):\n"
        "        record('start')\n"
        "    def serve_forever(self):\n"
        "        pass\n"
        "    def shutdown(self):\n"
        "        record('shutdown')\n"
        "    def server_close(self):\n"
        "        record('close')\n"
        "cs.ThreadingHTTPServer = DummyServer\n"
        "cs.CalendarSync.run = lambda self: None\n"
    )

    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(repo_root)])
    env["EVENT_FILE"] = str(events)

    result = subprocess.run(
        [sys.executable, "-m", "agents.calendar_sync"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert events.read_text().splitlines() == ["start", "shutdown", "close"]
