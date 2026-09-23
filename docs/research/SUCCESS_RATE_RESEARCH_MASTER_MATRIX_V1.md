# 成功率提升研究總矩陣 v1

狀態：草案（未 commit）｜ 2026-09-19 ｜ 對照來源：repo 既有 sealed 報告 + memory 既有結論

本文件的用途是把「成功率搜尋系統」提案，對照本 repo **已經量測過的實際結果**重新排序。
結論先講：提案的 A–F 分類是對的，但**優先順序大致相反**。

---

## 0. 決定性事實（這改變所有排序）

BIG_LOTTO 的開獎資料**與公平 6/49 無法區分**。這不是先驗假設，是量測結果。

| 檢定 | 來源 | 結果 |
|---|---|---|
| 8 項均勻性 battery（球頻、特別號、8 era 同質、carryover vs 超幾何、順序統計、和數、per-number Holm/49、pair Holm/1176） | 2026-08-12 uniformity audit | Holm min p = **0.2435**（PERIOD_LIKE, n=2138）／**0.3056**（Tue/Fri, n=2025） |
| EH01–EH10 ordinal temporal | `eh01-eh10-b649-ordinal-temporal-v1-report.md` | **NO_SIGNAL**（兩個假設皆是） |
| EH02 cross-lottery transfer entropy | `eh02-b649-cross-lottery-transfer-entropy-v1-report.md` | **NO_SIGNAL**，Holm p = **1.0**（兩條 edge） |
| Regime changepoint CUSUM | `regime-changepoint-cusum-b649-v1-report.md` | Holm-min p = **1.0** |
| 條件共現 family attribution | memory, 2026-09-04 | 9 candidates **NO_SUPPORT**，27/27 cells 低於隨機 |
| L2 pairwise null / z2 / Bayes / changepoint | BMSGV1, 2026-08-25 | 任何 horizon 皆 **no edge** |
| 8 個 candidate features 滾動驗證 | 2026-08-19 | 全部 8 個 temporal_direction = **MIXED** |
| LOO stability tie-break OOS | 2026-09-19 | **INSUFFICIENT_POWER**；K20 從不改變票組 |

**推論：** 提案中的 B（訊號搜尋）、C（ensemble 加權）、E（隨機性稽核）對 BIG_LOTTO 而言
**不是「未知但必要」，是已經量過且為 null**。E 尤其不該排 P1 — 它已經做完了，而且它的結果
正是砍掉 B 和 C 的那把刀。

推論的第二層，也是 uniformity audit 自己寫下的結論：
> 唯一剩下的槓桿是 `E[payout | win]`，不是 `P(win)`。

---

## 1. 唯一在數學上站得住的槓桿

⚠️ **本節於 2026-09-19 更正。** 初版把 `diversification-coverage-b649` 的 `delta`
（+4.24% @k=20）當成「幾何天花板」。那是錯的：該 delta 是 **Phase-1 Sidon 構造 vs random**，
不是上限。`diversification-constructor-frontier-b649-v1` 的 bounded search 已經找到明顯更好的解，
而且所有 constructor 報告都是 `GLOBAL_OPTIMUM_STATUS: UNKNOWN` — 真正的上限仍然未知。

提案 A 是對的，而且理由比提案講的更強：**票組幾何的優勢不需要任何訊號**。
在完全公平的抽獎下，單張票是可交換的（每張 P(win) 相同），但 K 張票的
`P(至少一張中獎)` 取決於重疊結構。這是純組合數學，不可能 overfit，不需要 OOS。

### M3+ 精確覆蓋（exact，分母 C(49,6)=13,983,816）

| k | Q_random | Q_sidon (Phase1) | **best-found (bounded)** | best vs random |
|---:|---:|---:|---:|---:|
| 1 | 0.01863755 | 0.01863755 | 0.01863755 | **+0.00%** |
| 3 | 0.05487704 | 0.05503762 | 0.05582682 | +1.73% |
| 5 | 0.08977829 | 0.09029231 | 0.09290168 | +3.48% |
| 10 | 0.17149647 | 0.17364180 | 0.18218232 | +6.23% |
| 15 | 0.24587816 | 0.25178807 | 0.26529203 | +7.90% |
| 20 | 0.31358200 | 0.32687687 | **0.34244823** | **+9.21%** |

