# Independent Fable Judge Report

VERDICT: REFUTED

TASK_ID: B649_R3_E440_EXACT_TREE_FULL_GATE_R1
TASK_CLASS: READ_ONLY_COMPLETION_REVIEW
WORKER_ROUTE: NOT_APPLICABLE
JUDGE_MODE: FRESH_CONTEXT
JUDGE_DEPTH: FULL
JUDGE_DEPTH_REASON: The Packet explicitly requests a FULL independent reproduction. The exact-tree full-suite evidence is missing, and the first required exact-tree preflight failed. Canonical depth is FULL.
PACKET_JUDGE_DEPTH: FULL
CANONICAL_REQUIRED_JUDGE_DEPTH: FULL
JUDGE_DEPTH_RECONCILIATION: MATCH
MISSING_JUDGE_EVIDENCE: FULL_SUITE (not run after the required preflight failed); process environment and umask capture; complete initial source refs manifest; complete filesystem write/deletion baseline; direct Family verification result.
IMPLEMENTATION_MUTATION_REQUIRED: NO
FRESH_CONTEXT_ACTUALLY_USED: YES — separate Judge subagent context; no Worker implementation context was reused.
ACTUAL_JUDGE_DEPTH: FULL
REVIEW_DATE: 2026-10-19
JUDGE_REPORT_LOCATOR: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_E440_EXACT_TREE_FULL_GATE_R1/judge-report.md
JUDGE_REPORT_SHA256: Detached hash supplied in the parent handoff after this file is written.

## Candidate identity and rules

Repository: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis
Candidate source worktree: /Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_ADV11_DESCENDANT_STABLE_CONTEXT_R1
Candidate branch: detached (no branch)
Expected and independently observed HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
Expected and independently observed tree: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
Expected and independently observed parent: 86f644010f41cd627f436c8d5cf9e0b5cca8fcdc
Source worktree status at review: clean.
Test repository: /private/tmp/e440-full-gate.rqGetV/testrepo
Test checkout HEAD/tree/parent: exact match to candidate.
Changed path from candidate parent to HEAD: tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py only.
Advanced test SHA-256: 5f1198daf582db4340c2bf424071375a442e8ca9e54fd8d27e4d10d03ef9f067 (matches Packet).
README blob at HEAD: 89170cf4311c06b38c3072b13975a082a8e15cde. Read the Quick Start, local Runtime Controller, and local DB/test-runtime sections.
RUNBOOK blob at HEAD: e146a33a6338328fc8bfcee830ad820b90a0b193. Read Toolchain requirements, Canonical backend commands, SQLite/data-directory rules, Reproducibility gates, Branch/worktree safety, and One-off evidence retention. RUNBOOK identifies bootstrap R1, status 2026-07-20.
The README and RUNBOOK blob IDs independently match the Worker evidence summary.

Installed Fable rules read and SHA-256 checked:
- /Users/kelvin/.codex/skills/fable-method/SKILL.md — d9ce3ab741820c55822584db4ed876db83ee8cf8b3fef31bd1a0c6dd899b58ee
- /Users/kelvin/.codex/skills/fable-method/references/task-checkpoint.md — ddec42a39a41919833fc04e7d351bea85c3cf5d7f097088667e23646871d4c9a
- /Users/kelvin/.codex/skills/fable-method/references/operational-gates.md — f87b59104179cbafc84c96804d4a5438cda63e49e48d222a4624cf6e707d64c2
- /Users/kelvin/.codex/skills/fable-method/references/judge-handoff.md — 0aeb32bc6a93afc064b8be5cce4c106fd1e76684b428277a38ffac1306ccabf4
- /Users/kelvin/.codex/skills/fable-method/references/reporting.md — b56f8af1833727ec16f114b7fd08599c4cc152eb5b28617d144934b741397e23
- /Users/kelvin/.codex/skills/fable-judge/SKILL.md — a9e16140f0a38a1ce68e8e96aa314aa26c547a33bbe1495780c16cd4a615f0b8
- /Users/kelvin/.codex/skills/fable-judge/references/judge-depth-contract.md — c02a2189582fcb0a08deef1d6e0faa3576eaf842b4f919d86d89045619193159

