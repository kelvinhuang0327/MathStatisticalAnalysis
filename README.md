# LottoLab

樂透統計分析系統——LotteryNew 的次世代重建，功能自 `~/Kelvin-WorkSpace/LotteryNew` 逐 capability 移植。本 repo 為**樂透專用**（ADR-0004）。

## 軌道紀律（不可違反）

1. 舊系統 LotteryNew 是**凍結中的參照實作**，本 repo 對它一律唯讀——一行都不寫。
2. 遷移採絞殺者模式：逐 capability 移植 → parity 驗證 → 舊端退役；細節見 [docs/migration/p600-plan.md](docs/migration/p600-plan.md)。
3. 文件唯一入口：[docs/README.md](docs/README.md)。

## 快速開始

```bash
uv sync                        # 安裝依賴（Python 版本鎖定見 .python-version）
uv run pytest                  # unit / contract / architecture 測試
uv run ruff check .            # lint
uv run pyright                 # 型別檢查（strict）
uv run uvicorn --factory lottolab.interfaces.api.app:create_app --reload   # API :8000
cd frontend && npm install && npm run dev                                  # 前端
```

## 本機 Runtime Controller

先以已提交的 lockfile 準備環境（controller 本身絕不安裝或更新依賴）：

```bash
uv sync --frozen
cd frontend && npm ci && cd ..
```

之後一律以 no-sync 模式管理固定的 loopback 服務：

```bash
uv run --no-sync lottolab local start    # API 127.0.0.1:8000 + Vite 127.0.0.1:5173
uv run --no-sync lottolab local status   # 驗證 state、PID identity、process group 與 listener
uv run --no-sync lottolab local smoke    # health、前端、直連/代理 Strategy Catalog
uv run --no-sync lottolab local stop     # 僅停止 controller 擁有的 process group
```

Controller 使用使用者專屬的系統暫存目錄保存 owner-only lock、state 與 log；controller 本身不讀取 DB、
不依賴 LotteryNew、不接受替代 port，也不會終止 foreign port owner。後端可依下方明確設定，在 HTTP
request 發生時唯讀開啟一個既有 Historical Results DB。
它目前面向 POSIX/macOS，Windows 尚不支援；固定使用 8000 與 5173 port 是刻意的安全限制。
成功停止後會移除 active state，但 task-owned 診斷 log 會保留在 repo 外、owner-only 的 runtime
目錄。Controller 只使用已存在的 locked Python／frontend 環境，絕不自行 bootstrap 依賴。

## Strategy Overview（P600F R1）

`#/strategies` 透過 DB-free 的 `GET /api/v1/strategy-overview` 查詢既有 Strategy Catalog。
可選參數為 `q`、`lottery_type`、`lifecycle_status` 與 `executable`；所有條件採 AND，結果固定保留
descriptor declaration order。`q` 會先 trim，再以 Unicode casefold 後對 strategy ID 與 display name
做 substring match；空白 query、超過 100 字元或未知 query property 會被 API validation 拒絕。

每筆結果只含 descriptor metadata 與 provenance。Summary 計算目前回傳集合的 total、execution、
lifecycle 與 lottery-type counts；支援多彩種的 descriptor 會分別計入每個 lottery type。
目前 LottoLab 沒有已註冊的 canonical strategy evaluation evidence，因此 evaluation metrics、D3 status
與 best-strategy ranking 皆明確回傳 unavailable，reason code 為
`NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE`。Lifecycle 或 executable metadata 不是品質分數；此頁不提供
score、rank、D3 值、hit rate、prediction、replay 或 execution control，也不解析 data path 或建立 DB。

## Historical Success Windows 本機研究工作區

`#/historical-success-windows` 是 persisted Historical Results 的唯讀研究工作區。若要啟用，必須以
`LOTTOLAB_HISTORICAL_RESULTS_DB` 指定一個**既有、絕對路徑**的 Historical Results SQLite DB：

