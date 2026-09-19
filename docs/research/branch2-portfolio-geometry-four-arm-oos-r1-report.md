# B649 portfolio geometry: frozen four-arm paired OOS replay R1

`TASK_STATUS: COMPLETE` · `GEOMETRY_VALIDITY_STATUS: SUPPORTED_DIRECTIONALLY` · `BEST_GEOMETRY_CANDIDATE: ARM_D DETERMINISTIC_MIN_OVERLAP` · `READY_FOR_CONFIRMATORY_BRANCH2: YES` · `READY_FOR_BRANCH6_ADOPTION: NO`

Under the pre-registered gates exactly one arm validated. Deterministic minimum-overlap
selection (ARM_D) raised `OFFICIAL_ANY_PRIZE` over the operational incumbent by
**+4.3157 pp at K=10** (24.0204% -> 28.3362%, +17.97% relative, Holm-adjusted p =
1.62e-4) and by **+1.1357 pp at K=20** (39.8069% -> 40.9426%, +2.85% relative,
Holm-adjusted p = 1.62e-3), over 1,761 strictly paired historical draws. All four arms
choose from one shared pre-draw candidate pool, so the contrast is portfolio geometry
only: no feature, ranking signal or predictive input was added. Random (ARM_B) and k-DPP
(ARM_C) selection moved the same metric in the same direction at both primary budgets,
but neither reached validation.

Two labels are kept apart. The frozen **hypothesis** concerns the random control (ARM_B)
and resolves `SUPPORTED_DIRECTIONALLY`: both primary point deltas are positive and
neither validated. It is not upgraded. ARM_D's `POSITIVE_LIFT_VALIDATED` is the frozen
**per-arm gate** verdict (Holm-adjusted p < 0.05, familywise interval above zero,
adequacy floors met); it answers a different question from the hypothesis.

Not claimed: a predictive edge; an improved expected payout (not measured here); any
improvement at the >= 4-hit tier (`P(max hits >= 4)` for ARM_D: 19 -> 19 draws at K=10,
34 -> 35 at K=20). K=10 is the principal geometry-inference budget. K=20 keeps a
low-decision-leverage caveat: 608 of 1,761 draws (34.5%) admit exactly one portfolio.

## Where the incumbent's redundancy comes from (mechanism candidate)

The incumbent's order key is `support_count DESC, ticket ASC`. No caller supplies
`quality_by_strategy`, so production always takes the `None -> {}` path (recorded in the
freeze commit). The eleven streams emit 22 native tickets and every replayed pool held
20-22 distinct tickets (608 / 831 / 322 draws with 20 / 21 / 22), so at most two
candidates have support above 1 and the operational order is essentially lexicographic.
Lexicographic order tends to place tickets that share leading numbers next to each
other; that last step is an inference consistent with, but not isolated by, this
experiment. What was measured: at K=10 the incumbent's mean pairwise overlap is 1.4525
against 0.7222 for ARM_D, and the incumbent carries 5,033 ticket pairs at overlap >= 4
across the replay where ARM_D carries 0.

## Arms and scope

All four arms select K tickets from one shared pre-draw candidate pool, at the same
target, same PRE_DRAW cutoff, same eligible information, same K, same legal-ticket
constraints, and the same official outcome evaluator.

| Arm | Identity | Seed |
|---|---|---|
| ARM_A | `B649_OPERATIONAL_PORTFOLIO_SELECTOR` 1.0.0 | none (deterministic) |
| ARM_B | `B649_SEEDED_RANDOM_K_CONTROL` 1.0.0 | `SHA256(canonical_bytes(seed object))`, own method domain |
| ARM_C | `B649_KDPP_RAW_MAJORITY_QUALITY_DIVERSITY` 1.1.0 | `SHA256(canonical_bytes(seed object))`, disjoint domain |
| ARM_D | `B649_DETERMINISTIC_MIN_OVERLAP` 1.0.0 (new) | none (deterministic) |

