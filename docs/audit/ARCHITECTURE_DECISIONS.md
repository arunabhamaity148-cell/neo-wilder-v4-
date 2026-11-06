# ARCHITECTURE_DECISIONS.md — NEO-WILDER V4 Architecture Decisions & Rationale

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Comprehensive record of approved, rejected, and unresolved architectural decisions, backed by source citations, empirical data, and operational constraints.

---

## 1. Approved Architectural Decisions

### ADR-01: Single Asyncio Process Modular Monolith
- **Decision:** NEO-WILDER V4 executes strictly as a **single asyncio process** within one operating system thread, using non-blocking asynchronous event loops and bounded queues.
- **Source Rationale:** `AGENT.md` §5, `BLUEPRINT.md` §1, `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §17 & §19.
- **Budget Justification:** The target host is a 1 GB RAM / 2 vCPU VPS. The measured memory allocation budget is:
  - Python runtime + numpy base: 55 MB
  - 8 symbols $\times$ (500 5m klines, 20k trade ring, 300 depth-20 ring): 70 MB
  - SQLite page cache (`PRAGMA cache_size = -20000`): 20 MB
  - aiohttp network buffers & Telegram client: 15 MB
  - Headroom & dynamic queue buffers: 60 MB
  - **Total Target RSS: 220 MB** (Hard abort limit: 300 MB, systemd `MemoryMax=400M`).

### ADR-02: SQLite WAL Persistence with Single-Writer Task
- **Decision:** All journal records, trade receipts, metrics, and bar data persist to a local SQLite database configured in Write-Ahead Logging (`WAL`) mode with `synchronous = NORMAL`. All writes are funneled through a single asynchronous writer task.
- **Source Rationale:** `AGENT.md` §5, `FINAL_FOLDER_STRUCTURE.md` line 41, `MODULE_CONTRACTS.md`.
- **Justification:** Eliminates SQLite database lock contention (`database is locked` errors), prevents multi-threaded race conditions, and requires minimal memory footprint (20 MB cache).

### ADR-03: Strategy Architecture E — Hybrid ("One Spine, Three Plugs")
- **Decision:** Candidate generation is powered by **one active spine** (S1: Sweep-Reclaim-v4). Order flow, liquidation metrics, and basis data act as **confirmation plugs**. Regime classification acts as a **gating plug**.
- **Source Rationale:** `BLUEPRINT.md` §3, `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §5.
- **Justification:** Sweep + Reclaim is the only legacy setup with complete, testable, and verified code (`sweep_reclaim_v1.py:60-240`). Liquidation flushes, OI drops, and basis shifts represent different facets of the same underlying liquidity event. Consolidating them into one spine prevents duplicate signal spam.

### ADR-04: Permanent SIGNAL_ONLY Operation & Public Execution Validation
- **Decision:** The system permanently operates in `SIGNAL_ONLY` mode. No private API keys, HMAC signatures, or order placement routines exist. CoinDCX integration uses **public REST endpoints only** to validate executable prices, spreads, depth, and drift.
- **Source Rationale:** `AGENT.md` §0 Rule 1, `COINDCX_MANUAL_EXECUTION_SPEC.md` §1.
- **Justification:** Absolute defense against runaway automated execution bugs, exchange credential theft, and unauthorized account liquidation.

