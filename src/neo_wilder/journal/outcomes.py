"""Signal outcome resolution engine for NEO-WILDER V4.

Evaluates open signals against sequential incoming candles.
Enforces the mandatory conservative intrabar ambiguity rule:
if both SL and TP are touched in the same bar, SL_HIT takes precedence.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from neo_wilder.data.store import DatabaseStore
from neo_wilder.domain.models import Candle
from neo_wilder.publish.schema import Signal

logger = logging.getLogger(__name__)


@dataclass
class SignalTracker:
    signal: Signal
    is_filled: bool
    fill_price: float
    bars_active: int = 0


class OutcomeResolver:
    """Evaluates and persists trade outcomes on candle stream."""

    def __init__(self, store: DatabaseStore, max_entry_window_bars: int = 4):
        self.store = store
        self.max_entry_window_bars = max_entry_window_bars
        # signal_id -> SignalTracker
        self._active_trackers: Dict[str, SignalTracker] = {}

    def track_signal(
        self, signal: Signal, is_filled: bool = False, fill_price: Optional[float] = None
    ):
        """Register a newly published signal for outcome resolution."""
        price = fill_price if fill_price is not None else signal.reference_price
        self._active_trackers[signal.signal_id] = SignalTracker(
            signal=signal,
            is_filled=is_filled,
            fill_price=price,
            bars_active=0,
        )

    def mark_filled(self, signal_id: str, fill_price: float):
        """Update tracker when operator reports a manual fill."""
        if signal_id in self._active_trackers:
            tracker = self._active_trackers[signal_id]
            tracker.is_filled = True
            tracker.fill_price = fill_price

    async def on_candle(self, symbol: str, candle: Candle) -> List[Dict[str, str]]:
        """Process incoming candle for open signals of the specified symbol.

        Returns list of resolved outcome summaries.
        """
        resolved_summaries = []
        to_remove = []

        for sig_id, tracker in list(self._active_trackers.items()):
            sig = tracker.signal
            if sig.symbol_binance != symbol:
                continue

            tracker.bars_active += 1

            # Check if entry window expired without fill
            if not tracker.is_filled and tracker.bars_active > self.max_entry_window_bars:
                # Mark as MISSED
                now_str = datetime.now(timezone.utc).isoformat()
                await self.store.record_outcome(
                    signal_id=sig_id,
                    resolved_status="MISSED",
                    exit_price=None,
                    realized_r=0.0,
                    resolution_time_utc=now_str,
                )
                resolved_summaries.append({"signal_id": sig_id, "status": "MISSED", "r": "0.0"})
                to_remove.append(sig_id)
                continue

            entry_price = tracker.fill_price
            sl = sig.stop_loss
            tp1 = sig.tp1

            # Only LONG is active in S1
            if sig.direction.value == "LONG":
                risk_dist = entry_price - sl
                if risk_dist <= 0:
                    risk_dist = sig.reference_price - sl

                hit_sl = candle.low <= sl
                hit_tp1 = candle.high >= tp1

                # CONSERVATIVE INTRABAR AMBIGUITY RULE:
                # If both SL and TP are hit in the same bar, SL_HIT MUST take precedence!
                if hit_sl and hit_tp1:
                    resolved_status = "SL_HIT"
                    exit_price = sl
                    realized_r = -1.0
                elif hit_sl:
                    resolved_status = "SL_HIT"
                    exit_price = sl
                    realized_r = -1.0
                elif hit_tp1:
                    resolved_status = "TP1_HIT"
                    exit_price = tp1
                    reward_dist = tp1 - entry_price
                    realized_r = reward_dist / max(risk_dist, 1e-8)
                else:
                    resolved_status = None
                    exit_price = None
                    realized_r = None

                if resolved_status is not None:
                    now_str = datetime.now(timezone.utc).isoformat()
                    await self.store.record_outcome(
                        signal_id=sig_id,
                        resolved_status=resolved_status,
                        exit_price=exit_price,
                        realized_r=realized_r,
                        resolution_time_utc=now_str,
                    )
                    resolved_summaries.append(
                        {
                            "signal_id": sig_id,
                            "status": resolved_status,
                            "r": f"{realized_r:.2f}",
                        }
                    )
                    to_remove.append(sig_id)
                    continue

            # Check for general expiry (e.g. max active holding bars = 48)
            if tracker.bars_active >= 48:
                now_str = datetime.now(timezone.utc).isoformat()
                await self.store.record_outcome(
                    signal_id=sig_id,
                    resolved_status="EXPIRED",
                    exit_price=candle.close,
                    realized_r=0.0,
                    resolution_time_utc=now_str,
                )
                resolved_summaries.append({"signal_id": sig_id, "status": "EXPIRED", "r": "0.0"})
                to_remove.append(sig_id)

        for sig_id in to_remove:
            self._active_trackers.pop(sig_id, None)

        return resolved_summaries
