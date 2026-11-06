# Aurex Strategy Research Reset

Status: `ACTIVE RESET / R4 PATH-QUALITY FAMILY STOPPED / U1 THEORY SCREEN FROZEN / NO ELIGIBLE STRATEGY`.

## Objective

Find out whether Aurex can identify a durable, cost-net crypto spot edge without
reusing opened holdouts, hiding unstable markets inside pooled totals, or treating
software completion as profitability. This reset now governs unrelated-mechanism
discovery after four honest rejections. It does not authorize paper or live trading.

## Evidence That Forces The Reset

| Candidate | Main result | Meaning |
| --- | --- | --- |
| `trend_pullback_v1` v1.3 | `-$695.52`, PF `0.8079`, 0/6 folds | Thin gross edge was overwhelmed by turnover and costs. |
| `volatility_breakout_v1` v1.1 | `-$533.87`, PF `0.6734`, 0/6 folds | The mechanism lost even before modeled costs. |
| `slow_breakout_spot_v1` v1.0 | `+$104.43` pooled, but both market validations failed | Lower turnover helped, but temporal and cross-market durability were not proven. |
| `path_quality_spot_v1` v1.0 | `-$73.83`, PF `0.7991`, 1/4 quarters, 0/35 LOMO | Untouched 2025 validation failed before and after costs; the family is stopped. |

Slow spot is especially instructive. Costs were only `$6.40` across 106 trades. The
failure was not execution drag. Returns depended on isolated trends, SOL became
negative OOS, and the preregistered walk-forward requirement failed on both markets.

## Research Boundary

BTCUSDT, ETHUSDT, and SOLUSDT through `2026-06-30` are development-contaminated for
the tested trend/breakout family. Their outcomes may be used for failure analysis and
development, never as a new promotion decision. A renamed candidate, nearby channel,
different stop multiplier, or different fold calculation does not create new evidence.

All R3/R3.1/R4 path-quality outcomes through 2025 are contaminated for that lineage.
The R4 failure analysis may describe why the mechanism failed, but its exit, duration,
month, symbol, omission, and cohort buckets may never become candidate rules. The
January-June 2026 holdout is sealed, and forward evidence from `2026-07-01` is locked.

The existing `range_mean_reversion_v1` is exploratory code, not the automatic next
candidate. It has no Aurex reference engine, freeze receipt, immutable real-market
replay, or eligibility verdict. `jam_reversal_v1` remains quarantined after repeated
outcome-conditioned tuning. Both are disabled by default.

## Next Hypothesis Standard

The U1 discovery charter is frozen under hash
`642f67fdc55fc041c010e1e7c90732e102a2214bc76c46df15d864c2d269fbcf`.
It permits up to three theory/data-feasibility proposals but at most one
return-tested mechanism, one selectable parameter set, and one candidate. The theory
screen may inspect no Aurex return.

The no-return screen is frozen under hash
`0d32405ea4eea989ee93b74b2f393d5e988cf9eadb63cbde78cc652996eab745`.
It considered:

1. volatility-managed broad spot market beta;
2. cross-sectional signed-jump risk premium;
3. delta-neutral spot-perpetual funding carry.

Only volatility-managed broad spot beta passed the frozen current-data and execution
screen. Its premise combines broad cryptocurrency market-factor evidence with the
general volatility-management hypothesis:

- https://www.nber.org/papers/w25882
- https://www.nber.org/papers/w22208

Signed-jump risk is deferred because the defining statistic requires high-frequency
prices that four-hour candles cannot reproduce:

- https://doi.org/10.1016/j.irfa.2023.102712
- https://doi.org/10.1162/REST_a_00503

Funding carry is deferred because Aurex lacks point-in-time funding, basis,
collateral, and liquidation evidence plus qualified derivatives execution:

- https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf
- https://arxiv.org/abs/2212.06888

Selection authorizes protocol design only. It is not evidence that volatility
management works in crypto, not an Aurex candidate, and not a profitability claim.

## Required Infrastructure Before Candidate Selection

1. A portfolio replay must use one shared cash/equity ledger. Independent `$1,000`
   symbol replays may support diagnostics but cannot represent simultaneous capital.
2. Concurrent signals need deterministic ordering, cash reservation, quantity
   rounding, exposure caps, and rejected-order evidence.
3. Portfolio results must include overlapping positions, correlation, symbol and trade
   concentration, turnover, fees, slippage, drawdown, and leave-one-market-out results.
4. The universe must be selected by a frozen rule using only availability, listing
   age, data integrity, and development-period liquidity. Current winners must not be
   hand-picked. Delisted and failed assets must be represented when source data allows.
5. Every imported market requires archive checksums, candle continuity, provenance,
   and immutable evidence hashes before strategy outcomes are calculated.
