# STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1 — locked preregistration

Status: LOCKED before any native T539 candidate coverage inspection ｜ 2026-08-17 ｜
T539 only

`TASK_ID: STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1`,
Owner authorization
`AUTHORIZE_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1`.
Locks the already-canonical Phase-7 constructor
`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1` against current `origin/main`
`f1bd254c5d8d753b4672a03edee1322d3d567552` for a T539-only replication.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256
PREREGISTRATION_HASH_SHA256:  3ecd753f664e7a2d558df8a2a9e43f9ab93105b0713e1a58d0e8d67abebee59d
LOCK_SCOPE: THIS_EXACT_T539_REPLICATION_ONLY
REAL_T539_CANDIDATE_COVERAGE: NOT_YET_RUN_AT_LOCK_TIME
B649_RERUN: FORBIDDEN
ARM_C_RERUN: FORBIDDEN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE: FORBIDDEN
```

## 0. Identity

```text
STUDY_ID:               STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
HYPOTHESIS_FAMILY_ID:   DIVERSIFICATION
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
CANONICAL_INPUT_COMMIT: f1bd254c5d8d753b4672a03edee1322d3d567552
CANONICAL_INPUT_TREE:   6be80c450de4eed82166df5311d5e1ded6d172f9
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
```

## 1. Research question

Does the unchanged generic constructor
`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`, evaluated at native T539
`(pool_size=39, draw_size=5)`, beat exact random and greedy Arm-B on
T539 `M3+` under the locked five-clause replication gate?

## 2. Frozen scope

```text
LOTTERY:            DAILY_539  pool=39, draw=5
K_LADDER:           [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:      M3+ (minimum_matches=3)
SECONDARY_EVENTS:   NOT_RUN
MONTE_CARLO:        NONE
HISTORICAL_DRAWS:   NOT_USED
B649:               SEALED AUTHORITY ONLY (NOT RERUN)
ARM_C:              NOT_RUN (no T539 frontier exists)
P638:               NOT_RUN
```

## 3. Frozen constructor

```text
RULE:      unused legal ticket minimizing (max_overlap, sum_overlap, ticket)
TIE_BREAK: max, then sum, then lexicographic ticket
WEIGHTS:   none
RANDOM:    none
HISTORY:   none
STOPPING:  exactly ticket_count tickets
PREFIX:    portfolio(k) == portfolio(20)[:k]
ENTRY:     greedy_minmax_then_sum_overlap_portfolio(39, 5, k)
```

## 4. Frozen comparators

```text
A = cyclic_sidon_shift_t539.sidon_shift_portfolio
    sealed diversification-coverage-t539-v1-result.json
    hash dd926b0ea045cb57be4e1cd10bc16e3d524e3b6acae5b34a805ed01f437e334e
    blob 013f4fbc1de6d62966b4c09e6f4bca5f5ae8a032
B = greedy_min_overlap_portfolio(39, 5, k)
    sealed greedy-min-overlap-constructor-t539-v1-result.json
    hash cb786aac3fc04ea2f1c302b37120831a2296869e94e7d397260d5745420ff8bd
    blob 346544f3a644a3083ef9863bd7f35a345a50f531
E = GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
D = exact_coverage_baseline.exact_random_portfolio_coverage
    identity: Arm-B q.c.3 == Sidon q_random.3
C = NOT_RUN
```

Sealed exact `M3+` fractions (copied into the hashed lock, aligned with
the ladder) are the identity checks for A, B, and D.

```text
Q_A: 1927/191919, 1915/63973, 9515/191919, 18754/191919, 1325/9139, 1940/10101
Q_B: 1927/191919, 1927/63973, 9635/191919, 2722/27417, 9391/63973, 37136/191919
Q_D: 1927/191919,
     797140793129/26731123085589,
     5589975608192723862911/113604563250262928889831,
     210136421818019142830254085117764470705343/2189141756352303974883307976771119210042635,
     4425648389458544938963379911506957588946026049013937458614804247/31505246626552976138504202934751941466931572184558599814136269720,
     1715441071920970397176193765176714544329158433866151866864960526518171695862708197/9385896987682404793826377339653018372590533675528860392291054310717822221458647480
```

## 5. Frozen metrics and T539 replication gate

Reported geometry: max/mean pairwise overlap, pair-intersection
histogram, overlap-1 pair count, S2/redundancy proxy, unique-number
coverage, reuse dispersion, duplicates, and the lex objective
`(max, sum)` required by clause 5.

`T539_REPLICATION_GATE` passes iff all hold:

1. `Q_E > Q_D` for every `k > 1`
2. `Q_E >= Q_B` for every `k > 1`
3. `Q_E > Q_B` at `k in {10, 15, 20}`
4. `duplicate_tickets == 0` at every ladder `k`
5. candidate does not increase the lexicographic `(max, sum)` objective
   relative to Arm-B at any tested `k` where coverage superiority
   (`Q_E > Q_B`) is claimed

Pass classification: `T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED`
and `P638_REPLICATION_ELIGIBLE: YES`.

Fail classification: `DO_NOT_ADVANCE_THIS_EXACT_T539_REPLICATION` and
`P638_REPLICATION_ELIGIBLE: NO`. Failure does not invalidate the sealed
B649 Phase-7 cell.

## 6. Claim boundary

```text
ALLOWED: exact deterministic T539 combinatorial replication evidence
NOT_PROVEN: global optimum, predictive advantage, profitability,
            prize/economic value, P638 replication, universal portability
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 7. No-rescue

The locked constructor key, ladder, event, sealed A/B/D values,
geometry metrics, and five gate clauses must not change after any native
`Q_E` is seen. B649 may not be rerun. Arm-C may not be manufactured.
P638 may not start in this task.