```bash
LOTTOLAB_HISTORICAL_RESULTS_DB=/absolute/owner-only/historical-results.db \
  uv run --no-sync lottolab local start
```

- 此設定可省略；省略或空字串時 local runtime、health 與其他 API 仍可啟動，Historical Results 與
  Historical Success Windows API 會回傳 sanitized `NOT_CONFIGURED` 503，前端顯示設定提示。
- 沒有 default path、default filename、directory scan、latest/newest discovery，也不會 fallback 到
  `LOTTOLAB_DATA_DIR`。設定值不 trim、不猜測，且兩個 API factory 永遠使用同一個 exact path。
- DB 只在 request 發生時以 SQLite `mode=ro` 與 `query_only` 開啟；local app construction、OpenAPI
  generation 與 frontend build 都不觸碰 DB，也不做 schema initialization 或 migration。
- 相對路徑、NUL、任何大小寫形式的 `LotteryNew` path component、missing/corrupt/unreadable DB 或 schema
  mismatch 都 fail closed 為 sanitized `UNAVAILABLE` 503；HTTP response 不揭露 path、SQL 或 raw exception。
- 頁面只列 persisted completed runs；使用者必須明確選擇 exact import SHA、prefix 與 criterion，再按
  Analyze。頁面不自動選 first/latest run，也不將 Historical Results 解讀為 ranking、promotion、veto
  threshold 或 prediction。
- Success rate 以 exact integer fraction 顯示，四個 window 固定為 FULL_HISTORY / REFERENCE_ONLY、
  LONG / PRIMARY_EVIDENCE / 750、MEDIUM / STABILITY_CONFIRMATION / 300、SHORT / DEGRADATION_VETO / 50；
  alias、replicate 與 zero-observation identity 都保留。

## Historical Results 明確匯入

本機 operator 可將一個已符合 LottoLab `HistoricalResultImportV1` target envelope 的 JSON 檔案，
明確匯入指定的 Historical Results SQLite DB：

```bash
uv run --no-sync lottolab import-historical-results \
  --input /absolute/operator-owned/historical-result-import.json \
  --database /absolute/operator-owned/historical-results.db
```

- `--input` 與 `--database` 都是必填；database 必須是絕對路徑，且兩者都沒有環境變數、
  default/latest/fallback 或目錄掃描行為。
- input 必須是 worktree 外的既有 regular file，不能是 symlink 或 `LotteryNew` path；CLI 只接受
  已有 target envelope，不轉換 legacy DB row、legacy JSON 或 research artifact。
- CLI 會在建立 SQLite repository 前完成既有
  `verify_and_normalize_historical_import` 驗證，再將完整 normalized import 原樣交給既有
  `ImportHistoricalResults` 與 `SQLiteHistoricalResultRepository`。
- closed validation/commit outcome 以 compact、sorted-key JSON 寫到 stdout；caller/input/runtime error
  以 sanitized 訊息寫到 stderr。成功為 exit 0，validation、persistence 或 caller error 為 exit 1，
  缺少 required option 則沿用 Typer 的 usage error。
- 重複匯入相同 import identity 會回傳既有 completed run，並以
  `"is_idempotent_replay":true` 明確標示；此命令不建立 scheduler、自動 ingestion、production
  deployment 或 legacy conversion。

## 非多票 Web 工作區（LotteryNew → LottoLab R1）

前端以 hash navigation 提供 `Strategy Overview`、`Historical Success Windows`、`Data Center`、
`History`、`Strategy Evidence` 與既有 `Live Zone Split Bets`。本節只描述非多票資料、歷史與
證據可用性；多票 replay／backtest／portfolio／ranking／combination／ticket matrix 一律不在此
遷移範圍。逐項 legacy 對照與未完成條件見
[non-multiticket web parity matrix](docs/migration/lotterynew-lottolab-non-multiticket-web-parity-r1.md)。

### Data Center

