# STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_V1 — result

Status: COMPLETE — `PHASE11_EXECUTION_GATE: PASS` ｜ 2026-08-28 ｜ T539 and P638 Zone-1

`INTENT: code does deterministic Phase-11 orchestration and certificate serialization; the check/task expects exact native Method-E regeneration plus terminal local-optimum evidence; the opened spec says to invoke the unchanged canonical Phase-10 algorithm with no plateau moves, cap, sampling, RNG, or second exchange.`

The canonical `ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1` implementation was
executed independently for all six requested structure/rung combinations.
Every rung reached a complete exact one-exchange local-optimum certificate.
Zero accepted moves occurred for T539 k=10 and k=20, and are valid terminal
results.

Preregistration SHA-256:
`f44ac9547828794a861898330744fc8535a48c818fa35f609d30d3863f6fa1df`.

Canonical result SHA-256:
`c7904f716a61fb6b43df2091664ef55a1972b9212cac3490133d0accd4ae7290`
(502,348 bytes).

## 0. Identity and authority

```text
STUDY_ID:                    STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_V1
TASK_ID:                     STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1
REFINEMENT_METHOD_ID:        ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
OWNER_AUTHORIZATION:         AUTHORIZE_STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1
CANONICAL_METHOD_IMPLEMENTATION: src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py
CANONICAL_BASE_COMMIT:       1de7bf0d51160802115aa7ade416e5e717a00461
CANONICAL_BASE_TREE:         895696e5c2ab87b7ebe1c294a2a32edcdefefe43
K_SCOPE:                     [10, 15, 20]
RUNG_COUPLING:               NONE
CROSS_STRUCTURE_STATE_SHARING: NONE
GLOBAL_OPTIMUM_STATUS:       UNKNOWN
```

The frozen Phase-7 authorities were verified before their corresponding
native regeneration:

| Structure | Phase-7 authority SHA-256 | Regenerated raw k=20 Method-E SHA-256 | Exact Method-E Q at k=10,15,20 |
|---|---|---|---|
| DAILY_539 | `5e8a52d5e841b9c7e0f29711ded55e717421cc0334c272bd94ac2ee84ebe9474` | `81830474195db8ae460367b71ecea271a390aaa432c5af4bd78fc18c65c09b60` | `2734/27417`, `9475/63973`, `152/777` |
| POWER_LOTTO_ZONE1 | `77e6df9e8baa8202c886d6b30808b5c78993bfda13b4eab7710ae60f5ea139ed` | `59182264db6be95ab51dff64f0548f1a5f1163ca33e8b4a646fe02db383d8d85` | `52270/145299`, `126653/250971`, `578195/920227` |

The Phase-7 constructor stores generation-order portfolios. The canonical
Phase-10 implementation canonicalizes its input before ascent; the result
records both representations. Canonical k=20 seed hashes were
`2015e3f326a136ab34ea8fe2b98f15fd0a519cb44df28f418d488d5b6d6a33f7` for
T539 and `94e969e7c87b8781a9a6fe7f008b68a3098d9587de697eec35556f20dfcfdf57`
for P638 Zone-1.

## 1. Terminal certificates

`Terminal best Δ` is the exact final-iteration best-neighbor Q minus the
terminal Q. A non-positive value is required for the terminal rejection.

| Structure | k | Seed Method-E SHA-256 | Seed exact Q | Unique terminal neighbors | Moves / iterations | Terminal exact Q | Δ terminal vs Method-E | Terminal best Δ | Terminal portfolio SHA-256 | Classification |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| DAILY_539 | 10 | `6a938cdc39299fb5545ad95dd6ce893413637acfa95abd2f0c861168c06521cc` | `2734/27417` | 1,700 | 0 / 1 | `2734/27417` | `0/1` | `0/1` | `6a938cdc39299fb5545ad95dd6ce893413637acfa95abd2f0c861168c06521cc` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| DAILY_539 | 15 | `2fafb5277e561782b34e82bf8d7eb3b84e99a166cd6256214891beb2330e932b` | `9475/63973` | 2,550 | 4 / 5 | `9491/63973` | `16/63973` | `0/1` | `09734dae0c4c752d797f54ef7cbfa60bedb2e2e5b971bca7188a953da60c2a51` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| DAILY_539 | 20 | `2015e3f326a136ab34ea8fe2b98f15fd0a519cb44df28f418d488d5b6d6a33f7` | `152/777` | 3,400 | 0 / 1 | `152/777` | `0/1` | `0/1` | `2015e3f326a136ab34ea8fe2b98f15fd0a519cb44df28f418d488d5b6d6a33f7` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| POWER_LOTTO_ZONE1 | 10 | `3a03740b2f1b5ca676bc5abdaba331ed1e5dff22e68155dc74e13c6ec0e6cab1` | `52270/145299` | 1,920 | 11 / 12 | `331675/920227` | `1895/2760681` | `0/1` | `47b8b68929e3ac99a9fb5029fc4465dafe9cefbbe2202e25c3a2d0b8ab342a57` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| POWER_LOTTO_ZONE1 | 15 | `365e8552780e46ec2c81e82cc3708a29bc7665b8642d452535e4f78386b06dbc` | `126653/250971` | 2,880 | 21 / 22 | `465452/920227` | `167/145299` | `-1/2760681` | `be4dfc831ba8ccf31b6c85e869970b51f3ea8472d5283e4bbc42b2127d0d755c` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| POWER_LOTTO_ZONE1 | 20 | `94e969e7c87b8781a9a6fe7f008b68a3098d9587de697eec35556f20dfcfdf57` | `578195/920227` | 3,840 | 24 / 25 | `157958/250971` | `2953/2760681` | `-1/920227` | `63ca63cac6a94fc956fe344ff026818d3322f6f3610c9ed7d7004c5eec894728` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |

