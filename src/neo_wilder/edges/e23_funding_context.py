"""E23: Funding context evaluation (ACTIVE)."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E23FundingContext(BaseEdge):
    """Evaluates funding rate risk."""

    def __init__(self):
        super().__init__("E23")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.funding_context:
            return EdgeResult.abstain(self.edge_id)

        fc = ctx.funding_context
        passed = not fc.is_funding_window_active

        return EdgeResult(
            edge_id=self.edge_id,
            passed=passed,
            confidence=1.0 if passed else 0.0,
            direction=Direction.BOTH,
            score_contribution=0,  # Veto input
            metadata={"funding_rate_pct": fc.funding_rate_pct},
        )
