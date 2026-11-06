"""Cumulative Volume Delta (CVD) tracking and turn detection (E15)."""

from dataclasses import dataclass
from typing import Deque, List, Optional

import numpy as np

from neo_wilder.domain.models import AggTrade


@dataclass(frozen=True)
class CVDResult:
    """Evaluated CVD status."""

    total_delta: float
    slope: float
    has_turned_bullish: bool  # Inflection from selling to buying
    has_turned_bearish: bool  # Inflection from buying to selling


class CVDEngine:
    """Computes Cumulative Volume Delta from aggressive trade ticks."""

    @staticmethod
    def compute(
        trades: List[AggTrade] | Deque[AggTrade], window_size: int = 1000
    ) -> Optional[CVDResult]:
        if not trades or len(trades) < 20:
            return None

        # Sample recent trades up to window_size
        trade_slice = list(trades)[-window_size:]
        deltas = np.zeros(len(trade_slice), dtype=np.float64)

        for i, t in enumerate(trade_slice):
            # is_buyer_maker=True means market sell (seller crossed spread)
            # is_buyer_maker=False means market buy (buyer crossed spread)
            qty = t.quantity
            deltas[i] = -qty if t.is_buyer_maker else qty

        cumulative = np.cumsum(deltas)
        total_delta = float(cumulative[-1])

        # Compute slope over recent 20% vs preceding 40%
        n = len(cumulative)
        mid = int(n * 0.7)
        slope_recent = float(cumulative[-1] - cumulative[mid])
        slope_prior = float(cumulative[mid] - cumulative[0])

        # Bullish turn: prior was negative or flat, recent is positive
        turned_bullish = slope_prior <= 0 and slope_recent > 0
        turned_bearish = slope_prior >= 0 and slope_recent < 0

        return CVDResult(
            total_delta=total_delta,
            slope=slope_recent,
            has_turned_bullish=turned_bullish,
            has_turned_bearish=turned_bearish,
        )
