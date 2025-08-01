from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.finance_advisor import percentile, percentile_zscore


def test_percentile() -> None:
    data = [1, 2, 3, 4, 5]
    assert percentile(data, 50) == 3
    assert percentile(data, 0) == 1
    assert percentile(data, 100) == 5


def test_percentile_zscore() -> None:
    history = [10, 20, 30, 40, 50]
    value = 60
    score = percentile_zscore(history, value)
    assert score > 0