6. A contamination ledger must identify every symbol, timeframe, date range, variant,
   and metric previously inspected.
7. Fold duration and minimum trades must agree with the expected trade rate. A future
   protocol must reject an internally impossible sample design before registration.
8. Variant count, parameter count, and selection process must be recorded. If several
   alternatives are compared, the final protocol must include an explicit
   multiple-testing penalty or nested selection procedure.

## Stage Contract

### R0 - Preserve Failure Evidence

Complete when all three rejected candidate records, audits, decisions, and
development-only postmortems are hash-verifiable. This stage is complete.

### R1 - Portfolio Evidence Engine

Implement shared-capital multi-symbol replay and audit semantics. Synthetic fixtures
must prove deterministic collisions, concurrent exposure, insufficient cash,
rounding, costs, liquidation, and replay hash stability. No market outcome is needed.

Status: `COMPLETE / PURE ENGINE FOUNDATION`. Engine
`shared-capital-spot-portfolio-v1.0.0` uses one shared ledger, aligned marks,
proportional simultaneous allocation, priority-based capacity, deterministic collision
handling, full costs, mark-to-market drawdown, rejection evidence, hash-stable replay,
and tamper-detecting audit. Persistence and a candidate adapter belong to later stages.

### R2 - Universe And Contamination Freeze

Commit a machine-readable universe rule and contamination ledger before importing or
inspecting candidate returns. Preserve excluded markets and reasons. Separate
development, validation, final holdout, and future-forward periods.

Status: `COMPLETE`. The contamination artifact audits under hash
`9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`
and is bound into the universe rule. The Binance Vision historical census preserves
all `680` USDT archive markets and every exclusion. The final manifest is `READY` with
`35` decision candidates, `3` development-only markets, and `642` exclusions under
hash `dacc57f649846f716b8134aa0abba5accc78b0f1607d653addb0df3d9e132a74`.
Development, sealed validation, sealed holdout, and locked-forward partitions are now
machine-readable. Selection inspected only open time and daily quote volume; no
strategy outcome was imported.

### R3 - Development-Only Mechanism Study

Use only declared development data. Compare the smallest defensible set of mechanisms,
record every variant, and reject complexity that has no economic justification. This
stage may end with no candidate.

Status: `COMPLETE / NO CANDIDATE`. The exact development bundle is frozen under hash
`fba63b8e237220c760daf902f2c999e9b01121357a4cc583c9fa5cb50b83d341` with
166,668 continuous 4h candles across 35 decision and 3 diagnostic-only markets. The
cross-sectional-momentum study protocol is `FROZEN_PRE_OUTCOME` under hash
`8af37e15ca08bcbbdd82c457927d5a4b5039e70f173ff735c16c91a3bed4f893`.
It fixes one 84-day/14-day primary and two non-selectable faster/slower falsification
variants, six quarterly folds, costs, shared capital, concentration controls, and
all-or-nothing gates. A separate exact execution specification is frozen under hash
`7125758ab4b4672576db8de49d8f67f5988f02dc5c39e2d94d36ae2e7edb6eb6`.
The engine/run package was frozen under hash
`2ca29f9328306c91f8281051731592da5e3d8b00db47573f5f4b08b9d9bb2756` before
outcomes. All 62 planned replays completed and reproduce under deterministic audit.
The primary earned `+$330.23`, PF `1.3907`, and 14.78% maximum drawdown, remained
positive at double costs, passed all 35 leave-one-market-out runs, and passed both
concentration limits. It was positive in only 3/6 independent quarters against a
required 4/6, so the all-gates verdict is `NO_CANDIDATE` under ledger hash
`dd751538457a4876ee38fbe7b139cace3b30a81f8846a0ec3e93114fa82d282c`.

The slow falsification horizon looked stronger in aggregate and had 4/6 positive
folds, but it cannot replace the primary after results. The fast horizon had only 2/6.
A post-outcome monthly-label correction is isolated under hash
`7f538ce899ca6513c109510479980602d6820397fb22e19d80334f46b036192a` and changes no
gate or verdict.

### R3.1 - Bounded Path-Quality Mechanism Study

Status: `COMPLETE / 9 OF 9 DEVELOPMENT GATES PASSED / NOT ELIGIBLE`.

R3.1 changed only endpoint-return ranking to positive 84-day log-price OLS slope times
R-squared. Protocol hash
`dba4e1282533d5a93825eb1b6bd8b8e854f4146218bd70d5633f9a489b7030b5`,
execution hash
`76a0403f61f7d684761a05765c9d48d3310e56c8433779abb164d14e209773f1`,
and run-package hash
`13c1e6cc657b055f3cf957fd6e841e9bdbe8ed59ce6eee89c6f7d9b39c78d722`
were frozen before outcomes.

