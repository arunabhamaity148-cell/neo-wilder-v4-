"""Operator self-report /fill command handler and journal for NEO-WILDER V4.

Conforms strictly to COINDCX_MANUAL_EXECUTION_SPEC.md §5.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from neo_wilder.data.store import DatabaseStore

logger = logging.getLogger(__name__)

# Format: /fill <signal_id> <price> <size>
FILL_REGEX = re.compile(
    r"^/fill\s+([a-zA-Z0-9_\-]+)\s+([0-9]*\.?[0-9]+)\s+([0-9]*\.?[0-9]+)$",
    re.IGNORECASE,
)


def parse_fill_command(text: str) -> Optional[Tuple[str, float, float]]:
    """Parse a Telegram /fill message string.

    Returns (signal_id, price, size) if valid, or None if malformed or non-positive.
    """
    text = text.strip()
    match = FILL_REGEX.match(text)
    if not match:
        return None

    signal_id, price_str, size_str = match.groups()
    try:
        price = float(price_str)
        size = float(size_str)
    except ValueError:
        return None

    if price <= 0.0 or size <= 0.0:
        return None

    return signal_id, price, size


class FillJournal:
    """Manages manual operator fill persistence."""

    def __init__(self, store: DatabaseStore):
        self.store = store

    async def process_fill_command(self, text: str) -> Tuple[bool, str]:
        """Validate and record a fill command from Telegram / operator chat.

        Returns (success: bool, reply_message: str).
        """
        parsed = parse_fill_command(text)
        if not parsed:
            return (
                False,
                "❌ Invalid /fill command. Required format: `/fill <signal_id> <price> <size>` with positive values.",
            )

        signal_id, price, size = parsed
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        await self.store.record_fill(
            signal_id=signal_id,
            price=price,
            size=size,
            timestamp_utc=timestamp_utc,
        )
        logger.info(f"Recorded fill for signal {signal_id}: price={price}, size={size}")
        return True, f"✅ Fill recorded for `{signal_id}`: Price={price}, Size={size}"
