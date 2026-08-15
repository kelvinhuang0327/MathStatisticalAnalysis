# STRATEGY_MATRIX_PHASE5_DIVERSIFICATION_CONSTRUCTOR_FRONTIER_DESIGN_R1 — design

Status: DESIGN ONLY — not locked, not executed ｜ 2026-08-15 ｜ Strategy Matrix
Phase 5, Generation 2

This document answers the question Phase 4's synthesis report explicitly
raised as its Phase-5 research priority: at a fixed B649 ticket count `k`,
how much of the Sidon-shift portfolio's coverage advantage is explained by
low pairwise overlap itself, and how close is Sidon-shift to the best
coverage a bounded, preregistered constructor search can find? It derives,
implements, and structurally verifies (toy/synthetic scale only) two new
constructor arms, freezes every parameter the eventual real-scale
experiment needs, and defines the classification, frontier-nearness, and
replication-eligibility rules that experiment's result will be read
through. **It does not run the real B649 frontier experiment, compute any
`Q_B(k)` or `Q_C(k)` value against the real `C(49,6)` winning-space
enumeration, retain any B649-scale challenger portfolio, or touch the
Strategy Matrix ledger.** That is explicitly deferred to a separate,
later lock-and-execute task, pending Owner authorization — the same
two-step pattern `strategy-matrix-phase3-p638-diversification-native-design-r1.md`
used for P638 Zone-1.

## 0. Identity

```text
TASK_ID:                    STRATEGY_MATRIX_PHASE5_DIVERSIFICATION_CONSTRUCTOR_FRONTIER_DESIGN_R1
PLANNED_VARIANT_FAMILY_ID:  DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1
HYPOTHESIS_FAMILY_ID:       DIVERSIFICATION
LOTTERY:                    BIG_LOTTO (B649), 6-of-49
SOURCE_TYPE:                 STRATEGY_MATRIX_NATIVE
MECHANISM:                   DIVERSIFICATION_CONSTRUCTOR_FRONTIER
REFERENCE_GAME:              B649 / 6-of-49
BUILDS ON (canonical, immutable, not rerun):
  - DIVERSIFICATION_COVERAGE_B649_V1        (sealed, OUTPERFORMS_RANDOM_COVERAGE)
  - DIVERSIFICATION_COVERAGE_T539_V1        (sealed, OUTPERFORMS_RANDOM_EXPECTED_COVERAGE)
  - DIVERSIFICATION_COVERAGE_P638_ZONE1_V1  (sealed, OUTPERFORMS_RANDOM_EXPECTED_COVERAGE)
  - STRATEGY_MATRIX_PHASE4_DIVERSIFICATION_CROSS_LOTTERY_SYNTHESIS_R1 (read-only synthesis,
    §7 names this exact mechanism as the recommended Phase-5 Generation-2 candidate)
PREREGISTRATION_LOCKED:      NO
B649_FRONTIER_EXECUTION:     NOT_RUN
```

## 1. Research question

At a fixed ticket count `k`, does a bounded, preregistered coverage-search
constructor materially outperform the canonical Sidon-shift geometry's
exact `M3_PLUS` winning-space coverage, and does a non-Sidon low-overlap
constructor recover most of Sidon-shift's advantage over random without
using any Sidon/difference-set algebra? `PREDICTIVE_ADVANTAGE: NOT_TESTED`.
`PRIZE_VALUE_ADVANTAGE: NOT_TESTED`. `ECONOMIC_OPTIMALITY: NOT_TESTED`.
This is not a test of future-number prediction, strategy skill, prize
value, economic ROI, optimal ticket count, or historical draw bias, and it
makes no claim that any arm here is globally optimal — see §5's
`GLOBAL_OPTIMUM_STATUS: UNKNOWN` rule.

## 2. Boundaries (frozen)

