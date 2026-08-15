# STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1 — design

Status: DESIGN ONLY — not locked, not executed ｜ 2026-08-15 ｜ Strategy
Matrix Phase 5, T539 native translation

This document answers the question the Owner packet posed: can
`GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1` — B649 Phase-5's non-Sidon,
deterministic, outcome-free low-overlap constructor (arm B,
`SIDON_BELOW_FRONTIER_MARGIN`, sealed
`docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-report.md`)
— be translated cleanly into DAILY_539's native 5/39 structure without
any B649-specific tuning? It answers yes, and the reason is almost the
whole design: `greedy_min_overlap_portfolio`
(`src/lottolab/research/greedy_min_overlap_constructor.py`) already takes
`(pool_size, draw_size, ticket_count)` as plain parameters and hardcodes
neither `49` nor `6` anywhere — a fact the frozen B649 Phase-5 design doc
itself established (§11(c)) and this task re-confirms by reading the
committed, unmodified source directly. **It does not invoke the
constructor at real T539 scale (`pool_size=39, draw_size=5`), compute any
`Q_ARM_B(k)` value against the real `C(39,5)` winning space, classify
T539, or touch the Strategy Matrix ledger.** That is deferred to a
separate, later lock-and-execute task, pending Owner authorization — the
same two-step pattern
`strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`
and `strategy-matrix-phase3-p638-diversification-native-design-r1.md`
both used.

## 0. Identity

```text
TASK_ID:                 STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1
T539_VARIANT_ID:          GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1
HYPOTHESIS_FAMILY_ID:     DIVERSIFICATION
LOTTERY:                  DAILY_539, 5-of-39
SOURCE_TYPE:               STRATEGY_MATRIX_NATIVE
REPLICATES:                GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 (native
                            parameter substitution, not a copy — see §5)
BUILDS ON (canonical, immutable, not rerun):
  - DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 (sealed, SIDON_BELOW_FRONTIER_MARGIN,
    docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-report.md)
  - DIVERSIFICATION_COVERAGE_T539_V1 (sealed, OUTPERFORMS_RANDOM_EXPECTED_COVERAGE,
    docs/research/matrix-native-results/diversification-coverage-t539-v1-report.md)
  - CYCLIC_SIDON_SHIFT_T539_V1 (existing, immutable, src/lottolab/research/cyclic_sidon_shift_t539.py)
PREREGISTRATION_LOCKED:   NO
T539_EXECUTION:            NOT_RUN
P638:                      NOT_RUN
```

## 1. Research question

