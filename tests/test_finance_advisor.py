from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.finance_advisor import percentile, percentile_zscore
import pytest


def test_percentile() -> None:
    data = [1, 2, 3, 4, 5]
    assert percentile(data, 50) == 3
    assert percentile(data, 0) == 1
    assert percentile(data, 100) == 5


def test_percentile_empty_list() -> None:
    with pytest.raises(ValueError):
        percentile([], 50)


def test_percentile_negative_numbers() -> None:
    data = [-5, -2, -1]
    assert percentile(data, 50) == -2


def test_percentile_zscore() -> None:
    history = [10, 20, 30, 40, 50]
    value = 60
    score = percentile_zscore(history, value)
    assert score > 0


def test_percentile_zscore_empty_history() -> None:
    assert percentile_zscore([], 10) == 0.0


def test_percentile_zscore_negative_numbers() -> None:
    history = [-30, -20, -10]
    value = -5
    score = percentile_zscore(history, value)
    assert score > 0