```text
B649:                         DESIGN ONLY, this task
T539:                         NOT_RUN
P638:                         NOT_RUN
A (SIDON_REFERENCE):          NO MUTATION — CYCLIC_SIDON_SHIFT_B649_V1 stays exactly as sealed
D (RANDOM_EXPECTED_BASELINE): NO MUTATION — exact_coverage_baseline.py stays exactly as sealed
B, C DEFINITIONS:             FROZEN by this document once written — not renegotiated mid-task
DB / API / PROSPECTIVE:       NONE
STRATEGY CHANGES:              NONE
HISTORICAL OUTCOMES:           NOT READ
MATRIX RESULT CELL:            NOT APPENDED (ledger untouched by design)
REAL B649 WINNING-SPACE
  ENUMERATION (`C(49,6) = 13,983,816`
  possible draws):              NOT ENUMERATED by this task, for any arm
CONSTRUCTOR TOOLKIT INVOCATION
  AT REAL B649 SCALE
  (`pool_size=49, draw_size=6`):  NOT INVOKED for B or C by this task, in
                                   committed code or in any script run
                                   during this task — toy/synthetic sizes
                                   only, everywhere (§7)
```

Phase-4 evidence (all three sealed `DIVERSIFICATION` cells,
`OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`) is treated as canonical and is not
reread, rerun, or reinterpreted here beyond the one-line summary above.

## 3. Contract

```text
K:                    {1, 3, 5, 10, 15, 20}   (same exposure ladder as A/B649's own sealed cell)
PRIMARY_EVENT:        M3_PLUS (>= 3 of 6 numbers match)
SECONDARY_EVENTS:     M4_PLUS, M5_PLUS, M6
WINNING_SPACE:        exact C(49,6) = 13,983,816 (never enumerated by this task)
REAL_DRAW_HISTORY:    NONE
PREDICTIVE / PRIZE / ROI CLAIM: NOT TESTED
DUPLICATE_TICKETS:    must be exactly 0 for every arm at every k (frozen invariant)
```

All four arms use identical `k` from the same ladder; no arm gets a
different exposure ladder.

## 4. The four arms

### A. `SIDON_REFERENCE` — `CYCLIC_SIDON_SHIFT_B649_V1` (existing, immutable)

`src/lottolab/research/cyclic_sidon_shift.py`. Base set
`{0,1,3,7,12,20}` in `Z_49`, verified Sidon, cyclic shifts, pairwise
overlap `<= 1` across all 49 shifts (exhaustively checked in
`tests/unit/test_cyclic_sidon_shift.py`, not rerun here). Already sealed
`OUTPERFORMS_RANDOM_COVERAGE` (`docs/research/matrix-native-results/diversification-coverage-b649-v1-report.md`).
No changes in this task.

### B. `NON_SIDON_LOW_OVERLAP` — `GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1` (new, this task)

