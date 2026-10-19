# Task-local Gate launch recorder

Executable: `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb`

The recorder uses the deployed, blob-pinned Fable `DurableCommandCapture` implementation. It does not modify Fable, create an execution registry, initialize Git metadata, install dependencies, or infer a different candidate. All persistent recorder files remain under this task's fixed output root. Every execution ID is exclusive: an existing directory is rejected and retained, including after an interrupted attempt. Do not change IDs to bypass a failed or unresolved run.

The validated final executions are `normal-smoke-final` and `negative-smoke-final`. The two `*-r1` executions are retained preliminary smoke evidence from before adding explicit candidate selection arguments. No pytest collection, pytest test suite, or solver was executed.

## Interface

```text
launch_gate.rb --execution-id STABLE_ID --kind smoke|pytest
  [--python ABSOLUTE_EXISTING_PYTHON_3_13]
  [--cwd ABSOLUTE_EXTERNAL_DIRECTORY]
  [--source-worktree ABSOLUTE_READ_ONLY_SOURCE
   --expected-head FULL_COMMIT_OID --expected-tree FULL_TREE_OID]
  -- UPSTREAM_ARGUMENTS...
```

Candidate selection defaults to the Packet's e440 source, HEAD and tree. To select another explicitly authorized fixed candidate, supply all three source/head/tree arguments together. The selected source must be an exact, clean Git worktree root. The recorder verifies full OIDs; it never checks out, resets, fetches, updates refs, or copies a worktree. A future Packet must authorize that candidate, the execution, and new receipts under the fixed recorder output root. The old Judge hash remains independently pinned and unchanged.

`--python` defaults to `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python`. The metadata probe rejects any Python other than 3.13 and records its actual version, executable and real executable, installed distribution names/versions, pytest version, and source lockfile hashes. It neither synchronizes nor installs dependencies.

For smoke, upstream arguments follow Python's inserted `-B`. An omitted cwd becomes a newly created external `work` directory. The exact validated command shape was:

```bash
/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb \
  --execution-id normal-smoke-final --kind smoke \
  --source-worktree /Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_ADV11_DESCENDANT_STABLE_CONTEXT_R1 \
  --expected-head e440d4298551ce93ef3ea9a9226143784afa3eff \
  --expected-tree 294cbf6bbe7ee8a8ebad947f397852edc1981b57 \
  -- /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py 0
```

That execution ID already exists and must not be rerun. The negative execution uses `negative-smoke-final` and argument `23`; it returned exactly 23 with its original streams.

## Future formal Gate invocation — NOT RUN in this task

Long-running execution must retain the deployed canonical Fable `--run` outer supervisor. `--kind pytest` fails closed without its inherited FD 10. This adapter does not replace protected acquisition, recovery, or task locking. It passes that open lock to the actual Python child through Fable's capture helper.

The next task must first provide an authorized, external **standalone** test checkout at its declared fixed commit/tree, with independent Git metadata, no shallow state or alternates, and an already initialized/verified Fable generation-2 lock authority. Creation/initialization is not performed here. Existing foreign worktrees and previous tasks' temporary repositories must not be repurposed. The outer CLI writes its ExecutionRecord/capture and lock metadata to that external test repository. This adapter writes its launch/capture/end receipts directly to this task's persistent root before the outer capture completes. Preserve both sets in the next task's accounting.

After substituting exact paths/OIDs and stable IDs from the next authorized Packet, the command is:

```bash
ruby /Users/kelvin/.codex/skills/fable-method/scripts/task_checkpoint.rb \
  --run \
  --repo "$GATE_TEST_REPO" \
  --worktree "$GATE_TEST_REPO" \
  --task-id "$GATE_TASK_ID" \
  --execution-id "$GATE_PROTECTED_EXECUTION_ID" \
  -- /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb \
  --execution-id "$GATE_RECORDER_EXECUTION_ID" --kind pytest \
  --source-worktree "$GATE_READ_ONLY_SOURCE" \
  --expected-head "$GATE_EXPECTED_HEAD" --expected-tree "$GATE_EXPECTED_TREE" \
  --python /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python \
  --cwd "$GATE_TEST_REPO" \
  -- -q
```

These shell variables are caller-supplied exact inputs, not executable defaults or discovery instructions. Nothing in this document authorizes running a FULL suite. The pytest/protected-parent branch is **NOT_RUN** here; its future runtime validation belongs to the next Gate task.

The actual Python command is built as an argv array without a shell:

```text
PYTHON -B -m pytest --basetemp=NEW_EXTERNAL_ROOT/basetemp
  -o cache_dir=NEW_EXTERNAL_ROOT/pytest-cache CALLER_PYTEST_ARGUMENTS...
```

For a future full suite, `-q` invokes the repository's default full collection from the external checkout; this task makes no suite-result claim. Do not supply a conflicting basetemp/cache override or additional reporter/output flags outside the next task's allowlist. `PYTHONPATH` points only at the external checkout's `src`. Runtime roots are newly and exclusively created under `/private/tmp/gate-launch-*`, mode 0700, with umask 0077. The actual app-data variable is `LOTTOLAB_DATA_DIR`, as specified by the pinned RUNBOOK. Python bytecode is disabled, and temp, bytecode/cache, pytest cache, app-data and HOME are bound outside protected worktrees. The child receives a minimal constructed environment; inherited credentials and unrelated environment variables are neither forwarded nor serialized.

## Receipts and accounting

Each execution writes `runs/ID/launch.json`, `capture.json`, `end.json`, `stdout.txt`, `stderr.txt`, `dependencies.json`, complete source/primary refs and porcelain status before/after, and `SHA256SUMS`. `launch.json` is written exclusively, flushed, fsynced together with its parent directory, and read back inside Fable's `before_spawn` callback before `Open3.popen3` starts the actual child. The child smoke independently opens and hashes this receipt; its output records the observed PID, PPID, cwd, Python, pytest, actual app-data, umask and modes. A 0600 task-owned file tests the effective inherited umask.

Fable's existing schema-1 terminal capture preserves command, stdout, stderr, exit_status, started_at, ended_at and execution_identity. The end receipt records stream locators/hashes, post snapshots, explicit ref/status differences, and the adapter's writes/runtime inventory. An original nonzero child exit remains a nonzero launcher exit after receipts are saved. Unexpected adapter failures return 125 and retain partial evidence; they are not successful child runs.

All observed ref changes remain recorded. Endpoint snapshots cannot identify an actor or exclude transient changes; unsupported attribution is `UNKNOWN`. The adapter records its own actions and endpoint manifests; it is not an OS/filesystem sandbox and cannot prove that an arbitrary future test child wrote nowhere else. The next task must account for its child behavior and consumers separately.

The original `validation.json` deliberately remains unchanged: two whole-session equality checks were false because a shared ref and unrelated primary untracked files appeared between preflight and final observation. This is an observed shared-state delta, separate from the passing final smoke checks. `acceptance.json` and `worker-report.md` retain that delta and its `UNKNOWN` attribution; neither asserts globally quiescent refs.

Verify the final persistent bundle from its fixed root using `shasum -a 256 -c SHA256SUMS`. The index excludes itself to avoid self-reference. Per-run indexes likewise exclude themselves. Runtime directories are retained, contain only the controlled probe files in these smoke runs, and may be removed only by an explicitly authorized task-owned cleanup.
