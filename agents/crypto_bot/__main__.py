from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from . import CryptoBot
from ..config import Config


async def _run(cfg_path: Path) -> None:
    bot = CryptoBot(Config(cfg_path))
    await asyncio.to_thread(bot.run)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_PATH", "config.toml"),
        help="Path to configuration file",
    )
    args = parser.parse_args()
    asyncio.run(_run(Path(args.config)))


if __name__ == "__main__":
    main()
