"""System health and resource monitor for NEO-WILDER V4.

Tracks process resident memory (RSS), event loop lag, and clock skew.
Enforces fail-closed veto flags when memory ceiling or clock skew is breached:
- V-H08: RSS > 300 MB (hard ceiling)
- V-H07: Clock skew > 1000 ms
"""

import asyncio
import logging
import os
import time
from typing import Dict, Optional, Tuple

import psutil

from neo_wilder.data.store import DatabaseStore

logger = logging.getLogger(__name__)

HARD_CEILING_RSS_MB = 300.0
TARGET_CEILING_RSS_MB = 220.0
MAX_CLOCK_SKEW_MS = 1000.0


class SystemHealthMonitor:
    """Monitors process resource utilization and event loop latency."""

    def __init__(self, store: Optional[DatabaseStore] = None):
        self.store = store
        self.process = psutil.Process(os.getpid())
        self._last_check_time = time.monotonic()

    def get_rss_mb(self) -> float:
        """Return process resident set size in megabytes."""
        try:
            rss_bytes = self.process.memory_info().rss
            return float(rss_bytes) / (1024.0 * 1024.0)
        except Exception as e:
            logger.warning(f"Error reading RSS memory: {e}")
            return 0.0

    async def measure_loop_lag_ms(self) -> float:
        """Measure event loop lag by measuring execution delay of zero sleep."""
        t0 = time.monotonic()
        await asyncio.sleep(0.0)
        lag_sec = time.monotonic() - t0
        return max(0.0, lag_sec * 1000.0)

    async def check_health(
        self, clock_skew_ms: float = 0.0
    ) -> Tuple[Dict[str, float], Dict[str, bool]]:
        """Run health check.

        Returns:
            metrics: dict of measured metrics (rss_mb, loop_lag_ms, clock_skew_ms)
            veto_flags: dict with V-H08 and V-H07 boolean flags (True if breached).
        """
        rss_mb = self.get_rss_mb()
        loop_lag_ms = await self.measure_loop_lag_ms()
        now_ms = int(time.time() * 1000)

        metrics = {
            "rss_mb": rss_mb,
            "loop_lag_ms": loop_lag_ms,
            "clock_skew_ms": clock_skew_ms,
        }

        # Check veto conditions
        veto_flags = {
            "V_H08": rss_mb > HARD_CEILING_RSS_MB,
            "V_H07": abs(clock_skew_ms) > MAX_CLOCK_SKEW_MS,
        }

        if veto_flags["V_H08"]:
            logger.critical(
                f"[V-H08 BREACH] Resident memory {rss_mb:.2f} MB exceeds hard ceiling {HARD_CEILING_RSS_MB} MB"
            )
        elif rss_mb > TARGET_CEILING_RSS_MB:
            logger.warning(
                f"Resident memory {rss_mb:.2f} MB exceeds target ceiling {TARGET_CEILING_RSS_MB} MB"
            )

        if veto_flags["V_H07"]:
            logger.critical(
                f"[V-H07 BREACH] Clock skew {clock_skew_ms:.1f} ms exceeds limit {MAX_CLOCK_SKEW_MS} ms"
            )

        if self.store is not None:
            await self.store.record_health(
                timestamp_ms=now_ms,
                rss_mb=rss_mb,
                skew_ms=clock_skew_ms,
                loop_lag_ms=loop_lag_ms,
            )

        return metrics, veto_flags
