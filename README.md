# QuantLab

數理統計分析平台。第一個 domain 是 **lottery**（自 `~/Kelvin-WorkSpace/LotteryNew` 逐步移植），架構預留多 domain 擴充（stock、betting-pool …）。

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
uv run uvicorn --factory quantlab.interfaces.api.app:create_app --reload   # API :8000
cd frontend && npm install && npm run dev                                  # 前端
```

## 目錄地圖

| 路徑 | 職責 |
|---|---|
| `src/quantlab/domain/` | 純業務模型（Draw、StrategyDescriptor、lifecycle）；不依賴任何其他層 |
| `src/quantlab/strategies/` | StrategyCatalog（metadata 唯一來源）與 ExecutableRegistry（只載入 ONLINE adapter） |
| `src/quantlab/application/` | Use cases、ports、DTO |
| `src/quantlab/interfaces/` | FastAPI routes 與 CLI（薄殼，無業務邏輯） |
| `src/quantlab/infrastructure/` | persistence／snapshot／scheduler，實作 application ports |
| `frontend/` | Vue 3 + TypeScript + Vite |
| `contracts/` | OpenAPI 匯出與前端型別生成鏈 |
| `docs/` | canonical 文件：架構、ADR、capability catalog、migration ledger |
| `tests/` | unit ／ contract ／ architecture（依賴方向強制）／ characterization（parity） |
| `data/` | 快照 payload（不進 git）；`data/manifests/` 的 hash manifest 進 git |
| `tools/` | 維運腳本（快照驗證等） |

依賴方向由 [tests/architecture/test_dependency_rules.py](tests/architecture/test_dependency_rules.py) 強制，違反＝CI 紅燈。

## 專案名

`QuantLab` 為建議名（備選：MathStat、NumberLab）。改名＝改 `pyproject.toml` 的 `name`、`src/quantlab/` 目錄名與 import 前綴；骨架階段一次 `grep -rl quantlab | xargs sed` 可完成。
