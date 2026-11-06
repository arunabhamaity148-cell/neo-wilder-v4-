"""Wilder 14-period True Range and ATR calculations for NEO-WILDER V4.

Pure, causal, no look-ahead.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from neo_wilder.domain.models import Candle


@dataclass(frozen=True)
class ATRResult:
    """ATR computation output."""

    atr: float
    atr_bps: float
    vol_tier: int  # 0: Low, 1: Normal, 2: High, 3: Extreme
    trailing_100_atr: List[float]


class ATREngine:
    """Computes Wilder's ATR over closed candles."""

    @staticmethod
    def compute(candles: List[Candle], period: int = 14) -> Optional[ATRResult]:
        if len(candles) < period + 1:
            return None

        closes = np.array([c.close for c in candles], dtype=np.float64)
        highs = np.array([c.high for c in candles], dtype=np.float64)
        lows = np.array([c.low for c in candles], dtype=np.float64)

        # True Range: max(H - L, abs(H - C_prev), abs(L - C_prev))
        hl = highs[1:] - lows[1:]
        hc = np.abs(highs[1:] - closes[:-1])
        lc = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(hl, np.maximum(hc, lc))

        if len(tr) < period:
            return None

        # Initial simple average of first `period` true ranges
        atr_series = np.zeros(len(tr), dtype=np.float64)
        atr_series[period - 1] = np.mean(tr[:period])

        # Wilder's smoothing: ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period
        for i in range(period, len(tr)):
            atr_series[i] = (atr_series[i - 1] * (period - 1) + tr[i]) / period

        current_atr = float(atr_series[-1])
        current_close = float(closes[-1])
        atr_bps = (current_atr / current_close) * 10000.0 if current_close > 0 else 0.0

        # Trailing 100 ATRs for dynamic stop alpha percentile
        trailing_atrs = [float(x) for x in atr_series[max(0, len(atr_series) - 100) :]]

        # Volatility tier based on trailing percentiles
        p30 = float(np.percentile(trailing_atrs, 30))
        p80 = float(np.percentile(trailing_atrs, 80))

        if current_atr < p30:
            vol_tier = 0  # Low
        elif current_atr <= p80:
            vol_tier = 1  # Normal
        else:
            vol_tier = 2  # High

        return ATRResult(
            atr=current_atr,
            atr_bps=atr_bps,
            vol_tier=vol_tier,
            trailing_100_atr=trailing_atrs,
        )
