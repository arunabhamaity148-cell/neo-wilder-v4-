"""E07: Volume Profile POC VAH VAL target edge."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E07VolumeProfile(BaseEdge):
    """Provides structural volume profile targets."""

    def __init__(self):
        super().__init__("E07")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.volume_profile or not ctx.candles:
            return EdgeResult.abstain(self.edge_id)

        curr_close = ctx.candles[-1].close
        vp = ctx.volume_profile

        # If current price is below VAL, VAL/POC/VAH form natural upside targets
        if curr_close < vp.val:
            return EdgeResult(
                edge_id=self.edge_id,
                passed=True,
                confidence=0.80,
                direction=Direction.LONG,
                score_contribution=6,
                metadata={"poc": vp.poc, "val": vp.val, "vah": vp.vah},
            )

        return EdgeResult(
            edge_id=self.edge_id,
            passed=True,
            confidence=0.60,
            direction=Direction.BOTH,
            score_contribution=4,
            metadata={"poc": vp.poc, "val": vp.val, "vah": vp.vah},
        )
