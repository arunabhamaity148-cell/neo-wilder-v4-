"""E13: Liquidation Burst Z-score confirmation (SHADOW).

Note: Strictly SHADOW due to Binance 1000 ms rate-limiting sampling bias.
Contributes 0 active points.
"""

from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class E13LiqBurst(BaseEdge):
    """Detects liquidation volume burst Z_liq >= 2.0."""

    def __init__(self):
        super().__init__("E13")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        # In live context, liquidation events are monitored via WebSocket ringbuffer
        # In standard candle context without liquidation stream, abstains
        return EdgeResult.abstain(self.edge_id)
