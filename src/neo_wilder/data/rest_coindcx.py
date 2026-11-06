"""Public CoinDCX REST client for NEO-WILDER V4.

Strictly public endpoints for manual execution price and depth validation.
No private credentials or order execution logic permitted.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from neo_wilder.domain.models import CoinDCXQuote

logger = logging.getLogger(__name__)


class CoinDCXPublicClient:
    """Public REST client for CoinDCX validation metrics."""

    def __init__(
        self,
        public_url: str = "https://public.coindcx.com",
        api_url: str = "https://api.coindcx.com",
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.public_url = public_url.rstrip("/")
        self.api_url = api_url.rstrip("/")
        self._session = session
        self._owns_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4.0))
            self._owns_session = True
        return self._session

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def get_active_instruments(self) -> List[Dict[str, Any]]:
        """Fetch active futures instruments for startup symbol mapping."""
        url = f"{self.api_url}/exchange/v1/derivatives/futures/data/active_instruments"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"Failed to fetch CoinDCX active instruments: HTTP {resp.status}")
                return []
        except Exception as e:
            logger.warning(f"CoinDCX active_instruments exception: {e}")
            return []

    async def get_current_prices_rt(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all real-time futures prices, funding, and mark prices."""
        url = f"{self.public_url}/market_data/v3/current_prices/futures/rt"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Map by pair name for O(1) lookup
                    return {item.get("pair", ""): item for item in data if "pair" in item}
                logger.warning(f"CoinDCX current_prices/rt error: HTTP {resp.status}")
                return {}
        except Exception as e:
            logger.warning(f"CoinDCX current_prices exception: {e}")
            return {}

    async def get_orderbook_depth(self, pair: str, depth: int = 10) -> Optional[Dict[str, Any]]:
        """Fetch top-10/20 orderbook depth for spread and liquidity validation."""
        # Ensure pair formatting, e.g. B-BTC_USDT -> B-BTC_USDT-futures
        instrument = pair if pair.endswith("-futures") else f"{pair}-futures"
        url = f"{self.public_url}/market_data/v3/orderbook/{instrument}/{depth}"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"CoinDCX orderbook error for {pair}: HTTP {resp.status}")
                return None
        except Exception as e:
            logger.warning(f"CoinDCX orderbook exception: {e}")
            return None

    async def get_validation_quote(self, pair: str, now_ms: int) -> Optional[CoinDCXQuote]:
        """Fetch combined price, spread and depth quote for execution validation.

        Returns None if quote cannot be fetched or parsed (feeds V-H31 fail-closed).
        """
        prices_task = self.get_current_prices_rt()
        book_task = self.get_orderbook_depth(pair, depth=10)

        prices_dict, book = await asyncio.gather(prices_task, book_task, return_exceptions=True)

        if isinstance(prices_dict, Exception) or not prices_dict or pair not in prices_dict:
            logger.warning(f"CoinDCX validation quote missing price for {pair}")
            return None

        price_data = prices_dict[pair]
        price = float(price_data.get("price", 0.0))
        mark_price = float(price_data.get("mp", price))
        funding_rate = float(price_data.get("fr", 0.0))

        if price <= 0:
            return None

        # Parse spread and depth
        spread_bps = 999.0
        top10_depth_usd = 0.0

        if isinstance(book, dict) and "bids" in book and "asks" in book:
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if bids and asks:
                best_bid = float(bids[0].get("price", 0.0))
                best_ask = float(asks[0].get("price", 0.0))
                if best_bid > 0 and best_ask >= best_bid:
                    spread_bps = ((best_ask - best_bid) / best_bid) * 10000.0

                # Sum top 10 bid notional
                for b in bids[:10]:
                    p = float(b.get("price", 0.0))
                    q = float(b.get("quantity", 0.0))
                    top10_depth_usd += p * q

        return CoinDCXQuote(
            pair=pair,
            timestamp_ms=now_ms,
            price=price,
            mark_price=mark_price,
            funding_rate=funding_rate,
            spread_bps=spread_bps,
            top10_depth_usd=top10_depth_usd,
        )
