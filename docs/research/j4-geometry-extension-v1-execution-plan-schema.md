# STRATEGY_MATRIX_PHASE6_J4_GEOMETRY_EXTENSION_V1 — conditional execution schema

Status: CONDITIONAL DESIGN ONLY — no lock, native execution, result, or
preregistration exists ｜ 2026-08-17

This schema is a deterministic future execution contract only if an Owner
later overrides the value-of-information classification in
`strategy-matrix-phase6-j4-geometry-extension-design-r1.md`. It does not
authorize execution. The current route is
`J4_GEOMETRY_EXTENSION_LOW_INFORMATION_VALUE`.

## 1. Fixed study configuration

```text
study_id: STRATEGY_MATRIX_PHASE6_J4_GEOMETRY_EXTENSION_V1
hypothesis_family_id: DIVERSIFICATION
event: primary M3+ only
minimum_matches: 3
configured_ladder: [1, 3, 5, 10, 15, 20]
j4_primary_ladder: [5, 10, 15, 20]
optional_audit_ladder: [1, 3]
omitted_k4_reason: no sealed Phase-5 k=4 S4 multiplicity input;
                   adding k=4 would require a new sealed input or winning-space work
arms: [ARM_B, SIDON]
delta_direction: ARM_B_MINUS_SIDON
historical_draws: false
monte_carlo: false
native_winning_space_enumeration: false
arm_c: out_of_scope
p638_zone2: out_of_scope
new_lottery_structures: out_of_scope
```

| structure | pool `n` | ticket/draw `d` | Arm-B constructor | Sidon constructor |
|---|---:|---:|---|---|
| `BIG_LOTTO` | 49 | 6 | `greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49,6,k)` | `cyclic_sidon_shift.sidon_shift_portfolio` |
| `DAILY_539` | 39 | 5 | `greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539` | `cyclic_sidon_shift_t539.sidon_shift_portfolio` |
| `POWER_LOTTO_zone1` | 38 | 6 | `greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1` | `cyclic_sidon_shift_p638.sidon_shift_portfolio` |

`k=1` and `k=3` may be retained for hash and continuity audit, but no J4
quadruple histogram is defined there. The future identity table is evaluated
only at `k in [5,10,15,20]`. No `k=4` row is silently inferred.

## 2. Authority and fail-closed preflight

Before any constructor call, a separately authorized executor must record the
canonical `origin/main` commit/tree and verify that the following sealed blobs
are unchanged:

```text
Phase-6 locked preregistration:
  docs/research/matrix-native-results/higher-order-residual-mechanism-v1-preregistration.md
  blob bc9f6f376296ee3471e6afa02035b3c266d0d596
  locked SHA-256 354d96bcee4c9e4efb59e3e88f18c686fdfb23ed00be5dae2c0ea0d133e550a6

Phase-6 sealed result:
  docs/research/matrix-native-results/higher-order-residual-mechanism-v1-result.json
  blob 4d5a9b50e3355f61df23034cdb0762d4a27c1813

Phase-5 sealed result:
  docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json
  blob dc17f0b39c9baf81f8c85162d5db554e7ca2797a
  preregistration SHA-256 8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be

Pure J4 helper:
  src/lottolab/research/fourth_order_geometry.py
```

The executor must stop with an input-drift status if a locked blob, sealed
result, constructor identity, or canonical source tree differs. It must not
repair or rewrite a sealed artifact. It must also verify that the execution
entry point imports no historical-draw provider, winning-space enumerator,
Arm-C path, P638 Zone-2 path, or untracked duplicate constructor.

## 3. Portfolio materialization and hash gate

For each structure and arm, materialize the canonical `k=20` portfolio once,
validate ascending distinct tickets and pool bounds, compute the already-used
canonical portfolio SHA-256, and compare it to the sealed Phase-6 hash. Only
after a match may the executor take prefixes:

```text
portfolio_20 = CANONICAL_CONSTRUCTOR(20)
for k in [1,3,5,10,15,20]:
    portfolio_k = portfolio_20[:k]
```

No smaller portfolio is rebuilt independently. The hash gate licenses reuse
of sealed Phase-5 `S4_MULTIPLICITY` values for the four primary J4 rungs. A
hash mismatch is terminal; it is not a reason to regenerate a winning space.

## 4. Deterministic J4 derivation

For every structure, arm, and `k in [5,10,15,20]`:

1. Enumerate only the `C(k,4)` ticket quadruples, never winning draws.
2. Compute the exact 16-region shape under all four-ticket relabelings.
3. Accumulate `ticket_quadruple_intersection_histogram[shape]`.
4. Require `sum(histogram.values()) == C(k,4)`.
5. Require every shape's 16 region sizes to be non-negative and to sum to `n`.
6. Compute `S4_GEOMETRY` by summing
   `count * ticket_quadruple_hit_event_intersection_size(n,d,3,shape)`.