`#/data-center` 只接受 LottoLab canonical CSV。檔案選擇器支援多檔；瀏覽器把每個檔案讀成
UTF-8 文字後，以獨立 preview request 取得後端權威 digest、parser version、valid／invalid／
duplicate／conflict 統計。使用者可明確 commit 全部有效檔或勾選的有效檔；每檔是獨立 transaction
與 ingestion run，不宣稱跨檔 atomicity。批次狀態固定為 `NOT_COMMITTED`、`SUCCESS`、`FAILED`
或 `PARTIAL_SUCCESS`。取消、切換檔案與 unmount 都會中止 request 並使舊 response 失效。

瀏覽器不使用 multipart，也不把 CSV 放進 localStorage、sessionStorage 或 IndexedDB；成功 commit
或取消後會丟棄該頁 session 的 raw text。

Canonical 欄位如下；`special_numbers` 與 `source` 可省略欄位，但目前 BIG_LOTTO 規則要求
恰好一個特別號，因此有效資料列仍須提供 `special_numbers`。號碼欄以 `|` 分隔：

```csv
lottery_type,draw_number,draw_date,main_numbers,special_numbers,source
BIG_LOTTO,000001,2026-07-16,1|3|9|17|24|49,7,synthetic-reference
```

- `preview` 只做後端權威解析、SHA-256 與 bounded preview；不解析 data path、不建立目錄／DB，
  也不寫 ingestion log。
- `commit` 必須帶回相同內容、preview digest、目前 parser version 與唯一支援的 conflict policy
  `REJECT`，後端會重新解析。Validation、digest、parser-version、input duplicate 與 input conflict
  失敗都保持 DB-free，且不會建立 ingestion run。
- 有效 commit 以單一 transaction 寫入 draws、ingestion items 與 SUCCESS run。語意完全相同的
  draw 會記為 `SKIPPED_DUPLICATE`。
- 已通過驗證的 persisted-draw conflict（同 key 不同內容）會先 rollback draw transaction、永不覆寫
  既有 draw，再以獨立 transaction commit FAILED ingestion audit。此行為同時適用於既有 DB，
  以及 fresh-path 在 schema 初始化後發生的 concurrent first-write conflict。
- BIG_LOTTO import contract 固定為 6 個不重複主號（1–49）、1 個必要且不與主號重疊的特別號
  （1–49），canonical storage order 為數字遞增；draw number 是保留前導零的 ASCII digit string。
- `DrawDataProvider` 是 application port；預設沒有 provider，automation endpoint 會回傳 sanitized
  `AUTOMATION_NOT_CONFIGURED`。Local runtime 只有在 `LOTTOLAB_DRAW_PROVIDER_URL` 明確設定為不含
  credential 的 absolute HTTPS URL 時，才建立 lazy JSON adapter；app construction、OpenAPI 與
  frontend build 不會連網。
- `MANUAL_SYNC`、`MISSING_DRAW_SCAN`、`BOUNDED_BACKFILL` 與 `SCHEDULED_SYNC` 共用最長 366 天、
  canonical backend validation、no-overwrite 與 append-only audit。接受的 bounded invocation 即使
  not configured、transport unavailable 或 provider contract invalid，也會留下 sanitized FAILED run。
  `SCHEDULED_SYNC` 是可供外部 scheduler 呼叫的明確 trigger，不會在 web process 啟動 background job。
- 目前 adapter boundary 不代表官方資料源已驗證，也不構成 production scheduler、traffic cutover
  或 LotteryNew retirement 證據。

本機 DB 永遠在 Git worktree 外。可用絕對、owner-only 的目錄覆寫預設位置：

```bash
LOTTOLAB_DATA_DIR=/absolute/owner-only/path uv run --no-sync lottolab local start
```

未存在 DB 的 history read 會回傳 deterministic empty result，不建立目錄、DB 或 migration；第一個
明確 write 才能建立 version-2 schema。既有 version-1 DB 的 read 仍以 SQLite `mode=ro` 與
`query_only` 驗證且不升級；下一個明確 write 才 transactionally 加入 version-2 ingestion context。
使用者 DB、SQLite sidecar、upload 與 runtime artifacts
都不進 Git。測試與 task lifecycle 一律把 `LOTTOLAB_DATA_DIR` 指向 repo 外的新建暫存目錄，並在
驗證後只移除該 task 自己建立的路徑。

