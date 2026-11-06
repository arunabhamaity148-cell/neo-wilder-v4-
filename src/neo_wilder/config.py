"""Configuration loader and schema validation for NEO-WILDER V4.

Loads and reconciles config/base.yaml and config/thresholds.yaml.
Maintains single-source-of-truth invariants without duplicate drift.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SystemSettings:
    process_model: str = "single_asyncio"
    max_rss_mb_target: int = 220
    hard_rss_ceiling_mb: int = 300
    sqlite_path: str = "data/neo_wilder_journal.db"
    sqlite_wal: bool = True
    sqlite_cache_size: int = -20000


@dataclass
class NetworkSettings:
    binance_ws_url: str = "wss://fstream.binance.com/stream"
    binance_rest_url: str = "https://fapi.binance.com"
    coindcx_public_rest_url: str = "https://public.coindcx.com"
    coindcx_api_rest_url: str = "https://api.coindcx.com"
    rest_poll_interval_sec: int = 30
    ws_disconnect_veto_sec: float = 5.0
    clock_desync_limit_ms: int = 1000


@dataclass
class ValidationSettings:
    max_price_drift_pct: float = 0.35
    max_spread_bps_major: float = 12.0
    max_spread_bps_alt: float = 25.0
    min_orderbook_depth_mult: float = 20.0
    default_intended_clip_usd: float = 500.0
    late_entry_max_progress: float = 0.35


@dataclass
class FrictionSettings:
    coindcx_taker_fee_pct: float = 0.050
    coindcx_maker_fee_pct: float = 0.044
    indian_gst_rate_pct: float = 18.0
    effective_round_trip_fee_pct: float = 0.1180
    slippage_spread_factor: float = 0.5
    slippage_atr_factor: float = 0.3
    slippage_floor_bps: float = 1.0
    baseline_round_trip_friction_pct: float = 0.1354


@dataclass
class RiskGeometrySettings:
    min_net_rr: float = 1.50
    min_sl_pct: float = 0.65
    min_sl_atr_factor: float = 0.50
    max_sl_atr_factor: float = 4.50
    max_entry_zone_atr_factor: float = 0.50
    min_entry_zone_width_pct: float = 0.20
    min_entry_zone_width_atr_factor: float = 0.05
    max_slippage_pct_of_stop: float = 15.0


@dataclass
class PortfolioSettings:
    max_concurrent_trades: int = 2
    max_total_open_risk_pct: float = 3.0
    cooldown_sec: float = 1800.0
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 6.0


@dataclass
class ScoringSettings:
    publish_threshold: float = 85.0
    base_setup_points: int = 60
    c1_c2_combined_cap: int = 24
    max_rr_bonus: int = 4


@dataclass
class AppConfig:
    version: str = "4.0.0"
    mode: str = "SIGNAL"
    system: SystemSettings = field(default_factory=SystemSettings)
    network: NetworkSettings = field(default_factory=NetworkSettings)
    validation: ValidationSettings = field(default_factory=ValidationSettings)
    friction: FrictionSettings = field(default_factory=FrictionSettings)
    risk_geometry: RiskGeometrySettings = field(default_factory=RiskGeometrySettings)
    portfolio: PortfolioSettings = field(default_factory=PortfolioSettings)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    thresholds: Dict[str, Any] = field(default_factory=dict)


def load_config(config_dir: Optional[Path] = None) -> AppConfig:
    """Load configuration from base.yaml and thresholds.yaml.

    Falls back to frozen specification defaults if configuration files are unavailable.
    """
    cfg_dir = config_dir or Path("config")
    app_cfg = AppConfig()

    base_path = cfg_dir / "base.yaml"
    if base_path.exists():
        try:
            with open(base_path, "r", encoding="utf-8") as f:
                base_data = yaml.safe_load(f) or {}

            app_cfg.version = base_data.get("version", app_cfg.version)
            app_cfg.mode = base_data.get("mode", app_cfg.mode)

            # System
            sys_d = base_data.get("system", {})
            app_cfg.system = SystemSettings(
                process_model=sys_d.get("process_model", app_cfg.system.process_model),
                max_rss_mb_target=int(
                    sys_d.get("max_rss_mb_target", app_cfg.system.max_rss_mb_target)
                ),
                hard_rss_ceiling_mb=int(
                    sys_d.get("hard_rss_ceiling_mb", app_cfg.system.hard_rss_ceiling_mb)
                ),
                sqlite_path=sys_d.get("sqlite_path", app_cfg.system.sqlite_path),
                sqlite_wal=bool(sys_d.get("sqlite_wal", app_cfg.system.sqlite_wal)),
                sqlite_cache_size=int(
                    sys_d.get("sqlite_cache_size", app_cfg.system.sqlite_cache_size)
                ),
            )

            # Network
            net_d = base_data.get("network", {})
            app_cfg.network = NetworkSettings(
                binance_ws_url=net_d.get("binance_ws_url", app_cfg.network.binance_ws_url),
                binance_rest_url=net_d.get("binance_rest_url", app_cfg.network.binance_rest_url),
                coindcx_public_rest_url=net_d.get(
                    "coindcx_public_rest_url", app_cfg.network.coindcx_public_rest_url
                ),
                coindcx_api_rest_url=net_d.get(
                    "coindcx_api_rest_url", app_cfg.network.coindcx_api_rest_url
                ),
                rest_poll_interval_sec=int(
                    net_d.get("rest_poll_interval_sec", app_cfg.network.rest_poll_interval_sec)
                ),
                ws_disconnect_veto_sec=float(
                    net_d.get("ws_disconnect_veto_sec", app_cfg.network.ws_disconnect_veto_sec)
                ),
                clock_desync_limit_ms=int(
                    net_d.get("clock_desync_limit_ms", app_cfg.network.clock_desync_limit_ms)
                ),
            )

            # Validation
            val_d = base_data.get("execution_validation", {})
            app_cfg.validation = ValidationSettings(
                max_price_drift_pct=float(
                    val_d.get("max_price_drift_pct", app_cfg.validation.max_price_drift_pct)
                ),
                max_spread_bps_major=float(
                    val_d.get("max_spread_bps_major", app_cfg.validation.max_spread_bps_major)
                ),
                max_spread_bps_alt=float(
                    val_d.get("max_spread_bps_alt", app_cfg.validation.max_spread_bps_alt)
                ),
                min_orderbook_depth_mult=float(
                    val_d.get(
                        "min_orderbook_depth_mult", app_cfg.validation.min_orderbook_depth_mult
                    )
                ),
                default_intended_clip_usd=float(
                    val_d.get(
                        "default_intended_clip_usd", app_cfg.validation.default_intended_clip_usd
                    )
                ),
            )

            # Friction
            fric_d = base_data.get("friction_model", {})
            app_cfg.friction = FrictionSettings(
                coindcx_taker_fee_pct=float(
                    fric_d.get("coindcx_taker_fee_pct", app_cfg.friction.coindcx_taker_fee_pct)
                ),
                coindcx_maker_fee_pct=float(
                    fric_d.get("coindcx_maker_fee_pct", app_cfg.friction.coindcx_maker_fee_pct)
                ),
                indian_gst_rate_pct=float(
                    fric_d.get("indian_gst_rate_pct", app_cfg.friction.indian_gst_rate_pct)
                ),
                effective_round_trip_fee_pct=float(
                    fric_d.get(
                        "effective_round_trip_fee_pct",
                        app_cfg.friction.effective_round_trip_fee_pct,
                    )
                ),
                baseline_round_trip_friction_pct=float(
                    fric_d.get(
                        "baseline_round_trip_friction_pct",
                        app_cfg.friction.baseline_round_trip_friction_pct,
                    )
                ),
            )

            # Risk Geometry
            rg_d = base_data.get("risk_geometry", {})
            app_cfg.risk_geometry = RiskGeometrySettings(
                min_net_rr=float(rg_d.get("min_net_rr", app_cfg.risk_geometry.min_net_rr)),
                min_sl_pct=float(rg_d.get("min_sl_pct", app_cfg.risk_geometry.min_sl_pct)),
                min_sl_atr_factor=float(
                    rg_d.get("min_sl_atr_factor", app_cfg.risk_geometry.min_sl_atr_factor)
                ),
                max_sl_atr_factor=float(
                    rg_d.get("max_sl_atr_factor", app_cfg.risk_geometry.max_sl_atr_factor)
                ),
                max_entry_zone_atr_factor=float(
                    rg_d.get(
                        "max_entry_zone_atr_factor", app_cfg.risk_geometry.max_entry_zone_atr_factor
                    )
                ),
            )

            # Portfolio
            port_d = base_data.get("portfolio", {})
            app_cfg.portfolio = PortfolioSettings(
                max_concurrent_trades=int(
                    port_d.get("max_concurrent_trades", app_cfg.portfolio.max_concurrent_trades)
                ),
                max_total_open_risk_pct=float(
                    port_d.get("max_total_open_risk_pct", app_cfg.portfolio.max_total_open_risk_pct)
                ),
                cooldown_sec=float(port_d.get("cooldown_sec", app_cfg.portfolio.cooldown_sec)),
                max_daily_loss_pct=float(
                    port_d.get("max_daily_loss_pct", app_cfg.portfolio.max_daily_loss_pct)
                ),
                max_weekly_loss_pct=float(
                    port_d.get("max_weekly_loss_pct", app_cfg.portfolio.max_weekly_loss_pct)
                ),
            )

            # Scoring
            score_d = base_data.get("scoring", {})
            app_cfg.scoring = ScoringSettings(
                publish_threshold=float(
                    score_d.get("publish_threshold", app_cfg.scoring.publish_threshold)
                ),
                base_setup_points=int(
                    score_d.get("base_setup_points", app_cfg.scoring.base_setup_points)
                ),
                c1_c2_combined_cap=int(
                    score_d.get("c1_c2_combined_cap", app_cfg.scoring.c1_c2_combined_cap)
                ),
            )
            logger.info("Loaded configuration from config/base.yaml successfully.")
        except Exception as e:
            logger.warning(
                f"Error loading config/base.yaml: {e}. Using frozen specification defaults."
            )

    thresh_path = cfg_dir / "thresholds.yaml"
    if thresh_path.exists():
        try:
            with open(thresh_path, "r", encoding="utf-8") as f:
                thresh_data = yaml.safe_load(f) or {}
            app_cfg.thresholds = thresh_data.get("thresholds", {})
            if "publish_threshold" in app_cfg.thresholds:
                app_cfg.scoring.publish_threshold = float(app_cfg.thresholds["publish_threshold"])
            if "min_net_rr" in app_cfg.thresholds:
                app_cfg.risk_geometry.min_net_rr = float(app_cfg.thresholds["min_net_rr"])
            if "max_drift_pct" in app_cfg.thresholds:
                app_cfg.validation.max_price_drift_pct = float(app_cfg.thresholds["max_drift_pct"])
            if "max_spread_bps_major" in app_cfg.thresholds:
                app_cfg.validation.max_spread_bps_major = float(
                    app_cfg.thresholds["max_spread_bps_major"]
                )
            if "max_spread_bps_alt" in app_cfg.thresholds:
                app_cfg.validation.max_spread_bps_alt = float(
                    app_cfg.thresholds["max_spread_bps_alt"]
                )
            if "late_entry_max_progress" in app_cfg.thresholds:
                app_cfg.validation.late_entry_max_progress = float(
                    app_cfg.thresholds["late_entry_max_progress"]
                )
            logger.info("Loaded thresholds from config/thresholds.yaml successfully.")
        except Exception as e:
            logger.warning(f"Error loading config/thresholds.yaml: {e}.")

    return app_cfg
