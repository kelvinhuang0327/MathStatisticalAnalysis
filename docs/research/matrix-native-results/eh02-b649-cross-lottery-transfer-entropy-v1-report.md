# EH02 — B649 Track B cross-lottery transfer entropy — result report

```text
TASK_ID:              EXPERIMENT_H02_V1_LOCK_EXECUTE_R1
VARIANT_ID:           EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_B649_V1
PREREGISTRATION_HASH: 45a7ddd6a1409a1da65bc347beed6cbb34efa73291910f91b4a3e59b98446045
EXECUTION:            RAN_TO_COMPLETION
SYNTHETIC_FIXTURE:     PASS (both hand-derived cases, exact to 1e-9)
PARAMETER_RESCUE_RUN:  NO
```

## Result

| | EDGE_1 (T539 → B649) | EDGE_2 (P638 Zone-1 → B649) |
|---|---:|---:|
| Observed TE | 0.0014772229 | 0.0018238165 |
| MI comparator | 0.0004837722 | 0.0007022650 |
| GLOBAL raw p | 0.933 | 0.869 |
| GLOBAL Holm p | 1.0 | 1.0 |
| ERA4 raw p | 0.918 | 0.88 |
| ERA4 Holm p | 1.0 | 1.0 |
| Timing control (28-day stale) | **FAIL** (0.001477 ≤ 0.003056) | **FAIL** (0.001824 ≤ 0.004322) |
| Directionality control | **FAIL** (fwd p 0.933 ≥ rev p 0.002) | **FAIL** (fwd p 0.869 ≥ rev p 0.669) |
| **Classification** | **NO_SIGNAL** | **NO_SIGNAL** |

Both edges: `NO_SIGNAL` — the primary `GLOBAL` Holm-adjusted p-value exceeds
0.10 for both edges, which alone is decisive under the locked classification
rule regardless of either control's outcome. Both non-Holm controls also
independently fail for both edges: the 28-day-stale placebo shows a *higher*
transfer-entropy point estimate than the real, causally-aligned signal (the
same era-drift artifact the immediately preceding cross-lottery lagged-context
study already surfaced), and the reverse direction is not weaker than the
forward direction (for EDGE_1, the reverse `B649 -> T539` direction's own raw
p is a striking 0.002 — a genuinely strong-looking association, but in the
*wrong* direction for a `T539 -> B649` transfer claim, and the directionality
gate correctly refuses to credit it as forward evidence).

## Data authority

| Dataset | Rows | Range | Logical SHA-256 |
|---|---:|---|---|
| A (BIG_LOTTO, target) | 2,138 | 2007-03-09 .. 2026-07-31 | `a1f39161…f71a9918` |
| B (DAILY_539, source 1) | 5,930 | 2007-01-01 .. 2026-08-01 | `794ef4e5…6fddcaa42` |
| C (POWER_LOTTO Zone-1, source 2) | 1,933 | 2008-01-24 .. 2026-07-30 | `49c19111…7ee46df0` |

Both edges' eligible-post-burn-in counts and `ERA4` partition sizes
(EDGE_1: 1,937 / [485,484,484,484]; EDGE_2: 1,846 / [462,461,462,461])
reproduced the values independently pinned in the data-authority resolution
artifact exactly — an independent cross-check of the causal-alignment
implementation, not merely a copied number.

## What is supported

Nothing at the locked `SIGNAL` threshold. Both edges are formally
`NO_SIGNAL`: this locked representation/lag/estimator/control set finds no
directed conditional information transfer from either T539's or P638
Zone-1's last-strictly-prior draw into B649's next main-number-sum tertile,
beyond what B649's own preceding value already predicts.

## What is not supported

Predictive advantage, allocation benefit, prize-value advantage, universal
cross-lottery causality, arbitrary-lag generalization, or a combined
EDGE_1+EDGE_2 effect — none were tested. `NO_SIGNAL` falsifies only this
exact representation/lag/estimator/null/control combination for each edge;
it does not rule out cross-lottery information transfer at any other lag,
representation, or estimator (Authority A Sec. 17.3).

## Scope and rescue discipline

`PARAMETER_RESCUE_RUN: NO`. No representation, lag, bin count, tie rule,
estimator, null, seed, permutation count, era rule, stale-day offset,
directionality gate, or threshold was changed after the preregistration hash
was recorded or after any result was inspected. No production prediction was
generated; no database was mutated (every source opened read-only).

## Artifacts

- Preregistration: `eh02-b649-cross-lottery-transfer-entropy-v1-preregistration.md`
- Preregistration hash: `eh02-b649-cross-lottery-transfer-entropy-v1-preregistration-hash.json`
- Machine-readable result: `eh02-b649-cross-lottery-transfer-entropy-v1-result.json`
- Attempt ledger: `eh02-b649-cross-lottery-transfer-entropy-v1-attempt-ledger.json`
- Implementation: `src/lottolab/research/b649_eh02_transfer_entropy.py`,
  `src/lottolab/research/b649_eh02_dataset.py`
- Runner: `tools/run_eh02_b649_v1.py`
- Tests: `tests/unit/test_b649_eh02_transfer_entropy.py`,
  `tests/unit/test_b649_eh02_dataset.py`
