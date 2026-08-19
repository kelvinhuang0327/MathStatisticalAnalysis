# STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1 — deterministic execution plan/schema

Status: DESIGN SCHEMA — no execution tool or Matrix result exists ｜
2026-08-15

This document is normative for a future, separately authorized
lock-and-execute task.  It specifies deterministic input resolution,
streaming enumeration, serialized fields, and exact invariants.  It does
not authorize or perform native execution.

## 1. Fixed configuration

```text
study_id: STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1
ladder: [1, 3, 5, 10, 15, 20]
minimum_matches: 3
arms: [SIDON, ARM_B]
delta_direction: ARM_B_MINUS_SIDON
secondary_events: []
monte_carlo: false
historical_draws: false
```

| key | pool `n` | draw/ticket `d` | winner count | Sidon function | Arm-B function |
|---|---:|---:|---:|---|---|
| `BIG_LOTTO` | 49 | 6 | 13,983,816 | `cyclic_sidon_shift.sidon_shift_portfolio` | `greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49,6,k)` |
| `DAILY_539` | 39 | 5 | 575,757 | `cyclic_sidon_shift_t539.sidon_shift_portfolio` | `greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539` |
| `POWER_LOTTO_zone1` | 38 | 6 | 2,760,681 | `cyclic_sidon_shift_p638.sidon_shift_portfolio` | `greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1` |

The future execution records the then-current canonical commit/tree and
exact input blobs.  The design-time authority snapshot is
`52b8353c932589c3f3ea8ff61fe7982c667cbbb0` /
`69e81767f701ea4f29f86bb0af34262191950c70`.

## 2. Pre-execution gate

Before a native constructor call:

1. Require a clean dedicated worktree at the Owner-approved canonical
   `origin/main` commit.
2. Read and verify every applicable repository instruction.
3. Verify the locked preregistration path and SHA-256.
4. Verify source matrix IDs and exact input Git blobs.
5. Verify no historical-draw path, P638 Zone2 module, Arm-C module, or
   duplicate P638 Sidon source is imported by the execution entry point.
6. Record starting HEAD/tree/status and the future output allowlist.

Any failed check is terminal for that execution attempt.

## 3. Portfolio materialization

For each lottery:

```text
sidon_20 = SIDON_CONSTRUCTOR(20)
arm_b_20 = ARM_B_CONSTRUCTOR(20)

for k in ladder:
    sidon_k = sidon_20[:k]
    arm_b_k = arm_b_20[:k]
```

Never rebuild a smaller prefix independently.  For each ordered maximum
portfolio, persist a SHA-256 over a canonical UTF-8 JSON encoding
(`separators=(',',':')`, no whitespace, tickets and numbers in existing
order).  Assert:

```text
len(portfolio_k) == k
all tickets have d distinct ascending numbers in 1..n
portfolio_k == portfolio_20[:k]
duplicate_count == 0
```

## 4. One-pass exact multiplicity algorithm

Convert each ticket to an integer bit mask once.  For each lottery, stream
`itertools.combinations(range(1,n+1),d)` in lexicographic order.  The
normative algorithm is equivalent to:

```text
N[arm][k] = integer array of length k+1, initialized to zero

for winner in all C(n,d) winners:
    winner_mask = mask(winner)
    for arm in [SIDON, ARM_B]:
        prefix_hits = 0
        for index, ticket_mask in enumerate(portfolio_20[arm], start=1):
            if bit_count(winner_mask & ticket_mask) >= 3:
                prefix_hits += 1
            if index in ladder:
                N[arm][index][prefix_hits] += 1
```

Do not retain winners, per-winner multiplicities, or a historical table.
The complete `N_c` arrays are sufficient for every primary endpoint.

## 5. Deterministic derivation order

For each `(lottery,arm,k)`, derive in this order:

1. `total_winning_combinations = sum_c N_c`.
2. `hit_event_size_per_ticket = K_M3+` from the exact binomial sum.
3. `total_hit_incidence = sum_c c*N_c`.
4. `covered = sum_{c>=1}N_c`.
5. `redundancy = sum_{c>=2}(c-1)N_c`.
6. `S_j = sum_c C(c,j)N_c` for every `j=1,...,k`.
7. inclusion-exclusion reconstruction of `covered`.
8. exact `Q=covered/C(n,d)` reduced by `fractions.Fraction`.
9. geometry from the same ordered prefix portfolio.
10. independent `S2_GEOMETRY=sum_r h_r H_3(n,d,r)`.

