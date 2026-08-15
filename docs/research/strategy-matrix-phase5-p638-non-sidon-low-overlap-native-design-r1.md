# STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1 — design

Status: DESIGN ONLY — not locked, not executed ｜ 2026-08-15 ｜ Strategy
Matrix Phase 5, P638 Zone-1 native translation (third and last native
lottery in this replication chain)

This document answers the question the Owner packet posed: can
`GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1` — B649 Phase-5's non-Sidon,
deterministic, outcome-free low-overlap constructor (arm B, sealed
`SIDON_BELOW_FRONTIER_MARGIN`,
`docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-report.md`),
already natively replicated once into DAILY_539
(`GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1`, sealed
`T539_REPLICATION_SUPPORTED`) — be translated cleanly into POWER_LOTTO
Zone-1's native 6/38 structure without any B649- or T539-specific
tuning? It answers yes, for the same reason both prior translations did:
`greedy_min_overlap_portfolio`
(`src/lottolab/research/greedy_min_overlap_constructor.py`, unmodified
since its sole commit `971b97b` — confirmed via `git log` in this task,
not assumed) already takes `(pool_size, draw_size, ticket_count)` as
plain parameters and hardcodes neither `49`/`6` nor `39`/`5` anywhere.
**It does not invoke the constructor at real P638 Zone-1 scale
(`pool_size=38, draw_size=6`), compute any `Q_ARM_B(k)` value against
the real `C(38,6)` winning space, classify P638, or touch the Strategy
Matrix ledger or the cross-lottery research ledger.** That is deferred
to a separate, later lock-and-execute task, pending Owner authorization
— the same two-step pattern
`strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`
and `strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md`
both used.

This translation carries one live, disclosed doubt the T539 translation
did not have to face: P638 Zone-1's own Sidon reference
(`cyclic_sidon_shift_p638.py`) needed a **genuinely new constant** and a
**different search algorithm** (backtracking, not plain greedy) because
`pool_size=38` is even and `19 = 38/2` is its own negation mod 38 — a
real mathematical obstruction specific to POWER_LOTTO Zone-1, absent for
both B649 (odd, 49) and T539 (odd, 39). §5 addresses this doubt directly
rather than assuming by analogy that arm B is unaffected.

## 0. Identity

```text
TASK_ID:                 STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1
P638_VARIANT_ID:          GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1
HYPOTHESIS_FAMILY_ID:     DIVERSIFICATION
LOTTERY:                  POWER_LOTTO, ZONE_1 (6-of-38); ZONE_2 (1-of-8) OUT OF SCOPE
SOURCE_TYPE:               STRATEGY_MATRIX_NATIVE
REPLICATES:                GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 and
                            GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 (native
                            parameter substitution, not a copy of either — see §5)
BUILDS ON (canonical, immutable, not rerun):
  - DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 (sealed, SIDON_BELOW_FRONTIER_MARGIN,
    docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-report.md)
  - GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 (sealed, T539_REPLICATION_SUPPORTED,
    docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-report.md)
  - DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 (sealed, OUTPERFORMS_RANDOM_EXPECTED_COVERAGE,
    D_3(20) = +0.05962996, docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-report.md)
  - CYCLIC_SIDON_SHIFT_P638_ZONE1_V1 (existing, immutable,
    src/lottolab/research/cyclic_sidon_shift_p638.py)
PREREGISTRATION_LOCKED:   NO
P638_EXECUTION:            NOT_RUN
```

## 1. Research question

