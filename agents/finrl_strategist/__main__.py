from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from . import main
from ..config import Config


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_PATH", "config.toml"),
        help="Path to configuration file",
    )
    return parser.parse_args()


def entrypoint() -> None:
    args = cli()
    cfg_path = Path(args.config)
    cfg = Config(cfg_path) if cfg_path.exists() else None
    import agents.finrl_strategist as module
    asyncio.run(main(cfg))


if __name__ == "__main__":
    entrypoint()