Then derive Arm-B-minus-Sidon deltas, signed inclusion-exclusion terms,
the higher-order residual, contribution share, contextual relative metrics,
per-cell descriptors, and cross-lottery classifications.

## 6. Exact value encoding

Every rational value uses this object; floats are never accepted in an
identity or classification field:

```json
{
  "numerator": 1,
  "denominator": 2,
  "exact": "1/2"
}
```

Requirements:

- `denominator > 0`;
- numerator and denominator are coprime;
- `exact` equals `"{numerator}/{denominator}"`;
- optional presentation floats live under an explicitly suffixed key such
  as `reuse_dispersion_float` and are never load-bearing.

Integer-indexed maps serialize keys as base-10 strings in numerical order.
JSON is emitted with `indent=2`, `sort_keys=True`, one trailing newline.

## 7. Normative result schema

The future result root must contain all fields below.  Bracketed names are
dynamic map keys, not optional fields.

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
    input_blobs[path]: full Git blob OID
  scope
    historical_draws_read: false
    monte_carlo: false
    p638_zone2: NOT_RUN
    arm_c: NOT_RUN
    secondary_events: NOT_RUN
    predictive_advantage: NOT_TESTED
    prize_value_advantage: NOT_TESTED
    economic_optimality: NOT_TESTED
  metric_semantics
    RELATIVE_LIFT_VS_RANDOM: "(Q_B-Q_R)/Q_R"
    RELATIVE_COVERAGE_DELTA_VS_SIDON: "(Q_B-Q_S)/Q_S"
    GAIN_OVER_RANDOM_RATIO_TO_SIDON: "(Q_B-Q_R)/(Q_S-Q_R)"
    sealed_REL_GAIN_OVER_SIDON_maps_to: GAIN_OVER_RANDOM_RATIO_TO_SIDON
  ladder: [1,3,5,10,15,20]
  minimum_matches: 3
  per_lottery[lottery]
    lottery_type
    zone: string or NOT_APPLICABLE
    pool_size
    draw_size
    total_winning_combinations
    source_matrix_ids
      arm_b
      sidon
    source_result_paths
      arm_b
      sidon
    portfolio_sha256
      ARM_B
      SIDON
    per_k[k]
      arms[ARM_B|SIDON]
        ticket_count
        hit_event_size_per_ticket
        total_hit_incidence
        multiplicity_counts[c]: integer
        covered: integer
        redundancy: integer
        collision_moments[j]: integer
        inclusion_exclusion_covered: integer
        q: exact-rational object
        geometry
          ticket_pair_intersection_histogram[r]: integer
          overlap_profile[r]: integer
          max_pairwise_overlap: integer
          mean_pairwise_overlap: exact-rational object
          per_number_reuse_vector: integer array of length pool_size
          unique_number_coverage: integer
          reuse_dispersion_population_variance: exact-rational object
          reuse_dispersion_float: number
          duplicate_count: integer
        s2_geometry: integer
        s2_multiplicity: integer
      comparison
        delta_direction: ARM_B_MINUS_SIDON
        delta_covered: integer
        delta_redundancy: integer
        delta_collision_moments[j]: integer
        pairwise_component: integer
        higher_order_signed_terms[j]: integer
        higher_order_residual: integer
        pairwise_absolute_contribution_share: exact-rational object or
          NOT_APPLICABLE_ZERO_CHANGE
        mechanism_descriptor: enum
        relative_lift_vs_random: exact-rational object
        relative_coverage_delta_vs_sidon: exact-rational object
        gain_over_random_ratio_to_sidon: exact-rational object or
          NOT_APPLICABLE_K1
      checks
        n_c_sums_to_winning_space: boolean
        fixed_incidence_identity: boolean
        redundancy_identity: boolean
        inclusion_exclusion_identity: boolean
        s2_geometry_identity: boolean
        reuse_vector_identity: boolean
        zero_duplicates: boolean
        q_arm_b_matches_sealed: boolean
        q_sidon_matches_sealed: boolean
  classifications
    redundancy_reduction
      value: REDUNDANCY_REDUCTION_REPLICATED or
        REDUNDANCY_REDUCTION_NOT_UNIVERSAL
      failing_or_equal_cells: array
    pairwise_collision_reduction
      value: PAIRWISE_COLLISION_REDUCTION_REPLICATED or
        PAIRWISE_COLLISION_NOT_UNIVERSALLY_EXPLANATORY
      failing_or_equal_cells: array
    mechanism_descriptor_counts
    aggregate_mechanism_descriptor: enum or MIXED_BY_LOTTERY_OR_K
    global_optimum_status: UNKNOWN
  runtime_seconds
    portfolio_generation_by_lottery_and_arm
    winning_space_enumeration_by_lottery
    derivation_and_validation
    total
  peak_memory_bytes
  final_classification
