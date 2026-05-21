"""Calibration helpers for comparing predicted probabilities with observed outcomes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CalibrationBucket:
    lower: float
    upper: float
    total: int
    wins: int

    @property
    def observed_rate(self) -> float:
        return self.wins / self.total if self.total else 0.0


def bucket_predictions(rows: Iterable[tuple[float, bool]], bucket_size: float = 0.05) -> list[CalibrationBucket]:
    buckets: dict[int, list[bool]] = defaultdict(list)
    for probability, won in rows:
        if not 0.0 <= probability <= 1.0:
            continue
        index = min(int(probability / bucket_size), int(1 / bucket_size) - 1)
        buckets[index].append(bool(won))

    result = []
    for index in sorted(buckets):
        lower = round(index * bucket_size, 4)
        upper = round(lower + bucket_size, 4)
        values = buckets[index]
        result.append(CalibrationBucket(lower=lower, upper=upper, total=len(values), wins=sum(values)))
    return result
