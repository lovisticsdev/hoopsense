"""Offline backtesting entry point for HoopSense model calibration.

This module is intentionally conservative: it does not fetch or mutate data by default.
Use it as the home for historical replay experiments that compare model forecasts against
actual outcomes and baselines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BacktestSummary:
    total: int
    wins: int

    @property
    def accuracy(self) -> float:
        return self.wins / self.total if self.total else 0.0


def summarize_statuses(statuses: Iterable[str]) -> BacktestSummary:
    values = [status.upper() for status in statuses if status.upper() in {"WIN", "LOSS"}]
    return BacktestSummary(total=len(values), wins=values.count("WIN"))


if __name__ == "__main__":
    print("HoopSense backtest scaffold. Add historical replay data before using this for model claims.")