```

Allowed per-cell mechanism descriptor values are exactly:

```text
PAIRWISE_COLLISION_EXACTLY_SUFFICIENT
PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL
HIGHER_ORDER_MULTIPLICITY_PRIMARY_OR_PAIRWISE_OPPOSING
```

The root `final_classification` is a mechanism result classification chosen
by the future locked rule; this design does not prewrite its value.

## 8. Mandatory invariants

All of these must be true for every arm/cell before classification:

```text
sum_c N_c = C(n,d)
sum_c c*N_c = k*K_M3+
COVERED = sum_{c>=1}N_c
REDUNDANCY = sum_{c>=2}(c-1)N_c = I-COVERED
S_j = sum_c C(c,j)N_c
COVERED = sum_{j>=1}(-1)^(j+1)S_j
S2_GEOMETRY = S2_MULTIPLICITY
sum(per_number_reuse_vector) = k*d
unique_number_coverage = count(reuse>0)
duplicate_count = 0
```

And for every comparison:

```text
S1_B = S1_S
DELTA_COVERED = -DELTA_S2+DELTA_S3-DELTA_S4+...
DELTA_REDUNDANCY = -DELTA_COVERED
Q_B and Q_S exactly match their sealed source fractions
```

All checks are exact integer/Fraction equality.  No epsilon is permitted.

## 9. Metric and classification gates

At `k=1`, set `GAIN_OVER_RANDOM_RATIO_TO_SIDON` to
`NOT_APPLICABLE_K1`; do not call the guarded ratio function.  At `k>1`,
require `Q_S-Q_R>0` before computing it.

The replicated redundancy and pairwise predicates quantify all 15 cells in
the Cartesian product of three lottery keys and `{3,5,10,15,20}`.  Empty,
missing, failed, or skipped cells make the predicate unavailable; they do
not count as pass.  A non-universal result lists exact cell keys and values.

## 10. Future write set and atomicity

Only a later Owner packet may authorize paths.  The expected artifact family
is:

```text
docs/research/matrix-native-results/
  low-overlap-geometry-mechanism-v1-preregistration.md
  low-overlap-geometry-mechanism-v1-preregistration-hash.json
  low-overlap-geometry-mechanism-v1-result.json
  low-overlap-geometry-mechanism-v1-report.md
  low-overlap-geometry-mechanism-v1-attempt-ledger.json
tools/run_low_overlap_geometry_mechanism_v1.py
tools/hash_preregistration_low_overlap_geometry_mechanism_v1.py
tests/unit/test_low_overlap_geometry_mechanism_v1_execution.py
```

None exists from this design task.  The future executor writes a result to
an allowlisted temporary sibling only if the Owner packet permits it,
validates every invariant, then atomically promotes it.  A failed run records
the attempt but must not leave a partial result/report presented as evidence.

## 11. Required report tables

The future human report includes, at minimum:

1. metric semantic mapping, including the sealed-label correction;
2. per lottery/k coverage, redundancy, and `S2` comparison;
3. full signed `-DELTA_S2,+DELTA_S3,-DELTA_S4,...` decomposition;
4. pairwise contribution share and per-cell descriptor;
5. geometry table for both arms;
6. exact identity/check table;
7. replicated classifications with all failures/equalities;
8. `GLOBAL_OPTIMUM_STATUS: UNKNOWN` and the unchanged claim boundary;
9. runtime, memory, exact input HEAD/tree/blobs, and artifact hashes.

No predictive, profitability, prize-value, economic, Zone2, or Arm-C table
is permitted.

## 12. Design-task validation boundary

The reusable formulas are implemented in
`src/lottolab/research/low_overlap_geometry_mechanism.py` and tested only
against toy/synthetic portfolios in
`tests/unit/test_low_overlap_geometry_mechanism.py`.  Native execution is
deliberately absent.

```text
REAL_MECHANISM_DECOMPOSITION: NOT_RUN
PREREGISTRATION_LOCKED: NO
NEW_MATRIX_SCIENTIFIC_CELL: NONE
```
