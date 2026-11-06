# MODULE_CONTRACTS.md — NEO-WILDER V4 Subsystem Interfaces & Contracts

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Specification of typed input/output boundaries, dependencies, error handling, test contracts, and import layering for all modules under `src/neo_wilder/`.

---

## 1. Architectural Layering & Import Boundaries

To ensure zero circular dependencies, high testability, and deterministic replaying, all modules must strictly adhere to the unidirectional dependency ladder:

```
[Layer 0: Clock & Schema / Types]
       │
       ▼
[Layer 1: Data Plane (WS Ingest, REST Poller, Integrity, Store)]
       │
       ▼
[Layer 2: Feature Plane (Pure Transforms, Numpy Arrays, No I/O)]
       │
       ▼
[Layer 3: Edge Plane (Pure Edge Evaluators, EdgeResult)]
       │
       ▼
[Layer 4: Strategy Plane (Candidate Generation, Geometry)]
       │
       ▼
[Layer 5: Veto Plane (Ordered Hard Vetoes, Soft Modifiers, Fail-Closed)]
       │
       ▼
[Layer 6: Scoring Plane (Orthogonal Cluster Caps, Isotonic Calibration)]
       │
       ▼
[Layer 7: Publish Plane (Immutable Signal Schema, Telegram Formatter)]
       │
       ▼
[Layer 8: Journal & Observability (SQLite WAL Writer, Watchdog, Metrics)]
```

### Strict Import Invariants
1. Lower layers **must never import from higher layers** (e.g. `features/` cannot import `strategies/` or `publish/`).
2. `features/` and `edges/` must be **pure functions** (no network, no file I/O, no access to database, no global mutable state).
3. **No pandas in live path**: pure `numpy` and standard library `dataclasses` / `typing` only.
4. Total RSS must not exceed 220 MB baseline (hard cap at 300 MB).

---

## 2. Comprehensive Module Contract Table

