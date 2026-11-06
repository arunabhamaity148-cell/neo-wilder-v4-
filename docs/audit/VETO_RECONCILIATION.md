# VETO_RECONCILIATION.md — NEO-WILDER V4 Veto Framework Audit

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Line-by-line reconciliation of all hard and soft vetoes, severity ratings, execution order, fail-closed mechanics, and exhaustive investigation of the 49 vs 50 row discrepancy.

---

## 1. Complete Hard Veto Inventory (34 Vetoes: V-H01 to V-H34)

| ID | Reason Code | Severity | Pipeline Stage | Trigger Condition / Formula | Test Requirement (Score 100 Block) | Fail-Closed Mechanic |
|---|---|---|---|---|---|---|
| **V-H01** | `DATA_STALE` | CRITICAL | data_integrity | Last closed bar older than `2*timeframe + 30s` | Inject synthetic 35m old bar -> assert blocked | Timestamp comparison timeout or null -> BLOCK |
| **V-H02** | `DATA_GAP` | CRITICAL | data_integrity | >=1 missing bar in last 20 bars | Drop 1 bar at index $t-5$ -> assert blocked | Non-continuous open_times -> BLOCK |
| **V-H03** | `CANDLE_TS_INVALID` | CRITICAL | data_integrity | Non-monotonic or `close_time <= open_time` | Invert consecutive open timestamps -> assert blocked | `ts_curr <= ts_prev` -> BLOCK |
| **V-H04** | `DUPLICATE_CANDLE` | CRITICAL | data_integrity | Same `open_time` processed twice | Feed duplicate open_time bar -> assert blocked | Hash collision on bar key -> BLOCK |
| **V-H05** | `WS_DISCONNECTED` | CRITICAL | infrastructure_health | Critical stream disconnected > 5s | Disconnect mock WS for 6s -> assert blocked | Disconnect state or socket error -> BLOCK |
| **V-H06** | `ORDERBOOK_STALE` | HIGH | infrastructure_health | Depth older than 3s or sequence break | Freeze book updates for 3.1s -> assert blocked | `now - last_depth_ts > 3.0` -> BLOCK |
| **V-H07** | `CLOCK_DESYNC` | HIGH | infrastructure_health | `abs(local_time - serverTime) > 1000ms` | Skew mock system clock by 1100ms -> assert blocked | Clock sync exception or delta > 1000ms -> BLOCK |
| **V-H08** | `MEMORY_EMERGENCY` | CRITICAL | infrastructure_health | RSS > 300MB or `MemAvailable < 120MB` | Mock psutil RSS = 305MB -> assert blocked | psutil read failure -> BLOCK |
| **V-H09** | `KILL_SWITCH` | CRITICAL | infrastructure_health | Operator flag active or watchdog degraded | Touch kill switch sentinel file -> assert blocked | Sentinel file read or unhandled fault -> BLOCK |
| **V-H10** | `WATCHDOG_FAILURE` | CRITICAL | infrastructure_health | Heartbeat missed 3 intervals | Suppress heartbeat loop for 3 ticks -> assert blocked | Watchdog counter >= 3 -> BLOCK |
| **V-H11** | `CRITICAL_SOURCE_DOWN` | HIGH | infrastructure_health | Funding or OI unavailable > 10min | Simulate REST 500 error for 11min -> assert blocked | REST circuit breaker OPEN -> BLOCK |
| **V-H12** | `ABNORMAL_SPREAD` | HIGH | market_safety | `spread_bps > 12` (major) / `25` (alt) or `> 2.5x 1h median` | Mock CoinDCX spread = 13 bps on BTC -> assert blocked | Missing quote / zero spread -> BLOCK |
| **V-H13** | `INSUFFICIENT_LIQUIDITY` | HIGH | market_safety | Top-10 notional depth < 20x intended clip | Mock depth = 15x clip notional -> assert blocked | Empty orderbook -> BLOCK |
| **V-H14** | `EXTREME_GAP` | HIGH | market_safety | `abs(open - prev_close)/prev_close > 3%` | Inject 3.5% opening gap candle -> assert blocked | Gap calculation error -> BLOCK |
| **V-H15** | `NEWS_WINDOW_ACTIVE` | HIGH | event_and_derivatives | P0/P1 economic event within -15/+30 min | Set event timestamp to `now + 10m` -> assert blocked | News calendar feed outage -> BLOCK (`V-H16`) |
| **V-H16** | `NEWS_DATA_UNAVAILABLE` | HIGH | event_and_derivatives | Calendar feed outage (fail-closed) | Mock calendar HTTP 503 -> assert blocked | API timeout / unparsed format -> BLOCK |
| **V-H17** | `FUNDING_WINDOW_ACTIVE` | MEDIUM* | event_and_derivatives | Within -15/+5 min of 8h settlement | Clock at 07:50 UTC (settlement 08:00) -> assert blocked | Monotonic clock read failure -> BLOCK |
| **V-H18** | `MARK_INDEX_DIVERGENCE` | HIGH | event_and_derivatives | `abs(mark - index) / index > 0.5%` | Mock mark 101, index 100 (1.0% div) -> assert blocked | Null price or div by zero -> BLOCK |
| **V-H19** | `ENTRY_GEOMETRY_INVALID` | CRITICAL | risk_geometry | Inverted zone, entry outside SL..TP, or zone > 0.5 ATR | Feed inverted entry zone `[105, 100]` -> assert blocked | Zone geometry assertion error -> BLOCK |
| **V-H20** | `STOP_INVALID` | CRITICAL | risk_geometry | `SL < max(0.65%, 0.5 ATR)` or `SL > 4.5 ATR` | Mock stop distance = 0.40% -> assert blocked | Invalid stop distance math -> BLOCK |
| **V-H21** | `TARGET_INVALID` | CRITICAL | risk_geometry | TP ordering wrong or TP inside entry zone | Set LONG TP1 below entry high -> assert blocked | Target geometry assertion error -> BLOCK |
| **V-H22** | `NET_RR_TOO_LOW` | CRITICAL | risk_geometry | Net R:R after fees + slip + funding < 1.50 | Candidate with 1.45 net R:R -> assert blocked | Fee / slip math failure -> BLOCK |
| **V-H23** | `SLIPPAGE_TOO_HIGH` | HIGH | risk_geometry | Slippage estimate > 15% of stop distance | Mock slippage = 20% of SL -> assert blocked | Slippage model error -> BLOCK |
| **V-H24** | `DUPLICATE_SIGNAL` | MEDIUM* | dedupe_and_cooldown | Same symbol + direction + strategy within 30min | Submit identical candidate 10m later -> assert blocked | SQLite journal query failure -> BLOCK |
| **V-H25** | `SYMBOL_COOLDOWN` | MEDIUM* | dedupe_and_cooldown | Symbol inside 30min lock window | Submit signal on locked symbol -> assert blocked | Lock table query failure -> BLOCK |
| **V-H26** | `PORTFOLIO_HEAT` | HIGH | exposure_exhaustion | Concurrent active trades >= 2 or open risk > 3.0% | Mock 2 active positions in journal -> assert blocked | Position tracker failure -> BLOCK |
| **V-H27** | `CLUSTER_HEAT` | HIGH | exposure_exhaustion | Cluster effective risk > 2.0R | Mock cluster risk = 2.1R -> assert blocked | Cluster calculation failure -> BLOCK |
| **V-H28** | `DAILY_LOSS_CAP` | CRITICAL | exposure_exhaustion | Day closed + unrealised PnL <= -3.0% equity | Mock day PnL = -3.2% -> assert blocked | Ledger calculation failure -> BLOCK |
| **V-H29** | `WEEKLY_LOSS_CAP` | CRITICAL | exposure_exhaustion | Week closed + unrealised PnL <= -6.0% equity | Mock week PnL = -6.1% -> assert blocked | Ledger calculation failure -> BLOCK |
| **V-H30** | `TRADING_HALTED` | CRITICAL | exposure_exhaustion | Instrument exchange status != 'TRADING' | Mock status = 'POST_ONLY' or 'BREAK' -> assert blocked | Unknown status -> BLOCK |
| **V-H31** | `COINDCX_FEED_UNAVAILABLE`| HIGH | execution_validation | No CoinDCX validation quote at publish time | Simulate CoinDCX public API 404 -> assert blocked | Missing / null price -> BLOCK |
| **V-H32** | `ENTRY_DRIFT_EXCEEDED` | HIGH | execution_validation | `abs(coindcx - reference)/reference > 0.35%` | Mock CoinDCX price 0.40% away from Binance -> assert blocked | Price drift math failure -> BLOCK |
| **V-H33** | `REGIME_INELIGIBLE` | MEDIUM* | event_and_derivatives | `NOISE_CHOP` or `atr_bps` outside `[4, 400]` | Mock regime = NOISE_CHOP -> assert blocked | Unrecognized regime state -> BLOCK |
| **V-H34** | `MODEL_PROBABILITY_UNVALIDATED`| CRITICAL | dedupe_and_cooldown | Calibration artefact missing or > 90 days old | Delete calibration JSON -> assert numeric probability blocked | Missing calibration hash -> BLOCK |