The one-shot 44-replay study produced ledger hash
`452a79da7bc12704a2685cf70f24b8d2d9c895b7123f29d646c89809ea25dd94`.
Base-cost net P/L was `+$488.79`, PF `1.5936`, maximum drawdown 10.82%, and 230
trades. Double-cost net P/L remained `+$423.78`. Exactly 4/6 quarterly folds and all
35/35 leave-one-market-out runs were positive; concentration limits passed. Both the
stored-artifact audit and a full deterministic second 44-replay audit pass.

The mechanical verdict is `PERMIT_R4_PREREGISTRATION`. R3.1 fixes
`creates_eligible_strategy=false` and `opens_validation_partition=false`. The
2023-2024 development partition is now fully contaminated for this mechanism and may
not be used for more tuning.

### R4 - Candidate Preregistration

Freeze source bytes, version, full parameters, portfolio construction, universe,
datasets, costs, order semantics, temporal windows, fold plan, thresholds, and one
decision rule in a committed and reload-verified protocol. Dry-run all binding checks
without exposing holdout outcomes.

Status: `COMPLETE / RETIRED`. The unchanged path-quality candidate, checksum-verified
2025 validation data, execution specification, engine, source/runtime package, and
42-run matrix were frozen before outcomes. The one-shot result is
`RETIRE_R4_CANDIDATE` under ledger hash
`797ea50d142bbd61f22e87ff9ddf72f30b12c70940d596d027e70660ee26e626`.
Base net P/L was `-$73.83`, PF `0.7991`, raw-price PF `0.8530`, double-cost net P/L
`-$94.18`, 1/4 quarters positive, and 0/35 leave-one-market-out runs positive.

### R4.1 - Frozen Failure Attribution

Status: `COMPLETE / PATH-QUALITY FAMILY STOPPED`.

The pre-analysis protocol, source package, and deterministic result froze under hashes
`3b0578e826a1c93929f7a2515a44169ad7a9b7c7887c23774078fc91dc3c714b`,
`e15fdf4ee9618e1b8d5f1195aebcf3065f0c0f66fa36e788129091fa6b84e2b4`, and
`b46b2181bf7b890f27a1ac43f6b6307bf095230cf4694c7231c5b8166bbaad4b`.
Raw price P/L was already `-$52.02`; missing markets, concentration, and drawdown did
not cause the loss. The final decision is
`STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY`.

### U1 - Unrelated Mechanism Discovery

Status: `COMPLETE / SELECTED MECHANISM RETIRED`.

The charter fixes three theory proposals, one return-tested mechanism, one parameter
set, and one candidate at most. It uses 2023-2024 for development, treats 2025 only as
internal validation, requires the sealed 2026 H1 holdout for eligibility, and locks
forward evidence. Every failed gate stops the selected mechanism; no rescue variant
may follow.

The theory screen selected `P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA` because it alone
fit current point-in-time data and long-only spot execution without leverage. Its
protocol, execution contract, deterministic engine, transformed data, and 47-run
package were frozen before outcomes under package hash
`fd6a1bd0a4faf4b8a65a650e41d69050f7d870d33dfcc29d9ce89d170bcd78b2`.

### U2 - One-Shot Development Falsification

Status: `COMPLETE / STOP`.

All 47 planned runs completed and passed stored-artifact plus full deterministic
replay audits under ledger hash
`06045816415f3fb270ed11bc8e9e3bbeab9382dfc886990e2e4297a5d9217669`.
The primary earned `+$2,168.47`, PF `1.9311`, remained positive at double costs, and
passed 35/35 leave-one-market-out runs. It failed maximum drawdown at 44.58% against
20% and temporal robustness at 4/8 positive folds against 6/8. The mechanical verdict
is `STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA`. Aggregate profit does not override the
failed risk and stability gates.

### U3 - Internal Validation And Final Holdout

Status: `NOT AUTHORIZED FOR U1`.

U1 may not open 2025 because U2 failed. January-June 2026 remains sealed and forward
evidence remains locked. A future mechanism must begin under a separate discovery
charter, close its data and execution gaps before return testing, and preserve the
same validation and final-holdout order.

### V2 - Lower-Directional-Risk Foundation And Discovery

Status: `THEORY SELECTED FOR FULL-DATA/PROTOCOL DESIGN / NO CANDIDATE`.

The V2 source census found 31/35 symbols complete across spot, USD-M contract,
funding, mark, index, and premium archives for 2023-2024. A 54-archive resource and
schema pilot passed. Those results establish source feasibility only.

