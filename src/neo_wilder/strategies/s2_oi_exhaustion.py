"""S2: OI-EXHAUSTION-v4 strategy engine (SHADOW).

Evaluated for internal telemetry and backtesting only.
Cannot fire within 30 min of S1 on the same symbol.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.strategies.base import BaseStrategy


class S2OIExhaustionStrategy(BaseStrategy):
    """Shadow strategy for Open Interest exhaustion reversals."""

    def __init__(self):
        super().__init__("S2_OI_EXHAUSTION")

    def generate_candidate(
        self,
        ctx: FeatureContext,
        edge_results: Dict[str, EdgeResult],
    ) -> Optional[Candidate]:
        # S2 is LONG only in v4.0
        # Mandatory: E21 (OI drop) + E15 (CVD turn) + E13 (Z_liq >= 2.0)
        e21 = edge_results.get("E21")
        e15 = edge_results.get("E15")
        e13 = edge_results.get("E13")

        if not (e21 and e21.passed and e15 and e15.passed and e13 and e13.passed):
            return None

        if not ctx.candles or not ctx.atr_result:
            return None

        curr_bar = ctx.candles[-1]
        atr = ctx.atr_result.atr
        stop_loss = curr_bar.low - (1.0 * atr)

        # TP1 = prior 1h swing high
        high_swings = [
            s.price for s in ctx.swings if s.pivot_type == "HIGH" and s.price > curr_bar.close
        ]
        if not high_swings:
            return None

        tp1 = min(high_swings)
        stop_dist = curr_bar.close - stop_loss
        if stop_dist <= 0:
            return None

        gross_rr = (tp1 - curr_bar.close) / stop_dist
        if gross_rr < 1.60:  # Ensures net R:R >= 1.50
            return None

        now_utc = datetime.now(timezone.utc).isoformat()

        return Candidate(
            symbol=ctx.symbol,
            direction=Direction.LONG,
            strategy_id=self.strategy_id,
            setup_edge_id="E21",
            reference_price=curr_bar.close,
            entry_zone_low=curr_bar.close * 0.999,
            entry_zone_high=curr_bar.close,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=None,
            gross_rr=round(gross_rr, 2),
            net_rr=round(gross_rr - 0.05, 2),
            active_edge_ids=["E21"],
            confirming_edge_ids=["E15", "E13"],
            expiry_bars=12,
            regime=ctx.regime_output.state if ctx.regime_output else RegimeState.NEUTRAL,
            created_at_utc=now_utc,
        )
