# DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 — native design

Status: DESIGN ONLY — not locked, not executed ｜ 2026-08-14 ｜ Strategy Matrix Phase 3

This document answers one question: can the B649/T539 low-overlap
portfolio-geometry mechanism be translated cleanly into a native POWER_LOTTO
Zone-1 6-of-38 contract suitable for a later exact combinatorial
replication? It derives and verifies the constructor and the baseline math.
**It does not run the P638 experiment, classify P638, or touch the Strategy
Matrix ledger.** That is explicitly deferred to a separate, later
lock-and-execute task, pending Owner authorization.

## 0. Identity

```text
TASK_ID:                    STRATEGY_MATRIX_PHASE3_P638_DIVERSIFICATION_NATIVE_DESIGN_R1
PLANNED_VARIANT_ID:         DIVERSIFICATION_COVERAGE_P638_ZONE1_V1
HYPOTHESIS_FAMILY_ID:       DIVERSIFICATION
LOTTERY:                    POWER_LOTTO
GAME_COMPONENT:             ZONE_1_ONLY (6-of-38 main numbers)
SOURCE_TYPE:                 STRATEGY_MATRIX_NATIVE
REPLICATES:                  DIVERSIFICATION_COVERAGE_B649_V1 and
                              DIVERSIFICATION_COVERAGE_T539_V1 (native
                              reconstruction, not a copy of either base set)
ZONE_2_ALLOCATION:           NOT_TESTED (out of scope, see §2)
```

Zone-1 rule (`main_number_count=6, main_number_min=1, main_number_max=38`)
is `POWER_LOTTO_RULE_CONTRACT` in
`src/lottolab/domain/lottery_rules.py` (`contract_version =
"2026-08-04.legacy-import-r1"`).

## 1. Research question (same claim as B649/T539, frozen for future lock)

At a fixed ticket count `k`, does a preregistered deterministic
portfolio-geometry rule increase exact `M3_PLUS` main-number winning-space
coverage relative to `k` uniformly random distinct Zone-1 tickets' expected
coverage? `PREDICTIVE_ADVANTAGE: NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE:
NOT_TESTED`. `ECONOMIC_OPTIMALITY: NOT_TESTED`. This is not a test of
future-number prediction, strategy skill, prize value, economic ROI,
optimal ticket count, or historical draw bias.

## 2. Zone-2 boundary (deferred, not designed here)

P638's Zone-2 (1-of-8) introduces an independent
allocation/full-ticket-structure mechanism that would confound this
replication if mixed in now. `ZONE_2_ALLOCATION: NOT_TESTED`.
`FULL_TICKET_DIVERSIFICATION: NOT_TESTED`. A possible later
`DIVERSIFICATION_FULL_TICKET_P638_V2` could study Zone-1 low-overlap
geometry × Zone-2 allocation/cycling geometry together — not predesigned
beyond this one line, and not authorized by this task.

## 3. Exposure ladder and events (frozen, unchanged from B649/T539)

```text
EXPOSURE_LADDER:              [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:                 ZONE1_M3_PLUS (>= 3 of 6 Zone-1 main numbers match)
SECONDARY_DESCRIPTIVE_EVENTS:  ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6
PRIZE_VALUE_CLAIM:             NONE
OFFICIAL_ANY_PRIZE_CLAIM:      NONE
```

Secondary events may be computed in the later execution task but cannot
alter the primary `M3_PLUS` classification. `P_1 ⊂ P_3 ⊂ P_5 ⊂ P_10 ⊂ P_15
⊂ P_20` holds by construction (see §4) — no offset tuning, no k-dependent
reorder, no post-k special rule, no historical or real-outcome information
anywhere in this design.

## 4. Portfolio constructor — `CYCLIC_SIDON_SHIFT_P638_ZONE1_V1` (derived and verified in this task)

**Base set in `Z_38` (0-indexed): `{0, 1, 3, 7, 17, 30}`.**
`T_0` (1-based, ascending) = `{1, 2, 4, 8, 18, 31}`.
Implementation: `src/lottolab/research/cyclic_sidon_shift_p638.py`. Tests:
`tests/unit/test_cyclic_sidon_shift_p638.py` (14 tests).

