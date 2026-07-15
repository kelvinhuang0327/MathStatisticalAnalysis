# P600 遷移計畫（落地版）

狀態：CURRENT ｜ 2026-07-15 ｜ 完整推導見 LotteryNew 對話紀錄與 owner 記憶檔

目標：以本 repo（LottoLab）為新系統，將 LotteryNew 的功能逐 capability 移植，最終舊核心退役。**不是大爆炸重寫。**

## 軌道紀律

1. LotteryNew 一律唯讀（該 repo 已有三次 live-writer collision 前科）。
2. 遷移 PR 不夾帶演算法／預測語意變更；semantics 變更＝獨立任務 + goldens 重生。
3. 每個 PR 只遷移一個 capability，並更新 migration-ledger。
4. 直譯器／數值依賴升級是獨立 gated PR（ADR-0003 可重現性條款）。

## 批次（先行步驟）

| 批次 | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| 1 | 本 repo bootstrap：uv+Py3.13、分層骨架、catalog/registry、三類測試、docs/ADR、Vue3 前端骨架、CI | 無 | **DONE 2026-07-15** |
| 2 | P600A 盤點：唯讀掃 LotteryNew（pin commit）→ 填 capability catalog + provenance；wiki 完整性稽核；ai-system 跨 repo 依賴登記；launchd/CLI/hook 背景入口掃描 | 無（與主線收尾並行） | **DONE 2026-07-15（pin `520c3922…`）** |
| 3 | 資料快照：canonical DB 唯讀匯出 + SHA-256 manifest；開獎歷史轉 parquet/CSV | 主線一個安靜點 | **P600AB R1 IN PROGRESS** |

## 後續階段（需主線收尾後）

| 階段 | 內容 |
|---|---|
| P600C | taskctl 最小版（preflight / verify / report；不做自動 merge/cleanup） |
| P600D | read-only capabilities 批次遷移（查詢、evidence read model、replay 呈現） |
| P600E | 執行核心（generation、replay、evaluation、ONLINE adapters）；golden digest 把關 |
| P600F | 高副作用區（DB write、ingest、scheduler、部署） |
| P600G | Legacy 退役：依 ledger 退場條件移除舊路徑 |

## 驗收指標

- 新增 OBSERVATION 策略不改任何中央清單與既有測試。
- 每策略一份 descriptor；exact-count 測試為零（真契約除外）。
- 前端只經 contracts 取數；golden 在鎖定版本下可重現。
- 每條 compatibility／KEEP_LEGACY 都有退場條件。
- LotteryNew 所有入口 100% 映射或明確標 UNKNOWN。
