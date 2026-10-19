# Isolated AC10 revalidation receipt

TASK_STATUS: GATE_LAUNCH_RECORDER_VALIDATED
ATTEMPT: AC10_ISOLATED_R2
IMPLEMENTATION_DEPTH: NORMAL
DEPTH_SOURCE: PLANNER_SUPPLIED
TASK_CLASS: STATE_CHANGING_IMPLEMENTATION
WORKER_ROUTE: STANDARD
JUDGE_MODE: NOT_APPLICABLE
JUDGE_DISPATCH: SUPPRESSED

此次獨立 R2 重驗 AC01–AC10 全部 PASS。這是新執行的 forward validation；原始 task 的 NOT_VERIFIED、第一對觀測覆蓋不足的 smoke、舊 Judge 的 REFUTED 均保留原樣。

INTENT: code does the original Fable-backed launcher capture; the check/task expects process/harness-origin evidence sufficient for AC10; the opened spec and Owner continuation require an independent Git environment, normal/nonzero smoke only, and preserved source refs/product/historical evidence.

ACTUAL_RULES_LOADED: installed /Users/kelvin/.codex/skills/fable-method/SKILL.md; references/task-checkpoint.md, operational-gates.md, reporting.md, workspace-containment.md; original e440 README/RUNBOOK necessary runtime/data/Git/evidence sections inherited from the original verified locator.
OWNER_AUTHORIZATION: 請在獨立 Git 環境重新驗證啟動器，加入程序／harness 寫入來源觀測，補齊 AC10。只跑正常與非零退出 smoke，保留既有收據與舊 Judge，不修改產品或既有 source refs，也不要跑 FULL Suite 或 solver。

REFERENCE_HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
REFERENCE_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
ISOLATED_SOURCE: /private/tmp/gate-ac10-cb5uv2in/source
ISOLATED_GIT_COMMON_DIR: /private/tmp/gate-ac10-cb5uv2in/source/.git
SHALLOW: false; ALTERNATES: absent; REMOTES: none; INDEPENDENT_OBJECTS: clone --local --no-hardlinks
SOURCE_MANIFEST_ENTRIES: 2556; complete source/Git content, modes and mtimes identical before/after

LAUNCHER_PATH: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb
LAUNCHER_SHA256: e9d3e5e03fded1974fb16fcb177cfc96ccc817bf8e72d2084ff7407a4383be62
PERSISTENT_OUTPUT_ROOT: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1
RECORDED_PYTHON: /private/tmp/gate-ac10-cb5uv2in/python-env/bin/python — Python 3.13.8
RECORDED_PYTEST: 9.1.1
APPDATA_MODE: 0700
EFFECTIVE_UMASK: 0077
EVIDENCE_INDEX: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/SHA256SUMS
OBSERVATION_INTERFACE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/isolation-usage.md

## ac10-isolated-normal-r2

LAUNCH_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-normal-r2/launch.json; 2026-10-19T14:36:29.744439000Z
END_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-normal-r2/end.json; 2026-10-19T14:36:31.308751000Z
RECORDED_ARGV: ["/private/tmp/gate-ac10-cb5uv2in/python-env/bin/python", "-B", "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py", "0"]
RECORDED_CWD: /private/tmp/gate-ac10-cb5uv2in/runtime/gate-launch-20261019-19663-1vg5wyx/work
APPDATA_PATH: /private/tmp/gate-ac10-cb5uv2in/runtime/gate-launch-20261019-19663-1vg5wyx/appdata
BASETEMP_PATH: /private/tmp/gate-ac10-cb5uv2in/runtime/gate-launch-20261019-19663-1vg5wyx/basetemp
DEPENDENCY_FINGERPRINT: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-normal-r2/dependencies.json; SHA256 009e63d71b1918eaa07f7a0b51a0c68e8bfbce8e333bbdf649fecce6a03ee54b
EXECUTOR_PID: 19663; HARNESS_PID: 19637; SMOKE_PID: 19696
PYTHON_CHILD_PIDS: [19675, 19696] (metadata + actual smoke)
GIT_CHILD_COUNT: 41; all reconciled with Ruby spawn PID and Git Trace2 SID
OBSERVED_RECEIPT_WRITERS: 15 files; each attributed to Ruby PID 19663; exact capture temporary file/rename recorded
EXIT: 0
STDOUT_STDERR_RESULTS: original dispatch/capture/files equal; stderr marker exactly preserved
REFS_BEFORE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-normal-r2/source-refs-before.txt
REFS_AFTER: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-normal-r2/source-refs-after.txt
REFS_DIFF: {"removed": [], "added": []}
SOURCE_STATUS_DIFF: {"removed": [], "added": []}
LAUNCH_RECEIPT_SHA256: b6a6cac93c06c46967c1a61726a3110f107436c2499d87af70d6208a72aecb12
TERMINAL_CAPTURE_SHA256: a5b3831495e439927c3ee9333621633440d0e66e3b7a16e56e97f433e3b8c69f
END_RECEIPT_SHA256: 092e98c1ce9db95916bd8d5fe90188206fcd6a14177fa5e9e8669af317e2d35c
PYTHON/RUBY_OBSERVERS: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/ruby-19663.jsonl; /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/python-child-19696.jsonl, /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/python-child-19675.jsonl

