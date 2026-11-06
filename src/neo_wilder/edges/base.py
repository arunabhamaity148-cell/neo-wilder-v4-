"""Base edge interface and feature evaluation context for NEO-WILDER V4.

Pure functions: no I/O, no network, deterministic replay.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from neo_wilder.domain.models import (
    AggTrade,
    Candle,
    EdgeResult,
    LiquidityPool,
    OrderBookSnapshot,
    SwingPivot,
)
from neo_wilder.features.atr import ATRResult
from neo_wilder.features.cvd import CVDResult
from neo_wilder.features.funding import FundingContextResult
from neo_wilder.features.obi import OBIResult
from neo_wilder.features.regime import RegimeOutput
from neo_wilder.features.structure import StructureState
from neo_wilder.features.volume_profile import VolumeProfileLevels


@dataclass(frozen=True)
class FeatureContext:
    """Read-only context containing all causal features at bar close t."""

    symbol: str
    timeframe: str
    now_ms: int
    candles: List[Candle]
    atr_result: Optional[ATRResult] = None
    swings: List[SwingPivot] = field(default_factory=list)
    pools: List[LiquidityPool] = field(default_factory=list)
    structure: Optional[StructureState] = None
    volume_profile: Optional[VolumeProfileLevels] = None
    funding_context: Optional[FundingContextResult] = None
    cvd_result: Optional[CVDResult] = None
    obi_result: Optional[OBIResult] = None
    regime_output: Optional[RegimeOutput] = None
    trades: Optional[List[AggTrade] | Deque[AggTrade]] = None
    orderbook: Optional[OrderBookSnapshot] = None
    btc_5m_return: float = 0.0


class BaseEdge(ABC):
    """Abstract base class for all edges."""

    def __init__(self, edge_id: str):
        self.edge_id = edge_id

    @abstractmethod
    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        """Pure evaluation function.

        Must never raise an unhandled exception into pipeline.
        Must return EdgeResult.abstain(self.edge_id) on missing data.
        """
        pass
