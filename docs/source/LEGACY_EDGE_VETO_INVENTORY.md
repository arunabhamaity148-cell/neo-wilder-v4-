# LEGACY_EDGE_VETO_INVENTORY.md
Source of truth: `neo-audit-final.zip` -> `neo-wilder-signal-bot/` (201 files, 30 dirs).
All line references are to files inside `src/neo_wilder_signal_bot/` unless stated.

## 0. Count reconciliation (read this first)
| Claimed in supplied docs | Verified in code | Verdict |
|---|---|---|
| 14 hard vetoes | `guards/pipeline.py` wires **11** guards; `guards/vetoes.py` defines **7** numeric vetoes + 1 news flag = 8, and `VetoEngine` is **not** imported by the pipeline | **UNVERIFIED / CONTRADICTED** |
| 56 hard-veto reason codes | `domain/enums.py::HardVetoReason` has exactly **56** members | CONFIRMED |
| "Edges 1-7" | `strategies/edges.py` wires only `EDGE_1`; `advanced_edges.py` implements `EDGE_6`, `EDGE_7`; **EDGE_2..EDGE_5 have no evaluator** | 5 of 7 exist |
| Score /200 | `scoring/quality_score.py` max = 100; `telegram/formatter.py:106` prints `/200` | **BUG (CONFIRMED)** |
| 49 test modules | `tests/*.py` = 49 | CONFIRMED |

## 1. Verified legacy edges
| ID | Name | File:line | Status in code | Data needed | Verdict for V4 |
|---|---|---|---|---|---|
| E01 | Liquidity Sweep + Reclaim (setup core) | `strategies/sweep_reclaim_v1.py:60-240`, `features/liquidity_pools.py:76` | Implemented, wired | 15m klines + swings | **RETAIN as spine** |
| E02 | 4-Stage Sweep Confirmation | `features/sweep_detector.py:49` | Implemented, used as evidence flag only | 15m klines + ATR | SHADOW |
| E03 | Sweep depth / ATR normalisation | `scoring/calibration.py:49` (x1) | Feature only | ATR series | RETAIN as feature |
| E04 | Liquidity pool detection (EQH/EQL) | `features/liquidity_pools.py:51` | Implemented | swings | RETAIN |
| E05 | Market structure BOS/CHoCH | `features/structure.py:42` | Implemented, not gating | swings/klines | SHADOW -> gating after test |
| E06 | Supply/Demand zones | `features/zones.py:38` | Implemented, evidence only | klines | SHADOW |
| E07 | Volume Profile POC/VAH/VAL | `features/volume_profile.py:40` | Implemented, target source | klines | RETAIN (targets) |
| E08 | Anchored VWAP | `features/anchored_vwap.py:13,51` | Implemented | klines + anchor | EXPERIMENTAL |
| E09 | Poor High / Poor Low | `features/poor_hl_fvg.py:22` | Implemented | klines | EXPERIMENTAL |
| E10 | Fair Value Gap (FVG) | `features/poor_hl_fvg.py:69` | Implemented, score slot 8 pts | klines | SHADOW |
| E11 | ATR / volatility regime | `features/volatility.py:59,112` | Implemented | klines | RETAIN (SL + sizing) |
| E12 | Dynamic SL buffer (ATR pct + funding) | `strategies/sweep_reclaim_v1.py:34` | Implemented | ATR, funding | RETAIN |
| E13 | Z_liq liquidation burst | `features/liq_heatmap.py:16` | Implemented over `!forceOrder@arr` ring | liquidation stream | SHADOW |
| E14 | Liquidation cluster proximity | `features/liq_heatmap.py:68` | Implemented | liquidation stream | EXPERIMENTAL |
| E15 | CVD turn | `features/orderflow.py:58` | Implemented | aggTrade | SHADOW |
| E16 | Order Book Imbalance | `features/orderflow.py:15` | Implemented, score slot 10 pts | depth20 | SHADOW |
| E17 | Book density / absorption | `features/book_density.py:17,44` | Implemented | depth20 | SHADOW |
| E18 | Microprice | `features/micro_price.py:15` | Implemented, unused | depth20 | REJECT (latency) |
| E19 | Microbar / volume clock | `features/microbar.py:16,74` | Implemented, unused | aggTrade | REJECT (complexity) |
| E20 | Hawkes intensity | `features/hawkes.py:33,56` | Implemented, feeds veto 3 | aggTrade | SHADOW (diagnostic) |
| E21 | OI exhaustion (EDGE_6) | `strategies/advanced_edges.py:159` | Implemented, wired | OI 1m + 4h lows | SHADOW (promising) |
| E22 | Spot-led basis (EDGE_7) | `strategies/advanced_edges.py:218` | Implemented, wired | perp vs spot | EXPERIMENTAL |
| E23 | Funding context | `features/funding_context.py:85` | Implemented | premiumIndex | RETAIN (veto input) |
| E24 | Mark/Index divergence | `features/funding_context.py:60` | Implemented | mark + index | RETAIN (veto) |
| E25 | Variance-ratio regime | `strategies/router.py:34`, `regime/vr_tracker.py` | **Two conflicting implementations** | closes | SHADOW |
| E26 | GEX / gamma flip | `cold/deribit.py:93-161` | Implemented with **assumed dealer signs** | Deribit options OI+IV | **REJECT for routing** |
| E27 | Session classification | `validation/walk_forward.py:100` | Implemented (analysis only) | timestamps | EXPERIMENTAL |
| E28 | Expiry engine (time/MFE/OI) | `journal/expiry_engine.py:32-355` | Implemented | signal + klines + OI | RETAIN (signal validity) |

