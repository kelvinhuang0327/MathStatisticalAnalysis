# Isolated launcher revalidation

This is a new forward validation. The original launcher, historical receipts, historical `NOT_VERIFIED` disposition and old Judge `REFUTED` report remain unchanged. The tested launcher is the original executable at `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb`, SHA256 `e9d3e5e03fded1974fb16fcb177cfc96ccc817bf8e72d2084ff7407a4383be62`.

The successful evidence is the remediated pair `ac10-isolated-normal-r2` and `ac10-isolated-negative-r2`. Both are complete; do not rerun those IDs. The first pair is preserved with `audit-coverage-r1.json: FAIL` because child audit/spawn coverage was missing. No result was deleted, overwritten or promoted to a pass retroactively.

## Actual environment and command

The task-owned external root is `/private/tmp/gate-ac10-cb5uv2in`. Its `source` directory is an independent local Git clone created with `--local --no-hardlinks --no-checkout --no-tags`, then detached at the exact e440 commit and stripped of its origin remote before the observation baseline. Its own `.git` is independent, with no shallow state, alternates or remaining remote. The complete 2,556-entry source/Git filesystem manifest, including modes, mtimes and content hashes, is identical before and after the remediated smoke pair.

The external `python-env` was created without pip; no dependency install or upgrade occurred. Its read-only dependency path points at the existing project's installed packages. The actual child records Python 3.13.8 and pytest 9.1.1. `ac10-observer.pth` installs the task's Python audit hook during interpreter startup. Homebrew's stdlib `sitecustomize` takes precedence over the initially attempted venv `sitecustomize`; that failed coverage method is retained in the attempt evidence. Python may process the startup path twice; validation deduplicates identities by PID and requires every observed Python PID to have its own hook and write-denial evidence.

The exact successful top-level invocation was:

```bash
/usr/bin/sandbox-exec \
  -f /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/smoke-r2.sb \
  /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -B \
  /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/run_pair.py \
  config-r2.json
```

That harness passes these arguments to the original launcher for each of the two stable IDs:

```text
/usr/bin/ruby -r ABSOLUTE_NEW_EVIDENCE_ROOT/ruby_observer.rb ORIGINAL_LAUNCHER
  --execution-id ac10-isolated-normal-r2|ac10-isolated-negative-r2
  --kind smoke
  --python /private/tmp/gate-ac10-cb5uv2in/python-env/bin/python
  --source-worktree /private/tmp/gate-ac10-cb5uv2in/source
  --expected-head e440d4298551ce93ef3ea9a9226143784afa3eff
  --expected-tree 294cbf6bbe7ee8a8ebad947f397852edc1981b57
  -- ORIGINAL_SMOKE_PROBE 0|23
```

`config-r2.json`, the dispatch receipts and process logs contain the exact expanded argv/PIDs. No shell-string reconstruction occurs. The Ruby observer rebinds only `Dir.mktmpdir('gate-launch-', '/private/tmp')` to the task-exclusive `runtime` parent, recording both requested/effective values. The original launcher's bytes, source-pin checks, environment construction, before-spawn fsync/readback, formal Fable capture and original exit/stream behavior are unchanged. The effective runtime location is recorded by the launcher and independently observed in the actual child.

## Enforcement and observation

The strict kernel policy starts at the Python harness entry point and is inherited by Ruby, every Git query, both metadata probes, and both actual smoke children. It denies network access and all filesystem writes except the new evidence root, task-owned runtime parent, the two new run directories and `/dev/null`. Original source, original Git metadata/refs, old receipts/Judge, dependencies and the independent source/.git are outside the write allowlist. No root privileges, system settings or tracing configuration are changed.

Python audit events identify harness/child PID, PPID, executable, requested write paths and subprocess invocations. Ruby hooks record successful receipt opens/writes, exact temporary filenames/rename, directories and Open3 spawn edges; a native spawn TracePoint provides a second PID observation. Git Trace2 ties each actual signed Git process to its PID and exact read-only query. Each run accounts for 43 Ruby children: 41 Git queries and two Python processes (metadata probe and actual smoke). The verifier reconciles those sets exactly.

The harness, two Ruby processes and four Python children attempt to create a harmless new file inside **this task's independent** `.git`. Every distinct PID receives EPERM/EACCES and no probe file exists. No probe targets an existing source ref or product file. These active denials, the inherited policy, all observed writer paths and identical complete source/Git manifests establish AC10 for this forward validation interval. The first preparation sandbox permitted only the new independent Git metadata to be constructed; it never permitted existing source Git writes.

This combines trusted runtime API observations, Git process tracing, kernel write confinement and before/after filesystem evidence. It is not a root-level global syscall trace or a malicious same-UID adversary guarantee. Ambient changes outside the controlled process tree cannot be assigned an actor from names alone. The remediated pair's saved host-source refs manifests are identical; historical unknown attribution is not reconstructed or cleared.

## Reuse and retained attempts

For a newly authorized smoke revalidation, use a fresh task-owned OS temporary root, explicit exact candidate pins, new stable IDs and a matching policy/config; preserve the previous evidence. `revalidate.py` is the preparation stage under `controller.sb`, and `run_pair.py` is the separate strict observation stage. macOS rejects nested `sandbox_apply`, so the strict policy must be applied at that stage's process entry, not nested inside an already sandboxed preparation process. Existing completed or partial run IDs are never recycled.

Two setup/orchestration errors are retained: audit JSON initially could not serialize a `Path` before the first Git child started, and nested sandbox application was rejected before any smoke child started. Their dispatch/error logs and attempted source are preserved. The later first pair ran normally but failed audit coverage, prompting the explicitly recorded observer-remediation pair. Exactly four smoke children ran in this new revalidation: normal/nonzero before and after observer remediation. No pytest collection, pytest suite or solver ran.

Future FULL Gate use still needs its own authorization, canonical Fable protected supervisor, appropriate runtime-output policy and consumer validation. This task neither executes nor certifies that branch. Runtime/temp roots are retained; only task-owned paths may be considered for a separately authorized cleanup.

All new persistent evidence and all four new run directories are covered by this revalidation's absolute-path `SHA256SUMS`. The original root index is unchanged and still verifies its original 69 entries.
