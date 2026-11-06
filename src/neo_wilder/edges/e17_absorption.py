"""E17: Book Density Absorption confirmation (SHADOW).

Reconciled strictly to Cluster C2 (order flow).
Contributes 0 active points to composite score.
"""

from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E17Absorption(BaseEdge):
    """Detects passive book absorption of aggressive selling or buying."""

    def __init__(self):
        super().__init__("E17")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        # Evaluated for telemetry only
        return EdgeResult.abstain(self.edge_id)
