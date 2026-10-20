# Worker execution receipt

TASK_ID: B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1
TASK_STATUS: NOT_VERIFIED
RECORDER_SMOKE_STATUS: VALIDATED
TASK_CLASS: STATE_CHANGING_IMPLEMENTATION
WORKER_ROUTE: STANDARD
JUDGE_MODE: NOT_APPLICABLE
JUDGE_DISPATCH: SUPPRESSED
IMPLEMENTATION_DEPTH: NORMAL
DEPTH_SOURCE: PLANNER_SUPPLIED

啟動器與最終正常／非零退出 smoke 的啟動、環境、輸出及退出證據通過；整體不宣告完全驗收。AC10 因共用 refs 變化缺乏 actor／harness write 歸因證據而為 NOT_VERIFIED。沒有執行 pytest Suite、collection 或 solver。

INTENT: code does terminal-only capture through the existing Fable helper; the check/task expects launch-time environment and before/after refs persisted around the actual child; the opened spec says use a task-local entry, preserve source and historical Judge, and run only controlled Python 3.13 smoke.

ACTUAL_RULES_LOADED:
- /Users/kelvin/.codex/skills/fable-method/SKILL.md — SHA256 d9ce3ab741820c55822584db4ed876db83ee8cf8b3fef31bd1a0c6dd899b58ee
- /Users/kelvin/.codex/skills/fable-method/references/task-checkpoint.md — SHA256 ddec42a39a41919833fc04e7d351bea85c3cf5d7f097088667e23646871d4c9a
- /Users/kelvin/.codex/skills/fable-method/references/operational-gates.md — SHA256 f87b59104179cbafc84c96804d4a5438cda63e49e48d222a4624cf6e707d64c2
- /Users/kelvin/.codex/skills/fable-method/references/reporting.md — SHA256 b56f8af1833727ec16f114b7fd08599c4cc152eb5b28617d144934b741397e23
- /Users/kelvin/.codex/skills/fable-method/references/implementation-depth.md — SHA256 a597f6a1f428e7b7db4fe5009a225ca38692483933feaaabeceadfb346cb6808
- /Users/kelvin/.codex/skills/fable-method/scripts/task_checkpoint.rb — SHA256 babba3757a7ea9ad59c7ff9b18b6e4497dbc887b86eebfb09ccae1a36ab96275
- git:e440d4298551ce93ef3ea9a9226143784afa3eff:README.md — Git blob 89170cf4311c06b38c3072b13975a082a8e15cde; loaded necessary line ranges [[11, 45], [212, 227]]
- git:e440d4298551ce93ef3ea9a9226143784afa3eff:.ai/ai-context/RUNBOOK.md — Git blob e146a33a6338328fc8bfcee830ad820b90a0b193; loaded necessary line ranges [[5, 20], [65, 123], [150, 161]]

未發現適用的祖先或所選 source／primary root AGENTS.md。實際讀取範圍為 Python／runtime/data-dir、Git/worktree、evidence retention，以及本輪啟動與收據相關 Fable 合約。

REFERENCE_HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff
REFERENCE_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57
REFERENCE_PARENT: 86f644010f41cd627f436c8d5cf9e0b5cca8fcdc
OLD_JUDGE_SHA256: 028e60ce4b0290a97c3b140b902157e4eb72eb2d1527f6297710c10a9dc22c68
OLD_JUDGE_VERDICT: REFUTED

LAUNCHER_PATH: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb
LAUNCHER_SHA256: e9d3e5e03fded1974fb16fcb177cfc96ccc817bf8e72d2084ff7407a4383be62
LAUNCHER_MODE: 0700
PERSISTENT_OUTPUT_ROOT: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1
EXECUTION_INTERFACE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launcher-usage.md
CANONICAL_FABLE_PATH: /Users/kelvin/.codex/skills/fable-method/scripts/task_checkpoint.rb
CANONICAL_FABLE_BLOB: 00e2cf4a4f06b0f0a8d8e4be6091a4304e6e2ae4
CANONICAL_FABLE_SHA256: babba3757a7ea9ad59c7ff9b18b6e4497dbc887b86eebfb09ccae1a36ab96275

RECORDED_PYTHON: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python — Python 3.13.8
RECORDED_PYTEST: 9.1.1 (metadata and actual child independently agree)
APPDATA_MODE: 0700
EFFECTIVE_UMASK: 0077 (parent and actual child; child file created as 0600)

## 最終 smoke 的直接執行證據

### normal-smoke-final

