"""Binance USD-M REST client and poller for NEO-WILDER V4.

Handles rate limiting, exponential backoff, and circuit breaker tracking.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from neo_wilder.domain.models import Candle, FundingSnapshot, OISnapshot

logger = logging.getLogger(__name__)


class BinanceRestClient:
    """Public REST client for Binance USD-M market data."""

    def __init__(
        self,
        base_url: str = "https://fapi.binance.com",
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._session = session
        self._owns_session = False
        self._last_success_ts: Dict[str, float] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5.0))
            self._owns_session = True
        return self._session

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self, path: str, params: Optional[Dict[str, Any]] = None, retries: int = 3
    ) -> Any:
        url = f"{self.base_url}{path}"
        session = await self._get_session()
        last_exc = None

        for attempt in range(retries):
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        self._last_success_ts[path] = time.monotonic()
                        return await resp.json()
                    elif resp.status in (429, 418):
                        # Rate limited
                        backoff = 2.0 ** (attempt + 1)
                        logger.warning(
                            f"Binance rate limit {resp.status} on {path}, backing off {backoff}s"
                        )
                        await asyncio.sleep(backoff)
                    else:
                        text = await resp.text()
                        logger.warning(f"Binance REST error {resp.status} on {path}: {text}")
            except Exception as e:
                last_exc = e
                await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError(
            f"Failed Binance REST request {path} after {retries} retries: {last_exc}"
        )

    def is_source_down(self, path: str, threshold_sec: float = 600.0) -> bool:
        """Return True if endpoint has not had a successful response in > threshold_sec."""
        last_ts = self._last_success_ts.get(path)
        if last_ts is None:
            return False
        return (time.monotonic() - last_ts) > threshold_sec

    async def get_server_time_ms(self) -> int:
        """Fetch server time from /fapi/v1/time."""
        data = await self._request("/fapi/v1/time")
        return int(data["serverTime"])

    async def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 100
    ) -> List[Candle]:
        """Fetch historical klines from /fapi/v1/klines."""
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        raw_bars = await self._request("/fapi/v1/klines", params=params)
        candles = []
        for b in raw_bars:
            candles.append(
                Candle(
                    open_time_ms=int(b[0]),
                    close_time_ms=int(b[6]),
                    open=float(b[1]),
                    high=float(b[2]),
                    low=float(b[3]),
                    close=float(b[4]),
                    volume=float(b[5]),
                )
            )
        return candles

    async def get_premium_index(self, symbol: str) -> FundingSnapshot:
        """Fetch mark, index and funding rate from /fapi/v1/premiumIndex."""
        params = {"symbol": symbol}
        data = await self._request("/fapi/v1/premiumIndex", params=params)
        return FundingSnapshot(
            symbol=symbol,
            timestamp_ms=int(data["time"]),
            mark_price=float(data["markPrice"]),
            index_price=float(data["indexPrice"]),
            funding_rate=float(data["lastFundingRate"]),
            next_funding_time_ms=int(data["nextFundingTime"]),
        )

    async def get_open_interest(self, symbol: str) -> OISnapshot:
        """Fetch current open interest from /fapi/v1/openInterest."""
        params = {"symbol": symbol}
        data = await self._request("/fapi/v1/openInterest", params=params)
        return OISnapshot(
            symbol=symbol,
            timestamp_ms=int(data["time"]),
            open_interest=float(data["openInterest"]),
            open_interest_value=float(data.get("openInterest", 0.0)),
        )
