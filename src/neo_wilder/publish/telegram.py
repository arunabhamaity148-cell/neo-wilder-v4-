"""Single canonical Telegram alert publisher and formatter for NEO-WILDER V4.

Conforms strictly to COINDCX_MANUAL_EXECUTION_SPEC.md §3 and §5.
Displays score as /100 (never /200).
"""

import asyncio
import logging
from typing import Optional

import aiohttp

from neo_wilder.publish.schema import Signal

logger = logging.getLogger(__name__)


class TelegramAlertPublisher:
    """Formats and transmits immutable signals to Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._session = session
        self._owns_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5.0))
            self._owns_session = True
        return self._session

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def format_signal(sig: Signal) -> str:
        """Render markdown text for Telegram transmission."""
        dir_emoji = "🟢 LONG" if sig.direction.value == "LONG" else "🔴 SHORT"
        active_edges_str = ", ".join(sig.active_edge_ids)
        confirm_edges_str = (
            ", ".join(sig.confirming_edge_ids) if sig.confirming_edge_ids else "None"
        )
        soft_vetoes_str = ", ".join(sig.soft_veto_list) if sig.soft_veto_list else "None"
        invalidations_str = (
            "; ".join(sig.invalidation_conditions) if sig.invalidation_conditions else "None"
        )

        tp2_str = f"{sig.tp2:.2f}" if sig.tp2 is not None else "UNSPECIFIED"

        text = f"""⚡ **NEO-WILDER V4 SIGNAL ALERT**
{dir_emoji} **{sig.symbol_binance}** ({sig.symbol_coindcx})
ID: `{sig.signal_id}` | Strategy: `{sig.strategy_id}`

📊 **Setup & Context**
• Regime: {sig.regime.value}
• BTC Context: {sig.btc_context}
• Active Edges: {active_edges_str}
• Confirmations: {confirm_edges_str}

🎯 **Execution Geometry (Manual CoinDCX)**
• Reference Close (Binance): {sig.reference_price:.2f}
• CoinDCX Price: {sig.coindcx_price:.2f} (Spread: {sig.coindcx_spread_bps:.1f} bps)
• Top-10 Depth: ${sig.coindcx_top10_depth_usd:,.0f}
• Entry Zone: [{sig.entry_zone_low:.2f} – {sig.entry_zone_high:.2f}]
• Stop Loss: {sig.stop_loss:.2f}
• Target TP1: {sig.tp1:.2f}
• Target TP2: {tp2_str}

📐 **Risk & Quality Metrics**
• Gross R:R: {sig.gross_rr:.2f}
• Fees + GST: {sig.fee_pct:.3f}% | Slippage: {sig.slippage_pct:.3f}%
• **Net R:R: {sig.net_rr:.2f}**
• **Composite Score: {sig.score_0_100}/100**
• Calibrated Probability: `{sig.calibrated_probability}`
• Veto Status: {sig.veto_status} (Soft: {soft_vetoes_str})
• Max Drift Allowed: {sig.max_entry_drift_pct:.2f}%

⚠️ **Thesis & Invalidation**
• Thesis: {sig.one_paragraph_thesis}
• Invalidation: {invalidations_str}
• Expiry: {sig.expires_at_utc}

📌 *DISCLAIMER: Permanent SIGNAL_ONLY. No automated execution.*
*Self-report fill after manual entry:* `/fill {sig.signal_id} <price> <size>`"""
        return text

    async def publish(self, sig: Signal) -> Optional[int]:
        """Publish signal to Telegram with retry loop.

        Returns Telegram message ID if successful, or None on failure.
        """
        message_text = self.format_signal(sig)

        if not self.bot_token or not self.chat_id:
            logger.warning(
                f"Telegram credentials not configured (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing). "
                f"Alert formatted locally for {sig.signal_id} but not transmitted:\n{message_text}"
            )
            return None

        # Mask chat ID for secure observability
        masked_chat = (
            f"***{str(self.chat_id)[-4:]}" if len(str(self.chat_id)) > 4 else "***"
        )
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        session = await self._get_session()
        for attempt in range(3):
            try:
                logger.info(
                    f"Attempting to transmit signal {sig.signal_id} ({sig.symbol_binance} {sig.direction.value}) "
                    f"to Telegram chat {masked_chat} (attempt {attempt + 1}/3)..."
                )
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg_id = data.get("result", {}).get("message_id")
                        logger.info(
                            f"Telegram transmission SUCCESS: signal {sig.signal_id} published, message_id={msg_id}"
                        )
                        return msg_id
                    else:
                        text = await resp.text()
                        logger.warning(
                            f"Telegram transmission HTTP {resp.status} on attempt {attempt + 1}/3: {text}"
                        )
            except Exception as e:
                logger.warning(f"Telegram transmission network error on attempt {attempt + 1}/3: {e}")
            await asyncio.sleep(1.0 * (attempt + 1))

        logger.error(
            f"Telegram transmission FAILED: signal {sig.signal_id} could not be delivered after 3 attempts."
        )
        return None
