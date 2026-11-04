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
- pytest 一律關掉快取；`--basetemp` 一律用 `mktemp -d "${TMPDIR%/}/msa-pytest.XXXXXX"` 建立的目錄，並把路徑記在 result.json：
  `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -m pytest -p no:cacheprovider --basetemp=<mktemp 建立的目錄> tests/<path>`
- 這是暫時例外（Owner 2026-11-04 同意）：有 3 個測試假設暫存目錄在所有 Git 倉庫之外，放進專案內會失敗。
  這 3 個測試修好之前，pytest 暫存留在系統暫存區；這個目錄只放 pytest 暫存，不算任務資料夾外的寫入。
- `--basetemp` 必須是專用的子目錄：pytest 每次執行前都會刪掉它。
  不要指向任務資料夾，也不要指向任何放了收據或資料的目錄。

## 專案資料位置

- 任務產生的資料一律放在主 checkout `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/` 底下，不在專案外新建資料。
- 任務資料夾（PERSISTENT_EVIDENCE_ROOT）：`/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/<YYYYMMDD>/<TASK_ID>/`。
  - 任務在 git worktree 執行時，也寫到主 checkout 的這個絕對路徑，不寫進 worktree 自己的 `.task-data`：worktree 刪除時會一起消失。
  - Packet 寫明的任務資料夾在專案外時，照 Packet 執行，並在回報中註明一行「任務資料夾在專案外」。
- 任務建立的資料庫與其他資料檔（收據以外）：`/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/_scratch/<名稱>/`。
  - 名稱不含 `B649`（不分大小寫），路徑中也不要有名為 `LotteryNew` 的目錄；產品程式只放行這個子樹。
  - 正式資料庫在 `data/`，不要寫進 `_scratch`。
- 主 checkout 不得執行 `git clean -x` 或 `git clean -X`：會刪掉被 git 忽略的 `.task-data/` 與 `data/`。

## 回測結果寫入

- 回測結果的正式寫入目標只有一個：`data/databases/database-locations.json` 的 `writable_databases` 裡登記給 `LOTTOLAB_REPLAY_BACKFILL_DB` 的檔案。寫入前先讀這個檔確認；Packet 寫的目標和登記不同時，停下回報。
- 還沒有登記可寫目標時（2026-11-04 現況：`writable_databases` 是空的），新結果只寫到 `.task-data/_scratch/<名稱>/` 底下的暫存 DB，收據寫明 `MERGE_PENDING` 和 DB 的絕對路徑，等資料庫整合 Planner 合併。
- 以下位置不得當成最終寫入目標：任務資料夾裡的 DB、`data/replay/reference/`、`data/databases/legacy/`（keeper）、`data/databases/backups/`、尚未完成的封存，以及未登記的 `data/replay/active/`。
- 不重跑已有結果。開跑前，用 cell 的唯一鍵（`lottery_type`、`strategy_id`、`strategy_version`、`execution_version`、`dataset_identity`、`target_draw_id`）查正式 DB 與待合併的暫存 DB：已完成的跳過，只算缺的。收據寫出「已存在跳過 N、新算 M」。
- 待合併的暫存結果用匯入合併，不重新計算。
- 同一個 DB 同時只能有一個寫入者。寫入前後記錄列數，寫入後從 App 或 API 的讀取路徑讀回。

## JSON 輸出

- 要比較或雜湊會寫成 JSON 的資料時，先做一次 `json.loads(json.dumps(x))` 往返再比較：
  dict 的整數鍵會變成字串、tuple 會變成 list、排序可能改變。

## 多段回報（Codex `/goal` 自動續跑）

- 同一任務在同一對話有多次結尾回報時（`/goal` 自動續跑、Owner 續行或重試），
  最後一次回報必須是完整版：依 Packet 的「Worker 必要回覆」逐欄寫出累計結果，
  整合前面每一輪的結論、證據位置與未完成項；不能只寫本輪的變化或「狀態未變」。