LAUNCH_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/launch.json; 2026-10-19T14:07:19.746889000Z
END_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/end.json; 2026-10-19T14:07:20.637413000Z
RECORDED_ARGV: ["/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python", "-B", "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py", "0"]
RECORDED_CWD: /private/tmp/gate-launch-20261019-12572-sn9d04/work
APPDATA_PATH: /private/tmp/gate-launch-20261019-12572-sn9d04/appdata
BASETEMP_PATH: /private/tmp/gate-launch-20261019-12572-sn9d04/basetemp
RUNTIME_ROOT: /private/tmp/gate-launch-20261019-12572-sn9d04
DEPENDENCY_FINGERPRINT: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/dependencies.json; SHA256 009e63d71b1918eaa07f7a0b51a0c68e8bfbce8e333bbdf649fecce6a03ee54b
EXECUTOR_PID: 12572; observed child PID 12601; observed PPID 12572
BEFORE_SPAWN_READBACK: PASS; child observed receipt SHA bdec09e96beab9712614944976170b808d40e57eb67cafaad47603898214ce09; receipt mtime_ns 1792418839747804085 <= child start_ns 1792418839956598000
EXIT: 0; expected 0
STDOUT_STDERR_RESULTS: dispatch, Fable capture, separate stream files and their SHA256 match exactly; stderr 'normal-smoke-stderr\n'
REFS_BEFORE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/source-refs-before.txt; count 1619; SHA256 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5
REFS_AFTER: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/source-refs-after.txt; count 1619; SHA256 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5
REFS_DIFF: {"removed": [], "added": []}
SOURCE_STATUS_DIFF: {"removed": [], "added": []}
FORMAL_FABLE_CAPTURE: EVIDENCE_COMPLETE (actual installed loader/classifier), schema 1

### negative-smoke-final

LAUNCH_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/launch.json; 2026-10-19T14:07:21.839636000Z
END_TIME_CAPTURE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/end.json; 2026-10-19T14:07:22.685591000Z
RECORDED_ARGV: ["/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python", "-B", "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py", "23"]
RECORDED_CWD: /private/tmp/gate-launch-20261019-12625-ft7sy0/work
APPDATA_PATH: /private/tmp/gate-launch-20261019-12625-ft7sy0/appdata
BASETEMP_PATH: /private/tmp/gate-launch-20261019-12625-ft7sy0/basetemp
RUNTIME_ROOT: /private/tmp/gate-launch-20261019-12625-ft7sy0
DEPENDENCY_FINGERPRINT: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/dependencies.json; SHA256 009e63d71b1918eaa07f7a0b51a0c68e8bfbce8e333bbdf649fecce6a03ee54b
EXECUTOR_PID: 12625; observed child PID 12663; observed PPID 12625
BEFORE_SPAWN_READBACK: PASS; child observed receipt SHA 86437e75cd1fbd2194dc0b5e3eb81a3e2f8b990f2d9afe039d67910e648505c4; receipt mtime_ns 1792418841840612295 <= child start_ns 1792418842021038000
EXIT: 23; expected 23
STDOUT_STDERR_RESULTS: dispatch, Fable capture, separate stream files and their SHA256 match exactly; stderr 'negative-smoke-stderr\n'
REFS_BEFORE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/source-refs-before.txt; count 1619; SHA256 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5
REFS_AFTER: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/source-refs-after.txt; count 1619; SHA256 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5
REFS_DIFF: {"removed": [], "added": []}
SOURCE_STATUS_DIFF: {"removed": [], "added": []}
FORMAL_FABLE_CAPTURE: EVIDENCE_COMPLETE (actual installed loader/classifier), schema 1

NORMAL_SMOKE_EXIT: 0
NEGATIVE_SMOKE_EXIT: 23

四個 small smoke 均保留：兩個初步 *-r1，以及加入明確 candidate pins 介面後的兩個 *-final。最終驗收只引用與交付 launcher SHA 相同的 *-final。前兩次不是 pytest 執行，也沒有失敗後變更 ID 繞過保護。

## 共用狀態差異與歸因限制

REFS_BEFORE: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/preflight.json → before.source.refs (完整 manifest，1618 entries)
REFS_AFTER: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/acceptance.json → final_observations.source.refs (完整 manifest，1616 entries)
REFS_DIFF: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/acceptance.json → whole_task_shared_ref_diff
REFS_ATTRIBUTION_LIMIT: UNKNOWN — 不把觀察到的變化自動歸因於本任務、其他 Agent 或 harness；端點快照不能證明所有中間過渡或寫入者。