ARM_B and ARM_C seeds are distinct per draw and per K and are recorded as decimal
strings in the result (up to 128 bits each). The paired bootstrap uses seed 649 with
10,000 replicates. K values: 10 and 20 primary, 5 diagnostic only.

`RAW_MAJORITY_EQUIVALENCE: BEHAVIOURALLY_IDENTICAL_PROVEN_BY_CONSTRUCTION`. ARM_A is
asserted equal to `build_portfolio(pool, {}, BUCKET_SIZES)[k]` at every draw and every
K; the replay aborts with `INCUMBENT_ARM_NOT_OPERATIONAL_SELECTOR` on any divergence.
The name alone was not accepted as evidence.

ARM_D tie-break, frozen before outcomes: seed with `candidate_pool_index` 0 (the
incumbent's own top ticket), then repeatedly append the candidate minimising `(max
overlap with selected ASC, summed overlap with selected ASC, candidate_pool_index ASC)`.
Deterministic, outcome-free, nested across K.

Scope: 2,171 canonical BIG_LOTTO draws (`96000001`..`115000089`). Excluded: 200 warm-up
draws (200 prior draws required), 191 with fewer than 20 distinct pool tickets, and 19
where `select_kdpp` returned `INFEASIBLE_NUMERICAL_RANK` at K=20 (a draw infeasible for
any arm is dropped for all arms, preserving same-draw pairing). Valid paired draws:
1,761, `97000098` (2008-12-05) .. `115000089` (2026-09-18), 81.11% coverage.

## Primary outcome — `OFFICIAL_ANY_PRIZE`, paired draw-level

Familywise control is Holm over 3 candidate arms x K10/K20 (family of 6); the familywise
interval is a 10,000-replicate seeded paired-draw bootstrap at alpha 0.05/6 (99.17%).
`POSITIVE_LIFT_VALIDATED` requires Holm-adjusted p < 0.05 and a familywise interval
above zero with >= 30 paired and >= 10 discordant draws; otherwise a non-zero delta is
`UNSTABLE_OR_INCONCLUSIVE`.

### K = 10 (PRIMARY) — incumbent 423/1761 = 24.0204%

| Arm | Wins | Rate | Delta | Rel. lift | Discordant (+/-) | Holm p | Familywise CI | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|---|
| ARM_B RANDOM | 442 | 25.0994% | +1.0789 pp | +4.49% | 313 (166/147) | 0.618 | [-1.647, +3.691] pp | UNSTABLE_OR_INCONCLUSIVE |
| ARM_C KDPP | 434 | 24.6451% | +0.6246 pp | +2.60% | 305 (158/147) | 0.618 | [-1.988, +3.237] pp | UNSTABLE_OR_INCONCLUSIVE |
| **ARM_D MIN_OVERLAP** | **499** | **28.3362%** | **+4.3157 pp** | **+17.97%** | **322 (199/123)** | **1.62e-4** | **[+1.647, +6.985] pp** | **POSITIVE_LIFT_VALIDATED** |

### K = 20 (PRIMARY) — incumbent 701/1761 = 39.8069%

| Arm | Wins | Rate | Delta | Rel. lift | Discordant (+/-) | Holm p | Familywise CI | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|---|
| ARM_B RANDOM | 712 | 40.4316% | +0.6246 pp | +1.57% | 35 (23/12) | 0.269 | [-0.284, +1.533] pp | UNSTABLE_OR_INCONCLUSIVE |
| ARM_C KDPP | 714 | 40.5451% | +0.7382 pp | +1.85% | 37 (25/12) | 0.188 | [-0.170, +1.647] pp | UNSTABLE_OR_INCONCLUSIVE |
| **ARM_D MIN_OVERLAP** | **721** | **40.9426%** | **+1.1357 pp** | **+2.85%** | **30 (25/5)** | **1.62e-3** | **[+0.341, +1.988] pp** | **POSITIVE_LIFT_VALIDATED** |

### K = 5 (DIAGNOSTIC ONLY, outside the familywise family) — incumbent 242/1761 = 13.7422%

| Arm | Wins | Rate | Delta | Nominal 95% CI | Discordant (+/-) | Nominal p |
|---|---:|---:|---:|---|---:|---:|
| ARM_B RANDOM | 270 | 15.3322% | +1.5900 pp | [-0.341, +3.521] pp | 308 (168/140) | 0.124 |
| ARM_C KDPP | 236 | 13.4015% | -0.3407 pp | [-2.158, +1.533] pp | 274 (134/140) | 0.763 |
| ARM_D MIN_OVERLAP | 275 | 15.6161% | +1.8739 pp | [+0.114, +3.634] pp | 247 (140/107) | 0.042 |

### Uncertainty intervals (delta vs incumbent)

| K | Arm | Delta | Nominal 95% CI | Familywise 99.17% CI |
|---|---|---:|---|---|
| 10 | ARM_B RANDOM | +1.0789 pp | [-0.909, +3.010] pp | [-1.647, +3.691] pp |
| 10 | ARM_C KDPP | +0.6246 pp | [-1.306, +2.555] pp | [-1.988, +3.237] pp |
| 10 | ARM_D MIN_OVERLAP | +4.3157 pp | [+2.328, +6.303] pp | [+1.647, +6.985] pp |
| 20 | ARM_B RANDOM | +0.6246 pp | [+0.000, +1.306] pp | [-0.284, +1.533] pp |
| 20 | ARM_C KDPP | +0.7382 pp | [+0.057, +1.420] pp | [-0.170, +1.647] pp |
| 20 | ARM_D MIN_OVERLAP | +1.1357 pp | [+0.568, +1.760] pp | [+0.341, +1.988] pp |
| 5 | ARM_B RANDOM | +1.5900 pp | [-0.341, +3.521] pp | n/a (diagnostic) |
| 5 | ARM_C KDPP | -0.3407 pp | [-2.158, +1.533] pp | n/a (diagnostic) |
| 5 | ARM_D MIN_OVERLAP | +1.8739 pp | [+0.114, +3.634] pp | n/a (diagnostic) |

## Secondary outcomes, and where the gain sits

Absolute values per arm (draw counts in parentheses; `E[max]` is the mean best-ticket main-number match).

| K | Arm | Any prize | P(max>=3) | P(max>=4) | E[max matches] |
|---|---|---:|---:|---:|---:|
| 5 | ARM_A INCUMBENT | 13.74% (242) | 7.67% (135) | 0.45% (8) | 1.5230 |
| 5 | ARM_B RANDOM | 15.33% (270) | 9.77% (172) | 0.62% (11) | 1.5855 |
| 5 | ARM_C KDPP | 13.40% (236) | 8.06% (142) | 0.17% (3) | 1.5781 |
| 5 | ARM_D MIN_OVERLAP | 15.62% (275) | 8.80% (155) | 0.68% (12) | 1.6814 |
| 10 | ARM_A INCUMBENT | 24.02% (423) | 14.31% (252) | 1.08% (19) | 1.8427 |
| 10 | ARM_B RANDOM | 25.10% (442) | 15.56% (274) | 1.02% (18) | 1.8915 |
| 10 | ARM_C KDPP | 24.65% (434) | 15.16% (267) | 0.74% (13) | 1.9160 |
| 10 | ARM_D MIN_OVERLAP | 28.34% (499) | 16.92% (298) | 1.08% (19) | 1.9920 |
| 20 | ARM_A INCUMBENT | 39.81% (701) | 25.89% (456) | 1.93% (34) | 2.1562 |
| 20 | ARM_B RANDOM | 40.43% (712) | 26.63% (469) | 1.93% (34) | 2.1715 |
| 20 | ARM_C KDPP | 40.55% (714) | 26.46% (466) | 1.93% (34) | 2.1726 |
| 20 | ARM_D MIN_OVERLAP | 40.94% (721) | 26.69% (470) | 1.99% (35) | 2.1783 |

Deltas versus the incumbent (nominal 95% paired-bootstrap intervals; no familywise adjustment).

| K | Arm | P(max>=3) delta | P(max>=4) draws (A -> arm) | E[max] delta |
|---|---|---|---:|---|
| 10 | ARM_B RANDOM | +1.2493 pp [-0.398, +2.839] pp | 19 -> 18 | +0.0488 [+0.0187, +0.0795] |
| 10 | ARM_C KDPP | +0.8518 pp [-0.795, +2.499] pp | 19 -> 13 | +0.0733 [+0.0426, +0.1045] |
| 10 | ARM_D MIN_OVERLAP | +2.6122 pp [+0.965, +4.259] pp | 19 -> 19 | +0.1493 [+0.1193, +0.1794] |
| 20 | ARM_B RANDOM | +0.7382 pp [+0.227, +1.306] pp | 34 -> 34 | +0.0153 [+0.0062, +0.0244] |
| 20 | ARM_C KDPP | +0.5679 pp [+0.000, +1.136] pp | 34 -> 34 | +0.0165 [+0.0074, +0.0261] |
| 20 | ARM_D MIN_OVERLAP | +0.7950 pp [+0.284, +1.363] pp | 34 -> 35 | +0.0221 [+0.0142, +0.0307] |
| 5 | ARM_B RANDOM | +2.1011 pp [+0.511, +3.691] pp | 8 -> 11 | +0.0625 [+0.0227, +0.1028] |
| 5 | ARM_C KDPP | +0.3975 pp [-1.079, +1.817] pp | 8 -> 3 | +0.0551 [+0.0165, +0.0926] |
| 5 | ARM_D MIN_OVERLAP | +1.1357 pp [-0.227, +2.555] pp | 8 -> 12 | +0.1584 [+0.1232, +0.1948] |

The gain sits in the lowest prize tiers. For ARM_D the +76 additional any-prize draws at
K=10 split into +46 draws in which some ticket matched three or more main numbers and
+30 draws won with fewer than three main matches; at K=20 the +20 split into +14 and +6.
`P(max hits >= 4)` is unchanged at K=10 (19 -> 19 draws) and moves by one draw at K=20
(34 -> 35). At K=10 ARM_B is at 18 and ARM_C at 13 draws; the ARM_C shortfall (-0.3407
pp, nominal 95% CI [-0.852, +0.114] pp) includes zero. The primary metric is the
probability of winning at least one prize on the day; it says nothing about prize size.
Expected payout was not measured and is not claimed.

## Geometry diagnostics

| K | Arm | Mean pairwise overlap | Unique-number coverage | Ticket-set changed vs ARM_A | Duplicate-ticket draws | Legal |
|---|---|---:|---:|---:|---:|---|
| 10 | ARM_A | 1.4525 | 26.89 | - | 0 | yes |
| 10 | ARM_B | 1.2226 | 28.79 | 1.0000 | 0 | yes |
| 10 | ARM_C | 1.1076 | 30.25 | 1.0000 | 0 | yes |
| 10 | ARM_D | 0.7222 | 35.46 | 1.0000 | 0 | yes |
| 20 | ARM_A | 1.2606 | 35.37 | - | 0 | yes |
| 20 | ARM_B | 1.2121 | 36.59 | 0.6332 | 0 | yes |
| 20 | ARM_C | 1.1986 | 36.84 | 0.6462 | 0 | yes |
| 20 | ARM_D | 1.1763 | 36.96 | 0.6547 | 0 | yes |
| 5 | ARM_A | 1.6819 | 18.59 | - | 0 | yes |
| 5 | ARM_B | 1.2129 | 20.49 | 0.9994 | 0 | yes |
| 5 | ARM_C | 1.0980 | 21.14 | 0.9994 | 0 | yes |
| 5 | ARM_D | 0.3397 | 26.66 | 1.0000 | 0 | yes |

K=10 pairwise-overlap distribution (pair counts at overlap 0..6, summed over 1,761 draws):

| Arm | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ARM_A | 18737 | 26185 | 20849 | 8441 | 3266 | 1767 | 0 |
| ARM_B | 24701 | 26588 | 17952 | 6604 | 2417 | 983 | 0 |
| ARM_C | 26745 | 27568 | 17203 | 5598 | 1649 | 482 | 0 |
| ARM_D | 35984 | 29827 | 12895 | 539 | **0** | **0** | 0 |

K=20 pairwise-overlap distribution (pair counts at overlap 0..6, summed over 1,761 draws):

| Arm | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ARM_A | 99662 | 111666 | 78981 | 29434 | 10369 | 4478 | 0 |
| ARM_B | 105002 | 112744 | 75521 | 27597 | 9641 | 4085 | 0 |
| ARM_C | 105878 | 113444 | 74976 | 27234 | 9340 | 3718 | 0 |
| ARM_D | 107610 | 113813 | 74494 | 26634 | 9330 | 2709 | 0 |

## Decision leverage

At K=10 no draw is forced and every candidate arm's portfolio differs from the
incumbent's in 1,761 of 1,761 draws. K=20 has little freedom: 608 of 1,761 draws (34.5%)
have exactly 20 candidates, so a single portfolio exists and all four arms are identical
there by construction (`forced_selection_draws`: K=5 0, K=10 0, K=20 608). Another 831
draws have 21 candidates (21 possible K=20 portfolios) and 322 have 22 (231 possible).
ARM_D's K=20 portfolio differs from the incumbent's in all 1,153 non-forced draws; ARM_B
and ARM_C coincide with it by chance in 38 and 15. The freeze note's "21-22 distinct
tickets" came from a three-target dry run; the full replay shows 20-22 (mean 20.84).

The adequacy floors (>= 30 paired draws, >= 10 primary discordant draws) are met at K=10
(305-322 discordant) and K=20 (30-37), so every verdict is computable. That is not the
same as having leverage: `DECISION_LEVERAGE: HIGH at K=10; LOW at K=20`. A K=20 null
would not have refuted the mechanism, and the K=20 positive is a small absolute effect
resting on 30 discordant draws.

## Are the outcome deltas consistent with the overlap changes?

Directionally, but the relation is not a simple monotone in overlap.

| K | Arm | d(overlap) | d(coverage) | d(any prize) |
|---|---|---:|---:|---:|
| 10 | ARM_B | -0.2299 | +1.90 | +1.0789 pp |
| 10 | ARM_C | -0.3449 | +3.35 | +0.6246 pp |
| 10 | ARM_D | -0.7303 | +8.57 | +4.3157 pp |
| 20 | ARM_B | -0.0485 | +1.23 | +0.6246 pp |
| 20 | ARM_C | -0.0620 | +1.47 | +0.7382 pp |
| 20 | ARM_D | -0.0844 | +1.60 | +1.1357 pp |
| 5 | ARM_B | -0.4691 | +1.90 | +1.5900 pp |
| 5 | ARM_C | -0.5839 | +2.55 | -0.3407 pp |
| 5 | ARM_D | -1.3422 | +8.06 | +1.8739 pp |

ARM_C lowers mean overlap more than ARM_B at every K, yet its any-prize point estimate
is not reliably higher: ARM_C minus ARM_B is -0.4543 pp at K=10 (p = 0.688), +0.1136 pp
at K=20 (p = 0.832) and -1.9307 pp at K=5 (nominal p = 0.049, diagnostic). Among the
three candidate arms only ARM_D combines a large overlap reduction, removal of every
pair at overlap >= 4 (K=10) and a large gain in unique-number coverage, and it is the
only arm that validated. With three arms these properties cannot be separated from one
another, so which of them carries the effect is a hypothesis for the confirmatory step,
not a finding.

## The K=20 saturation caveat, recorded before outcomes

The freeze commit recorded, before any outcome was read, that the live pool is small
enough for K=20 to be nearly saturated (measured counts are under Decision leverage).
That is why every K=20 effect is compressed and why the pre-registered `+6.7pp` K=20
reference expectation was not reached: that figure assumed free choice over the whole
ticket space, not this pool. K=10 is where the experiment has real leverage; the K=20
result is read as a weak-leverage confirmation, not as an independent test, and a K=20
null would not have counted against the mechanism.

## Frozen hypothesis outcome

`GEOMETRY_VALIDITY_HYPOTHESIS` (frozen): at K=10 and K=20, `SEEDED_RANDOM_K_CONTROL`
should improve the primary union-success metric relative to the operational incumbent if
excessive incumbent overlap is the dominant mechanism identified by the historical
geometry analysis.

`GEOMETRY_VALIDITY_STATUS: SUPPORTED_DIRECTIONALLY`. ARM_B improved at both primary K
(+1.0789 pp and +0.6246 pp), so the direction predicted by the overlap diagnosis held
and the diagnosis is not refuted. Neither result reached validation (Holm-adjusted p
0.618 and 0.269). Against the `REFERENCE_EXPECTATION_ONLY` values, which were never
acceptance thresholds: the K=10 estimate is below +2.7pp but its nominal 95% interval
[-0.909, +3.010] pp covers it, so K=10 cannot distinguish "no effect" from the reference
effect; the K=20 estimate and its interval [+0.000, +1.306] pp sit far below +6.7pp. The
only arm that validated is the one that minimises overlap by construction; this does not
isolate overlap from the other properties of ARM_D.

## Cross-arm contrasts

Unadjusted and outside the frozen Holm family; descriptive. Delta is the first-named arm
minus the second-named arm.

| K | Contrast | Wins (second -> first) | Delta | Nominal 95% CI | Discordant (+/-) | Nominal p |
|---|---|---:|---:|---|---:|---:|
| 10 | ARM_D vs ARM_B | 442 -> 499 | +3.2368 pp | [+1.306, +5.224] pp | 317 (187/130) | 1.62e-3 |
| 10 | ARM_D vs ARM_C | 434 -> 499 | +3.6911 pp | [+1.704, +5.622] pp | 311 (188/123) | 2.71e-4 |
| 10 | ARM_C vs ARM_B | 442 -> 434 | -0.4543 pp | [-2.385, +1.476] pp | 304 (148/156) | 0.688 |
| 20 | ARM_D vs ARM_B | 712 -> 721 | +0.5111 pp | [+0.057, +1.022] pp | 19 (14/5) | 0.064 |
| 20 | ARM_D vs ARM_C | 714 -> 721 | +0.3975 pp | [+0.000, +0.852] pp | 15 (11/4) | 0.118 |
| 20 | ARM_C vs ARM_B | 712 -> 714 | +0.1136 pp | [-0.398, +0.625] pp | 22 (12/10) | 0.832 |
| 5 | ARM_D vs ARM_B | 270 -> 275 | +0.2839 pp | [-1.760, +2.271] pp | 325 (165/160) | 0.824 |
| 5 | ARM_D vs ARM_C | 236 -> 275 | +2.2147 pp | [+0.227, +4.145] pp | 313 (176/137) | 0.032 |
| 5 | ARM_C vs ARM_B | 270 -> 236 | -1.9307 pp | [-3.805, -0.057] pp | 282 (124/158) | 0.049 |

At K=10 ARM_D is ahead of both stochastic arms at the nominal level (p = 1.62e-3 and
2.71e-4); k-DPP and random are not distinguishable from each other at K=10 or K=20. This
is consistent with deterministic overlap minimisation outperforming stochastic
diversification on this pool. The contrast does not isolate why: ARM_D differs from
ARM_C in more than the sampling-versus-maximising distinction.

## Interpretation limits

- No predictive edge. All arms share one pool and one information set; nothing that
  could predict outcomes was added, and the contrasts are between selection rules over
  the same tickets.
- No expected-payout claim. Payout was not measured; the >= 4-hit tier did not improve.
- History is the current canonical dataset with causal prefixes reconstructed, not a
  vintage PRE_DRAW archive. IID bootstrap and exact McNemar do not establish temporal
  independence across overlapping histories.
- No untouched holdout. The whole available history was scored. The overlap-deficit
  diagnosis that motivated ARM_D came from earlier analyses of the B649 historical
  record (the frozen hypothesis and reference expectations cite it). ARM_D's rule was
  frozen before this experiment scored any outcome and has no fitted parameter, but the
  idea was not formed independently of this history.
- The reference expectations were never thresholds and were not used as such. No
  `q_sidon` value or diversification table was used as a bound, filter or acceptance
  gate.

## Stability

Windows are the last 50 / 300 / 750 canonical draws and are nested: descriptive, not
independent confirmation. "Earlier" is derived by subtracting the last-750 window from
the full period (arithmetic on frozen outputs, not a test, and not part of the frozen
acceptance). Cells are the any-prize delta versus the incumbent.

| K | Arm | Last 50 (n=49) | Last 300 (n=278) | Last 750 (n=676) | Earlier (n=1085) | Full (n=1,761) |
|---|---|---:|---:|---:|---:|---:|
| 10 | ARM_B | +8.1633 pp | +6.8345 pp | +4.2899 pp | -0.9217 pp | +1.0789 pp |
| 10 | ARM_C | +0.0000 pp | +2.1583 pp | +0.7396 pp | +0.5530 pp | +0.6246 pp |
| 10 | ARM_D | +10.2041 pp | +8.2734 pp | +6.2130 pp | +3.1336 pp | +4.3157 pp |
| 20 | ARM_B | +0.0000 pp | +0.7194 pp | +0.7396 pp | +0.5530 pp | +0.6246 pp |
| 20 | ARM_C | +0.0000 pp | +0.3597 pp | +0.7396 pp | +0.7373 pp | +0.7382 pp |
| 20 | ARM_D | +0.0000 pp | +0.7194 pp | +1.0355 pp | +1.1982 pp | +1.1357 pp |

ARM_B's full-period K=10 gain (+1.0789 pp) comes entirely from the most recent 676
paired draws; over the preceding 1,085 it is -0.9217 pp. ARM_D is positive in both
partitions (+3.1336 pp earlier, +6.2130 pp recent). At K=20 ARM_D has 11 / 4 / 0
discordant draws in the last 750 / 300 / 50, too few to read.

## Validation

- External cross-check of the incumbent (recorded at the time; not re-executed at
  finalisation). Against the independently produced Lane-2 donor result (`4b55d728`),
  over the 1,760 shared target draws, ARM_A showed 0 ticket mismatches and 0
  official-prize score mismatches, with identical win counts (242 / 423 / 701 at K=5 /
  10 / 20). Pair counts reconcile exactly: 1,779 donor + 1 new target (`115000089`) - 19
  `ARM_INFEASIBLE_K20` = 1,761. This result's ARM_A totals over all 1,761 draws are 242
  / 423 / 701: the new target contributed no incumbent win.
- `LEAKAGE_STATUS: PASS_STRICT_PREFIX_AND_OUTCOME_ISOLATED_SELECTION`. All eleven
  producers receive only strictly earlier rows; all four selections are sealed before
  the target is scored. Recomputed from the stored rows: 0 PRE_DRAW cutoff violations
  across all 5,283 draw-K rows.
- `OUTCOME_TUNING: NONE`. The freeze commit precedes outcome evaluation, and no frozen
  source was amended afterwards: the final commit adds only this report and the result
  file, and the module SHA-256 recorded in the result equals the frozen blob.
- Pre-freeze verification on the frozen tree, recorded before the freeze and reused
  without re-execution at finalisation: focused tests 25 PASS; affected regression 109
  PASS (134 total); Ruff PASS; Pyright 0 errors (`--pythonversion 3.13`, the project's
  `requires-python`); mutation sanity: a mutant removing the PRE_DRAW cutoff guard and a
  mutant making ARM_D ignore overlap each failed the suite and were reverted.
- Result-artifact integrity, checked at finalisation with a verifier that is not
  committed (it is a scratch script): the result is byte-for-byte the module's own
  encoder output (sorted keys, compact separators, one trailing newline); every stored
  aggregate was recomputed from the raw per-draw rows with 0 differences, including
  exact McNemar p-values, Holm adjustment, verdicts, geometry, ticket-set-changed counts
  and an exact replay of every seeded bootstrap interval; the four arms' tickets at
  every draw fit inside one candidate pool of `candidate_count` tickets, and all four
  arms are identical on every forced draw.

## Authority and execution

- `BASE_HEAD` `947baf9da42a5656a6e6e9577b33cc5e33213347`, `BASE_TREE`
  `109f6ca34db4363f11b378f2ad3cbeb730e6ce99`.
- `FREEZE_COMMIT` `4a8516d8cbd6d1c682e4c9ffb9c7a7528adb20b3`, `FREEZE_TREE`
  `b1d3513654ae953055898728a6f1dd5107c40596`.
- k-DPP producer `19f15af7a7424bdfc7e04c49055fc4ca41b59635`, canonical on main via PR
  #311.
- Three-arm adapter donor `a329bb2e1edf78001dea057dc88bf608427de986` (local-only,
  resolved by bounded object lookup).
- OOS harness donor `4b55d728a807e851ca87ed484edd5722696c8116` (local-only). Its LOO
  tie-break modules are absent from main, so the statistical procedure, `load_draws`,
  `build_pool` and `score` were reused directly rather than importing the unrelated LOO
  candidate.
- Source: `/Users/kelvin/Library/Application Support/LottoLab/lottolab.db`, 2,171 draws
  `96000001`..`115000089`, logical SHA-256
  `43b3cc4726b5a4cbe43ff40d8d08d20aeb37837db90f0857fb344ada0579b842`.
- **Concurrent writer observed.** The physical database file hash changed during the
  replay (before/after hashing recorded at the time), caused by an unrelated writer. The
  BIG_LOTTO logical dataset was unchanged: the module re-derives the logical hash after
  the replay and refuses to write its result on any difference
  (`CANONICAL_SOURCE_MUTATED_DURING_REPLAY`), and the result exists. Reads were `PRAGMA
  query_only`. This task wrote nothing to the database, and finalisation did not open
  it.
- `EXECUTION_PROVENANCE: DIRECT_UNPROTECTED_EXECUTION`. The Fable protected-execution
  launcher is absent from this install (no `scripts/` directory), so the replay ran as a
  direct background process without duplicate-execution protection.
- Result:
  [branch2-portfolio-geometry-four-arm-oos-r1-result.json](branch2-portfolio-geometry-four-arm-oos-r1-result.json),
  17,243,659 bytes on a single line, SHA-256
  `af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3`. It is the largest
  tracked artifact under `docs/` (the next largest is 3.8 MB); it is kept byte-exact
  because the per-draw sealed selections it carries cannot be regenerated once the
  source database grows.
- `PUSH: NOT RUN`; `PR: NOT CREATED`; `PRODUCTION_MUTATION: NONE`.

## Recommended next action

Open one pre-registered confirmatory Branch2 evaluation of ARM_D at K=10 (K=20
secondary, with the forced-selection caveat), freeze its acceptance before any scoring,
and add an explicit expected-payout metric. This replay already scored the whole
available history, so the confirmation must use information it did not score, such as
forward draws or an outcome-free exact-probability evaluation of the sealed selections,
rather than re-scoring the same history. Branch6 adoption stays `NO` until that
confirmation passes.
