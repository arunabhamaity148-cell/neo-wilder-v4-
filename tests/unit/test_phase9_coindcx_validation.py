"""Unit tests for Phase 9: CoinDCX Public Validation & Universe Mapping."""

from unittest.mock import AsyncMock

import pytest

from neo_wilder.coindcx.universe import SymbolUniverseManager
from neo_wilder.coindcx.validator import CoinDCXExecutionValidator
from neo_wilder.data.rest_coindcx import CoinDCXPublicClient
from neo_wilder.domain.enums import SymbolTier
from neo_wilder.domain.models import CoinDCXQuote


@pytest.mark.asyncio
async def test_symbol_universe_mapping():
    """Verify SymbolUniverseManager correctly drops unmapped Binance symbols."""
    mock_client = AsyncMock(spec=CoinDCXPublicClient)
    # Mock active instruments returned by CoinDCX
    mock_client.get_active_instruments.return_value = [
        {"pair": "B-BTC_USDT", "status": "active"},
        {"pair": "B-ETH_USDT", "status": "active"},
        {"pair": "B-SOL_USDT", "status": "active"},
        # DOGE is NOT in CoinDCX
    ]

    manager = SymbolUniverseManager(mock_client)
    input_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]

    approved = await manager.initialize_universe(input_symbols)

    assert "BTCUSDT" in approved
    assert "ETHUSDT" in approved
    assert "SOLUSDT" in approved
    assert "DOGEUSDT" not in approved  # Must be dropped!

    assert manager.get_coindcx_pair("BTCUSDT") == "B-BTC_USDT"
    assert manager.get_coindcx_pair("DOGEUSDT") is None
    assert manager.get_symbol_tier("BTCUSDT") == SymbolTier.MAJOR
    assert manager.get_symbol_tier("SOLUSDT") == SymbolTier.ALT


def test_coindcx_validator_quote_unavailable():
    """Verify V-H31: missing or non-positive quote blocks publication."""
    validator = CoinDCXExecutionValidator()

    # None quote
    res_none = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=None,
    )
    assert res_none.is_valid is False
    assert res_none.veto_id == "V-H31"

    # Zero price quote
    bad_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=0.0,
        mark_price=0.0,
        funding_rate=0.0,
        spread_bps=5.0,
        top10_depth_usd=100000.0,
    )
    res_zero = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=bad_quote,
    )
    assert res_zero.is_valid is False
    assert res_zero.veto_id == "V-H31"


def test_coindcx_validator_price_drift():
    """Verify V-H32: drift > 0.35% blocks publication."""
    validator = CoinDCXExecutionValidator(max_drift_pct=0.35)

    # Reference 50000, CoinDCX 50200 -> drift = 200 / 50000 = 0.40% > 0.35%
    drift_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=50200.0,
        mark_price=50200.0,
        funding_rate=0.0001,
        spread_bps=5.0,
        top10_depth_usd=100000.0,
    )
    res = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=drift_quote,
    )
    assert res.is_valid is False
    assert res.veto_id == "V-H32"
    assert res.drift_pct == pytest.approx(0.40, rel=1e-2)


def test_coindcx_validator_spread_limits():
    """Verify V-H33: spread > 12 bps (MAJOR) or > 25 bps (ALT) blocks publication."""
    validator = CoinDCXExecutionValidator()

    # Spread 15 bps on MAJOR (limit 12) -> should fail
    quote_major_fail = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=50010.0,
        mark_price=50010.0,
        funding_rate=0.0,
        spread_bps=15.0,
        top10_depth_usd=100000.0,
    )
    res_major = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=quote_major_fail,
        symbol_tier=SymbolTier.MAJOR,
    )
    assert res_major.is_valid is False
    assert res_major.veto_id == "V-H12"

    # Spread 15 bps on ALT (limit 25) -> should pass spread gate
    res_alt = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=quote_major_fail,
        symbol_tier=SymbolTier.ALT,
    )
    assert res_alt.is_valid is True


def test_coindcx_validator_depth_and_friction():
    """Verify V-H13 depth gate and 0.1354% round-trip friction calculation."""
    validator = CoinDCXExecutionValidator(default_clip_usd=1000.0)

    # Top 10 depth only $15,000 (< 20 x $1000 = $20,000 required)
    shallow_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=50010.0,
        mark_price=50010.0,
        funding_rate=0.0,
        spread_bps=5.0,
        top10_depth_usd=15000.0,
    )
    res_shallow = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=shallow_quote,
        symbol_tier=SymbolTier.MAJOR,
    )
    assert res_shallow.is_valid is False
    assert res_shallow.veto_id == "V-H13"

    # Good depth $100,000 -> passes all gates
    good_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=50010.0,
        mark_price=50010.0,
        funding_rate=0.0,
        spread_bps=5.0,
        top10_depth_usd=100000.0,
    )
    res_good = validator.validate_candidate(
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        tp1=51000.0,
        quote=good_quote,
        symbol_tier=SymbolTier.MAJOR,
    )
    assert res_good.is_valid is True
    # Fee is 0.050% * 1.18 * 2 = 0.1180%
    assert res_good.fee_pct == pytest.approx(0.1180, rel=1e-3)
    # Total baseline friction is ~ 0.1354%
    assert res_good.total_friction_pct == pytest.approx(0.1354, rel=0.1)


