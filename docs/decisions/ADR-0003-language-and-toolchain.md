# ADR-0003：語言與工具鏈

狀態：ACCEPTED ｜ 2026-07-15

## Decision

| 層 | 選型 | 理由 |
|---|---|---|
| 後端語言 | **Python 3.13（鎖版）** + uv（lockfile） | 統計生態不可替代；舊系統全部策略資產為 Python；單機系統無吞吐瓶頸，換語言零收益 |
| Web 框架 | FastAPI + pydantic v2 | OpenAPI 自動生成 → 前端型別的契約來源 |
| 前端 | **TypeScript + Vite + Vue 3** | 取代舊系統 6k 行單檔 vanilla JS；型別由 OpenAPI 生成 |
| 儲存 | SQLite，repository 層強制單一 canonical path | 舊系統多份 .db 散落是 drift 的結構性根源 |
| 品質 | ruff + pyright(strict) + pytest 分層 | 新 code 一律過三關 |
| ML 依賴 | **不入核心**（tensorflow／autogluon／prophet 等留在未來 research extras） | 現役策略只需 numpy/pandas/scipy 級依賴 |
| 效能熱點 | 先 numpy／polars 向量化；profiling 證明後才考慮 Rust/PyO3 | 不預先跨語言 |

## 可重現性條款（硬約束）

直譯器或數值依賴升級＝**獨立的 gated PR**，必須同時重生並重 pin 所有 golden digests。
教訓來源：LotteryNew 曾因 Python 3.12 改用 Neumaier summation 導致既有 digest 全數失效。

## Consequences

- `.python-version`＝3.13；`uv.lock` 進 git；CI 用 `uv sync --frozen`。
- 任何「順手升級依賴」的 PR 一律拒收。
