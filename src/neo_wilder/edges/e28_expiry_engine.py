"""E28: Dynamic Signal Expiry engine (ACTIVE)."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E28ExpiryEngine(BaseEdge):
    """Calculates max holding bars: min(16, 4 + 2 * vol_tier)."""

    def __init__(self):
        super().__init__("E28")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        vol_tier = ctx.atr_result.vol_tier if ctx.atr_result else 1
        expiry_bars = min(16, 4 + 2 * vol_tier)

        return EdgeResult(
            edge_id=self.edge_id,
            passed=True,
            confidence=1.0,
            direction=Direction.BOTH,
            score_contribution=0,  # Risk input
            metadata={"expiry_bars": expiry_bars},
        )
