# SOURCE_INVENTORY.md — NEO-WILDER V4 Source Document Audit

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Line-by-line verification of all research documents, extracted blueprints, and repository artifacts under `docs/source/` and the root workspace.

---

## 1. Executive Summary of Source Inventory

| Category | Total Discovered | Read Completely | Partially Read | Missing | Unreadable |
|---|---|---|---|---|---|
| **Root Source Documents** (`docs/source/*.md`, `*.yaml`) | 13 | 13 | 0 | 0 | 0 |
| **Extracted Deliverables** (`docs/source/neo-wilder-v4-blueprint/deliverables/*`) | 13 | 13 | 0 | 0 | 0 |
| **Source Archives** (`docs/source/*.zip`) | 1 | 1 (archive table verified) | 0 | 0 | 0 |
| **Total Artifacts Inspected** | **27** | **27** | **0** | **0** | **0** |

> [!IMPORTANT]
> **Duplicate Integrity Check:** All 13 files in `docs/source/neo-wilder-v4-blueprint/deliverables/` are byte-identical and SHA-256 identical to the corresponding 13 files located directly under `docs/source/`. The zip archive `neo-wilder-v4-blueprint.zip` contains exactly these 13 deliverable files. There are no additional hidden documents or missing research fragments.

---

## 2. Source-Reading Checklist (Required Minimum Documents)

| # | Document Name | File Path | Reading Status | Verified Hash (SHA-256) |
|---|---|---|---|---|
| 1 | `AGENT.md` | `docs/source/AGENT.md` | **READ COMPLETELY** | `EABA7CD8C2281AA030E6421631BEB9B51CDB0E8357AE16970B9F8AD1ABDDE632` |
| 2 | `BLUEPRINT.md` | `docs/source/BLUEPRINT.md` | **READ COMPLETELY** | `85839A27AD97D0372928A7C29F2DEF809E1C8CD8308D201AD13FDCCA98D55881` |
| 3 | `FINAL_FOLDER_STRUCTURE.md` | `docs/source/FINAL_FOLDER_STRUCTURE.md` | **READ COMPLETELY** | `6292B087772EC955072121DBB2846A6066964BA3B79E2501E9794C6BD2CA0EBC` |
| 4 | `IMPLEMENTATION_ROADMAP.md` | `docs/source/IMPLEMENTATION_ROADMAP.md` | **READ COMPLETELY** | `80AD99CAB68FE2E8593AC352BBD004D79124CA93FE584D021CA0C7FF44CBB51B` |
| 5 | `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` | `docs/source/NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` | **READ COMPLETELY** | `8097AA539E46855EAACA53F52CF039B5D4708818544FAA79EC12A5CB3227383A` |
| 6 | `LEGACY_EDGE_VETO_INVENTORY.md` | `docs/source/LEGACY_EDGE_VETO_INVENTORY.md` | **READ COMPLETELY** | `70781B4B2ED3BE74085C84B995E222291937E75EC0ACD3686C85D8C763439D6F` |
| 7 | `EDGE_REGISTRY.yaml` | `docs/source/EDGE_REGISTRY.yaml` | **READ COMPLETELY** | `F5F06D6113433DC5B69A93251536A0B4E9BCEFC8DDA89B91B1214838396AF917` |
| 8 | `VETO_REGISTRY.yaml` | `docs/source/VETO_REGISTRY.yaml` | **READ COMPLETELY** | `D9C0EA78960E391C89D24E371EA984B523D42A6ECBA3075CA6925852D58D6244` |
| 9 | `EDGE_DEPENDENCY_MATRIX.md` | `docs/source/EDGE_DEPENDENCY_MATRIX.md` | **READ COMPLETELY** | `EBDEA222657FDB6749B178B3966CB8379A54FCF584ED7208DA661A1735CB3C8B` |
| 10 | `STRATEGY_SPECIFICATIONS.md` | `docs/source/STRATEGY_SPECIFICATIONS.md` | **READ COMPLETELY** | `32D65356CDAC3731F6F58E5414FA8B1AB1B1726CCB8002614E48C0E2855603B2` |
| 11 | `COINDCX_MANUAL_EXECUTION_SPEC.md` | `docs/source/COINDCX_MANUAL_EXECUTION_SPEC.md` | **READ COMPLETELY** | `A12BD0C7750CB893DCFA82AF8B85ABA9432492ADD756E7628E5A8A0ED3D78FFF` |
| 12 | `BACKTEST_PROTOCOL.md` | `docs/source/BACKTEST_PROTOCOL.md` | **READ COMPLETELY** | `BF732724E8B557E75827B000E03E13A116951D8099B54C4E63143D8F4C388838` |
| 13 | `RESEARCH_REFERENCES.md` | `docs/source/RESEARCH_REFERENCES.md` | **READ COMPLETELY** | `6C4B875077C06D13CD4A707DC75A8E8EDD2D7923A38D1530CBD570255915B9E4` |
| 14 | Blueprint Delivery Folder | `docs/source/neo-wilder-v4-blueprint/deliverables/*` | **READ COMPLETELY** | Verified identical to 1–13 above |

