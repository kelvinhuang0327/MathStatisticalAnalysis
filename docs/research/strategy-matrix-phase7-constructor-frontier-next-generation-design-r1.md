# STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_DESIGN_R1 — design

Status: DESIGN COMPLETE — OWNER REVIEW REQUIRED ｜ 2026-08-17 ｜ no native
constructor study executed

```text
PREREGISTRATION_STATUS: DRAFT_NOT_LOCKED
REAL_PHASE7_EXECUTION: NOT_RUN
ARM_C_RERUN: NOT_RUN
NEW_MATRIX_SCIENTIFIC_CELL: NONE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
EXECUTION_READINESS: NEXT_GEN_CONSTRUCTOR_READY_FOR_BOUNDED_EXECUTION
```

This document designs the next Matrix-native constructor study.  It does
not predict draws, measure profit, choose live numbers, rerun a sealed
cell, execute Arm-C, or start real portfolio optimization.  The question
is whether a deterministic, geometry-aware constructor can be specified
that improves on greedy Arm-B and moves closer to the sealed B649
best-found frontier without Arm-C-style expensive black-box search.

## 0. Identity and authority

```text
TASK_ID:              STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_DESIGN_R1
FUTURE_STUDY_ID:      STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
SOURCE_TYPE_NOW:       STRATEGY_MATRIX_DESIGN
FUTURE_EVIDENCE_TYPE: EXACT_COMBINATORIAL
CANONICAL_STARTING_CLASSIFICATION:
  REDUNDANCY_REDUCTION_REPLICATED
  PAIRWISE_COLLISION_REDUCTION_REPLICATED
  S3_GEOMETRY_IDENTITY_REPLICATED
  J4_GEOMETRY_EXTENSION_LOW_INFORMATION_VALUE
  GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

Scientific authority is canonical `origin/main` commit
`3b3f953bf9857b85094e9f26c6ef5301ba3561e5`, tree
`6774dcade3c662d0ab3b757710e9e0aafcc3900b`.  The dirty, diverged local
`main` checkout was not used as scientific authority.  No `AGENTS.md` or
`AGENTS.override.md` applies in that canonical tree.

Owner authorization is design-only.  One later task may lock and execute
only after separate authorization.  Push, PR, merge, Arm-C rerun, Phase-5/6
rerun, P638 Zone-2, historical draws, repair of sealed artifacts, and
production or prospective actions remain outside this task.

### 0.1 Recovered sealed authorities (unique)

| Role | Canonical locator | origin/main blob |
|---|---|---|
| A. Sidon B649 | `cyclic_sidon_shift.py`; sealed `diversification-coverage-b649-v1` and frontier arm A | constructor `d07efb5c71a0b25bb00ba3823e208c57aabb306e` |
| A. Sidon T539 | `cyclic_sidon_shift_t539.py`; sealed `diversification-coverage-t539-v1` | `f6b95bed2e0d51ed81781efd096d4f87d88606a1` |
| A. Sidon P638 Zone-1 | `cyclic_sidon_shift_p638.py`; sealed `diversification-coverage-p638-zone1-v1` | `736d0c7e8efc79f68e989921be3e5e0742617e97` |
| B. Arm-B generic | `greedy_min_overlap_constructor.py` | `5511f67d981f7f8a1c33183c966d76ee50249d7d` |
| B. Arm-B T539 | `greedy_min_overlap_constructor_t539.py`; sealed `greedy-min-overlap-constructor-t539-v1` | `372542aa0c164d3548a6aaa91dd56b28821d0eaa` |
| B. Arm-B P638 Zone-1 | `greedy_min_overlap_constructor_p638_zone1.py`; sealed `greedy-min-overlap-constructor-p638-zone1-v1` | `622898a9f0a9f4c72af456a21af83c0fc63c7d45` |
| C. Arm-C search | `bounded_coverage_optimizer.py` / `_fast.py`; sealed only on B649 as `diversification-constructor-frontier-b649-v1` | `1f1b767d6b6bac470d07496d7674c912ba7c8982` / `4ee0c9f7cc842e44dee1fddbf0fe77f901271c7d` |
| C. Sealed B649 frontier result / report | `diversification-constructor-frontier-b649-v1-{result.json,report.md}` | `169df1649ff0b8247ef5c779e8104079ae574cf4` / `60289b021f7859f0b92ccf42f38add16b9a31158` |
| D. Phase-5 mechanism | `low-overlap-geometry-mechanism-v1-{result.json,report.md}` | `dc17f0b39c9baf81f8c85162d5db554e7ca2797a` / `0243589b14068ea6a3f32d8af37e4db9b7569065` |
| D. Phase-6 S3 identity | `higher-order-residual-mechanism-v1-{result.json,report.md}` | `4d5a9b50e3355f61df23034cdb0762d4a27c1813` / `d7bf3baef56b81303fae41ad7e51f0e5f5920ab3` |
| D. J4 value gate | `strategy-matrix-phase6-j4-geometry-extension-design-r1.md` | `90e1f32610d03ae380fe6443c5b5e4e10502c93a` |
| D. Phase-5 synthesis | `strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-result.json` | `d9e5d86582e71ba86f8e48d091f31eaf824bf224` |
| S2 identity helper | `low_overlap_geometry_mechanism.py` | `20b6e0d70b17ef4e34c4d3d6f89196685c5bd22c` |
| Random expected D | `exact_coverage_baseline.py` | `3f842d6f29af4bc0691e1baf92a284c0ab8a0cac` |

Each role has exactly one canonical sealed locator of the stated kind.
No competing alternate Sidon, Arm-B, B649 Arm-C, Phase-5, or Phase-6
cell was found on `origin/main`.  Authority is therefore
`AUTHORITY_STATUS: RESOLVED`.

Fixed prior conclusions, copied rather than re-argued:

- Arm-B outperforms random and Sidon at every tested `k > 1` in all three
  native structures.
- Pairwise collision / redundancy reduction is the primary mechanism.
- `S3_GEOMETRY == S3_MULTIPLICITY` exactly (Phase 6).
- J4+ extension has low information value (Phase-6 J4 design gate).
- `GLOBAL_OPTIMUM_STATUS` remains `UNKNOWN`.

## 1. Boundaries (frozen)

```text
PHASE_5_RERUN:                 NOT_RUN
PHASE_6_RERUN:                 NOT_RUN
ARM_C_RERUN:                   NOT_RUN
REAL_B649/T539/P638_EXECUTION: NOT_RUN
P638_ZONE2:                    OUT_OF_SCOPE
HISTORICAL_DRAWS:              NOT_USED
MONTE_CARLO:                   NONE
WEIGHTED_SCORE_TUNING:         FORBIDDEN
POST_RESULT_COEFFICIENT:       FORBIDDEN
RANDOM_RESTART:                FORBIDDEN
DB / API / PROSPECTIVE:        NONE
MATRIX RESULT CELL:            NOT APPENDED
```

Arm-C exists only as a **sealed B649 frontier reference**.  Its tickets
are not regenerated.  Its search is not resumed.

## 2. Design question

Given that low-overlap / redundancy reduction is the sealed main coverage
mechanism, can one deterministic geometry-aware constructor be specified
that:

1. is lottery-native via `(pool_size, draw_size, ticket_count)`;
2. is history-free and outcome-free;
3. uses no random restart and no post-result tuning;
4. is portable in principle across the three native structures;
5. is expected, at toy scale, to differ meaningfully from Arm-B;
6. is cheap relative to Arm-C's bounded coverage search?

Evaluated construction objectives:

| Candidate objective | Disposition |
|---|---|
| 1. Minimize pairwise ticket overlap / `S2` proxy | **Retained as the entire objective**, split into a lex pair `(max, sum)` |
| 2. Minimize saturated-triple / `S3` proxy | **Rejected as a constructor objective** |
| 3. Lexicographic: pairwise first, then `S3` / reuse | **Pairwise lex retained; S3/reuse not added as a scored term** |
| 4. Another exact geometry objective | **Not added.**  Number-use / reuse-dispersion remain descriptive |

`S3` is not a coverage-minimization objective.  The sealed inclusion-
exclusion identity is `COVERED = S1 - S2 + S3 - S4 + ...`.  For fixed
`k`, `S1` is combinatorially identical across legal `k`-ticket
portfolios.  Reducing `S2` raises coverage.  Reducing `S3` *lowers*
coverage.  Phase 6 already explained `S3` exactly as a function of the
ticket-triple histogram; J4+ was gated as low information value.  Using
`S3` as an independent constructor score would therefore either fight
the sealed primary mechanism or retune a residual that is already
explained.

Number-use and reuse-dispersion are sealed as
`AGGREGATE_MECHANISM_DESCRIPTOR: MIXED_BY_LOTTERY_OR_K`.  They are
reported, not optimized.  Putting them into the key would be an extra
hypothesis aimed at Arm-C's known `unique_number_coverage = 49`.

## 3. Sealed frontier comparison (B649 only)

Primary event `M3_PLUS`.  Exact fractions come from sealed
`diversification-constructor-frontier-b649-v1-result.json`.  Arm-C is
`INDEPENDENT_PER_K` (no prefix guarantee).  Arm-B is prefix-stable.

| k | Q_A | Q_B | Q_C | Q_D | best-found |
|---:|---:|---:|---:|---:|:---:|
| 1 | 4654/249711 | 4654/249711 | 4654/249711 | 4654/249711 | tie |
| 3 | 27487/499422 | 32528/582659 | 32528/582659 | 159788892251374/2911762307093563 | B = C |
| 5 | 18299/202664 | 54130/582659 | 54130/582659 | (sealed exact) | B = C |
| 10 | 2428175/13983816 | 211705/1165318 | 636901/3495954 | (sealed exact) | **C** |
| 15 | 5351/21252 | 86785/332948 | 3709795/13983816 | (sealed exact) | **C** |
| 20 | 108833/332948 | 142111/423752 | 4788733/13983816 | (sealed exact) | **C** |

Approximate floats, for reading only:

| k | Q_A | Q_B | Q_C | Q_D | C − B |
|---:|---:|---:|---:|---:|---:|
| 3 | 0.055038 | 0.055827 | 0.055827 | 0.054877 | 0 |
| 5 | 0.090292 | 0.092902 | 0.092902 | 0.089778 | 0 |
| 10 | 0.173642 | 0.181671 | 0.182182 | 0.171496 | 19/37191 ≈ 0.000511 |
| 15 | 0.251788 | 0.260656 | 0.265292 | 0.245878 | 64825/13983816 ≈ 0.004636 |
| 20 | 0.326877 | 0.335364 | 0.342448 | 0.313582 | 49535/6991908 ≈ 0.007085 |

### 3.1 Geometry (sealed histograms)

All three arms have `max_pairwise_overlap <= 1` and `duplicate_tickets = 0`
at every tested `k`.

| k | arm | max | mean | n_{r=1} | unique | uses 49 | reuse disp. |
|---:|:---:|---:|---:|---:|---:|---:|---:|
| 3 | A | 1 | 1.000 | 3 | 15 | 0 | 0.596 |
| 3 | B | 0 | 0.000 | 0 | 18 | 0 | 0.482 |
| 3 | C | 0 | 0.000 | 0 | 18 | 0 | 0.482 |
| 5 | A | 1 | 1.000 | 10 | 22 | 0 | 0.803 |
| 5 | B | 0 | 0.000 | 0 | 30 | 0 | 0.487 |
| 5 | C | 0 | 0.000 | 0 | 30 | 1 | 0.487 |
| 10 | A | 1 | 1.000 | 45 | 30 | 0 | 1.250 |
| 10 | B | 1 | 0.289 | 13 | 48 | 0 | 0.506 |
| 10 | C | 1 | 0.244 | 11 | 49 | 1 | 0.417 |
| 15 | A | 1 | 0.943 | 99 | 35 | 0 | 1.582 |
| 15 | B | 1 | 0.591 | 62 | 48 | 0 | 0.997 |
| 15 | C | 1 | 0.410 | 43 | 49 | 2 | 0.467 |
| 20 | A | 1 | 0.858 | 163 | 40 | 0 | 1.762 |
| 20 | B | 1 | 0.663 | 126 | 48 | 0 | 1.263 |
| 20 | C | 1 | 0.505 | 96 | 49 | 2 | 0.608 |

Arm-B never uses number 49 at any tested `k`.  That is a documented
lexicographic scan artifact, not a geometry theorem.

### 3.2 Exact identities versus descriptive association

**Exact identity (already sealed, Phase 5).**  For event `M3+`,

```text
S2_GEOMETRY = sum_r n_r * H_3(n, d, r) = S2_MULTIPLICITY
```

where `H_3(n, d, r)` is the number of winning combinations hitting both
tickets of a pair with intersection `r`.  On B649 this evaluates to

```text
H_3(49, 6, 0) = 400
H_3(49, 6, 1) = 4100
H_3(49, 6, 1) - H_3(49, 6, 0) = 3700
```

**Exact corollary, used here only under the sealed `max <= 1` regime.**
If every pair has `r ∈ {0, 1}` and `n_0 + n_1 = C(k, 2)`, then

```text
mean_pairwise_overlap = n_1 / C(k, 2)
S2 = C(k, 2) * 400 + n_1 * 3700
```

So mean overlap and `S2` are affinely equivalent.  Minimizing the
intersecting-pair count *is* minimizing `S2`.  This identity is
arm-agnostic; it does not require rerunning Phase 5.

**Identity-derived `S2` for sealed Arm-C histograms** (not a new Matrix
cell; the histograms are already sealed; the formula is already sealed):

| k | n_1(B) | n_1(C) | S2_B (sealed) | S2_C (derived) | S2_B − S2_C |
|---:|---:|---:|---:|---:|---:|
| 10 | 13 | 11 | 66100 | 58700 | 7400 = 2 × 3700 |
| 15 | 62 | 43 | 271400 | 201100 | 70300 = 19 × 3700 |
| 20 | 126 | 96 | 542200 | 431200 | 111000 = 30 × 3700 |

`S2_B` matches the sealed Phase-5 `S2_B` column exactly, which is the
required cross-check that the same identity is being applied.

**Descriptive association, not an identity.**  Arm-C's higher unique-number
coverage (49 vs 48) and lower reuse dispersion travel with the lower
`n_1`.  They are not independently load-bearing: Phase 5 classified
aggregate descriptors as mixed by lottery or `k`, and at `k = 5` Arm-C
already uses 49 while tying Arm-B on both coverage and the pair
histogram (`n_1 = 0` for both).  Using 49 is therefore not itself a
coverage mechanism.

**Not claimed.**  That a constructor which incrementally minimizes
`(max, sum)` *will* raise native `Q`.  That is the future experiment.
The sealed evidence only shows that the remaining B-to-C gap lives
inside a lower `S2` at the same `max`, which is exactly the increment
Arm-B throws away when it tie-breaks by scan order.

### 3.3 Runtime / evaluation cost (sealed, B649)

| Arm | Cost | Notes |
|---|---|---|
| A Sidon | ~0 s | closed construction |
| B greedy min-max | 774.5 s (~12.9 min) | one full `C(49,6)` scan per ticket after the disjoint phase |
| C bounded search | 6904.6 s (~115 min); 56,730 coverage evaluations | 5 restarts, sample 60, 3 swap passes; `k = 20` alone 48.4 min |
| D random expected | ~0 s | closed form |

Arm-C is the expensive black-box: each evaluation re-enumerates
`C(49, 6) = 13,983,816` draws (fast evaluator) and the search is seeded
and restart-based.  It is not a portable deterministic constructor.

## 4. Mechanism-to-objective mapping

```text
SEALED_PRIMARY_MECHANISM:   pairwise collision / S2 reduction
SEALED_S2_IDENTITY:         S2 = sum_r n_r H_m(n,d,r)
SEALED_MAX_REGIME:          max_pairwise_overlap <= 1 for A, B, C at every tested k
COROLLARY:                  under that regime, S2 ≡ n_1
ARM_B_OBJECTIVE:            minimize incremental max overlap; lex scan otherwise
ARM_C_OBJECTIVE:            maximize exact M3+ coverage by seeded local search
REMAINING_B_TO_C_GAP:       same max, strictly smaller n_1 / S2 for C at k in {10,15,20}
PROPOSED_OBJECTIVE:         lex minimize (max overlap, sum overlap)
WHY_NOT_S3:                 IE sign of S3 is opposite to S2; S3 already explained
WHY_NOT_REUSE_SCORE:        mixed aggregate descriptor; would track Arm-C's known unique=49
```

Arm-B already implements the first coordinate.  The missing coordinate
that the sealed B-to-C histograms isolate is the second.

## 5. Proposed constructor (exactly one)

```text
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
ENTRY_POINT:
  lottolab.research.greedy_minmax_then_sum_overlap_constructor
    .greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, ticket_count)
