"""Wilder 14-period RSI and Structural Divergence Engine for NEO-WILDER V4.

Pure, causal, no look-ahead.
Enforces institutional Wilder smoothing identical to Wilder's original 1978 specification.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from neo_wilder.domain.models import Candle, SwingPivot


@dataclass(frozen=True)
class RSIResult:
    """Evaluated RSI metrics and structural divergence."""

    rsi: float
    rsi_series: List[float]
    has_bearish_divergence: bool  # Price HH while RSI LH (LONG danger)
    has_bullish_divergence: bool  # Price LL while RSI HL (SHORT danger)
    is_overbought: bool  # RSI > 70
    is_oversold: bool  # RSI < 30


class RSIEngine:
    """Wilder 14-period Relative Strength Index and divergence detector."""

    @staticmethod
    def compute_rsi(closes: np.ndarray, period: int = 14) -> Optional[np.ndarray]:
        """Compute Wilder's smoothed RSI array."""
        if len(closes) < period + 1:
            return None

        diffs = np.diff(closes)
        gains = np.maximum(diffs, 0.0)
        losses = np.maximum(-diffs, 0.0)

        rsi_array = np.full(len(closes), np.nan, dtype=np.float64)

        # Initial simple average
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        if avg_loss == 0.0:
            rsi_array[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_array[period] = 100.0 - (100.0 / (1.0 + rs))

        # Wilder's exponential smoothing
        for i in range(period, len(diffs)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0.0:
                rsi_array[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_array[i + 1] = 100.0 - (100.0 / (1.0 + rs))

        return rsi_array

    @classmethod
    def evaluate(
        cls,
        candles: List[Candle],
        swings: Optional[List[SwingPivot]] = None,
        period: int = 14,
    ) -> Optional[RSIResult]:
        """Compute current RSI and detect regular divergence against structural swings."""
        if not candles or len(candles) < period + 1:
            return None

        closes = np.array([c.close for c in candles], dtype=np.float64)
        rsi_array = cls.compute_rsi(closes, period=period)
        if rsi_array is None or np.isnan(rsi_array[-1]):
            return None

        current_rsi = float(rsi_array[-1])
        valid_rsi_list = [float(x) for x in rsi_array if not np.isnan(x)]

        has_bearish_div = False
        has_bullish_div = False

        # Structural divergence over swing pivots
        if swings and len(swings) >= 2:
            high_swings = [s for s in swings if s.pivot_type == "HIGH"]
            low_swings = [s for s in swings if s.pivot_type == "LOW"]

            # Bearish Divergence: Price HH, RSI LH
            if len(high_swings) >= 2:
                s_prev = high_swings[-2]
                s_curr = high_swings[-1]
                idx_prev = s_prev.bar_index
                idx_curr = s_curr.bar_index

                if 0 <= idx_prev < len(rsi_array) and 0 <= idx_curr < len(rsi_array):
                    rsi_prev = rsi_array[idx_prev]
                    rsi_curr = rsi_array[idx_curr]
                    if not np.isnan(rsi_prev) and not np.isnan(rsi_curr):
                        # Price higher high but RSI lower high
                        if s_curr.price > s_prev.price and rsi_curr < rsi_prev:
                            has_bearish_div = True

            # Bullish Divergence: Price LL, RSI HL
            if len(low_swings) >= 2:
                s_prev = low_swings[-2]
                s_curr = low_swings[-1]
                idx_prev = s_prev.bar_index
                idx_curr = s_curr.bar_index

                if 0 <= idx_prev < len(rsi_array) and 0 <= idx_curr < len(rsi_array):
                    rsi_prev = rsi_array[idx_prev]
                    rsi_curr = rsi_array[idx_curr]
                    if not np.isnan(rsi_prev) and not np.isnan(rsi_curr):
                        # Price lower low but RSI higher low
                        if s_curr.price < s_prev.price and rsi_curr > rsi_prev:
                            has_bullish_div = True

        return RSIResult(
            rsi=current_rsi,
            rsi_series=valid_rsi_list,
            has_bearish_divergence=has_bearish_div,
            has_bullish_divergence=has_bullish_div,
            is_overbought=current_rsi > 70.0,
            is_oversold=current_rsi < 30.0,
        )
