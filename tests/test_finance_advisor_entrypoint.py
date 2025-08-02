from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_finance_advisor_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "kafka").mkdir()
    (tmp_path / "kafka" / "__init__.py").write_text(
        "class DummyMessage:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "\n"
        "class KafkaConsumer:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        self._sent = False\n"
        "    def __iter__(self):\n"
        "        return self\n"
        "    def __next__(self):\n"
        "        if self._sent:\n"
        "            raise StopIteration\n"
        "        self._sent = True\n"
        "        print('event consumed', flush=True)\n"
        "        return DummyMessage({'amount': 1, 'user_id': 'u1'})\n"
        "\n"
        "class KafkaProducer:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        pass\n"
        "    def send(self, *args, **kwargs):\n"
        "        pass\n"
        "    def flush(self):\n"
        "        pass\n"
    )

    (tmp_path / "requests").mkdir()
    (tmp_path / "requests" / "__init__.py").write_text(
        "class Response:\n"
        "    def raise_for_status(self):\n"
        "        pass\n"
        "    def json(self):\n"
        "        return {'allow': True}\n"
        "def post(*args, **kwargs):\n"
        "    return Response()\n"
    )

    (tmp_path / "prometheus_client").mkdir()
    (tmp_path / "prometheus_client" / "__init__.py").write_text(
        "def start_http_server(*args, **kwargs):\n"
        "    pass\n"
        "class Counter:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        pass\n"
        "    def labels(self, **kwargs):\n"
        "        class L:\n"
        "            def inc(self, *a, **k):\n"
        "                pass\n"
        "        return L()\n"
        "class Histogram:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        pass\n"
        "    def labels(self, **kwargs):\n"
        "        class L:\n"
        "            def observe(self, *a, **k):\n"
        "                pass\n"
        "        return L()\n"
    )

    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(repo_root)])

    result = subprocess.run(
        [sys.executable, "-m", "agents.finance_advisor"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "event consumed" in result.stdout
