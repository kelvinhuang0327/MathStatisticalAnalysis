# Worker evidence summary — B649_R3_E440_EXACT_TREE_FULL_GATE_R1

TASK_CLASS: READ_ONLY_COMPLETION_REVIEW
WORKER_ROUTE: NOT_APPLICABLE
JUDGE_MODE: FRESH_CONTEXT
PACKET_JUDGE_DEPTH: FULL
CANONICAL_REQUIRED_JUDGE_DEPTH: FULL
JUDGE_DEPTH_RECONCILIATION: MATCH
MISSING_JUDGE_EVIDENCE: FULL_SUITE (preflight failed)
IMPLEMENTATION_MUTATION_REQUIRED: NO

## Candidate identity

Source worktree: /Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_ADV11_DESCENDANT_STABLE_CONTEXT_R1
Expected/test HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
Expected/test tree: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
Expected/test parent: 86f644010f41cd627f436c8d5cf9e0b5cca8fcdc
Advanced test blob: c9e8bba7dc72f026658d88c516af8cc9790388a0
Advanced test SHA-256: 5f1198daf582db4340c2bf424071375a442e8ca9e54fd8d27e4d10d03ef9f067
Candidate worktree status was clean before and after focused execution; all tests ran in the external repository.

## Project and Fable rules observed

README.md blob: 89170cf4311c06b38c3072b13975a082a8e15cde
.ai/ai-context/RUNBOOK.md blob: e146a33a6338328fc8bfcee830ad820b90a0b193
RUNBOOK sections read: Toolchain requirements and Canonical backend commands (lines 5–21); SQLite/data-directory rules and DB authorization (81–99); reproducibility and branch/worktree safety (106–120); one-off evidence retention (154–161).

Loaded installed Fable files and their SHA-256:
- fable-method/SKILL.md d9ce3ab741820c55822584db4ed876bea83ee8cf8b3fef31bd1a0c6dd899b58ee
- fable-method/references/task-checkpoint.md ddec42a39a41919833fc04e7d351bea85c3cf5d7f097088667e23646871d4c9a
- fable-method/references/operational-gates.md f87b59104179cbafc84c96804d4a5438cda63e49e48d222a4624cf6e707d64c2
- fable-method/references/judge-handoff.md 0aeb32bc6a93afc064b8be5cce4c106fd1e76684b428277a38ffac1306ccabf4
- fable-method/references/reporting.md b56f8af1833727ec16f114b7fd08599c4cc152eb5b28617d144934b741397e23
- fable-judge/SKILL.md a9e16140f0a38a1ce68e8e96aa314aa26c547a33bbe1495780c16cd4a615f0b8
- fable-judge/references/judge-depth-contract.md c02a2189582fcb0a08deef1d6e0faa3576eaf842b4f919d86d89045619193159
Installed protected-run launcher mode 0755 and Git blob 00e2cf4a4f06b0f0a8d8e4be6091a4304e6e2ae4; launcher SHA-256 babba3757a7ea9ad59c7ff9b18b6e4497dbc887b86eebfb09ccae1a36ab96275.

## External test repository and runtime

Test repository: /private/tmp/e440-full-gate.rqGetV/testrepo
Method: new Git repository; packed the complete valid object inventory from the managed source ODB, imported all source refs, then detached checkout at the exact expected HEAD. Source objects were used as a transient pack-generation alternate only; the resulting test repository has no alternates file, no shallow state, no remote, and no lazy-fetch dependency.
At the test-repository inventory point, source and test OID/type manifests both contained 27,489 objects and had SHA-256 6c1325a5667aa7657f74dc3c8a2be51fe52587438f9c4f2de079412ed2e4129d. The saved manifest is test-object-manifest.txt.
External full git fsck: exit 0; 719 dangling notices; zero missing/corrupt/error lines. Full output SHA-256: 14608012dbeaf0c27acb5ba79d57cc0650e9899682c1fab3d4c7847e28ba4a35.
No remote was configured. GIT_NO_LAZY_FETCH=1 and GIT_OPTIONAL_LOCKS=0 were used for exact-tree test commands.

