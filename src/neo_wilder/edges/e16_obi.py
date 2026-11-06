"""E16: Order Book Imbalance top10 (SHADOW).

Contributes 0 active points.
"""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E16OBI(BaseEdge):
    """Detects top-10 book imbalance."""

    def __init__(self):
        super().__init__("E16")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.obi_result:
            return EdgeResult.abstain(self.edge_id)

        obi = ctx.obi_result.obi
        if obi > 0.25:
            return EdgeResult(
                edge_id=self.edge_id,
                passed=True,
                confidence=float(min(1.0, obi * 2.0)),
                direction=Direction.LONG,
                score_contribution=0,  # SHADOW
                metadata={"obi": obi},
            )

        return EdgeResult.abstain(self.edge_id)
