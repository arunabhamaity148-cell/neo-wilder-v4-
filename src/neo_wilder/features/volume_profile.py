"""Session Volume Profile (POC, VAH, VAL) calculation for NEO-WILDER V4 (E07).

Causal, pure numpy calculation.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from neo_wilder.domain.models import Candle


@dataclass(frozen=True)
class VolumeProfileLevels:
    """Calculated volume profile structural levels."""

    poc: float  # Point of Control
    vah: float  # Value Area High (70%)
    val: float  # Value Area Low (70%)
    total_volume: float


class VolumeProfileEngine:
    """Computes Point of Control and Value Area boundaries."""

    @staticmethod
    def compute(
        candles: List[Candle], bins: int = 50, value_area_pct: float = 0.70
    ) -> Optional[VolumeProfileLevels]:
        if not candles:
            return None

        # Sample price range across candles
        highs = np.array([c.high for c in candles], dtype=np.float64)
        lows = np.array([c.low for c in candles], dtype=np.float64)
        closes = np.array([c.close for c in candles], dtype=np.float64)
        volumes = np.array([c.volume for c in candles], dtype=np.float64)

        min_price = float(np.min(lows))
        max_price = float(np.max(highs))
        total_vol = float(np.sum(volumes))

        if min_price >= max_price or total_vol <= 0:
            return None

        # Bin prices and distribute volume evenly across bar range
        bin_edges = np.linspace(min_price, max_price, bins + 1)
        bin_mids = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        bin_volumes = np.zeros(bins, dtype=np.float64)

        for i in range(len(candles)):
            c_low = lows[i]
            c_high = highs[i]
            c_vol = volumes[i]
            # Identify which bins overlap this bar
            mask = (bin_mids >= c_low) & (bin_mids <= c_high)
            n_overlap = np.sum(mask)
            if n_overlap > 0:
                bin_volumes[mask] += c_vol / n_overlap
            else:
                # If bar range is smaller than a bin, assign to closest bin
                closest_idx = int(np.argmin(np.abs(bin_mids - closes[i])))
                bin_volumes[closest_idx] += c_vol

        # 1. Point of Control (POC)
        poc_idx = int(np.argmax(bin_volumes))
        poc_price = float(bin_mids[poc_idx])

        # 2. Value Area (70% of total volume) expanding outward from POC
        target_vol = total_vol * value_area_pct
        accumulated_vol = bin_volumes[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx

        while accumulated_vol < target_vol and (low_idx > 0 or high_idx < bins - 1):
            next_low_vol = bin_volumes[low_idx - 1] if low_idx > 0 else -1.0
            next_high_vol = bin_volumes[high_idx + 1] if high_idx < bins - 1 else -1.0

            if next_low_vol >= next_high_vol and low_idx > 0:
                low_idx -= 1
                accumulated_vol += bin_volumes[low_idx]
            elif high_idx < bins - 1:
                high_idx += 1
                accumulated_vol += bin_volumes[high_idx]
            else:
                break

        val_price = float(bin_mids[low_idx])
        vah_price = float(bin_mids[high_idx])

        return VolumeProfileLevels(
            poc=poc_price,
            vah=vah_price,
            val=val_price,
            total_volume=total_vol,
        )
