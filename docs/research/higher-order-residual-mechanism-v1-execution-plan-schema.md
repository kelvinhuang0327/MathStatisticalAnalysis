# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1 — deterministic execution plan/schema

Status: DESIGN SCHEMA — no execution tool or Matrix result exists ｜
2026-08-16

This document is normative for a future, separately authorized
lock-and-execute task. It specifies deterministic input resolution, triple-
geometry computation, serialized fields, and exact invariants. It does not
authorize or perform native execution.

## 1. Fixed configuration

```text
study_id: STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1
ladder: [1, 3, 5, 10, 15, 20]         (identical to Phase 5)
minimum_matches: 3
arms: [SIDON, ARM_B]
delta_direction: ARM_B_MINUS_SIDON
secondary_events: []
monte_carlo: false
historical_draws: false
native_winning_space_enumeration: false   (NEW vs Phase 5 -- not needed;
                                            S3_MULTIPLICITY is reused from
                                            the sealed Phase-5 result)
```

| key | pool `n` | draw/ticket `d` | Sidon function | Arm-B function |
|---|---:|---:|---|---|
| `BIG_LOTTO` | 49 | 6 | `cyclic_sidon_shift.sidon_shift_portfolio` | `greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49,6,k)` |
| `DAILY_539` | 39 | 5 | `cyclic_sidon_shift_t539.sidon_shift_portfolio` | `greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539` |
| `POWER_LOTTO_zone1` | 38 | 6 | `cyclic_sidon_shift_p638.sidon_shift_portfolio` | `greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1` |

The design-time authority snapshot is canonical `origin/main` commit
`8110479`, tree `a82dc823bab4d396ac63a8856d507b43d393047d`. The future
execution records the then-current canonical commit/tree and re-verifies
this design's cited sealed Phase-5 blobs are unchanged (S1 of the design
doc) before proceeding.

## 2. Pre-execution gate

Before a native constructor call:

1. Require a clean dedicated worktree at the Owner-approved canonical
   `origin/main` commit.
2. Read and verify every applicable repository instruction.
3. Verify the locked preregistration path and SHA-256 (once locked).
4. Verify the sealed Phase-5 mechanism result's own preregistration hash
   (`8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be`) and
   input blob SHA-1s are unchanged.
5. Verify no historical-draw path, P638 Zone2 module, Arm-C module, or
   duplicate P638 Sidon source is imported by the execution entry point.
6. Record starting HEAD/tree/status and the future output allowlist.

Any failed check is terminal for that execution attempt.

## 3. Portfolio materialization (unchanged from Phase 5)

```text
sidon_20 = SIDON_CONSTRUCTOR(20)
arm_b_20 = ARM_B_CONSTRUCTOR(20)

for k in ladder:
    sidon_k = sidon_20[:k]
    arm_b_k = arm_b_20[:k]
```

Never rebuild a smaller prefix independently. For each ordered maximum
portfolio, compute a SHA-256 over the identical canonical UTF-8 JSON
encoding Phase 5 used (`separators=(',',':')`, no whitespace, tickets and
numbers in existing order) and assert it equals the sealed `portfolio_
sha256[arm]` already published in `low-overlap-geometry-mechanism-v1-
result.json`. This hash match is what licenses reusing the sealed `S3_
MULTIPLICITY` values instead of recomputing them from a fresh winning-space
enumeration (S8 below).

## 4. Triple-geometry computation (new; no winning-space pass)

For each lottery, arm, and ladder `k >= 3`:

```text
for (t_i, t_j, t_l) in combinations(portfolio_k, 3):
    r_ij = |t_i & t_j|;  r_il = |t_i & t_l|;  r_jl = |t_j & t_l|
    s    = |t_i & t_j & t_l|
    shape = canonical_triple_shape(r_ij, r_il, r_jl, s)
    triple_histogram[shape] += 1

S3_GEOMETRY = sum(
    count * ticket_triple_hit_event_intersection_size(n, d, 3, *shape)
    for shape, count in triple_histogram.items()
)
saturated_triple_count = sum(
    count for shape, count in triple_histogram.items()
    if triple_collision_mass_bound(*shape[:3], shape[3]) == 3*3 - d
)
```

