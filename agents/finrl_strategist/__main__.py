from __future__ import annotations

import asyncio

from . import FinRLStrategist


async def main() -> None:
    strategist = FinRLStrategist(["SPY"])
    await asyncio.to_thread(strategist.run_weekly)


if __name__ == "__main__":
    asyncio.run(main())
