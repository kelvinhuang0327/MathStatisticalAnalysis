# B649 next tied resolved frontier: Worker handoff

TASK_ID: B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1
TASK_STATUS: COMPLETE_LOCAL_RESEARCH_SELF_CHECK_ONLY
MODEL: Codex / GPT-6; exact runtime model ID is not exposed to this Worker.
REMAINING_TASK_MODEL: 最強模型 — fresh-context independent mathematical Judge; 強模型 — subsequent verified-certificate Family correctness integration.

BASE_HEAD/TREE: ee4bb2f22ff101522e73952a3f11c66c55d95098 / 876d80cb5fb524af925bd35e0d6042093248710e
FROZEN_HEAD/TREE: 6569a9667d5e2094c8542cdff9905c3fd89f9e44 / 986d20859c86be9036b2321ac47e2e9622786a3b
FIXED_HEAD/TREE: MATCH
PROFILE_A_SOURCE_IDENTITY: 65555555555442000000; NB_CERTIFICATES[1620]; original cap 266; S4 base 112; MATCH.
PROFILE_B_SOURCE_IDENTITY: 66555555554433000000; NB_CERTIFICATES[1467]; original cap 266; S4 base 112; MATCH.
SOURCE_ROW_A: RESOLVED
SOURCE_ROW_B: RESOLVED

Both source labels have prefix b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json. They identify virtual replay-generated catalog rows, not literal summary-JSON array entries. The source proof is the pinned NB module docstring and refine_resolved function. The result records actual catalog degree tuples and source SHA bindings; it does not manufacture a nonexistent JSON locator.

OLD_BOUND_A: 313392232
OLD_BOUND_B: 313392232
MATHEMATICAL_THEOREM_A: Every legal realization of A satisfies T<=224, hence the complete Route-B envelope is at most 313015432.
MATHEMATICAL_THEOREM_B: Every legal realization of B satisfies T<=222, hence the complete Route-B envelope is at most 312995528.
LOAD_BEARING_PREMISES_A: Fixed 20-ticket/6-label, 22-triple/27-pair support model; pair-linearity; d=(6^1,5^10,4^2,2^1,0^6); core/zero sizes 14/6; 0<=sigma<=6-d; 1<=zeta<=6; sum sigma=sum zeta; P is a sum of cardinalities and is nonnegative.
LOAD_BEARING_PREMISES_B: Same support and cross-edge premises; d=(6^2,5^8,4^2,3^2,0^6).
EXACT_INEQUALITY_A/B: T<=200+sum_core sigma*(sigma+3-d)-P.
PROOF_SCOPE_A: FULL_PROFILE
PROOF_SCOPE_B: FULL_PROFILE
PROVED_T_CAP_A: 224
PROVED_T_CAP_B: 222
NEW_BOUND_A: 313015432
NEW_BOUND_B: 312995528
RELAXATION_COMPLETENESS_A: Universal support-to-degree map and analytic inequalities cover every legal realization; no finite search is used.
RELAXATION_COMPLETENESS_B: Same complete analytic argument; no graphicality or joint-realizability assumption is required by the enlarged domain.
INDEPENDENT_ARITHMETIC_RECOUNT_A/B: Independent integer and exact-Fraction implementations agree at every old and new term; all terms also match the existing pinned R32 helper.
ROUNDING_CHECK_A/B: PASS; K4 uses ceiling, and the rational S4 union credit uses integer minus floor. A's endpoint K4 argument is 191.5 and rounds to 192.
ARGMAX_TERM_A: [224,313015432,192,192,86016,4674544]
ARGMAX_TERM_B: [222,312995528,177,177,79296,4650800]
ROUTE_B_RECOUNT_A: Inclusive domain 22..224, 203 terms; old inclusive 22..266, 245 terms; strict improvement 376800.
ROUTE_B_RECOUNT_B: Inclusive domain 22..222, 201 terms; old inclusive 22..266, 245 terms; strict improvement 396704.

## Acceptance evidence