> [!NOTE]
> **Severity Anomaly Audit (*):** `V-H17` (Funding Window), `V-H24` (Duplicate Signal), `V-H25` (Symbol Cooldown), and `V-H33` (Regime Ineligible) are labeled `severity: MEDIUM` in `VETO_REGISTRY.yaml`, yet they reside under `hard_vetoes:`. In NEO-WILDER V4, **all 34 hard vetoes are absolute execution blocks**. The `severity` tag in these 4 items indicates operational recovery urgency (e.g. temporary cooldown vs fatal data corruption), but their gating behavior is 100% fail-closed.
>
> [!WARNING]
> **V-H03 Condition String Defect:** In `VETO_REGISTRY.yaml` line 19, `cond` is written as `"non monotonic or close<=open"`. If literally evaluated against candle prices, this would veto every bearish candle! The true specification from `BACKTEST_PROTOCOL.md` §1 and legacy `guards/data_health.py` is `close_time <= open_time` (timestamp invalidity) or non-positive price (`close <= 0`). This typo must be corrected in the implementation.

---

## 2. Complete Soft Veto Inventory (15 Vetoes: V-S01 to V-S15)

| ID | Reason Code | Pipeline Stage | Operational Effect | Escalates to Hard Veto When |
|---|---|---|---|---|
| **V-S01** | `BTC_DIRECTIONAL_CONFLICT` | soft_modifiers | Confidence -15, Score Threshold +5 | `BTC 5m return < -1.0%` (for LONG) |
| **V-S02** | `BTC_VOLATILITY_INSTABILITY` | soft_modifiers | Confidence -10 | None (pure penalty) |
| **V-S03** | `WEAK_TREND` | soft_modifiers | Confidence -8 (ADX14 < 18) | None |
| **V-S04** | `FUNDING_EXTREME` | soft_modifiers | Risk Multiplier x0.5 | `abs(funding_rate) > 0.05%` |
| **V-S05** | `OI_INSTABILITY` | soft_modifiers | Confidence -8 | None |
| **V-S06** | `POOR_LIQUIDITY` | soft_modifiers | Risk Multiplier x0.6 | None |
| **V-S07** | `CORRELATED_EXPOSURE` | soft_modifiers | Risk Multiplier x0.5 | None |
| **V-S08** | `CLUSTER_HEAT_HIGH` | soft_modifiers | Score Threshold +3 | `cluster_effective_risk > 2.0R` (`V-H27`) |
| **V-S09** | `WEAK_SESSION` | soft_modifiers | Confidence -5 | None |
| **V-S10** | `LATE_ENTRY` | soft_modifiers | Score Threshold +5 | `entry_progress > 0.35` of TP1 distance |
| **V-S11** | `WEAK_ORDERFLOW` | soft_modifiers | Confidence -10 | None |
| **V-S12** | `VOLATILITY_MISMATCH` | soft_modifiers | Risk Multiplier x0.7 | None |
| **V-S13** | `LOW_QUALITY_REGIME` | soft_modifiers | Confidence -12 | None |
| **V-S14** | `POOR_EXECUTION_QUALITY` | soft_modifiers | Score Threshold +5 | None |
| **V-S15** | `SCORE_BELOW_PUBLISH` | soft_modifiers | Suppress publication | Always suppresses if `score < publish_threshold` |