A separate earlier read-only source OID inventory observed 27,486 objects (OID/type manifest SHA-256 344087de10dc6388bb7ca70060975c5f6e66ab8602cbef81972f301548f4a895). Before the test repository manifest was saved, a later read observed 27,489 and the test repository matched it. Cause of the three-object inventory difference is UNKNOWN and is not attributed to this task.

## Runtime isolation

Python: 3.13.8
pytest: 9.1.1
Existing interpreter: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python
No uv run, environment sync, package install, or .venv creation was used.
Project lock inputs and installed distribution manifest are recorded in runtime-and-lock-fingerprints.txt and dependency-manifest.txt.
Default app-data path was observed mode 0700 and not used. Test LOTTOLAB_DATA_DIR: /private/tmp/e440-full-gate.rqGetV/appdata, observed mode 0700.
Effective umask: 0077.
Pytest basetemp: /private/tmp/e440-full-gate.rqGetV/pytest-basetemp, outside both repositories and without b649 in the path.
Python bytecode/cache, pytest cache, TMPDIR, XDG cache/data, UV cache, and PIP cache were placed under /private/tmp/e440-full-gate.rqGetV; all created directories were mode 0700.

## Focused execution results

1. T249 collection probe only: 88 nodes collected from the three T249 composition modules; no tests executed. Capture: captures/e440-collect-t249-r1.json, SHA-256 94a2f16011f39473e78cdf9a2f1fcf1ae1ecb39abd61e85dc4625792764676aa.
2. r9 filename collection probe only: 4 nodes collected from test_b649_k20_min_s2_top_plateau_closure_r9.py; no tests executed. This was not a PIN9 test execution. Capture: captures/e440-collect-pin9-r1.json, SHA-256 6081f8a9ccc63818bf3eb9af8d0f609108bffbfc8d395b58aae6a54ee2111025.
3. First required focused execution, Advanced 19 module: 19 collected; 17 passed, 1 failed, 1 skipped; 0 errors; process exit 1; pytest-reported wall time 10.24 seconds. Started 2026-10-19T13:01:45Z, ended 2026-10-19T13:01:56Z.
   Failed node: tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_candidate_is_not_accepted_as_historical_child
   Failure: assertion at line 761, all outcomes in _child_run.outcomes were expected to equal passed, but the assertion was false. Raw capture contains the first-failure traceback and exact command.
   Capture: captures/e440-focused-advanced19-r1.json
   Capture SHA-256: c47928ba36902263964fa3a76c710f3ce83ab28bb99770a2497c81cc0048171b.
   The required preflight failed here, so all later focused executions and the one authorized repository FULL pytest suite were NOT RUN. No tests were retried and no source was changed.

## Source refs

Initial source snapshot: 1,626 lines, SHA-256 0e18913049bece31b73f19e684ff5ce31c088174c0999e98c02e4730d7ab92df. The complete initial ref manifest was not persisted.
Observed after focused execution: 1,625 lines, SHA-256 c371c8e6aa644df0f34ef020f89fccd3b81c03d550e9fd64719762aa2372590e; full observed output is source-refs-after.txt.
The digest/count changed. This task issued no source ref mutation; whether this was an application snapshot ref or another external change is UNKNOWN. Do not attribute it to the task.
The external test repository ref digest/count at its snapshot were c371c8e6aa644df0f34ef020f89fccd3b81c03d550e9fd64719762aa2372590e / 1,625.

## Execution boundary

FULL_SUITE_EXECUTIONS: 0
FULL_SUITE_COMMAND: NOT RUN (stopped at failed mandatory preflight)
FULL_SUITE_PASS: NO
No source commit, push, remote write, PR, merge, deployment, branch cleanup, or other worktree mutation was executed. Task-owned Fable execution records/captures were generated in the external test repository and copied to this Packet-authorized evidence root. This summary is a Worker claim; the Judge must verify it independently.
