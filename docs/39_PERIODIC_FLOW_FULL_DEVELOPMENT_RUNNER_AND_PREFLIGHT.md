# Aurex Q1 Full-Development Runner And Preflight

Status: `IMPLEMENTED_AND_AUDITED_ACQUISITION_BLOCKED_BY_DISK_PREFLIGHT`

This checkpoint closes the execution-design gap without opening market outcomes.
It does not establish a strategy, signal, edge, backtest, paper-trading authority,
or profit.

## Runner Contract

The source-bound runner processes months chronologically from `2020-01` through
`2023-12`, with Spot `aggTrades` before USD-M raw `trades` in each month. It uses
one full identity-encoded `GET` at a time, no `HEAD`, redirects, ranges, concurrent
requests, or partial resume. Every attempt has an immutable request marker and a
terminal response marker.

An interrupted partial is counted, recorded, deleted, and never parsed. A completed
destination can be recovered only when its checksum exactly matches the published
hash after an unmatched request marker. Reuse-candidate failure has no network
fallback. The first target, paired-clock, integrity, budget, or resource failure
stops all later targets.

Only archive structure, IDs, timestamps, and buyer-maker booleans may be parsed.
Price, quantity, quote quantity, features, parameters, returns, validation,
holdout, candidates, and orders remain sealed.

## Proven Behavior

Focused tests prove:

- source-hash and parent-authority binding;
- full `GET` with identity encoding and no range header;
- retry only for the frozen transient HTTP status set;
- immediate stop on checksum integrity failure;
- interrupted-partial accounting and deletion;
- exact-hash completed archive recovery;
- rejection of responses without requests;
- ZIP path-traversal rejection;
- exact byte identity for the special 2021-12 duplicate member;
- parsing succeeds structurally even when price/quantity text is deliberately
  nonnumeric, proving those fields are not consumed.

## Canonical Preflight

All 37 reuse candidates passed fresh checksum and ZIP-policy validation. Their
combined compressed size is `27,856,663,229` bytes. This includes the exact
2021-12 duplicate-member exception.

The point-in-time storage observation was:

- Free bytes: `48,036,913,152`.
- Required before acquisition: `120,000,000,000`.
- Additional bytes required: `71,963,086,848`.
- Network requests: `0`.
- Payload bytes: `0`.
- Outcomes: `0`.
- Orders: `0`.

Decision: `BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK`.

## Canonical Evidence

- Execution contract evidence hash:
  `542c84962812de3950a543c221f31375cacb8c5de702a805ae74379b2ce1adf9`.
- Execution-contract audit hash:
  `018ef8a010f9b971c3ed638b5f2173e1520f65104ed3c1574dfb540efd6f16e3`.
- Frozen runner source hash:
  `0c07c93dc99f55ef19ba3b49cfb57017f9dae0b71d5de5617e8d558756473487`.
- Preflight result evidence hash:
  `623c22fec5a5895eda9ffac2940f1cd932582d1b7977300f55e0918d78980c5c`.
- Preflight audit hash:
  `eadf6ea3e7a7cf223f53de83ca0f44d453614579f7589b1e970af5ce15dca4ba`.

## Exact Resume Point

1. Make at least `120,000,000,000` bytes free on the acquisition volume.
2. Rerun:

   ```powershell
   .\.venv\Scripts\python.exe scripts\run_periodic_flow_full_development_acquisition.py --preflight
   ```

3. If and only if preflight passes, run:

   ```powershell
   .\.venv\Scripts\python.exe scripts\run_periodic_flow_full_development_acquisition.py --run
   ```

4. Keep the process attached. The runner checkpoints after every qualified archive
   and paired month. Do not delete markers, checkpoint files, or completed archives.
5. Do not begin feature design, outcome calculations, strategy construction, Pine,
   paper trading, Testnet strategy orders, production, or live trading at this
   checkpoint.

## Verification

- Repository-wide Ruff: PASS.
- Pytest collection: `1,171` tests.
- Focused acquisition protocol and runner chain: `17 passed`.
- Readiness integration: PASS.
- Complete Aurex suite: `1,171 passed` in `981.45s`.
- Warning: the existing Starlette/httpx deprecation warning only.
