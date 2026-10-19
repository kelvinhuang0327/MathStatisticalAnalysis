# B649 OFFICIAL_ANY_PRIZE constructor reference designation R1

Status: CANONICALIZED — research reference designation only; no runtime or production promotion.

REFERENCE_UPDATE: REFERENCE_UPDATE_RECOMMENDED
REFERENCE_METHOD_ID: ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
SEED_POLICY: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
REFERENCE_METHOD_VERSION: V1
SCOPE: BIG_LOTTO K10/K15/K20 only
REFERENCE_PRIMARY_DECISION_METRIC: OFFICIAL_ANY_PRIZE
OPTIMIZATION_OBJECTIVE: M3_PLUS_EXACT_COVERAGE
POSTCHECK_OBJECTIVE: OFFICIAL_ANY_PRIZE_EXACT

## Decision boundary

The iterative exact one-number-exchange refinement is designated as the
reference comparator only for BIG_LOTTO K10/K15/K20. The refinement
optimizes M3_PLUS exact coverage; OFFICIAL_ANY_PRIZE is the primary
decision metric checked by the separate exact postcheck.

| K | Reference E seed hash | Terminal hash | Phase 10 moves | Combined moves | First-step max ties | Official outcomes gained |
|---:|:---|:---|---:|---:|---:|---:|
| 10 | `8e7e2dd0417a3eab3b9c9155257cf8be443de4dc34132e50024851ea9b31a810` | `4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5` | 0 | 1 | 1 | 72240 |
| 15 | `a4400d0f1d50f096b74bfb72f8eb10f42bb31bfc6d3d180d6781a867ad1b1d62` | `8057138edd980413fa52607144d66a90372e68d251654998e3a1767fd3d9ce83` | 21 | 22 | 40 | 1504860 |
| 20 | `ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff` | `bf561d28d26961043f112ba8ed762ba9535666022c7df6bcefe49b8a21412710` | 27 | 28 | 1 | 1090558 |

The K15 first-step maximum tie count (40) is load-bearing: exact-Q
ties use the lexicographically smallest canonical portfolio. No plateau
move is accepted.

## Required status fields

```text
GLOBAL_OPTIMUM_STATUS: UNKNOWN
KNOWN_FRONTIER: NO
REFERENCE_COMPARATOR: YES
RUNTIME_PROMOTION: NOT_AUTHORIZED
PRODUCTION_PROMOTION: NOT_AUTHORIZED
PREDICTIVE_SIGNAL_CLAIM: NO
HISTORICAL_OOS_CLAIM: NO
EXPECTED_PAYOUT_CLAIM: NO
STRATEGY_ID_CREATED: NO
```

K1/K2/K3/K5 are not superseded. T539 and P638 are not superseded.
No Phase-7, Phase-9, Phase-10, Matrix, runtime, DB, API, or frontend
artifact was modified by this designation.

## Canonicalized postcheck evidence

Evidence directory: `docs/research/matrix-native-results/b649-reference-e-improved-portfolio-official-any-prize-postcheck-r1`

The original `SHA256SUMS` bytes are preserved. Its logical sealed
filename `verifier.py` maps to the stored non-Python evidence file
`verifier-source.txt`; its bytes match the manifest digest exactly.
The manifest is reconciled logically because the physical filename
differs; direct `shasum -c SHA256SUMS` is not claimed for the relocated
directory.

Do not call this designation best known or globally optimal; do not
start the next task, push, or open a PR in this task.
