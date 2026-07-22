# 文件入口（canonical）

> 本頁是新系統文件的**唯一入口**（ADR-0002）。每個主題只有一份 canonical 文件；歷史軌跡留在 LotteryNew 原地，由 capability catalog 的 `provenance` 欄位反查。

## 路由

| 主題 | 位置 | 狀態 |
|---|---|---|
| 系統架構與依賴規則 | [architecture/system.md](architecture/system.md) | CURRENT |
| 架構決策紀錄（ADR） | [decisions/](decisions/) | CURRENT |
| 功能盤點（capability catalog） | [capabilities/catalog.yaml](capabilities/catalog.yaml) | P600A VERIFIED |
| 舊系統入口機器清單 | [capabilities/legacy-entrypoints.yaml](capabilities/legacy-entrypoints.yaml) | P600A PINNED |
| LotteryNew 基線稽核 | [audits/lotterynew-baseline.md](audits/lotterynew-baseline.md) | P600A VERIFIED |
| LotteryNew wiki 完整性 | [audits/lotterynew-wiki-integrity.md](audits/lotterynew-wiki-integrity.md) | P600A VERIFIED |
| Phase-S snapshot 停止紀錄 | [audits/p600ab-phase-s-snapshot-stop.md](audits/p600ab-phase-s-snapshot-stop.md) | STOPPED · NOT CANONICAL EVIDENCE |
| 外部 agent 相依 | [integrations/external-agent-dependencies.yaml](integrations/external-agent-dependencies.yaml) | P600A METADATA ONLY |
| 遷移計畫 P600 | [migration/p600-plan.md](migration/p600-plan.md) | CURRENT |
| 遷移帳本（哪些 capability 已遷/退役） | [migration/migration-ledger.yaml](migration/migration-ledger.yaml) | P600A INVENTORIED · P600B MIGRATING |
| API 契約 | [../contracts/](../contracts/) | CURRENT |
| AI agent context（repo-local Worker context、安全邊界、runbook） | [../.ai/ai-context/PROJECT_PROFILE.md](../.ai/ai-context/PROJECT_PROFILE.md) | CURRENT |

## 治理規則

1. 新增文件必須掛進本頁路由表，否則視為散落。
2. 文件被取代時標 `SUPERSEDED` 並連到新位置，不直接刪除。
3. LotteryNew 在 pinned commit 沒有 canonical `wiki/README.md`；舊知識入口以
   [wiki 完整性稽核](audits/lotterynew-wiki-integrity.md)記錄的實際路徑為準。兩邊**不重複內容**，跨系統引用一律走連結。