來源：`diversification-constructor-frontier-b649-v1-result.json`
（`best_found_q_primary_event`，exact rationals，k=20 = `4788733/13983816`）。
其 optimizer：candidate_sample_size=60、5 restarts、3 swap passes、56,730 evaluations。

**`FRONTIER_CAPTURE_RATIO`（16.9%→46.1%）也被我初版讀錯了。** 它是
`(Q_sidon − Q_random)/(Q_best − Q_random)` — 即 Sidon 構造佔 best-found 優勢的比例，
**不是**「我們距離理論上限還差多少」。

### 修正後的讀法

1. **k=1 的 delta 仍然精確為 0**（`sanity_check_delta_at_k1_is_exactly_zero = True`）。
   單注不存在幾何優勢，任何單注策略 M3+ 不可能超過 1.8638%。這條結論不變。
2. **優勢隨 k 遞增**，且比初版所說大約**大一倍**：k=20 是 +9.21%（不是 +4.24%），
   k=5 是 +0.31pp（不是 +0.05pp）。
3. **上限未知且高於 +9.21%** — 所以 P0c 的投資理由比初版更強，不是更弱。
4. 造假偵測門檻要相應放寬：k=5 的已證明幾何收益是 +0.31pp，而非 +0.05pp。

## 2. 提案 P0/P1 五項 vs 實際狀態

| 提案項目 | 提案優先度 | 實際狀態 | 處置 |
|---|---|---|---|
| 1. Same-K portfolio optimization | P0 | **部分完成**。b649/t539/p638 皆有 sealed diversification-coverage；constructor 只捕獲 16.9–46.1% | **保留為唯一 P0**，但改為「關閉 capture gap」，不是重開題 |
| 2. LOO / stability tie-break OOS | P0 | **已完成 2026-09-19**：INSUFFICIENT_POWER，1,779 paired draws，K20 從不改變票組，補足 adequacy gate 需再 ~10⁴ draws | **關閉。不要重開。** |
| 3. Online expert weighting (Hedge / Fixed-Share) | P0 | **前提不成立**。Hedge 的 regret bound 只在 experts 間存在可利用的效能差時有價值；EH01-10 + CUSUM + 8-feature rolling 三路都顯示 regime 與 expert 差異不可辨識 | **降到 P3**，且須先通過下方 G1 gate |
| 4. Weighted covering | P1 | **已證明退化**。`EXPECTED_HIT_UTILITY_CONTRACT_FREEZE_R1`：uniform weighting 下 `E[count] = k·p1(n,d,m)`，與選哪些票、如何重疊完全無關（對稱性直接證明）。`EXPECTED_ANY_THRESHOLD_HIT` 則與現有 coverage objective **逐字相同** | **關閉**。權重要非退化就得用 historical weighting，而 historical weighting 正是 null |
| 5. Diversity-aware ensemble | P1 | 未做，但同 #3 前提問題 | P3，同 G1 gate |
| E. Randomness / machine bias audit | P1(中) | **BIG_LOTTO 已做完且為 null**；DAILY_539 / POWER_LOTTO **從未做過** | **拆開**：B649 關閉；539/Power 升為 **P1**（見下） |
| F. Payout / unpopularity exploitation | P2(低) | `domain/unpopularity_candidate_selection.py` **已存在**（生日penalty、高號reward、連號penalty），但只有 unit + architecture 測試，**零 production 呼叫端** | **升為 P2**，見下 |

---

## 3. 重排後的實際執行順序

### P0 — 唯一真正的工程項目

**G0. 關閉 constructor capture gap** — ✅ **已執行 2026-09-19，三個 K 全部突破 sealed best**

| k | random | sealed best | **本次** | delta | 寬鬆上界 | vs random | 已吃掉的可證明餘裕 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.171496 | 0.182182 | **0.182223** | +0.00004083 | 0.186118 | +6.25% | 1.04% |
| 15 | 0.245878 | 0.265292 | **0.265951** | +0.00065905 | 0.279163 | +8.16% | 4.75% |
| 20 | 0.313582 | 0.342448 | **0.343429** | +0.00098092 | 0.372207 | **+9.52%** | 3.30% |

精確值：K10 `364025/1997688`、K15 `3719011/13983816`、K20 `2401225/6991908`。
這些解的精確 ANY_PRIZE：0.29325336 / 0.41555535 / 0.51938195。整體性檢查全 PASS，三者都用滿 49/49 號。