Can the deterministic, non-Sidon, low-overlap mechanism that exceeded
Sidon's own gain over random at every tested `k > 1` in B649
(`arm_b_sidon_capture_ratio_primary_event`: 5.91x at `k=3` down to 1.64x
at `k=20`, never below 1x — sealed report, quoted verbatim in §10) be
translated cleanly to T539 5/39 without B649-specific tuning?
`PREDICTIVE_ADVANTAGE: NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE: NOT_TESTED`.
`ECONOMIC_OPTIMALITY: NOT_TESTED`. This is not a test of future-number
prediction, strategy skill, prize value, economic ROI, optimal ticket
count, or historical draw bias, and it makes no claim that T539 arm B
will in fact outperform T539's own Sidon reference once actually run —
only that the translation itself is well-defined and requires no guessed
constant (§5's `STOP_T539_ARM_B_NATIVE_MAPPING_UNRESOLVED` check).

## 2. Boundaries (frozen)

```text
T539:                          DESIGN ONLY, this task
P638:                          NOT_RUN
A (T539 SIDON REFERENCE):      NO MUTATION — CYCLIC_SIDON_SHIFT_T539_V1
                                (src/lottolab/research/cyclic_sidon_shift_t539.py)
                                stays exactly as sealed
B (B649 GREEDY CONSTRUCTOR):   NO MUTATION — greedy_min_overlap_constructor.py
                                (src/lottolab/research/) stays exactly as frozen;
                                this task adds a new T539-scoped module, never
                                edits the shared one
C (RANDOM EXPECTED BASELINE):  NO MUTATION — exact_coverage_baseline.py stays
                                exactly as sealed
B649 ARM C (BOUNDED OPTIMIZER): OUT_OF_SCOPE per Owner packet — not
                                translated, not referenced beyond this line
DB / API / PROSPECTIVE:        NONE
STRATEGY CHANGES:               NONE
HISTORICAL OUTCOMES:            NOT READ
MATRIX RESULT CELL:             NOT APPENDED (ledger untouched by design)
CROSS-LOTTERY RESEARCH LEDGER:  NOT APPENDED
REAL T539 WINNING-SPACE
  ENUMERATION (`C(39,5) = 575,757`
  possible draws):               NOT ENUMERATED against arm B by this task
                                  (§9's descriptive K(m)/Q_random computations
                                  are closed-form, not enumeration, and do not
                                  touch arm B — see §8)
CONSTRUCTOR TOOLKIT INVOCATION
  AT REAL T539 SCALE
  (`pool_size=39, draw_size=5`):  NOT INVOKED by this task, in committed code
                                   or in any script run during this task —
                                   toy/synthetic sizes only, everywhere (§6),
                                   mirroring the B649 Phase-5 boundary exactly
                                   (that document's own §9, applied here for
                                   the identical reason: this constructor's
                                   cost is dominated by a full
                                   C(pool_size,draw_size) scan per forced
                                   ticket, not a cheap bounded search)
```

## 3. Contract (frozen, from the Owner packet)

```text
LOTTERY:                DAILY_539 (5-of-39; DAILY_539_RULE_CONTRACT,
                         src/lottolab/domain/lottery_rules.py:
                         main_number_count=5, main_number_max=39,
                         special_number_count=0 — no bonus-number
                         boundary to draw, unlike POWER_LOTTO Zone-1/Zone-2)
K_LADDER:                {1, 3, 5, 10, 15, 20}  (same ladder as A/B649/P638)
PRIMARY_EVENT:           M3_PLUS (>= 3 of 5 numbers match)
SECONDARY_EVENTS:        M4_PLUS, M5 (T539's own sealed Sidon cell already
                         established M5 is the degenerate exact-match case
                         for a 5-of-39 draw — D_5(k) = k/575,757 for any
                         fixed-size portfolio, geometry-independent; noted
                         here so the later execution task is not surprised
                         by a near-zero M5 delta)
WINNING_SPACE:           exact C(39,5) = 575,757 (not enumerated against
                         arm B by this task — §2)
REAL_DRAW_HISTORY:       NONE
PREDICTIVE / PRIZE / ROI CLAIM: NOT TESTED
DUPLICATE_TICKETS:       must be exactly 0 for every arm at every k (frozen
                         invariant, inherited unchanged from B649/T539/P638)
```

## 4. Comparators

### A. T539 Sidon reference — `CYCLIC_SIDON_SHIFT_T539_V1` (existing, immutable)

`src/lottolab/research/cyclic_sidon_shift_t539.py`. Base set `{0,1,3,7,12}`
in `Z_39`, independently verified Sidon, cyclic shifts, pairwise overlap
`<= 1` across all 39 shifts. Already sealed
`OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`
(`docs/research/matrix-native-results/diversification-coverage-t539-v1-report.md`).
No changes in this task.

### B. T539 native greedy low-overlap constructor — `GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1` (new, this task)

`src/lottolab/research/greedy_min_overlap_constructor_t539.py`
(`greedy_min_overlap_portfolio_t539`), a thin, unconditional delegation to
the shared, unmodified `greedy_min_overlap_portfolio(pool_size=39,
draw_size=5, ticket_count)`. See §5 for why no new algorithm, search, or
constant was needed. Structurally verified in this task (wiring +
constant provenance + a new toy-scale `draw_size=5` generalization check
on the shared module) — never invoked at `(39, 5)` itself, per §2.

### C. Exact random-expected baseline — existing, immutable

`src/lottolab/research/exact_coverage_baseline.py`
(`exact_random_portfolio_coverage`), reused verbatim, exactly as
A/B649/T539/P638 already do. No changes in this task. (Labeled `C` here
to match the Owner packet's own `FUTURE COMPARATORS` list, which does not
include B649's bounded-optimizer arm — see §2.)

## 5. B649-to-T539 mapping (the core deliverable)

`greedy_min_overlap_portfolio(pool_size, draw_size, ticket_count)`
(`src/lottolab/research/greedy_min_overlap_constructor.py`, unchanged
since 971b97b/PR132) takes `pool_size` and `draw_size` as plain
parameters. Reading the committed source in this task (not just trusting
the frozen design doc's own claim) confirms: no modular arithmetic, no
fixed base set, no literal `49` or `6` anywhere in the function body — the
entire mechanism is `itertools.combinations(range(1, pool_size + 1),
draw_size)` plus a plain set-intersection overlap check. This is the
opposite situation from arm A (Sidon), which needed an independently
searched-and-verified base-set *constant* per lottery (already done for
T539: `{0,1,3,7,12}` in `cyclic_sidon_shift_t539.py`).

```text
B649_TO_T539_MAPPING:
  pool_size:     49 -> 39   (DAILY_539_RULE_CONTRACT.main_number_max)
  draw_size:      6 -> 5    (DAILY_539_RULE_CONTRACT.main_number_count)
  ticket_count:  unchanged parameter, same k ladder
  algorithm:      UNCHANGED — zero lines of greedy_min_overlap_constructor.py
                  differ between the B649 and T539 instantiation; only the
                  two integers passed in change, and both come directly
                  from the existing, already-canonical DAILY_539_RULE_CONTRACT,
                  not invented for this task
  UNRESOLVED_CONSTANTS: NONE
```

`STOP_T539_ARM_B_NATIVE_MAPPING_UNRESOLVED` does **not** apply: there is
no B649 constant to translate, because arm B was never parametrized by
one in the first place. This was independently re-confirmed in this task
by reading the unmodified source (not just re-citing the Phase-5 design
doc's own §11(c) claim) and is the reason this design task is
significantly shorter than P638 Zone-1's own native design (which had to
discover and resolve a real mathematical obstruction — an even-modulus
self-paired-difference case — for its Sidon *constant*, §4.1 of that
document). No such search or obstruction exists here because there is no
constant to search for.

## 6. Computational feasibility

**Frozen boundary:** the constructor is not invoked at `(pool_size=39,
draw_size=5)` anywhere in this task (§2). This section estimates, from
toy-scale measurements only, whether the later execution task needs a
fast-evaluator-style optimization the way B649 arm C did
(`exact_coverage_fast_evaluator.py`, c7e3b4a) before it can run.

**Cost shape.** For ticket `i < pool_size // draw_size`, the greedy rule
finds an overlap-`0` candidate and breaks scanning immediately (cheap).
For `i >= pool_size // draw_size`, no overlap-`0` candidate exists, so the
`break` on `score == 0` never fires and the *entire*
`C(pool_size, draw_size)` candidate space must be scanned, each candidate
requiring `i` set-intersection overlap checks against the current
portfolio (the `max()` generator inside `greedy_min_overlap_portfolio`
does not short-circuit). Worst case:

```text
COST_UNITS(pool_size, draw_size, k) = C(pool_size, draw_size)
    * sum(i for i in range(pool_size // draw_size, k))
```

**Measured (this task, toy scale only — pool_size in {16, 18, 20, 22},
draw_size=5 matching T539's own draw size, ticket_count=20, never
pool_size=39):**

| pool_size | C(n,5) | disjoint capacity | k=20 wall-clock |
|---:|---:|---:|---:|
| 16 | 4,368 | 3 | 0.2410s |
| 18 | 8,568 | 3 | 0.4746s |
| 20 | 15,504 | 4 | 0.8500s |
| 22 | 26,334 | 4 | 1.4811s |

Fitted cost-per-unit is tight across all four points: `2.95e-7` to
`3.06e-7` seconds/unit (average `2.9872e-7`), consistent with a
pool-size-independent per-candidate-visit cost, as the cost-shape model
predicts.

**Cross-validation against a real measurement (not toy-scale-only
guessing).** Applying this same toy-fit model (calibrated only on
`draw_size=5` toy pools, never on `pool_size=49` or `39`) to B649's real
parameters (`pool_size=49, draw_size=6, k=20`) predicts **676.7s**. The
sealed B649 result reports arm B's actual real-scale runtime as
**774.5s** (`diversification-constructor-frontier-b649-v1-report.md`,
"Runtime and resources") — the model, extrapolated across two different
draw-sizes and roughly 3200x more cost-units than anything it was fit on,
lands within **12.6%** of a real, independently measured number. This is
disclosed as a strong but imperfect cross-validation, not a proof: the
774.5s figure likely also includes some coverage-evaluation overhead this
model does not separately account for, and the residual 12.6%
under-prediction is consistent with `draw_size=6`'s slightly larger
per-overlap-check cost (6-element vs. 5-element set intersections) than
the toy fit's `draw_size=5` data used.

**T539 estimate:**

```text
T539_COST_UNITS(pool=39, draw=5, k=20) = 97,302,933
RAW_MODEL_ESTIMATE:                       29.1s
B649-CROSS-VALIDATION-CORRECTED ESTIMATE: 33.3s (applying the observed
                                           1.145x under-prediction ratio
                                           from the B649 check above)
```

Because `greedy_min_overlap_portfolio` is a strict nested prefix (§4.B —
unlike B649 arm C, which reruns independently per `k`), **one single call
at `ticket_count=20` yields every `k` in `{1,3,5,10,15,20}` as a free
slice** — the ladder does not multiply this cost.

```text
COMPUTATIONAL_FEASIBILITY:  FEASIBLE, estimated ~30-35s for the full
                             k-ladder construction at real T539 scale (not
                             measured — §2's boundary is not crossed by
                             this estimate). No fast-evaluator-style
                             optimization is anticipated to be necessary
                             for arm B's own construction cost (unlike
                             B649 arm C's exact_portfolio_coverage, which
                             needed exact_coverage_fast_evaluator.py
                             before a bounded search was practical).
                             Coverage evaluation on top of the built
                             portfolio reuses the already-proven-feasible
                             T539 winning-space method (0.025s bare
                             enumeration of C(39,5), already exercised
                             successfully by the sealed T539 Sidon cell)
                             — no new evaluator work anticipated.
MONTE_CARLO:                 NONE
REAL_DRAW_HISTORY:           NOT_USED
REAL_T539_SCALE_EXECUTION:   NOT_RUN (§2)
```

## 7. Geometry metrics (frozen, reused verbatim from B649 Phase-5 §8)

Identical definitions — already generic in `k` and `pool_size`, requiring
no T539-specific adaptation:

```text
max_pairwise_overlap      = max over all C(k,2) ticket pairs of |T_i ∩ T_j|
mean_pairwise_overlap     = mean over the same C(k,2) pairs
overlap_profile           = {overlap_size: pair_count} histogram
number_use_counts         = {number: ticket_count_containing_it} for 1..39
unique_number_coverage    = count of numbers with use_count >= 1 (max 39)
reuse_dispersion          = population standard deviation of number_use_counts
duplicate_tickets         = k - |set(portfolio)|  (frozen invariant: must be 0)
exact M3+/M4+/M5 coverage = Q_X(k), via the existing exact-coverage
                             evaluator — computed ONLY in the later
                             real-execution task, never here
```

No metric beyond this list may be added post-hoc once the real T539
experiment runs (no post-hoc metric expansion, inherited unchanged from
B649 Phase-5 §8).

**One disclosed, testable prediction for the later execution task, not a
result:** B649's real arm-B portfolio never used number 49 (the pool's
highest number) at any tested `k`, a purely structural consequence of the
lexicographic tie-break, not a special case (sealed report, Q4). If the
same structural bias holds for T539, the later execution task's arm-B
portfolio may similarly never use number 39. This is disclosed in advance
so it is read as an anticipated structural property if observed, not a
new post-hoc metric invented after seeing the T539 result.

## 8. Estimands (frozen, from the Owner packet's own EXACT EVALUATION CONTRACT)

```text
Q_ARM_B(k)            = exact M3_PLUS coverage of T539 arm B's k-ticket
                         portfolio (computed ONLY in the later execution task)
Q_SIDON(k)             = exact M3_PLUS coverage of CYCLIC_SIDON_SHIFT_T539_V1
                         (already sealed, quoted in §9)
Q_RANDOM_EXPECTED(k)   = exact_random_portfolio_coverage(39, 5, 3, k)
                         (closed-form, computed and verified in this task — §9)
DELTA_RANDOM(k)        = Q_ARM_B(k) - Q_RANDOM_EXPECTED(k)
DELTA_SIDON(k)         = Q_ARM_B(k) - Q_SIDON(k)
```

No Monte Carlo, per the Owner packet. Both `DELTA_RANDOM` and
`DELTA_SIDON` require `Q_ARM_B(k)`, which is not computed by this task.

## 9. Exact baseline status (computed in this task — closed-form, not enumeration)

`exact_coverage_baseline.py`'s `qualifying_ticket_count` and
`exact_random_portfolio_coverage` are reused verbatim and already
confirmed to generalize to `(pool=39, draw=5)` with no code changes by
the sealed `DIVERSIFICATION_COVERAGE_T539_V1` cell. This task independently
re-verified rather than re-quoted the sealed report's numbers (`python3`,
this task):

```text
N = C(39,5) = 575,757
K(3) = 5,781    (1.004069% of draws)
K(4) = 171      (0.029700% of draws)
K(5) = 1        (0.000174% of draws — the degenerate exact-match case, §3)

Q_random_M3(k):
  k= 1: 0.01004069   k= 3: 0.02982070   k= 5: 0.04920556
  k=10: 0.09599032   k=15: 0.14047338   k=20: 0.18276794

sanity check Q_random_3(1) == K(3)/N exactly: PASS
```

These match the already-sealed T539 Sidon report's own `Q_random_expected`
column exactly, confirming the shared baseline module's behavior has not
drifted. `Q_SIDON(k)` for the same ladder (already sealed, quoted for
reference, not recomputed): `0.01004069, 0.02993450, 0.04957821,
0.09771831, 0.14498304, 0.19206019` (k=1,3,5,10,15,20).

```text
EXACT_BASELINE_STATUS: REUSED_UNMODIFIED_AND_RE-VERIFIED (Q_random_M3
                        ladder + K(3..5) independently recomputed via the
                        existing, unmodified exact_coverage_baseline.py in
                        this task; Q_ARM_B(k) NOT computed — requires the
                        arm-B portfolio, deferred per §2)
```

## 10. Classification and replication rules (frozen, not applied here)

Answering the Owner packet's three `FUTURE REPLICATION RULE` questions as
deterministic, mechanically-applicable rules — none of these are applied
in this task, since `Q_ARM_B(k)` does not yet exist.

**Q1 — does T539 arm B outperform random expected coverage at every
`k > 1`?**

```text
DELTA_RANDOM(k) > 0 for every k in {3,5,10,15,20}  -> T539_ARM_B_OUTPERFORMS_RANDOM
DELTA_RANDOM(k) <= 0 for every k in {3,5,10,15,20} -> T539_ARM_B_DOES_NOT_OUTPERFORM_RANDOM
otherwise                                           -> T539_ARM_B_MIXED_BY_EXPOSURE
```

**Q2 — does it exceed T539 Sidon's own gain over random?**

```text
DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}  -> T539_ARM_B_EXCEEDS_SIDON_GAIN
DELTA_SIDON(k) <= 0 for every k in {3,5,10,15,20} -> T539_ARM_B_DOES_NOT_EXCEED_SIDON_GAIN
otherwise                                          -> T539_ARM_B_MIXED_VS_SIDON
```

**Q3 — is direction consistent with B649 arm B?** B649's own sealed
result (not rerun here, cited as given): `DELTA_SIDON(k) > 0` for arm B at
**every** tested `k > 1`, with `arm_b_sidon_capture_ratio_primary_event`
5.91x (`k=3`), 6.08x (`k=5`), 4.74x (`k=10`), 2.50x (`k=15`), 1.64x
(`k=20`) — shrinking toward but never crossing 1x
(`diversification-constructor-frontier-b649-v1-report.md`, Q1 and the
primary-event result table).

```text
T539's Q2 classification == T539_ARM_B_EXCEEDS_SIDON_GAIN -> CONSISTENT_WITH_B649
otherwise                                                  -> DIRECTION_INCONSISTENT_WITH_B649
                                                               (disclosed, not treated as a
                                                               failure of the T539 result —
                                                               cross-lottery divergence is a
                                                               legitimate outcome, matching
                                                               T539 Sidon's own "not pooled
                                                               into a single numerical
                                                               estimate" convention)
```

**Replication-eligibility rule** (for a possible future P638 translation
of this same arm B, matching the B649 Phase-5 §11(c) pattern): T539 arm B
is `ELIGIBLE_FOR_P638_REPLICATION` only if **all** of:

```text
(a) T539_ARM_B_OUTPERFORMS_RANDOM (Q1)
(b) DELTA_SIDON(k) > 0 for at least one k in {3,5,10,15,20} (Q2, weak form)
(c) the constructor remains genuinely parametrized by (pool_size,
    draw_size) with no T539-specific tuned constant — TRUE by
    construction already, inherited unchanged from the shared module
    (§5); this task's T539 wrapper adds zero new constants (proven by
    the wiring test, §11) so condition (c) cannot be broken by the
    translation itself
```

Otherwise `NOT_ELIGIBLE_FOR_REPLICATION`, with the failing condition
recorded.

```text
CLASSIFICATION_RULE:  Q1/Q2 above (T539_ARM_B_OUTPERFORMS_RANDOM /
                       T539_ARM_B_EXCEEDS_SIDON_GAIN, the same
                       DELTA_RANDOM/DELTA_SIDON sign-across-ladder shape
                       as every prior Strategy Matrix native cell)
REPLICATION_RULE:      Q3 (B649 direction-consistency) + the
                       ELIGIBLE_FOR_P638_REPLICATION rule above
```

## 11. Toy-scale structural verification performed in this task

`tests/unit/test_greedy_min_overlap_constructor_t539.py`:

1. `POOL_SIZE == 39` and `DRAW_SIZE == 5` match
   `DAILY_539_RULE_CONTRACT.main_number_max` /
   `.main_number_count` exactly (no transcription error, no guessing).
2. The T539 wrapper delegates to the *exact* shared, unmodified
   `greedy_min_overlap_portfolio` function object (identity check — no
   local copy, no reimplementation, nothing shadowed).
3. The wrapper's call is proven to pass exactly `(39, 5, ticket_count)`
   through, via `monkeypatch` substituting the shared function with a
   call-recording stub — this proves the wiring is exactly right
   **without ever invoking the real constructor at `(39, 5)`** (§2's
   boundary), by composing two already-true facts: the shared function is
   already proven generic/deterministic/duplicate-free at toy scale
   (existing, unmodified `test_greedy_min_overlap_constructor.py`), and
   this wrapper is now proven to call it with exactly T539's own
   parameters — so the wrapper is deterministic and duplicate-free *by
   substitution*, without executing at real scale.
4. A new toy-scale generalization check on the *shared* (unmodified)
   constructor at `draw_size=5` for the first time (the existing B649
   suite only covers `draw_size` 2 and 3) — `pool_size=15` (far below
   39), confirming disjoint-block behavior and correct ticket shape at
   this draw size, strengthening (not re-deciding) the "no B649-specific
   tuning" claim §5 relies on.

```text
FEASIBILITY_RESULT:   PASS (wiring correct, constants provenance-checked,
                       shared constructor generalizes to draw_size=5 at
                       toy scale)
```

## 12. Pre-lock decisions — resolved

```text
constructor translation:            RESOLVED — direct parameter substitution,
                                     no new algorithm (§5)
unresolved B649 constants:          RESOLVED — NONE exist (§5)
computational feasibility:          RESOLVED — estimated feasible, ~30-35s
                                     for the full k-ladder, cross-validated
                                     against a real B649 measurement (§6)
geometry metric definitions:        RESOLVED — reused verbatim from B649
                                     Phase-5 §8 (§7)
estimands:                          RESOLVED (§8)
exact baseline generalization:      RESOLVED — re-verified, not just
                                     re-quoted (§9)
classification rule (Q1/Q2):        RESOLVED (§10)
B649 direction-consistency rule (Q3): RESOLVED (§10)
replication-eligibility rule:       RESOLVED (§10)
```

## 13. Remaining pre-lock issues (not resolved here, by design)

1. **Which of Q1/Q2's outcomes will actually occur is unknown** — this
   design task makes no prediction stronger than "the mechanism ported
   cleanly and B649's own result makes a positive outcome plausible,"
   consistent with `PREDICTIVE / PRIZE / ROI CLAIM: NOT_TESTED`.
2. **Whether the later execution task should build a T539-scale
   incremental/fast evaluator before running**, the way B649 arm C needed
   `exact_coverage_fast_evaluator.py` — §6 estimates this is
   *unnecessary* for arm B specifically (unlike arm C's very different
   cost shape), but that estimate is not a measurement, and the Owner may
   still prefer to measure before committing compute.
3. **Whether to run T539 arm B alone, or bundle a same-wave P638
   translation** — this document only derives T539 (per the Owner
   packet's explicit scope); P638's own translation is undesigned and
   would need its own pre-lock pass, per the packet's `No P638` boundary.
4. **The correction factor in §6 (1.145x) is derived from a single
   cross-lottery data point (B649)** — a real T539-scale measurement, once
   authorized, would supersede it rather than confirm or refute a
   multi-point trend.

```text
STOP_PHASE5_PRELOCK_DESIGN_UNRESOLVED: does NOT apply — none of the four
    items above block writing or reading this document; they are open
    empirical questions for the *next* task, not defects in this one.
```

## 14. Scope boundary (frozen)

```text
PREDICTIVE_ADVANTAGE:                NOT_TESTED
PRIZE_VALUE_ADVANTAGE:                NOT_TESTED
ECONOMIC_OPTIMALITY:                  NOT_TESTED
T539_EXECUTION / P638_EXECUTION:      NOT_RUN
MATRIX_RESULT_CELL:                   NOT_APPENDED
CROSS_LOTTERY_RESEARCH_LEDGER:        NOT_APPENDED
PRODUCTION / COHORT / PROSPECTIVE:    NONE
REAL_DATA_ACCESS:                     NONE
A / C MUTATION:                       NONE
B DEFINITION MUTATION MID-TASK:       NONE (frozen once written, §2)
B649 ARM C / BOUNDED OPTIMIZER:       OUT_OF_SCOPE, not translated
```

## 15. What this task did and did not do

**Did:** located and read the exact, unmodified B649 arm-B source
(`greedy_min_overlap_constructor.py`) and confirmed by direct inspection
(not by re-citing the frozen design doc alone) that it hardcodes no
B649-specific constant; fast-forwarded a stale local `main` (4 commits
behind `origin/main`, clean fast-forward, no local commits at risk) to
pick up the actual sealed `DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1`
result before writing this document's mapping and Q3 sections against it;
wrote a minimal, unconditional T539 wrapper module and structurally
verified its wiring via monkeypatching (proving correctness without
invoking the real constructor at `(39,5)`); added one new toy-scale
`draw_size=5` generalization test on the shared, already-frozen
constructor; independently re-verified (not re-quoted) T539's `K(3..5)`
and `Q_random_M3` ladder via the existing, unmodified
`exact_coverage_baseline.py`; measured real, toy-scale wall-clock timings
at four `draw_size=5` pool sizes (16/18/20/22, all far below 39), fit a
cost model from them, and cross-validated that model against B649's own
real, measured arm-B runtime (774.5s) before applying it to estimate
T539's real-scale feasibility (~30-35s); froze the geometry metrics,
estimands, classification rule, B649 direction-consistency rule, and a
replication-eligibility rule for a possible future P638 translation.

**Did not:** invoke `greedy_min_overlap_portfolio` (directly or via the
new wrapper) at `(pool_size=39, draw_size=5)` for any `k`, in committed
code or in any script run during this task; compute or retain any
`Q_ARM_B(k)` value for the real T539 rule; enumerate any part of the real
`C(39,5) = 575,757` T539 winning space against arm B; classify T539 under
the frozen rules in §10; append a Strategy Matrix ledger cell or the
cross-lottery research ledger; touch P638, production, the frontend/API,
draw synchronization, historical draw data, or B649's own sealed arm B/C
result files.

## 16. No-rescue statement

The mapping (§5), boundary (§2), feasibility estimate (§6), geometry
metric definitions (§7), estimands (§8), and every classification /
direction-consistency / eligibility rule (§10) were fixed by reading
already-existing, already-frozen code and already-sealed results — none
of them required seeing a real T539 arm-B result to write, because no
such result exists yet. The toy-scale measurements in §6 and §11 were
computed after the mapping was already established as trivial (§5) and
changed nothing about it; they exist only to ground the feasibility
estimate and prove the wrapper's wiring, and are disclosed in full
including the one place a real number (B649's 774.5s) was used to correct
a toy-only projection.

## 17. Artifacts

```text
src/lottolab/research/greedy_min_overlap_constructor_t539.py
tests/unit/test_greedy_min_overlap_constructor_t539.py
docs/research/strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md  (this file)
docs/research/greedy-min-overlap-constructor-t539-v1-preregistration-draft.md
```

## 18. Next step

Return to Owner for explicit lock + execute authorization before any
`Q_ARM_B(k)` value is computed against the real T539 constructor, a
classification is assigned, or the Strategy Matrix ledger (or
cross-lottery research ledger) is touched.
`FINAL_CLASSIFICATION: T539_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_READY_FOR_OWNER_REVIEW`.
