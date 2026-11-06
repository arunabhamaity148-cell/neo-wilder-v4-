# BACKTEST_PROTOCOL.md

## 0. The rule that governs everything else
No number in the final report may be produced by any path other than a run of this protocol.
Anything else is written as `NOT PROVEN`.

## 1. Data
- Source: Binance USD-M public REST (`/fapi/v1/klines`, `/fapi/v1/premiumIndex`,
  `/fapi/v1/openInterest`, `/futures/data/openInterestHist`, `/fapi/v1/aggTrades`).
- Range: >= 24 months per symbol, >= 8 symbols, >= 3 regime periods (2023 chop, 2024 trend, 2025-26 stress).
- Integrity gate: duplicate `open_time`, gaps > 1 bar, non-monotonic timestamps, zero-volume bars,
  and any bar whose `close_time - open_time != 900000 ms` on 15m => symbol rejected from the study.
- Survivorship: the universe must be the **as-of-date** top-volume list, re-selected monthly from
  `24h quote volume` at that date, not today's list.

## 2. Cost model (all four must be modelled; skipping one invalidates the run)
| Component | Value used | Source |
|---|---|---|
| CoinDCX taker fee | 0.050% per side; **0.044% maker** alternative | coindcx.com/fees (search snippet; page itself blocked -> re-verify in app) |
| GST on fees | +18% => effective 0.118% round trip taker | Indian GST rule as stated on the same fee page |
| Slippage | 0.5 x spread_bps + 0.3 x ATR_bps/100, floor 1.0 bp | engineering estimate, must be re-fitted from live fills |
| Funding | actual historical 8h rate applied to holding time | `/fapi/v1/fundingRate` |
Legacy `vetoes.py` used a flat `ROUND_TRIP_FEE_PCT = 0.0010` with **no GST**; that understates friction by
about 18% on the fee component and must not be reused.

## 3. Execution simulation
- Signal is generated on bar close `t`; fill is assumed at the **next bar open** (never `close_t`).
- Entry is a limit at the entry-zone mid; if the next bar's range does not touch the zone, the trade is
  recorded as **MISSED** (manual execution reality) and counted, not deleted.
- Latency + manual reaction model: `20 s <= delay <= 120 s`, sampled uniformly, with price drift applied.
- Intrabar ambiguity: if SL and TP are both inside the same bar's range, resolve as **SL first** (conservative).
- Max holding = strategy expiry in bars; exit at that bar's close.

## 4. Validation
1. Walk-forward: train 12 months / test 3 months / roll 3 months. Purge 24 bars at each boundary.
2. Out-of-sample: final 6 months never touched until the last run.
3. Multiple testing: report the number of configurations tried `N`; apply a deflated-Sharpe style haircut
   or at minimum report `p` adjusted by Bonferroni over `N`.
4. Bootstrap: 10,000 resamples of trade sequence for expectancy CI; report the 5th percentile.
5. Regime partition: every metric reported per regime (E25) and per direction and per symbol.

## 5. Ablation (mandatory, one row per edge)
`full` vs `full minus E_xx`. An edge is only marked ACTIVE if removing it **and** the decision is
statistically distinguishable (`p < 0.05` on expectancy, or a >= 15% reduction in false positives
with <= 10% loss of trade count). Otherwise it goes to SHADOW.

## 6. Report table (every backtest must emit exactly this)
trades, win rate, avg win (R), avg loss (R), expectancy (R), net profit factor, net avg R, max DD (R and %),
max losing streak, Sharpe (with the caveat that per-trade Sharpe is not annualisable cleanly), Sortino,
Calmar, signals/day, cost contribution (R), missed-fill rate, regime breakdown, direction breakdown,
symbol breakdown, bootstrap 5th pct expectancy, OOS degradation %.

## 7. Anti-cheating checklist (run before believing any result)
- [ ] No feature reads index `> t`. Unit test that shuffles future bars and asserts identical output.
- [ ] No parameter chosen on the test window.
- [ ] Fees, GST, funding and slippage all switched ON.
- [ ] Missed fills counted.
- [ ] Losing months printed, not just the equity curve.
- [ ] Result reproducible from a single seed and a single config hash.
