"""Binance USD-M WebSocket streaming ingest for NEO-WILDER V4.

Maintains bounded ringbuffers adhering to the 220 MB RAM budget.
Feeds V-H05 (WS_DISCONNECTED) on stream drops > 5s.
"""

import asyncio
import json
import logging
import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional

import aiohttp

from neo_wilder.domain.models import AggTrade, Candle, OrderBookLevel, OrderBookSnapshot

logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """Manages Binance USD-M combined stream connection with bounded buffers."""

    def __init__(
        self,
        symbols: List[str],
        base_ws_url: str = "wss://fstream.binance.com/stream",
        max_disconnect_sec: float = 5.0,
    ):
        self.symbols = [s.lower() for s in symbols]
        self.base_ws_url = base_ws_url
        self.max_disconnect_sec = max_disconnect_sec

        # Bounded ringbuffers (RAM budget strictly enforced)
        self.trade_buffers: Dict[str, Deque[AggTrade]] = {
            s.upper(): deque(maxlen=20000) for s in self.symbols
        }
        self.depth_buffers: Dict[str, Deque[OrderBookSnapshot]] = {
            s.upper(): deque(maxlen=300) for s in self.symbols
        }
        self.kline_5m_buffers: Dict[str, Deque[Candle]] = {
            s.upper(): deque(maxlen=500) for s in self.symbols
        }
        self.kline_15m_buffers: Dict[str, Deque[Candle]] = {
            s.upper(): deque(maxlen=500) for s in self.symbols
        }
        self.liquidation_buffer: Deque[Dict] = deque(maxlen=1000)

        # Connection state
        self._running = False
        self._connected = False
        self._last_message_ts = 0.0
        self._task: Optional[asyncio.Task] = None
        self._candle_close_callbacks: List[Callable[[str, str, Candle], None]] = []

    def register_candle_callback(self, cb: Callable[[str, str, Candle], None]):
        """Register callback for completed candle closes."""
        self._candle_close_callbacks.append(cb)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def is_stale_or_disconnected(self) -> bool:
        """Feed for V-H05: disconnected or silence > max_disconnect_sec."""
        if not self._connected:
            return True
        return (time.monotonic() - self._last_message_ts) > self.max_disconnect_sec

    def _build_stream_url(self) -> str:
        streams = []
        for s in self.symbols:
            streams.append(f"{s}@aggTrade")
            streams.append(f"{s}@kline_5m")
            streams.append(f"{s}@kline_15m")
            streams.append(f"{s}@depth20@100ms")
        streams.append("!forceOrder@arr")
        return f"{self.base_ws_url}?streams={'/'.join(streams)}"

    async def start(self):
        """Start async listener task."""
        self._running = True
        self._task = asyncio.create_task(self._connection_loop())

    async def stop(self):
        """Stop connection loop."""
        self._running = False
        self._connected = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _connection_loop(self):
        """Exponential backoff reconnecting WebSocket loop."""
        backoff = 1.0
        while self._running:
            url = self._build_stream_url()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=15.0) as ws:
                        self._connected = True
                        self._last_message_ts = time.monotonic()
                        backoff = 1.0
                        logger.info("Binance WS stream connected successfully.")

                        async for msg in ws:
                            if not self._running:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                self._last_message_ts = time.monotonic()
                                self._handle_message(msg.data)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                logger.warning(f"Binance WS closed/error: {msg}")
                                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                logger.warning(f"Binance WS connection failed: {e}, retrying in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 1.5)
            finally:
                self._connected = False

    def _handle_message(self, raw_text: str):
        """Parse raw stream payload into typed dataclasses."""
        try:
            payload = json.loads(raw_text)
            stream_name = payload.get("stream", "")
            data = payload.get("data", {})

            if "@aggTrade" in stream_name:
                symbol = data["s"].upper()
                trade = AggTrade(
                    trade_id=int(data["a"]),
                    symbol=symbol,
                    price=float(data["p"]),
                    quantity=float(data["q"]),
                    timestamp_ms=int(data["T"]),
                    is_buyer_maker=bool(data["m"]),
                )
                if symbol in self.trade_buffers:
                    self.trade_buffers[symbol].append(trade)

            elif "@kline_5m" in stream_name or "@kline_15m" in stream_name:
                tf = "15m" if "@kline_15m" in stream_name else "5m"
                k = data["k"]
                symbol = data["s"].upper()
                candle = Candle(
                    open_time_ms=int(k["t"]),
                    close_time_ms=int(k["T"]),
                    open=float(k["o"]),
                    high=float(k["h"]),
                    low=float(k["l"]),
                    close=float(k["c"]),
                    volume=float(k["v"]),
                    is_closed=bool(k["x"]),
                )
                if tf == "15m":
                    if symbol in self.kline_15m_buffers:
                        self.kline_15m_buffers[symbol].append(candle)
                else:
                    if symbol in self.kline_5m_buffers:
                        self.kline_5m_buffers[symbol].append(candle)

                if candle.is_closed:
                    for cb in self._candle_close_callbacks:
                        try:
                            cb(symbol, tf, candle)
                        except Exception as e:
                            logger.error(f"Error in candle close callback ({tf}): {e}")

            elif "@depth20" in stream_name:
                symbol = stream_name.split("@")[0].upper()
                bids = [
                    OrderBookLevel(price=float(b[0]), quantity=float(b[1]))
                    for b in data.get("bids", [])
                ]
                asks = [
                    OrderBookLevel(price=float(a[0]), quantity=float(a[1]))
                    for a in data.get("asks", [])
                ]
                book = OrderBookSnapshot(
                    symbol=symbol,
                    timestamp_ms=int(data.get("E", int(time.time() * 1000))),
                    bids=bids,
                    asks=asks,
                )
                if symbol in self.depth_buffers:
                    self.depth_buffers[symbol].append(book)

            elif "!forceOrder" in stream_name:
                self.liquidation_buffer.append(data)

        except Exception as e:
            logger.debug(f"Failed to parse Binance WS payload: {e}")
