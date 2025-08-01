from __future__ import annotations

import asyncio
from pathlib import Path

from . import CryptoBot
from ..config import Config


async def main() -> None:
    bot = CryptoBot(Config(Path("config.toml")))
    await asyncio.to_thread(bot.run)


if __name__ == "__main__":
    asyncio.run(main())