### 4.1 Why this needed more than the B649/T539 procedure, disclosed in full

The same plain greedy search used verbatim for B649 (mod 49) and T539 (mod
39) — start from `{0}`; keep the smallest not-yet-included residue whenever
it introduces no duplicate ordered pairwise difference with the current
set; stop at `target_size` — was tried first, run independently for
modulus 38 (`greedy_sidon_base(38, 6)` in the committed module). It
reproduces `{0, 1, 3, 7, 12}` for the first five elements — identical to
T539's complete base set, for the same reason T539's own docstring already
discloses for its own coincidence with B649's prefix: neither search has
yet needed to diverge while every difference involved stays well under the
smaller modulus. It then **exhausts every remaining residue (13..37)
without finding a valid sixth element.**

This is a real, provable obstruction, not a search-quality accident.
POWER_LOTTO Zone-1's pool size, 38, is **even** — unlike 49 and 39, both
odd. `19 = 38/2` is its own negation mod 38 (`-19 mod 38 == 19`). Any pair
of base elements differing by exactly 19 therefore yields the *same*
signed difference from both of its two orderings, where a genuine Sidon
set needs two distinct values there. Independent of that
difference-counting framing, such a pair provably forces a pairwise
cyclic-shift intersection of exactly 2 at shift-distance 19: if elements
`a` and `b` of the base differ by 19, then for any shift `i`, ticket `T_i`
and `T_{i+19}` each contain both `a+i` and `b+i` in swapped roles
simultaneously (`a+i ≡ b+(i+19)` and `b+i ≡ a+(i+19)` both hold whenever
`a-b ≡ 19`), giving `|T_i ∩ T_{i+19}| = 2`. Odd moduli have no nonzero
element equal to its own negation, so this case never arose for B649 or
T539 — confirmed here by re-running the identical greedy procedure against
pool sizes 49 and 39 and reproducing their exact committed base sets
(`test_plain_greedy_reproduces_big_lotto_and_daily_539`).

**Resolution**, not a weakened criterion: the same acceptance rule, with
the one addition it already implies — reject any candidate whose
difference from an existing element equals `pool_size / 2` (a no-op for an
odd modulus) — applied via depth-first backtracking instead of
non-backtracking greedy. This is a *completion* of the identical
deterministic, pre-result criterion (same "try the smallest untried
residue next" order; same rejection rule; the only change is that a dead
end triggers backtracking instead of permanently discarding a candidate),
not a switch to a heuristic, randomized, or outcome-tuned method — it never
inspects winning-space coverage, and it reproduces the *exact same* B649
and T539 base sets when run against pool sizes 49 and 39
(`test_backtracking_search_reproduces_big_lotto_and_daily_539`), because
greedy is exactly this same search with backtracking disabled. Against
pool 38, it finds the lexicographically smallest base set containing 0
under this order: `{0, 1, 3, 7, 17, 30}` — differing from the shared
B649/T539 prefix starting at its fifth element, disclosed as a real
divergence forced by exhaustive search, not a coincidence to preserve and
not a manually attractive set chosen after the fact.
`derive_base_set_by_backtracking_search(38, 6)` re-derives this exact
constant from the search procedure alone
(`test_backtracking_search_reproduces_this_modules_own_constant`) — the
constant was not hand-picked.

### 4.2 Verification performed in this task

1. **Sidon validity mod 38**: all `6*5=30` ordered pairwise differences
   distinct (`test_base_set_is_a_sidon_set_mod_38`), and no base pair
   differs by exactly 19
   (`test_base_set_contains_no_self_paired_half_modulus_distance`).
2. **Pairwise ticket overlap `<= 1` across all 38 possible shifts**
   (`C(38,2) = 703` pairs), exhaustively checked, not asserted
   (`test_pairwise_overlap_is_at_most_one_across_every_possible_shift_pair`).
   **Measured maximum: exactly 1** — the preferred invariant is met without
   needing a weaker fallback.
