"""Data integrity and continuity auditor for NEO-WILDER V4.

Feeds V-H01 (DATA_STALE), V-H02 (DATA_GAP), V-H03 (CANDLE_TS_INVALID),
and V-H04 (DUPLICATE_CANDLE) fail-closed.
"""

from dataclasses import dataclass
from typing import List, Optional

from neo_wilder.domain.enums import HardVetoReason
from neo_wilder.domain.models import Candle


@dataclass(frozen=True)
class DataQuality:
    """Result of data integrity inspection."""

    is_valid: bool
    veto_reason: Optional[HardVetoReason] = None
    details: str = ""


class DataIntegrityAuditor:
    """Audits candle stream continuity and freshness."""

    TIMEFRAME_MS = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
    }

    @classmethod
    def audit_candle_series(
        cls,
        candles: List[Candle],
        timeframe: str = "15m",
        now_ms: Optional[int] = None,
        check_freshness: bool = True,
    ) -> DataQuality:
        """Perform comprehensive integrity checks on trailing candles."""
        if not candles:
            return DataQuality(
                is_valid=False,
                veto_reason=HardVetoReason.DATA_STALE,
                details="Candle series is empty",
            )

        interval_ms = cls.TIMEFRAME_MS.get(timeframe, 900_000)

        # 1. Inspect individual candle validity & monotonicity (V-H03, V-H04)
        seen_open_times = set()
        prev_open_ms: Optional[int] = None

        for idx, c in enumerate(candles):
            # Check price validity
            if c.open <= 0 or c.high <= 0 or c.low <= 0 or c.close <= 0:
                return DataQuality(
                    is_valid=False,
                    veto_reason=HardVetoReason.CANDLE_TS_INVALID,
                    details=f"Non-positive price in candle at index {idx}: {c}",
                )

            # Check timestamp geometry (close_time > open_time)
            if c.close_time_ms <= c.open_time_ms:
                return DataQuality(
                    is_valid=False,
                    veto_reason=HardVetoReason.CANDLE_TS_INVALID,
                    details=f"Invalid close/open interval at index {idx}: close {c.close_time_ms} <= open {c.open_time_ms}",
                )

            # Check duplicates (V-H04)
            if c.open_time_ms in seen_open_times:
                return DataQuality(
                    is_valid=False,
                    veto_reason=HardVetoReason.DUPLICATE_CANDLE,
                    details=f"Duplicate open_time_ms detected: {c.open_time_ms}",
                )
            seen_open_times.add(c.open_time_ms)

            # Check monotonicity (V-H03)
            if prev_open_ms is not None and c.open_time_ms <= prev_open_ms:
                return DataQuality(
                    is_valid=False,
                    veto_reason=HardVetoReason.CANDLE_TS_INVALID,
                    details=f"Non-monotonic timestamps: {c.open_time_ms} <= {prev_open_ms}",
                )
            prev_open_ms = c.open_time_ms

        # 2. Inspect gaps in trailing 20 bars (V-H02)
        window = candles[-20:] if len(candles) >= 20 else candles
        for i in range(1, len(window)):
            expected_open = window[i - 1].open_time_ms + interval_ms
            actual_open = window[i].open_time_ms
            if actual_open != expected_open:
                return DataQuality(
                    is_valid=False,
                    veto_reason=HardVetoReason.DATA_GAP,
                    details=f"Data gap detected: bar {i} open {actual_open} != expected {expected_open}",
                )

        # 3. Inspect freshness of the last closed bar (V-H01)
        if check_freshness and now_ms is not None:
            last_candle = candles[-1]
            max_age_ms = 2 * interval_ms + 30_000  # 2*timeframe + 30s
            age_ms = now_ms - last_candle.close_time_ms
            if age_ms > max_age_ms:
                return DataQuality(
                    is_valid=False,
                    veto_reason=HardVetoReason.DATA_STALE,
                    details=f"Last bar is stale: age {age_ms / 1000.0:.1f}s > limit {max_age_ms / 1000.0:.1f}s",
                )

        return DataQuality(is_valid=True)
