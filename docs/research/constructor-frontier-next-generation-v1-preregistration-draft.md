# STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1 — preregistration DRAFT

Status: DRAFT — NOT LOCKED ｜ 2026-08-17 ｜ native constructor comparison
not executed

This draft was produced by
`STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_DESIGN_R1`.
It is not a Matrix result and has no hash.  A later Owner-authorized
task must either approve this exact draft or revise and re-draft it,
then create and verify a lock hash before invoking any native
portfolio constructor or winning-space enumeration.

```text
PREREGISTRATION_LOCKED: NO
HASH: NOT_COMPUTED
REAL_PHASE7_EXECUTION: NOT_RUN
ARM_C_RERUN: NOT_RUN
```

## 0. Identity

```text
STUDY_ID:              STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
STARTING_CLASSIFICATION:
  REDUNDANCY_REDUCTION_REPLICATED
  PAIRWISE_COLLISION_REDUCTION_REPLICATED
  S3_GEOMETRY_IDENTITY_REPLICATED
  J4_GEOMETRY_EXTENSION_LOW_INFORMATION_VALUE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 1. Research question and disclosed prior observation

Does the deterministic constructor `GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`:

1. beat exact random expected coverage at every tested `k > 1`;
2. beat sealed greedy Arm-B at every tested `k > 1` on the sealed-gap
   rungs, and never lose to Arm-B on the other rungs;
3. capture at least one quarter of the sealed B649 Arm-C-minus-Arm-B
   coverage gap at `k = 20`;
4. remain a deterministic `(pool_size, draw_size, ticket_count)` rule
   with no Arm-C search?

The positive Arm-B-minus-Sidon and Arm-B-minus-random directions, the
pairwise/`S2` primary mechanism, the `S3` identity, the J4 low-value
gate, and the sealed B649 Arm-C coverages are already sealed.  They
are inputs, not discoveries of this study.

Arm-C is a **read-only sealed B649 frontier reference**.  It is not an
experimental arm.

## 2. Frozen lottery, exposure, and event scope

```text
FIRST_LOTTERY:      BIG_LOTTO  pool=49, draw/ticket=6, event=M3_PLUS
CONDITIONAL:        DAILY_539  pool=39, draw/ticket=5, event=M3_PLUS
                    POWER_LOTTO_ZONE1 pool=38, draw/ticket=6, event=ZONE1_M3_PLUS