using `src/lottolab/research/higher_order_residual_mechanism.py`'s
functions unchanged. `S3_MULTIPLICITY` for the same `(lottery, arm, k)` is
read directly from the sealed
`low-overlap-geometry-mechanism-v1-result.json`
(`per_lottery[lottery].per_k[k].arms[arm].collision_moments["3"]`), not
recomputed. Do not retain the enumerated triples beyond the histogram; the
canonical-shape histogram is sufficient for every downstream endpoint.

## 5. Deterministic derivation order

For each `(lottery, arm, k)` with `k >= 3`, derive in this order:

1. `ticket_triple_intersection_histogram` from the regenerated portfolio
   prefix (S4).
2. `S3_GEOMETRY` from the histogram (S4).
3. `S3_MULTIPLICITY`, read from the sealed Phase-5 result (S3/S4).
4. `s3_geometry_identity = (S3_GEOMETRY == S3_MULTIPLICITY)`.
5. `saturated_triple_count` from the histogram (S4) -- the `H2` endpoint.
6. `mass_bound_prediction = all(triple_collision_is_impossible(d, 3, *shape[:3], shape[3])
    for shape in triple_histogram) == (S3_MULTIPLICITY == 0)` -- whether the
   Necessary Mass Bound Lemma's zero/nonzero prediction matches the sealed
   value for this cell.
7. Copy `T3, T4, T5, H, mechanism_descriptor, DELTA_COVERED` read-only from
   the sealed Phase-5 result for side-by-side reporting.
8. `residual_to_net_gain_ratio = H / DELTA_COVERED` if `DELTA_COVERED != 0`
   else `NOT_APPLICABLE_ZERO_NET_GAIN`.

Then derive the cross-lottery classifications (preregistration draft S7).

## 6. Exact value encoding (unchanged convention from Phase 5)

Every rational value uses:

```json
{"numerator": 1, "denominator": 2, "exact": "1/2"}
```

Integer-indexed maps serialize keys as base-10 strings in numerical order.
Canonical-shape histogram keys serialize as `"r_min,r_mid,r_max,s"` strings
in ascending tuple order. JSON is emitted with `indent=2`, `sort_keys=True`,
one trailing newline. Floats are never accepted in an identity or
classification field.

## 7. Normative result schema

```text
root
  study_id: exact constant
  source_type: STRATEGY_MATRIX_NATIVE_MECHANISM
  evidence_type: EXACT_COMBINATORIAL
  canonical_input
    repository
    commit
    tree
    locked_preregistration_path
    locked_preregistration_sha256
    sealed_phase5_result_path: docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json
    sealed_phase5_result_blob: dc17f0b39c9baf81f8c85162d5db554e7ca2797a
    sealed_phase5_preregistration_sha256: 8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be
    input_blobs[path]: full Git blob OID
  scope
    historical_draws_read: false
    monte_carlo: false
    native_winning_space_enumeration: false
    p638_zone2: NOT_RUN
    arm_c: NOT_RUN
    secondary_events: NOT_RUN
    j4_geometry: NOT_RUN
    predictive_advantage: NOT_TESTED
    prize_value_advantage: NOT_TESTED
    economic_optimality: NOT_TESTED
  ladder: [1,3,5,10,15,20]
  minimum_matches: 3
  per_lottery[lottery]
    lottery_type
    zone: string or NOT_APPLICABLE
    pool_size
    draw_size
    portfolio_sha256[ARM_B|SIDON]: verified equal to the sealed Phase-5 value
    per_k[k]                       (k >= 3 only; k=1 has no triples)
      arms[ARM_B|SIDON]
        ticket_triple_intersection_histogram[shape]: integer
        s3_geometry: integer
        s3_multiplicity: integer            (copied read-only from sealed Phase-5)
        s3_geometry_identity: boolean
        saturated_triple_count: integer
        mass_bound_prediction_correct: boolean
        sealed_t3: integer
        sealed_t4: integer
        sealed_t5: integer
        sealed_higher_order_residual: integer
        sealed_mechanism_descriptor: enum   (copied read-only)
        sealed_delta_covered: integer       (ARM_B row only; comparison-level)
      comparison
        residual_to_net_gain_ratio: exact-rational object or
          NOT_APPLICABLE_ZERO_NET_GAIN
      checks
        portfolio_sha256_matches_sealed: boolean
        triple_region_sizes_all_nonnegative: boolean
        s3_geometry_identity: boolean
  classifications
    s3_geometry_identity
      value: S3_GEOMETRY_IDENTITY_REPLICATED or S3_GEOMETRY_IDENTITY_FAILED
      failing_cells: array
    mass_bound_prediction
      value: MASS_BOUND_PREDICTS_ZERO_SPLIT or MASS_BOUND_PREDICTION_NOT_UNIVERSAL
      exception_cells: array
    saturated_triple_count_by_k: table    (the H2 endpoint's direct answer)
    global_optimum_status: UNKNOWN
  runtime_seconds
    portfolio_generation_by_lottery_and_arm
    triple_geometry_computation_by_lottery_and_arm
    derivation_and_validation
    total
  peak_memory_bytes
  final_classification
```

