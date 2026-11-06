"""E21: Open Interest Exhaustion Reversal (SHADOW).

Detects rapid OI contraction (>= 0.8% drop) near structural lows, indicating
forced position unwinding and absorption. Strictly SHADOW telemetry for S2.
Contributes 0 active score points.
"""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E21OIExhaustion(BaseEdge):
    """Detects Open Interest exhaustion drop >= 0.8%."""

    def __init__(self, min_oi_drop_pct: float = 0.008):
        super().__init__("E21")
        self.min_oi_drop_pct = min_oi_drop_pct

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.oi_history or len(ctx.oi_history) < 2:
            return EdgeResult.abstain(self.edge_id)

        if not ctx.candles:
            return EdgeResult.abstain(self.edge_id)

        # Calculate relative OI change over recent snapshots
        latest_oi = ctx.oi_history[-1].open_interest
        prev_oi = ctx.oi_history[0].open_interest

        if prev_oi <= 0.0:
            return EdgeResult.abstain(self.edge_id)

        delta_pct = (latest_oi - prev_oi) / prev_oi

        # Exhaustion requires significant OI drop (<= -0.8%)
        if delta_pct <= -self.min_oi_drop_pct:
            # Confirm price is near recent low (within 1.0 ATR if ATR available)
            curr_bar = ctx.candles[-1]
            atr = ctx.atr_result.atr if ctx.atr_result else (curr_bar.high - curr_bar.low)
            recent_low = min(c.low for c in ctx.candles[-min(10, len(ctx.candles)) :])

            if (curr_bar.close - recent_low) <= 1.5 * max(atr, 1.0):
                return EdgeResult(
                    edge_id=self.edge_id,
                    passed=True,
                    confidence=0.80,
                    direction=Direction.LONG,
                    score_contribution=0,  # Strictly SHADOW
                    metadata={"oi_delta_pct": delta_pct, "recent_low": recent_low},
                )

        return EdgeResult.abstain(self.edge_id)
