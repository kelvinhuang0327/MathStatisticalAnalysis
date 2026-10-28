# MathStatisticalAnalysis 專案規則

## Python 直譯器

- 所有 Python 指令（執行腳本、pytest、`python -m …`）一律使用
  `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python`（Python 3.13）。
  例如：`/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -m pytest tests/<path>`
- 不要使用系統的 `python3` 或 `python`：它是 Python 3.9，低於本專案要求的 3.13，
  會出現 `datetime.UTC`、`int.bit_count` 之類的錯誤。
- 在 git worktree 中執行時，這個 `.venv` 預設載入的是主 checkout 的 `src/`；
  請加上 `PYTHONPATH=<worktree>/src`，並確認 `lottolab.__file__` 位於該 worktree 內。

## Codex `/goal`

- 用 `/goal` 開始的任務，goal 已經建立好了。先呼叫 `get_goal` 讀取目前的 goal，
  不要再呼叫 `create_goal`，因為已有未完成的 goal 時它一定會失敗。
- 之後回報進度或完成狀態，只用 `update_goal`。

## 工具快取與暫存

- ruff 一律加 `--no-cache`，不要在 repo 留下 `.ruff_cache`：
  `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/ruff check --no-cache <paths>`
  （`ruff format` 也一樣加 `--no-cache`）。
- pytest 一律關掉快取，並把暫存目錄放在任務資料夾：
  `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -m pytest -p no:cacheprovider --basetemp=<PERSISTENT_EVIDENCE_ROOT>/pytest-tmp tests/<path>`
- `--basetemp` 必須是專用的子目錄：pytest 每次執行前都會刪掉它。
  不要指向任務資料夾本身，也不要指向任何放了收據的目錄。
- 例外：路徑含 `B649`（不分大小寫）或含 `LotteryNew` 這一層目錄時，專案的重播來源保護
  與 Fable 的 `validate-test-scratch` 都會拒絕。這時改用
  `mktemp -d "${TMPDIR%/}/msa-pytest.XXXXXX"` 建立的目錄，並把路徑記在 result.json；
  這個目錄只放 pytest 暫存，不算任務資料夾外的寫入。
- Packet 沒有任務資料夾時，同樣用上面的 `mktemp -d` 目錄。

## JSON 輸出

- 要比較或雜湊會寫成 JSON 的資料時，先做一次 `json.loads(json.dumps(x))` 往返再比較：
  dict 的整數鍵會變成字串、tuple 會變成 list、排序可能改變。

## 多段回報（Codex `/goal` 自動續跑）

- 同一任務在同一對話有多次結尾回報時（`/goal` 自動續跑、Owner 續行或重試），
  最後一次回報必須是完整版：依 Packet 的「Worker 必要回覆」逐欄寫出累計結果，
  整合前面每一輪的結論、證據位置與未完成項；不能只寫本輪的變化或「狀態未變」。
- 需要 Owner 回覆或授權才能繼續時，在同一則回報寫出完整內容與 Owner 要回覆的原句；
  自動續跑的回合只做唯讀複核，不重做任何寫入。

## 長時間指令

- `exec_command` 回傳 `session_id` 表示程序還在執行；要等它結束、讀到結束碼，
  才讀取結果或寫入紀錄。

## Shell

- 指令包裝器不要對 zsh 的 `status`、`path` 賦值（兩者是保留變數）；結束碼請存成 `rc`。
