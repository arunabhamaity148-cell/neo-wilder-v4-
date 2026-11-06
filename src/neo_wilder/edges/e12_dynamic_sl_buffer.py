"""E12: Dynamic Stop Loss Buffer multiplier calculation."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E12DynamicSLBuffer(BaseEdge):
    """Calculates buffer multiplier: alpha(pct_ATR) + 0.60 * 1[|funding| >= 0.03%]."""

    def __init__(self):
        super().__init__("E12")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.atr_result:
            return EdgeResult.abstain(self.edge_id)

        vol_tier = ctx.atr_result.vol_tier
        alpha_map = {0: 1.5, 1: 2.2, 2: 3.0}
        alpha = alpha_map.get(vol_tier, 2.2)

        # Check toxic funding penalty
        funding_penalty = 0.0
        if ctx.funding_context and abs(ctx.funding_context.funding_rate_pct) >= 0.03:
            funding_penalty = 0.60

        buffer_mult = alpha + funding_penalty

        return EdgeResult(
            edge_id=self.edge_id,
            passed=True,
            confidence=1.0,
            direction=Direction.BOTH,
            score_contribution=0,  # Risk input
            metadata={
                "buffer_multiplier": buffer_mult,
                "alpha": alpha,
                "funding_penalty": funding_penalty,
            },
        )
