from __future__ import annotations

import asyncio

from . import FinRLStrategist


async def _run() -> None:
    strategist = FinRLStrategist(["SPY"])
    await asyncio.to_thread(strategist.run_weekly)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
