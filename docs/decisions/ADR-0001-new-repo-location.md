# ADR-0001：新系統落點為獨立 repo

狀態：ACCEPTED ｜ 2026-07-15 ｜ 決策者：owner（Kelvin）

## Context

P600 重建評估原建議「同 repo（LotteryNew）新頂層套件」以利 parity 測試與資料共置。Owner 決定新系統落在獨立位置 `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis`，同時 LotteryNew 主線（P541 系列 PR 收尾）由其他 session 並行進行。

## Decision

新系統為獨立 repo。原「同 repo」方案的優勢改由以下三條紀律補回：

1. **LotteryNew 一律唯讀**——該 repo 已有三次 live-writer collision 事故；新系統軌道永不寫入。
2. **跨 repo parity harness**——舊系統匯出 hash-pinned golden／snapshot 檔，新系統測試只讀匯出物，不 import 舊程式（舊 repo 有已知 import 副作用）。
3. **Pinned-commit 盤點**——capability inventory 掃描時記錄 LotteryNew 的 commit hash；主線收尾後做一次 refresh diff。

## Consequences

- 資料流入必經 `tools/import_snapshot.py` 的 manifest 驗證。
- 舊 repo 的 wiki／00-Plan／evidence 不搬遷，由 capability `provenance` 反查。
- 未來若需 GitHub remote，另行建立（本 ADR 不涵蓋）。
