"""E11: ATR Realized Volatility feature edge."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E11ATRVolatility(BaseEdge):
    """Computes ATR and validates volatility bounds."""

    def __init__(self):
        super().__init__("E11")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.atr_result:
            return EdgeResult.abstain(self.edge_id)

        atr_bps = ctx.atr_result.atr_bps
        passed = 4.0 <= atr_bps <= 400.0

        return EdgeResult(
            edge_id=self.edge_id,
            passed=passed,
            confidence=1.0 if passed else 0.0,
            direction=Direction.BOTH,
            score_contribution=0,  # Risk/Geometry input
            metadata={
                "atr": ctx.atr_result.atr,
                "atr_bps": atr_bps,
                "vol_tier": ctx.atr_result.vol_tier,
            },
        )
