from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.config import Config


def test_load_and_get(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("a = 1\n[b]\nc = 'd'")

    cfg = Config(config_file)

    assert cfg.get("a") == 1
    assert cfg.get("b") == {"c": "d"}
