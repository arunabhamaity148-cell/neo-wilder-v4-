"""S1: SWEEP-RECLAIM-v4 strategy engine (active spine).

In strict compliance with KNOWN_LIMITATIONS.md, SHORT candidate generation
is disabled fail-closed. Emits candidates exclusively for research-supported
LONG setups.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class S1SweepReclaimStrategy(BaseStrategy):
    """Active spine strategy generating Sweep-Reclaim candidates."""

    def __init__(self, baseline_friction_pct: float = 0.1354):
        super().__init__("S1_SWEEP_RECLAIM")
        self.baseline_friction_pct = baseline_friction_pct

    def generate_candidate(
        self,
        ctx: FeatureContext,
        edge_results: Dict[str, EdgeResult],
    ) -> Optional[Candidate]:
        # 1. Regime Eligibility Gate
        regime = ctx.regime_output.state if ctx.regime_output else RegimeState.NEUTRAL
        if regime in (RegimeState.NOISE_CHOP, RegimeState.LIQUIDITY_STRESS):
            return None

        # 2. Check S1 Setup Edge (E01)
        e01 = edge_results.get("E01")
        if not e01 or not e01.passed:
            return None

        # Fail-closed boundary: SHORT is disabled
        if e01.direction != Direction.LONG:
            return None

        if not ctx.candles or not ctx.atr_result:
            return None

        curr_bar = ctx.candles[-1]
        atr = ctx.atr_result.atr
        pool_level = e01.metadata.get("pool_level", curr_bar.close)
        sweep_low = e01.metadata.get("sweep_low", curr_bar.low)

        # 3. Confirmation Requirement (at least 1 must pass)
        # Options: (a) Structure Shift E05, (b) Displacement body > 0.6 ATR, (c) Relative volume > 1.2x median
        e05 = edge_results.get("E05")
        has_structure_shift = e05.passed if e05 else False

        real_body = abs(curr_bar.close - curr_bar.open)
        has_displacement = real_body > (0.60 * atr)

        x02 = edge_results.get("X02")
        has_vol_spike = x02.passed if x02 else False

        if not (has_structure_shift or has_displacement or has_vol_spike):
            return None

        # 4. Entry Zone Geometry
        # Reference price is strictly the reclaim bar close
        ref_price = curr_bar.close
        zone_low = min(ref_price, pool_level)
        zone_high = ref_price

        # Widen to minimum width: max(0.20%, 0.05 ATR)
        min_width = max(0.0020 * ref_price, 0.05 * atr)
        if (zone_high - zone_low) < min_width:
            zone_low = zone_high - min_width

        # 5. Stop Loss Geometry
        # Stop = sweep_extreme - buffer * ATR
        e12 = edge_results.get("E12")
        buffer_mult = e12.metadata.get("buffer_multiplier", 2.2) if e12 else 2.2
        stop_loss = sweep_low - (buffer_mult * atr)
        stop_dist = ref_price - stop_loss

        # Bounds: max(0.65%, 0.5 ATR) <= stop_dist <= 4.5 ATR
        min_stop_dist = max(0.0065 * ref_price, 0.50 * atr)
        max_stop_dist = 4.50 * atr
        if not (min_stop_dist <= stop_dist <= max_stop_dist):
            return None

        # 6. Take Profit TP1 Selection (Structural Target)
        # Nearest opposing structural level that gives Net R:R >= 1.50
        opposing_levels = []
        for s in ctx.swings:
            if s.pivot_type == "HIGH" and s.price > ref_price:
                opposing_levels.append(s.price)

        if ctx.volume_profile:
            if ctx.volume_profile.vah > ref_price:
                opposing_levels.append(ctx.volume_profile.vah)
            if ctx.volume_profile.poc > ref_price:
                opposing_levels.append(ctx.volume_profile.poc)

        opposing_levels = sorted(list(set(opposing_levels)))

        valid_tp1 = None
        best_net_rr = 0.0
        best_gross_rr = 0.0

        for level in opposing_levels:
            gross_reward = level - ref_price
            gross_rr = gross_reward / stop_dist if stop_dist > 0 else 0.0

            # Approximate friction in R: total friction pct * price / stop_dist
            friction_r = (self.baseline_friction_pct / 100.0 * ref_price) / stop_dist
            net_rr = gross_rr - friction_r

            if net_rr >= 1.50:
                valid_tp1 = level
                best_gross_rr = gross_rr
                best_net_rr = net_rr
                break

        # Tautology elimination: If no structural level provides Net R:R >= 1.50, trade is NOT taken
        if valid_tp1 is None:
            return None

        # 7. Expiry Bars
        e28 = edge_results.get("E28")
        expiry_bars = e28.metadata.get("expiry_bars", 16) if e28 else 16

        # Active & Confirming Edge Lists
        active_edges = ["E01", "E04", "E11", "E12"]
        confirming_edges = []
        if has_structure_shift:
            confirming_edges.append("E05")
        if has_vol_spike:
            confirming_edges.append("X02")

        now_utc = datetime.now(timezone.utc).isoformat()

        return Candidate(
            symbol=ctx.symbol,
            direction=Direction.LONG,
            strategy_id=self.strategy_id,
            setup_edge_id="E01",
            reference_price=ref_price,
            entry_zone_low=zone_low,
            entry_zone_high=zone_high,
            stop_loss=stop_loss,
            tp1=valid_tp1,
            tp2=None,  # Unresolved reference anchor per KNOWN_LIMITATIONS.md
            gross_rr=round(best_gross_rr, 2),
            net_rr=round(best_net_rr, 2),
            active_edge_ids=active_edges,
            confirming_edge_ids=confirming_edges,
            expiry_bars=int(expiry_bars),
            regime=regime,
            created_at_utc=now_utc,
        )
