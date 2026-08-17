# STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1 — deterministic execution plan/schema

Status: DESIGN SCHEMA — no execution tool or Matrix result exists ｜
2026-08-17

This document is normative for a future, separately authorized
lock-and-execute task.  It specifies deterministic input resolution,
constructor invocation, sealed Arm-C reference loading, serialized
fields, and exact invariants.  It does not authorize or perform native
execution.

## 1. Fixed configuration

```text
study_id: STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1
ladder: [1, 3, 5, 10, 15, 20]
minimum_matches: 3
prefix_stable_arms: [SIDON, ARM_B, CANDIDATE]
frontier_reference: C_SEALED   # B649 only; never constructed
random_arm: D
delta_direction: CANDIDATE_MINUS_ARM_B
secondary_events: []
monte_carlo: false
historical_draws: false
arm_c_rerun: false
```

| key | pool `n` | draw `d` | winner count | Sidon | Arm-B | CANDIDATE | when |
|---|---:|---:|---:|---|---|---|---|
| `BIG_LOTTO` | 49 | 6 | 13,983,816 | `cyclic_sidon_shift.sidon_shift_portfolio` | `greedy_min_overlap_portfolio(49,6,k)` | `greedy_minmax_then_sum_overlap_portfolio(49,6,k)` | always first |
| `DAILY_539` | 39 | 5 | 575,757 | `cyclic_sidon_shift_t539.sidon_shift_portfolio` | `greedy_min_overlap_portfolio_t539` | `greedy_minmax_then_sum_overlap_portfolio(39,5,k)` | only if B649 gate passes |
| `POWER_LOTTO_zone1` | 38 | 6 | 2,760,681 | `cyclic_sidon_shift_p638.sidon_shift_portfolio` | `greedy_min_overlap_portfolio_p638_zone1` | `greedy_minmax_then_sum_overlap_portfolio(38,6,k)` | only if B649 gate passes |

Random expected coverage uses `exact_coverage_baseline` at the same
`(n, d, k, minimum_matches=3)`.

Sealed B649 `Q_C(k)` is copied from

```text
path: docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-result.json
blob: 169df1649ff0b8247ef5c779e8104079ae574cf4
field: q.c.3[k].exact
```

The optimizer modules must not be imported by the execution entry
point.

The future execution records the then-current canonical commit/tree
and exact input blobs.  The design-time authority snapshot is
`3b3f953bf9857b85094e9f26c6ef5301ba3561e5` /
`6774dcade3c662d0ab3b757710e9e0aafcc3900b`.

## 2. Pre-execution gate

Before a native constructor call:

1. Require a clean dedicated worktree at the Owner-approved canonical
   `origin/main` commit.
2. Read and verify every applicable repository instruction.
3. Verify the locked preregistration path and SHA-256.
4. Verify source matrix IDs and exact input Git blobs, including the
   sealed Arm-C result blob above.
5. Verify no historical-draw path, P638 Zone-2 module, bounded
   optimizer module, or score-guided portfolio constructor is imported
   by the execution entry point.
6. Record starting HEAD/tree/status and the future output allowlist.

Any failed check is terminal for that execution attempt.

## 3. Portfolio materialization

For `BIG_LOTTO`, and later for each authorized replica lottery:

```text
sidon_20      = SIDON_CONSTRUCTOR(20)
arm_b_20      = ARM_B_CONSTRUCTOR(20)
candidate_20  = CANDIDATE_CONSTRUCTOR(20)

for k in ladder:
    sidon_k     = sidon_20[:k]
    arm_b_k     = arm_b_20[:k]
    candidate_k = candidate_20[:k]
```

Never rebuild a smaller prefix independently.  Never call Arm-C.
For each ordered maximum portfolio, persist a SHA-256 over a canonical
UTF-8 JSON encoding (`separators=(',', ':')`, no whitespace, tickets
and numbers in existing order).  Assert:

```text
len(portfolio_k) == k
all tickets have d distinct ascending numbers in 1..n
portfolio_k == portfolio_20[:k]
duplicate_count == 0
candidate_k[:floor(n/d)] == arm_b_k[:floor(n/d)]
```

The last assertion is the disjoint-prefix identity of the two greedy
rules and is required on every lottery.

## 4. One-pass exact coverage algorithm

Convert each ticket to an integer bit mask once.  For each authorized
lottery, stream `itertools.combinations(range(1, n+1), d)` in
lexicographic order.  The normative algorithm is equivalent to:

```text
N[arm][k] = integer array of length k+1, initialized to zero
arms = [SIDON, ARM_B, CANDIDATE]

for winner in all C(n, d) winners:
    winner_mask = mask(winner)
    for arm in arms:
        prefix_hits = 0
        for index, ticket_mask in enumerate(portfolio_20[arm], start=1):
            if bit_count(winner_mask & ticket_mask) >= 3:
                prefix_hits += 1
            if index in ladder:
                N[arm][index][prefix_hits] += 1
```