3. Strict nested-prefix portfolio property for the exposure ladder
   (`test_portfolio_is_a_strict_nested_prefix`), shift periodicity exactly
   38, and full-range ticket validity for every one of the 38 shifts.

```text
DETERMINISTIC_SEARCH_PROCEDURE:  greedy first, provably insufficient here,
                                  completed by backtracking (§4.1)
SHIFT_COUNT:                     38
PAIR_COUNT:                      703
MAX_PAIRWISE_INTERSECTION:       1
SIDON_VALIDATION:                PASS (30/30 distinct differences)
```

## 5. Primary estimand and computation method (frozen, not yet executed)

```text
Q_geometry_M3(k) = exact P(>= 1 ticket in P_k has Zone-1 hits >= 3), by
                    single-pass enumeration over all C(38,6) = 2,760,681
                    possible Zone-1 draws -- NOT COMPUTED in this task
Q_random_M3(k)    = exact_random_portfolio_coverage(38, 6, 3, k), reused
                    verbatim, unmodified, from
                    src/lottolab/research/exact_coverage_baseline.py --
                    confirmed in this task to generalize correctly to
                    (pool=38, draw=6) with no code changes

D_3(k)                        = Q_geometry_M3(k) - Q_random_M3(k)
MARGINAL_GEOMETRY_DELTA(k_j)  = [D_3(k_j) - D_3(k_(j-1))] / (k_j - k_(j-1))
```

`MARGINAL_GEOMETRY_DELTA` is a geometry quantity, normalized per additional
ticket (divided by the ladder step size, since the ladder's steps are
uneven) — matching B649/T539's convention exactly. Not called "efficiency,"
"ROI," "optimal spending," or "marginal prize value": no cost/utility
authority exists here.

`K(3)` for P638 Zone-1 = `sum_{j=3}^{6} C(6,j) * C(32,6-j) = 106,833` (out
of `N = 2,760,681`, i.e. `3.869806%` of draws) — computed via the reused,
unmodified `qualifying_ticket_count` function
(`tests/unit/test_exact_coverage_baseline.py`,
`test_exact_coverage_at_k_one_equals_marginal_hit_probability_for_power_lotto_zone1`).
`K(4) = 7,633` (`0.276490%`), `K(5) = 193` (`0.006991%`), `K(6) = 1`
(the single exact-match ticket) — all as descriptive context only, not a
result.

**Required identity, verified in this task**: `Q_random_3(1) == K(3)/N`
exactly — `35611/920227` on both sides, confirmed by exact `Fraction`
arithmetic, not floating-point proximity. `Q_random_3(k)` is also confirmed
monotonically non-decreasing across `k = 0..20`
(`test_exact_coverage_is_monotonically_nondecreasing_in_k_for_power_lotto_zone1`).
For reference (descriptive only, not `Q_geometry`), `Q_random_3(k)` across
the ladder: `k=1: 0.03869806`, `k=3: 0.11165955`, `k=5: 0.17908342`,
`k=10: 0.32609621`, `k=15: 0.44678160`, `k=20: 0.54585434`.

## 6. Computational feasibility (verified in this task, before locking)

Bare enumeration of all `2,760,681` P638 Zone-1 draws: **`0.1421s`**
(measured, this task, Python 3.13, exhaustive `itertools.combinations`).
This is `~5x` fewer draws than B649's `13,983,816` and `~4.8x` more than
T539's `575,757` — comfortably within the range both already-executed
replications handled routinely, with no method change needed.

A full per-draw, up-to-20-ticket bitmask hit-counting pass (the same style
of loop `tools/run_diversification_coverage_t539_v1.py` uses) was
separately timed at **`5.11s`** over the complete `2,760,681`-draw space,
using a **deliberately synthetic, non-representative 20-ticket fixture**
(the lexicographically first 20 Zone-1 combinations — heavily overlapping,
not a low-overlap geometry) purely to confirm the per-draw evaluation
algorithm scales fine at this space size. Per §11 below, this synthetic
run was never pointed at the real `CYCLIC_SIDON_SHIFT_P638_ZONE1_V1`
constructor, and its output numbers carry no scientific meaning.

