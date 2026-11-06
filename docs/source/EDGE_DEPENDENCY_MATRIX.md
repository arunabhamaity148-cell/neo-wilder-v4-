# EDGE_DEPENDENCY_MATRIX.md

## 1. Dependency graph (edges only depend downwards)
```
E11 ATR/vol  ──┬─> E01 setup ──┬─> E02 4-stage
               │               ├─> E05 BOS/CHoCH
               │               ├─> E06 zones
               │               └─> E12 dynamic stop
E04 pools ─────┘
E07 vol profile ──> targets
E23 funding ─────┬─> E12
                 └─> E24 mark/index
E15 CVD ─────────┬─> E21 OI exhaustion
                 └─> E17 absorption
E16 OBI ─────────> E17
E13 Z_liq ───────> E14 clusters
E25 variance ratio ──> X01 BTC conflict
E20 Hawkes ──────> (diagnostic only; no downstream edge)
E26 GEX ─────────> REJECTED, no downstream edge
```

## 2. Matrix (X = hard dependency, o = soft/optional)
| consumer \ provider | E04 | E07 | E11 | E13 | E15 | E16 | E20 | E23 | E25 |
|---|---|---|---|---|---|---|---|---|---|
| E01 sweep setup | X | o | X | o | o | o | o | | |
| E02 4-stage | | | X | | o | | | | |
| E05 structure | o | | o | | | | | | |
| E06 zones | | | X | | | | | | |
| E12 stop buffer | | | X | | | | | X | |
| E14 clusters | | | | X | | | | | |
| E17 absorption | | | | | X | X | o | | |
| E21 OI exhaustion | | | o | | X | | | o | |
| X01 BTC conflict | | | o | | | | | o | X |
| X04 late entry | | X | X | | | | | | |

## 3. Correlation clusters (must NOT be scored independently)
| Cluster | Members | Rationale | Cap |
|---|---|---|---|
| C1 forced-flow | E13, E14, E20, E17 | all measure liquidation / aggressive burst activity within the same seconds | 1 slot, max 12 pts |
| C2 order flow | E15, E16, E17 | CVD, OBI and absorption are three views of the same book pressure | 1 slot, max 12 pts |
| C3 structure | E01, E02, E05, E06 | all derived from the same swing/liquidity geometry | 1 slot, max 20 pts |
| C4 positioning | E21, E22, E23, E24 | all derived from derivatives positioning | 1 slot, max 12 pts |
| C5 location | E07, E08, E09, E10 | all are price-location descriptors | 1 slot, max 10 pts |
| C6 regime | E25, E27 | both are time-series state variables | not scored, only gates |

## 4. What this forbids
The legacy `compute_composite_quality_score_kernel` awarded `ideal_obi_score` (10) + `idea2_oi_cvd_score` (10)
+ `idea5_squeeze_score` (10) as separate slots. OBI, OI/CVD and squeeze are all inside C1/C2, so the legacy
implementation could reach 30 points for one underlying phenomenon. That is exactly the double-counting failure
mode the brief calls out; v4 collapses C1 and C2 to two slots totalling 24 points maximum.
