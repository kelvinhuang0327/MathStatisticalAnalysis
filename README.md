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

Controller 使用使用者專屬的系統暫存目錄保存 owner-only lock、state 與 log；不讀取 DB、
不依賴 LotteryNew、不接受替代 port，也不會終止 foreign port owner。
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

## 本機 Draw Data（P600D R1B）

前端以 hash navigation 提供三個頁面：`Strategy Overview`、`Data Center`、`Draw History`。
Data Center 只接受 LottoLab canonical CSV；瀏覽器把檔案讀成 UTF-8 文字並以 JSON 傳送，
不使用 multipart，也不把 CSV 放進 localStorage、sessionStorage 或 IndexedDB。

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
- Draw History 的 draw-number filter 是 substring search；結果固定依 draw date descending、
  draw number stable-string descending、internal ID descending 排序並分頁，且沒有編輯／刪除功能。

本機 DB 永遠在 Git worktree 外。可用絕對、owner-only 的目錄覆寫預設位置：

```bash
LOTTOLAB_DATA_DIR=/absolute/owner-only/path uv run --no-sync lottolab local start
```

未存在 DB 的 history read 會回傳 deterministic empty result，不建立目錄、DB 或 migration；第一個
有效 commit 才能建立 version-1 schema。使用者 DB、SQLite sidecar、upload 與 runtime artifacts
都不進 Git。測試與 task lifecycle 一律把 `LOTTOLAB_DATA_DIR` 指向 repo 外的新建暫存目錄，並在
驗證後只移除該 task 自己建立的路徑。

LottoLab 是本機、非機密的研究應用。固定 path、owner、權限、symlink、hardlink、special-file、
repository 與 LotteryNew 邊界檢查仍會強制執行；但已用相同 OS 使用者身分執行、可競速或直接修改
owner-owned 檔案的惡意 process 不在支援的 threat model 內，實作不宣稱具備 same-UID
namespace-race immunity。若需更強隔離，必須採用 OS sandboxing 或 privilege separation，超出目前範圍。

R1B 不提供 fetch-latest、missing-period scan、backfill、scheduler 或自動 ingestion；這些不是
隱藏或 disabled controls，而是明確不在目前功能面。

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

依賴方向由 [tests/architecture/test_dependency_rules.py](tests/architecture/test_dependency_rules.py) 強制，違反＝CI 紅燈。

## 專案名

**LottoLab**（owner 2026-07-15 定案，樂透專用；見 [ADR-0004](docs/decisions/ADR-0004-project-name-and-scope.md)）。