## ac10-isolated-negative-r2

LAUNCH_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-negative-r2/launch.json; 2026-10-19T14:36:33.791885000Z
END_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-negative-r2/end.json; 2026-10-19T14:36:35.466237000Z
RECORDED_ARGV: ["/private/tmp/gate-ac10-cb5uv2in/python-env/bin/python", "-B", "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py", "23"]
RECORDED_CWD: /private/tmp/gate-ac10-cb5uv2in/runtime/gate-launch-20261019-19714-lhyh3w/work
APPDATA_PATH: /private/tmp/gate-ac10-cb5uv2in/runtime/gate-launch-20261019-19714-lhyh3w/appdata
BASETEMP_PATH: /private/tmp/gate-ac10-cb5uv2in/runtime/gate-launch-20261019-19714-lhyh3w/basetemp
DEPENDENCY_FINGERPRINT: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-negative-r2/dependencies.json; SHA256 009e63d71b1918eaa07f7a0b51a0c68e8bfbce8e333bbdf649fecce6a03ee54b
EXECUTOR_PID: 19714; HARNESS_PID: 19637; SMOKE_PID: 19744
PYTHON_CHILD_PIDS: [19723, 19744] (metadata + actual smoke)
GIT_CHILD_COUNT: 41; all reconciled with Ruby spawn PID and Git Trace2 SID
OBSERVED_RECEIPT_WRITERS: 15 files; each attributed to Ruby PID 19714; exact capture temporary file/rename recorded
EXIT: 23
STDOUT_STDERR_RESULTS: original dispatch/capture/files equal; stderr marker exactly preserved
REFS_BEFORE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-negative-r2/source-refs-before.txt
REFS_AFTER: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/ac10-isolated-negative-r2/source-refs-after.txt
REFS_DIFF: {"removed": [], "added": []}
SOURCE_STATUS_DIFF: {"removed": [], "added": []}
LAUNCH_RECEIPT_SHA256: 9c791343cba00f43945f28b678377cf84b8de21bc3ab73cbe29637a6ceef25a4
TERMINAL_CAPTURE_SHA256: 5ba44068833ffc04384e80840c0f5bcf6cdba35a80283d90265315987bd31d28
END_RECEIPT_SHA256: c12457debc50a83131c223e90ca187374f881b58f5118b26882cb51e79c855e8
PYTHON/RUBY_OBSERVERS: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/ruby-19714.jsonl; /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/python-child-19723.jsonl, /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/python-child-19744.jsonl

## AC01–AC10

| AC | 結果 | 直接證據與觀察 |
|---|---|---|
| AC01 | PASS | Pinned source and independent clone HEAD/tree/parent match; old Judge SHA unchanged. [strict-r2-isolated-before.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-isolated-before.json); [strict-r2-host-before.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-host-before.json); [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json) |
| AC02 | PASS | Actual child reads/hashes pre-spawn receipt; Ruby launch commit event precedes Python observer startup. [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json); [execution-result-r2.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/execution-result-r2.json) |
| AC03 | PASS | Parent/child umask 0077; app-data 0700; task-exclusive external temp/cache; observed probe 0600. [execution-result-r2.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/execution-result-r2.json); [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json) |
| AC04 | PASS | Actual argv/cwd/PIDs, Python 3.13.8, pytest 9.1.1, installed dependencies and source lock fingerprints persisted. [execution-result-r2.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/execution-result-r2.json) |
| AC05 | PASS | Complete ref/status snapshots plus full isolated filesystem and Git metadata before/after. [strict-r2-isolated-before.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-isolated-before.json); [strict-r2-isolated-after.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-isolated-after.json); [strict-r2-host-before.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-host-before.json); [strict-r2-host-after.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-host-after.json) |
| AC06 | PASS | Isolated refs and existing host refs unchanged in the observed R2 interval; all deltas explicitly empty. Historical UNKNOWN attribution remains untouched. [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json); [strict-r2-host-before.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-host-before.json); [strict-r2-host-after.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-host-after.json) |
| AC07 | PASS | Normal smoke actual exit 0; original stdout/stderr exactly equal dispatch, capture and separate files. [ac10-isolated-normal-r2-dispatch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/ac10-isolated-normal-r2-dispatch.json); [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json) |
| AC08 | PASS | Negative smoke actual exit 23 with exact negative-smoke-stderr; no swallowed failure. [ac10-isolated-negative-r2-dispatch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/ac10-isolated-negative-r2-dispatch.json); [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json) |
| AC09 | PASS | Persistent launch/capture/end and observer/Git traces are readable and indexed; all new run files are covered by SHA256SUMS. [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json); [SHA256SUMS](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/SHA256SUMS) |
| AC10 | PASS | For this new isolated R2 interval: inherited kernel write/network confinement, seven distinct PID denial probes, complete spawn reconciliation, observed writers for every run receipt and child probe, only read-only Git commands, identical full source/.git manifests, unchanged existing source refs/old files/Judge; no suite or solver. [provenance-validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/provenance-validation.json); [smoke-r2.sb](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/smoke-r2.sb); [strict-controller-r2-dispatch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-controller-r2-dispatch.json); [strict-r2-isolated-before.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-isolated-before.json); [strict-r2-isolated-after.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/strict-r2-isolated-after.json); [execution-result-r2.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/isolated-revalidation-r1/execution-result-r2.json) |

