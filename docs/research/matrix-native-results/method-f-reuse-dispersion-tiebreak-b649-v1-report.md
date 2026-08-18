# MATRIX_PHASE8_METHOD_F_DISCOVERY_R1 — result

Status: SEALED -- `DO_NOT_ADVANCE_THIS_EXACT_METHOD_F_VARIANT` -- 2026-08-18
-- B649 (Structure A) only

Preregistration hash:
`32f673d601feadd54d8019a0942358ce1aaf0ef7cda6e7423a5bf9bf85824263`.
Reference E was not rerun (its sealed `Q_E` and geometry were copied). T539
and P638 were not executed.

## Identity

```text
STUDY_ID: STRATEGY_MATRIX_PHASE8_METHOD_F_REUSE_DISPERSION_TIEBREAK_V1
TASK_ID: MATRIX_PHASE8_METHOD_F_DISCOVERY_R1
REFERENCE_E: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
CANDIDATE_F: GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1
LOTTERY: BIG_LOTTO (pool=49, draw=6)
PRIMARY_EVENT: M3_PLUS
GLOBAL_OPTIMUM_STATUS: UNKNOWN
REFERENCE_E_RERUN: NO
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE_RUN: NO
```

## Headline finding

Candidate F's generated portfolio is **byte-identical** to Reference E's
own sealed portfolio at every tested `k` (`portfolio_sha256`
`ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff` for
both -- confirmed by direct comparison, not merely equal coverage). Q_F,
every geometry field, and every ticket are exactly Reference E's. This
means Candidate F's two reuse-dispersion tiebreak coordinates were never
actually decisive during native B649 construction up to `k=20`: at every
step where Reference E's own `(max, sum)` key left more than one legal
ticket tied, the lexicographically-first of those tied tickets already
happened to also be reuse-dispersion-optimal (or no live tie existed at
all). This is a real, previously-open empirical question the toy-scale
tests could not settle -- toy scale and one `draw_size=6` toy example
(pool=11) did show real divergence (first at its 36th ticket, past this
study's `k<=20` ladder) -- and native B649 answers it: no divergence
within the tested range.

## Exact primary coverages

| k  | Q_F            | Q_E (sealed)   | Q_RANDOM (exact)                                                                                                                                                          | DELTA_F_VS_E | DELTA_F_VS_RANDOM |
|---:|:---------------|:---------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------:|:------------------|
| 10 | 212295/1165318 | 212295/1165318 | 3245609755099340710811707686284489657738894441607314745205/18925227210815123131416370444785812104697344617405087907644                                                    | 0/1          | 9905123291865404370631603145662057934141358281349774329345/927336133329941033439402151794504793130169886252849307474556 |
| 15 | 927161/3495954 | 927161/3495954 | 271586308598091491944473961161920217701361795742045773468872681632141016123471965/1104556455747825549799619007981605395356311895723711279867280216503407663299199788     | 0/1          | 72193835762937467068194426150264610454552145338011589953025208869348199836782461037/3734505376883398183872511865985807841699690519441867837231274411998021309614594483228 |
| 20 | 17379/50666    | 17379/50666    | 136464931196442477556786924908590695592336254501634564575023749354655653145167291853998053419693416916091773745/435181005946643158001043454324458968052260403234855038192511642491193996017476596387224730277641783401254902388 | 0/1          | 627542068034581117028982451920808726207857714931072398442462814363130691039342127213649142101498928684432437173/21323869291385514742051129261898489434560759758507896871433070482068505804856353222974011783604447386661490217012 |

Approximate floats, presentation only:

| k  | Q_F      | Q_E      | Q_RANDOM | DELTA_F_VS_E | DELTA_F_VS_RANDOM |
|---:|---------:|---------:|---------:|-------------:|-------------------:|
| 10 | 0.182178 | 0.182178 | 0.171496 | 0.000000     | +0.010681           |
| 15 | 0.265210 | 0.265210 | 0.245878 | 0.000000     | +0.019332           |
| 20 | 0.343011 | 0.343011 | 0.313582 | 0.000000     | +0.029429           |

## Candidate F geometry

| k  | max | sum | peak_reuse | SUM_C_REUSE_3 | reuse_histogram      | unique | dup |
|---:|----:|----:|-----------:|--------------:|:---------------------|-------:|----:|
| 10 | 1   | 11  | 2          | 0             | {1: 38, 2: 11}        | 49     | 0   |
| 15 | 1   | 43  | 3          | 2             | {1: 10, 2: 37, 3: 2}  | 49     | 0   |
| 20 | 1   | 93  | 3          | 22            | {2: 27, 3: 22}        | 49     | 0   |

Identical to sealed Reference E geometry at every `k` (same `max`, same
`sum`, same `duplicate_count`, same portfolio).

## Method F advance gate

```text
METHOD_F_ADVANCE_GATE: FAIL
METHOD_F_STATUS: DO_NOT_ADVANCE_THIS_EXACT_METHOD_F_VARIANT
CROSS_STRUCTURE_REPLICATION_ELIGIBLE: NO
```

- `q_f_ge_q_e_for_every_k_10_15_20`: TRUE (equality at every k)
- `q_f_gt_q_e_at_k_20`: **FALSE** -- `Q_F(20) == Q_E(20)` exactly, not strictly greater
- `duplicate_count_eq_0_for_every_k_10_15_20`: TRUE
- `geometry_max_and_sum_not_worse_than_sealed_e_for_every_k_10_15_20`: TRUE (identical)
- `second_independent_run_byte_identical`: TRUE (and identical to Reference E's own sealed portfolio hash)

One clause fails (`q_f_gt_q_e_at_k_20`), so `METHOD_F_ADVANCE_GATE` is
`FAIL` under the locked all-must-hold rule. This is not tuned or rescued:
the preregistration was hashed before this coverage was computed, and no
parameter changed afterward.

## Reproducibility

Two independent, fresh-process invocations of
`greedy_minmax_sum_then_reuse_dispersion_portfolio(49, 6, 20)` returned
byte-identical portfolios (`ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff`
for both). No randomness, no restart, no history/outcome data was read.

## Runtime

```text
run1_generation_seconds: 1110.8625544590177
run2_generation_seconds: 1116.7835896250326
winning_space_seconds:   15.323698749998584
```

## Claim boundary

This cell supports exact deterministic B649 combinatorial comparison of
Candidate F against Reference E and against the exact random baseline,
for this constructor variant only. It does not prove global optimality,
predictive advantage, profitability, prize/economic value, or that
reuse-dispersion tiebreaks are useless in general -- only that they did
not activate within native B649's `k<=20` ladder for this exact rule.

```text
MONTE_CARLO: NONE
HISTORICAL_DRAWS: NOT_USED
REFERENCE_E_RERUN: NO
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE_RUN: NO
GLOBAL_OPTIMUM_STATUS: UNKNOWN
RUNTIME_PROMOTION: NOT_AUTHORIZED
```