```

### 5.1 Constructor rule

1. Reject `pool_size < draw_size` or `ticket_count` outside
   `[0, C(pool_size, draw_size)]`.
2. Ticket 0 is the lexicographically first `draw_size`-subset of
   `1..pool_size`.
3. For `i = 1, ..., ticket_count - 1`, among unused legal tickets,
   select the unique minimizer of

   ```text
   key(candidate) = (
       max_j |candidate ∩ T_j|,
       sum_j |candidate ∩ T_j|,
       candidate
   )
   ```

   where `T_0, ..., T_{i-1}` are already chosen.
4. Append the winner.  Earlier tickets are never revised.

While an overlap-0 candidate exists, `key = (0, 0, ticket)`, so the
rule reproduces Arm-B's sequential disjoint blocks.  The constructors
first differ when every remaining candidate has positive overlap and a
smaller collision *count* can beat a lexicographically earlier
transversal.

### 5.2 Tie-breaking

```text
PRIMARY:   minimize incremental max pairwise overlap
SECONDARY: minimize incremental sum of pairwise overlaps
FINAL:     lexicographically smallest ticket
```

The final coordinate is a total-order device, not a geometry objective.
There is no numeric weight, no lottery-specific constant, and no
coefficient fitted to sealed `Q_C`.

### 5.3 Duplicate handling

Already-chosen tickets are excluded from the candidate scan.  Combined
with `ticket_count <= C(n, d)`, this forces `duplicate_tickets = 0`.

### 5.4 Stopping rule

Stop after exactly `ticket_count` tickets.  No coverage threshold, no
early `Q` stop, no budget of evaluations.

### 5.5 Computational complexity

Naive scan: `O(k · C(n, d) · k · d)` set-intersection work, identical
order to Arm-B.  While overlap 0 remains, the scan may stop at the
first such unused ticket (same early-exit Arm-B already uses).  After
the disjoint capacity `⌊n / d⌋` is exhausted, each new ticket requires
a full `C(n, d)` pass, again as in Arm-B.

Expected native cost envelope, from sealed Arm-B generation times, not
from a new run:

```text
B649   (49,6), k=20:  ~13 min   [Confirmed: sealed 774.5 s]
T539   (39,5), k=20:  ~0.5 min  [Confirmed: sealed 30.2–30.7 s]
P638Z1 (38,6), k=20:  ~2.5 min  [Confirmed: sealed 151–154 s]
```

The candidate adds only a running sum beside Arm-B's running max.
Planning envelope: `COMPARABLE_TO_ARM_B`, far below Arm-C's 115 minutes
and 56,730 exact-coverage evaluations.  Peak memory remains the
iterator plus `O(k)` tickets.

### 5.6 Expected portability

The rule names only `(pool_size, draw_size, ticket_count)`.  The three
native structures are exactly three parameter triples:

```text
BIG_LOTTO:          (49, 6, k)
DAILY_539:          (39, 5, k)
POWER_LOTTO_ZONE1:  (38, 6, k)
```

No Sidon algebra, no modular base set, no B649-only constant.  T539's
sealed `H_3(39, 5, 0) = 0` makes pairwise *exactly* sufficient there;
the same `(max, sum)` key remains well-defined and is the entire `S2`
increment (`H_3(39, 5, 1) = 36`).

### 5.7 What this constructor is not

It is not a Steiner system, not a cyclic design, not a restart search,
not an Arm-C clone, and not claimed globally optimal.  It is the
smallest deterministic greedy that implements the sealed pairwise
mechanism on *both* coordinates the B-to-C histograms actually
separate.

## 6. Toy / synthetic behaviour

All examples below are unit-tested.  No native lottery is constructed.

### 6.1 Agreement on the disjoint prefix

`(n, d) = (10, 3)`, `k = 3`:

```text
ARM_B = CANDIDATE = ((1,2,3), (4,5,6), (7,8,9))
```

### 6.2 First meaningful divergence

`(n, d) = (10, 3)`, `k = 4`.  Leftover number = 10.

```text
ARM_B[3]      = (1, 4, 7)     key = (1, 3, (1,4,7))
CANDIDATE[3]  = (1, 4, 10)    key = (1, 2, (1,4,10))
```

Both have `max = 1`.  Arm-B keeps the lex-first transversal of the
three blocks and never spends 10.  The candidate spends 10 and
intersects only two existing tickets.  Pair-sum is 2 versus 3.

This is the same geometry as B649 at the first post-disjoint ticket:
`⌊49/6⌋ = 8` disjoint blocks, leftover 49, and Arm-B's lex-first
6-transversal of the first six blocks does not need 49.

### 6.3 Max still dominates sum

Against `((1,2,3),(4,5,6),(7,8,9))`:

```text
(1, 4, 10)  -> (1, 2, ...)
(1, 2, 10)  -> (2, 2, ...)
```

Equal collision *count* cannot override a worse *max*.  That preserves
Arm-B's primary coordinate.

### 6.4 A second shape where they re-agree

`(n, d) = (8, 2)`, `k = 5`: after the perfect matching
`(1,2),(3,4),(5,6),(7,8)` every remaining pair has sum 2, so lex
returns `(1, 3)` for both constructors.  Divergence is forced by the
key, not by a hidden "always use the largest number" rule.

## 7. Future experiment

### 7.1 Comparators

```text
A = sealed Sidon reference          (immutable constructors)
B = current greedy Arm-B            (immutable constructors)
CANDIDATE = GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
D = exact random expected coverage  (exact_coverage_baseline)
C_SEALED = B649 Arm-C coverage      (read-only sealed Q_C; NOT rerun)
```

Arm-C tickets are not materialized.  Only sealed `Q_C(k)` and sealed
geometry summaries are referenced, and only on B649.

### 7.2 Future k ladder

```text
K_LADDER: {1, 3, 5, 10, 15, 20}
PRIMARY_EVENT: M3_PLUS (minimum_matches = 3)
SECONDARY_EVENTS: NOT_RUN_BY_DEFAULT
k = 1: sanity / identity only; excluded from k>1 predicates
```

The same ladder as every sealed diversification cell in this family.
CANDIDATE is prefix-stable, so `k = 20` is generated once and smaller
rungs are exact prefixes.

### 7.3 Frontier-capture metric

Let `Q_E(k)`, `Q_B(k)`, `Q_D(k)` be the future exact CANDIDATE / Arm-B /
random coverages, and `Q_C(k)` the **sealed** Arm-C coverage.

```text
FRONTIER_CAPTURE_RATIO_CANDIDATE(k) =
    (Q_E(k) - Q_D(k)) / (Q_C(k) - Q_D(k))
    if Q_C(k) > Q_D(k)
    else NOT_APPLICABLE

