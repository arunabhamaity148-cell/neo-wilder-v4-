"""E01: Liquidity Sweep and Reclaim setup edge (the spine).

Note: Per KNOWN_LIMITATIONS.md, SHORT candidate generation is disabled fail-closed.
Only LONG setups supported by research specifications are evaluated.
"""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E01SweepReclaim(BaseEdge):
    """Core S1 setup edge."""

    def __init__(self):
        super().__init__("E01")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.candles or not ctx.atr_result or not ctx.pools:
            return EdgeResult.abstain(self.edge_id)

        atr = ctx.atr_result.atr
        curr_bar = ctx.candles[-1]

        # Scan for Equal Lows (EQL) pools for LONG setups
        eql_pools = [p for p in ctx.pools if p.pool_type == "EQL"]

        for pool in eql_pools:
            # Check sweep depth: bar wicks beyond pool
            # d_long = pool - low
            if curr_bar.low < pool.level:
                sweep_depth = pool.level - curr_bar.low
                min_depth = 0.05 * atr
                max_depth = 1.20 * atr

                if min_depth <= sweep_depth <= max_depth:
                    # Check same-bar reclaim: close > pool
                    if curr_bar.close > pool.level:
                        return EdgeResult(
                            edge_id=self.edge_id,
                            passed=True,
                            confidence=0.85,
                            direction=Direction.LONG,
                            score_contribution=10,
                            metadata={
                                "sweep_depth": sweep_depth,
                                "pool_level": pool.level,
                                "sweep_low": curr_bar.low,
                                "atr": atr,
                            },
                        )

        return EdgeResult.abstain(self.edge_id)