新增：
- `refs/codex/turn-diffs/checkpoints/baf96281349f4477eb5c29750b7e135d/9a10165611306fc5e20d13c7a98c5dd4/1792419032654/ecb71a47-5d86-4b1b-a593-b9a2b72d0919 865df393fe1ade7259de797940bc4b238275dde9`
- `refs/heads/b649/k20-hhl-full-family-proof-formalization-r1 fc7d61b48bfdcfe16e65d30a5f983fd04a31b705`

移除：
- `refs/codex/turn-diffs/captures/1792418150873/379118ef-11d5-4b20-9002-07abdb10e656/base eca8ede364d89acabbc0c45d3ff9dc7748f1091f`
- `refs/codex/turn-diffs/captures/1792418202935/bfd6c480-dee2-49e3-857e-41c097591509/base eca8ede364d89acabbc0c45d3ff9dc7748f1091f`
- `refs/codex/turn-diffs/checkpoints/27f8934b405cfe97a4a6c249f37e1d0d/522c5014a31f8263155852cacaedf9d4/1791813646574/5dc11fc9-25a3-4065-b9d8-6322a88cb372 51db6e86e5e30b04f9be7679ab8bfe5d2355a258`
- `refs/codex/turn-diffs/checkpoints/8c7f8d480888e10c397cbffafbf0a22b/fbcfeea6871625596016da55ddcc57e9/1791813756681/4520fd8d-2cf0-49a7-a515-93e1c9b4027b 51db6e86e5e30b04f9be7679ab8bfe5d2355a258`

Primary allowlist 外新增的 untracked status entries（僅記錄 status，沒有讀取／修改這些檔案；actor UNKNOWN）：
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1.json`
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1/baseline.json`
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1/launcher-stop.json`
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1/packet.txt`
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1/prepare_external.py`
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1/run_focused.py`
- `?? .fable/checkpoints/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1/worker-report.txt`

原有 status entries 未觀察到移除；primary HEAD/tree 未變。受保護 source HEAD/tree、clean status、HEAD 檔與 index bytes／mtime 均維持前置狀態。這些觀察不等於完整的 source-ref／harness write 歸因證明。原始 validation.json 的兩個 global equality checks 為 false，原樣保留；沒有覆寫成 PASS。acceptance.json revision 2 將 AC10 明確收緊為 NOT_VERIFIED。

## AC01–AC10

| AC | 結果 | 直接證據與觀察 |
|---|---|---|
| AC01 | PASS | Pinned source HEAD/tree and old Judge SHA match; protected source remains clean. [preflight.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/preflight.json) |
| AC02 | PASS | Fable before_spawn callback persists/fsyncs/reads launch receipt before popen3; each actual child independently read and hashed that receipt, with an earlier mtime. [launch_gate.rb](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb); [stdout.txt](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/stdout.txt); [stdout.txt](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/stdout.txt) |
| AC03 | PASS | Inherited umask 0077 measured in child; real app-data/runtime/basetemp 0700; 0600 child file; external temp/cache and disabled bytecode. [launch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/launch.json); [launch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/launch.json) |
| AC04 | PASS | Python 3.13.8, pytest 9.1.1, argv/cwd/process identity, lockfile and installed dependency fingerprints recorded. [launch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/launch.json); [launch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/launch.json); [dependencies.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/dependencies.json); [dependencies.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/dependencies.json) |
| AC05 | PASS | Complete source/primary refs and status before/after persisted; whole-task baseline/final also retained. [end.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/end.json); [end.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/end.json) |
| AC06 | PASS | Per-smoke refs have no observed drift; whole-task shared ref addition and primary out-of-scope additions explicitly retained, actor/cause UNKNOWN. No automatic attribution. [preflight.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/preflight.json); [validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/validation.json); [acceptance.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/acceptance.json) |
| AC07 | PASS | Actual launcher exit 0; exact original stdout and stderr match saved streams/capture. [final-smoke-dispatch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/final-smoke-dispatch.json); [capture.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/capture.json) |
| AC08 | PASS | Actual launcher exit 23; exact original stdout and negative-smoke-stderr are preserved. [final-smoke-dispatch.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/final-smoke-dispatch.json); [capture.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/capture.json) |
| AC09 | PASS | Launch, terminal and end receipts are directly persisted under the authorized root; hashes indexed. Final seal verifies readability/hash equality. [SHA256SUMS](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/SHA256SUMS); [SHA256SUMS](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/SHA256SUMS); [SHA256SUMS](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/SHA256SUMS) |
| AC10 | NOT_VERIFIED | No task product/ref-mutating Git/remote/solver/suite/other-worktree write action is observed; protected source HEAD/tree/status and HEAD/index bytes/mtime are preserved. Shared refs and out-of-scope primary outputs changed with UNKNOWN actor/cause, including refs under refs/codex. A complete source-ref/harness-write non-attribution proof is unavailable. Endpoint manifests alone cannot prove that this task/harness caused none of those changes. [launch_gate.rb](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb); [smoke_probe.py](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py); [preflight.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/preflight.json); [validation.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/validation.json); [acceptance.json](/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/acceptance.json) |

