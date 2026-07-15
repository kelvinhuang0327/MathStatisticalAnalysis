# ADR-0004：專案定名 LottoLab，範圍為樂透專用

狀態：ACCEPTED ｜ 2026-07-15 ｜ 決策者：owner（Kelvin）

## Context

骨架初建時暫以 QuantLab（多 domain 平台定位）建檔，備選 MathStat、NumberLab。Owner 隨後定案：本 repo 為**樂透系統專用**，名字應反映此範圍。

## Decision

1. 專案名 **LottoLab**，Python package `lottolab`，CLI 命令 `lottolab`。
2. 範圍限定樂透（DAILY_539、BIG_LOTTO、POWER_LOTTO）；未來其他 domain（stock、betting-pool）另立專案，不共用本 repo。
3. 因範圍專用，`domain/lottery/` 攤平為 `domain/`（`lottolab.domain.draws`、`lottolab.domain.strategies`）。

## Consequences

- 外層目錄 `MathStatisticalAnalysis` 為 workspace 資料夾名，與專案名脫鉤；owner 可自行 `mv` 改名，不影響 repo 內容。
- 所有 import 前綴、pyproject、契約（openapi title）、文件已同步更名；`uv.lock` 與 `contracts/openapi.json` 重生。
