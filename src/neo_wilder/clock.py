"""System clock synchronization and monotonic time guarding for NEO-WILDER V4."""

import time


class SystemClock:
    """Monotonic system clock with exchange serverTime offset tracking."""

    def __init__(self, max_skew_ms: float = 1000.0):
        self._max_skew_ms = max_skew_ms
        self._last_server_offset_ms: float = 0.0
        self._last_sync_timestamp: float = 0.0

    def update_server_time(self, server_time_ms: int) -> float:
        """Calculate and update clock offset from Binance /fapi/v1/time."""
        local_now_ms = time.time() * 1000.0
        self._last_server_offset_ms = server_time_ms - local_now_ms
        self._last_sync_timestamp = time.monotonic()
        return self._last_server_offset_ms

    @property
    def skew_ms(self) -> float:
        """Current estimated clock skew in milliseconds."""
        return abs(self._last_server_offset_ms)

    def is_desynced(self) -> bool:
        """Return True if local clock deviates from exchange time by > max_skew_ms."""
        return self.skew_ms > self._max_skew_ms

    @staticmethod
    def now_ms() -> int:
        """Return current UTC epoch milliseconds."""
        return int(time.time() * 1000)

    @staticmethod
    def monotonic_sec() -> float:
        """Return monotonic seconds for interval measuring."""
        return time.monotonic()