B_TO_C_GAP_CAPTURE(k) =
    (Q_E(k) - Q_B(k)) / (Q_C(k) - Q_B(k))
    if Q_C(k) > Q_B(k)
    else NOT_APPLICABLE_TIED_FRONTIER
```

Both are exact `fractions.Fraction` values.  Presentation floats are
non-load-bearing.  `B_TO_C_GAP_CAPTURE` is undefined at `k ∈ {1, 3, 5}`
on B649 because sealed `Q_C = Q_B` there.

Materiality is frozen *before* seeing `Q_E`:

```text
MATERIAL_B649_GAP_CAPTURE:
  B_TO_C_GAP_CAPTURE(20) >= 1/4
```

One quarter of the largest sealed gap is a pre-registered constant, not
a value fitted to a trial run.  The future report must still publish
the exact ratio at every `k` where it is defined.

### 7.4 Future primary questions

Does CANDIDATE:

1. beat random at every `k > 1`?  Require `Q_E(k) > Q_D(k)`.
2. beat Arm-B at every `k > 1`?  Require `Q_E(k) >= Q_B(k)` everywhere
   and `Q_E(k) > Q_B(k)` on the sealed-gap rungs `{10, 15, 20}`.
3. capture materially more of the sealed B649 Arm-C frontier gap?
   Require `MATERIAL_B649_GAP_CAPTURE`.
4. retain deterministic cross-lottery portability?  Same module, only
   `(n, d, k)` changes.

Do not assert global optimality.  A pass of (1)–(4) is
`CANDIDATE_IMPROVES_ON_ARM_B_TOWARD_SEALED_FRONTIER`, not
`GLOBALLY_OPTIMAL`.

### 7.5 B649 advance gate

```text
B649_ADVANCE_GATE passes iff all hold:
  1. Q_E(k) > Q_D(k)                         for every k in {3,5,10,15,20}
  2. Q_E(k) >= Q_B(k)                        for every k in {3,5,10,15,20}
  3. Q_E(k) > Q_B(k)                         for every k in {10,15,20}
  4. B_TO_C_GAP_CAPTURE(20) >= 1/4
  5. duplicate_tickets == 0 at every k
  6. constructor invoked only as
     greedy_minmax_then_sum_overlap_portfolio(49, 6, k)
  7. ARM_C_RERUN == NOT_RUN
