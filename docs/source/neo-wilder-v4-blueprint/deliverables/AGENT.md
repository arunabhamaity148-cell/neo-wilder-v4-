# AGENT.md — NEO-WILDER V4 Build Rules for Coding Agents

## 0. Absolute contract
1. The system is **SIGNAL_ONLY, permanently**. No exchange order placement, no cancel, no position
   mutation, no `POST /exchange/v1/derivatives/futures/positions`, no API keys for CoinDCX.
2. No `AUTO`, `SEMI_AUTO`, `PAPER_EXECUTE` mode may exist. The only modes are `SIGNAL`, `SHADOW`, `BACKTEST`.
3. A **hard veto can never be overridden** by a score, a model probability, or a config flag.
4. Never add an indicator because it "sounds institutional". Every edge needs a registry entry with
   `evidence_status` in {PROVEN, PROMISING, SPECULATIVE, NOT_PROVEN, DATA_SOURCE_NOT_VERIFIED}.
5. If a number (win rate, expectancy, edge) cannot be produced by a reproducible run in this repo,
   the string `NOT PROVEN` must be written in the report, not a number.

## 1. Forbidden modules (must not be created)
- `execution/*` order engines, `adapters/exchange/execution_bridge.py` (order path),
  `maker_engine.py`, `exit_manager.py`, `indian_adapter.py` (authenticated private endpoints).
- Any KMS/HMAC signing helper for CoinDCX private REST.
- Any LLM/ML call that can emit a signal without passing the veto pipeline.

## 2. Required reading order before any code
`LEGACY_EDGE_VETO_INVENTORY.md` -> `EDGE_REGISTRY.yaml` -> `VETO_REGISTRY.yaml` ->
`STRATEGY_SPECIFICATIONS.md` -> `BLUEPRINT.md` -> `BACKTEST_PROTOCOL.md`.

## 3. Definition of Done for any edge module
- Pure function `evaluate(ctx) -> EdgeResult`, no I/O, no network, no global mutable state.
- Deterministic under replay: same input array => same output bit-for-bit.
- Unit tests: (a) fires on a hand-built positive fixture, (b) does not fire on the negative fixture,
  (c) returns `None`/`ABSTAIN` on missing data instead of a fabricated 0.
- Registered in `EDGE_REGISTRY.yaml` with `active|shadow|experimental|reject`.
- Has an ablation flag so it can be switched off in backtest without code change.

## 4. Definition of Done for any veto
- Unique `VETO_ID`, unique `reason_code` present in the signal payload and DB row.
- Fail-closed: exception or timeout => veto fires, signal blocked.
- A test that proves the veto blocks a signal that would otherwise score 100/100.

## 5. Style / runtime constraints (1 GB RAM, 2 vCPU)
- One live process. No SHM bridge, no second daemon, no cross-process IPC in v4.0.
- Bounded memory: every buffer has `maxlen`; total RSS budget 220 MB; hard abort at 300 MB.
- No pandas in the live path. numpy only. numba only if it is already compiled at install time.
- All network calls wrapped with timeout + retry + circuit breaker; no unbounded `await` without timeout.
- SQLite in WAL mode, single writer task, `synchronous=NORMAL`.

## 6. Commit hygiene
- Every change to a threshold must carry the calibration artefact path in the commit message.
- No threshold may be changed in `live` without a new walk-forward report attached.