- 每次結尾回報前，把回報全文覆寫到 `<PERSISTENT_EVIDENCE_ROOT>/final_reply.md`，供 Owner 原樣複製給 Planner：
  第一行 `貼回：<Packet 的 TARGET_CONVERSATION>`（沒有就寫 SOURCE_CONVERSATION），接著 TASK_ID 與
  task_lifecycle_state，再寫白話結論（做了什麼、結果、有沒有問題或要 Owner 決定的事）與上一項的累計完整版。
  回報最後兩行依序是 `任務資料夾：<PERSISTENT_EVIDENCE_ROOT 絕對路徑>` 與
  `pbcopy < <final_reply.md 絕對路徑>`。這個檔屬於任務收據，Packet 的 ALLOWED_WRITES 沒列也可以寫；
  不寫入密碼、金鑰、token 或個人資料；Owner 指定只回覆對話、或 Packet 沒有任務資料夾時不建立。
- 之後在對話中貼出的完整回報，一律放在單一程式碼區塊中，讓 Owner 可以原樣複製。
  有 `final_reply.md` 時，區塊內全文必須與該檔內容逐字一致；`final_reply.md` 本身不含外層程式碼區塊標記。
- 程式碼區塊裡的路徑點不開。區塊之後（區塊外）再寫兩行 Markdown 連結，目標用絕對路徑，Codex 桌面版會變成可點的連結：
  「總結檔：[final_reply.md](<final_reply.md 絕對路徑>)」與「任務資料夾：[<TASK_ID>](<PERSISTENT_EVIDENCE_ROOT 絕對路徑>)」。
  連結外面不要加反引號，連結裡也不要有反引號，不要用 `file://`。
- 同一對話中的後續工作（包括採用 Codex 建議的下一步）：屬於某個已有 TASK_ID 的，照上面的續行規則寫進那個任務的資料夾與
  final_reply.md；不屬於任何任務的（例如彙整表、狀態矩陣），產出檔案放在本對話主任務的資料夾，並在主任務的 final_reply.md
  新增「後續追加」一節，每輪列出 Owner 的原句、結果與產出檔案路徑；最後回報仍是累計完整版。
- 需要 Owner 回覆或授權才能繼續時，在同一則回報寫出完整內容與 Owner 要回覆的原句；
  自動續跑的回合只做唯讀複核，不重做任何寫入。

## 長時間指令

- `exec_command` 回傳 `session_id` 表示程序還在執行；要等它結束、讀到結束碼，
  才讀取結果或寫入紀錄。

## Shell

- 指令包裝器不要對 zsh 的 `status`、`path` 賦值（兩者是保留變數）；結束碼請存成 `rc`。
- 只讀 Git 狀態時用 `git --no-optional-locks -c core.fsmonitor=false status`（或設 `GIT_OPTIONAL_LOCKS=0`），
  避免改寫 index 或在 worktree 啟動 fsmonitor 常駐程序。

## 資料庫備份與還原

- 已退役研究 DB 的 keeper 在 `data/databases/legacy/`，對照表是 `data/databases/legacy/INDEX.json`（舊絕對路徑 → keeper_path）。
- 這些 keeper 在 Owner 的 Google Drive 另有一份雲端備份，批次名稱是 `MSADBBK-<YYYYMMDD>`，可透過 rclone remote `msa-gdrive:` 存取。
- 遇到以下情況，照 `data/databases/CLOUD_BACKUP_RESTORE.md` 的步驟處理：keeper 不見或損毀、測試找不到 `legacy/` 底下的 DB、需要從雲端還原。
  - 步驟依序為：下載到暫存資料夾 → 用 CATALOG 核對 sha256 → 用 `04 RESTORE` 還原到 `data/databases`。
  - 還原不覆寫既有檔。
- rclone 的登入由 Owner 執行。
  - agent 不得讀取或印出 `~/.config/rclone/rclone.conf`。
  - 雲端只能用 `rclone copy` 或 `copyto`，不得刪除或覆蓋雲端上的舊批次。