```

Failure of any clause is `B649_ADVANCE_GATE: FAIL`.  T539/P638 must
not start.

### 7.6 Cross-lottery replication rule

```text
IF B649_ADVANCE_GATE = PASS:
  replicate CANDIDATE vs A, B, D on DAILY_539 then POWER_LOTTO Zone-1
  using the same module and the same k ladder
  Arm-C is NOT rerun and is NOT a comparator off B649
  success there is Q_E > Q_D and Q_E >= Q_B at every k>1,
  plus Q_E > Q_B at every k where disjoint capacity is exceeded
    T539:  k > floor(39/5) = 7  -> tested k in {10,15,20}
    P638:  k > floor(38/6) = 6  -> tested k in {10,15,20}
ELSE:
  STOP.  No T539.  No P638.
```

## 8. Execution-scope decision

Existing sealed evidence is sufficient to name **one** next constructor
without inventing a score:

- the primary mechanism is pairwise / `S2`;
- under the sealed `max <= 1` regime, `S2` *is* the intersecting-pair
  count;
- Arm-B already minimizes `max` and wastes the `sum` coordinate on lex
  scan order;
- the sealed B-to-C gap is exactly that wasted coordinate;
- the rule is parameter-free, deterministic, and portable;
- toy scale already separates it from Arm-B.

```text
EXECUTION_READINESS: NEXT_GEN_CONSTRUCTOR_READY_FOR_BOUNDED_EXECUTION
SMALLEST_FUTURE_SEQUENCE:
  lock preregistration
  -> execute B649 only
  -> apply B649_ADVANCE_GATE
  -> replicate T539 then P638 Zone-1 only if the gate passes
