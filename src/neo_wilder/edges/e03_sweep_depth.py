"""E03: Sweep Depth normalized by ATR."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E03SweepDepth(BaseEdge):
    """Computes normalized sweep depth ratio."""

    def __init__(self):
        super().__init__("E03")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.candles or not ctx.atr_result or not ctx.pools:
            return EdgeResult.abstain(self.edge_id)

        atr = ctx.atr_result.atr
        curr_bar = ctx.candles[-1]

        for pool in ctx.pools:
            if pool.pool_type == "EQL" and curr_bar.low < pool.level:
                depth_ratio = (pool.level - curr_bar.low) / atr if atr > 0 else 0.0
                return EdgeResult(
                    edge_id=self.edge_id,
                    passed=True,
                    confidence=min(1.0, depth_ratio),
                    direction=Direction.LONG,
                    score_contribution=0,  # Feature edge
                    metadata={"depth_ratio": depth_ratio},
                )

        return EdgeResult.abstain(self.edge_id)
