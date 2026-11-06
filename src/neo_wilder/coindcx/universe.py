"""CoinDCX symbol mapping and active universe manager for NEO-WILDER V4.

Conforms strictly to COINDCX_MANUAL_EXECUTION_SPEC.md §2:
- CoinDCX futures instruments use the 'B-{BASE}_USDT' pair format.
- Instruments are queried from /exchange/v1/derivatives/futures/data/active_instruments at startup.
- Any Binance symbol with no active CoinDCX instrument is DROPPED from the universe (never silently substituted).
"""

import logging
from typing import Dict, List, Optional, Set

from neo_wilder.data.rest_coindcx import CoinDCXPublicClient
from neo_wilder.domain.enums import SymbolTier

logger = logging.getLogger(__name__)


class SymbolUniverseManager:
    """Maintains valid Binance-to-CoinDCX symbol mappings."""

    def __init__(self, client: CoinDCXPublicClient):
        self.client = client
        # Map: binance_symbol -> coindcx_pair (e.g. "BTCUSDT" -> "B-BTC_USDT")
        self._binance_to_coindcx: Dict[str, str] = {}
        self._active_coindcx_pairs: Set[str] = set()

    @staticmethod
    def derive_coindcx_pair(binance_symbol: str) -> str:
        """Derive canonical CoinDCX futures pair name from Binance symbol.

        e.g. 'BTCUSDT' -> 'B-BTC_USDT', 'ETHUSDT' -> 'B-ETH_USDT'.
        """
        symbol = binance_symbol.upper()
        if symbol.endswith("USDT"):
            base = symbol[:-4]
            return f"B-{base}_USDT"
        return f"B-{symbol}"

    @staticmethod
    def get_symbol_tier(binance_symbol: str) -> SymbolTier:
        """Classify symbol as MAJOR or ALT."""
        if binance_symbol in ("BTCUSDT", "ETHUSDT"):
            return SymbolTier.MAJOR
        return SymbolTier.ALT

    async def initialize_universe(self, binance_symbols: List[str]) -> List[str]:
        """Fetch active instruments from CoinDCX and build valid universe.

        Returns list of approved Binance symbols that have active CoinDCX instruments.
        """
        raw_instruments = await self.client.get_active_instruments()
        self._active_coindcx_pairs.clear()
        self._binance_to_coindcx.clear()

        # Build set of active CoinDCX pairs
        for inst in raw_instruments:
            # CoinDCX active_instruments returns dicts with 'pair' or 'symbol'
            pair_name = inst.get("pair") or inst.get("symbol")
            status = inst.get("status", "active").lower()
            if pair_name and status in ("active", "trading"):
                self._active_coindcx_pairs.add(pair_name)

        valid_binance_symbols = []
        for b_sym in binance_symbols:
            expected_cdcx_pair = self.derive_coindcx_pair(b_sym)
            # If active_instruments was returned and instrument is found
            # (or if network mock allows fallback when mock is active)
            if expected_cdcx_pair in self._active_coindcx_pairs:
                self._binance_to_coindcx[b_sym] = expected_cdcx_pair
                valid_binance_symbols.append(b_sym)
            else:
                logger.warning(
                    f"Symbol {b_sym} (expected CoinDCX pair {expected_cdcx_pair}) is not active on CoinDCX. Dropping from universe."
                )

        logger.info(
            f"Initialized CoinDCX universe: {len(valid_binance_symbols)} of {len(binance_symbols)} symbols active."
        )
        return valid_binance_symbols

    def get_coindcx_pair(self, binance_symbol: str) -> Optional[str]:
        """Lookup CoinDCX pair for a Binance symbol."""
        return self._binance_to_coindcx.get(binance_symbol)

    def is_symbol_supported(self, binance_symbol: str) -> bool:
        """Check if Binance symbol is mapped to an active CoinDCX instrument."""
        return binance_symbol in self._binance_to_coindcx