## 持久收據及 SHA256

RECEIPT_LOCATORS: 下表及完整 /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/SHA256SUMS
RECEIPT_SHA256: 下表；完整索引包含所有持久檔案，索引本身的 detached SHA256 由最終交付提供。

| Locator | SHA256 |
|---|---|
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/launch.json | bdec09e96beab9712614944976170b808d40e57eb67cafaad47603898214ce09 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/capture.json | 614d45361e0880199811c85bceba4ca5a99edfb11a380dbb0cfefedea25549f0 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/end.json | 4fef22d9fc0c4bcd1cf69e57492afe2d7ae0b92d03a6964e7fc771ddf26e2138 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/stdout.txt | 3f6fe8c94a7489334c83511989e9eec5983cdb762f145704aa0d379b0e4c2b9f |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/stderr.txt | 9012e47cf63119afcea7be3605fb17e5469711a5d9833121b73dacac2e91aed3 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/dependencies.json | 009e63d71b1918eaa07f7a0b51a0c68e8bfbce8e333bbdf649fecce6a03ee54b |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/source-refs-before.txt | 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/source-refs-after.txt | 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/normal-smoke-final/SHA256SUMS | 891079fcfd2785c04e80dca15a44476db5dc602a6dbaaab775154ae7ac9a9fce |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/launch.json | 86437e75cd1fbd2194dc0b5e3eb81a3e2f8b990f2d9afe039d67910e648505c4 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/capture.json | d92e1aef726d80c0ae7832b2e721373b86926ab81bacc3593deb86b0d15251b2 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/end.json | 13573db0882ecfc02a5207fc5ab11fa087da287bbd2d9ef0400317ae8ecc64c6 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/stdout.txt | f0c0c5a68a379441b7624d3b08ae129838a007e1ed784bddaae552bb73a322cb |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/stderr.txt | 853d339a55306a611eb1f132630e22b9e7fe88105c30f19dbb10b495f36335dd |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/dependencies.json | 009e63d71b1918eaa07f7a0b51a0c68e8bfbce8e333bbdf649fecce6a03ee54b |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/source-refs-before.txt | 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/source-refs-after.txt | 1116e760b362be801dc36614d9a90af43348ae67634ca5fcf0087510087efad5 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/runs/negative-smoke-final/SHA256SUMS | f5f1a595d7ea4a1cfd35f6596b5af5e707411962c5590f32d54bbbabe7eb1af6 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/preflight.json | 4cb12e2fb4fd21989afd68c45881fdb7e67988f9cfeaf0c034ed0294d59d910f |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/final-smoke-dispatch.json | 97a9c0f507d1e220a772688aea0e0e4802008a4eeee0ab4d0cfda7093965f9e4 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/validation.json | e78870d3c03d6de6ffc3cd551638e65dd2a371e2caabf3302954336ab436a75c |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/acceptance.json | bc1287719cb3f0c256bc02447b70ee628ff278ceaf4c81f1faa887fe4a44b873 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launch_gate.rb | e9d3e5e03fded1974fb16fcb177cfc96ccc817bf8e72d2084ff7407a4383be62 |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/smoke_probe.py | a478acf70154ab4edce1ae5159c951cc15d8f7cba212a4b5df328dbcbfd5206c |
| /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1/launcher-usage.md | f3590c96f52b3f1d2381a53d2ae914ecdc4e75a2c4d89240a5d73211fc522508 |

## 本任務寫入帳與處置