Do not retain winners or a historical table.  Do not evaluate Arm-C.
`Q_arm(k) = sum_{c>=1} N[arm][k][c] / C(n, d)` as a reduced Fraction.

`Q_D(k)` is the closed-form exact random expected coverage.  `Q_C(k)`
on B649 is the sealed exact fraction; it is never produced by this
loop.

## 5. Deterministic derivation order

For each `(lottery, arm, k)` in `{SIDON, ARM_B, CANDIDATE}`:

1. `total_winning_combinations = sum_c N_c`.
2. `covered = sum_{c>=1} N_c`.
3. `Q = covered / C(n, d)` reduced by `fractions.Fraction`.
4. geometry from the same ordered prefix portfolio (pair histogram,
   max, exact mean, reuse vector, unique coverage, duplicate count).
5. optional independent `S2_GEOMETRY = sum_r n_r H_3(n, d, r)` using
   the already-sealed helper, as a descriptive check, not a gate
   input.

Then derive CANDIDATE-minus-Arm-B and CANDIDATE-minus-random deltas,
`FRONTIER_CAPTURE_RATIO_CANDIDATE` and `B_TO_C_GAP_CAPTURE` on B649
only, the B649 advance gate, and — only if that gate passes and the
Owner has authorized replication — the T539 / P638 comparisons.

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
- optional presentation floats live under an explicitly suffixed key
  such as `reuse_dispersion_float` and are never load-bearing.

Integer-indexed maps serialize keys as base-10 strings in numerical
order.  JSON is emitted with `indent=2`, `sort_keys=True`, one
trailing newline.

## 7. Normative result schema

The future result root must contain all fields below.  Bracketed names
are dynamic map keys, not optional fields.

```text
root
  study_id: exact constant
  source_type: STRATEGY_MATRIX_NATIVE
  evidence_type: EXACT_COMBINATORIAL
  proposed_constructor_id: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
  canonical_input
    repository
    commit
    tree
    locked_preregistration_path
    locked_preregistration_sha256
    input_blobs[path]: full Git blob OID
    sealed_arm_c_result_path
    sealed_arm_c_result_blob
  scope
    historical_draws_read: false
    monte_carlo: false
    p638_zone2: NOT_RUN
    arm_c_rerun: NOT_RUN
    secondary_events: NOT_RUN
    predictive_advantage: NOT_TESTED
    prize_value_advantage: NOT_TESTED
    economic_optimality: NOT_TESTED
    global_optimum_status: UNKNOWN
  ladder: [1,3,5,10,15,20]
  minimum_matches: 3
  per_lottery[lottery]
    lottery_type
    zone: string or NOT_APPLICABLE
    pool_size
    draw_size
    total_winning_combinations
    executed: true | false
    skip_reason: null | B649_ADVANCE_GATE_FAILED | NOT_YET_REACHED
    per_arm[arm]
      portfolio_sha256
      per_k[k]
        q
        geometry
        n_c
    q_random[k]
    q_c_sealed[k]            # B649 only; omitted elsewhere
    frontier_capture_ratio_candidate[k]
    b_to_c_gap_capture[k]
  b649_advance_gate: PASS | FAIL | NOT_EVALUATED
  classification
  runtime_seconds
  peak_memory_bytes
```

## 8. Required invariants (any violation is terminal)

```text
sum_c N_c == C(n, d)
Q_E(1) == Q_B(1) == Q_A(1) == Q_D(1)
candidate prefix-stable
arm_b prefix-stable
candidate[:floor(n/d)] == arm_b[:floor(n/d)]
duplicate_count == 0
ARM_C_RERUN == NOT_RUN
no optimizer import
```

## 9. Computational envelope (planning only)

Sealed Arm-B generation plus one winning-space pass, not a new
measurement:

```text
B649 constructor floor (Arm-B sealed):     ~13 min
B649 winning-space pass (Phase-5 sealed):  ~36 s
T539 constructor floor:                    ~0.5 min
P638 Zone-1 constructor floor:             ~2.5 min
Arm-C:                                     NOT IN THIS BUDGET
```

CANDIDATE is the same scan order as Arm-B plus a running sum, so the
planning envelope is `COMPARABLE_TO_ARM_B`.  Replication is not
started unless the B649 gate passes, so the default authorized
sequence is B649 only.

## 10. Output allowlist (future lock must name exact paths)

```text
docs/research/matrix-native-results/constructor-frontier-next-generation-v1-preregistration.md
docs/research/matrix-native-results/constructor-frontier-next-generation-v1-preregistration-hash.json
docs/research/matrix-native-results/constructor-frontier-next-generation-v1-result.json
docs/research/matrix-native-results/constructor-frontier-next-generation-v1-report.md
docs/research/matrix-native-results/constructor-frontier-next-generation-v1-attempt-ledger.json
```

This design task must not write any of those result paths.
