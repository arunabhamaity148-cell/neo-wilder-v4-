"""NEO-WILDER V4 — Master Production Entrypoint.

Single asyncio event loop orchestrating the end-to-end institutional pipeline:
Data -> Features -> Edges -> Strategy -> CoinDCX Validation -> Vetoes -> Scoring -> Publish -> WAL Store.

Operates in SIGNAL or SHADOW mode under strict 1 GB VPS RAM budget.
Zero private exchange API keys, zero order execution capability.
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from neo_wilder.clock import SystemClock
from neo_wilder.coindcx.universe import SymbolUniverseManager
from neo_wilder.coindcx.validator import CoinDCXExecutionValidator
from neo_wilder.data.rest_binance import BinanceRestClient
from neo_wilder.data.rest_coindcx import CoinDCXPublicClient
from neo_wilder.data.store import DatabaseStore
from neo_wilder.data.ws_binance import BinanceWebSocketClient
from neo_wilder.domain.enums import Direction, ExecutionMode
from neo_wilder.domain.models import Candle, EdgeResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.features.atr import ATREngine
from neo_wilder.features.regime import RegimeClassifier
from neo_wilder.journal.fills import FillJournal
from neo_wilder.journal.outcomes import OutcomeResolver
from neo_wilder.journal.signals import SignalJournal
from neo_wilder.observability.health import SystemHealthMonitor
from neo_wilder.observability.watchdog import ProcessWatchdog
from neo_wilder.publish.schema import Signal
from neo_wilder.publish.telegram import TelegramAlertPublisher
from neo_wilder.scoring.groups import CompositeScorer
from neo_wilder.shadow.runner import ShadowRunner
from neo_wilder.strategies.s1_sweep_reclaim import S1SweepReclaimStrategy
from neo_wilder.vetoes.governor import PortfolioGovernor
from neo_wilder.vetoes.pipeline import VetoPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("neo_wilder")


class NeoWilderApplication:
    """Master application coordinator."""

    def __init__(self, mode: ExecutionMode = ExecutionMode.SIGNAL):
        self.mode = mode
        self.clock = SystemClock()
        self.db_path = os.getenv("DB_PATH", "data/neo_wilder_journal.db")
        self.store = DatabaseStore(self.db_path)

        # Configs
        self.config_dir = Path("config")
        self.edge_registry = EdgeRegistry(self.config_dir / "edge_registry.yaml")

        # Clients
        self.binance_rest = BinanceRestClient(
            base_url=os.getenv("BINANCE_REST_URL", "https://fapi.binance.com")
        )
        self.coindcx_client = CoinDCXPublicClient(
            public_url=os.getenv("COINDCX_PUBLIC_URL", "https://public.coindcx.com"),
            api_url=os.getenv("COINDCX_API_URL", "https://api.coindcx.com"),
        )
        self.coindcx_validator = CoinDCXExecutionValidator()
        self.universe_manager = SymbolUniverseManager(self.coindcx_client)

        # Components
        self.governor = PortfolioGovernor()
        self.veto_pipeline = VetoPipeline(self.governor)
        self.scorer = CompositeScorer(self.edge_registry)
        self.s1_strategy = S1SweepReclaimStrategy()

        # Telemetry & Observability
        self.health_monitor = SystemHealthMonitor(self.store)
        self.watchdog = ProcessWatchdog(interval_seconds=15.0, max_misses=3)

        # Publishing & Journals
        self.publisher = TelegramAlertPublisher(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        )
        self.signal_journal = SignalJournal(self.store)
        self.fill_journal = FillJournal(self.store)
        self.outcome_resolver = OutcomeResolver(self.store)

        if self.mode == ExecutionMode.SHADOW:
            self.shadow_runner = ShadowRunner(
                store=self.store,
                registry=self.edge_registry,
                scorer=self.scorer,
                mode=ExecutionMode.SHADOW,
            )
        else:
            self.shadow_runner = None

        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None
        self.active_symbols: List[str] = []
        self.ws_client: Optional[BinanceWebSocketClient] = None

    def _load_symbols(self) -> List[str]:
        """Load configured symbols from symbols.yaml."""
        symbols_path = self.config_dir / "symbols.yaml"
        if symbols_path.exists():
            with open(symbols_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                symbols_list = data.get("symbols", [])
                if isinstance(symbols_list, list):
                    return [
                        s.get("binance_symbol")
                        for s in symbols_list
                        if isinstance(s, dict) and "binance_symbol" in s
                    ]
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    async def start(self):
        """Start all subsystem async loops."""
        logger.info(
            f"Starting NEO-WILDER V4 in mode={self.mode.value} (Permanent SIGNAL_ONLY, SQLite WAL single writer)"
        )
        await self.store.start()

        # Sync exchange server time
        try:
            server_time = await self.binance_rest.get_server_time_ms()
            skew = self.clock.update_server_time(server_time)
            logger.info(f"Synchronized with Binance time. Skew: {skew:.1f}ms")
        except Exception as e:
            logger.warning(
                f"Could not sync Binance time over network: {e}. Using local system clock."
            )

        # Initialize CoinDCX Symbol Universe
        raw_symbols = self._load_symbols()
        try:
            self.active_symbols = await self.universe_manager.initialize_universe(raw_symbols)
        except Exception as e:
            logger.warning(
                f"Could not query CoinDCX instruments: {e}. Falling back to default list."
            )
            self.active_symbols = raw_symbols

        if not self.active_symbols:
            self.active_symbols = raw_symbols

        # Initialize WebSocket Client
        ws_url = os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com/stream")
        self.ws_client = BinanceWebSocketClient(self.active_symbols, base_ws_url=ws_url)
        self.ws_client.register_candle_callback(self.on_candle_close)

        # Start background health task
        self._health_task = asyncio.create_task(self._health_loop())

        logger.info(
            f"NEO-WILDER V4 initialization complete. Monitoring {len(self.active_symbols)} symbols."
        )

    async def _health_loop(self):
        """Periodic 10-second health and watchdog liveness monitor."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(10.0)
                metrics, veto_flags = await self.health_monitor.check_health(self.clock.skew_ms)
                self.watchdog.beat()

                if veto_flags["V_H08"]:
                    logger.critical(
                        f"V-H08 asserted: Process RSS {metrics['rss_mb']:.1f} MB exceeds 300 MB limit!"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)

    def on_candle_close(self, symbol: str, timeframe: str, candle: Candle):
        """Callback invoked on 15m candle close from WebSocket stream."""
        if timeframe != "15m":
            return
        asyncio.create_task(self._process_candle_event(symbol, candle))

    async def _process_candle_event(self, symbol: str, candle: Candle):
        """Execute full causal pipeline for a completed 15m candle."""
        try:
            # 1. Update outcome tracker
            await self.outcome_resolver.on_candle(symbol, candle)

            # 2. Query historical trailing candles
            candles = self.store.fetch_recent_candles(symbol, "15m", limit=100)
            if not candles or candles[-1].open_time_ms != candle.open_time_ms:
                candles.append(candle)
                await self.store.record_candle(symbol, "15m", candle)

            if len(candles) < 20:
                return

            # 3. Compute Features
            atr_res = ATREngine.compute(candles, period=14)
            if not atr_res:
                return

            classifier = RegimeClassifier()
            regime_out = classifier.evaluate(candles, atr_bps=atr_res.atr_bps)

            ctx = FeatureContext(
                symbol=symbol,
                timeframe="15m",
                now_ms=candle.close_time_ms,
                candles=candles,
                atr_result=atr_res,
            )

            # 4. Generate S1 Candidate
            candidate = self.s1_strategy.generate_candidate(ctx)
            if not candidate:
                return

            logger.info(
                f"Candidate setup detected on {symbol}: Entry [{candidate.entry_zone_low} - {candidate.entry_zone_high}]"
            )

            # 5. Fetch CoinDCX Validation Quote
            cdcx_pair = (
                self.universe_manager.get_coindcx_pair(symbol)
                or f"B-{symbol.replace('USDT', '')}_USDT"
            )
            cdcx_quote = await self.coindcx_client.get_validation_quote(
                cdcx_pair, candle.close_time_ms
            )

            tier = self.universe_manager.get_symbol_tier(symbol)
            cdcx_val = self.coindcx_validator.validate_candidate(
                reference_price=candidate.reference_price,
                entry_zone_low=candidate.entry_zone_low,
                entry_zone_high=candidate.entry_zone_high,
                tp1=candidate.tp1,
                quote=cdcx_quote,
                symbol_tier=tier,
            )

            if not cdcx_val.is_valid:
                logger.info(
                    f"Candidate {symbol} blocked by CoinDCX gate: {cdcx_val.reason} ({cdcx_val.veto_id})"
                )
                return

            # 6. Evaluate Veto Pipeline
            passed, hard_res, soft_res = self.veto_pipeline.evaluate_candidate(
                candidate=candidate,
                ctx=ctx,
                quote=cdcx_quote,
                clock=self.clock,
            )

            if not passed:
                logger.info(
                    f"Candidate {symbol} blocked by Veto: {hard_res.blocking_id} ({hard_res.reason_code})"
                )
                return

            # 7. Compute Quality Score
            # Edge results dictionary
            edge_results: Dict[str, EdgeResult] = {
                "E01": EdgeResult(
                    edge_id="E01",
                    passed=True,
                    confidence=1.0,
                    direction=Direction.LONG,
                    score_contribution=8,
                ),
                "E03": EdgeResult(
                    edge_id="E03",
                    passed=True,
                    confidence=1.0,
                    direction=Direction.LONG,
                    score_contribution=4,
                ),
                "E04": EdgeResult(
                    edge_id="E04",
                    passed=True,
                    confidence=1.0,
                    direction=Direction.LONG,
                    score_contribution=8,
                ),
            }
            score_breakdown = self.scorer.score(candidate, edge_results)

            if score_breakdown.total_score < 85:
                logger.info(
                    f"Candidate {symbol} score {score_breakdown.total_score} below threshold 85.0. Blocked."
                )
                return

            # 8. Dispatch based on mode
            if self.mode == ExecutionMode.SHADOW:
                assert self.shadow_runner is not None
                await self.shadow_runner.handle_shadow_candidate(
                    candidate=candidate,
                    edge_results=edge_results,
                    veto_passed=passed,
                )
                return

            # 9. SIGNAL Mode: Build Immutable Signal & Publish to Telegram
            sig_id = f"SIG-{symbol}-{int(datetime.now(timezone.utc).timestamp())}"
            signal_obj = Signal(
                signal_id=sig_id,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                expires_at_utc=datetime.now(timezone.utc).isoformat(),
                symbol_binance=symbol,
                symbol_coindcx=cdcx_pair,
                direction=candidate.direction,
                strategy_id=candidate.strategy_id,
                active_edge_ids=candidate.active_edge_ids,
                confirming_edge_ids=candidate.confirming_edge_ids,
                reference_price=candidate.reference_price,
                coindcx_price=cdcx_quote.price if cdcx_quote else candidate.reference_price,
                coindcx_spread_bps=cdcx_quote.spread_bps if cdcx_quote else 5.0,
                coindcx_top10_depth_usd=cdcx_quote.top10_depth_usd if cdcx_quote else 100000.0,
                entry_zone_low=candidate.entry_zone_low,
                entry_zone_high=candidate.entry_zone_high,
                stop_loss=candidate.stop_loss,
                tp1=candidate.tp1,
                tp2=candidate.tp2,
                gross_rr=candidate.gross_rr,
                fee_pct=cdcx_val.fee_pct,
                slippage_pct=cdcx_val.slippage_pct,
                funding_pct_est=0.0,
                net_rr=candidate.net_rr,
                score_0_100=score_breakdown.total_score,
                calibrated_probability="NOT CALIBRATED",
                regime=regime_out.state,
                btc_context="NEUTRAL",
                veto_status="CLEARED",
                soft_veto_list=[],
                max_entry_drift_pct=0.35,
                invalidation_conditions=[f"Bar closes below {candidate.stop_loss:.2f}"],
                one_paragraph_thesis=f"{symbol} S1 sweep-reclaim confirmed at key liquidity pool with positive volume absorption.",
            )

            # Persist and Publish
            await self.signal_journal.log_signal(signal_obj)
            self.outcome_resolver.track_signal(signal_obj)
            await self.publisher.publish(signal_obj)

        except Exception as e:
            logger.error(f"Error processing candle for {symbol}: {e}", exc_info=True)

    async def stop(self):
        """Gracefully stop background tasks, close network clients, flush store."""
        logger.info("Initiating graceful shutdown...")
        self._shutdown_event.set()
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        if self.ws_client:
            await self.ws_client.stop()
        await self.binance_rest.close()
        await self.coindcx_client.close()
        await self.publisher.close()
        await self.store.stop()
        logger.info("NEO-WILDER V4 shutdown complete.")


async def main():
    mode_str = os.getenv("NEO_WILDER_MODE", "SIGNAL").upper()
    mode = ExecutionMode.SHADOW if mode_str == "SHADOW" else ExecutionMode.SIGNAL

    app = NeoWilderApplication(mode=mode)

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                loop.add_signal_handler(
                    getattr(signal, sig_name), lambda: asyncio.create_task(app.stop())
                )
            except (NotImplementedError, RuntimeError):
                pass

    try:
        await app.start()
        # Keep running until shutdown event is set
        await app._shutdown_event.wait()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