LottoLab 是本機、非機密的研究應用。固定 path、owner、權限、symlink、hardlink、special-file、
repository 與 LotteryNew 邊界檢查仍會強制執行；但已用相同 OS 使用者身分執行、可競速或直接修改
owner-owned 檔案的惡意 process 不在支援的 threat model 內，實作不宣稱具備 same-UID
namespace-race immunity。若需更強隔離，必須採用 OS sandboxing 或 privilege separation，超出目前範圍。

### History

`#/history` 統一三個唯讀分頁：

- Draw History：draw-number substring filter；結果依 draw date descending、draw number
  stable-string descending、internal ID descending 排序並分頁。
- Ingestion History：依 status、trigger、provider／filename 與日期查詢 run，並顯示 bounded
  item／duplicate／conflict／failure detail；partial detail 會明確標示。
- Historical Import Runs：只讀取已存在 Historical Results DB 的 completed import metadata、
  identity、source、counts、time 與 idempotent-import flag；未設定時顯示 `NOT_CONFIGURED`。

此 workspace 沒有 edit、delete、clear、prediction、strategy execution、replay 或 ranking control；
read routes 不會 initialize schema、migration 或 fallback 到其他 DB。

### Strategy Evidence

`#/strategy-evidence` 以完整 `strategy_id`／`strategy_version`／`replicate` identity 顯示 Catalog
metadata 與 canonical evidence availability。Catalog 沒有 replicate 維度時固定顯示
`NOT_APPLICABLE`。Registration／definition／verification 只來自 committed evidence registry 與
metric definition，不從 lifecycle、adapter、歷史結果或 catalog order 推導。

目前 registry 沒有 canonical strategy evaluation evidence，因此 Best Strategy 固定為
`UNAVAILABLE / NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE`。D3 definition 固定為
`RESERVED_UNAVAILABLE`，value 顯示 `NOT_AVAILABLE`，絕不以 0 代替。Strategy Combination Hit Rate
固定顯示 `EXCLUDED_ACTIVE_MULTITICKET_SCOPE`，不讀取或模擬 active multi-ticket agent 的產物。

## 目錄地圖

| 路徑 | 職責 |
|---|---|
| `src/lottolab/domain/` | 純業務模型（Draw、StrategyDescriptor、lifecycle）；不依賴任何其他層 |
| `src/lottolab/strategies/` | StrategyCatalog（metadata 唯一來源）與 ExecutableRegistry（只載入 ONLINE adapter） |
| `src/lottolab/application/` | Use cases、ports、DTO |
| `src/lottolab/interfaces/` | FastAPI routes 與 CLI（薄殼，無業務邏輯） |
| `src/lottolab/infrastructure/` | persistence／snapshot／scheduler，實作 application ports |
| `frontend/` | Vue 3 + TypeScript + Vite |
| `contracts/` | OpenAPI 匯出與前端型別生成鏈 |
| `docs/` | canonical 文件：架構、ADR、capability catalog、migration ledger |
| `tests/` | unit ／ contract ／ architecture（依賴方向強制）／ characterization（parity） |
| `data/` | 快照 payload（不進 git）；`data/manifests/` 的 hash manifest 進 git |
| `tools/` | 維運腳本（快照驗證等） |
| `prompt/control-plane-v1/` | 跨專案 Shared Control Plane（目前為 `DRAFT_FOR_OWNER_REVIEW`） |

依賴方向由 [tests/architecture/test_dependency_rules.py](tests/architecture/test_dependency_rules.py) 強制，違反＝CI 紅燈。

## 專案名

**LottoLab**（owner 2026-07-15 定案，樂透專用；見 [ADR-0004](docs/decisions/ADR-0004-project-name-and-scope.md)）。
