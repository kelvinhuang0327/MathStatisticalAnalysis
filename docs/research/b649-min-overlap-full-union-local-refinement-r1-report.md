# B649 MIN_OVERLAP Full-Union K10 Local Refinement R1

## Frozen pre-outcome contract

- Cohort: 1761 targets from the sealed MIN_OVERLAP K10/K20 archive.
- Full union: eleven same-target strategy streams; Branch2 result SHA-256 `af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3`.
- Each target's strict history count, cutoff, history SHA-256, pool SHA-256, and distinct count matched the pinned replay.
- The Branch2 result supplied only projected pre-draw fields; paired outcome scores were not decoded or passed to selection.
- Target main and special numbers were excluded from selection queries; only strict prior history entered the adapters.
- Selector `B649_MIN_OVERLAP_FULL_UNION_LOCAL_REFINEMENT_R1` starts from frozen K10 MIN_OVERLAP tickets; K remains 10.
- Selection sample: 65,536 seeded main draws, seed `20260923`; special balls integrated analytically.
- Search: all one-for-one swaps, strict sample improvement, tie-break (remove position, add pool position), maximum 4 swaps.
- Final values use the unchanged exhaustive OFFICIAL_ANY_PRIZE evaluator over all 601,304,088 fair-draw outcomes.

## Full-union and search diagnostics

- Full-union sizes: `{'20': 608, '21': 831, '22': 322}`.
- Outside-prior-20 counts: `{'0': 608, '1': 831, '2': 322}`; total 1475.
- Targets with outside tickets: 1153.
- Targets with any swap: 1519.
- Targets with final portfolio change: 1519.
- Mean swap count: 1085/587 (1.8484).

## Exact K10 comparison on all targets

| Metric | Value |
|---|---:|
| MIN_OVERLAP mean probability | 40898896109/151270928424 (0.27036851) |
| Candidate mean probability | 2291534373/8403940468 (0.27267380) |
| Absolute delta | 4528865/1964557512 (+0.00230529) |
| Relative delta | 348722605/40898896109 (+0.8526%) |
| Required relative lift | 1/100 (+1.0%) |
| READY_FOR_BRANCH2_OOS | **NO** |

The sampled selection score is separate from these exact final probabilities.

## Subset with tickets outside the prior 20

- Targets: 1153.
- MIN_OVERLAP mean: 6700419169/24760843338.
- Candidate mean: 9013559041/33014457784.
- Absolute delta: 34142921/14149053336; relative delta: 239000447/26801676676.
- This subset is diagnostic; the all-target mean is the sole primary gate.

K20 selector optimization and Branch2 OOS were not run. No target outcome value was decoded or used, and no database write, production action, push, or PR occurred.
This fair-draw model result makes no predictive, payout, profit, or ROI claim.