```

This document does not lock or execute that sequence.

## 9. Claim boundary

This design may say: a unique deterministic next-generation constructor
is identifiable from sealed pairwise identities and the sealed B-to-C
histogram gap.

It may not say: CANDIDATE beats Arm-B on native `Q`; CANDIDATE captures
the Arm-C frontier; CANDIDATE is optimal; S3 or number-use should be
scored; Arm-C should be rerun; any live ticket should be played.

```text
PREDICTIVE_ADVANTAGE / PRIZE_VALUE / ECONOMIC_OPTIMALITY: NOT_TESTED
GLOBAL_OPTIMUM_STATUS: UNKNOWN
REAL_PHASE7_EXECUTION: NOT_RUN
ARM_C_RERUN: NOT_RUN
NEW_MATRIX_SCIENTIFIC_CELL: NONE
```

## 10. Remaining prelock issues

1. A later Owner-authorized task must lock the preregistration draft
   and record the then-current canonical `origin/main` commit/tree.
   The design-time snapshot above is not a lock.
2. Execution must start from a clean worktree at that canonical ref,
   not from the current dirty/diverged local `main`.
3. Sealed Arm-C `Q_C` values must be copied from the frontier result
   blob `169df1649ff0b8247ef5c779e8104079ae574cf4` and not recomputed
   by calling the optimizer.
4. CANDIDATE must not import or wrap
   `low_overlap_portfolio_constructor.py` (unrelated untracked Phase-5
   application) or any score-guided candidate pool.
5. Secondary events, P638 Zone-2, and any weighted variant remain
   out of scope even after a successful B649 gate.

## 11. Final design disposition

```text
AUTHORITY_STATUS: RESOLVED
SEALED_FRONTIER_COMPARISON: COMPLETE (read-only)
MECHANISM_TO_OBJECTIVE_MAPPING: PAIRWISE_S2_LEX_MAX_THEN_SUM
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
CONSTRUCTOR_RULE: greedy unused ticket minimizing (max, sum, ticket)
TIE_BREAKING: max, then sum, then lex ticket
TOY_BEHAVIOR: agrees with Arm-B on disjoint prefix; differs at first leftover
FRONTIER_CAPTURE_METRIC: B_TO_C_GAP_CAPTURE and FRONTIER_CAPTURE_RATIO_CANDIDATE
FUTURE_COMPARATORS: A, B, CANDIDATE, D; C_SEALED on B649 only
FUTURE_K_LADDER: {1,3,5,10,15,20}
B649_ADVANCE_GATE: defined in §7.5
CROSS_LOTTERY_REPLICATION_RULE: B649 first; T539 then P638 only if gate passes
COMPUTATIONAL_FEASIBILITY: COMPARABLE_TO_ARM_B
EXECUTION_READINESS: NEXT_GEN_CONSTRUCTOR_READY_FOR_BOUNDED_EXECUTION
REMAINING_PRELOCK_ISSUES: listed in §10
REAL_PHASE7_EXECUTION: NOT_RUN
ARM_C_RERUN: NOT_RUN
NEW_MATRIX_SCIENTIFIC_CELL: NONE
```

Final classification:
`PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_DESIGN_READY_FOR_OWNER_REVIEW`.
