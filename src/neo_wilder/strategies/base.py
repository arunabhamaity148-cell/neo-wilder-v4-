"""Base strategy interface for NEO-WILDER V4."""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.base import FeatureContext


class BaseStrategy(ABC):
    """Abstract interface for all candidate generating strategies."""

    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    @abstractmethod
    def generate_candidate(
        self,
        ctx: FeatureContext,
        edge_results: Dict[str, EdgeResult],
    ) -> Optional[Candidate]:
        """Generate unvalidated trade candidate from causal features and edges.

        Returns None if setup conditions are not satisfied.
        """
        pass