The required FULL depth follows the Owner's explicit request and the missing full-suite evidence. The first required preflight failure is a stop condition, so no FULL suite was run and none is claimed.

## Evidence reviewed and integrity

Authorized persistent evidence root: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_E440_EXACT_TREE_FULL_GATE_R1

Independent SHA-256 checks:
- worker-evidence-summary.md: 1727f234ebdfeabf69de6b6f8ab4f322595a3a4fbfed43135d5c359097bc8d77
- source-refs-before-summary.txt: 08d7922a5d576dded7dd5a567a6eb67020d30590cc29ec9b77c420482bf5122d
- source-refs-after.txt: c371c8e6aa644df0f34ef020f89fccd3b81c03d550e9fd64719762aa2372590e
- test-object-manifest.txt: 6c1325a5667aa7657f74dc3c8a2be51fe52587438f9c4f2de079412ed2e4129d
- dependency-manifest.txt: a9e9ceb4d3434a7cc3f98c35417be1c2e611c5e8232f2b9dba6a71dc7b2f5f80
- runtime-and-lock-fingerprints.txt: 91524e96e05b38a2721e90e8ad0f36a98f6eabd045d0237c0fe22a0785b304bf

Execution receipts:
- executions/e440-collect-pin9-r1.json: 042509ddbd710bf5e4d94a38f285899459bf8c8d83b5713c7bb10f1cec846c12
- executions/e440-collect-t249-r1.json: 95b8d7304d23db7e4abf0ecc9e39f120616f9ce12166efc2166df0dc8a7dee0f
- executions/e440-focused-advanced19-r1.json: 15808c46bac0c207e89d2096ef11be2fc1b39615ed1207635d713ffbcc26b088

Raw captures:
- captures/e440-collect-pin9-r1.json: 6081f8a9ccc63818bf3eb9af8d0f609108bffbfc8d395b58aae6a54ee2111025
- captures/e440-collect-t249-r1.json: 94a2f16011f39473e78cdf9a2f1fcf1ae1ecb39abd61e85dc4625792764676aa
- captures/e440-focused-advanced19-r1.json: c47928ba36902263964fa3a76c710f3ce83ab28bb99770a2497c81cc0048171b

All six saved original execution/capture JSON files were read. Their contents in the external test repository match byte-for-byte with the copies in the authorized evidence root. The Advanced capture records the exact Python command, relative test target, stdout/stderr, exit status, start/end times, and repository/head/tree identity. It does not serialize process environment, effective umask, or working directory.

## Test repository identity, object closure, and isolation

The external test repository directly resolves to the expected HEAD/tree/parent. Its ref manifest has 1,625 entries and SHA-256 c371c8e6aa644df0f34ef020f89fccd3b81c03d550e9fd64719762aa2372590e, exactly matching the persisted source-after manifest. Its live object inventory contains 27,489 OID/type entries and exactly matches test-object-manifest.txt.

Independent checks:
- is-shallow-repository: false.
- alternates: no alternates file.
- remote configuration: none.
- partial-clone/promisor/fetch-filter configuration: none.
- object database: one pack, 27,489 packed objects.
- git fsck --full --no-reflogs: exit 0; 719 dangling notices; zero missing/corrupt/error lines.

These observations support a standalone, complete test repository with no remote or lazy-fetch dependency. The Worker described building a new repository from the source object inventory and importing refs before detached checkout; the resulting identity, refs, object inventory, and isolation were independently verified. No separate itemized path-pin execution log was saved; the full object inventory, imported refs, and fsck closure provide the available evidence.

## Runtime and safety evidence

The saved test command uses the existing interpreter at /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python. A direct version query at review time reported Python 3.13.8 and pytest 9.1.1, matching the runtime fingerprint and dependency manifest. No uv run, sync, package install, or repository-local virtualenv creation appears in the captures. No .venv exists in the candidate worktree or test repository.

The captured pytest commands place basetemp at /private/tmp/e440-full-gate.rqGetV/pytest-basetemp and cache_dir at /private/tmp/e440-full-gate.rqGetV/pytest-cache, outside both repositories. That path contains no b649 text in any casing. At review time the basetemp and appdata directories were mode 0700. The test app-data path recorded in the Worker summary is /private/tmp/e440-full-gate.rqGetV/appdata; its current measured mode is 0700. The separate default app-data path and its observation time are not stated in the capture.

