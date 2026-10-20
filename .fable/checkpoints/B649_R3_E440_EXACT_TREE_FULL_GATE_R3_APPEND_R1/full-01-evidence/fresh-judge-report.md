# Fresh-context Fable FULL Judge Report

## Verdict

**REFUTED**

The candidate identity is correct and the protected run chain was observed, but the only authorized FULL suite exited 1 with failure and error progress markers. The persisted run also has a pytest session-finish collector collision. In addition, 128 pre-existing Recorder R1 paths and the old R1 checkpoint root are absent after the run, while source ref snapshots show a material delta that conflicts with the postflight summary. The causes of these disappearances and ref changes remain UNKNOWN; this report assigns no actor or cause.

The result is a gate failure, not a claim that a particular product defect caused every test failure. The first test traceback and complete failure/error node-ID lists were not captured, so those causes cannot be adjudicated here.

## Judge mode and depth

TASK_CLASS: READ_ONLY_COMPLETION_REVIEW  
WORKER_ROUTE: NOT_APPLICABLE  
JUDGE_MODE: FRESH_CONTEXT  
JUDGE_DEPTH: FULL  
JUDGE_DEPTH_REASON: The Packet calls for a fresh-context FULL Judge. The canonical depth contract also triggers FULL because final-suite evidence is incomplete and internally contradictory, and because the suite did not pass. The suite was already consumed once for this exact source snapshot; this Judge did not rerun it.

PACKET_JUDGE_DEPTH: FULL  
CANONICAL_REQUIRED_JUDGE_DEPTH: FULL  
JUDGE_DEPTH_RECONCILIATION: MATCH  
MISSING_JUDGE_EVIDENCE: Complete observer write trace; authoritative full-suite failure/error node IDs and first test traceback; currently missing Launcher and validation-receipt bytes; complete old Recorder/R1 evidence; attribution and corrected accounting for shared-ref changes.  
IMPLEMENTATION_MUTATION_REQUIRED: NO

This was a fresh review context using the Packet and preserved evidence. It was not a continuation of the Worker’s implementation context.

## Packet and rules reviewed

Packet: `/Users/kelvin/.codex/attachments/fc86d02d-8f15-4d0f-ada9-a665b34f9701/pasted-text-1.txt`

Applied the installed `fable-judge` skill and complete `judge-depth-contract.md`, plus the required Fable method references named by the Packet: `SKILL.md`, `task-checkpoint.md`, `operational-gates.md`, `reporting.md`, `workspace-containment.md`, and `judge-handoff.md`. Read the fixed E440 README and RUNBOOK sections for Git, Python/pytest, runtime, Fable execution/evidence, and acceptance.

## Fixed Git identity

- Repository: `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis`
- Source worktree: `/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_ADV11_DESCENDANT_STABLE_CONTEXT_R1`
- Branch state: detached
- Expected and observed HEAD: `e440d4298551ce93ef3ea9a9226143784afa3eff`
- Expected and observed tree: `294cbf6bbe7ee8a8ebad947f397852edc1981b57`
- Expected and observed parent: `86f644010f41cd627f436c8d5cf9e0b5cca8fcdc`
- Source worktree status: clean at review; candidate tree unchanged.
- Parent-to-candidate diff: one modified test file, `tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py`. Inspection found explicit historical-child identity handling, nonzero child exit enforcement, external basetemp checks, and added wrong-identity cases. I found no weakened assertions or product-source change in this diff.

Git provenance is applicable. Candidate identity was checked directly; the detached state does not change the fixed commit/tree identity.

## Git object closure

The retained external clone at `/private/tmp/mathstat-e440-full-gate-r3-repo` has the expected HEAD/tree/parent. It is not shallow; its alternates file is absent; no partial-clone/promisor configuration was found; and the connectivity check ran with lazy fetching disabled. `git fsck --connectivity-only --no-reflogs --full` exited 0. It reported dangling objects, but no missing or corrupt objects. The external clone’s normalized refs were identical before and after the FULL run. Its required disposition is RETAIN.

## Run and evidence accounting

