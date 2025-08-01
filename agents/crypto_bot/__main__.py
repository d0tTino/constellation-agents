from __future__ import annotations

import asyncio
from pathlib import Path

from . import CryptoBot
from ..config import Config


async def _run() -> None:
    bot = CryptoBot(Config(Path("config.toml")))
    await asyncio.to_thread(bot.run)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
