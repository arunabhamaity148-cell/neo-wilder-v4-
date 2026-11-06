# FINAL_FOLDER_STRUCTURE.md

```
neo-wilder-v4/
├── AGENT.md
├── BLUEPRINT.md
├── pyproject.toml
├── config/
│   ├── base.yaml                 # one source of truth, no duplicate thresholds
│   ├── symbols.yaml              # Binance <-> CoinDCX mapping, tier, tick size
│   ├── thresholds.yaml           # generated ONLY by calibration, never hand-edited
│   └── calibration/
│       └── score_v4_YYYYMMDD.json   # artefact + hash + training window
├── src/neo_wilder/
│   ├── main.py                   # single asyncio entrypoint (no hot/cold split)
│   ├── clock.py                  # serverTime sync, monotonic guards
│   ├── data/
│   │   ├── ws_binance.py         # aggTrade, kline_5m, depth20, !forceOrder@arr
│   │   ├── rest_binance.py       # klines, premiumIndex, openInterest, openInterestHist
│   │   ├── rest_coindcx.py       # current_prices, orderbook, active_instruments (PUBLIC ONLY)
│   │   ├── integrity.py          # gap/dup/monotonic checks -> feeds V-H01..V-H04
│   │   └── store.py              # SQLite WAL, single writer task
│   ├── features/                 # pure, causal, no I/O
│   │   ├── swings.py  liquidity.py  structure.py  zones.py
│   │   ├── volume_profile.py  atr.py  funding.py  cvd.py  obi.py
│   │   └── regime.py             # variance ratio, single taxonomy
│   ├── edges/                    # one file per edge id, registry-driven
│   │   ├── registry.py           # loads EDGE_REGISTRY.yaml, resolves status
│   │   ├── e01_sweep_reclaim.py  e05_structure.py  e13_liq_burst.py ...
│   ├── strategies/
│   │   ├── s1_sweep_reclaim.py   s2_oi_exhaustion.py  s3_basis.py
│   ├── vetoes/
│   │   ├── hard.py               # V-H01..V-H34, ordered, fail-closed
│   │   ├── soft.py               # V-S01..V-S15
│   │   └── governor.py           # concurrency, cooldown, loss caps
│   ├── scoring/
│   │   ├── groups.py             # C1..C6 caps, no double counting
│   │   └── calibrate.py          # isotonic + reliability report producer
│   ├── publish/
│   │   ├── telegram.py           # formatter + publisher (ONE copy)
│   │   └── schema.py             # immutable Signal dataclass, validates all fields
│   ├── journal/
│   │   ├── signals.py  fills.py  outcomes.py
│   └── observability/
│       ├── health.py  watchdog.py  metrics.py  logging.py
├── research/                     # NEVER deployed to the VPS
│   ├── backtest/  walkforward/  ablation/  data_audit/
├── tests/
│   ├── unit/  integration/  property/  replay/
└── deploy/
    ├── neo-wilder.service
    ├── neo-wilder.env.example
    └── README_ops.md
```

## Module contract table
| Module | Responsibility | Input | Output | Dependency | Error handling | Unit test | Integration test |
|---|---|---|---|---|---|---|---|
| `data/ws_binance` | maintain 2 sockets, emit typed events | wss | event stream | clock | reconnect exp backoff 1-30 s, mark stale | mock ws | 6 h soak |
| `data/rest_binance` | poll OI/funding/premium | REST | snapshots | rate limiter | retry 3, then circuit open -> V-H11 | nock | live smoke |
| `data/rest_coindcx` | validation price/book | REST | quote | none | 404/empty => V-H31 | fixture | live smoke |
| `data/integrity` | bar continuity | events | `DataQuality` | store | fail-closed | fuzz | replay |
| `features/*` | pure transforms | arrays | feature dict | numpy | return `None` on short input | golden fixtures | replay determinism |
| `edges/*` | one edge each | features | `EdgeResult` or `ABSTAIN` | features | never raise into pipeline | pos/neg fixture | ablation harness |
| `strategies/*` | compose candidate | edges | `Candidate` | edges, atr | return `[]` on ambiguity | fixture | replay |
| `vetoes/hard` | block | candidate+ctx | `VetoResult` | all | exception => BLOCK | 34 tests, one per veto | chaos test |
| `scoring/groups` | 0-100 score | candidate | score+breakdown | edges | n/a | monotonic tests | calibration run |
| `publish/telegram` | format+send | signal | message id | schema | retry 3, journal fallback | snapshot test | staging bot |
| `journal/*` | persistence | signals/fills | sqlite rows | store | WAL, single writer | crud test | restart drill |
| `observability/watchdog` | degradation ladder | metrics | flags | none | n/a | simulated fault | kill -9 drill |

## VPS resource budget (measured target, 1 GB / 2 vCPU)
| Component | RSS target | Note |
|---|---|---|
| Python base + numpy | 55 MB | |
| 8 symbols x (5m klines 500 bars, trades ring 20k, depth top-20 ring 300) | 70 MB | bounded ringbuffers only |
| SQLite page cache | 20 MB | `PRAGMA cache_size=-20000` |
| Telegram/aiohttp | 15 MB | |
| Working headroom | 60 MB | |
| **Total budget** | **220 MB** | hard block at 300 MB, systemd `MemoryMax=400M` |
Legacy hot+cold dual daemon with SHM bridge does not fit this budget; v4 runs ONE process.
