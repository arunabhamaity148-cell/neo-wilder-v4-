"""Market structure shift detector (BOS and CHoCH) for NEO-WILDER V4 (E05)."""

from dataclasses import dataclass
from typing import List, Optional

from neo_wilder.domain.models import Candle, SwingPivot


@dataclass(frozen=True)
class StructureState:
    """Structure shift assessment."""

    has_bullish_bos: bool
    has_bearish_bos: bool
    has_bullish_choch: bool
    has_bearish_choch: bool
    last_broken_pivot: Optional[SwingPivot] = None


class StructureDetector:
    """Detects Break of Structure and Change of Character."""

    @staticmethod
    def detect_shift(candles: List[Candle], swings: List[SwingPivot]) -> StructureState:
        if not candles or not swings:
            return StructureState(False, False, False, False)

        curr_candle = candles[-1]
        prev_candle = candles[-2] if len(candles) >= 2 else curr_candle

        high_swings = [s for s in swings if s.pivot_type == "HIGH" and s.index < len(candles) - 1]
        low_swings = [s for s in swings if s.pivot_type == "LOW" and s.index < len(candles) - 1]

        last_high = high_swings[-1] if high_swings else None
        last_low = low_swings[-1] if low_swings else None

        bullish_bos = False
        bearish_bos = False
        bullish_choch = False
        bearish_choch = False
        broken_pivot = None

        # Bullish break: close breaks above prior swing high
        if last_high and curr_candle.close > last_high.price >= prev_candle.close:
            bullish_bos = True
            broken_pivot = last_high
            # Check if previous context was series of lower highs -> CHoCH
            if len(high_swings) >= 2 and high_swings[-1].price < high_swings[-2].price:
                bullish_choch = True

        # Bearish break: close breaks below prior swing low
        if last_low and curr_candle.close < last_low.price <= prev_candle.close:
            bearish_bos = True
            broken_pivot = last_low
            # Check if previous context was series of higher lows -> CHoCH
            if len(low_swings) >= 2 and low_swings[-1].price > low_swings[-2].price:
                bearish_choch = True

        return StructureState(
            has_bullish_bos=bullish_bos,
            has_bearish_bos=bearish_bos,
            has_bullish_choch=bullish_choch,
            has_bearish_choch=bearish_choch,
            last_broken_pivot=broken_pivot,
        )
