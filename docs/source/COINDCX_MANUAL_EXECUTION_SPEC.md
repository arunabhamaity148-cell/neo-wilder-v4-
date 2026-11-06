# COINDCX_MANUAL_EXECUTION_SPEC.md

## 1. Verified public data (no keys, no private endpoints)
| Purpose | Endpoint | Verified |
|---|---|---|
| Live futures prices + funding fields (`fr`,`efr`,`mp`) | `GET https://public.coindcx.com/market_data/v3/current_prices/futures/rt` | YES |
| Candles (res 1/5/60/1D only — **no 15m**) | `GET https://public.coindcx.com/market_data/candlesticks?...&pcode=f` | YES |
| Orderbook depth 10/20/50 | `GET https://public.coindcx.com/market_data/v3/orderbook/{instrument}-futures/10` | YES |
| Trades | `GET https://api.coindcx.com/exchange/v1/derivatives/futures/data/trades?pair=...` | YES |
| Open interest | **no public endpoint documented** | NO |
| Liquidation data | **no public endpoint documented** | NO |
Source: https://docs.coindcx.com/ (public endpoints section).

Consequence: CoinDCX can only be used for **validation and metrics**, never for candle-based signal
generation on 15m (resolution not offered) and never for derivatives context (OI/liquidation absent).
Binance remains the research/data venue; CoinDCX is the execution venue. This is a permanent
asymmetry of the design, not a temporary limitation.

## 2. Symbol mapping
CoinDCX futures instruments use the `B-{BASE}_USDT` form (legacy `execution_bridge.to_coindcx_pair`
implements this). The mapping table must be fetched at startup from
`/exchange/v1/derivatives/futures/data/active_instruments` and cached; any Binance symbol with no
CoinDCX instrument is dropped from the universe (never silently substituted).

## 3. Mandatory signal payload (all fields required, immutable)
```
signal_id, created_at_utc, expires_at_utc
symbol_binance, symbol_coindcx, direction, strategy_id
active_edge_ids[], confirming_edge_ids[]
reference_price (Binance close), coindcx_price, coindcx_spread_bps, coindcx_top10_depth_usd
entry_zone_low, entry_zone_high
stop_loss, tp1, tp2
gross_rr, fee_pct, slippage_pct, funding_pct_est, net_rr
score_0_100, calibrated_probability (or "NOT CALIBRATED")
regime, btc_context, veto_status, soft_veto_list[]
max_entry_drift_pct = 0.35
invalidation_conditions[]
one_paragraph_thesis  (<= 300 chars, plain Bengali + English identifiers)
```

## 4. Publication gate (all must pass, in order)
1. No hard veto.
2. `net_rr >= 1.50`.
3. `coindcx_price` present, `abs(coindcx - reference)/reference <= 0.35%`.
4. `coindcx_spread_bps <= 12` (major) / `25` (alt).
5. `coindcx_top10_depth_usd >= 20 x intended clip`.
6. Late-entry: progress to TP1 `<= 0.35`.

If CoinDCX validation is unavailable the signal is **blocked** (`V-H31`), not published as "unvalidated".
The legacy design allowed an unvalidated signal through; that is rejected here.

## 5. What the human must do (and the bot cannot)
The bot cannot see the human's fill. Therefore every signal carries a **self-report obligation**:
after execution the operator sends `/fill <signal_id> <price> <size>`; without a fill record the trade is
scored as `MISSED` in the journal, and the journal is what backtests are re-fitted on. Statistics that
silently drop unfilled signals are forbidden.