---

## 3. Detailed Master File Catalog

### 3.1 `AGENT.md`
- **Location:** `docs/source/AGENT.md` (and blueprint mirror)
- **Size / Lines:** 2,923 bytes / 45 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Absolute rules for coding agents. Mandates permanent `SIGNAL_ONLY` contract; forbids order execution modules, KMS/HMAC private signing keys, and `AUTO`/`SEMI_AUTO`/`PAPER_EXECUTE` modes. Specifies Definition of Done for edges (pure deterministic functions, no I/O, ablation flags) and vetoes (fail-closed, unique reason codes). Sets strict VPS resource limits (1 live process, 220 MB target RSS, 300 MB hard limit, no pandas in live path, SQLite WAL with single writer).

### 3.2 `BLUEPRINT.md`
- **Location:** `docs/source/BLUEPRINT.md` (and blueprint mirror)
- **Size / Lines:** 2,834 bytes / 44 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Architectural definition of the 7-plane pipeline: Data → Feature → Edge → Strategy → Veto → Score → Publish. Outlines architecture choice E (Hybrid: "One Spine, Three Plugs") where S1 (Sweep + Reclaim) is the spine and order flow/regime form plugs. Explicitly rejects independent bots (B), regime-first routing (D), and single strategy without confirmations (A). Defines data tiers (TIER_A WS, TIER_B REST, TIER_C stale/blocking). Lists explicit non-goals (no GEX routing, no LSTM, no Hawkes gating, no microprice).

### 3.3 `FINAL_FOLDER_STRUCTURE.md`
- **Location:** `docs/source/FINAL_FOLDER_STRUCTURE.md` (and blueprint mirror)
- **Size / Lines:** 5,198 bytes / 81 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Full repository directory tree under `src/neo_wilder/` (data, features, edges, strategies, vetoes, scoring, publish, journal, observability) plus `research/` (strictly non-deployable to VPS) and `deploy/`. Contains detailed module contract table (inputs, outputs, dependencies, error handling, tests). Itemizes the 220 MB VPS RAM budget across components.

### 3.4 `IMPLEMENTATION_ROADMAP.md`
- **Location:** `docs/source/IMPLEMENTATION_ROADMAP.md` (and blueprint mirror)
- **Size / Lines:** 3,554 bytes / 67 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** 13-phase roadmap from Phase 0 (Source Audit) to Phase 12 (Controlled Live). Establishes Phase 9 (Backtest + Ablation) as the supreme Go/No-Go gate (full system net expectancy must beat S1 alone with <40% OOS degradation). Line 8 records: "Verification: 201 files listed, 32 edge rows, 50 veto rows, 10 integrity defects." Defines hard failure conditions that immediately abort deployment.

### 3.5 `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md`
- **Location:** `docs/source/NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` (and blueprint mirror)
- **Size / Lines:** 28,018 bytes / 288 lines (in Bengali with technical identifiers)
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Master research report detailing the audit of legacy `neo-audit-final.zip` (201 files across 30 directories). Documents 10 confirmed integrity defects in legacy code. Reconciles legacy edges (28 verified + 4 new = 32 edges). Confirms 34 hard vetoes and 15 soft vetoes. Details S1, S2, S3 strategy designs. Outlines CoinDCX public API capabilities and confirms absence of 15m candle endpoint and open interest data. Explains Binance liquidation stream 1000 ms rate-limiting. Recommends rule-based scoring + isotonic calibration over machine learning.

### 3.6 `LEGACY_EDGE_VETO_INVENTORY.md`
- **Location:** `docs/source/LEGACY_EDGE_VETO_INVENTORY.md` (and blueprint mirror)
- **Size / Lines:** 8,902 bytes / 88 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Audit breakdown of legacy codebase. Confirms 56 members in `HardVetoReason` enum, but only 11 wired guards in `guards/pipeline.py` and 8 dead veto functions in `guards/vetoes.py`. Documents legacy edges E01–E28 with line references. Details 16 legacy guards (G01–G16) and 7 orphan vetoes (V1–V7). Fully lists the 10 legacy integrity defects including duplicate Telegram formatters, missing adapter publisher, conflicting score/RR thresholds, and private execution contract breaches.

### 3.7 `EDGE_REGISTRY.yaml`
- **Location:** `docs/source/EDGE_REGISTRY.yaml` (and blueprint mirror)
- **Size / Lines:** 5,864 bytes / 39 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Canonical machine-readable registry defining 32 edges: E01 to E28 plus X01 to X04. Specifies status (`ACTIVE`, `SHADOW`, `EXPERIMENTAL`, `REJECT`), evidence status, legacy source, archetype, and direction for each edge. Notes schema anomalies: `UNSUPPORTED_FOR_HORIZON` (E18, E19), `ESTABLISHED_METHOD_NOT_CALIBRATED` (E25), and `ACTIVE_SOFT_VETO` (X01).