NEGATIVE_CASE_RESULTS: PASS_REJECTED for wrong profile, wrong histogram, unsupported T cap, missing capacity, invalid cross-edge balance, negative remainder, incorrect ceiling/rounding, and missing Route-B term. Finite realization coverage is NOT_APPLICABLE to the analytic proof; removing required coordinate arithmetic coverage is rejected. All nine listed controls are mapped to observed test cases in the validation JSON.
FOCUSED_TEST_COMMAND:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_b649_next_tied_resolved_frontier_math_r1.py --junitxml=docs/research/matrix-native-results/b649-next-tied-resolved-frontier-math-r1-focused-tests-final.xml
```

FOCUSED_TEST_EXIT_CODE: 0
FOCUSED_TEST_RESULT: 17 passed.
FALSIFIABILITY_CHECK: CONFIRMED. Process-local cap-minus-one mutation produces 4 failures and 13 passes, exit 1. Process exit restores original behavior; source bytes are unchanged. Final reverify: 17 passed, exit 0.

These tests audit source bindings, arithmetic, coverage and rejection behavior. Full-profile validity rests on the deductive proof in B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1.md, not on tests passing.

FRONTIER_AFTER_BOTH_UPDATES: NOT_PROVED_EXACT_NUMERIC_VALUE. Since the fixed ledger identifies A and B as its sole tied resolved owners, tightening both would strictly lower its resolved maximum. No update is installed. Tightening only one leaves 313392232 controlled by the other owner.
FAMILY_GAIN_WITH_OLD_CURSOR: 0. The fixed 197-profile cursor still gives 313394584; its bound and count were read and checked from the fixed ledger.
RESULT_SHA256: 5b5834e003dc52daabdf72acf872f8fce83184030b7ed40f139b686d6836c1b2 (canonical JSON payload excluding RESULT_SHA256)
RESULT_FILE_SHA256: 89c9fda3d3526285677e81867161f0fdeefa6f00a84779e1ccdd5f7cb96c1180 (saved result bytes)
LOCAL_COMMIT_HEAD/TREE: The single local commit containing this report; exact post-commit identity is supplied in the final chat handoff to avoid a self-referential commit hash.
WORKTREE_CLEAN: Post-commit observation is supplied in the final chat handoff.

SCIENTIFIC_JUDGE: SELF_CHECK_ONLY
FORMAL_FAMILY_AUTHORITY: NOT_ACCEPTED
COUNTEREXAMPLE_STATUS: NONE_KNOWN; cap attainment is not claimed.
UNPROVED_ASSUMPTIONS: NONE within the fixed min-S2 support model.
MISSING_EVIDENCE: Fresh-context independent mathematical Judge and exact next resolved frontier numeric aggregate. Subsequent formal Family integration has not been performed.
NEW_WINNING_OUTCOMES: 0

## Worktree and execution accounting

ACTUAL_PATH: /Users/kelvin/.codex/worktrees/b649-next-tied-resolved-frontier-math-r1/MathStatisticalAnalysis
BRANCH: codex/b649-next-tied-resolved-frontier-math-r1
WORKTREE_CREATION: Codex supported create_worktree entrypoint at the pinned base; registered attachment.
CLEANUP_DISPOSITION: RETAIN

The protected launcher initially refused execution because the common Git repository lacks its generation-2 lock marker. No lock marker was initialized or migrated. The human explicitly authorized direct local final certificate generation and focused tests, with CPU<=120 seconds and one CPU-bound process. The certificate capture preserves both the original refusal and the supplemental authorization. Certificate generation completed in about 36 seconds of wall time. The child enforces RLIMIT_CPU=120; test children have the same limit. All computational jobs were sequential, with BLAS/OpenMP thread counts set to one.

Only this task's new proof, checker, focused test, result, command captures, JUnit records, validation record and Worker report are retained. No existing tracked source or certificate is changed. T261 and T255 worktrees are untouched. No third Profile is researched. No new Family ledger engine, heavy solver, CP-SAT, FIBER, full suite, Family adoption, push, merge, PR or production mutation is performed.