The one canonical FULL run was execution ID `e440-full-gate-r3-full-01`, on the exact E440 tree, with Python 3.13.8 and pytest 9.1.1. Its cwd was the external clone. The actual pytest argv used `-B -m pytest --basetemp=/private/tmp/gate-launch-20261020-17573-14iut56/basetemp -o cache_dir=/private/tmp/gate-launch-20261020-17573-14iut56/pytest-cache -q`.

- FULL suite executions: **1 of 1 permitted**
- Pytest started: 2026-10-20 02:13:50Z
- Pytest ended: 2026-10-20 02:56:59Z
- Measured pytest duration: 2,589 seconds
- Collected: 11,679
- Progress markers: 11,296 passed; 50 failed; 310 errors; 23 skipped; 0 xfail/xpass
- Pytest capture exit status: 1
- Outer protected task/Launcher exit status: 125, after pytest, because the old R1 `judge-report.md` path was missing
- Warning summary: unavailable; pytest emitted no terminal warning summary
- Failed/error node IDs: not recovered
- First test-failure traceback: unavailable
- The nested outcome file contains only 27 entries and is not treated as full-suite evidence.

The full output’s terminal markers sum to the collected count. The pytest session-finish outcome collector then raised `FileExistsError` because its shared outcome path already existed. This prevents treating its nested outcome file as an authoritative full-suite result and means the requested per-test failure/error accounting is incomplete. It does not erase the observed nonzero pytest exit or the 50 failure and 310 error progress markers.

R3 evidence root: `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_E440_EXACT_TREE_FULL_GATE_R3_APPEND_R1`

Key preserved evidence:

- `full-01-evidence/full-01-run-results.json`, SHA-256 `c49f50ff28cdfc1684807105ac6b6141e0e32aca3c85ed63e18012471109848f`
- `full-01-evidence/full-01-final-postflight.json`, SHA-256 `d39bdcb5f69f09fcd69a25124e7b9863d5f2e42d6eb43996775f3aa28a53ec4b`
- `full-01-evidence/full-01-write-audit.json`, SHA-256 `5746585e5b4d51719cf021f7e7bf087a7c1d416888e1be5e3879ef8493f2ae48`
- `full-01-evidence/full-01-recorder-append-only-final.json`, SHA-256 `c4cb0c6aa4909ea0fe58fe3b4cfd78c7fd36e6f1fbffd266e4d60a4b07679e57`
- `full-01-evidence/raw-captures/SHA256SUMS` and its capture index; the raw-capture checksum verification succeeded.
- Captured pytest stdout: 13,039 bytes, SHA-256 `108600a7e67328011deb9221ff5551caea729efe84fdf3efec1cdf7d55ed08e3`
- Captured pytest stderr: 4,990 bytes, SHA-256 `2870343f5ad61de62a75615eaeffefcf6abab2a36d0d71a8565c23e5662e0a40`

The Recorder’s full-run directory lacks `end.json` and `SHA256SUMS`; corresponding capture, stdout/stderr, run results, raw captures, and R3 checksums remain readable in the persistent R3 root. The outer capture and execution records are retained in the external clone and bound by the run-results receipt.

## Runtime and protected controller

The saved controller invocation and live process evidence show the canonical protected `task_checkpoint.rb --run` chain. The taskcheckpoint, Launcher, and pytest PIDs were 17548, 17573, and 17635. Launcher and pytest shared FD10 lock device 16777232 / inode 252984624. The live lock snapshot is SHA-256 `24ba1dc96553ec30745b04cf7b059cc45ad09dd87aff7438afa2b32f29185f80`.

Recorded runtime root, app-data, and basetemp modes were 0700; effective umask was 0077; pytest cache and basetemp were outside the candidate source worktree. However, the main pytest observer’s open FD3 log inode had link count zero while the current pathname referred to a different inode. The retained current-path snapshot is explicitly partial, not a complete execution trace. Therefore I cannot independently close the actual pytest-child write audit or certify all PID-attributed writes. The `/private/tmp/gate-launch-20261020-17573-14iut56` runtime directory remained present at review; I did not remove it.

## Focused preflight evidence

The exact-tree preflight records support the required focused checks:

- Advanced19: 19 pass, zero fail/error/skip/xfail.
- T249: the existing 27 IDs were exercised in normal and reverse ordering; the saved runs report 46 passing checks each.
- OR-Tools guard: no parent-process solver imports; the loaded-child guard rejects the prohibited case.
- PIN9 current set: 24 passing IDs. The Packet explicitly preserves the historical nine events as NOT_VERIFIED; their attribution remains unresolved.
- Family replay: 21 passing checks; UB 313389300, owner 65555555555433000000, next bound 313388988, open profiles 1513; no network use.

