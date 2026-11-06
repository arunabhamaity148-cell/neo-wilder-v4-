"""E15: CVD Turn confirmation (SHADOW).

Contributes 0 active points.
"""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E15CVDTurn(BaseEdge):
    """Detects Cumulative Volume Delta inflection turn."""

    def __init__(self):
        super().__init__("E15")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.cvd_result:
            return EdgeResult.abstain(self.edge_id)

        if ctx.cvd_result.has_turned_bullish:
            return EdgeResult(
                edge_id=self.edge_id,
                passed=True,
                confidence=0.80,
                direction=Direction.LONG,
                score_contribution=0,  # SHADOW
                metadata={"slope": ctx.cvd_result.slope},
            )

        return EdgeResult.abstain(self.edge_id)