```text
MONTE_CARLO:               NONE
REAL_DRAW_HISTORY:         NOT_USED
EXACT_EVALUATION_FEASIBILITY: PASS
```

## 7. Classification rule (frozen, for future execution — not applied here)

```text
SANITY_CHECK: D_3(1) must equal exactly 0 (both terms reduce to "one
              arbitrary ticket's marginal hit probability" by symmetry at
              k=1 -- this does not require Q_random_3(1) itself to be 0;
              it is K(3)/N, verified nonzero above).

For k > 1, over the full ladder:
  D_3(k) > 0 for every k  -> OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
  D_3(k) == 0 for every k -> MATCHES_RANDOM_EXPECTED_COVERAGE
  D_3(k) < 0 for every k  -> UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE
  otherwise                -> MIXED_BY_EXPOSURE

GEOMETRY_ADVANTAGE_ZERO_CROSSING = smallest k_j (after the first ladder
    step) where MARGINAL_GEOMETRY_DELTA(k_j) <= 0, or NONE.
```

If the future execution's classification is `MATCHES_RANDOM_EXPECTED_COVERAGE`
or `UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE`: record it and stop. No new base
set, no offset, no different Sidon construction, no different event
threshold for this `matrix_variant_id` — a different geometry would be a new
variant, preregistered before touching the winning-space enumeration, exactly
as this document (and B649/T539 before it) were.

## 8. Cross-lottery interpretation contract (unchanged in kind from B649/T539)

If future P638 execution is positive, the Matrix may say
`DIVERSIFICATION_COVERAGE: SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES`. It may
still not say "universal predictive mechanism," "proven to improve winning
probability through forecasting," "economically optimal," or "profitable."
The evidence type remains `EXACT_COMBINATORIAL`; the mechanism is portfolio
geometry / winning-space coverage, not forecasting.

## 9. Scope boundary (frozen)

```text
PREDICTIVE_ADVANTAGE:                NOT_TESTED
PRIZE_VALUE_ADVANTAGE:                NOT_TESTED
ECONOMIC_OPTIMALITY:                  NOT_TESTED
ZONE_2_ALLOCATION:                    NOT_TESTED (see §2)
P638_EXPERIMENT_EXECUTION:            NOT_RUN
MATRIX_RESULT_CELL:                   NOT_APPENDED (ledger untouched by design)
PRODUCTION / COHORT / PROSPECTIVE:    NONE
REAL_DATA_ACCESS:                     NONE
A_B_C_D_MUTATION:                     NONE
```

## 10. What this task did and did not do

**Did**: independently derive and exhaustively verify a native Z_38/size-6
low-overlap cyclic constructor (including discovering and correctly
resolving a real even-modulus obstruction the two prior replications never
faced); confirm the shared exact-coverage baseline module generalizes to
`(38, 6)` with no code changes; verify the required `k=1` identity exactly;
confirm full-winning-space evaluation is comfortably feasible with the
existing method, timed on a synthetic fixture.

**Did not**: run the frozen constructor through the full scientific
evaluation; compute or retain any `Q_geometry_M3(k)` or `D_3(k)` value for
the real P638 constructor; classify P638; append a Strategy Matrix ledger
cell; read any real P638 draw history; touch Zone-2, Cohort V2, production
strategies, the frontend/API, or draw synchronization.

## 11. No-rescue commitment

The base set, exposure ladder, and event thresholds above were fixed by
the deterministic search in §4 before any winning-space enumeration was
run against them. The synthetic feasibility fixture in §6 is explicitly
disclosed as unrelated to and never merged with this constructor's actual
evaluation path.

## 12. Next step

Return to Owner for explicit lock + execute authorization before any
`Q_geometry_M3(k)` value is computed against the real constructor above, a
classification is assigned, or the Strategy Matrix ledger is touched.