**本專案第一個上界。** 所有 sealed 報告都只有 `GLOBAL_OPTIMUM_STATUS: UNKNOWN`。
每張票 qualify |Q_t| = 260,624 個 draw，而兩張**互斥**的票仍強制共用 C(6,3)²=400 個
（D 必須 3+3 分），重疊的票只會更多，故 `|∪Q| ≤ k·260624 − (k−1)·400`。
**有效但寬鬆**（只計一個前驅的重疊）。K=20 最佳解落在 [0.343429, 0.372207]，即 +9.52%～+18.70%。

**「gap 來自 search 還是 formulation？」→ 部分是 search，但已進入嚴重遞減。**
更細的 move set（單號突變）確實找到 sealed 整票替換搜尋漏掉的改善，三個 K 都有；
但幅度只有可證明餘裕的 1–5%，K=10 用 3 倍 probe 只換到 1.04%。這個槓桿在此 formulation 下接近耗盡。

**ILP / CP-SAT 的現實：** 這台機器**沒有 scipy 也沒有 CP-SAT**，且直接 ILP 需要 13,983,816 條約束。
那是採購＋重新建模的專案，不是換 solver；而依上界，它在 K=20 的最大可能報酬也被 +8.4pp 相對封頂。

### P1 — 便宜且資訊量最高

**G1. DAILY_539 / POWER_LOTTO 均勻性稽核** — ✅ **已完成 2026-09-19，結果 NULL**

| Lottery | n | 期間 | Battery Holm min p | 判定 |
|---|---:|---|---:|---|
| DAILY_539 (5/39) | 5,913 | 2007-01-01..2026-07-13 | **0.5562** | NO_DETECTABLE_DEPARTURE |
| POWER_LOTTO (6/38+1/8) | 1,928 | 2008-01-24..2026-07-13 | **0.3369** | NO_DETECTABLE_DEPARTURE |

- 完整報告：`.task-data/T539_P638_UNIFORMITY_AUDIT_R1/report.md`
- 資料來源：sealed legacy corpus，sha256 `e8a56e9f…`（與 memory 記錄逐字相符，read-only，byte-unchanged）
- Integrity gate 全過：0 structural violations、0 duplicates、0 DATE_LIKE、無合成分帶指紋
- **Power：539 可偵測 10.9% 相對偏差、Power 16.9%** — 對照 BIG_LOTTO audit 的 ~19%，
  **539 的 null 比當初關閉 BIG_LOTTO 的那個更強**
- **Mutation check 通過**：植入 +2%(539) / +5%(Power) 偏差後 battery 確實 reject
  （Holm p = 5.05e-03 / 3.90e-06），所以 null 不是 vacuous suite

**→ Gate 判定：三個彩種全部 null。P3 關閉。**

**G2. ANY_PRIZE 口徑補正** — ✅ **已完成 2026-09-19，結論分兩半**

報告：`.task-data/B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1/report.md`

**(a) 報告口徑確實錯了，要修。** 精確值：

| 量 | exact | float |
|---|---|---:|
| P(main>=3) — 目前 objective | `4654/249711` | 0.01863755 |
| P(main==2 & special) — 柒獎，**被忽略** | — | 0.01231424 |
| **真 ANY_PRIZE（單注）** | `7729/249711` | **0.03095178** |
| 柒獎佔全部中獎 | — | **39.79%** |

三個精確交叉驗證全中：`4654/249711` 與 sealed `q_random/3/1/exact` 逐字相同；
`1-(1-p)^k` 重現 Branch6 的 6.09/14.55/26.98%。
**所以 Branch6 用對的 ANY_PRIZE 評策略，constructor 卻用 M3+ 最佳化 — 這個不一致才是真缺陷。**

**(b) 但 optimizer 不用改，也不該重做。** K=20、60 個 portfolio、全部精確評分：

| 指標 | 值 |
|---|---:|
| Spearman ρ | **0.997666** |
| Pearson r | 0.999130 |
| 擬合關係 | `ANY ≈ 1.6642 × M3+ − 0.0553` |
| 最大殘差 | 0.002362（平均 ANY 的 0.48%） |
| argmax 是否一致 | **是（全 60 / top20 / top10 皆是）** |
| 用 M3+ 選最佳所損失的 ANY | **+0.000000** |

