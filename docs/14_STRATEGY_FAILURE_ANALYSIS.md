# Rejected Strategy Failure Analysis

Status: completed development analysis. No failed version may be rescued in place.

The analysis is deterministic, read-only, bound to the immutable replay records, and
restricted to development use. It separates pre-cost signal quality, fee/slippage
burden, turnover, direction, holding duration, calendar persistence, loss streaks, and
regime labels. It does not manufacture a new rule from favorable outcome buckets.

## trend_pullback_v1 v1.3

- Replay: `e1e5539a-49df-409d-8790-93639e173dc5`.
- Analysis hash:
  `a7aee7fcd90981b4a51a5d6582a99843614ffec3d3620be92553d4a41118d6c5`.
- Trades: `2,270`, approximately `665` per year.
- Pre-cost P/L: `+$175.7252`; pre-cost PF: `1.05755`.
- Fees plus slippage: `$871.2404`.
- Net P/L: `-$695.5152`.
- Median holding duration: `180` minutes.
- Profitable/losing months: `14 / 27`.
- Maximum consecutive losses: `18`.
- Long and short sides are each positive before modeled costs and negative after them.
- No calendar year is profitable after modeled costs.

Interpretation: the signal has only a very thin pre-cost edge while turnover imposes a
much larger cost burden. The failure is economic, not just a software bug. Longer
observed holding-duration buckets appear better, but duration is known only after exit;
using those buckets as entry filters would be outcome-conditioned leakage.

## volatility_breakout_v1 v1.1.0

- Replay: `9c2f12c7-9ee8-46c3-b8ea-c4aacbb5fae7`.
- Analysis hash:
  `cb139650893fe41b56c6e5b4630c29d27d1cfc0a6e93de8ed7ead3e680c29c1`.
- Trades: `1,125`, approximately `330` per year.
- Pre-cost P/L: `-$37.1046`; pre-cost PF: `0.97144`.
- Fees plus slippage: `$496.7683`.
- Net P/L: `-$533.8729`.
- Median holding duration: `120` minutes.
- Profitable/losing months: `6 / 35`.
- Maximum consecutive losses: `17`.
- Both directions lose before and after modeled costs.
- No calendar year is profitable after modeled costs.

Interpretation: the compression/volume breakout mechanism has no demonstrated gross
edge on the development window. Lower costs cannot rescue it.

## slow_breakout_spot_v1 v1.0.0

- ETH replay: `0bbe94e9-4596-41f0-9889-e21ab26085e7`; analysis hash
  `875df2b26714b0fde5b4441a267b4b6ac47d7a944e70a9fc4bc46adc36274b99`.
- SOL replay: `97700413-7a29-4dff-aa7c-aab086e8c1b1`; analysis hash
  `5e2fcdabe850dd0a9ff34061b55de745765115f87db2904ba423695631f9b558`.
- Each market recorded 53 trades, approximately 15.7 annualized. Modeled costs were
  only `$3.00` on ETH and `$3.40` on SOL, so turnover and fees did not cause failure.
- ETH was net positive in 2024 and 2025 but negative in 2023 and 2026. SOL was positive
  in 2023 and 2024 but negative in 2025 and 2026.
- ETH profitable/losing months: `14 / 20`; SOL: `17 / 18`.
- The mechanism is asymmetric by construction: channel exits captured occasional
  large trends, while catastrophe stops absorbed repeated small losses. That profile
  produced positive whole-period returns but did not persist across time.
- SOL's OOS loss and both markets' poor walk-forward pass rates are the decisive
  robustness failures. The combined result is strongly influenced by isolated 2023
  and 2024 trends and cannot establish a stable forward edge.

The preregistered quarterly test folds also exposed a future study-design problem.
With an observed rate near 16 trades per year, most quarterly folds cannot meet a
five-trade minimum. This does not reverse the rejection: SOL independently fails OOS,
and gates cannot be changed after results. Future low-frequency protocols must use
fold horizons and sample requirements that are mathematically compatible before any
outcome is opened.

## Research Implication

The only defensible next test is a genuinely different, lower-turnover mechanism, not
another nearby 15-minute parameter set. `slow_breakout_spot_v1` therefore changes the
economic exposure: native 4-hour bars, long-only spot, asymmetric 55/20 channels, no
profit target, smaller risk, and a 50% notional cap. BTCUSDT remains development-
contaminated. ETHUSDT and SOLUSDT are the untouched cross-market decision set.

This direction is consistent with the broad time-series momentum hypothesis described
in the primary research by Moskowitz, Ooi, and Pedersen and the long-horizon evidence
reviewed by AQR, but those papers do not validate this crypto implementation:

- https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing?aqrPDF=1

That frozen cross-market decision did reject v1.0.0. The lower-turnover mechanism
solved the prior cost problem but not temporal durability. No post-result channel,
stop, symbol, timeframe, or fold change is permitted under version `1.0.0`.

The next experiment must not be `slow_breakout_spot_v1` with nearby parameters. Before
another outcome is opened, Aurex needs a portfolio-level study design that models
simultaneous positions, shared capital, correlation, and a prespecified market
universe without survivorship-based cherry-picking. BTC, ETH, and SOL through June
2026 are now development-contaminated for this research family. A new candidate also
needs an untouched market/time decision set or must wait for forward data.