### ADR-05: Strict Correlation-Aware Group-Capped Scoring
- **Decision:** Composite quality scoring is divided into 6 orthogonal clusters (C1: forced-flow, C2: order flow, C3: structure, C4: positioning, C5: location, C6: regime gate). C1 and C2 are capped at 12 points each, with a combined cap of 24 points. Total score is an integer in `[0, 100]`.
- **Source Rationale:** `EDGE_DEPENDENCY_MATRIX.md` §3, `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §10.
- **Justification:** Prevents collinear microstructure features (CVD, OBI, Squeeze) from manufacturing artificial 30+ point scores for a single orderbook event.

### ADR-06: Strict Separation of Research Directory
- **Decision:** The `research/` directory (backtesting engines, walk-forward notebooks, ablation scripts, and historical raw data) is strictly maintained in an offline research repository and **is never deployed to the live VPS**.
- **Source Rationale:** `FINAL_FOLDER_STRUCTURE.md` line 46, `AGENT.md` §5.
- **Justification:** Keeps VPS disk and memory footprints minimal, isolates production from heavy analytic dependencies (pandas, scipy, scikit-learn), and guarantees zero test-set leakage into live memory.

---

## 2. Rejected Architectural Alternatives

### REJ-01: Multi-Daemon Hot/Cold Split with 128-Byte SHM Bridge
- **Proposed in:** Legacy `docs/ARCHITECTURE.md`.
- **Rejection Reason:** Running a "hot" execution daemon and a "cold" feature daemon connected via shared memory (SHM) doubles baseline Python runtime memory to $\sim 400\text{ MB}+$. On a 1 GB VPS, this inevitably triggers OOM killer events. Furthermore, for a 15-minute closed-bar manual trading horizon, sub-millisecond IPC provides zero signal quality benefit while introducing IPC synchronization failure modes (`LEGACY_EDGE_VETO_INVENTORY.md` §3.9).

### REJ-02: Multi-Bot Independent Architecture (Architecture B)
- **Proposed in:** Early research concepts (independent bots for S1, S2, and S3).
- **Rejection Reason:** Running multiple independent bots across 8 symbols consumes redundant memory buffers and emits competing, highly correlated signals on the same market dislocation (e.g. S1 sweep alert and S2 OI flush alert simultaneously), violating the core requirement that signals must be high-conviction and non-redundant (`BLUEPRINT.md` §3).

### REJ-03: Regime-First Routing Architecture (Architecture D)
- **Proposed in:** Legacy `strategies/router.py`.
- **Rejection Reason:** The variance-ratio regime classifier (`E25`) is an uncalibrated statistical model on cryptocurrency futures. Routing strategy execution dynamically through an unproven classifier multiplies model uncertainty and causes catastrophic false negatives (`BLUEPRINT.md` §3).

### REJ-04: Microprice (E18) and Microbar Volume Clock (E19)
- **Proposed in:** Legacy `features/micro_price.py` and `features/microbar.py`.
- **Rejection Reason:** Microprice and volume-clock bars operate on microsecond-to-millisecond timescales for high-frequency market making. In a 15-minute swing strategy with manual human execution taking 20–120 seconds, microsecond price adjustments provide zero predictive alpha while consuming massive CPU cycles and state-machine RAM (`LEGACY_EDGE_VETO_INVENTORY.md` §1).

### REJ-05: GEX and Gamma Flip Routing (E26)
- **Proposed in:** Legacy `cold/deribit.py:93-161`.
- **Rejection Reason:** The legacy code assumed dealer gamma sign (calls $+1$, puts $-1$) without verifiable counterparty positioning data. If the sign assumption is incorrect, the calculated gamma flip is inverted, resulting in trading against the market. Classified as `DATA SOURCE NOT VERIFIED` (`LEGACY_EDGE_VETO_INVENTORY.md` §1).

### REJ-06: Deep Learning / Machine Learning in Initial Build
- **Proposed in:** Exploration of LSTM and gradient boosting classifiers.
- **Rejection Reason:** Over a 15-minute horizon, sweep events occur at modest frequencies (a few hundred trades per year across 8 symbols). Complex ML models (XGBoost, neural networks) severely overfit on regime-shifting financial series. Furthermore, ML probabilities cannot override hard vetoes. Rule-based orthogonal scoring combined with offline isotonic calibration is far more robust and verifiable (`NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §16).

---

## 3. Unresolved Decisions Requiring Immediate Signoff

Before implementation can proceed to Phase 1, the following 4 engineering decisions require explicit User / Chief Architect approval:

1. **Approval of Symmetric S1 Short-Side Formulas:**
   - Formal signoff on:
     - $d_{\text{short}} = \text{bar\_high} - \text{pool\_level}$
     - $\text{Entry\_Zone}_{\text{short}} = [close\_reclaim, \max(close\_reclaim, pool)]$
     - $\text{Stop}_{\text{short}} = \text{sweep\_extreme\_high} + (\text{buffer} \times \text{ATR}_{14})$
     - $\text{TP2} = \text{Reference\_Price} \pm 1.618 \times |\text{TP1} - \text{Reference\_Price}|$
2. **Approval of E17 Single Cluster Allocation:**
   - Formal signoff on removing `E17` from Cluster C1 and confining it strictly to Cluster C2 (order flow), leaving C1 exclusively for liquidation and burst events.
3. **Approval of Default Uncalibrated Score Threshold:**
   - Formal signoff on setting default `publish_threshold = 85.0` in `config/base.yaml` until empirical calibration on $\ge 300$ resolved trades is completed.
4. **CoinDCX Fee Schedule Field Audit:**
   - In-app verification of Global Futures taker fees ($0.050\%$) and GST ($+18\%$) by the manual operator before live capital deployment.