### 3.8 `VETO_REGISTRY.yaml`
- **Location:** `docs/source/VETO_REGISTRY.yaml` (and blueprint mirror)
- **Size / Lines:** 5,239 bytes / 66 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Canonical machine-readable registry of vetoes. Defines pipeline processing order (11 stages). Enumerates exactly 34 hard vetoes (V-H01 to V-H34) and 15 soft vetoes (V-S01 to V-S15). Total items = 49 IDs. Specifies reason code, severity, condition, effect, and escalation rules. Declares absolute override policy: no hard veto can ever be overridden.

### 3.9 `EDGE_DEPENDENCY_MATRIX.md`
- **Location:** `docs/source/EDGE_DEPENDENCY_MATRIX.md` (and blueprint mirror)
- **Size / Lines:** 2,647 bytes / 50 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Downward dependency graph and matrix (providers vs consumers). Defines 6 correlation clusters: C1 forced-flow (cap 12), C2 order flow (cap 12), C3 structure (cap 20), C4 positioning (cap 12), C5 location (cap 10), and C6 regime (gating only). Reveals that E17 (Book density / absorption) is assigned to both C1 and C2. Details the double-counting prevention rationale that caps C1+C2 at 24 points.

### 3.10 `STRATEGY_SPECIFICATIONS.md`
- **Location:** `docs/source/STRATEGY_SPECIFICATIONS.md` (and blueprint mirror)
- **Size / Lines:** 3,363 bytes / 54 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Technical specifications for S1 (SWEEP-RECLAIM-v4, active spine), S2 (OI-EXHAUSTION-v4, shadow), and S3 (BASIS-DIVERGENCE-v4, experimental). Specifies 15m closed-bar setup TF, 1h/4h context TF, entry zones, stops, targets, expiry, and regime eligibility matrix. Documents rejected strategy families. Highlights missing short-side formulas in S1.

### 3.11 `COINDCX_MANUAL_EXECUTION_SPEC.md`
- **Location:** `docs/source/COINDCX_MANUAL_EXECUTION_SPEC.md` (and blueprint mirror)
- **Size / Lines:** 3,077 bytes / 56 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Public CoinDCX market data endpoints (`current_prices/futures/rt`, `candlesticks` with no 15m, `orderbook/10`, `trades`, `active_instruments`). Confirms absence of public OI and liquidation endpoints. Defines mandatory 20+ field immutable signal payload. Specifies 6-step publication gate (drift <=0.35%, spread <=12/25 bps, depth >=20x clip, progress <=0.35). Defines `/fill` self-report protocol for manual trader tracking.

### 3.12 `BACKTEST_PROTOCOL.md`
- **Location:** `docs/source/BACKTEST_PROTOCOL.md` (and blueprint mirror)
- **Size / Lines:** 3,904 bytes / 59 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Backtest standards: >=24 months data, >=8 symbols, survivorship-free as-of-date monthly universe. Cost model: 0.050% taker + 18% GST (0.118% round-trip) + dynamic slippage + historical 8h funding. Next-bar open fill simulation, 20–120s manual latency, missed-fill tracking, intrabar ambiguity SL-first rule. Purged walk-forward (12m train / 3m test / 3m roll), 6m untouched OOS, 10,000-sample bootstrap, mandatory 12-edge ablation table, and anti-cheating checklist.

### 3.13 `RESEARCH_REFERENCES.md`
- **Location:** `docs/source/RESEARCH_REFERENCES.md` (and blueprint mirror)
- **Size / Lines:** 4,698 bytes / 60 lines
- **Reading Status:** READ COMPLETELY
- **Key Contents:** Classification of evidence types. External API verifications for CoinDCX and Binance. Binance liquidation stream 1000 ms rate-limiting citation. CoinDCX fee/GST citation. Academic references for variance ratio (Lo-MacKinlay), microstructure / OFI (O'Hara, Cont-Kukanov-Stoikov), Hawkes processes (Bacry et al., Abergel-Jedidi), Deflated Sharpe Ratio (Bailey-López de Prado), and multiple testing hurdles (Harvey-Liu-Zhu). Explicit list of unverified items (win rates, historical liquidation data, GEX sign, Indian peak depth).

---

## 4. Source Audit Verdict

1. **Completeness:** 100% of all required files exist, are readable, and have been parsed in full line by line.
2. **Missing Documents:** 0 missing files.
3. **Unreadable Documents:** 0 unreadable files.
4. **Duplicate Integrity:** Extracted deliverables perfectly match top-level source files.
5. **Next Step:** Proceed to specification conflict analysis and reconciliation.
