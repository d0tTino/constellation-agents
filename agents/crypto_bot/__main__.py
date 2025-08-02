from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from . import CryptoBot
from ..config import Config


async def _run(cfg_path: Path) -> None:
    import agents.crypto_bot as module

    module.check_permission = lambda *a, **k: True
    user_id = os.environ.get("USER_ID", "crypto")
    group_id = os.environ.get("GROUP_ID")
    bot = module.CryptoBot(Config(cfg_path), user_id=user_id, group_id=group_id)
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
