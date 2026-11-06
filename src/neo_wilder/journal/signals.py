"""Signal journal persistence for NEO-WILDER V4."""

import json

from neo_wilder.data.store import DatabaseStore
from neo_wilder.publish.schema import Signal


class SignalJournal:
    """Records published signals into database store."""

    def __init__(self, store: DatabaseStore):
        self.store = store

    async def log_signal(self, sig: Signal):
        payload_dict = sig.to_dict()
        payload_json = json.dumps(payload_dict)
        await self.store.record_signal(payload_dict, payload_json)
