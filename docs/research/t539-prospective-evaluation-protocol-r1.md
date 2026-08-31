# T539 prospective evaluation protocol R1

> Deterministic preregistration only. No post-freeze outcome is consumed or evaluated.

## Frozen authority

- Freeze source: `docs/research/matrix-native-results/t539-callable-family-dedup-prospective-shadow-freeze-r1.json`
- Freeze SHA-256: `f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8`
- Rule fingerprint: `eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446`
- Freeze boundary: `115000186`
- Primary metric: `OFFICIAL_ANY_PRIZE_TARGET_RATE`
- Protocol JSON SHA-256: `694ee84e50b393b3ad3e3b40cf44ab4cbb269e5973c24b88accae44730ca43c8` (31643 bytes)

## Frozen experiment surface

- K values: `K1`, `K2`, `K3`, `K4`, `K5`, `K7`, `K10`, `K11`, `K12`, `K25`
- Windows: `W50`, `W300`, `W750`
- Experiments: `30`, measured independently
- Arm A: `ORIGINAL_ROLLING`
- Arm B: `CALLABLE_FAMILY_DEDUP_ROLLING`
- Arm C: `CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE`

| Experiment | K | Window | Arms | Comparisons |
|---|---:|---|---|---|
| `T539:K1:W50` | 1 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K1:W300` | 1 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K1:W750` | 1 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K2:W50` | 2 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K2:W300` | 2 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K2:W750` | 2 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K3:W50` | 3 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K3:W300` | 3 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K3:W750` | 3 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K4:W50` | 4 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K4:W300` | 4 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K4:W750` | 4 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K5:W50` | 5 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K5:W300` | 5 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K5:W750` | 5 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K7:W50` | 7 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K7:W300` | 7 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K7:W750` | 7 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K10:W50` | 10 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K10:W300` | 10 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K10:W750` | 10 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K11:W50` | 11 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K11:W300` | 11 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K11:W750` | 11 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K12:W50` | 12 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K12:W300` | 12 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K12:W750` | 12 | `W750` | A, B, C | B minus A; B minus C |
| `T539:K25:W50` | 25 | `W50` | A, B, C | B minus A; B minus C |
| `T539:K25:W300` | 25 | `W300` | A, B, C | B minus A; B minus C |
| `T539:K25:W750` | 25 | `W750` | A, B, C | B minus A; B minus C |

## Prospective inclusion

A target enters the cohort only when `target_identity > 115000186`, a complete PRETARGET snapshot for that exact target was sealed before outcome availability, its rule fingerprint matches, the outcome authority matches the same target, and the full observation is technically valid.

`MISSED_PRETARGET_SEAL` is never backfilled and is classified as neither positive nor negative. Historical reconstruction must remain separate and may never be relabeled prospective.

## Technical-only exclusions

- `MISSED_PRETARGET_SEAL`
- `PRETARGET_SNAPSHOT_INVALID`
- `RULE_FINGERPRINT_MISMATCH`
- `TARGET_IDENTITY_MISMATCH`
- `OUTCOME_AUTHORITY_UNAVAILABLE`
- `INCOMPLETE_FROZEN_EXPERIMENT_SURFACE`

Exclusions may not depend on whether any arm won or lost.

## Measurement and accumulation

Each K x window experiment retains chronological raw target-level A/B/C binary success indicators. Reports preserve the valid target count, each arm's exact success numerator over that common denominator, B-A and B-C exact paired rate deltas, chronological target identities, and technical exclusions separately.

There is no cross-K/window aggregation, composite or weighted score, rank, best-window selection, early-stopping winner, materiality threshold, p-value threshold, significance claim, or promotion threshold.

## Integrity

```text
FUTURE_OUTCOME_ACCESS = NO
PROSPECTIVE_OBSERVATIONS = 0
HISTORICAL_REPLAY = NOT RUN
STRATEGY_EXECUTION = NOT RUN
DB_ACCESS = NO
SIGNIFICANCE_RULE = NOT DEFINED
PROMOTION_RULE = NOT DEFINED
PREDICTIVE_ADVANTAGE = NOT ESTABLISHED
PROFITABILITY = NOT ESTABLISHED
```
