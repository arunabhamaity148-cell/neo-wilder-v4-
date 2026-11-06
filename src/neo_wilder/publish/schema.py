"""Canonical, immutable Signal schema for NEO-WILDER V4.

Every field is mandatory and validated at creation.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from neo_wilder.domain.enums import Direction, RegimeState


@dataclass(frozen=True)
class Signal:
    """Immutable published signal dataclass conforming to COINDCX_MANUAL_EXECUTION_SPEC.md §3."""

    # Identifiers & Timestamps
    signal_id: str
    created_at_utc: str
    expires_at_utc: str

    # Instruments & Setup
    symbol_binance: str
    symbol_coindcx: str
    direction: Direction
    strategy_id: str
    active_edge_ids: List[str]
    confirming_edge_ids: List[str]

    # Execution & Reference Geometry
    reference_price: float
    coindcx_price: float
    coindcx_spread_bps: float
    coindcx_top10_depth_usd: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: Optional[float]

    # Risk & Friction Model
    gross_rr: float
    fee_pct: float
    slippage_pct: float
    funding_pct_est: float
    net_rr: float

    # Scoring & Calibration
    score_0_100: int
    calibrated_probability: str  # e.g. "NOT CALIBRATED" or "0.642"

    # Context & Vetoes
    regime: RegimeState
    btc_context: str
    veto_status: str  # "PASSED"
    soft_veto_list: List[str]
    max_entry_drift_pct: float  # fixed at 0.35
    invalidation_conditions: List[str]
    one_paragraph_thesis: str  # Bengali rationale + English identifiers

    def __post_init__(self):
        """Strict validation of signal fields."""
        if not (0 <= self.score_0_100 <= 100):
            raise ValueError(f"Score must be between 0 and 100: {self.score_0_100}")
        if self.net_rr < 1.50:
            raise ValueError(f"Net R:R must be >= 1.50: {self.net_rr}")
        if self.entry_zone_low > self.entry_zone_high:
            raise ValueError(
                f"Inverted entry zone: low {self.entry_zone_low} > high {self.entry_zone_high}"
            )
        if self.max_entry_drift_pct != 0.35:
            raise ValueError(f"max_entry_drift_pct must be 0.35, got {self.max_entry_drift_pct}")
        if len(self.one_paragraph_thesis) > 350:
            raise ValueError("one_paragraph_thesis exceeds maximum length")

    def to_dict(self) -> Dict[str, Any]:
        """Convert frozen dataclass to serializable dictionary."""
        d = asdict(self)
        d["direction"] = self.direction.value
        d["regime"] = self.regime.value
        return d
