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
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from neo_wilder.clock import SystemClock
from neo_wilder.coindcx.universe import SymbolUniverseManager
from neo_wilder.coindcx.validator import CoinDCXExecutionValidator
from neo_wilder.config import load_config
from neo_wilder.data.rest_binance import BinanceRestClient
from neo_wilder.data.rest_coindcx import CoinDCXPublicClient
from neo_wilder.data.store import DatabaseStore
from neo_wilder.data.ws_binance import BinanceWebSocketClient
from neo_wilder.domain.enums import ExecutionMode
from neo_wilder.domain.models import Candidate, Candle, EdgeResult, FundingSnapshot, OISnapshot
from neo_wilder.edges.base import FeatureContext
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.edges.runner import EdgeRunner
from neo_wilder.features.atr import ATREngine
from neo_wilder.features.cvd import CVDEngine
from neo_wilder.features.funding import FundingContextResult, FundingEngine
from neo_wilder.features.liquidity import LiquidityEngine
from neo_wilder.features.obi import OBIEngine
from neo_wilder.features.regime import RegimeClassifier
from neo_wilder.features.rsi import RSIEngine
from neo_wilder.features.swings import SwingDetector
from neo_wilder.features.volume_profile import VolumeProfileEngine
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
from neo_wilder.strategies.s2_oi_exhaustion import S2OIExhaustionStrategy
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

        # Load authoritative configuration
        self.config_dir = Path("config")
        self.config = load_config(self.config_dir)

        self.db_path = os.getenv("DB_PATH", self.config.system.sqlite_path)
        self.store = DatabaseStore(self.db_path)

        # Configs & Registries
        self.edge_registry = EdgeRegistry(self.config_dir / "edge_registry.yaml")
        self.edge_runner = EdgeRunner(registry=self.edge_registry)

        # Clients
        self.binance_rest = BinanceRestClient(
            base_url=os.getenv("BINANCE_REST_URL", self.config.network.binance_rest_url)
        )
        self.coindcx_client = CoinDCXPublicClient(
            public_url=os.getenv("COINDCX_PUBLIC_URL", self.config.network.coindcx_public_rest_url),
            api_url=os.getenv("COINDCX_API_URL", self.config.network.coindcx_api_rest_url),
        )
        self.coindcx_validator = CoinDCXExecutionValidator(
            max_drift_pct=self.config.validation.max_price_drift_pct,
            max_spread_major=self.config.validation.max_spread_bps_major,
            max_spread_alt=self.config.validation.max_spread_bps_alt,
            default_clip_usd=self.config.validation.default_intended_clip_usd,
        )
        self.universe_manager = SymbolUniverseManager(self.coindcx_client)

        # Components
        self.governor = PortfolioGovernor(
            max_concurrent=self.config.portfolio.max_concurrent_trades,
            max_open_risk_pct=self.config.portfolio.max_total_open_risk_pct,
            cooldown_sec=self.config.portfolio.cooldown_sec,
            max_daily_loss_pct=self.config.portfolio.max_daily_loss_pct,
            max_weekly_loss_pct=self.config.portfolio.max_weekly_loss_pct,
        )
        self.veto_pipeline = VetoPipeline(self.governor)
        self.scorer = CompositeScorer(self.edge_registry)
        self.s1_strategy = S1SweepReclaimStrategy(
            baseline_friction_pct=self.config.friction.baseline_round_trip_friction_pct
        )
        self.s2_strategy = S2OIExhaustionStrategy()
        self.regime_classifier = RegimeClassifier()

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

        self.shadow_runner: Optional[ShadowRunner] = None
        if self.mode == ExecutionMode.SHADOW:
            self.shadow_runner = ShadowRunner(
                store=self.store,
                registry=self.edge_registry,
                scorer=self.scorer,
                mode=ExecutionMode.SHADOW,
            )

        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None
        self._derivatives_task: Optional[asyncio.Task] = None
        self.active_symbols: List[str] = []
        self.ws_client: Optional[BinanceWebSocketClient] = None

        # In-memory derivatives context cache (updated by background poller)
        self._funding_cache: Dict[str, FundingContextResult] = {}
        self._oi_history: Dict[str, List[OISnapshot]] = {}

    def _load_symbols(self) -> List[str]:
        """Load configured symbols from symbols.yaml."""
        symbols_path = self.config_dir / "symbols.yaml"
        if symbols_path.exists():
            with open(symbols_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                symbols_list = data.get("symbols", [])
                if isinstance(symbols_list, list):
                    return [
                        str(s.get("binance_symbol"))
                        for s in symbols_list
                        if isinstance(s, dict) and s.get("binance_symbol")
                    ]
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    async def start(self):
        """Start all subsystem async loops and network connections."""
        logger.info(
            f"Starting NEO-WILDER V4 in mode={self.mode.value} (Permanent SIGNAL_ONLY, SQLite WAL single writer)"
        )
        await self.store.start()

        # Reload open unresolved signals from SQLite for outcome tracking on restart
        self.outcome_resolver.reload_unresolved_signals()

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

        # Initialize and Start WebSocket Client
        ws_url = os.getenv("BINANCE_WS_URL", self.config.network.binance_ws_url)
        self.ws_client = BinanceWebSocketClient(self.active_symbols, base_ws_url=ws_url)
        self.ws_client.register_candle_callback(self.on_candle_close)
        await self.ws_client.start()
        logger.info(
            f"Binance WebSocket ingestion loop started for {len(self.active_symbols)} symbols."
        )

        # Start background health & derivatives polling loops
        self._health_task = asyncio.create_task(self._health_loop())
        self._derivatives_task = asyncio.create_task(self._poll_derivatives_loop())

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

                if veto_flags.get("V_H08"):
                    logger.critical(
                        f"V-H08 asserted: Process RSS {metrics['rss_mb']:.1f} MB exceeds 300 MB limit!"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)

    async def poll_derivatives_once(self) -> None:
        """Single polling cycle for Funding and Open Interest context across all active symbols.

        Ensures p_data lifecycle is strictly isolated per-symbol, preventing any mark price contamination.
        Funding and OI fetch failures are handled independently.
        """
        now_ms = int(time.time() * 1000)
        for sym in self.active_symbols:
            funding_snap: Optional[FundingSnapshot] = None
            # 1. Fetch Premium Index / Funding independently
            try:
                funding_snap = await self.binance_rest.get_premium_index(sym)
                if funding_snap:
                    self._funding_cache[sym] = FundingEngine.evaluate(funding_snap, now_ms)
            except Exception as e:
                logger.debug(f"Derivatives poll funding error for {sym}: {e}")

            # 2. Fetch Open Interest independently (strictly isolated to sym, no cross-symbol leak)
            try:
                oi_raw = await self.binance_rest.get_open_interest(sym)
                if oi_raw:
                    mark_p = funding_snap.mark_price if funding_snap else 0.0
                    oi_snap = OISnapshot(
                        symbol=sym,
                        timestamp_ms=oi_raw.timestamp_ms,
                        open_interest=oi_raw.open_interest,
                        open_interest_value=oi_raw.open_interest * mark_p,
                    )
                    if sym not in self._oi_history:
                        self._oi_history[sym] = []
                    self._oi_history[sym].append(oi_snap)
                    if len(self._oi_history[sym]) > 50:
                        self._oi_history[sym].pop(0)
            except Exception as e:
                logger.debug(f"Derivatives poll OI error for {sym}: {e}")

    async def _poll_derivatives_loop(self):
        """Periodic background loop invoking poll_derivatives_once."""
        while not self._shutdown_event.is_set():
            try:
                await self.poll_derivatives_once()
                await asyncio.sleep(float(self.config.network.rest_poll_interval_sec))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in derivatives poll loop: {e}")
                await asyncio.sleep(5.0)

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

            # 2. Query historical trailing candles (non-blocking)
            candles = await self.store.fetch_recent_candles_async(symbol, "15m", limit=100)
            if not candles or candles[-1].open_time_ms != candle.open_time_ms:
                candles.append(candle)
                await self.store.record_candle(symbol, "15m", candle)

            if len(candles) < 20:
                return

            # 3. Compute Real Features
            atr_res = ATREngine.compute(candles, period=14)
            if not atr_res:
                return

            swings = SwingDetector.find_swings(candles)
            pools = LiquidityEngine.detect_pools(swings, atr=atr_res.atr)
            regime_out = self.regime_classifier.evaluate(candles, atr_bps=atr_res.atr_bps)

            trades = list(self.ws_client.trade_buffers.get(symbol, [])) if self.ws_client else []
            cvd_res = CVDEngine.compute(trades) if trades else None
            vp_res = VolumeProfileEngine.compute(candles, bins=50)

            orderbook = (
                self.ws_client.depth_buffers[symbol][-1]
                if self.ws_client
                and symbol in self.ws_client.depth_buffers
                and self.ws_client.depth_buffers[symbol]
                else None
            )
            obi_res = OBIEngine.compute(orderbook) if orderbook else None
            rsi_res = RSIEngine.compute(candles, swings)

            funding_ctx = self._funding_cache.get(symbol)
            oi_snaps = self._oi_history.get(symbol, [])
            oi_snap = oi_snaps[-1] if oi_snaps else None

            ctx = FeatureContext(
                symbol=symbol,
                timeframe="15m",
                now_ms=candle.close_time_ms,
                candles=candles,
                atr_result=atr_res,
                swings=swings,
                pools=pools,
                regime_output=regime_out,
                volume_profile=vp_res,
                trades=trades,
                orderbook=orderbook,
                cvd_result=cvd_res,
                obi_result=obi_res,
                rsi_result=rsi_res,
                funding_context=funding_ctx,
                oi_snapshot=oi_snap,
                oi_history=oi_snaps,
            )

            # 4. Evaluate Real Edges via EdgeRunner
            edge_results: Dict[str, EdgeResult] = self.edge_runner.evaluate_all(ctx)

            # 5. Generate Candidate Setups (S1 always; S2 in SHADOW mode only)
            candidates_to_process: List[Candidate] = []
            s1_cand = self.s1_strategy.generate_candidate(ctx, edge_results)
            if s1_cand:
                candidates_to_process.append(s1_cand)

            if self.mode == ExecutionMode.SHADOW:
                s2_cand = self.s2_strategy.generate_candidate(ctx, edge_results)
                if s2_cand:
                    # S2 collision invariant: cannot fire within 30 min of S1 on the same symbol
                    if not self.governor.is_symbol_locked(symbol):
                        candidates_to_process.append(s2_cand)

            if not candidates_to_process:
                return

            for candidate in candidates_to_process:
                logger.info(
                    f"Candidate setup detected on {symbol} ({candidate.strategy_id}): "
                    f"Entry [{candidate.entry_zone_low} - {candidate.entry_zone_high}]"
                )

                # 6. Fetch CoinDCX Validation Quote
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
                        f"Candidate {symbol} ({candidate.strategy_id}) blocked by CoinDCX gate: "
                        f"{cdcx_val.reason} ({cdcx_val.veto_id})"
                    )
                    if self.mode == ExecutionMode.SHADOW and self.shadow_runner is not None:
                        await self.shadow_runner.handle_shadow_candidate(
                            candidate=candidate,
                            edge_results=edge_results,
                            veto_passed=False,
                            veto_blocking_id=cdcx_val.veto_id or "COINDCX_INVALID",
                            rejection_stage="COINDCX_VALIDATION",
                            rejection_reason=cdcx_val.reason,
                        )
                    continue

                # 7. Evaluate Veto Pipeline (Infrastructure, Risk Guard, Hard & Soft Vetoes)
                is_ws_disconnected = (
                    self.ws_client.is_stale_or_disconnected() if self.ws_client else True
                )
                orderbook_age_sec = (
                    (time.time() - (orderbook.timestamp_ms / 1000.0)) if orderbook else 999.0
                )
                is_orderbook_stale = orderbook_age_sec > 3.0

                passed, hard_res, soft_res = self.veto_pipeline.evaluate_candidate(
                    candidate=candidate,
                    ctx=ctx,
                    quote=cdcx_quote,
                    clock=self.clock,
                    is_ws_disconnected=is_ws_disconnected,
                    is_orderbook_stale=is_orderbook_stale,
                    publish_threshold=self.config.scoring.publish_threshold,
                )

                if not passed:
                    logger.info(
                        f"Candidate {symbol} ({candidate.strategy_id}) blocked by Veto: "
                        f"{hard_res.blocking_id} ({hard_res.reason_code})"
                    )
                    if self.mode == ExecutionMode.SHADOW and self.shadow_runner is not None:
                        await self.shadow_runner.handle_shadow_candidate(
                            candidate=candidate,
                            edge_results=edge_results,
                            veto_passed=False,
                            veto_blocking_id=hard_res.blocking_id or hard_res.reason_code,
                            rejection_stage="VETO_PIPELINE",
                            rejection_reason=hard_res.reason_code,
                        )
                    continue

                # 8. Compute Correlation-Aware Composite Quality Score with Real Edge Results
                score_breakdown = self.scorer.score(
                    candidate=candidate,
                    edge_results=edge_results,
                    confidence_penalty=soft_res.confidence_penalty,
                )

                threshold = self.config.scoring.publish_threshold + soft_res.threshold_increment
                if score_breakdown.total_score < threshold:
                    logger.info(
                        f"Candidate {symbol} ({candidate.strategy_id}) score {score_breakdown.total_score} "
                        f"below effective threshold {threshold:.1f}. Blocked."
                    )
                    if self.mode == ExecutionMode.SHADOW and self.shadow_runner is not None:
                        await self.shadow_runner.handle_shadow_candidate(
                            candidate=candidate,
                            edge_results=edge_results,
                            veto_passed=False,
                            veto_blocking_id=f"SCORE_{score_breakdown.total_score}_LT_{int(threshold)}",
                            rejection_stage="QUALITY_SCORE",
                            rejection_reason=f"Score {score_breakdown.total_score} < {threshold:.1f}",
                            score_override=score_breakdown.total_score,
                        )
                    continue

                # 9. Dispatch based on mode
                if self.mode == ExecutionMode.SHADOW:
                    if self.shadow_runner is not None:
                        await self.shadow_runner.handle_shadow_candidate(
                            candidate=candidate,
                            edge_results=edge_results,
                            veto_passed=True,
                            veto_blocking_id=None,
                            rejection_stage="CLEARED",
                            rejection_reason=None,
                            score_override=score_breakdown.total_score,
                        )
                    # STRICT INVARIANT: ZERO Telegram egress in SHADOW mode!
                    continue

                # 10. SIGNAL Mode: Build Immutable Signal & Publish to Telegram
                # In SIGNAL mode, S2 candidates never publish; only S1 can publish
                if candidate.strategy_id != "S1_SWEEP_RECLAIM":
                    continue

                sig_id = f"SIG-{symbol}-{int(datetime.now(timezone.utc).timestamp())}"
                created_at = datetime.now(timezone.utc)
                expiry_duration_min = max(1, candidate.expiry_bars) * 15
                expires_at = created_at + timedelta(minutes=expiry_duration_min)

                signal_obj = Signal(
                    signal_id=sig_id,
                    created_at_utc=created_at.isoformat(),
                    expires_at_utc=expires_at.isoformat(),
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
                    funding_pct_est=funding_ctx.funding_rate_pct if funding_ctx else 0.0,
                    net_rr=candidate.net_rr,
                    score_0_100=score_breakdown.total_score,
                    calibrated_probability="NOT CALIBRATED",
                    regime=regime_out.state,
                    btc_context="NEUTRAL",
                    veto_status="CLEARED",
                    soft_veto_list=soft_res.active_soft_vetoes,
                    max_entry_drift_pct=self.config.validation.max_price_drift_pct,
                    invalidation_conditions=[f"Bar closes below {candidate.stop_loss:.2f}"],
                    one_paragraph_thesis=(
                        f"{symbol} S1 sweep-reclaim confirmed at key liquidity pool with orthogonal edge confluence "
                        f"(Score: {score_breakdown.total_score}/100, Net R:R: {candidate.net_rr:.2f})."
                    ),
                )

                # Persist and Publish
                # Telegram failure must NOT record success in cooldown or journal as published!
                await self.publisher.publish(signal_obj)
                self.governor.record_signal_published(
                    symbol=symbol,
                    direction=candidate.direction.value,
                    strategy=candidate.strategy_id,
                )
                await self.signal_journal.log_signal(signal_obj)
                self.outcome_resolver.track_signal(signal_obj)
                logger.info(f"Signal {sig_id} successfully published and tracked.")

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
        if self._derivatives_task:
            self._derivatives_task.cancel()
            try:
                await self._derivatives_task
            except asyncio.CancelledError:
                pass
        if self.ws_client:
            await self.ws_client.stop()
        await self.binance_rest.close()
        await self.coindcx_client.close()
        await self.publisher.close()
        await self.store.stop()
        logger.info("Shutdown complete.")


def handle_signals(app: NeoWilderApplication, loop: asyncio.AbstractEventLoop):
    """Register graceful OS signal handlers."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(app.stop()))
        except NotImplementedError:
            # Signal handling on Windows
            pass


async def main():
    mode_str = os.getenv("EXECUTION_MODE", "SIGNAL").upper()
    mode = ExecutionMode.SHADOW if mode_str == "SHADOW" else ExecutionMode.SIGNAL
    app = NeoWilderApplication(mode=mode)

    loop = asyncio.get_running_loop()
    handle_signals(app, loop)

    await app.start()
    try:
        while not app._shutdown_event.is_set():
            await asyncio.sleep(1.0)
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
