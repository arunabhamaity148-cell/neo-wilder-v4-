"""Causal structural swing pivot identification for NEO-WILDER V4.

Identifies swing highs and lows strictly at bar close without future leak.
"""

from typing import List

from neo_wilder.domain.models import Candle, SwingPivot


class SwingDetector:
    """Detects causal swing highs and lows."""

    @staticmethod
    def find_swings(
        candles: List[Candle], left_bars: int = 3, right_bars: int = 1
    ) -> List[SwingPivot]:
        """Identify confirmed swing pivots in the candle series.

        At bar `t`, a pivot at index `i = t - right_bars` is confirmed if it exceeds
        the `left_bars` prior to it and `right_bars` after it.
        """
        pivots: List[SwingPivot] = []
        n = len(candles)
        if n < left_bars + right_bars + 1:
            return pivots

        for i in range(left_bars, n - right_bars):
            curr_candle = candles[i]
            # Check Swing High
            left_highs = [candles[j].high for j in range(i - left_bars, i)]
            right_highs = [candles[j].high for j in range(i + 1, i + right_bars + 1)]

            if curr_candle.high > max(left_highs) and curr_candle.high >= max(right_highs):
                pivots.append(
                    SwingPivot(
                        index=i,
                        timestamp_ms=curr_candle.open_time_ms,
                        price=curr_candle.high,
                        pivot_type="HIGH",
                    )
                )

            # Check Swing Low
            left_lows = [candles[j].low for j in range(i - left_bars, i)]
            right_lows = [candles[j].low for j in range(i + 1, i + right_bars + 1)]

            if curr_candle.low < min(left_lows) and curr_candle.low <= min(right_lows):
                pivots.append(
                    SwingPivot(
                        index=i,
                        timestamp_ms=curr_candle.open_time_ms,
                        price=curr_candle.low,
                        pivot_type="LOW",
                    )
                )

        return pivots

    # Alias to support both naming conventions from audit specifications
    find_swing_pivots = find_swings
