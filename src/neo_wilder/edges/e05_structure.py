"""E05: BOS and CHoCH structure confirmation edge (SHADOW)."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E05Structure(BaseEdge):
    """Detects market structure break (BOS) or change of character (CHoCH)."""

    def __init__(self):
        super().__init__("E05")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.structure:
            return EdgeResult.abstain(self.edge_id)

        if ctx.structure.has_bullish_choch:
            return EdgeResult(
                edge_id=self.edge_id,
                passed=True,
                confidence=0.90,
                direction=Direction.LONG,
                score_contribution=0,  # SHADOW: strictly 0 active points
                metadata={"shift_type": "BULLISH_CHOCH"},
            )

        if ctx.structure.has_bullish_bos:
            return EdgeResult(
                edge_id=self.edge_id,
                passed=True,
                confidence=0.75,
                direction=Direction.LONG,
                score_contribution=0,  # SHADOW
                metadata={"shift_type": "BULLISH_BOS"},
            )

        return EdgeResult.abstain(self.edge_id)