K_LADDER:           [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:      minimum_matches=3 only
SECONDARY_EVENTS:   NOT_RUN_BY_DEFAULT
MONTE_CARLO:        NONE
HISTORICAL_DRAWS:   NOT_USED
P638_ZONE2:         OUT_OF_SCOPE
ARM_C_RERUN:        FORBIDDEN
PHASE_5_RERUN:      FORBIDDEN
PHASE_6_RERUN:      FORBIDDEN
```

`k = 1` is an identity/sanity boundary and is excluded from replicated
`k > 1` decision predicates.

T539 and P638 Zone-1 are not in the initial execution.  They become
eligible only after `B649_ADVANCE_GATE` passes.

## 3. Frozen arms

```text
A:          canonical cyclic Sidon-shift portfolio
B:          canonical greedy min-max-overlap portfolio
CANDIDATE:  greedy_minmax_then_sum_overlap_portfolio(n, d, k)
D:          exact random expected coverage (closed form)
C_SEALED:   sealed B649 Q_C(k) from
            diversification-constructor-frontier-b649-v1-result.json
            blob 169df1649ff0b8247ef5c779e8104079ae574cf4
            USED ONLY AS A FRONTIER REFERENCE ON B649
```

At execution, the maximum `k = 20` portfolio is generated once per
prefix-stable arm (A, B, CANDIDATE) and all smaller portfolios are
exact prefixes.  Arm-C is not generated.

Implementation must use:

- A: existing `cyclic_sidon_shift.sidon_shift_portfolio` (and the T539
  / P638 modules only if replication is authorized);
- B: existing `greedy_min_overlap_constructor.greedy_min_overlap_portfolio`
  (and the T539 / P638 wrappers only if replication is authorized);
- CANDIDATE: `greedy_minmax_then_sum_overlap_constructor.greedy_minmax_then_sum_overlap_portfolio`;
- D: existing `exact_coverage_baseline` closed form.

No copied algorithm, new weight, offset, seed, random search,
optimizer call, or post-result adjustment.

The future clean canonical `origin/main` commit, tree, input Git
blobs, and the locked preregistration hash must be recorded before the
first native call.  Any mismatch stops execution.  The design-time
authority snapshot is commit
`3b3f953bf9857b85094e9f26c6ef5301ba3561e5`, tree
`6774dcade3c662d0ab3b757710e9e0aafcc3900b`.

## 4. Frozen constructor contract (CANDIDATE)

```text
RULE:       unused legal ticket minimizing (max_overlap, sum_overlap, ticket)
TIE_BREAK:  max, then sum, then lexicographic ticket
DUPLICATES: excluded by construction; required count == 0
STOPPING:   exactly ticket_count tickets
RANDOM:     none
HISTORY:    none
OUTCOMES:   none
WEIGHTS:    none
PREFIX:     portfolio(k) == portfolio(20)[:k]
```

## 5. Frozen metric semantics

Exact coverages `Q_A`, `Q_B`, `Q_E` (CANDIDATE), `Q_D`, and sealed
`Q_C`:

```text
DELTA_RANDOM_E(k) = Q_E(k) - Q_D(k)
DELTA_ARM_B_E(k)  = Q_E(k) - Q_B(k)
FRONTIER_CAPTURE_RATIO_CANDIDATE(k) =
    (Q_E(k) - Q_D(k)) / (Q_C(k) - Q_D(k))
    if Q_C(k) > Q_D(k) else NOT_APPLICABLE
B_TO_C_GAP_CAPTURE(k) =
    (Q_E(k) - Q_B(k)) / (Q_C(k) - Q_B(k))
    if Q_C(k) > Q_B(k) else NOT_APPLICABLE_TIED_FRONTIER
```

`Q_C` is the sealed B649 value.  It is not defined as an experimental
output.  Off B649, `FRONTIER_CAPTURE_RATIO_CANDIDATE` and
`B_TO_C_GAP_CAPTURE` are `NOT_APPLICABLE_NO_SEALED_ARM_C`.

Every rational is a reduced `fractions.Fraction`.  Floats are
presentation-only.

Also persist, for A, B, and CANDIDATE at every `k`: max pairwise
overlap, exact mean pairwise overlap, full pair-intersection
histogram, unique-number coverage, reuse vector, reuse-dispersion
population variance, and duplicate count.  These geometry fields are
descriptive.  They do not enter the advance gate except
`duplicate_tickets == 0`.

## 6. Frozen B649 advance gate

```text
B649_ADVANCE_GATE = PASS iff all hold:
  1. Q_E(k) > Q_D(k)                  for k in {3,5,10,15,20}
  2. Q_E(k) >= Q_B(k)                 for k in {3,5,10,15,20}
  3. Q_E(k) > Q_B(k)                  for k in {10,15,20}
  4. B_TO_C_GAP_CAPTURE(20) >= 1/4
  5. duplicate_tickets == 0           at every ladder k
  6. CANDIDATE invoked only as
     greedy_minmax_then_sum_overlap_portfolio(49, 6, k)
  7. ARM_C_RERUN == NOT_RUN
```

Clause 4 uses the pre-registered constant `1/4`.  It is not revised
after `Q_E` is seen.

## 7. Frozen cross-lottery replication rule

```text
IF B649_ADVANCE_GATE = PASS:
  run DAILY_539, then POWER_LOTTO_ZONE1
  comparators: A, B, CANDIDATE, D only
  require Q_E(k) > Q_D(k) and Q_E(k) >= Q_B(k) for every k>1
  require Q_E(k) > Q_B(k) for every tested k exceeding disjoint capacity
    DAILY_539:         k in {10,15,20}
    POWER_LOTTO_ZONE1: k in {10,15,20}
ELSE:
  T539: NOT_RUN
  P638: NOT_RUN
```

## 8. Classification rule

On B649, after the gate is evaluated:

```text
if B649_ADVANCE_GATE = PASS:
  CANDIDATE_IMPROVES_ON_ARM_B_TOWARD_SEALED_FRONTIER
else if Q_E(k) < Q_B(k) for any k>1:
  CANDIDATE_DOES_NOT_DOMINATE_ARM_B
else if B_TO_C_GAP_CAPTURE(20) < 1/4:
  CANDIDATE_GAP_CAPTURE_BELOW_MATERIALITY
else:
  CANDIDATE_ADVANCE_GATE_FAILED
```

```text
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

always, including on a pass.

## 9. Claim boundary

```text
predictive_advantage:   NOT_TESTED
prize_value_advantage:  NOT_TESTED
economic_optimality:    NOT_TESTED
global_optimum_status:  UNKNOWN
p638_zone2:             NOT_RUN
arm_c_rerun:            NOT_RUN
monte_carlo:            false
historical_draws_read:  false
```

## 10. No-rescue

The locked arms, ladder, event, constructor key, materiality constant
`1/4`, advance gate, and replication rule must not change after any
native `Q_E` is seen.  No weighted variant may be added.  Arm-C may
not be rerun to enlarge the frontier.  Budget may not be expanded to
rescue a failed gate.
