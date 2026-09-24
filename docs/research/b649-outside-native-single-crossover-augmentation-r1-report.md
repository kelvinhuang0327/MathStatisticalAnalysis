# B649 Outside-Native Single-Crossover K10 Augmentation R1

## Frozen pre-outcome contract

- Cohort: 1761 targets from the sealed MIN_OVERLAP K10/K20 archive.
- Candidate pool per target: native PRE_DRAW full union (U) augmented with deterministic single-number crossover children between the frozen K10 baseline (P10) and native tickets outside the prior 20-ticket pool (O = U minus P20).
- Augmentation `B649_OUTSIDE_NATIVE_SINGLE_CROSSOVER_AUGMENTATION_R1` starts from frozen K10 MIN_OVERLAP tickets; K remains 10.
- Selection sample: 65,536 seeded main draws, seed `20260923`; special balls integrated analytically.
- Search: unchanged local-refinement selector, all one-for-one swaps, strict sample improvement, tie-break (remove position, add pool position), maximum 4 swaps.
- Final values use the unchanged exhaustive OFFICIAL_ANY_PRIZE evaluator over all 601,304,088 fair-draw outcomes.
- No target outcome was decoded or used at any stage.

## Native full-union and augmentation diagnostics

- Native full-union sizes: `{20: 608, 21: 831, 22: 322}`.
- Outside-native counts (|O|): `{0: 608, 1: 831, 2: 322}`; total 1475.
- Augmented pool size: min 20, median 248, mean 362573/1761 (205.89), max 595.
- Generated child count: min 0, median 228, mean 327203/1761 (185.81), max 574.
- Targets with generated children: 1153.

## Search diagnostics

- Targets with any swap: 1669.
- Targets with final portfolio change: 1669.
- Mean swap count: 5606/1761 (3.1834).

## Exact K10 comparison on all targets

| Metric | Value |
|---|---:|
| MIN_OVERLAP mean probability | 40898896109/151270928424 (0.27036851) |
| Candidate mean probability | 10403811713/37817732106 (0.27510406) |
| Absolute delta | 79594527/16807880936 (+0.00473555) |
| Relative delta | 716350743/40898896109 (+1.7515%) |
| Required relative lift | 1/100 (+1.0%) |
| READY_FOR_BRANCH2_OOS | **YES** |

The sampled selection score is separate from these exact final probabilities.

## Control subset (|O| = 0, no augmentation possible)

- Targets: 608.
- MIN_OVERLAP mean: 27267349/101020416.
- Candidate mean: 100758451/370408192.
- Absolute delta: 166751/79373184.

## Outside subset (|O| > 0, augmentation possible)

- Targets: 1153.
- MIN_OVERLAP mean: 6700419169/24760843338.
- Candidate mean: 27408305261/99043373352.
- Absolute delta: 606628585/99043373352.
- Both subsets are diagnostic; the all-target mean is the sole primary gate.

K20 selector optimization and Branch2 OOS were not run. No target outcome value was decoded or used, and no database write, production action, push, or PR occurred.
This fair-draw model result makes no predictive, payout, profit, or ROI claim.