The Worker summary claims effective umask 0077 and that the test process used the recorded LOTTOLAB_DATA_DIR. The capture does not record the environment or umask, so those launch-time claims cannot be independently verified. The existing runtime root remains under /private/tmp/e440-full-gate.rqGetV. The only regular files observed under its cache/temp directories were pytest-cache/v/cache/lastfailed and pytest-cache/v/cache/nodeids. The repository-local test runtime produced no .venv.

Result: AC03 remains NOT_VERIFIED because the required launch-time umask and app-data environment binding are absent, despite the interpreter, external basetemp, and current directory modes being verified.

## Execution results and counts

Three Worker execution records exist:
1. T249 collection probe: 88 nodes collected, zero tests executed, exit 0.
2. PIN9/R9 filename collection probe: 4 nodes collected, zero tests executed, exit 0. This is not the required PIN9 24-test run.
3. First required Advanced 19 execution: 19 collected; 17 passed, 1 failed, 1 skipped, 0 errors; exit 1; reported wall time 10.24 seconds; start 2026-10-19T13:01:45Z; end 2026-10-19T13:01:56Z.

The failed node was tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py::test_candidate_is_not_accepted_as_historical_child. Its captured traceback says the child run exited 0 and had 17 outcomes, but the assertion that all outcomes equal passed was false. No more specific failing child outcome is present in the capture.

The required stop rule was followed after that preflight failure. T249 runtime tests, OR-Tools collection/negative guard, PIN9 24 tests, six path-sensitive tests, Family --verify-result, all later focused checks, and the repository FULL pytest suite were NOT RUN. The two collection probes do not satisfy these test requirements.

FULL_SUITE_EXECUTIONS: 0
FULL_SUITE_COMMAND: NOT RUN; canonical command in README/RUNBOOK is uv run pytest.
FULL_SUITE_EXIT_CODE: NOT RUN
FULL_SUITE_PASS: NO
FULL suite collected/passed/failed/errors/skipped/warnings/wall time: NOT RUN / NOT RUN / NOT RUN / NOT RUN / NOT RUN / NOT RUN / NOT RUN.
FULL-suite failed IDs, error IDs, and first traceback: not applicable because the suite was not run. The Advanced preflight failure above is the only captured test failure.

No tests were run by the Judge. Judge verification-run counts: 1 FULL Judge; 0 Judge test runs; 0 FULL suite runs; 0 delta re-Judges. The Worker ran 1 focused test command and 2 collection-only probes.

## Source refs, object inventory, and attribution

The Worker saved:
- before refs: 1,626 entries, SHA-256 0e18913049bece31b73f19e684ff5ce31c088174c0999e98c02e4730d7ab92df; the complete before manifest was not persisted.
- after refs: 1,625 entries, SHA-256 c371c8e6aa644df0f34ef020f89fccd3b81c03d550e9fd64719762aa2372590e; full after manifest was persisted and matches the external test repository refs.

The Worker summary reports an earlier source OID inventory of 27,486 objects with SHA-256 344087de10dc6388bb7ca70060975c5f6e6ab8602cbef81972f301548f4a895, followed by 27,489 objects before the test copy. The persisted 27,489-object test manifest is the test repository inventory; a complete source inventory at both source-read times was not saved. Attribution for the three-object change is UNKNOWN.

A live Judge-time read observed 1,624 source refs and 27,506 source objects. One later ref snapshot differed from the saved after manifest by one removed ref; two Judge-time snapshots with the same ref count also produced different digests. This shows live source refs were changing during the review. No actor or cause is established. These changes are not attributed to the Worker or Judge. The exact initial-to-after change set cannot be reconstructed from the saved before hash/count alone.