Can the deterministic, non-Sidon, low-overlap mechanism that exceeded
Sidon's own gain over random at every tested `k > 1` in both B649
(`arm_b_sidon_capture_ratio_primary_event`: 5.91x at `k=3` down to 1.64x
at `k=20`, never below 1x) and T539 (`T539_REPLICATION_SUPPORTED`, Q1/Q2/Q3
all PASS) be translated cleanly to POWER_LOTTO Zone-1's native 6/38
structure without B649- or T539-specific tuning? `PREDICTIVE_ADVANTAGE:
NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE: NOT_TESTED`. `ECONOMIC_OPTIMALITY:
NOT_TESTED`. This is not a test of future-number prediction, strategy
skill, prize value, economic ROI, optimal ticket count, or historical
draw bias, and it makes no claim that P638 Zone-1 arm B will in fact
outperform P638 Zone-1's own Sidon reference once actually run — only
that the translation itself is well-defined and requires no guessed
constant (§5's `STOP_P638_ARM_B_NATIVE_MAPPING_UNRESOLVED` check).

## 2. Boundaries (frozen)

```text
P638:                          DESIGN ONLY, this task
ZONE_2 (1-of-8):                OUT OF SCOPE ENTIRELY — no line of this task
                                reads POWER_LOTTO_RULE_CONTRACT.special_number_*
A (P638 ZONE-1 SIDON REFERENCE): NO MUTATION — CYCLIC_SIDON_SHIFT_P638_ZONE1_V1
                                (src/lottolab/research/cyclic_sidon_shift_p638.py)
                                stays exactly as sealed
B (SHARED GREEDY CONSTRUCTOR):  NO MUTATION — greedy_min_overlap_constructor.py
                                (src/lottolab/research/, frozen since 971b97b)
                                stays exactly as frozen; this task adds a new
                                P638-Zone-1-scoped module, never edits the shared one
C (RANDOM EXPECTED BASELINE):   NO MUTATION — exact_coverage_baseline.py stays
                                exactly as sealed
B649 ARM C (BOUNDED OPTIMIZER): OUT_OF_SCOPE per Owner packet — not
                                translated, not referenced beyond this line
DB / API / PROSPECTIVE:        NONE
STRATEGY CATALOG CHANGES:       NONE
HISTORICAL OUTCOMES:            NOT READ
MATRIX RESULT CELL:             NOT APPENDED (ledger untouched by design;
                                19 cells confirmed present at task start,
                                docs/research/cross_lottery_research_ledger_r1.json,
                                none named POWER_LOTTO constructor-frontier)
CROSS-LOTTERY RESEARCH LEDGER:  NOT APPENDED
REAL P638 ZONE-1 WINNING-SPACE
  ENUMERATION (`C(38,6) = 2,760,681`
  possible draws):               NOT ENUMERATED against arm B by this task
                                  (§9's descriptive Q_random computations are
                                  closed-form, not enumeration, and do not
                                  touch arm B — see §8)
CONSTRUCTOR TOOLKIT INVOCATION
  AT REAL P638 ZONE-1 SCALE
  (`pool_size=38, draw_size=6`):  NOT INVOKED by this task, in committed code
                                   or in any script run during this task —
                                   toy/synthetic sizes only, everywhere (§6,
                                   §11), mirroring the B649 Phase-5 and T539
                                   design boundaries exactly, for the identical
                                   reason: this constructor's cost is
                                   dominated by a full C(pool_size,draw_size)
                                   scan per forced ticket, not a cheap
                                   bounded/residue search
PRE-EXISTING UNCOMMITTED FILES
  DISCOVERED, NOT THIS TASK'S:    src/lottolab/research/cyclic_sidon_shift_p638_zone1.py,
                                   tools/b649_operational_prediction_loop.py,
                                   tests/unit/test_b649_operational_prediction_loop.py
                                   — all three were already untracked in the
                                   working tree before this task started (confirmed
                                   via `git status` at task start), are unrelated
                                   to this task's scope, and were read (the first)
                                   or left completely untouched (all three) — see §13
```

## 3. Contract (frozen, from the Owner packet)

```text
LOTTERY:                POWER_LOTTO Zone-1 (6-of-38; POWER_LOTTO_RULE_CONTRACT,
                         src/lottolab/domain/lottery_rules.py:
                         main_number_count=6, main_number_max=38,
                         special_number_count=1, special_number_min=1,
                         special_number_max=8 — Zone-2, out of scope)
K_LADDER:                {1, 3, 5, 10, 15, 20}  (same ladder as A/B649/T539)
PRIMARY_EVENT:           ZONE1_M3_PLUS (>= 3 of 6 numbers match)
SECONDARY_EVENTS:        ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6 (M6 is the
                         degenerate exact-match case for a 6-of-38 draw —
                         D_6(k) = k/2,760,681 for any fixed-size portfolio,
                         geometry-independent, already established by the
                         sealed P638 Zone-1 Sidon cell's own test suite;
                         noted here so the later execution task is not
                         surprised by a near-zero M6 delta, exactly as
                         T539 disclosed for its own M5)
WINNING_SPACE:           exact C(38,6) = 2,760,681 (not enumerated against
                         arm B by this task — §2)
REAL_DRAW_HISTORY:       NONE
PREDICTIVE / PRIZE / ROI CLAIM: NOT TESTED
DUPLICATE_TICKETS:       must be exactly 0 for every arm at every k (frozen
                         invariant, inherited unchanged from B649/T539/P638)
```

## 4. Comparators

### A. P638 Zone-1 Sidon reference — `CYCLIC_SIDON_SHIFT_P638_ZONE1_V1` (existing, immutable)

`src/lottolab/research/cyclic_sidon_shift_p638.py`. Base set `{0, 1, 3, 7,
17, 30}` in `Z_38`, independently verified Sidon (no pair differs by
exactly `19 = 38/2`), cyclic shifts, pairwise overlap `<= 1` across all 38
shifts (`C(38,2) = 703` pairs, exhaustively checked). Already sealed
`OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`
(`docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-report.md`,
`D_3(20) = +0.05962996`). No changes in this task. This is the one and
only P638 Zone-1 Sidon module this task treats as sealed — see §13 for a
separate, uncommitted, byte-different file discovered in the working
tree that is **not** this comparator and was not used or trusted as one.

### B. P638 Zone-1 native greedy low-overlap constructor — `GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1` (new, this task)

`src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py`
(`greedy_min_overlap_portfolio_p638_zone1`), a thin, unconditional
delegation to the shared, unmodified `greedy_min_overlap_portfolio(
pool_size=38, draw_size=6, ticket_count)`. See §5 for why no new
algorithm, search, or constant was needed — and why this constructor, unlike
comparator A, does not inherit P638 Zone-1's even-modulus obstruction.
Structurally verified in this task (wiring + constant provenance + a new
toy-scale `draw_size=6` generalization check at P638 Zone-1's own
remainder shape + a geometry-metric computability fixture) — never
invoked at `(38, 6)` itself, per §2.

### C. Exact random-expected baseline — existing, immutable

`src/lottolab/research/exact_coverage_baseline.py`
(`exact_random_portfolio_coverage`), reused verbatim, exactly as
A/B649/T539/P638 already do. No changes in this task. (Labeled `C` here
to match the Owner packet's own comparator list, which does not include
B649's bounded-optimizer arm.)

## 5. B649/T539-to-P638-Zone-1 mapping (the core deliverable)

`greedy_min_overlap_portfolio(pool_size, draw_size, ticket_count)`
(`src/lottolab/research/greedy_min_overlap_constructor.py`, unchanged
since its sole commit `971b97b`, re-confirmed via `git log
-- src/lottolab/research/greedy_min_overlap_constructor.py` in this task)
takes `pool_size` and `draw_size` as plain parameters. Reading the
committed source directly in this task (not just trusting the frozen
B649 or T539 design docs' own claims) confirms: the entire mechanism is
`itertools.combinations(range(1, pool_size + 1), draw_size)` plus a plain
set-intersection overlap check, and a targeted grep for the literals
`38`, `39`, and `49` inside the module found none in the function body —
the only match was inside the module's own docstring, describing what it
is *not* invoked at (real B649 scale), which is prose, not code.

```text
B649/T539_TO_P638_ZONE1_MAPPING:
  pool_size:     49 -> 39 -> 38   (POWER_LOTTO_RULE_CONTRACT.main_number_max)
  draw_size:      6 ->  5 ->  6   (POWER_LOTTO_RULE_CONTRACT.main_number_count)
  ticket_count:  unchanged parameter, same k ladder
  algorithm:      UNCHANGED — zero lines of greedy_min_overlap_constructor.py
                  differ between the B649, T539, and P638 Zone-1 instantiation;
                  only the two integers passed in change, and both come
                  directly from the existing, already-canonical
                  POWER_LOTTO_RULE_CONTRACT, not invented for this task
  UNRESOLVED_CONSTANTS: NONE
```

`STOP_P638_ARM_B_NATIVE_MAPPING_UNRESOLVED` does **not** apply: there is
no B649/T539 constant to translate, because arm B was never parametrized
by one in the first place — the same conclusion T539's own design task
reached, independently re-confirmed here by reading the unmodified source
directly rather than re-citing either prior doc's claim.

### 5.1 Why P638 Zone-1's even-modulus obstruction does not recur for arm B

This is the one question this translation cannot answer by analogy alone,
because it has already gone wrong once for a sibling constructor at this
exact `pool_size`. `cyclic_sidon_shift_p638.py`'s own docstring discloses
a genuine, provable obstruction: `pool_size=38` is even, `19 = 38/2` is
its own negation mod 38, so any Sidon base-set pair differing by exactly
19 collides — a case that never arises for B649 (odd, 49) or T539 (odd,
39), and that defeated plain greedy Sidon search, requiring backtracking
instead.

`greedy_min_overlap_portfolio` has **no modular or cyclic-shift structure
of any kind** for that obstruction to attach to:

```text
Sidon construction (comparator A):     candidates are integers mod pool_size;
                                        acceptance depends on pairwise
                                        DIFFERENCES mod pool_size; a
                                        "distance = pool_size/2" case is
                                        meaningful because two integers can
                                        be equidistant in both directions
                                        around a cycle of even length.

Greedy min-overlap constructor (arm B): candidates are literal draw_size-
                                        subsets of {1..pool_size}, enumerated
                                        by itertools.combinations in a fixed
                                        lexicographic order; acceptance
                                        depends only on |candidate ∩ prior
                                        ticket| (plain set intersection size).
                                        There is no shift, no residue, no
                                        "distance", and no modular arithmetic
                                        anywhere in this procedure for
                                        pool_size's parity to interact with.
```

The shared function's own internal guarantee (`assert best_candidate is
not None`) holds by a plain pigeonhole argument, independent of parity:
as long as `ticket_count <= math.comb(pool_size, draw_size)`, at least one
not-yet-used `draw_size`-subset always remains for the exhaustive
`itertools.combinations` scan to find, however large its worst-case
overlap score. Nothing about `pool_size` being even, or about `pool_size /
2` in particular, changes that argument. This is stated here as
`[Confirmed]` by direct source reading, not `[Inferred]` by analogy to the
Sidon case's own resolution.

**Toy-scale verification, not just argument.** §11 exercises the shared
constructor for the first time at `draw_size=6` (matching P638 Zone-1's
real draw size) on an even `pool_size=20`, chosen so that `pool_size %
draw_size == 2` — the exact same remainder P638 Zone-1 itself has (`38 %
6 == 2`) — specifically because "does P638 Zone-1's own pool/draw shape
misbehave for this constructor too" is a live question this task checks
rather than assumes clean. Result: no exception, no stall, correct ticket
shape, zero duplicates, full disjoint-block behavior for the first
`pool_size // draw_size` tickets, and — a genuine, disclosed, minor
quantitative difference from the T539/B649 toy tests' own numbers, not a
problem — the first ticket beyond disjoint capacity is forced to reuse 4
numbers (only 2 fresh numbers remain, `20 - 3*6 = 2`) spread across only 3
prior tickets, so the best *achievable* max-overlap-against-any-single-
prior-ticket is `ceil(4/3) = 2` by pigeonhole, not the `<= 1` bound the
existing toy tests happen to show for their own, different remainder (`10
% 3 == 1`). The greedy rule reaches exactly this theoretical value — the
mechanism is doing optimal work at this step, not degrading.

```text
EVEN_MODULUS_OBSTRUCTION_APPLIES_TO_ARM_B: NO — [Confirmed] by source
    reading (no modular structure exists to carry the obstruction) and by
    a toy-scale run at P638 Zone-1's own remainder shape (§11)
STOP_P638_ARM_B_NATIVE_MAPPING_UNRESOLVED: does NOT apply
```

## 6. Computational feasibility

**Frozen boundary:** the constructor is not invoked at `(pool_size=38,
draw_size=6)` anywhere in this task (§2). This section estimates, from
toy-scale measurements only, whether the later execution task needs a
fast-evaluator-style optimization the way B649 arm C did before it can
run — and, unlike T539's own equivalent section, can validate its cost
model against B649's real measurement **without a draw-size mismatch**,
since P638 Zone-1's own `draw_size=6` already equals B649's.

**Cost shape** (identical formula to the T539 design task, reused
verbatim — nothing P638-specific about the shape itself):

```text
COST_UNITS(pool_size, draw_size, k) = C(pool_size, draw_size)
    * sum(i for i in range(pool_size // draw_size, k))
```

**Measured (this task, toy scale only — `pool_size` in `{14, 16, 18, 20,
22}`, `draw_size=6` matching P638 Zone-1's own real draw size exactly,
`ticket_count=20`, never `pool_size=38`; via the actual shared,
unmodified `greedy_min_overlap_portfolio`, not a reimplementation):**

| pool_size | C(n,6) | disjoint capacity | k=20 wall-clock | rate (s/unit) |
|---:|---:|---:|---:|---:|
| 14 | 3,003 | 2 | 0.1691s | 2.9788e-07 |
| 16 | 8,008 | 2 | 0.4354s | 2.8769e-07 |
| 18 | 18,564 | 3 | 1.0466s | 3.0150e-07 |
| 20 | 38,760 | 3 | 2.1118s | 2.9135e-07 |
| 22 | 74,613 | 3 | 4.0565s | 2.9073e-07 |

Fitted cost-per-unit is tight across all five points: `2.877e-7` to
`3.015e-7` seconds/unit (average `2.9383e-7`), consistent with a
pool-size-independent per-candidate-visit cost.

**Cross-validation against a real measurement, same draw size (a
tighter basis than T539's own cross-draw-size check).** Applying this
toy-fit model (calibrated only on `draw_size=6` toy pools, never on
`pool_size=49` or `38`) to B649's real parameters (`pool_size=49,
draw_size=6, k=20`, cost_units=2,265,378,192) predicts **665.6s**. The
sealed B649 result reports arm B's actual real-scale runtime as **774.5s**
(`diversification-constructor-frontier-b649-v1-report.md`, "Runtime and
resources") — the model lands within a **1.1635x** correction factor of a
real, independently measured number, using the *same* `draw_size=6` for
both the toy fit and the real validation point (T539's own equivalent
check had to cross a `draw_size` 5-vs-6 mismatch; this one does not).

```text
P638_ZONE1_COST_UNITS(pool=38, draw=6, k=20) = 483,119,175
RAW_MODEL_ESTIMATE:                             141.96s
B649-CROSS-VALIDATION-CORRECTED ESTIMATE:       165.17s (applying the
                                                 observed 1.1635x
                                                 under-prediction ratio
                                                 from the B649 check above)
NON_LOAD_BEARING_RUNTIME_ESTIMATE:              TRUE -- both the 1.1635x
                                                 factor and the
                                                 141.96s/165.17s figures
                                                 are engineering
                                                 feasibility estimates
                                                 only (used solely to
                                                 decide whether a
                                                 fast-evaluator
                                                 optimization is needed
                                                 before running arm B).
                                                 Neither feeds Q_ARM_B(k),
                                                 DELTA_RANDOM(k),
                                                 DELTA_SIDON(k), any
                                                 classification, or the
                                                 locked preregistration's
                                                 LOCKED_PARAMETERS -- the
                                                 real lock-and-execute
                                                 task measures actual
                                                 wall-clock time directly
                                                 and does not read this
                                                 estimate.
```

This toy-scale measurement and cross-validation was run in this task as a
separate, uncommitted, discarded mechanics/timing check (not part of the
committed test suite, not retained as a scientific result) — the same
disclosure convention the B649 Phase-5 design doc's own §7 and the P638
Zone-1 diversification-coverage design task's own §6 already used for
comparable checks.

Because `greedy_min_overlap_portfolio` is a strict nested prefix (§4.B —
unlike B649 arm C, which reruns independently per `k`), **one single call
at `ticket_count=20` yields every `k` in `{1,3,5,10,15,20}` as a free
slice** — the ladder does not multiply this cost.

```text
COMPUTATIONAL_FEASIBILITY:  FEASIBLE, estimated ~165s (~2.75 minutes) for
                             the full k-ladder construction at real P638
                             Zone-1 scale (not measured — §2's boundary is
                             not crossed by this estimate) -- notably
                             cheaper than B649's own real 774.5s, consistent
                             with C(38,6) = 2,760,681 being ~5.07x smaller
                             than C(49,6) = 13,983,816. No fast-evaluator-
                             style optimization is anticipated to be
                             necessary for arm B's own construction cost.
                             Coverage evaluation on top of the built
                             portfolio reuses the already-proven-feasible
                             P638 Zone-1 winning-space method (bare
                             enumeration of C(38,6) measured at 0.1421s by
                             the sealed P638 Zone-1 diversification-coverage
                             design task) -- no new evaluator work
                             anticipated.
MONTE_CARLO:                 NONE
REAL_DRAW_HISTORY:           NOT_USED
REAL_P638_ZONE1_SCALE_EXECUTION: NOT_RUN (§2)
```

## 7. Geometry metrics (frozen, reused verbatim from the Owner packet's own GEOMETRY METRICS list, identical in kind to B649 Phase-5 §8 and T539 §7)

```text
max_pairwise_overlap      = max over all C(k,2) ticket pairs of |T_i ∩ T_j|
mean_pairwise_overlap     = mean over the same C(k,2) pairs
overlap_profile           = {overlap_size: pair_count} histogram
number_use_counts         = {number: ticket_count_containing_it} for 1..38
unique_number_coverage    = count of numbers with use_count >= 1 (max 38)
reuse_dispersion          = population standard deviation of number_use_counts
duplicate_tickets         = k - |set(portfolio)|  (frozen invariant: must be 0)
exact ZONE1_M3+/M4+/M5+/M6 coverage = Q_X(k), via the existing exact-coverage
                             evaluator — computed ONLY in the later
                             real-execution task, never here
```

No metric beyond this list may be added post-hoc once the real P638
Zone-1 experiment runs (no post-hoc metric expansion, inherited unchanged
from B649 Phase-5 and T539).

**One disclosed, testable prediction for the later execution task, not a
result:** B649's real arm-B portfolio never used number 49 (the pool's
highest number) at any tested `k`, a purely structural consequence of the
lexicographic tie-break, not a special case (sealed B649 report, Q4). If
the same structural bias holds for P638 Zone-1, the later execution
task's arm-B portfolio may similarly never use number 38. This is
disclosed in advance so it is read as an anticipated structural property
if observed, not a new post-hoc metric invented after seeing the P638
result — exactly the same disclosure T539's own design doc made for
number 39.

**Toy-scale geometry-computability check performed in this task
(`tests/unit/test_greedy_min_overlap_constructor_p638_zone1.py::
test_geometry_metrics_are_computable_on_a_toy_p638_zone1_shaped_portfolio`):**
confirms all six metric definitions above are well-defined and computable
against a toy portfolio of this constructor's own output shape
(`pool_size=20, draw_size=6`) — not a claim about real P638 Zone-1
geometry, which this task never builds.

## 8. Estimands (frozen, from the Owner packet's own EXACT EVALUATION CONTRACT)

```text
Q_ARM_B(k)            = exact ZONE1_M3_PLUS coverage of P638 Zone-1 arm B's
                         k-ticket portfolio (computed ONLY in the later
                         execution task)
Q_SIDON(k)             = exact ZONE1_M3_PLUS coverage of CYCLIC_SIDON_SHIFT_P638_ZONE1_V1
                         (already sealed, quoted in §9)
Q_RANDOM_EXPECTED(k)   = exact_random_portfolio_coverage(38, 6, 3, k)
                         (closed-form, independently recomputed and
                         verified in this task — §9)
DELTA_RANDOM(k)        = Q_ARM_B(k) - Q_RANDOM_EXPECTED(k)
DELTA_SIDON(k)         = Q_ARM_B(k) - Q_SIDON(k)
```

No Monte Carlo, per the Owner packet. Both `DELTA_RANDOM` and
`DELTA_SIDON` require `Q_ARM_B(k)`, which is not computed by this task.

## 9. Exact baseline status (computed in this task — closed-form, not enumeration)

`exact_coverage_baseline.py`'s `qualifying_ticket_count` and
`exact_random_portfolio_coverage` are reused verbatim and already
confirmed to generalize to `(pool=38, draw=6)` with no code changes by
the sealed `DIVERSIFICATION_COVERAGE_P638_ZONE1_V1` cell. This task
independently re-verified rather than re-quoted the sealed report's
numbers (`python3`, this task, via the unmodified `exact_coverage_baseline.py`):

```text
N = C(38,6) = 2,760,681
K(3) = 106,833   (3.869806% of draws)
K(4) = 7,633     (0.276490% of draws)
K(5) = 193       (0.006991% of draws)
K(6) = 1         (0.000036% of draws — the degenerate exact-match case, §3)

Q_random_M3(k):
  k= 1: 0.03869806   k= 3: 0.11165955   k= 5: 0.17908342
  k=10: 0.32609621   k=15: 0.44678160   k=20: 0.54585434

sanity check Q_random_3(1) == K(3)/N exactly: PASS
```

These independently recomputed values match the already-sealed P638
Zone-1 Sidon report's own `q_random` column exactly (cross-checked
against `docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-result.json`
in this task), confirming the shared baseline module's behavior has not
drifted. `Q_SIDON(k)` for the same ladder (already sealed, quoted for
reference from that same result file, not recomputed): `0.03869806,
0.11285730, 0.18280852, 0.34421978, 0.48421748, 0.60548430` (`k=1, 3, 5,
10, 15, 20`) — and `0.60548430 - 0.54585434 = 0.05962996`, matching the
sealed cell's own headline `D_3(20)` exactly.

```text
EXACT_BASELINE_STATUS: REUSED_UNMODIFIED_AND_RE-VERIFIED (Q_random_M3
                        ladder + K(3..6) independently recomputed via the
                        existing, unmodified exact_coverage_baseline.py in
                        this task, and cross-checked byte-for-byte against
                        the sealed result.json; Q_ARM_B(k) NOT computed —
                        requires the arm-B portfolio, deferred per §2)
```

## 10. Classification and replication rules (frozen, not applied here)

Answering the Owner packet's three `FUTURE DECISION RULE` questions as
deterministic, mechanically-applicable rules — none of these are applied
in this task, since `Q_ARM_B(k)` does not yet exist.

**Q1 — does P638 Zone-1 arm B outperform random expected coverage at
every `k > 1`?**

```text
DELTA_RANDOM(k) > 0 for every k in {3,5,10,15,20}  -> P638_ARM_B_OUTPERFORMS_RANDOM
DELTA_RANDOM(k) <= 0 for every k in {3,5,10,15,20} -> P638_ARM_B_DOES_NOT_OUTPERFORM_RANDOM
otherwise                                           -> P638_ARM_B_MIXED_BY_EXPOSURE
```

**Q2 — does it exceed P638 Zone-1 Sidon's own gain over random?**

```text
DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}  -> P638_ARM_B_EXCEEDS_SIDON_GAIN
DELTA_SIDON(k) <= 0 for every k in {3,5,10,15,20} -> P638_ARM_B_DOES_NOT_EXCEED_SIDON_GAIN
otherwise                                          -> P638_ARM_B_MIXED_VS_SIDON
```

**Q3 — is direction consistent with B649 and T539 arm B?** Both prior
sealed results (not rerun here, cited as given): B649's arm B has
`DELTA_SIDON(k) > 0` at **every** tested `k > 1`
(`arm_b_sidon_capture_ratio_primary_event` 5.91x/6.08x/4.74x/2.50x/1.64x
at `k=3/5/10/15/20`); T539's arm B is
`T539_ARM_B_EXCEEDS_SIDON_GAIN` (Q1/Q2/Q3 all PASS,
`T539_REPLICATION_SUPPORTED`,
`docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-report.md`).

```text
P638 Zone-1's Q2 classification == P638_ARM_B_EXCEEDS_SIDON_GAIN -> CONSISTENT_WITH_B649_AND_T539
otherwise                                                          -> DIRECTION_INCONSISTENT_WITH_B649_AND_T539
                                                                       (disclosed, not treated as a
                                                                       failure of the P638 result —
                                                                       cross-lottery divergence is a
                                                                       legitimate outcome, matching
                                                                       the Sidon cell's own "not
                                                                       pooled into a single numerical
                                                                       estimate" convention)
```

**Replication-closure note.** Unlike B649 (which named T539 and P638 as
future replication targets) and T539 (which named a possible future P638
translation), P638 Zone-1 is the last of the three native lottery
structures this repository currently supports (BIG_LOTTO, DAILY_539,
POWER_LOTTO Zone-1). There is no fourth native lottery for this
particular arm-B translation chain to extend to next; a future
`P638_REPLICATION_SUPPORTED`-equivalent classification (once actually
executed) would **close** the three-lottery arm-B replication chain, not
open a new one. Zone-2 (1-of-8) remains a wholly separate, unresolved
design dimension, out of scope here as it was for the sealed P638 Zone-1
Sidon and diversification-coverage cells.

```text
CLASSIFICATION_RULE:  Q1/Q2 above (P638_ARM_B_OUTPERFORMS_RANDOM /
                       P638_ARM_B_EXCEEDS_SIDON_GAIN, the same
                       DELTA_RANDOM/DELTA_SIDON sign-across-ladder shape
                       as every prior Strategy Matrix native cell)
REPLICATION_RULE:      Q3 (B649-and-T539 direction-consistency); no
                       further native-lottery replication target exists
                       beyond P638 Zone-1 for this arm-B chain
```

## 11. Toy-scale structural verification performed in this task

`tests/unit/test_greedy_min_overlap_constructor_p638_zone1.py` (8 tests):

1. `POOL_SIZE == 38` and `DRAW_SIZE == 6` match
   `POWER_LOTTO_RULE_CONTRACT.main_number_max` /
   `.main_number_count` exactly (no transcription error, no guessing).
2. `(POOL_SIZE, DRAW_SIZE) == (38, 6)`, guarding against an accidental
   copy-paste of B649's `(49, 6)` or T539's `(39, 5)`.
3. The P638 Zone-1 wrapper delegates to the *exact* shared, unmodified
   `greedy_min_overlap_portfolio` function object (identity check — no
   local copy, no reimplementation, nothing shadowed).
4. The wrapper's call is proven to pass exactly `(38, 6, ticket_count)`
   through, via `monkeypatch` substituting the shared function with a
   call-recording stub, for two different `ticket_count` values — this
   proves the wiring is exactly right **without ever invoking the real
   constructor at `(38, 6)`** (§2's boundary), by composing two
   already-true facts: the shared function is already proven
   generic/deterministic/duplicate-free at toy scale (existing,
   unmodified `test_greedy_min_overlap_constructor.py`), and this wrapper
   is now proven to call it with exactly P638 Zone-1's own parameters —
   so the wrapper is deterministic and duplicate-free *by substitution*,
   without executing at real scale.
5. A new toy-scale generalization check on the *shared* (unmodified)
   constructor at `draw_size=6` for the first time (the existing suite
   only covers `draw_size` 2, 3, and T539's own 5) — `pool_size=20`,
   deliberately chosen so `pool_size % draw_size == 2`, matching P638
   Zone-1's own remainder (`38 % 6 == 2`) exactly, per §5.1's reasoning.
   Confirms disjoint-block behavior for the first 3 tickets, correct
   ticket shape/no duplicates, and — the theoretically correct, derived
   value, not an assumed one — a max-overlap of exactly `2` (not `1`) for
   the first ticket beyond disjoint capacity, matching the pigeonhole
   bound `ceil(4/3)` exactly (§5.1).
6. A geometry-metric computability fixture: all six frozen geometry
   definitions (§7) computed inline against the same toy portfolio and
   checked for internal consistency (duplicate count is 0, unique
   coverage `<= pool_size`, overlap histogram sums to `C(k,2)`, dispersion
   non-negative, mean `<=` max) — confirms the metric definitions are
   well-formed and computable, not a claim about real P638 Zone-1
   geometry.

```text
FEASIBILITY_RESULT:   PASS (wiring correct, constants provenance-checked,
                       shared constructor generalizes to draw_size=6 at
                       toy scale including at P638 Zone-1's own remainder
                       shape, geometry metrics computable)
```

## 12. Pre-lock decisions — resolved

```text
constructor translation:            RESOLVED — direct parameter substitution,
                                     no new algorithm (§5)
unresolved B649/T539 constants:     RESOLVED — NONE exist (§5)
even-modulus obstruction concern:   RESOLVED — does not apply to arm B;
                                     confirmed by source reading and a
                                     toy-scale check at P638 Zone-1's own
                                     remainder shape (§5.1, §11)
computational feasibility:          RESOLVED — estimated feasible, ~165s
                                     for the full k-ladder, cross-validated
                                     against a real B649 measurement at the
                                     same draw_size (§6)
geometry metric definitions:        RESOLVED — reused verbatim from the
                                     Owner packet / B649 Phase-5 §8 (§7);
                                     computability confirmed by fixture (§11)
estimands:                           RESOLVED (§8)
exact baseline generalization:       RESOLVED — re-verified against the
                                     sealed result.json, not just re-quoted (§9)
classification rule (Q1/Q2):        RESOLVED (§10)
B649/T539 direction-consistency
  rule (Q3):                         RESOLVED (§10)
replication-closure note:            RESOLVED — P638 Zone-1 is the last of
                                     three native lotteries for this chain (§10)
```

## 13. Remaining pre-lock issues (not resolved here, by design)

1. **Which of Q1/Q2's outcomes will actually occur is unknown** — this
   design task makes no prediction stronger than "the mechanism ported
   cleanly and both prior sealed results make a positive outcome
   plausible," consistent with `PREDICTIVE / PRIZE / ROI CLAIM:
   NOT_TESTED`.
2. **Whether the later execution task should build a fast evaluator
   before running** — §6 estimates this is *unnecessary* (P638 Zone-1's
   estimated ~165s is well under B649's real 774.5s), but that estimate is
   not a measurement, and the Owner may still prefer to measure before
   committing compute.
3. **The correction factor in §6 (1.1635x) is derived from a single
   cross-lottery data point (B649)** — a real P638 Zone-1-scale
   measurement, once authorized, would supersede it rather than confirm
   or refute a multi-point trend. (This factor's basis is somewhat
   stronger than T539's own 1.145x, since it required no cross-draw-size
   adjustment — both the toy fit and the B649 validation point use
   `draw_size=6` — but it remains a single data point.)
4. **A pre-existing, uncommitted, byte-different duplicate of the P638
   Zone-1 Sidon module was discovered in the working tree**
   (`src/lottolab/research/cyclic_sidon_shift_p638_zone1.py`) — same base
   set `(0, 1, 3, 7, 17, 30)` and `POOL_SIZE = 38`, but a separate file
   from the committed, sealed `cyclic_sidon_shift_p638.py` this design
   relies on as comparator A. It was already untracked before this task
   started (confirmed via `git status`), is not this task's to author,
   resolve, or delete, and was not committed, mutated, or relied upon as
   an authoritative comparator by this task. Flagged here as a repository
   hygiene question for the Owner — likely leftover, superseded output
   from an earlier exploratory session — not a defect in this design.
   Two other unrelated untracked files
   (`tools/b649_operational_prediction_loop.py`,
   `tests/unit/test_b649_operational_prediction_loop.py`) were also
   present at task start and were left completely untouched.

```text
STOP_PHASE5_PRELOCK_DESIGN_UNRESOLVED: does NOT apply — none of the four
    items above block writing or reading this document; items 1-3 are open
    empirical questions for the *next* task, and item 4 is an out-of-scope
    repository-hygiene observation, not a defect in this one.
```

## 14. Scope boundary (frozen)

```text
PREDICTIVE_ADVANTAGE:                NOT_TESTED
PRIZE_VALUE_ADVANTAGE:                NOT_TESTED
ECONOMIC_OPTIMALITY:                  NOT_TESTED
P638_EXECUTION:                       NOT_RUN
ZONE_2_ALLOCATION:                    NOT_TESTED, NOT_DESIGNED
MATRIX_RESULT_CELL:                   NOT_APPENDED
CROSS_LOTTERY_RESEARCH_LEDGER:        NOT_APPENDED
PRODUCTION / COHORT / PROSPECTIVE:    NONE
REAL_DATA_ACCESS:                     NONE
A / C MUTATION:                       NONE
B DEFINITION MUTATION MID-TASK:       NONE (frozen once written, §2)
B649 ARM C / BOUNDED OPTIMIZER:       OUT_OF_SCOPE, not translated
```

## 15. What this task did and did not do

**Did:** located and read the exact, unmodified shared arm-B source
(`greedy_min_overlap_constructor.py`), confirmed via `git log` it has had
exactly one commit (`971b97b`) since creation, and confirmed by direct
inspection (not by re-citing either frozen design doc alone) that it
hardcodes no B649- or T539-specific constant; located and read the
committed, sealed P638 Zone-1 Sidon module
(`cyclic_sidon_shift_p638.py`) and its even-modulus obstruction
disclosure, and reasoned through — then toy-verified — why that
obstruction has no analogue for arm B; wrote a minimal, unconditional
P638 Zone-1 wrapper module and structurally verified its wiring via
monkeypatching (proving correctness without invoking the real constructor
at `(38,6)`); added one new toy-scale `draw_size=6` generalization test
on the shared, already-frozen constructor at P638 Zone-1's own remainder
shape, including a pigeonhole-derived (not assumed) overlap bound; added
one geometry-metric computability fixture; independently re-verified (not
re-quoted) P638 Zone-1's `K(3..6)` and `Q_random_M3` ladder via the
existing, unmodified `exact_coverage_baseline.py`, cross-checked against
the sealed result JSON; measured real, toy-scale wall-clock timings at
five `draw_size=6` pool sizes (14/16/18/20/22, all far below 38), fit a
cost model from them, and cross-validated that model against B649's own
real, measured arm-B runtime (774.5s, same `draw_size=6`, no cross-size
adjustment needed) before applying it to estimate P638 Zone-1's real-scale
feasibility (~165s); froze the geometry metrics, estimands, classification
rule, direction-consistency rule, and a replication-closure note; verified
the shared constructor + P638 Zone-1 wrapper + existing P638 Zone-1
diversification-coverage test suites (28 tests total) plus the 8 new tests
all pass together; discovered and disclosed a pre-existing, uncommitted,
unrelated duplicate Sidon file and two other unrelated untracked files,
none of which this task touched, committed, or relied upon.

**Did not:** invoke `greedy_min_overlap_portfolio` (directly or via the
new wrapper) at `(pool_size=38, draw_size=6)` for any `k`, in committed
code or in any script run during this task; compute or retain any
`Q_ARM_B(k)` value for the real P638 Zone-1 rule; enumerate any part of
the real `C(38,6) = 2,760,681` P638 Zone-1 winning space against arm B;
classify P638 Zone-1 under the frozen rules in §10; append a Strategy
Matrix ledger cell or the cross-lottery research ledger; touch Zone-2,
production, the frontend/API, draw synchronization, historical draw data,
B649/T539's own sealed arm B result files, or the pre-existing untracked
files discovered in the working tree.

## 16. No-rescue statement

The mapping (§5), the even-modulus non-applicability argument (§5.1), the
boundary (§2), the feasibility estimate (§6), the geometry metric
definitions (§7), the estimands (§8), and every classification /
direction-consistency / replication-closure rule (§10) were fixed by
reading already-existing, already-frozen code and already-sealed results
— none of them required seeing a real P638 Zone-1 arm-B result to write,
because no such result exists yet. The toy-scale measurements in §6 and
§11 were computed after the mapping was already established as trivial
(§5) and changed nothing about it; they exist only to ground the
feasibility estimate and prove the wrapper's wiring and the even-modulus
non-applicability argument, and are disclosed in full including the one
place a real number (B649's 774.5s) was used to correct a toy-only
projection.

## 17. Artifacts

```text
src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py
tests/unit/test_greedy_min_overlap_constructor_p638_zone1.py
docs/research/strategy-matrix-phase5-p638-non-sidon-low-overlap-native-design-r1.md  (this file)
docs/research/greedy-min-overlap-constructor-p638-zone1-v1-preregistration-draft.md
```

## 18. Next step

Return to Owner for explicit lock + execute authorization before any
`Q_ARM_B(k)` value is computed against the real P638 Zone-1 constructor, a
classification is assigned, or the Strategy Matrix ledger (or
cross-lottery research ledger) is touched. Executing this translation
would close the three-native-lottery arm-B replication chain begun by
B649 Phase 5 (§10).
`FINAL_CLASSIFICATION: P638_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_READY_FOR_OWNER_REVIEW`.