These are focused/preflight evidence for the same E440 tree and were reused where their recorded command/environment and source identity matched. Recorder IDs include `e440-full-gate-r3-family-01`, `...-pin9-01`, `...-pin9-02`, `...-t249-01`, and `...-t249-02`; the `pin9-01` attempt is incomplete. Advanced19 evidence was reused from the exact-tree preflight. This focused evidence does not override the failed FULL suite.

## Ref snapshots and write accounting

I independently parsed the raw before/after snapshots in `full-01-evidence/raw-captures/recorder-run/`, using each row’s refname and object ID (one symbolic `refs/remotes/origin/HEAD` row also carries its target).

- Before: 1,613 unique refnames, 241,358 bytes, SHA-256 `ad258d6d5ddcc61ec337675f0d65b7e3bb7d9ab60df0a72a6e2cc38a6c77cc52`
- After: 1,603 unique refnames, 238,957 bytes, SHA-256 `8ef33bb43a9047e2e151ea2d85acab11287a6890d192f854ab3deb3e5950b28f`
- Source and primary snapshot bytes are identical for both before and after.
- Direct refname-set diff: 7 added, 17 removed, and 1 changed. `refs/heads/main` changed from `bf3cce1443695ae757462a8482288612de48ba3a` to `a7bc0b8d0202bc0562f8094d7f8f75c0434b5bed`.

The postflight JSON binds those same raw snapshot hashes but reports 765 before / 764 after, with 3 added / 4 removed / 1 changed. Those totals do not describe the raw refname snapshots. The separate write-audit JSON contains the exact refname delta. I treat this as a material unresolved receipt inconsistency. The cause and task attribution are UNKNOWN; no refs were changed by this Judge. The isolated external clone’s normalized refs remained equal, which does not reconcile the shared source-repository delta.

Recorder R1 append-only audit: baseline 128 entries, current 85; 128 pre-existing paths are missing and none of the pre-existing paths are reported changed in place. The 85 new paths are confined to six new R3 execution IDs, with no disallowed new paths. The old R1 checkpoint root is absent after the run, although its pre-run snapshot recorded 15 entries and a complete manifest match, including a `judge-report.md` SHA-256 of `028e60ce4b0290a97c3b140b902157e4eb72eb2d1527f6297710c10a9dc22c68`. The verified Launcher and its validation receipt are also absent at their recorded paths after the run. Their expected pre-run hashes are present in the preflight/postflight evidence, but the missing source bytes prevent an independent content check now. Each absence’s cause is UNKNOWN.

The old R2 checkpoint was already absent in the preflight state and its required status was BLOCKED_LAUNCHER_CONTRACT. I do not infer that this run changed it.

## AC01–AC12 adjudication

| Criterion | Decision | Evidence and observed result |
|---|---|---|
| AC01 | PASS | Direct candidate HEAD/tree/parent match all expected values; worktree clean. |
| AC02 | NOT_VERIFIED | Postflight says Launcher and validation receipt paths are absent. Their pre-run hashes are recorded, but the bytes cannot now be independently checked against those hashes. |
| AC03 | PASS | Protected controller invocation is captured; live process snapshot shows Launcher and pytest sharing the same FD10 lock device/inode. |
| AC04 | FAIL | Recorder baseline had 128 entries; all 128 pre-existing paths are now missing. Six new task IDs account for the new paths; no cause is attributed. |
| AC05 | NOT_VERIFIED | Recorded runtime mode, app-data mode, umask, and external cache/basetemp comply. The main observer log inode disappeared/replaced, leaving the actual child write trace incomplete; runtime temp cleanup is unresolved. |
| AC06 | PASS | External clone identity matches; not shallow; no alternates or promisor config; lazy fetch disabled; connectivity check exited 0. |
| AC07 | PASS | Exact-tree focused evidence covers Advanced19, T249, OR-Tools guard, PIN9 current 24, and Family values. Historical PIN9 nine-event attribution remains NOT_VERIFIED as the Packet requires. |
| AC08 | FAIL | Exactly one FULL suite ran, but pytest exited 1 with 50 failed and 310 error progress markers, plus collector `FileExistsError`; outer controller then exited 125 due missing old R1 report. No rerun was performed. |
| AC09 | PASS | R3 retains the run-results manifest, outer capture/execution references, raw stdout/stderr and hash receipts; raw-capture checksum verification passed. Recorder’s own run directory lacks end.json and SHA256SUMS, noted as a limitation. |
| AC10 | PASS | This report is a genuine fresh-context FULL review of the same E440 HEAD/tree. |
| AC11 | FAIL | The previously complete old R1 root and 128 pre-existing Recorder R1 paths are absent after the run. R2 was already absent before this run; no R2 change is asserted. |
| AC12 | NOT_VERIFIED | Candidate product tree is unchanged and external clone refs are stable. Shared source ref snapshots show 7 additions, 17 removals, and one changed main ref, with attribution UNKNOWN; observer write accounting is incomplete. |