SOURCE_REFS_BEFORE: count 1,626; SHA-256 0e18913049bece31b73f19e684ff5ce31c088174c0999e98c02e4730d7ab92df; full manifest NOT PERSISTED.
SOURCE_REFS_AFTER: count 1,625; SHA-256 c371c8e6aa644df0f34ef020f89fccd3b81c03d550e9fd64719762aa2372590e.
REFS_ATTRIBUTION: UNKNOWN.
SOURCE_OID_INVENTORY_ATTRIBUTION: UNKNOWN.
AC11 is NOT_VERIFIED. AC12 is NOT_VERIFIED because all source-ref/object changes and the complete write/deletion set cannot be accounted from a full before manifest.

## Findings

finding_id: F01
severity: BLOCKING
FINDING_CONFIDENCE: CONFIRMED
claim: The required Advanced 19 preflight failed.
criterion_or_rule: AC04; Packet section VIII requires stopping when a required compatibility preflight fails.
evidence: captures/e440-focused-advanced19-r1.json, SHA-256 c47928ba36902263964fa3a76c710f3ce83ab28bb99770a2497c81cc0048171b; exit 1, 17 passed, 1 failed, 1 skipped.
expected: Advanced 19 required cases pass in the exact-tree test repository.
observed: test_candidate_is_not_accepted_as_historical_child failed; one case was skipped.
decision: AC04 FAIL; subsequent preflights and the one authorized FULL suite correctly remain unrun.

finding_id: F02
severity: BLOCKING
FINDING_CONFIDENCE: CONFIRMED
claim: Source ref and OID inventory changes cannot be fully reconciled or attributed.
criterion_or_rule: AC11 and AC12; source Git writes are forbidden and before/after source ref states must be accountable.
evidence: before refs 1,626 / 0e189130… with no full manifest; after refs 1,625 / c371c8e6… with full manifest; reported source OID inventory 27,486 then 27,489; Judge-time source refs/OID inventory changed again.
expected: Full before/after states and an evidence-backed attribution or non-attribution of each difference.
observed: Initial ref names and initial object OIDs are unavailable; live state continued changing; no evidence assigns the differences to this task or another actor.
decision: AC11 and AC12 NOT_VERIFIED. This confirms an evidence-accounting gap, not a finding that the Worker caused the changes.

finding_id: F03
severity: BLOCKING
FINDING_CONFIDENCE: CONFIRMED
claim: Launch-time app-data binding and effective umask are not independently established.
criterion_or_rule: AC03; Packet section VII requires measured runtime safety evidence.
evidence: The three capture JSON files contain command/output/exit/times and repo identity, but no process environment, cwd, or umask. Worker summary claims LOTTOLAB_DATA_DIR and umask 0077. Current test appdata and basetemp modes are 0700.
expected: Capture tying the test process to the exact app-data path, mode, external temp, and effective umask.
observed: Current path modes and command basetemp are verifiable; launch-time app-data variable and umask are not.
decision: AC03 NOT_VERIFIED.

## AC01–AC13 adjudication

| Criterion | Evidence and observed result | Decision |
|---|---|---|
| AC01 | Direct source and test-repository HEAD/tree/parent all match the expected full OIDs. | PASS |
| AC02 | Test repository refs equal the persisted source-after refs; 27,489-object manifest matches live testrepo; no shallow state, alternates, remote, or promisor configuration; full fsck exit 0. | PASS |
| AC03 | Python 3.13.8/pytest 9.1.1, external basetemp, current mode 0700, and no repository .venv verified. Launch-time LOTTOLAB_DATA_DIR and umask are not captured. | NOT_VERIFIED |
| AC04 | Advanced 19 captured as 17 passed, 1 failed, 1 skipped, exit 1; mandated stop then followed. | FAIL |
| AC05 | Repository FULL suite executed zero times; no exclusions can be assessed from a suite run. Stop rule prevented execution. | NOT_RUN |
| AC06 | Full-suite counts/exit/failure IDs do not exist because the suite was not run. Preflight counts and traceback are saved and hashed. | NOT_RUN |
| AC07 | Family --verify-result was not run in this task. Packet expected values are not a same-command execution result. | NOT_RUN |
| AC08 | Candidate commit changes only the Advanced test file; candidate worktree is clean; tests ran in separate external repo. No product, math-source, result, or sealed-pin modification is observed. | PASS |
| AC09 | Three preflight/collection captures are persisted and hashes verified. No FULL-suite capture exists because no suite ran; this report is persisted separately. | NOT_RUN |
| AC10 | Separate Fresh-context Judge verified the same exact candidate HEAD/tree. | PASS |
| AC11 | Before/after source-ref counts and hashes differ; full initial manifest is missing and attribution is unknown. | NOT_VERIFIED |
| AC12 | No product or remote write is observed; source refs/OID drift and lack of a complete filesystem baseline/deletion ledger prevent a full write-boundary finding. | NOT_VERIFIED |
| AC13 | Failed, unknown, and unrun work is explicitly recorded; no full-suite pass or gate completion is claimed. | PASS |