| Subsystem / Module | Primary Responsibility | Input Types | Output Types | Direct Dependencies | Error Handling Contract | Unit Test Requirement | Integration Test Requirement |
|---|---|---|---|---|---|---|---|
| **`clock.py`** | ServerTime synchronization & monotonic time guarding | Server response timestamps | `MonotonicTime`, skew delta float | None | Skew > 1000ms triggers `V-H07` | Mock server time offset tests | Clock skew injection drill |
| **`data/ws_binance.py`** | Ingest Binance WS (`aggTrade`, `kline_5m`, `depth20`, `!forceOrder`) | Raw JSON stream from WebSocket | Typed event dataclasses (`AggTrade`, `Depth20`, etc.) | `clock.py` | Exp backoff reconnect (1–30s); socket drop >5s sets `V-H05` | Mock websocket framing | 6-hour soak test with zero unhandled drops |
| **`data/rest_binance.py`** | Poll OI, premiumIndex, klines chunking | REST endpoints | Snapshot dataclasses (`FundingSnapshot`, `OISnapshot`) | `aiohttp`, rate limiter | 3 retries with backoff; 10min failure triggers `V-H11` | Nock / mock HTTP endpoints | Live smoke test |
| **`data/rest_coindcx.py`** | Public validation quote and orderbook fetch | CoinDCX REST endpoints | `CoinDCXQuote`, `CoinDCXDepth` | `aiohttp`, rate limiter | HTTP 404/empty/timeout immediately triggers `V-H31` | Synthetic CoinDCX response fixtures | Live smoke test against public API |
| **`data/integrity.py`** | Bar continuity, duplicate, and gap auditing | Ingested candle streams | `DataQuality` flag & validated arrays | `store.py` | Gap or non-monotonic timestamps trigger `V-H01..V-H04` | Fuzz testing on corrupted timestamps | Historical gap replay test |
| **`data/store.py`** | SQLite WAL persistence with single-writer loop | Event / Bar dataclasses | Persisted SQLite rows | `aiosqlite` | Single background queue; WAL flush failure logs CRITICAL | In-memory SQLite CRUD tests | High-throughput write stress test |
| **`features/swings.py`** | Identify structural swing highs and lows | Price arrays (`high`, `low`) | `List[SwingPivot]` | `numpy` | Returns empty list if bars < minimum window | Positive swing detection fixture | Historical determinism test |
| **`features/liquidity.py`**| Detect Equal Highs / Lows (`E04`) | `List[SwingPivot]`, ATR | `List[LiquidityPool]` | `numpy`, `swings.py` | Returns empty list on insufficient swings | Synthetic pool clustering fixture | Replay parity check |
| **`features/structure.py`**| BOS and CHoCH detection (`E05`) | `List[SwingPivot]`, price array | `StructureState` | `numpy`, `swings.py` | Returns `None` if structure broken | Structural break positive/negative tests | Replay parity check |
| **`features/volume_profile.py`**| Compute session POC, VAH, VAL (`E07`)| Price and volume arrays | `VolumeProfileLevels` | `numpy` | Returns fallback empty if volume sum == 0 | Pre-calculated profile fixture | Parity vs reference profile |
| **`features/atr.py`** | 14-period Wilder ATR and volatility tiers (`E11`)| `high`, `low`, `close` arrays | `float` ATR, `ATRPercentileTier` | `numpy` | Returns `None` if len < 15 bars | Mathematical golden fixture test | Precision parity vs Wilder standard |
| **`features/funding.py`** | Track funding magnitude & basis divergence (`E23`, `E24`)| `mark_price`, `index_price`, `funding_rate` | `FundingContext` | `numpy` | Returns `None` if values non-positive | Mark/index divergence fixture | Replay parity check |
| **`features/cvd.py`** | Cumulative Volume Delta and inflection turns (`E15`)| `AggTrade` sequence | `CVDState` (slope, z-score) | `numpy` | Returns `None` if trade count < threshold | CVD inflection positive/negative tests | Replay parity check |
| **`features/obi.py`** | Top-10 Order Book Imbalance (`E16`)| Top-10 bids and asks | `float` OBI in `[-1.0, 1.0]` | `numpy` | Returns 0.0 if book empty (triggers `V-H06`) | Mathematical OBI ratio fixture | Replay parity check |
| **`features/regime.py`** | Lo-MacKinlay Variance Ratio composite (`E25`)| 15m & 1h `close` arrays | `RegimeState` (VR, Vol, Stress) | `numpy` | Returns `NEUTRAL` if bars insufficient | Synthetic mean-reverting vs trending | Replay parity check |
| **`edges/registry.py`** | Load & parse `EDGE_REGISTRY.yaml` | YAML file path | `Dict[str, EdgeMetadata]` | `pyyaml` | Fails fast at startup if YAML malformed | Schema parsing & validation tests | CI registry lint test |
| **`edges/base.py`** | Abstract edge evaluator interface | Feature context | `EdgeResult` (`status`, `confidence`) | None | Pure interface; never raises | Mock evaluator tests | Interface compliance test |
| **`edges/e01_...`** | Individual edge implementations (`E01`..`X04`)| Feature context | `EdgeResult` or `ABSTAIN` | `features/*` | Catch internal errors; return `ABSTAIN` | Pos fixture, neg fixture, abstain test | Ablation harness isolation test |
| **`strategies/base.py`**| Abstract strategy interface | Edge evaluations, feature context| `Optional[Candidate]` | `dataclasses` | Pure interface | Mock strategy tests | Interface compliance test |
| **`strategies/s1_sweep_reclaim.py`**| Emit S1 candidates (spine) | Pools, sweeps, ATR, confirmations | `Candidate` dataclass | `edges/*`, `features/*` | Returns `None` if any setup rule fails | S1 long & short synthetic fixtures | Historical replay test (0.5–6 signals/day) |
| **`strategies/s2_oi_exhaustion.py`**| Emit S2 shadow candidates | OI delta, CVD, Z_liq, 4h lows | `Candidate` (marked SHADOW) | `edges/*`, `features/*` | Returns `None` if not qualified | S2 long flush fixture | S1 collision suppression test |
| **`strategies/s3_basis.py`**| Emit S3 experimental candidates | Basis z-score, clock sync | `Candidate` (marked EXPERIMENTAL) | `edges/*`, `features/*` | Abstains if clock offset > 150ms | S3 basis dislocation fixture | Clock desync abstention test |
| **`vetoes/pipeline.py`** | Master veto execution runner | `Candidate`, context | `VetoResult` (passed, blocking_id)| `vetoes/*` | Uncaught exception -> FAIL-CLOSED BLOCK | Pipeline execution ordering tests | Chaos injection test |
| **`vetoes/hard.py`** | Execute V-H01 through V-H34 | `Candidate`, system state | `VetoResult` | `data/*`, `clock.py` | Any violation immediately halts pipeline | 34 individual unit tests (one per veto)| "Score 100 with Veto" must block |
| **`vetoes/soft.py`** | Execute V-S01 through V-S15 | `Candidate`, system state | `SoftVetoModifications` | `features/*` | Modifies score threshold or confidence | 15 individual unit tests | Escalation to hard veto test |
| **`vetoes/governor.py`**| Concurrency, loss caps, cooldowns | Account state, journal | `VetoResult` (`V-H24..V-H29`)| `journal/*` | Exceeded limits immediately block | Max concurrent & loss cap tests | Simulation of consecutive losses |
| **`scoring/groups.py`** | Correlation-aware composite scoring | `Candidate`, confirming edges | `ScoreBreakdown` (0–100 integer) | `edges/*` | C1+C2 capped at 24; enforces cluster caps | Monotonic score increment tests | Calibration set distribution test |
| **`scoring/calibrate.py`**| Isotonic regression & probability mapper | Raw score, calibration JSON | `float` probability or `"NOT CALIBRATED"`| `sklearn` (offline) | Missing or >90d artefact -> `"NOT CALIBRATED"`| Calibration mapping fixture | Expiry date boundary test |
| **`publish/schema.py`** | Canonical immutable `Signal` dataclass | All signal parameters | Frozen `Signal` instance | `dataclasses` | Type validation fails if any field missing | Schema field validation test | Serialization round-trip test |
| **`publish/telegram.py`** | Format Bengali/English alert & transmit | Frozen `Signal` | Published message ID | `aiohttp`, `schema.py` | 3 retries; logs failure to journal | Markdown formatter snapshot test | Staging Telegram bot smoke test |
| **`journal/signals.py`** | Record emitted signals | Frozen `Signal` | SQLite row ID | `data/store.py` | Write failure logs CRITICAL alarm | Journal write/read tests | Database recovery test |
| **`journal/fills.py`** | Record manual `/fill` receipts | User fill command payload | SQLite fill record | `data/store.py` | Invalid format returns user error | Fill parsing & reconciliation tests | Unmatched fill alert test |
| **`journal/outcomes.py`**| Track MFE, MAE, and trade resolution | Klines, active signals | Updated outcome record | `data/store.py` | Intrabar ambiguity resolved as SL first | Outcome resolution fixture tests | Replay outcome reconciliation |
| **`observability/health.py`**| System health & resource monitoring | `psutil` metrics | `HealthStatus` dataclass | `psutil` | RSS > 300MB triggers `V-H08` | Memory threshold assertion test | Synthetic resource exhaustion test |
| **`observability/watchdog.py`**| Monitor event loop delays & heartbeat | Loop timestamps | Degradation ladder level | `clock.py` | 3 missed beats triggers `V-H10` & `V-H09` | Simulated event loop freeze test | Emergency kill switch drill |

---

## 3. Data Ownership & Concurrency Model

1. **Single Writer Database Rule:**
   Only `src/neo_wilder/data/store.py` opens a write connection to the SQLite database. All other modules submit write requests over an internal `asyncio.Queue`.
2. **Read-Only Context in Pure Layers:**
   `features/`, `edges/`, and `strategies/` receive read-only immutable slices or tuples of past data. They have zero direct access to database handles or network sockets.
3. **Immutable Signal Contract:**
   Once a `Signal` object is instantiated in `src/neo_wilder/publish/schema.py`, it is frozen (`@dataclass(frozen=True)`). No downstream component or retry loop can alter its fields, reference price, stop loss, or targets.