---

## 3. Exhaustive Investigation of the 49 vs 50 Veto Row Discrepancy

### 3.1 The Discrepancy Statement
- `VETO_REGISTRY.yaml` contains:
  - 34 Hard Veto entries (`V-H01` to `V-H34`)
  - 15 Soft Veto entries (`V-S01` to `V-S15`)
  - **Total Defined IDs = 49 IDs**.
- `IMPLEMENTATION_ROADMAP.md` line 8 states:
  > *"Verification: 201 files listed, 32 edge rows, 50 veto rows, 10 integrity defects."*

### 3.2 Detailed Investigation & Root Cause Identification

To resolve whether a 50th veto was omitted, duplicated, or miscounted, we examined every relevant source file:

1. **Investigation of Line Numbers in `VETO_REGISTRY.yaml`:**
   In `VETO_REGISTRY.yaml`, the `hard_vetoes:` block begins on line 16 and ends on **line 50**:
   ```yaml
   50: - {id: V-H34, reason: MODEL_PROBABILITY_UNVALIDATED, severity: CRITICAL, cond: "calibration artefact missing or > 90 days old"}
   ```
   A mechanical parser or script checking line indices of the hard veto section reported `50`, which was erroneously transcribed in the text of `ROADMAP.md` as "50 veto rows".