The terminal iterations had `accepted_move = false` in all six rungs and
their exact best-neighbor Q was less than or equal to the terminal Q. Every
accepted iteration had exact positive delta, and the serialized input/best/
terminal portfolio SHA-256 values were recomputed by the focused tests.

## 2. Deterministic reproduction

Two complete fresh Python processes ran the same command and wrote the same
scientific result bytes. Performance timings were printed only and are not
part of the canonical JSON.

```text
RUN1_RESULT_SHA256:          c7904f716a61fb6b43df2091664ef55a1972b9212cac3490133d0accd4ae7290
RUN1_RESULT_BYTES:           502348
RUN2_RESULT_SHA256:          c7904f716a61fb6b43df2091664ef55a1972b9212cac3490133d0accd4ae7290
RUN2_RESULT_BYTES:           502348
FRESH_PROCESS_BYTE_IDENTITY: PASS
```

Observed runtime summaries (not serialized into the scientific result):

```text
FINAL-TREE RUN 1 — T539 Method-E regeneration: 30.672753s
FINAL-TREE RUN 1 — P638 Zone-1 Method-E regeneration: 155.613617s
FINAL-TREE RUN 1 — T539 ascent seconds k=10,15,20: 0.900697, 6.179888, 1.646205
FINAL-TREE RUN 1 — P638 ascent seconds k=10,15,20: 66.875210, 170.096054, 242.510631
FINAL-TREE RUN 2 — T539 Method-E regeneration: 31.586185s
FINAL-TREE RUN 2 — P638 Zone-1 Method-E regeneration: 177.236741s
FINAL-TREE RUN 2 — T539 ascent seconds k=10,15,20: 0.879176, 6.145565, 1.582834
FINAL-TREE RUN 2 — P638 ascent seconds k=10,15,20: 73.647323, 177.867133, 240.043105
```

## 3. Verification