FILES_WRITTEN_DURING_TASK: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1 下的 launcher、smoke、preflight/dispatch/validation/acceptance、usage/report、四個 run 的 receipt/snapshot/stream/dependency/index，及全域 SHA256SUMS；全部以最終索引列出。
TASK_CREATED_FILES_RETAINED: 所有上述輸出；四個獨占 runtime root 的目錄與各自一個 controlled 0600 umask-probe.txt。
FILES_DELETED_BEFORE_END: 無 explicit delete／cleanup。既有 Fable capture helper 在各自 run_dir 中建立 capture.json.tmp.<PID>.<epoch> 再 rename 成 capture.json；未建立新的框架或 source metadata lock。
TOOLCHAIN_RUNTIME_OUTPUTS_CREATED:
- /private/tmp/gate-launch-20261019-12625-ft7sy0; observed regular files: /private/tmp/gate-launch-20261019-12625-ft7sy0/work/umask-probe.txt
- /private/tmp/gate-launch-20261019-12207-n9fetk; observed regular files: /private/tmp/gate-launch-20261019-12207-n9fetk/work/umask-probe.txt
- /private/tmp/gate-launch-20261019-12572-sn9d04; observed regular files: /private/tmp/gate-launch-20261019-12572-sn9d04/work/umask-probe.txt
- /private/tmp/gate-launch-20261019-12089-1prqad3; observed regular files: /private/tmp/gate-launch-20261019-12089-1prqad3/work/umask-probe.txt

PRE_EXISTING_FILES_RETAINED_UNCHANGED: 舊 Judge SHA 核對未變；受保護 source 與 HEAD/index 證據見 validation.json；Primary 既有 dirty/untracked 未被任務指令處理。沒有對不相關既有 untracked 內容做全面 hashing。
REPOSITORY_FILES_MODIFIED: 僅授權的 task output root；無產品 source/test/config edit。
GIT_WORKTREE_METADATA_WRITES: 本任務受控程式未呼叫 Git mutation；source HEAD/index bytes/mtime 未變。共用 refs 的實際 actor 未知。
HARNESS_GIT_METADATA_WRITES: NOT_VERIFIED; refs/codex 的差異被保留，名稱本身不證明 actor。
GIT_NETWORK_METADATA_WRITES: 無 network command 或 remote mutation 被執行。
WORKTREE_MATERIALIZATION_CREATED: NONE
WORKTREE_MATERIALIZATION_UPDATED: NONE
WORKTREE_MATERIALIZATION_REMOVED: NONE
UNAUTHORIZED_WRITE_EVENTS: No confirmed product/remote/other-worktree mutation by the controlled programs; observed shared-ref changes and out-of-scope primary additions have UNKNOWN attribution. No complete absence-of-event claim.

FULL_SUITE_RERUN: NO
PYTEST_COLLECTION_OR_SUITE_EXECUTIONS: 0
SOLVER_EXECUTIONS: 0
SOURCE_CHANGED: NO (protected product HEAD/tree/status; refs separately disclosed)
GIT_REFS_CHANGED_BY_TASK: NOT_VERIFIED
REMOTE_WRITE: NO observed; no remote/network action invoked
OLD_JUDGE_VERDICT: REFUTED
OLD_JUDGE_SHA256: 028e60ce4b0290a97c3b140b902157e4eb72eb2d1527f6297710c10a9dc22c68
FRESH_JUDGE_EXECUTIONS: 0 (not requested; dispatch suppressed)
TASK_COMMIT: NONE
COMMIT_LINK: NOT_APPLICABLE
TASK_TREE: UNCOMMITTED_TASK_ARTIFACTS_ONLY
FINAL_HEAD: e440d4298551ce93ef3ea9a9226143784afa3eff (protected source)
FINAL_TREE: 294cbf6bbe7ee8a8ebad947f397852edc1981b57 (protected source)
PR_PUBLICATION_STATUS: NOT_APPLICABLE
POSTMERGE_LIFECYCLE_STATUS: NOT_APPLICABLE
BRANCH_CLEANUP_STATUS: NOT_APPLICABLE
FULL_PR_LIFECYCLE_CLOSED: NO

BLOCKER_CODE: SHARED_REF_WRITE_ATTRIBUTION_UNKNOWN
BLOCKER_DETAIL: Whole-task refs changed: 2 added and 4 removed at final recorded observation. Actor/cause, including possible harness metadata writes, is UNKNOWN; AC10 cannot be verified from endpoint snapshots.
SMALLEST_NEXT_ACTION: Before a future formal Gate, use a newly authorized isolated execution environment with process/harness-origin write evidence in addition to these before/after manifests; do not reinterpret this attempt as fully verified.
REMAINING_TASK_MODEL: 強模型 — 新固定Tree的正式FULL Gate

未來正式 Gate 的 canonical --run／pytest 路徑：NOT_RUN。可直接採用的參數介面與前置條件在 launcher-usage.md；這份文件不新增 FULL Suite 授權，也不宣稱修復過去缺失的 launch-time 證據。
