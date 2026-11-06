"""E04: Liquidity Pool EQH/EQL confirmation edge."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E04LiquidityPools(BaseEdge):
    """Verifies that an Equal Highs or Equal Lows pool exists."""

    def __init__(self):
        super().__init__("E04")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.pools:
            return EdgeResult.abstain(self.edge_id)

        # Check if there is at least one verified pool with >= 2 touches
        active_pools = [p for p in ctx.pools if p.touch_count >= 2]
        if active_pools:
            best_pool = active_pools[0]
            direction = Direction.LONG if best_pool.pool_type == "EQL" else Direction.SHORT
            return EdgeResult(
                edge_id=self.edge_id,
                passed=True,
                confidence=0.80,
                direction=direction,
                score_contribution=0,  # Feature edge
                metadata={"touch_count": best_pool.touch_count, "level": best_pool.level},
            )

        return EdgeResult.abstain(self.edge_id)
