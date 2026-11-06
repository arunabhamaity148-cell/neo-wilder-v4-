"""Top-10 Order Book Imbalance (OBI) calculation (E16)."""

from dataclasses import dataclass
from typing import Optional

from neo_wilder.domain.models import OrderBookSnapshot


@dataclass(frozen=True)
class OBIResult:
    """Calculated Order Book Imbalance."""

    obi: float  # -1.0 (all ask) to +1.0 (all bid)
    total_depth_bids: float
    total_depth_asks: float


class OBIEngine:
    """Computes top-10 Order Book Imbalance ratio."""

    @staticmethod
    def compute(snapshot: OrderBookSnapshot, levels: int = 10) -> Optional[OBIResult]:
        if not snapshot.bids or not snapshot.asks:
            return None

        bid_qty = sum(b.quantity for b in snapshot.bids[:levels])
        ask_qty = sum(a.quantity for a in snapshot.asks[:levels])
        denom = bid_qty + ask_qty

        if denom <= 0:
            return OBIResult(obi=0.0, total_depth_bids=0.0, total_depth_asks=0.0)

        obi = (bid_qty - ask_qty) / denom

        return OBIResult(
            obi=float(obi),
            total_depth_bids=float(bid_qty),
            total_depth_asks=float(ask_qty),
        )
