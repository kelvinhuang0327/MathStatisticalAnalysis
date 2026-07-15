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