```text
PHASE11_EXECUTION_GATE: PASS
K10/K15/K20 T539 TERMINAL_CERTIFICATE: PASS / PASS / PASS
K10/K15/K20 P638_ZONE1 TERMINAL_CERTIFICATE: PASS / PASS / PASS
EVERY_ACCEPTED_MOVE_STRICT: TRUE
P638_ZONE2: NOT RUN
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

Commands and observed outcomes:

- The Phase-11 runner completed twice with exit status 0 and printed
  `PHASE11_EXECUTION_GATE: PASS` both times.
- `PYTHONPATH=.:src ... pytest -p no:cacheprovider` on the impacted
  canonical-ascent regression slice plus the Phase-11 focused tests:
  `18 passed` on the final source tree.
- Ruff on the new runner and test, Pyright on the new runner and test
  (`0 errors, 0 warnings, 0 informations`), plus `git diff --check`: all
  checks passed.

## 4. Attempt ledger

1. The initial execution regenerated T539 k=20 with the required frozen hash,
   then stopped before native ascent because the runner incorrectly required
   each raw constructor prefix to already be canonical. No result artifact
   was written. The runner was corrected to retain raw source-prefix hashes
   and pass canonicalized prefixes to the unchanged canonical ascent method.
2. A corrected pre-fix execution completed all six rungs and wrote the result;
   its scientific SHA-256 was later invalidated when the runner received the
   type-only JSON-parser cast fix.
3. A fresh pre-fix process reproduced the same result bytes; that evidence was
   also invalidated by the later source edit.
4. Pyright then found five strict-typing errors. The pre-fix Judge stopped
   without a verdict, the five JSON-parser casts were added, and the final
   source tree was checked with Pyright and the focused regression slice.
5. Final-tree run 1 and final-tree run 2 each completed all six rungs with
   exit status 0 and reproduced the result SHA-256 above.

The initial missing `.venv/bin/python` and unavailable global `ruff` probes
were resolved by using the existing Python 3.13.8 environment at the main
checkout's absolute path with `PYTHONPATH=.:src`; no product or authority
change was made for those environment differences.

One read-only diff probe temporarily redirected two untracked-file diff
outputs to `/tmp/phase11-runner.diff` and `/tmp/phase11-tests.diff`; those
exact temporary files were deleted before the final state and are listed in
the ledger below.

## 5. Filesystem and lifecycle ledger

```text
FILES_WRITTEN_DURING_TASK:
- docs/research/matrix-native-results/strategy-matrix-phase11-t539-p638-zone1-iterative-exact-1exchange-replication-v1-preregistration.md
- docs/research/matrix-native-results/strategy-matrix-phase11-t539-p638-zone1-iterative-exact-1exchange-replication-v1-result.json
- docs/research/matrix-native-results/strategy-matrix-phase11-t539-p638-zone1-iterative-exact-1exchange-replication-v1-report.md
- tests/unit/test_strategy_matrix_phase11_t539_p638_zone1_iterative_exact_1exchange_replication.py
- tools/run_strategy_matrix_phase11_t539_p638_zone1_iterative_exact_1exchange_replication.py
- /tmp/phase11-runner.diff
- /tmp/phase11-tests.diff
- tools/__pycache__/* (ignored Python cache)
- .ruff_cache/* (ignored cache created by the delta Judge)
FILES_RETAINED_AT_END: the five task-created repository artifacts above
FILES_DELETED_BEFORE_END:
- /tmp/phase11-runner.diff
- /tmp/phase11-tests.diff
- tools/__pycache__/*
- .ruff_cache/*
TASK_CREATED_FILES_RETAINED: the five task-created repository artifacts above
TASK_CREATED_FILES_DELETED: the two /tmp diff files and ignored tools/__pycache__/*
REVIEW_CREATED_FILES_DELETED: ignored .ruff_cache/* created by the delta Judge
PRE_EXISTING_FILES_RETAINED_UNCHANGED: all other checked-in files
PRE_EXISTING_FILES_MODIFIED_AND_RATIFIED: NONE
FILES_MODIFIED_DURING_TASK: the five task-created repository artifacts above
REPOSITORY_FILES_MODIFIED: the five task-created repository artifacts above
TOOLCHAIN_RUNTIME_OUTPUTS_CREATED: /tmp diff files, tools/__pycache__/*, and .ruff_cache/*; all deleted
TOOLCHAIN_RUNTIME_OUTPUTS_MODIFIED: NONE
PRE_EXISTING_RUNTIME_OUTPUTS_RETAINED_UNCHANGED: NONE
WORKTREE_MATERIALIZATION_CREATED: /Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1
WORKTREE_MATERIALIZATION_UPDATED: NONE
WORKTREE_MATERIALIZATION_REMOVED: NONE
GIT_NETWORK_METADATA_WRITES: NONE
GIT_WORKTREE_METADATA_WRITES: fresh worktree registration only
HARNESS_GIT_METADATA_WRITES: NONE
IMPLEMENTATION_LIFECYCLE_STATUS: COMPLETE
COMMIT_AUTHORIZED: YES
PR_PUBLICATION_STATUS: NOT_APPLICABLE
POSTMERGE_LIFECYCLE_STATUS: NOT_APPLICABLE
BRANCH_CLEANUP_STATUS: NOT_APPLICABLE
FULL_PR_LIFECYCLE_CLOSED: NO
```

## 6. Claim boundary and lifecycle

This result certifies local optimality only within each terminal portfolio's
complete legal exact one-number-exchange neighborhood. It does not establish
global optimality, predictive advantage, profitability, prize/economic value,
a new research reference, a runtime strategy, or any P638 Zone-2 result.

```text
HISTORICAL_DRAWS: NOT_USED
RNG: NONE
MONTE_CARLO: NONE
DB_ACCESS: NO
SECOND_EXCHANGE: NOT_RUN
P638_ZONE2: NOT_RUN
REFERENCE_PROMOTION: NOT_AUTHORIZED
RUNTIME_PROMOTION: NOT_AUTHORIZED
PUSH: NOT_RUN
PR: NOT_CREATED
```

`TASK_COMMIT: CREATED` after the required checks and independent Judge review.
The requested fresh worktree remains retained at the packet-specified path for
review. No push, PR, merge, or branch cleanup was authorized.