A synthetic paired-leg protocol froze under hash
`b7709efb8555611b9041afc0cb030259c2355c1c82a76c8e22cd6b26a6767c4b`.
Its result passed 14/14 funding, fee, margin, liquidation/ADL, partial-fill, rollback,
kill-switch, idempotency, flattening, and reconciliation scenarios under hash
`8cf54efc7989b1370db4be80267b47a763637285a1e66d503093f9fe15a49fe8`.
This is internal arithmetic evidence, not exchange or return evidence.

The no-return discovery charter and screen froze under hashes
`af4dd3e28e20f9a5e99c47e98d567587ef11697c38dd976074ddcb80255db07f`
and `ec03d31db661a36b1def820711b20134d416ec2d390a49cdbafaf19f27758dea`.
The screen selected `P01_POSITIVE_FUNDING_SPOT_PERP_CARRY` for full-data and protocol
design only. Premium convergence is a nonselectable related diagnostic. Negative
funding reverse carry is rejected under this charter because historical spot-borrow
state and reverse execution are not qualified.

V2 has inspected zero Aurex numeric market fields, defined zero parameter sets,
calculated zero returns, and created no candidate. Development, validation, holdout,
forward paper, sandbox, live trading, and capital remain closed.

## Parallel Operational Track

Research does not block infrastructure proof, but infrastructure cannot manufacture
edge. With explicit operator authority Aurex may independently:

1. run the bounded rejected trend strategy in TradingView for engine calibration;
2. compare completed trades at trade level and preserve all mismatches;
3. send one genuine authenticated TradingView alert through the external webhook;
4. prove delivery and pipeline behavior while risk correctly rejects the ineligible
   strategy and creates no paper order.

## Advancement Rule

No candidate enters forward paper because it is the best of a weak group, profitable
when pooled, visually attractive, or operationally convenient. It must pass its frozen
decision on untouched evidence. Forward paper, exchange sandbox, approved micro-live,
and the first settled `$100` net profit remain sequential gates. Real profit is still
`$0`, and live trading remains disabled.

## Exact Next Implementation

Preserve the complete U1 lineage and its stop verdict. Do not tune the target
volatility, lookback, rebalance schedule, basket, exposure transform, or risk gates,
and do not open 2025 for U1.

Preserve V2 capability-audit hash
`3726b944529990be7160604942f4e580cd8d198efe79f8e074dc72b760638e42`.
It records one ready capability and eleven blocked capabilities and authorizes
data-contract design only.

Preserve source-census contract hash
`7502a7eb6a54089d90bfc40889390f8c6ac18bbe55d18ef4122421e7fa18e0dc`.
It fixes 5,040 checksum checks across 35 symbols, 24 months, and six one-minute
spot/perpetual, funding, mark, index, and premium families.

Preserve census-result hash
`ce5d60e3338903bcb8a3783bd4b41fa63bec518c3041b213c9529bd6458d652e`.
The completed census found 4,790 present checksums, 250 missing archives, and 31
complete symbols. CFXUSDT, LUNCUSDT, SHIBUSDT, and STXUSDT remain excluded without
substitution. The result permits acquisition-protocol design only.

Preserve pilot-acquisition protocol hash
`aa88b2ff6add0637b889da27b784cd1a26b1addc4590832c9c51e973e2aaebc5`.
Preserve completed pilot-result hash
`95e9aaaf1b05b01372ddcdc3f19fff6612f6a7f5ae4e1ca4b99b0eb6e7947874`.
All 54 checksum-pinned targets passed resource, checksum-revision,
transactional-download, ZIP-safety, schema, value, ordering, and timestamp gates.
The result permits a separate full-acquisition protocol but does not authorize or
begin the remaining acquisition automatically.

Preserve the synthetic foundation protocol/result hashes
`b7709efb8555611b9041afc0cb030259c2355c1c82a76c8e22cd6b26a6767c4b`
and `8cf54efc7989b1370db4be80267b47a763637285a1e66d503093f9fe15a49fe8`.
Preserve the V2 charter/screen hashes
`af4dd3e28e20f9a5e99c47e98d567587ef11697c38dd976074ddcb80255db07f`
and `ec03d31db661a36b1def820711b20134d416ec2d390a49cdbafaf19f27758dea`.

Next freeze one integrated P01 full-acquisition and development-protocol design. It
must bind resource ceilings, checksum and normalization semantics, historical
contract/fee/funding/margin/collateral metadata, partition boundaries, paired
execution and costs, run matrix, multiplicity, decision gates, automatic stop, and
immutable audit before the remaining archives are downloaded or any return is
calculated.

Do not promote either deferred U1 proposal, treat P01 as a candidate, import the 2026
holdout, connect a candidate adapter, start paper, or enable live trading.
