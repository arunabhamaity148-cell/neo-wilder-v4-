"""S3: BASIS-DIVERGENCE-v4 strategy engine (EXPERIMENTAL).

Abstains fail-closed if feed clock offset > 150 ms.
"""

from typing import Dict, Optional

from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.strategies.base import BaseStrategy


class S3BasisDivergenceStrategy(BaseStrategy):
    """Experimental strategy for spot-led basis dislocation."""

    def __init__(self, max_clock_offset_ms: float = 150.0):
        super().__init__("S3_BASIS_DIVERGENCE")
        self.max_clock_offset_ms = max_clock_offset_ms

    def generate_candidate(
        self,
        ctx: FeatureContext,
        edge_results: Dict[str, EdgeResult],
    ) -> Optional[Candidate]:
        # S3 is EXPERIMENTAL only; abstains if synchronisation is unverified
        return None