## Evidence reuse and missing items

REUSED_EVIDENCE: Exact candidate HEAD/tree/parent from Git; exact HEAD README/RUNBOOK blobs; saved execution/capture JSON; test object manifest; dependency/runtime fingerprints; source refs-after manifest. Each saved capture SHA-256 was recomputed.
INVALIDATED_OR_NOT_REUSED: Packet prior focused results and mathematical claims were not treated as fresh exact-tree runtime evidence; the available execution captures do not establish identical environment and command for this task. No missing historical R3 capture was searched for.
COVERED_ITEMS: Exact tree identity; changed path; external repository identity/ref snapshot/object inventory; shallow/alternate/remote/promisor state; object integrity; captured focused execution result; captured collection-only results; evidence copy integrity; candidate worktree status; persistent evidence inventory.
MISSING_ITEMS: Successful Advanced preflight; remaining focused preflights; exact launch environment and umask; complete initial source refs and source OID manifests; complete filesystem baseline/final write/deletion ledger; per-pin execution log; Family verification result; canonical FULL suite result/capture.

## Write and lifecycle accounting

Authorization: The Packet authorizes the external test repository/runtime and task-owned evidence under the exact persistent evidence root. Product writes, source repository Git writes, commit, push, PR, merge, deployment, and cleanup are not authorized.

Confirmed task-owned retained outputs:
- The standalone external test repository and checkout at /private/tmp/e440-full-gate.rqGetV/testrepo, including one 27,489-object pack and its imported refs.
- Three execution JSON receipts and three capture JSON files under the task-specific .fable/checkpoints directory in that external repo; byte-identical copies are retained under the authorized persistent evidence root.
- One task execution lock directory under testrepo/.git/fable-locks/task-execution/e26e8eed2814763d6337914afb61a6d8367cc3c9cca81176cd43c911cf0718ad, with authority.json and execution.lock.
- External runtime directories under /private/tmp/e440-full-gate.rqGetV: appdata, pytest-basetemp, pytest-cache, python-cache, tmp, uv-cache, xdg-cache, xdg-data, and pip-cache. The only regular files observed in those runtime/cache paths were pytest-cache/v/cache/lastfailed and pytest-cache/v/cache/nodeids.
- The 12 pre-existing files in the authorized persistent evidence root listed in the Evidence reviewed section.
- This formal report, the only intentional write performed by this Judge, at the authorized persistent evidence root.

