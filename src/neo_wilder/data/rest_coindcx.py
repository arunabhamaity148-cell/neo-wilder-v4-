"""Public CoinDCX REST client for NEO-WILDER V4.

Strictly public endpoints for manual execution price and depth validation.
No private credentials or order execution logic permitted.
Includes token bucket rate limiting (max 2 req/s) with bounded backoff and jitter.
"""

import asyncio
import logging
import secrets
import time
from typing import Any, Dict, List, Optional

import aiohttp

from neo_wilder.domain.models import CoinDCXQuote

logger = logging.getLogger(__name__)


class CoinDCXRateLimiter:
    """Token bucket rate limiter enforcing a bounded request rate (default 2 req/s)."""

    def __init__(self, max_rate_rps: float = 2.0, burst: float = 2.0):
        self.max_rate_rps = max(0.1, max_rate_rps)
        self.burst = max(1.0, burst)
        self.tokens = self.burst
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available before returning."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.max_rate_rps)
            self.last_refill = now

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.max_rate_rps
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_refill = time.monotonic()
            else:
                self.tokens -= 1.0


class CoinDCXPublicClient:
    """Public REST client for CoinDCX validation metrics."""

    def __init__(
        self,
        public_url: str = "https://public.coindcx.com",
        api_url: str = "https://api.coindcx.com",
        session: Optional[aiohttp.ClientSession] = None,
        rate_limiter: Optional[CoinDCXRateLimiter] = None,
        max_retries: int = 3,
    ):
        self.public_url = public_url.rstrip("/")
        self.api_url = api_url.rstrip("/")
        self._session = session
        self._owns_session = False
        self.rate_limiter = rate_limiter or CoinDCXRateLimiter(max_rate_rps=2.0, burst=2.0)
        self.max_retries = max_retries

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4.0))
            self._owns_session = True
        return self._session

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _get_with_retry(self, url: str) -> Optional[Any]:
        """Fetch endpoint with rate limiting, Retry-After header parsing, and bounded jitter backoff."""
        session = await self._get_session()
        for attempt in range(self.max_retries):
            await self.rate_limiter.acquire()
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait_sec = min(5.0, float(retry_after))
                            except ValueError:
                                wait_sec = 1.0
                        else:
                            wait_sec = min(
                                5.0,
                                1.0 * (1.5**attempt) + secrets.SystemRandom().uniform(0.05, 0.2),
                            )
                        logger.warning(
                            f"CoinDCX HTTP 429 rate limit hit on {url}. Backing off for {wait_sec:.2f}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(wait_sec)
                    else:
                        logger.warning(f"CoinDCX GET {url} failed: HTTP {resp.status}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(0.3 * (attempt + 1))
            except Exception as e:
                logger.warning(f"CoinDCX request exception on {url} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.3 * (attempt + 1))
        return None

    async def get_active_instruments(self) -> List[Dict[str, Any]]:
        """Fetch active futures instruments for startup symbol mapping."""
        url = f"{self.api_url}/exchange/v1/derivatives/futures/data/active_instruments"
        data = await self._get_with_retry(url)
        return data if isinstance(data, list) else []

    async def get_current_prices_rt(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all real-time futures prices, funding, and mark prices."""
        url = f"{self.public_url}/market_data/v3/current_prices/futures/rt"
        data = await self._get_with_retry(url)
        if isinstance(data, list):
            return {item.get("pair", ""): item for item in data if "pair" in item}
        return {}

    async def get_orderbook_depth(self, pair: str, depth: int = 10) -> Optional[Dict[str, Any]]:
        """Fetch top-10/20 orderbook depth for spread and liquidity validation."""
        instrument = pair if pair.endswith("-futures") else f"{pair}-futures"
        url = f"{self.public_url}/market_data/v3/orderbook/{instrument}/{depth}"
        data = await self._get_with_retry(url)
        return data if isinstance(data, dict) else None

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
