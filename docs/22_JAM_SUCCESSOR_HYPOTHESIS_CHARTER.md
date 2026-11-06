# Aurex Jam Successor Hypothesis Charter

Status: `DESIGN ONLY / FROZEN / NOT AUTHORIZED TO RUN`

This charter is the first post-rejection step for the Aurex Jam family. It uses the
stored v1.0.1 failure evidence, the append-only contamination ledger, the frozen
BTCUSDT Spot Testnet scope, and external mechanism research. It opens no market
data, inspects no new return, defines no threshold, and creates no strategy.

## Hard Constraints

- Venue boundary: Binance Spot Testnet
- Product: spot only
- Symbol: BTCUSDT only
- Direction: long-only successor research
- Maximum leverage: `1x`
- Simulated equity: `$100`
- Maximum risk per trade: `$0.50`
- Maximum daily loss: `$1.00`
- Maximum total loss: `$10.00`
- Paid data budget: `$0`
- Live and production authority: false

The exact future account and symbol commission must be obtained from Binance's
commission API. Until then, research may not assume a fee discount or a maker fill.

## Research Basis

- Binance public data:
  `https://github.com/binance/binance-public-data/blob/master/README.md`
- Binance Spot commission FAQ:
  `https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md`
- Bianchi, Dickerson, and Babiak, liquidity provision and crypto reversal:
  `https://doi.org/10.1016/j.jbankfin.2022.106547`
- BTCUSDT within-venue liquidity resiliency:
  `https://doi.org/10.3390/jrfm19050372`
- Bitcoin market-microstructure maturation:
  `https://doi.org/10.1016/j.bir.2026.100869`

These sources motivate or constrain a hypothesis. None is proof that Aurex has an
edge.

## Proposal Decision

### Selected For Future Capability Review

`J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM`

Hypothesis: a sharp BTCUSDT aggressive sell-flow shock can create temporary price
impact. A long opportunity may exist only after aggressive sell imbalance decays
and price reclaims a pre-shock reference. This is a liquidity-resiliency hypothesis,
not a claim that candle wicks reliably reverse.

It requires official Binance spot aggregate trades and one-minute klines for
reconciliation. It assumes taker execution and full conservative costs. It remains
unparameterized and untested.

### Rejected

- Candle-parameter rescue: rejected because the Jam v1.0.1 outcome window is
  consumed and threshold loosening would be outcome-conditioned tuning.
- Passive maker retest: rejected because zero-cost historical data does not identify
  queue position, missed fills, or adverse selection. Touch-fill assumptions would
  manufacture edge.

### Deferred

- Lower-activity cross-asset reversal: academically plausible, but incompatible with
  the frozen BTCUSDT-only operator scope.

## Pine Boundary

The selected mechanism is not exactly Pine-compatible. Binance aggregate-trade
aggressor identity is not an exact TradingView Pine input. If this path eventually
qualifies, Aurex's backend must be the signal authority. Pine may be an optional
visualization layer, never the execution dependency or source of truth.

A candle-only Pine proxy may not be substituted and called equivalent.

## Evidence Map

- February 2023 through December 2025: consumed by Jam v1.0.1.
- May through July 2026: contaminated by exploratory Jam v1.14 probes.
- January 2019 through December 2022 aggregate trades and one-minute klines:
  provisional, unopened, and unverified. No development/validation/holdout role has
  been assigned.
- August 1, 2026 onward: locked forward evidence.

## Next Gate

The only next authorization requested by this charter is:

`AUTHORIZE_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS`

That census may establish whether official archive files and checksums exist. It may
not download market payloads, calculate features, select thresholds, inspect returns,
create a strategy version, or submit an order.

If the metadata census fails, the proposal stops. If it passes, Aurex must freeze a
separate data-capability pilot before any payload acquisition.

Frozen charter:
`data/evidence/jam_successor_hypothesis_charter_v1.json`

Charter evidence hash:
`426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019`

## Post-Charter Checkpoint

The authorized metadata-only census completed on `2026-08-01`. All 96 frozen
BTCUSDT 2019-2022 aggregate-trade and one-minute-kline checksum targets were
present. Result hash:

`e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e`

No archive payload was requested, so the historical market values remain unopened.
The next gate is now:

`AUTHORIZE_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT`
