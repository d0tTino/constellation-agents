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
