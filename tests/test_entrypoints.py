from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_crypto_bot_entrypoint(tmp_path: Path) -> None:
    # Create minimal config and strategy
    (tmp_path / "config.toml").write_text("[crypto_bot]\nstrategy = 'strategy.yaml'\n")
    (tmp_path / "strategy.yaml").write_text("exchange: binance\n")

    # Stub required external modules
    (tmp_path / "ccxt").mkdir()
    (tmp_path / "ccxt" / "__init__.py").write_text(
        "class binance:\n    def __init__(self, *a, **k):\n        pass\nclass kraken:\n    def __init__(self, *a, **k):\n        pass\n"
    )
    (tmp_path / "freqtrade").mkdir()
    (tmp_path / "freqtrade" / "__init__.py").write_text("")
    (tmp_path / "freqtrade" / "worker.py").write_text(
        "class Worker:\n    def __init__(self, *a, **k):\n        pass\n"
    )
    (tmp_path / "freqtrade" / "configuration.py").write_text(
        "class Configuration:\n    def __init__(self, *a):\n        pass\n    def get_config(self):\n        return {}\n"
    )

    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(repo_root)])

    result = subprocess.run(
        [sys.executable, "-m", "agents.crypto_bot"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_finrl_strategist_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "agents.finrl_strategist"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_eureka_watcher_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "kafka").mkdir()
    (tmp_path / "kafka" / "__init__.py").write_text(
        "class KafkaConsumer:\n    def __init__(self,*a,**k):\n        pass\n    def __iter__(self):\n        class M:\n            def __init__(self,v):\n                self.value=v\n        yield M({'id':'i','vector':[1,0]})\n" "class KafkaProducer:\n    def __init__(self,*a,**k):\n        pass\n    def send(self,*a,**k):\n        pass\n    def flush(self):\n        pass\n"
    )
    (tmp_path / "requests").mkdir()
    (tmp_path / "requests" / "__init__.py").write_text(
        "def post(*a,**k):\n    class R:\n        def raise_for_status(self):\n            pass\n        def json(self):\n            return {'docs':[{'id':'d','vector':[1,0]}]}\n    return R()\n"
    )
    # Stub prometheus_client to avoid starting an HTTP server
    (tmp_path / "prometheus_client").mkdir()
    (tmp_path / "prometheus_client" / "__init__.py").write_text(
        "def start_http_server(*a, **k):\n    pass\nclass Counter:\n    def __init__(self,*a,**k):\n        pass\n    def labels(self, **k):\n        class L:\n            def inc(self,*a,**k):\n                pass\n        return L()\nclass Histogram:\n    def __init__(self,*a,**k):\n        pass\n    def labels(self, **k):\n        class L:\n            def observe(self,*a,**k):\n                pass\n        return L()\n"
    )
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(repo_root)])
    result = subprocess.run(
        [sys.executable, "-m", "agents.eureka_watcher"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
