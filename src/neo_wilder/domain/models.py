"""Core domain data models for NEO-WILDER V4.

All models are strongly typed, immutable dataclasses.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from neo_wilder.domain.enums import Direction, RegimeState


@dataclass(frozen=True)
class Candle:
    """15m or 5m OHLCV bar."""

    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True

    def __post_init__(self):
        if self.close_time_ms <= self.open_time_ms:
            raise ValueError(
                f"Invalid candle timestamps: close_time_ms {self.close_time_ms} <= open_time_ms {self.open_time_ms}"
            )
        if any(p <= 0 for p in (self.open, self.high, self.low, self.close)):
            raise ValueError(f"Candle prices must be strictly positive: {self}")
        if self.high < max(self.open, self.close, self.low) or self.low > min(
            self.open, self.close, self.high
        ):
            raise ValueError(f"Invalid candle high/low geometry: {self}")


@dataclass(frozen=True)
class AggTrade:
    """Individual aggregated trade tick from Binance."""

    trade_id: int
    symbol: str
    price: float
    quantity: float
    timestamp_ms: int
    is_buyer_maker: bool  # True => buyer is maker, aggressive sell


@dataclass(frozen=True)
class OrderBookLevel:
    """Single price level in depth book."""

    price: float
    quantity: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Top-N order book snapshot."""

    symbol: str
    timestamp_ms: int
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    @property
    def spread_bps(self) -> float:
        if not self.bids or not self.asks:
            return 999.0
        best_bid = self.bids[0].price
        best_ask = self.asks[0].price
        if best_bid <= 0:
            return 999.0
        return ((best_ask - best_bid) / best_bid) * 10000.0


@dataclass(frozen=True)
class FundingSnapshot:
    """Binance premiumIndex and funding rate snapshot."""

    symbol: str
    timestamp_ms: int
    mark_price: float
    index_price: float
    funding_rate: float
    next_funding_time_ms: int


@dataclass(frozen=True)
class OISnapshot:
    """Open interest snapshot."""

    symbol: str
    timestamp_ms: int
    open_interest: float
    open_interest_value: float = 0.0

    @property
    def open_interest_usd(self) -> float:
        return self.open_interest_value


@dataclass(frozen=True)
class CoinDCXQuote:
    """Public CoinDCX market execution snapshot."""

    pair: str
    timestamp_ms: int
    price: float
    mark_price: float
    funding_rate: float
    spread_bps: float
    top10_depth_usd: float


@dataclass(frozen=True)
class SwingPivot:
    """Structural swing high or swing low."""

    index: int
    timestamp_ms: int
    price: float
    pivot_type: str  # "HIGH" or "LOW"

    @property
    def bar_index(self) -> int:
        """Alias for index to maintain backwards compatibility across indicators."""
        return self.index


@dataclass(frozen=True)
class LiquidityPool:
    """Identified Equal Highs (EQH) or Equal Lows (EQL) pool."""

    pool_type: str  # "EQH" or "EQL"
    level: float
    swings: List[SwingPivot]
    touch_count: int
    width_atr: float


@dataclass(frozen=True)
class EdgeResult:
    """Pure output of an edge evaluator."""

    edge_id: str
    passed: bool
    confidence: float  # 0.0 to 1.0
    direction: Direction
    score_contribution: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def abstain(cls, edge_id: str) -> "EdgeResult":
        return cls(
            edge_id=edge_id,
            passed=False,
            confidence=0.0,
            direction=Direction.BOTH,
            score_contribution=0,
        )


@dataclass(frozen=True)
class Candidate:
    """Unvalidated candidate signal emitted by a strategy."""

    symbol: str
    direction: Direction
    strategy_id: str
    setup_edge_id: str
    reference_price: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: Optional[float]
    gross_rr: float
    net_rr: float
    active_edge_ids: List[str]
    confirming_edge_ids: List[str]
    expiry_bars: int
    regime: RegimeState
    created_at_utc: str


@dataclass(frozen=True)
class VetoResult:
    """Output of veto pipeline evaluation."""

    passed: bool
    blocking_id: Optional[str] = None
    reason_code: Optional[str] = None
    severity: Optional[str] = None
    details: str = ""


@dataclass(frozen=True)
class ScoreBreakdown:
    """Composite score computation breakdown."""

    total_score: int  # 0 to 100
    cluster_scores: Dict[str, int]
    rr_bonus: int
    calibrated_probability: Optional[float]
    is_calibrated: bool