## 8. Mandatory invariants

All of these must be true for every arm/cell before classification:

```text
portfolio_sha256[arm] == sealed portfolio_sha256[arm]
every ticket-triple region size (design doc S5/S6) is >= 0
sum of triple_histogram values == C(k, 3)
s3_geometry == s3_multiplicity                       (the core new identity)
s3_multiplicity == sealed collision_moments["3"]      (reuse, not drift)
```

And for the lemma-prediction cross-check:

```text
mass_bound_prediction_correct ==
  (all triples impossible) == (s3_multiplicity == 0)
```

All checks are exact integer equality. No epsilon is permitted.

## 9. Metric and classification gates

`k=1` is excluded entirely from this study's per-`k` table (no triples
exist). The `S3_GEOMETRY_IDENTITY_REPLICATED` and `MASS_BOUND_PREDICTS_
ZERO_SPLIT` predicates quantify all cells in the Cartesian product of three
lottery keys, two arms, and `{3,5,10,15,20}` (30 cells). Empty, missing,
failed, or skipped cells make the predicate unavailable; they do not count
as pass. A non-universal result lists exact cell keys and values, matching
Phase 5's convention.

## 10. Future write set and atomicity

Only a later Owner packet may authorize paths. The expected artifact family
mirrors Phase 5's naming exactly:

```text
docs/research/matrix-native-results/
  higher-order-residual-mechanism-v1-preregistration.md
  higher-order-residual-mechanism-v1-preregistration-hash.json
  higher-order-residual-mechanism-v1-result.json
  higher-order-residual-mechanism-v1-report.md
  higher-order-residual-mechanism-v1-attempt-ledger.json
tools/run_higher_order_residual_mechanism_v1.py
tools/hash_preregistration_higher_order_residual_mechanism_v1.py
tests/unit/test_higher_order_residual_mechanism_v1_execution.py
```

None exists from this design task. The future executor writes a result to
an allowlisted temporary sibling only if the Owner packet permits it,
validates every invariant, then atomically promotes it. A failed run
records the attempt but must not leave a partial result/report presented
as evidence.

## 11. Required report tables

The future human report includes, at minimum:

1. per-cell `S3_GEOMETRY` vs sealed `S3_MULTIPLICITY`, and the identity
   check result;
2. the ticket-triple intersection histogram, per lottery/arm/k;
3. `saturated_triple_count` by `k` (the direct `H2` answer) and how it
   correlates, descriptively, with the sealed residual magnitude (design
   doc S12's ratio table) -- reported as observation, not as a new proven
   identity unless a further exact argument is derived;
4. the Necessary Mass Bound Lemma's prediction vs the sealed zero/nonzero
   pattern, cell by cell;
5. `GLOBAL_OPTIMUM_STATUS: UNKNOWN` and the unchanged claim boundary.

No predictive, profitability, prize-value, economic, Zone2, or Arm-C table
is permitted.

## 12. Design-task validation boundary

The reusable formulas are implemented in
`src/lottolab/research/higher_order_residual_mechanism.py` and tested only
against toy/synthetic portfolios, plus formula evaluation at the real
`(n,d,m)` triples (not native portfolios), in
`tests/unit/test_higher_order_residual_mechanism.py`. Native portfolio
construction and native triple-geometry computation are deliberately
absent.

```text
REAL_S3_GEOMETRY_TRIPLE_HISTOGRAM: NOT_RUN
PREREGISTRATION_LOCKED: NO
NEW_MATRIX_SCIENTIFIC_CELL: NONE
```