7. Read `S4_MULTIPLICITY` from the sealed Phase-5 result's
   `arms[arm].collision_moments["4"]`; do not recompute it.
8. Require exact equality `S4_GEOMETRY == S4_MULTIPLICITY`.
9. Count saturated shapes where `M4 == 4*3-d`.
10. Copy sealed `T3`, `T4`, `T5+`, `H`, and `DELTA_COVERED` read-only for
    the residual attribution table.

The exact pure functions are:

```text
canonical_quadruple_region_shape
ticket_quadruple_intersection_histogram
ticket_quadruple_hit_event_intersection_size
s4_from_ticket_quadruple_region_histogram
quadruple_region_mass
quadruple_collision_mass
quadruple_collision_is_impossible
quadruple_shape_is_saturated
max_pairwise_overlap_forces_zero_quadruple_collisions
```

## 5. Normative output schema

The future result must be written atomically only after all required cells pass:

```text
root
  study_id
  source_type: STRATEGY_MATRIX_DESIGNED_NATIVE_MECHANISM
  evidence_type: EXACT_COMBINATORIAL
  canonical_input
    repository
    commit
    tree
    phase6_preregistration_path
    phase6_preregistration_sha256
    phase6_result_path
    phase6_result_blob
    sealed_phase5_result_path
    sealed_phase5_result_blob
    input_blobs[path]
  scope
    historical_draws_read: false
    monte_carlo: false
    native_winning_space_enumeration: false
    arm_c: NOT_RUN
    p638_zone2: NOT_RUN
    predictive_advantage: NOT_TESTED
    prize_value_advantage: NOT_TESTED
    economic_optimality: NOT_TESTED
    global_optimum_status: UNKNOWN
  configured_ladder: [1,3,5,10,15,20]
  j4_primary_ladder: [5,10,15,20]
  optional_audit_ladder: [1,3]
  per_structure[structure]
    pool_size
    draw_size
    portfolio_sha256[ARM_B|SIDON]
    per_k[k]
      arms[ARM_B|SIDON]
        ticket_quadruple_intersection_histogram[16-region-shape]: integer
        s4_geometry: integer
        s4_multiplicity: integer
        s4_geometry_identity: boolean
        saturated_quadruple_count: integer
        mass_bound_prediction: boolean
      comparison
        sealed_t3: integer
        sealed_t4: integer
        sealed_t5_plus: integer
        sealed_higher_order_residual: integer
        sealed_delta_covered: integer
        h4_plus: integer
        h4_plus_over_delta_covered: exact-rational or NOT_APPLICABLE
        j4_materiality_rule_pass: boolean
      checks
        portfolio_sha256_matches_sealed: boolean
        quadruple_histogram_total_identity: boolean
        region_sizes_nonnegative: boolean
        s4_geometry_identity: boolean
  classifications
    s4_geometry_identity: S4_GEOMETRY_IDENTITY_REPLICATED or FAILED
    mass_bound_prediction: MASS_BOUND_PREDICTS_ZERO_SPLIT or NOT_UNIVERSAL
    j4_materiality: WARRANTED or LOW_INFORMATION_VALUE
    global_optimum_status: UNKNOWN
  runtime_seconds
  peak_memory_bytes
  final_classification
```

All integers and rationals are exact. A rational uses the established
`{numerator, denominator, exact}` encoding. Missing, skipped, or failed cells
are not passes. A failed S4 identity prevents classification and result
publication.

## 6. Write set and forbidden actions

Only a later Owner packet may authorize this artifact family:

```text
docs/research/matrix-native-results/j4-geometry-extension-v1-result.json
docs/research/matrix-native-results/j4-geometry-extension-v1-report.md
docs/research/matrix-native-results/j4-geometry-extension-v1-attempt-ledger.json
tools/run_j4_geometry_extension_v1.py
```

This current design task creates none of those native result artifacts. It
does not create or lock a J4 preregistration because the value-of-information
gate did not warrant execution. No winning-space enumeration, real
constructor call, portfolio regeneration, push, PR, merge, Arm-C, P638
Zone-2, prediction, profitability, or global-optimum claim is permitted by
this schema.

## 7. Computational feasibility estimate

The sealed Phase-6 measurements give an observed constructor floor of
`946.713 s` total (about 15.8 minutes), with `0.021 s` for all triple geometry
after portfolios were materialized. Future J4 geometry has more ticket
subsets (`C(20,4)=4845` versus `C(20,3)=1140`) but still only `d<=6` and a
bounded 16-region exact recursion. Its native tail is not measured and must
be reported as observed at execution; it is not a reason to run now.

```text
COMPUTATIONAL_FEASIBILITY: FEASIBLE_WITHOUT_WINNING_SPACE_ENUMERATION
PORTFOLIO_REGENERATION_FOR_GATE: NOT_REQUIRED
PORTFOLIO_REGENERATION_IF_EXECUTED: REQUIRED
REAL_J4_EXECUTION: NOT_RUN
```
