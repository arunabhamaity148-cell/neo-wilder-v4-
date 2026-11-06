"""CoinDCX public execution validation engine for NEO-WILDER V4.

Conforms strictly to COINDCX_MANUAL_EXECUTION_SPEC.md §3 and §4:
- Evaluates live prices, spread, and top-10 depth against publication gates.
- Enforces V-H31, V-H32, V-H33, and V-H34 fail-closed gates.
- Calculates exact CoinDCX round-trip friction (0.050% taker + 18% GST + slippage).
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from neo_wilder.domain.enums import SymbolTier
from neo_wilder.domain.models import CoinDCXQuote

logger = logging.getLogger(__name__)

# Default Constants per spec
TAKER_FEE_PCT_PER_SIDE = 0.050  # 0.050%
GST_RATE = 0.18  # 18%
BASELINE_SLIPPAGE_PCT = 0.0174  # 0.0174%
MAX_DRIFT_PCT = 0.35  # 0.35%
MAX_SPREAD_BPS_MAJOR = 12.0  # 12.0 bps
MAX_SPREAD_BPS_ALT = 25.0  # 25.0 bps
DEPTH_CLIP_MULTIPLIER = 20.0  # 20x intended clip
LATE_ENTRY_MAX_PROGRESS = 0.35  # 35% progress to TP1


@dataclass
class ValidationResult:
    is_valid: bool
    veto_id: Optional[str] = None
    reason: Optional[str] = None
    drift_pct: float = 0.0
    fee_pct: float = 0.1180
    slippage_pct: float = BASELINE_SLIPPAGE_PCT
    total_friction_pct: float = 0.1354


class CoinDCXExecutionValidator:
    """Validates trade candidate against live CoinDCX public market conditions."""

    def __init__(
        self,
        default_clip_usd: float = 1000.0,
        max_drift_pct: float = MAX_DRIFT_PCT,
        max_spread_major: float = MAX_SPREAD_BPS_MAJOR,
        max_spread_alt: float = MAX_SPREAD_BPS_ALT,
    ):
        self.default_clip_usd = default_clip_usd
        self.max_drift_pct = max_drift_pct
        self.max_spread_major = max_spread_major
        self.max_spread_alt = max_spread_alt

    @staticmethod
    def calculate_friction(
        clip_usd: float = 1000.0, top10_depth_usd: float = 100000.0
    ) -> Tuple[float, float, float]:
        """Calculate round-trip taker fee + 18% GST and dynamic slippage.

        Returns (round_trip_fee_pct, slippage_pct, total_friction_pct).
        """
        # Taker fee with GST per side: 0.050% * 1.18 = 0.0590%
        fee_per_side = TAKER_FEE_PCT_PER_SIDE * (1.0 + GST_RATE)
        round_trip_fee_pct = fee_per_side * 2.0  # 0.1180%

        # Dynamic slippage based on clip vs depth
        if top10_depth_usd > 0:
            participation_ratio = clip_usd / top10_depth_usd
            slippage_pct = max(
                BASELINE_SLIPPAGE_PCT, BASELINE_SLIPPAGE_PCT * (1.0 + participation_ratio * 5.0)
            )
        else:
            slippage_pct = BASELINE_SLIPPAGE_PCT

        total_friction_pct = round_trip_fee_pct + slippage_pct
        return round_trip_fee_pct, slippage_pct, total_friction_pct

    def validate_candidate(
        self,
        reference_price: float,
        entry_zone_low: float,
        entry_zone_high: float,
        tp1: float,
        quote: Optional[CoinDCXQuote],
        symbol_tier: SymbolTier = SymbolTier.MAJOR,
        intended_clip_usd: Optional[float] = None,
    ) -> ValidationResult:
        """Evaluate live CoinDCX quote against publication criteria.

        Fail-closed: if quote is missing or any parameter breached, signal is blocked.
        """
        clip = intended_clip_usd if intended_clip_usd is not None else self.default_clip_usd

        # Gate 1: Quote availability (V-H31)
        if quote is None or quote.price <= 0.0:
            return ValidationResult(
                is_valid=False,
                veto_id="V_H31",
                reason="CoinDCX live quote is unavailable or non-positive (fail-closed)",
            )

        fee_pct, slippage_pct, total_friction = self.calculate_friction(clip, quote.top10_depth_usd)

        # Gate 2: Price drift against reference close (V-H32)
        drift_pct = abs(quote.price - reference_price) / max(reference_price, 1e-8) * 100.0
        if drift_pct > self.max_drift_pct:
            return ValidationResult(
                is_valid=False,
                veto_id="V_H32",
                reason=f"CoinDCX price drift ({drift_pct:.3f}%) exceeds limit {self.max_drift_pct}%",
                drift_pct=drift_pct,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct,
                total_friction_pct=total_friction,
            )

        # Gate 3: Bid-ask spread (V-H33)
        max_spread = (
            self.max_spread_major if symbol_tier == SymbolTier.MAJOR else self.max_spread_alt
        )
        if quote.spread_bps > max_spread:
            return ValidationResult(
                is_valid=False,
                veto_id="V_H33",
                reason=f"CoinDCX spread ({quote.spread_bps:.1f} bps) exceeds {max_spread:.1f} bps",
                drift_pct=drift_pct,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct,
                total_friction_pct=total_friction,
            )

        # Gate 4: Orderbook depth (V-H34)
        required_depth = clip * DEPTH_CLIP_MULTIPLIER
        if quote.top10_depth_usd < required_depth:
            return ValidationResult(
                is_valid=False,
                veto_id="V_H34",
                reason=f"CoinDCX top-10 depth (${quote.top10_depth_usd:,.0f}) < required ${required_depth:,.0f} (20x clip)",
                drift_pct=drift_pct,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct,
                total_friction_pct=total_friction,
            )

        # Gate 5: Late-entry progress check (must not have progressed > 35% toward TP1)
        total_target_distance = tp1 - entry_zone_low
        if total_target_distance > 0:
            current_progress = (quote.price - entry_zone_low) / total_target_distance
            if current_progress > LATE_ENTRY_MAX_PROGRESS:
                return ValidationResult(
                    is_valid=False,
                    veto_id="V_H30",  # Stale/late entry geometry
                    reason=f"CoinDCX price already advanced {current_progress * 100:.1f}% toward TP1 (max {LATE_ENTRY_MAX_PROGRESS * 100:.0f}%)",
                    drift_pct=drift_pct,
                    fee_pct=fee_pct,
                    slippage_pct=slippage_pct,
                    total_friction_pct=total_friction,
                )

        return ValidationResult(
            is_valid=True,
            drift_pct=drift_pct,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
            total_friction_pct=total_friction,
        )