## Findings

### F-01 — FULL suite failed

finding_id: F-01  
severity: BLOCKING  
FINDING_CONFIDENCE: CONFIRMED  
claim: The required canonical FULL suite did not pass.  
criterion_or_rule: AC08; Packet requires one canonical FULL suite and forbids a pass label without valid passing evidence.  
evidence: `full-01-run-results.json`; preserved stdout/stderr and SHA-256 values above; pytest exit 1; 11,679 collected markers with 50 failed and 310 errors; sessionfinish collector `FileExistsError`.  
expected: A successful FULL suite with complete result accounting.  
observed: The one permitted run failed. Full failed/error node IDs, first test traceback, and warnings summary are unavailable. The outer task then exited 125 because the old R1 report path was missing.

### F-02 — Recorder append-only history was not preserved

finding_id: F-02  
severity: BLOCKING  
FINDING_CONFIDENCE: CONFIRMED  
claim: Pre-existing Recorder R1 evidence paths are missing after the run.  
criterion_or_rule: AC04 and AC11; only fresh task-specific directories may be added, with existing Recorder evidence preserved.  
evidence: `full-01-recorder-append-only-final.json`, baseline snapshot, and `full-01-write-audit.json`; baseline 128 entries, current 85, 128 pre-existing paths missing, zero pre-existing changed paths, six new task IDs.  
expected: All pre-existing R1 paths retain their original contents and hashes.  
observed: All 128 pre-existing paths are reported missing. The missing-path cause is UNKNOWN; this finding does not attribute deletion to the Worker or another actor.

### F-03 — Old R1 checkpoint and required Launcher inputs are unavailable

finding_id: F-03  
severity: BLOCKING  
FINDING_CONFIDENCE: CONFIRMED  
claim: The old R1 checkpoint root, verified Launcher path, and Launcher validation receipt are absent after execution.  
criterion_or_rule: AC02 and AC11; preserve historical checkpoints and verify the fixed Launcher/receipt hashes.  
evidence: `full-01-final-postflight.json` records the old R1 root and Launcher absent after execution and the R1 pre-run manifest match; direct path checks found the files absent. The outer controller’s stderr names the missing old R1 `judge-report.md`.  
expected: Old R1/R2 evidence is not modified, and the required Launcher bytes and receipt remain available for hash verification.  
observed: The old R1 root and required Launcher/receipt are unavailable. Pre-run expected hashes are recorded but cannot be independently verified from absent files. Cause is UNKNOWN. AC02 is therefore NOT_VERIFIED; AC11 is FAIL due the observed R1 disappearance.

### F-04 — Source-ref receipt summary conflicts with raw snapshots

finding_id: F-04  
severity: BLOCKING  
FINDING_CONFIDENCE: CONFIRMED  
claim: The source-ref postflight summary does not account for the raw refname snapshots, and the snapshots show shared refs changed with unknown attribution.  
criterion_or_rule: AC12; source Git refs must not be modified by this task, and unknown ref drift must remain explicitly unresolved.  
evidence: Raw snapshots’ hashes match the postflight-bound hashes. Independent parsing gives 1,613 → 1,603 unique refnames, +7 / −17 / one changed (`refs/heads/main`, bf3cce1… → a7bc0b8…). The postflight summary instead reports 765 → 764 and +3 / −4 / one changed. Source and primary snapshot bytes are identical.  
expected: Correct, internally consistent ref accounting and no unauthorized ref modifications.  
observed: The receipt totals conflict with the raw evidence; raw snapshots prove a delta, but attribution is UNKNOWN. External clone refs stayed stable. No cause or actor is asserted.