@pytest.mark.asyncio
async def test_coindcx_rate_limiter():
    """Verify CoinDCXRateLimiter enforces a maximum request rate and bounded timing."""
    import time

    from neo_wilder.data.rest_coindcx import CoinDCXRateLimiter

    limiter = CoinDCXRateLimiter(max_rate_rps=10.0, burst=2.0)
    start = time.monotonic()

    # Acquire 5 tokens: initial 2 tokens available immediately from burst, remaining 3 spaced at 0.1s
    for _ in range(5):
        await limiter.acquire()

    elapsed = time.monotonic() - start
    # At 10 req/s, 5 requests with burst of 2 should take >= 0.25s
    assert elapsed >= 0.20


@pytest.mark.asyncio
async def test_symbol_universe_mapping_real_coindcx_string_list():
    """Verify SymbolUniverseManager correctly handles real CoinDCX API format (list of strings).

    Regression test for: 'str' object has no attribute 'get'.
    """
    mock_client = AsyncMock(spec=CoinDCXPublicClient)
    # The actual CoinDCX endpoint returns a flat list of string pair identifiers
    mock_client.get_active_instruments.return_value = [
        "B-BTC_USDT",
        "B-ETH_USDT",
        "B-SOL_USDT",
        "B-XRP_USDT",
    ]

    manager = SymbolUniverseManager(mock_client)
    input_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]

    approved = await manager.initialize_universe(input_symbols)

    assert approved == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert "DOGEUSDT" not in approved
    assert manager.is_symbol_supported("BTCUSDT") is True
    assert manager.is_symbol_supported("DOGEUSDT") is False
    assert manager.get_coindcx_pair("BTCUSDT") == "B-BTC_USDT"


@pytest.mark.asyncio
async def test_symbol_universe_mapping_malformed_and_edge_cases():
    """Verify SymbolUniverseManager handles malformed, empty, and mixed input gracefully."""
    mock_client = AsyncMock(spec=CoinDCXPublicClient)
    # Mixed data: strings, dicts, integers, None, inactive status
    mock_client.get_active_instruments.return_value = [
        "B-BTC_USDT",
        {"pair": "B-ETH_USDT", "status": "active"},
        {"pair": "B-SOL_USDT", "status": "suspended"},  # suspended -> must be ignored
        {"pair": "B-ADA_USDT", "status": "trading"},   # trading -> active
        None,
        12345,
        "   ",  # whitespace string
    ]

    manager = SymbolUniverseManager(mock_client)
    input_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]

    approved = await manager.initialize_universe(input_symbols)

    assert "BTCUSDT" in approved
    assert "ETHUSDT" in approved
    assert "ADAUSDT" in approved
    assert "SOLUSDT" not in approved  # Suspended pair dropped


@pytest.mark.asyncio
async def test_coindcx_get_validation_quote_live_dictionary_format():
    """Verify CoinDCXPublicClient parses live CoinDCX prices rt and orderbook dict structures."""
    client = CoinDCXPublicClient()

    # Mock real CoinDCX endpoint returns:
    # 1. prices rt returns {"prices": {"B-BTC_USDT": {"ls": 76000.0, "mp": 75995.0, "fr": 0.0001}}}
    # 2. orderbook returns {"bids": {"75990.0": "2.0", "75980.0": "3.0"}, "asks": {"76010.0": "1.5"}}
    client.get_current_prices_rt = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "B-BTC_USDT": {"ls": 76000.0, "mp": 75995.0, "fr": 0.0001}
        }
    )
    client.get_orderbook_depth = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "bids": {"75990.0": "2.0", "75980.0": "3.0"},
            "asks": {"76010.0": "1.5"},
        }
    )

    quote = await client.get_validation_quote("B-BTC_USDT", now_ms=1700000000000)

    assert quote is not None
    assert quote.pair == "B-BTC_USDT"
    assert quote.price == 76000.0
    assert quote.mark_price == 75995.0
    assert quote.funding_rate == 0.0001
    # best_bid=75990, best_ask=76010 -> spread = (20 / 75990) * 10000 bps ~ 2.63 bps
    assert quote.spread_bps == pytest.approx(2.6319, rel=1e-2)
    # top 10 depth = 75990*2 + 75980*3 = 151980 + 227940 = 379920.0 USD
    assert quote.top10_depth_usd == pytest.approx(379920.0, rel=1e-2)
