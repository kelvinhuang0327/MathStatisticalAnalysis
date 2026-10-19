# MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1 — locked preregistration

Status: LOCKED before native Phase 10 execution ｜ 2026-08-27 ｜ B649 (Structure A) only

`TASK_ID: STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1`, Owner authorization `AUTHORIZE_STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1`. Fresh task worktree created from canonical commit `d024c52895b68191f20564c7d7494782f374ca4a` (tree `df025ea5a9c52a4fe06325c68c97dad4508b964b`).

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: SHA-256 of this exact frozen Markdown document
LOCK_SCOPE: PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1_ONLY
NATIVE_B649_PHASE10_EXECUTION: NOT_YET_RUN_AT_LOCK_TIME
PHASE9_AUTHORITY: IMMUTABLE_INPUT
PHASE9_RESEAL: FORBIDDEN
RUNG_COUPLING: NONE
ITERATION_CAP: NONE
RESTARTS: NONE
CANDIDATE_SAMPLING: NONE
RNG: NONE
MONTE_CARLO: NONE
SECOND_EXCHANGE: FORBIDDEN
PLATEAU_MOVES: FORBIDDEN
POST_RESULT_BUDGET_CHANGE: FORBIDDEN
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
REFERENCE_PROMOTION: NOT_AUTHORIZED
RUNTIME_PROMOTION: NOT_AUTHORIZED
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 0. Identity

```text
STUDY_ID:                    STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1
TASK_ID:                     STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1
REFINEMENT_METHOD_ID:        ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
LOTTERY:                     BIG_LOTTO
POOL_SIZE:                   49
DRAW_SIZE:                   6
PRIMARY_EVENT:               M3_PLUS
PRIMARY_EVENT_MIN_MATCHES:   3
K_SCOPE:                     [10, 15, 20]
RUNG_COUPLING:               NONE
CANONICAL_BASE_COMMIT:       d024c52895b68191f20564c7d7494782f374ca4a
CANONICAL_BASE_TREE:         df025ea5a9c52a4fe06325c68c97dad4508b964b
GLOBAL_OPTIMUM_STATUS:       UNKNOWN
```

## 1. Research question

Starting independently from the sealed Phase 9 best exact one-exchange neighbor at each B649 exposure rung $k \in \{10,15,20\}$, what deterministic portfolio is reached by repeatedly selecting the complete neighborhood's unique best exact-$M3+$ one-number-exchange neighbor and accepting it only when it is a strict improvement? Does each rung terminate with a complete exact one-exchange-local-optimum certificate?

The Phase 10 procedure-completion gate does not require an improvement over the Phase 9 seed. Zero accepted moves is a valid terminal result.

## 2. Immutable Phase 9 input authority

Authority path at the pinned base:

`docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json`

Authority file SHA-256:

`5c45204d227cc3750b9efe68ec9afeb3d83d6bd72104acbe319897fc94013e00`

Frozen seeds:

| $k$ | Phase 9 best-neighbor portfolio SHA-256 | Exact seed $Q_0$ | Exact Method E $Q$ used only for terminal delta |
|---:|:---|:---:|:---:|
| 10 | `4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5` | `90995/499422` | `212295/1165318` |
| 15 | `ba6f516af65c31246550827ddcdcff2fcbf3f588be336e6de959a59dc898d1c8` | `464027/1747977` | `927161/3495954` |
| 20 | `a107d9cb5c7e0def7b19ccf2a6d02306b25bc0efe3443ea9899f3a4755429a4a` | `171323/499422` | `17379/50666` |

Before any Phase 10 neighborhood execution, all three portfolio bytes are canonicalized, their SHA-256 values are recomputed, and every artifact SHA/Q field is required to equal the frozen identity above. Any mismatch stops execution as `PHASE9_SEED_IDENTITY_MISMATCH`.

## 3. Frozen iterative ascent rule

For each $k$ independently, let $P_0$ be that rung's sealed Phase 9 seed.

At iteration $i$:

1. Enumerate every portfolio obtainable from $P_i$ by selecting exactly one ticket slot, removing exactly one number from that ticket, and adding exactly one pool number not already in that ticket.
2. Canonicalize every ticket ascending and the complete portfolio lexicographically.
3. Reject any result containing a duplicate ticket.
4. De-duplicate equivalent complete portfolios.
5. Evaluate exact $M3+$ coverage for every unique legal neighbor.
6. Select the neighbor with maximum exact coverage. Resolve an exact coverage tie by the lexicographically smallest complete resulting portfolio.
7. Accept the selected neighbor if and only if $Q_{best} > Q(P_i)$ exactly.
8. When accepted, set $P_{i+1}$ to that neighbor and repeat the same complete procedure.
9. When $Q_{best} \le Q(P_i)$, reject the move and stop the rung.

There is no plateau move, iteration cap, restart, candidate sampling, random choice, Monte Carlo estimate, second exchange, or result-dependent budget expansion. Strict increase over a finite exact state space prevents cycles without an artificial limit.

## 4. Exact simultaneous evaluator

The implementation scans the complete finite winning space of $\binom{49}{6}=13,983,816$ draws once per iteration and represents tickets and draws as integer bit masks. It computes the current exact covered-draw count and, for each ticket slot, the exact coverage of every legal remove-one/add-one candidate through the following exhaustive partition of draws not covered by the remaining portfolio:

- a draw matching at least four numbers in the removed ticket remains covered by every one-number mutation;
- a three-match draw remains covered when the removed number is not one of its three matched ticket numbers, or when the added number occurs in the draw;
- a currently uncovered two-match draw becomes covered when the removed number is not one of its two matched ticket numbers and the added number occurs in the draw;
- draws with fewer than two matches cannot become an $M3+$ hit through one added number.

These cases are mutually exclusive and complete for $M3+$ under a one-number exchange. Candidate coverage remains an integer count over the full winning space and is converted to `Fraction`; floating point never participates in ranking or acceptance. Tests require all-neighbor parity against an independent brute-force winning-space scan on toy cases.

## 5. Required iteration and terminal certificates

Every iteration records at least:

- iteration index;
- complete input portfolio and SHA-256;
- exact input $Q$;
- unique legal neighbor count;
- complete deterministic best-neighbor portfolio and SHA-256;
- exact best-neighbor $Q$;
- exact delta;
- `accepted_move`.

Every accepted iteration must have exact `delta > 0`. The final iteration must have `accepted_move = false` and `Q_best <= Q_terminal` exactly.

Each rung returns:

- iteration count and accepted move count;
- terminal portfolio and SHA-256;
- exact terminal $Q$;
- exact terminal delta versus the Phase 9 seed;
- exact terminal delta versus historical Method E;
- `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED`;
- terminal certificate `PASS`.

## 6. Completion and deterministic reproduction gates

```text
PHASE10_EXECUTION_GATE = PASS iff:
- k=10 terminal certificate PASS;
- k=15 terminal certificate PASS;
- k=20 terminal certificate PASS;
- every accepted move has exact delta > 0;
- all invariants hold;
- a second fresh-process scientific result is byte-identical to the first.
```

The canonical result JSON uses sorted-key deterministic serialization with one trailing newline. Non-deterministic elapsed-time and peak-memory measurements are excluded from that scientific authority payload and reported separately. Native rungs execute sequentially in the order `10, 15, 20`.

## 7. Reference and claim boundary

Method E remains the historical constructor reference. Phase 9 portfolios are optimization inputs only. Phase 10 terminal portfolios do not become the research reference or runtime strategy in this task.

```text
CROSS_STRUCTURE_POLICY: NEXT_IF_PHASE10_PASSES
CROSS_STRUCTURE_EXECUTION: NOT_RUN
GLOBAL_OPTIMUM_STATUS: UNKNOWN
HISTORICAL_DRAWS: NOT_USED
DB_ACCESS: NO
REFERENCE_PROMOTION: NOT_AUTHORIZED
RUNTIME_PROMOTION: NOT_AUTHORIZED
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
SECOND_EXCHANGE: NOT_RUN
PUSH: NOT_RUN
PR: NOT_CREATED
```