### F-05 — Complete pytest write accounting is unavailable

finding_id: F-05  
severity: BLOCKING  
FINDING_CONFIDENCE: CONFIRMED  
claim: The preserved main observer pathname is not a complete trace of the pytest process’s writes.  
criterion_or_rule: AC05 and AC12; verify pytest child write locations and account for all permitted and forbidden writes.  
evidence: `full-01-main-observer-log-discrepancy.json` records pytest PID 17635’s open FD3 on an inode with link count zero while the pathname snapshot is a different inode; the receipt explicitly labels that snapshot partial.  
expected: A complete observer trace sufficient to attribute pytest writes and verify the runtime boundary.  
observed: The FD3 trace is incomplete. Runtime modes and lock evidence are present, but actual child writes cannot all be independently reconciled. The runtime temp directory also remained present at review; the Judge did not clean it up.

## Coverage, missing evidence, and reuse

COVERED_ITEMS: Exact E440 identity and diff; external Git object closure; protected controller/FD10 evidence; focused Advanced19/T249/OR-Tools/PIN9-current/Family preflight; recorded runtime modes and umask; one canonical FULL invocation and its preserved output; raw-capture checksums; Recorder and ref-delta accounting; fresh-context review.

MISSING_ITEMS: Independent current bytes for `launch_gate.rb` and `provenance-validation.json`; 128 pre-existing Recorder paths and old R1 checkpoint contents; complete main pytest observer trace; authoritative full failed/error node IDs, first test traceback, and warning summary; consistent postflight refname accounting and attribution; resolved runtime-temp cleanup disposition.

REUSED_EVIDENCE: Exact-tree formal preflight for Advanced19 and relevant T249/OR-Tools checks; the saved exact-tree focused Family and PIN9 runs; raw full-run captures and SHA-256-verified R3 copies. Reuse was limited to evidence whose recorded source identity matched the E440 HEAD/tree. The FULL suite was not reused as a pass.

INVALIDATED_OR_UNAVAILABLE_EVIDENCE: No candidate source identity change was observed, so same-tree evidence was not invalidated by a tree change. The old R1 contents and 128 historical Recorder paths are unavailable and were not treated as reusable. The current-path main observer snapshot is partial and cannot support a complete write audit. The failed FULL run remains valid evidence of a failed run, not of a pass.

ACTUAL_VERIFICATION_RUN_COUNTS:
- Canonical FULL suite: 1 run; 0 reruns.
- Judge-initiated FULL suite runs: 0.
- Focused Recorder IDs: five (Family, PIN9-01 incomplete attempt, PIN9-02, T249-01, T249-02); Advanced19 reused from exact-tree preflight.
- Historical PIN9 attribution events: 9 remain NOT_VERIFIED as instructed by the Packet.

## Scope, lifecycle, and next action

This Judge made no source, test, Git-ref, commit, remote, publication, or cleanup changes. Its only persistent write was this report, created exclusively at the Packet-authorized path. No tests were run during the Judge review. No commit, push, PR, merge, deployment, branch cleanup, or remote write was performed by the Judge. The run’s shared source-ref changes have UNKNOWN attribution; local snapshots cannot prove whether a remote write occurred, and none is claimed.

Technical outcome: REFUTED.  
Authorization: this read-only review and this report write were authorized.  
Publication: NOT RUN.  
Cleanup: NOT RUN; the task runtime directory was left untouched.  
TASK_STATUS: FULL_SUITE_FAILED.  
FULL_SUITE_PASS: NO.  
OLD_R1_VERDICT: REFUTED.  
OLD_R2_STATUS: BLOCKED_LAUNCHER_CONTRACT.

No second FULL run is authorized under this Packet. Preserve this verdict and route the findings to the Owner/Planner for a separate decision. Any later remediation must remain within the canonical one-bounded-remediation limit and use a DELTA re-Judge; this Judge does not repair the candidate or missing evidence.

