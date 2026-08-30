# B649 Radical-gap 29-failure parity attribution R1

## Outcome

All **29** sealed Radical-gap failures classified as `DONOR_FAITHFUL_SOURCE_CLOSURE`: **29**. Current-port regressions: **0**. Source-authority unresolved rows: **0**.

Result JSON SHA-256: `53747069fa79006360a41fb1fde4f9c76f7e5cbab739f2f52928216542dc9faa`

The analysis reconstructed only each target's directly necessary sealed 300-draw window. It did not open a database or rerun K2.

## Required questions

1. Are all 29 failures donor-faithful? **True**.
2. Current-port regressions: **0**.
3. Is `fewer than six legal candidates` load-bearing for every donor-faithful row? **True**.
4. Positional component attribution: **ONE_POSITIONAL_COMPONENT:GAP_01_19**.
5. Identifiable frozen-input clustering: **True**.
6. Semantics-preserving adapter repair: **NO**.
7. Corrected successor/new lineage required to change the closures: **YES**.

## Exact 29-row classification

| Target | Date | Classification | Retained candidate counts | Load-bearing positional closure | Failed frozen engines | First divergence |
|---|---|---|---:|---|---|---|
| `111000108` | 2022-12-09 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `112000116` | 2023-12-29 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/11 | `GAP_01_19` | none | none |
| `113000024` | 2024-02-19 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000025` | 2024-02-20 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000027` | 2024-02-22 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `113000028` | 2024-02-23 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000046` | 2024-04-23 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000068` | 2024-07-09 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000088` | 2024-09-17 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `113000102` | 2024-11-05 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000103` | 2024-11-08 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000109` | 2024-11-29 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000110` | 2024-12-03 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `113000114` | 2024-12-17 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `114000006` | 2025-01-21 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `114000050` | 2025-05-06 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `114000054` | 2025-05-20 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `114000058` | 2025-06-03 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `114000059` | 2025-06-06 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `114000060` | 2025-06-10 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `114000065` | 2025-06-27 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/11 | `GAP_01_19` | none | none |
| `114000077` | 2025-08-08 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `114000078` | 2025-08-12 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `114000096` | 2025-10-14 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `114000108` | 2025-11-25 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `115000019` | 2026-02-18 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 4/12 | `GAP_01_19` | none | none |
| `115000039` | 2026-03-27 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `115000062` | 2026-06-16 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |
| `115000065` | 2026-06-26 | `DONOR_FAITHFUL_SOURCE_CLOSURE` | 5/12 | `GAP_01_19` | none | none |

For every row above, the retained source closes with `FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET` and the current adapter closes with `legacy_biglotto__backtest_radical_strategy__e54cc0812bc6: frozen donor emitted fewer than six legal candidates`. Exact candidates, component outputs/errors, history-window hashes, and sealed causal fingerprints are retained in the JSON.

## Frozen-input condition clusters

| Condition | Targets | Exact target IDs |
|---|---:|---|
| `deficient=GAP_01_19;failed_engines=NONE;pool_sizes=4,11` | 1 | `114000065` |
| `deficient=GAP_01_19;failed_engines=NONE;pool_sizes=4,12` | 7 | `113000027`, `113000088`, `114000050`, `114000054`, `114000059`, `114000096`, `115000019` |
| `deficient=GAP_01_19;failed_engines=NONE;pool_sizes=5,11` | 1 | `112000116` |
| `deficient=GAP_01_19;failed_engines=NONE;pool_sizes=5,12` | 20 | `111000108`, `113000024`, `113000025`, `113000028`, `113000046`, `113000068`, `113000102`, `113000103`, `113000109`, `113000110`, `113000114`, `114000006`, `114000058`, `114000060`, `114000077`, `114000078`, `114000108`, `115000039`, `115000062`, `115000065` |

## Disposition

Keep the current donor-faithful adapter unchanged. Any attempt to emit tickets for these closures requires a corrected successor/new lineage decision.

No strategy behavior, catalog entry, registry, replay, database, QuickML surface, K2 R2, or successor lineage was changed by this task.