**「把錯的目標函數最佳化到極致」這個疑慮，量測後不成立** — 兩個目標幾乎同序。
sealed constructor 工作**不失效**，P0c 不需要換目標函數。

**可直接用，但範圍要講清楚：** `ANY ≈ 1.6642 × M3+ − 0.0553` 是**只在 K=20 擬合**的，
**不能跨 K 使用** — 用 P0c 的解實測：K=20 誤差 0.61%、K=15 6.80%、K=10 **15.45%**。
其他 K 直接算精確 ANY_PRIZE（一次呼叫就好）。

**唯一要加的步驟：** top-20 內 discordance 升到 6.84%，所以**決賽名單要用精確 ANY_PRIZE 重排**
— 這是最後一道便宜的重排，不是新的搜尋目標。

### P2 — 唯一未被 null 結果封死的價值來源

**G3. E[payout | win] — pari-mutuel 分獎**
- uniformity audit 自己指名這是唯一剩下的槓桿
- `unpopularity_candidate_selection.py` 已實作，零 production 呼叫端 → **接線成本低**
- **已知阻擋**：`BigLottoPrizeTier` 根本沒有 `prize_amount` 欄位；
  `PowerLottoPrizeTier.prize_amount` 在 FIRST/SECOND 為 `None`；
  `research_ticket_results` 只有 `prize_tier_id`；`lottery_v2.db draws.jackpot_amount` 為空且零列
- 所以真正的 P2 第一步是**資料取得**（per-draw per-tier 中獎人數），不是演算法
- 唯一 4 個 tier 都有固定金額的是 DAILY_539 → 可作為先導

### P3 — ❌ 已關閉（G1 於 2026-09-19 在 539/Power 皆回傳 null）

Hedge / AdaHedge / Fixed-Share / multiplicative weights、regime-conditioned ensemble、
diversity-aware expert selection、Fourier / wavelet / HMM / GBM / NN / transformer。

**Gate 條件已執行且未通過。** BIG_LOTTO、DAILY_539、POWER_LOTTO 三者的均勻性 battery 全部 null，
且三者的 null 都通過 power 與 mutation 驗證。重開任一項需要**新的獨立證據**推翻 uniform baseline，
不是「換一個更複雜的模型再試一次」。

---

## 4. 我同意提案的部分（原文保留為規範）

**baseline 三件組 B0/B1/B2 是對的，而且已是本專案的既有規定** — 見
[[b649-hit-depth-must-show-ticket-count-baseline]]：8/8 抽樣策略的 M2+ 都低於
其票數匹配的隨機 baseline（最差 -43.76pp），而裸 % 讓它們看起來很強。
每個命中率**必須**配 ticket-count-matched baseline + delta。

**選模偏差是最大風險 — 這點提案完全正確。** 補充一個本 repo 實測到、提案沒提的坑：
滾動決策點高度自相關（相鄰 T/T+1 在 WINDOW_750 共用最多 749/750 draws），
名目上數千個決策點的有效獨立樣本數遠低於此。任何顯著性檢定必須 block bootstrap
over non-overlapping blocks。

**「極端顯著性是資料完整性警報，不是發現」** — 污染版資料曾產生 sum mean z=−7.4、
positional p=8.6e-157。把這條寫進漏斗的 leakage check。

---

## 5. 對「PORTFOLIO + SELECTION + SIGNAL」排序的修正

提案的排序方向正確，但應改為：

```
PORTFOLIO   — 真實、精確、有界。天花板 +4.24% 相對 @k=20，+0.00% @k=1
SELECTION   — 只剩防偽功能（避免把雜訊當成功），不是收益來源
SIGNAL      — BIG_LOTTO / DAILY_539 / POWER_LOTTO 三者皆測定為 null（G1 完成 2026-09-19）
PAYOUT      — 唯一未被封死的價值來源，但被缺資料擋住（= G3）
```

最誠實的一句話：**本專案在 BIG_LOTTO 上已經接近它的數學上限。**
剩下的工作是 (a) 把 1.3pp 信封裡沒拿到的部分拿完，(b) 去 539/Power 問同一個問題，
(c) 解決分獎資料。其餘都是在對 null 做更貴的重測。