FILES_WRITTEN_DURING_TASK: Confirmed task-owned outputs are listed above. A complete baseline/final filesystem manifest was not saved, so this is not an exhaustive per-path write ledger.
FILES_RETAINED_AT_END: External testrepo and runtime roots; task Fable receipts/captures and lock metadata; 12 existing persistent evidence files; this report.
FILES_DELETED_BEFORE_END: UNKNOWN; no complete baseline or deletion ledger exists.
TASK_CREATED_FILES_RETAINED: External test repository/materialization, task receipts/captures, lock metadata, runtime outputs, and this report.
TASK_CREATED_FILES_DELETED: UNKNOWN.
PRE_EXISTING_FILES_RETAINED_UNCHANGED: UNKNOWN; no full filesystem baseline.
PRE_EXISTING_FILES_MODIFIED_AND_RATIFIED: NONE observed; full baseline unavailable.
FILES_MODIFIED_DURING_TASK: Candidate product files: none observed. Authorized evidence files: yes, listed above. External runtime cache files: lastfailed and nodeids observed.
REPOSITORY_FILES_MODIFIED: No product source/test changes during execution observed. Candidate commit's only changed path is the specified test. Persistent evidence is under the authorized primary-checkout evidence root.
TOOLCHAIN_RUNTIME_OUTPUTS_CREATED: Task-owned appdata/temp/cache directories; pytest cache lastfailed and nodeids.
TOOLCHAIN_RUNTIME_OUTPUTS_MODIFIED: UNKNOWN without baseline.
PRE_EXISTING_RUNTIME_OUTPUTS_RETAINED_UNCHANGED: UNKNOWN without baseline.
WORKTREE_MATERIALIZATION_CREATED: New standalone external test repository and detached checkout.
WORKTREE_MATERIALIZATION_UPDATED: Task receipts/captures and test cache in that external repository/runtime.
WORKTREE_MATERIALIZATION_REMOVED: None observed.
GIT_NETWORK_METADATA_WRITES: None observed; external test repo has no remote and no network operation is in the captures.
GIT_WORKTREE_METADATA_WRITES: External repo object pack, imported refs, and detached checkout are authorized. Candidate HEAD remains the expected commit. Live common-source refs/OID changes remain unattributed.
HARNESS_GIT_METADATA_WRITES: External repo task execution lock directory and execution metadata, as listed above.
TASK_COMMIT: No task-created commit observed; candidate remains the expected HEAD.
TASK_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
FINAL_HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
FINAL_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
CANONICAL_FINAL_HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
CANONICAL_FINAL_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
COMMIT_LINK: NOT_APPLICABLE
RUNTIME_TRANSITION_OCCURRED: NO
LOCAL_FULL_SUITE_RUNS: 0
FOCUSED_TEST_RUNS: 1
INITIAL_JUDGE_RUNS: 0
DELTA_REJUDGE_RUNS: 0
FULL_JUDGE_RUNS: 1
EXACT_HEAD_CI_RUNS: 0
REUSED_EVIDENCE: exact identity, saved captures, test object manifest, refs-after manifest, runtime/dependency records as described above.
INVALIDATED_EVIDENCE: no prior runtime result was accepted as proof for this fresh gate.

The Judge used read-only Git, filesystem, checksum, and version inspection; no tests were run and no source refs or product files were intentionally written. Some Git status commands were issued without disabling optional index refresh; the candidate worktree index mtime is 2026-10-19T12:49:47Z, before the captured test start, so no index refresh during this review is observed. The Python/pytest version query used the pre-existing project environment; no baseline manifest was available to prove whether it caused a bytecode-cache write. No such cache write was confirmed. The report is the only intentional Judge write.

TASK_STATUS: NOT_VERIFIED
FRESH_JUDGE_VERDICT: REFUTED
JUDGED_HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
JUDGED_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
TREE_MATCH: YES
FULL_SUITE_PASS: NO
MAIN_MUTATED: NOT_VERIFIED
REMOTE_WRITE: NO observed
LOCAL_COMMIT_COUNT: 0 task-created commits observed

JUDGE_SESSION_LINEAGE:
PARENT_SESSION_NAME: /root
JUDGE_SESSION_NAME_REQUESTED: b649_r3_e440_full_judge (collaboration task name)
JUDGE_SESSION_NAME_ACTUAL: /root/b649_r3_e440_full_judge (canonical task identity; UI title unavailable)
JUDGE_SESSION_RELATION: FRESH_CONTEXT_CHILD
JUDGE_SESSION_REUSED: NO
JUDGE_SESSION_NAMING_CAPABILITY: SUPPORTED (collaboration tool accepted task_name)
JUDGE_SESSION_LINEAGE_RULE: first fresh Judge <parent>-judge; nth fresh re-Judge after remediation <parent>-judge-rN (N starts at 2)
HARNESS_CHANGE_REQUIRED_FOR_ACTUAL_RENAME: UNKNOWN

REMAINING_TASK_MODEL: Strong model — Canonical Family Authority adoption.
NEXT_ACTION: END_WITH_EXACT_TREE_FULL_GATE_DISPOSITION. Stop this gate at the failed preflight; no remediation, rerun, or product change is requested by this Judge. Any further action requires a new explicit Owner instruction/Packet.

