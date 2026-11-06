# RESEARCH_REFERENCES.md

## A. Evidence classes used in this report
`[SUPPlied-doc]` findings from the user's PDFs · `[CODE]` directly read in the ZIP ·
`[EXT-VERIFY]` verified on an external page this session · `[EXT-SNIPPET]` search snippet only ·
`[ENG]` engineering recommendation · `[HYP]` hypothesis requiring testing.

## B. Verified this session
1. [EXT-VERIFY] CoinDCX public futures endpoints (active_instruments, instrument details, trades,
   orderbook depth 10/20/50, candlesticks res 1/5/60/1D, current_prices/rt with `fr`,`efr`,`mp` fields).
   No public open-interest or liquidation endpoint is documented.
   https://docs.coindcx.com/ — accessed 2026-11-05.
2. [EXT-VERIFY] Binance USD-M futures public REST paths: `/fapi/v1/klines`, `/fapi/v1/depth`,
   `/fapi/v1/aggTrades`, `/fapi/v1/ticker/price`, `/fapi/v1/premiumIndex`, `/fapi/v1/openInterest`,
   `/futures/data/openInterestHist`, `/futures/data/globalLongShortAccountRatio`,
   `/futures/data/takerlongshortRatio`, `/futures/data/topLongShortPositionRatio` (this last one shows
   `X-MBX-APIKEY required` on the doc page).
   https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api — 2026-11-05.
3. [EXT-VERIFY] Binance USDS-M regular-user fee example: **maker 0.02%, taker 0.05%**;
   10% discount when fees are paid in BNB.
   https://www.binance.com/en/support/faq/detail/360033544231 — 2026-11-05.
4. [EXT-SNIPPET] Binance liquidation stream publishes **only the latest liquidation per symbol per
   1000 ms** window ("All Liquidation Order Snapshot Streams ... for each symbol, only the latest one").
   https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log and
   https://docs.tardis.dev/historical-data-details/binance-futures — 2026-11-05.
   Consequence: any Z_liq / liquidation-heatmap edge is structurally under-sampled.
5. [EXT-SNIPPET] CoinDCX fee page: **Maker 0.044%, Taker 0.050%, +18% GST** on Global Futures.
   https://coindcx.com/fees (page itself blocked the crawler — snippet only; MUST be re-verified
   in the app before it is written into the cost model).
6. [EXT-SNIPPET] CoinGlass API: "no free API access for testing", Hobbyist from $29/month.
   https://dev.to/great-time-flies/coinglass-api-review-2026-is-it-worth-it-for-crypto-quant-traders-2bcf

## C. Academic anchors (method, not results)
7. Lo, A. & MacKinlay, C. (1988) "Stock market prices do not follow random walks" — variance-ratio test,
   basis of E25. [ESTABLISHED METHOD]
8. O'Hara, M. (2015) "High frequency market microstructure", *J. Financial Economics* — order-flow
   information content, cited for E15/E16 limits. https://doi.org/10.1016/j.jfineco.2015.01.003
9. Cont, Kukanov, Stoikov (2014) "The price impact of order book events" — OFI, the formal basis for the
   OBI family; note OFI requires event-level book updates, which Binance `depth20@100ms` only approximates.
10. Bacry, Mastromatteo, Muzy (2015) / Rambaldi, Bacry, Lillo (2017) "The role of volume in order book
    dynamics: a multivariate Hawkes process analysis", *Quantitative Finance* — Hawkes is a legitimate
    model class, but parameter stability across regimes is the known failure mode. [ESTABLISHED METHOD,
    NOT VALIDATED FOR THIS SYSTEM]
11. Abergel & Jedidi (2015) "Long-time behavior of a Hawkes-process-based limit order book", SIAM J. Fin.
    — stability conditions; supports the "don't gate trading on an uncalibrated Hawkes" decision.
12. Bailey & López de Prado (2014) "The deflated Sharpe ratio" — multiple-testing haircut used in
    `BACKTEST_PROTOCOL.md` §4.3. [ESTABLISHED]
13. Harvey, Liu, Zhu (2016) "…and the cross-section of expected returns" — t > 3 hurdle for new factors;
    applied here as the minimum evidence bar for promoting an edge to ACTIVE.
14. Bailey, Borwein, López de Prado, Zhu (2017) "Pseudo-mathematics and financial charlatanry" —
    basis for banning backtest-derived probability claims without OOS calibration.

## D. Explicitly UNVERIFIED / NOT PROVEN in this report
- Any win rate, expectancy, profit factor or signal frequency for NEO-WILDER: **NOT PROVEN** — no
  reproducible backtest exists in the supplied repo (the `validation/` modules exist but no stored
  result artefacts were provided, therefore nothing can be cited).
- Dealer gamma positioning sign (E26 GEX): **DATA SOURCE NOT VERIFIED**.
- Historical liquidation dataset for backtesting E13/E14: **DATA SOURCE NOT VERIFIED**.
- CoinDCX liquidity depth for the 8 chosen symbols at Indian peak hours: **NOT MEASURED**.
- The claim "14 hard vetoes": contradicted by code (11 wired guards, 8 veto functions, one dead engine).