## AC10 寫入來源與邊界

macOS sandbox 在 strict harness 入口啟用，整個 Ruby/Git/Python 子程序樹繼承；禁止 network 與 allowlist 外所有寫入。allowlist 僅新 evidence root、任務獨占 runtime parent、兩個 R2 run dir 與 /dev/null。既有 source/.git、舊收據、dependency 安裝與獨立 source/.git 均不可寫。
7 個不同 PID 的無害獨立 .git 新檔探針均返回 EPERM/EACCES 且檔案不存在：[19637, 19663, 19675, 19696, 19714, 19723, 19744]。沒有對既有 source ref 或產品檔進行寫入探測。
Ruby File/IO/Dir/Open3/native spawn、Python audit 與 Git Trace2 實際事件可交叉核對；每次 43 個子程序的集合精確等於 41 個唯讀 Git 與 2 個 Python。兩次 actual smoke 的 probe file 亦有 Python PID 寫入事件。
每個新 run 的 15 個持久檔案都有 writer PID；同目錄 capture 暫存檔建立與 rename 也被實際觀察。沒有僅由終態推定刪除來源。
既有 source refs 在此次 R2 前後快照沒有差異；完整 manifests 位於 strict-r2-host-before.json / strict-r2-host-after.json。獨立 repository 的所有產品及 Git metadata 位元組/mode/mtime 完全相同。
REFS_ATTRIBUTION_LIMIT: 此次 controlled interval 無 drift；歷史 UNKNOWN 不回填。不聲稱有 root-level global syscall trace、所有 host app 的寫入 actor，或同 UID 惡意程序防護。受控流程之外的環境不能只依 ref 名稱歸因。

## 保留與實際寫入帳

ORIGINAL_FILES_PRESERVED: 70 (含原始 69-entry index 本身)；所有內容與 mode 未變。
ALL_PRIOR_RECEIPTS_PRESERVED: 128 at R2 closure, including first pair and orchestration failures.
TASK_WRITES: 新 isolated-revalidation-r1 evidence/code/profile/trace/report/index；四個新 run directories；任務獨占 /private/tmp/gate-ac10-cb5uv2in 內的獨立 clone、無 pip 的 Python env、observer bootstrap 與四個 runtime roots。
GIT_METADATA_PREPARATION: 只在新 clone 於 smoke baseline 前執行 clone/checkout --detach/remote remove origin；命令與 PID 於 setup.json、Git trace、Python harness events 保存。既有 source metadata 不在準備階段 sandbox 寫入 allowlist。
FILES_DELETED_BEFORE_END: 無 cleanup/delete；Fable capture 的 temporary-name → capture.json 為實測 rename。
WORKTREE_MATERIALIZATION_CREATED: 新的 task-owned independent clone；無 git worktree add、無共用 metadata、無接管既有工作樹。
HARNESS_GIT_METADATA_WRITES_DURING_R2: NONE; protected by inherited policy and identical full Git manifest.
GIT_NETWORK_METADATA_WRITES: NONE; no network capability during controlled preparation/smoke.
UNAUTHORIZED_WRITE_EVENTS: NONE observed in the controlled R2 process tree; only explicitly denied harmless probe requests in task-owned .git. Existing source ref/product write capabilities were denied by the inherited policy.

Two orchestration errors and observer coverage remediation are explicitly retained in isolation-usage.md/audit-coverage-r1.json. Four new smoke children ran (two normal, two nonzero); final acceptance uses only R2. No pytest collection, suite or solver.

FULL_SUITE_RERUN: NO
SOLVER_RUN: NO
SOURCE_CHANGED: NO
GIT_REFS_CHANGED_BY_TASK: NO existing source refs; independent clone metadata only prepared before baseline
REMOTE_WRITE: NO
OLD_JUDGE_VERDICT: REFUTED
OLD_JUDGE_SHA256: 028e60ce4b0290a97c3b140b902157e4eb72eb2d1527f6297710c10a9dc22c68
HISTORICAL_ORIGINAL_TASK_STATUS: NOT_VERIFIED (unchanged)
COMMIT/PUSH/PR/MERGE/DEPLOY/CLEANUP: NOT_RUN
REMAINING_TASK_MODEL: 強模型 — 新固定Tree的正式FULL Gate；此輪未執行亦未授權FULL Suite

原 launcher 位元組不變；唯一 runtime allocator 綁定由觀測層明確記錄，使暫存只落在本任務根下。未修改產品、Fable skill 或舊 Judge。