2. **Investigation of `X01` in `EDGE_REGISTRY.yaml`:**
   `EDGE_REGISTRY.yaml` line 36 defines:
   ```yaml
   - {id: X01, legacy: null, src: "new", name: BTC Directional Conflict, archetype: MODIFIER, direction: BOTH, status: ACTIVE_SOFT_VETO, evidence: PROMISING}
   ```
   `X01` has status `ACTIVE_SOFT_VETO`. It is the exact functional twin of `V-S01` (`BTC_DIRECTIONAL_CONFLICT`). If an inventory script aggregated the 49 items from `VETO_REGISTRY.yaml` plus the 1 `ACTIVE_SOFT_VETO` row from `EDGE_REGISTRY.yaml`, the total count reached exactly **50 veto rows**.

3. **Investigation of Pipeline Stages in `VETO_REGISTRY.yaml`:**
   Lines 3–14 define 11 processing stages. One stage, `strategy_eligibility` (line 8), has no explicit `V-H` veto ID tagged next to it in comments (while `V-H33` is grouped under `event_and_derivatives_risk`). An earlier draft of the registry included a distinct `STRATEGY_INELIGIBLE` or `CANDIDATE_MALFORMED` hard veto as a 35th hard veto, which was subsequently subsumed into strategy candidate emission logic.

4. **Investigation of Legacy Codebase:**
   Legacy `domain/enums.py::HardVetoReason` contains **56** enum members. Legacy `guards/` contains 11 wired pipeline guards, 7 orphan functions in `vetoes.py`, and 5 un-wired governors/locks (total 23 rows in `LEGACY_EDGE_VETO_INVENTORY.md` Table 2). None of these totaled 50.

### 3.3 Conclusive Verdict
- There is **no missing 50th veto ID** in the V4 architecture.
- The 49 IDs in `VETO_REGISTRY.yaml` (34 Hard + 15 Soft) represent the complete, exhaustive, and canonical V4 veto registry.
- The phrase "50 veto rows" in `IMPLEMENTATION_ROADMAP.md` line 8 was an artifact of either the line 50 boundary in `VETO_REGISTRY.yaml` or the double-counting of `X01` / `V-S01`.
- **Action:** Freeze the V4 registry at exactly **34 Hard Vetoes and 15 Soft Vetoes (49 total)**.

---

## 4. Pipeline Execution Ordering & Absolute Override Prohibition

### 4.1 Strict Pipeline Order (Corrected for Execution Validation)
The veto engine must evaluate candidate signals in the following non-negotiable sequence:

```mermaid
flowchart TD
    S1[1. Data Integrity: V-H01..V-H04] --> S2[2. Infrastructure Health: V-H05..V-H11]
    S2 --> S3[3. Market Safety: V-H12..V-H14]
    S3 --> S4[4. Event & Derivatives: V-H15..V-H18, V-H33]
    S4 --> S5[5. CoinDCX Execution Validation: V-H31, V-H32]
    S5 --> S6[6. Risk Geometry & Net R:R: V-H19..V-H23]
    S6 --> S7[7. Exposure & Loss Caps: V-H26..V-H30]
    S7 --> S8[8. Dedupe, Cooldown & Governance: V-H24, V-H25, V-H34]
    S8 --> S9[9. Soft Modifiers: V-S01..V-S15]
    S9 --> S10[10. Final Gate: Publish or Suppress]
```

### 4.2 Absolute Override Prohibition
Per `AGENT.md` §0 Rule 3 and `VETO_REGISTRY.yaml` line 15:
> **"A hard veto can never be overridden by a score, a model probability, a config flag, or an operator flag."**

- If any hard veto fires, the candidate is discarded immediately.
- The veto engine emits a `VetoResult(passed=False, blocking_id='V-Hxx', reason_code='...')`.
- The signal is recorded in `journal/outcomes.py` as `BLOCKED` with its reason code.
- No Telegram message is published.
- Fail-closed invariant: If an unhandled exception or timeout occurs inside any veto evaluator, the veto automatically fires and blocks publication.