## 2. Verified legacy vetoes and guards
| ID | Guard | File | Threshold in code | In pipeline? | V4 |
|---|---|---|---|---|---|
| G01 | Kill switch | `guards/kill_switch.py:18` | manual flag | YES | RETAIN, mandatory |
| G02 | VPS memory | `guards/vps_memory.py:37` | 300-350 MB RSS | YES | RETAIN, mandatory |
| G03 | Data health | `guards/data_health.py:22` | stale/gap/not-trading/mark-index<=0 | YES | RETAIN, mandatory |
| G04 | Book desync | `guards/execution_quality.py:98` | wire lag > 500 ms, seq break | YES | RETAIN, mandatory |
| G05 | Slippage/spread | `guards/execution_quality.py:18` | 5 bps major / 15 bps alt; slip/stop > 15% | YES | RETAIN + recalibrate for CoinDCX |
| G06 | Risk geometry | `guards/risk_geometry.py:94` | min SL 0.65%, net RR >= 1.30 | YES | RETAIN, raise RR to 1.50 |
| G07 | Portfolio heat | `guards/portfolio_risk.py:22` | max 4 trades, 6.0% total, 1.5%/trade | YES | CONFLICT with G12 -> unify at 2 / 3.0% |
| G08 | Cluster heat | `guards/cluster_heat.py:26` | max_eff_risk 2.0 | YES | RETAIN |
| G09 | Funding settlement window | `guards/volatility_funding.py:76` | -15 min / +5 min | YES | RETAIN, mandatory |
| G10 | Volatility + basis | `guards/volatility_funding.py:27` | ATR ratio 2.5, basis 0.50% | YES | RETAIN |
| G11 | News | `guards/news.py:22` | -15 min / +30 min, TTL 2 h | YES | RETAIN, mandatory |
| V1 | Fee geometry (orphan) | `guards/vetoes.py:30` | SL 0.65%, netRR 1.30 | **NO** | merge into G06 |
| V2 | Book spoofing / withdrawal (orphan) | `guards/vetoes.py:35` | spread > 2.5x median, 55% depth pull | **NO** | merge into G05 as SHADOW |
| V3 | BTC lead-lag / Hawkes (orphan) | `guards/vetoes.py:47` | BTC 5m ret +-0.35%, lambda thresh | **NO** | SHADOW, then enable if it ablates positively |
| V4 | Toxic funding (orphan) | `guards/vetoes.py:61` | |funding| > 0.05%, +-15 min | **NO** | duplicate of G09 -> delete duplicate |
| V5 | 15m counter-trend (orphan) | `guards/vetoes.py:69` | VWAP + EMA21 slope | **NO** | SHADOW |
| V6 | OI/CVD exhaustion (orphan) | `guards/vetoes.py:83` | OI drop >= 0.8% + CVD sign | **NO** | SHADOW |
| V7 | Memory pressure (orphan) | `guards/vetoes.py:98` | RSS > 350 MB | **NO** | duplicate of G02 -> delete |
| G12 | Concurrency governor | `guards/governors.py:18` | max 2 concurrent | **NO** | RETAIN, wire in |
| G13 | Symbol lock / cooldown | `guards/governors.py:47`, `guards/symbol_lock.py:21` | 1800 s | **NO** | RETAIN, mandatory |
| G14 | Loss governor | `guards/governors.py:74` | -3% day, -6% week, DD -5% step-down | **NO** | RETAIN, mandatory |
| G15 | Watchdog / degradation ladder | `guards/watchdog.py:120,214` | RSS/CPU steal/notify | **NO** | RETAIN, mandatory |
| G16 | Symbol lock guard | `guards/symbol_lock.py:21` | 30 min TTL | **NO** | merge with G13 |

## 3. Verified integrity defects (all CONFIRMED by file inspection)
1. `telegram/formatter.py` and `adapters/telegram/formatter.py` are byte-identical (both 8,312 B) yet
   `adapters/telegram/` has no `publisher.py` -> the adapter path cannot publish.
2. `guards/vetoes.py::VetoEngine` is dead code: `create_default_guard_pipeline()` does not import it.
3. Three incompatible score thresholds: `quality_score.SCORE_THRESHOLD = 76`,
   `calibration.MIN/MAX_SCORE_CUTOFF = 76..86`, `config/base.yaml scoring.publish_threshold = 85.0`.
4. Two incompatible R:R thresholds: `config guards.min_r_multiple = 1.5` vs `vetoes.MIN_NET_RR_RATIO = 1.30`.
5. Two incompatible concurrency limits: `portfolio_risk.max_concurrent_trades = 4` vs `governors.ClusterHeatGovernor(max_concurrent=2)`.
6. Two incompatible regime taxonomies: `strategies/router.py` (5 states, int) vs `regime/vr_tracker.py` (3 states, str).
7. Score slots exist for "idea2/idea3/idea4/idea5" with no evaluator -> phantom edges inflate max score.
8. `execution/coindcx_client.py:133-149` HMAC-signs a private POST to `/exchange/v1/derivatives/futures/positions`;
   `execution/maker_engine.py`, `exit_manager.py`, `adapters/exchange/execution_bridge.py`,
   `adapters/exchange/indian_adapter.py` exist -> **the legacy repo violates the SIGNAL_ONLY contract.**
9. `attach: docs/ARCHITECTURE.md` describes a 128-byte SHM bridge and hot/cold dual daemons; on a 1 GB /
   2 vCPU box that is ~2x baseline RSS for zero signal-quality gain.
10. `apply_fixes.py` (largest file in repo) is a patch script, i.e. the repo is mid-refactor, not a release.
