"""E24: Mark/Index divergence evaluation (ACTIVE)."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E24MarkIndexDiv(BaseEdge):
    """Evaluates mark/index divergence (V-H18)."""

    def __init__(self):
        super().__init__("E24")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.funding_context:
            return EdgeResult.abstain(self.edge_id)

        div_pct = ctx.funding_context.mark_index_divergence_pct
        passed = div_pct <= 0.50

        return EdgeResult(
            edge_id=self.edge_id,
            passed=passed,
            confidence=1.0 if passed else 0.0,
            direction=Direction.BOTH,
            score_contribution=0,  # Veto input
            metadata={"divergence_pct": div_pct},
        )