`src/lottolab/research/greedy_min_overlap_constructor.py`
(`greedy_min_overlap_portfolio`). Deterministic, outcome-free, and
structurally unrelated to Sidon algebra: no modular arithmetic, no
pairwise-difference distinctness, no cyclic shift of any fixed base set.
Ticket 0 is the lexicographically first `draw_size`-subset of the pool.
Each subsequent ticket is the lexicographically first not-yet-used
candidate whose worst-case pairwise overlap against every already-chosen
ticket is smallest — plain greedy scan-and-keep-best, no backtracking, no
revisiting an earlier ticket (a strict nested-prefix portfolio holds by
construction, matching arm A's convention). A disclosed, not
special-cased, consequence of the rule: while an overlap-0 candidate still
exists (true for the first `pool_size // draw_size` tickets), the search
finds and keeps it and stops scanning immediately, so early tickets look
like sequential disjoint blocks purely because the general rule produces
that as its optimum, not because disjointness was hard-coded.

**Verified in this task (toy/synthetic pool sizes only — §7, §2):**
determinism, no duplicate tickets, correct ticket shape, exact zero
overlap for tickets within disjoint capacity, bounded (`<= 1`) overlap for
the first ticket forced beyond disjoint capacity in the tested toy case,
strict nested-prefix property, and generalization to a second
`(pool_size, draw_size)` shape with no code change
(`tests/unit/test_greedy_min_overlap_constructor.py`, 12 tests).

**Not done in this task:** invoking this constructor at `(49, 6)` — real
B649 scale — for any `k`, including the geometry-only metrics of §8. See
§9's rationale for why this is a stricter boundary than
`strategy-matrix-phase3-p638-diversification-native-design-r1.md` drew for
its own (much cheaper) base-set derivation.

### C. `BOUNDED_COVERAGE_OPTIMIZER` — `RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1` (new, this task)

`src/lottolab/research/bounded_coverage_optimizer.py`
(`restart_greedy_swap_search`, plus `exact_portfolio_coverage`, the
complete-enumeration exact evaluator it optimizes against — the same
enumerate-and-bitmask method
`tools/run_diversification_coverage_p638_zone1_v1.py` already uses for a
single fixed portfolio, generalized here to be called repeatedly against
arbitrary candidate portfolios during search). Full freeze in §6.

**Verified in this task (toy/synthetic sizes only):** determinism given a
seed, no duplicate tickets, correct ticket shape, reported coverage
matches independent recomputation, evaluation count stays within the
documented ceiling formula, every restart converges (a full swap pass with
no improving candidate) within the tested budget, more swap passes never
decreases the best final coverage, and generalization to a second
`(pool_size, draw_size)` shape
(`tests/unit/test_bounded_coverage_optimizer.py`, 10 tests).

### D. `RANDOM_EXPECTED_BASELINE` — existing, immutable

`src/lottolab/research/exact_coverage_baseline.py`
(`exact_random_portfolio_coverage`), reused verbatim, unmodified, exactly
as A/B649, T539, and P638 Zone-1 already do. No changes in this task.

## 5. Frontier terminology (frozen, kept distinct)

```text
BEST_FOUND_COVERAGE(k)      = max(Q_sidon(k), Q_B(k), Q_C(k))  -- whichever
                               arm's real-execution result is largest at k;
                               a *found* maximum among 3 disclosed arms,
                               nothing more
SIDON_FRONTIER_GAP(k)       = BEST_FOUND_COVERAGE(k) - Q_sidon(k)
GLOBAL_OPTIMUM_STATUS:        UNKNOWN, always, unless mathematically proven
```

`BEST_FOUND_COVERAGE` is never called globally optimal. `C(49,6) =
13,983,816` possible 6-subsets exist as candidate tickets for a
`k`-ticket portfolio; this design searches a vanishingly small, bounded,
disclosed fraction of that space (§6) and makes no claim to have found,
approached in a provable sense, or bounded the true maximum achievable
coverage.

## 6. Optimizer design freeze (arm C)

```text
SEARCH_SPACE:        k-ticket portfolios of distinct draw_size-subsets of
                      {1..pool_size}; no portfolio structure assumed
OBJECTIVE:            maximize exact_portfolio_coverage(pool_size,
                      draw_size, minimum_matches=3, portfolio) -- the real
                      M3_PLUS target, not a proxy
INITIALIZATION:       randomized greedy construction -- ticket i (i=0..k-1)
                      is the best-of-sample candidate by exact coverage,
                      sampled from a seeded RNG, appended to tickets 0..i-1
CANDIDATE_ORDERING:    each candidate batch is generated by
                      rng.sample(range(1, pool_size+1), draw_size), sorted
                      to a canonical ascending tuple, de-duplicated against
                      already-chosen and already-sampled tickets
TIE_BREAK:             lexicographically smaller candidate tuple wins ties
                      in both the construction and the local-search phase
LOCAL_SEARCH:          up to MAX_SWAP_PASSES full sweeps; each sweep tries,
                      for every ticket slot in a fixed left-to-right order,
                      a fresh same-sample steepest-ascent replacement
                      (evaluate the whole candidate_sample_size batch,
                      swap in the best one only if it strictly improves
                      total portfolio coverage)
STOPPING_RULE:         a restart stops early the first sweep that makes no
                      improving swap (`converged=True`); otherwise stops
                      after MAX_SWAP_PASSES sweeps regardless
RESTART_COUNT:         each restart independently seeded
                      random.Random(seed + restart_index); the best restart
                      by final coverage (ties: lexicographically smaller
                      portfolio) is returned
NESTED VS
  INDEPENDENT-PER-K:   INDEPENDENT-PER-K (decision, with rationale in §6.1)
MAX_EVALUATIONS:       per k, at most
                      restart_count * (k*candidate_sample_size +
                      max_swap_passes*k*(candidate_sample_size+1))
                      calls to exact_portfolio_coverage -- an exact,
                      code-enforced ceiling, not an approximation
                      (tests/unit/test_bounded_coverage_optimizer.py::
                      test_evaluations_used_is_within_the_documented_ceiling)
```

### 6.1 Nested vs. independent-per-k — decision

**Independent-per-k**, i.e. `restart_greedy_swap_search` is called once
per ladder rung with that rung's own `k`, with no carried-over portfolio
and no nested-prefix guarantee across `k` (unlike arms A and B). Rationale:
the research question is "what is the best coverage achievable *at a
given, fixed* `k`" — a per-`k` optimization target. Constraining the
search to extend a smaller-`k` portfolio (nesting) is a strictly harder,
more limited search than optimizing fresh at each `k`, so nesting would
systematically understate `BEST_FOUND_COVERAGE(k)` and bias
`SIDON_FRONTIER_GAP(k)` toward zero. The cost is that arm C's six ladder
rungs are six independent runs with no shared work — an explicit,
disclosed tradeoff, not an oversight.

### 6.2 Two frozen parameter sets — toy verification vs. a real-scale budget

`exact_portfolio_coverage` re-enumerates the complete `C(pool_size,
draw_size)` winning space on every call, so its cost is dominated by
`pool_size`/`draw_size`, not by anything the optimizer controls. This
makes a single parameter set a poor fit for both purposes at once; two are
frozen, both fully specified, neither invoked at real B649 scale by this
task:

```text
TOY_VERIFICATION_PARAMETERS (used by the committed test suite, §4):
  seed=20260815, restart_count=1-2, candidate_sample_size=6-10, max_swap_passes=1-4
  (exact values per test, chosen only for toy-pool speed, see the test file)

REAL_B649_SCALE_PARAMETERS (frozen for the later execution task, NOT run here):
  seed=20260815, restart_count=3, candidate_sample_size=40, max_swap_passes=2
```

`seed=20260815` is this design-lock date (2026-08-15) read as an integer,
disclosed for transparency, not tuned against any outcome — chosen before
any real-B649-scale evaluation exists to tune against.

### 6.3 Real B649-scale cost — why this budget is deliberately small (estimated, not measured)

`exact_portfolio_coverage`'s cost is dominated by re-enumerating
`C(pool_size, draw_size)` draws per call.
`strategy-matrix-phase3-p638-diversification-native-design-r1.md` §6
directly measured two real numbers this estimate reuses: bare enumeration
of `C(38,6) = 2,760,681` P638 draws took `0.1421s`, and a full 20-ticket
bitmask hit-counting pass over that same space took `5.11s`. Scaling both
linearly by `C(49,6)/C(38,6) ≈ 5.065` and by ticket count gives a rough
per-call cost model at real B649 scale of approximately
`0.72 + 1.26 * portfolio_size` seconds. Applying that model to the exact
evaluation-count formula above (`REAL_B649_SCALE_PARAMETERS`, summed
across the whole `k` ladder) projects to **multiple days of wall-clock
time**, overwhelmingly dominated by the `k=15` and `k=20` rungs. A
much smaller budget (`restart_count=1, candidate_sample_size=5,
max_swap_passes=1`) projects to roughly **2 hours total** across the whole
ladder by the same model, at the cost of a far thinner search (a sample of
5 out of `13,983,816` candidates per step, versus the toy tests' sample
fractions of several percent).

This is disclosed as a genuine open engineering question, not resolved by
picking a number and moving on: `REAL_B649_SCALE_PARAMETERS` above is
the disclosed, practical, bounded choice this document freezes, but
whether ~2 hours (thin search) or a multi-day run (richer search) is the
right tradeoff — or whether the later execution task should first build
an incremental evaluator instead of `exact_portfolio_coverage`'s full
re-enumeration — is listed as a remaining pre-lock issue in §12, not
decided unilaterally here. Nothing about this cost estimate required
seeing a real B649 result to compute: it is a projection from already-
measured enumeration cost, not from this frontier experiment's own
outcome, so it does not trigger `STOP_PHASE5_PRELOCK_DESIGN_UNRESOLVED`.

## 7. Toy/synthetic feasibility check performed in this task

Both constructors were exercised end-to-end at toy pool sizes only, never
at `(49, 6)`:

- **Arm B** (`tests/unit/test_greedy_min_overlap_constructor.py`): pool
  sizes 6, 8, and 10; draw sizes 2 and 3. All 12 tests pass in `0.12s`
  combined with arm C's suite (see below).
- **Arm C** (`tests/unit/test_bounded_coverage_optimizer.py`): pool sizes
  8 and 10; draw sizes 2 and 3. All 10 tests pass.
- **Separate, uncommitted, discarded mechanics/timing check** (not part of
  the test suite, not retained as a scientific result — same disclosure
  convention P638's own §6 used for its synthetic 20-ticket fixture): pool
  14, draw 4, `M2_PLUS` (`C(14,4) = 1001` draws), ladder `{1, 3, 5}`,
  `restart_count=3, candidate_sample_size=30, max_swap_passes=2`. Observed:

  ```text
  k=1: Q_C=0.310689  Q_random=0.310689  evaluations_used=183   converged: [True, True, True]
  k=3: Q_C=0.824176  Q_random=0.672918  evaluations_used=633   converged: [True, True, True]
  k=5: Q_C=0.976024  Q_random=0.845078  evaluations_used=1201  converged: [True, True, True]
  arm B (both k above, plus k=1,3,5): 0.0048s total
  arm C (all three k above): 0.7035s total
  ```

  This confirms the search mechanics run to completion, converge, respect
  the evaluation-count ceiling, and comfortably beat the closed-form random
  baseline **at this toy pool and this generous sample fraction** — it is
  not evidence about real B649 coverage, does not use the real B649 rule,
  and must not be read as predicting the real-scale result, especially
  since the real-scale budget (§6.3) necessarily samples a far smaller
  fraction of a far larger space.

```text
FEASIBILITY_RESULT:            PASS (both constructors run to completion,
                                deterministically, within their documented
                                evaluation ceilings, at toy scale)
MONTE_CARLO:                   NONE (arm C is a seeded bounded search over
                                sampled candidates, not a Monte Carlo
                                coverage estimate -- every coverage number
                                it computes is exact, via complete
                                enumeration, never simulated)
REAL_DRAW_HISTORY:             NOT_USED
REAL_B649_SCALE_EXECUTION:     NOT_RUN (§2, §6.3)
```

## 8. Geometry metrics (frozen definitions, not yet evaluated at real scale)

For a `k`-ticket portfolio over pool `{1..pool_size}`:

```text
max_pairwise_overlap      = max over all C(k,2) ticket pairs of |T_i ∩ T_j|
mean_pairwise_overlap     = mean over the same C(k,2) pairs
overlap_profile           = {overlap_size: pair_count} histogram over the
                             same C(k,2) pairs
number_use_counts         = {number: ticket_count_containing_it} for every
                             number 1..pool_size (0 if never used)
unique_number_coverage    = count of numbers with use_count >= 1
reuse_dispersion          = population standard deviation of
                             number_use_counts across all pool_size numbers
duplicate_tickets         = k - |set(portfolio)|  (frozen invariant: must be 0)
exact M3+/M4+/M5+/M6 coverage = Q_X(k) for minimum_matches in {3,4,5,6},
                             via exact_portfolio_coverage -- computed ONLY
                             in the later real-execution task, never here
```

No metric beyond this list may be added post-hoc once the real experiment
runs (no post-hoc metric expansion).

## 9. Why arm B's real-scale derivation is deferred too (not just its coverage)

`strategy-matrix-phase3-p638-diversification-native-design-r1.md` did
derive and structurally verify its real P638 base set at real scale in its
own design task — but that derivation is a backtracking search over at
most 38 residues, cheap regardless of pool size. `greedy_min_overlap_constructor`
is a different shape of cost: each of its `k` steps scans up to the full
remaining candidate space (`C(pool_size, draw_size)`) computing pairwise
overlaps, so at real B649 scale (`C(49,6) = 13,983,816`), deriving even
just the geometry (no coverage evaluation at all) for `k` up to 20 is a
nontrivial computation on the actual B649 problem instance, not a cheap
residue search. This document treats that as within the same "do not
execute at real B649 scale" boundary as arm C's coverage search, stricter
than P638 Phase 3 needed to be for its own, structurally cheaper,
constructor.

## 10. Estimands (frozen, per arm X in {B, C}, per k)

```text
Q_X(k)                       = exact M3_PLUS coverage of arm X's k-ticket portfolio
DELTA_RANDOM(k)               = Q_X(k) - Q_random_expected(k)
DELTA_SIDON(k)                 = Q_X(k) - Q_sidon(k)
RELATIVE_LIFT_VS_RANDOM(k)     = DELTA_RANDOM(k) / Q_random_expected(k)
SIDON_FRONTIER_GAP(k)          = BEST_FOUND_Q(k) - Q_sidon(k)   (§5)
```

## 11. Classification, frontier-nearness, and replication-eligibility rules (frozen, not applied here)

**Deterministic classification rule** (reused verbatim from A/B649,
T539, P638 Zone-1's own sealed convention, applied independently to arm B
and arm C):

```text
DELTA_RANDOM(k) > 0 for every k in the ladder  -> OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
DELTA_RANDOM(k) == 0 for every k               -> MATCHES_RANDOM_EXPECTED_COVERAGE
DELTA_RANDOM(k) < 0 for every k                -> UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE
otherwise                                       -> MIXED_BY_EXPOSURE
```

**Frontier-nearness rule.** Define
`FRONTIER_CAPTURE_RATIO(k) = DELTA_SIDON_TO_RANDOM(k) / DELTA_BEST_TO_RANDOM(k)`
where `DELTA_SIDON_TO_RANDOM(k) = Q_sidon(k) - Q_random_expected(k)` and
`DELTA_BEST_TO_RANDOM(k) = BEST_FOUND_COVERAGE(k) - Q_random_expected(k)`
— the fraction of the best-found improvement over random that Sidon-shift
already captures. `FRONTIER_NEARNESS_MARGIN = 0.90`.

```text
DELTA_BEST_TO_RANDOM(k) == 0  -> UNDEFINED_NO_IMPROVEMENT_FOUND (no arm beat random at this k)
FRONTIER_CAPTURE_RATIO(k) >= 0.90 for every defined k -> SIDON_NEAR_FRONTIER
SIDON_FRONTIER_GAP(k) <= 0 for every k                -> SIDON_AT_OR_ABOVE_BEST_FOUND
otherwise                                              -> SIDON_BELOW_FRONTIER_MARGIN
```

**Replication-eligibility rule** (answers future question 5, §12): a
challenger arm (B or C) is `ELIGIBLE_FOR_T539_P638_REPLICATION` only if
**all** of:

```text
(a) that arm's own DETERMINISTIC_CLASSIFICATION_RULE outcome is
    OUTPERFORMS_RANDOM_EXPECTED_COVERAGE across the full ladder (the same
    bar Sidon-shift itself met before being treated as canonical)
(b) SIDON_FRONTIER_GAP(k) > 0 for at least one k (replicating a challenger
    that never beats already-canonical Sidon-shift has no purpose)
(c) the arm's procedure is genuinely parametrized by (pool_size, draw_size)
    with no B649-specific tuned constant (both B and C satisfy this by
    construction -- neither module hard-codes 49 or 6 anywhere)
```

Otherwise `NOT_ELIGIBLE_FOR_REPLICATION`, with the failing condition
recorded.

## 12. Future decision questions (draft rules only, not applied)

1. Does non-Sidon low overlap (arm B) reproduce most of Sidon's gain? —
   Answered by `DELTA_SIDON(k)` for arm B across the ladder: consistently
   near 0 (or positive) → yes; consistently negative and large → no,
   overlap alone under-explains it.
2. Does bounded optimization (arm C) materially outperform Sidon? —
   Answered by arm C's own `DETERMINISTIC_CLASSIFICATION_RULE` against
   Sidon specifically (`DELTA_SIDON(k) > 0` for every k) plus
   `SIDON_FRONTIER_GAP(k)`'s magnitude, not just its sign.
3. How large is the Sidon frontier gap across k? — `SIDON_FRONTIER_GAP(k)`
   and `FRONTIER_CAPTURE_RATIO(k)` reported at every ladder rung, per §11.
4. Is reduced overlap associated with increased coverage? — Compare each
   arm's §8 `mean_pairwise_overlap(k)` against its own `Q_X(k)` across
   arms and across k; a descriptive association check, not a causal claim
   (n=4 arms is far too small for statistical inference).
5. Is the best-found constructor worth T539/P638 replication? — §11's
   replication-eligibility rule, applied to whichever of B or C is
   `BEST_FOUND` at each k.

`ECONOMIC / OPERATIONAL MEANINGFULNESS: OUT_OF_SCOPE` for all five, per
the packet's own instruction — none of these rules produce or require a
cost, ROI, or "worth playing" judgment.

## 13. Pre-lock decisions — resolved

```text
non-Sidon constructor:              RESOLVED -- GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 (§4.B)
optimizer family:                   RESOLVED -- RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1 (§4.C, §6)
exact search budget:                RESOLVED -- two frozen parameter sets (§6.2), real-scale
                                     cost implication disclosed as an open question (§6.3, §16)
nested vs independent-per-k:        RESOLVED -- independent-per-k (§6.1)
primary estimands:                  RESOLVED (§10)
frontier-nearness rule:             RESOLVED -- FRONTIER_CAPTURE_RATIO, margin 0.90 (§11)
deterministic classification rule:  RESOLVED -- reused verbatim from A/B649 (§11)
replication-eligibility rule:       RESOLVED (§11)
```

None of these required seeing a real B649 frontier result to resolve, so
`STOP_PHASE5_PRELOCK_DESIGN_UNRESOLVED` does not apply.

## 14. Scope boundary (frozen)

```text
PREDICTIVE_ADVANTAGE:                NOT_TESTED
PRIZE_VALUE_ADVANTAGE:                NOT_TESTED
ECONOMIC_OPTIMALITY:                  NOT_TESTED
T539_EXECUTION / P638_EXECUTION:      NOT_RUN
B649_FRONTIER_EXPERIMENT_EXECUTION:   NOT_RUN
MATRIX_RESULT_CELL:                   NOT_APPENDED (ledger untouched by design)
PRODUCTION / COHORT / PROSPECTIVE:    NONE
REAL_DATA_ACCESS:                     NONE
A / D MUTATION:                       NONE
B / C DEFINITION MUTATION MID-TASK:   NONE (frozen once written, §2)
```

## 15. What this task did and did not do

**Did**: derived and disclosed one deterministic, outcome-free, non-Sidon
low-overlap constructor (arm B) and one bounded, seeded, reproducible
coverage-search optimizer family (arm C); implemented both generically
(parametrized by pool/draw size, not tuned to B649); structurally verified
both at toy/synthetic scale (22 committed tests, all passing, plus one
discarded uncommitted mechanics/timing check); froze the exposure ladder,
events, geometry metrics, estimands, frontier terminology, frontier-
nearness rule, classification rule, and replication-eligibility rule;
estimated (not measured) real B649-scale computational cost from already-
measured P638 enumeration benchmarks and disclosed the resulting budget
tradeoff as an open question rather than resolving it unilaterally.

**Did not**: enumerate any part of the real `C(49,6) = 13,983,816` B649
winning space; invoke either new constructor at real B649 scale
(`pool_size=49, draw_size=6`) for any `k`, in committed code or in any
script run during this task; compute or retain any `Q_B(k)` or `Q_C(k)`
value for the real B649 rule; classify B649 under the frozen rules;
append a Strategy Matrix ledger cell; touch T539, P638, production, the
frontend/API, draw synchronization, or any historical draw data.

## 16. No-rescue statement

The constructor definitions (§4.B, §4.C), search-space/objective/
initialization/candidate-ordering/tie-break/stopping-rule freeze (§6),
geometry metrics (§8), estimands (§10), and every classification/
nearness/eligibility rule (§11) were fixed before any real-B649-scale
evaluation existed to see. The toy/synthetic feasibility numbers in §7
were computed after those freezes, changed nothing about them, and are
disclosed in full including the caveat that they overstate what the
real-scale thin-sample budget (§6.2, §6.3) is likely to achieve. The
real-scale cost estimate in §6.3 is derived from already-published P638
enumeration benchmarks, not from any result this task produced, and its
own open question (thin real-scale search vs. multi-day rich search vs.
building an incremental evaluator first) is left to the Owner rather than
picked silently.

## 17. Artifacts

```text
src/lottolab/research/greedy_min_overlap_constructor.py
src/lottolab/research/bounded_coverage_optimizer.py
tests/unit/test_greedy_min_overlap_constructor.py
tests/unit/test_bounded_coverage_optimizer.py
docs/research/strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md  (this file)
```

## 18. Next step

Return to Owner for explicit lock + execute authorization, and resolution
of the §6.3 real-scale search-budget tradeoff, before any `Q_B(k)` or
`Q_C(k)` value is computed against the real B649 constructor, a
classification is assigned, or the Strategy Matrix ledger is touched.
`FINAL_CLASSIFICATION: PHASE5_DIVERSIFICATION_CONSTRUCTOR_FRONTIER_READY_FOR_OWNER_REVIEW`.
