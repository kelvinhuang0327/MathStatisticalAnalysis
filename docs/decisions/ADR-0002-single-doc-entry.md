# ADR-0002：文件單一入口

狀態：ACCEPTED ｜ 2026-07-15

## Context

舊系統文件散落多處（root md、docs/、wiki/、00-Plan/、.ai per-worktree、handoff），且 wiki 索引與內容已 drift（宣告 13 頁、實存 2 頁）。多入口是散落的根源。

## Decision

1. 新系統的 canonical 文件入口是 **`docs/README.md`** 的路由表；任何新文件必須掛進路由，否則視為散落。
2. LotteryNew 的 `wiki/README.md` 仍是**舊系統**知識入口；兩邊不重複內容，跨系統引用走連結。
3. 歷史需求軌跡（00-Plan 快照、docs 舊報告、outputs/research、rejected/）**原地保留、不改寫、不搬遷**，由 capability catalog 的 `provenance` 欄位反向索引。
4. 文件被取代標 `SUPERSEDED` 連到新位置；不直接刪除。

## Consequences

- 不存在第三個入口；「在哪裡找」永遠只有一個答案。
- 批次 2 需交付 wiki 完整性稽核（宣告 vs 實存）作為舊系統側的收斂輸入。
