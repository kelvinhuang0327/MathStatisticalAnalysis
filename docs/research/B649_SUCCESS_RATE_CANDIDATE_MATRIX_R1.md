# B649 全支線成功率提升候選矩陣 R1

`STATUS: ANALYSIS_COMPLETE` · `DATE: 2026-09-19` · `AUTHORITY: origin/main @947baf9d`

對「8 大方向 / 5 個優先候選」策略提案的**倉庫對帳 + 量化排序 + 一項修正**。

> **注意：這份 roadmap 今天稍早已被 triage 過一次**（14:01，寫成未提交的
> `docs/research/SUCCESS_RATE_RESEARCH_MASTER_MATRIX_V1.md`）。本文件不是重跑，
> 而是**接續**：確認已完成項目、補上遺漏的量化、並**修正一個會誤殺候選的錯誤上界**。

---

## 0. 先讀：組合幾何是變異數重分配，不是 edge

對任意 K 張**相異**票，期望中獎票數恆為 `K x p`、期望獎金恆為 `K x E[單票獎金]`，
與重疊結構**完全無關**（期望值線性）。重疊只改變分佈，不改變均值。

降低重疊會 **提高** `P(至少一注中獎)` / `P(max_hits>=3)` / `E[max matches]`（union、max 統計量），
**不改變** 期望獎金（sum 統計量），並**降低**同期多注同時中獎的機率。

這正好是 harness 宣告的 `PRIMARY_SUCCESS_METRIC = OFFICIAL_ANY_PRIZE`，
所以它**確實**提升宣告 KPI，但**不是**在打敗彩券。

---

## 1. 修正：倉庫現用的「幾何上界」不是上界

`diversification-coverage-b649-v1-result.json` 的欄位鍵是 **`q_sidon`**。
那張表的 "geometry delta" 是 `q_sidon - q_random`，是**單一建構家族（Sidon）的達成值**，
不是全域最佳。同系列報告自己也寫 `GLOBAL_OPTIMUM_STATUS: UNKNOWN`、`SIDON_BELOW_FRONTIER_MARGIN`。

**k <= 8 時真實最佳值有閉式解且精確**：k 張兩兩不相交的票放得進 49 個號碼中的 48 個；
三張不相交的票不可能各自命中 6 個開出主號中的 3 個（3+3+3 > 6），
故所有三階以上 inclusion-exclusion 項為零：

```text
P_opt(k) = k*p3 - C(k,2) * C(6,3)^2 / C(49,6)      p3 = 260624/13983816
```

| k | q_random | 表中 q_sidon | Sidon delta | **真實最佳** | 真實 delta | 低估倍數 |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0.054877 | 0.055038 | +0.000161 | 0.055827 | +0.000950 | **5.9x** |
| 5 | 0.089778 | 0.090292 | +0.000514 | **0.092902** (=54130/582659) | +0.003123 | **6.1x** |
| 8 | 0.139729 | – | – | 0.148299 | +0.008571 | – |

k > 8 無法全不相交；一個很樸素的 round-based 建構（每輪 8 張不相交，每輪換排列）
已量到 **k=10: 0.18015**（+0.00865，Sidon 的 **4.0x**）、**k=20: 0.32900**
（+0.01542，Sidon 的 **1.2x**）。這兩個是下界，k>8 的全域最佳仍未知。

### 1.1 這項修正的後果（重要）

memory 目前把那張表當成 fraud/noise 篩選器在用：
「K=5 宣稱 +1pp 比幾何能給的高兩個數量級，所以必定是 leakage 或 noise」。

**這個篩選器校準錯了約 6 倍。** M3+ 在 K=5 幾何可給到 +0.31pp，+1pp 只是約 3 倍，
不是兩個數量級；而在 **ANY_PRIZE** 口徑下空間更大（K=5 隨機 14.55% → 低重疊 15.30%），
**K=5 宣稱 +1pp 是落在幾何能力範圍內的，不可以被這道篩選器刷掉。**
已回寫修正至 `success-rate-ceiling-portfolio-geometry-envelope` memory。

---

## 2. 現行 operational selector 表現**低於隨機基準**

單票官方任一獎機率（精確）：`p = 432,824 / 13,983,816 = 3.0952%`
（`main>=3` 或 `main==2 且中特別號`，`domain/lottery_rules.py:387-394`）

| K | 實測 LIVE | 精確隨機基準 | 差距 (pp) | SE (pp) | z |
|---:|---:|---:|---:|---:|---:|
| 5 | 13.940% | 14.547% | −0.607 | 0.821 | −0.74 |
| 10 | 24.283% | 26.978% | −2.695 | 1.017 | **−2.65** |
| 20 | 39.966% | 46.678% | −6.712 | 1.161 | **−5.78** |

**K=20 時，現行選票器比「隨機挑 20 張相異票」還差 6.7pp。**

### 2.1 驗證：差距純粹來自重疊

逐票邊際命中分佈與精確超幾何**完全吻合**（主號命中 0..4 的 z 分別為
−1.96 / +0.06 / +3.00 / −0.56 / +0.09），代表開獎正常、票合法且逐票均勻。
逐票正常但 union 低 6.7pp ⇒ **票與票之間正相關（重疊）**。

反推平均兩兩重疊：LIVE ≈ **1.19** 個號碼/對，隨機 0.735，低重疊建構 0.495。
**現行組合的內部冗餘約為隨機的 1.6 倍**，行為上像是從約 30 個號碼的池子抽票。
成因直接：11-stream equal-weight consensus 先把號碼排名收斂到窄集合，K 張票再全部從中生出。

（注意：平均重疊只是粗略摘要。真正的冗餘曲線是**強凸**的 —— 正規化
`P(A_i ∩ A_j)/P(A)` 依重疊 0..6 為 0.0058 / 0.0308 / 0.0911 / 0.1864 / 0.3344 / 0.5790 / 1.0，
重疊 4 以下幾乎不造成冗餘。驅動 union 損失的是高重疊尾部，不是平均值。）

### 2.2 幾何在深層獎項**沒有作用**

| K | 指標 | LIVE | 隨機 | 低重疊 |
|---:|---|---:|---:|---:|
| 20 | P(any prize) | 39.97% | 46.68% | 49.73% |
| 20 | P(max hits ≥ 3) | 26.14% | 31.36% | 32.90% |
| 20 | **P(max hits ≥ 4)** | **1.967%** | **1.956%** | **1.965%** |

事件夠稀有時 union ≈ sum，重疊結構失效。**若目標是 4 星以上，本方向無效。**

---

## 3. 量化的 decision-leverage 篩選（閉式，不需重放）

harness 的 adequacy gate 是 `MIN_DISCORDANT_DRAWS = 10`，配對 n = 1,779。
最低 `ticket_set_changed_rate`：

| K | 換 1 張 | 換 2 張 | 換 3 張 | 換 5 張 | 換 10 張 | 換 20 張 |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 10.6% | 5.4% | 3.7% | 2.3% | – | – |
| 10 | 12.4% | 6.3% | 4.3% | 2.6% | 1.4% | – |
| 20 | 17.0% | 8.6% | 5.9% | 3.6% | 2.0% | 1.1% |

對照剛被否決的 `LOO_STABILITY_TIEBREAK_V1`：實際變動率 2.30% / 2.08% / 0%
（K=5/10/20），分別低於門檻 4.6x / 6.0x / 結構上不可能。
**這個候選在動工前就數學上不可能產生結論。** 此篩選應成為強制前置關卡。

**另一個重點：K=5 不適合當主戰場。** 即使真有 +1.36pp 效果，n=1,779 下
McNemar z ≈ 1.14。K=20 (z≈5.83) 與 K=10 (z≈3.10) 才有力量。

---

## 4. 倉庫對帳

| # | 方向 | 現況 | 位置 |
|---|---|---|---|
| 1 | Portfolio coverage optimization | **元件齊全、未接線到生產選票器** | `research/bounded_coverage_optimizer{,_fast}.py`、`expected_max_main_matches.py`、`low_overlap_portfolio_constructor.py`、`greedy_min_overlap_constructor.py` |
| 2 | DPP selector | **已合併**（PR#311, `947baf9d`）；**三臂 adapter 亦已建好**（`a329bb2e` local-only，未推送） | `research/k_dpp_ticket_portfolio.py`；`B649_KDPP_CAUSAL_SOURCE_AND_CONTROL_ADAPTER_R1` |
| 3 | Dynamic stream weighting | 未實作；與**凍結合約**衝突 | `domain/b649_canonical_consensus.py`：`STREAM_WEIGHT_POLICY = EQUAL_STREAM_WEIGHT`（CTO 核准 2026-09-10） |
| 4 | Meta-feature interactions | **已實作**（R2，含預註冊 + pinned R1 hash）；R1 已測 8 特徵在時序切分下全 MIXED | `research/historical_replay_meta_feature_interaction_discovery.py` |
| 5 | Uncertainty-aware ranking | tie-break 層已做且**已否決**；score 層未做 | `research/b649_rank_stability.py`、`b649_loo_stability_tiebreak.py`（未推送） |
| 6 | Regime gating | 元件 + 完整預註冊/報告/結果已有；**CUSUM regime Holm-min p = 1.0（已測 null）** | `research/regime_changepoint_cusum.py` |
| 7 | External causal metadata | **無**資料源（draw automation provider gap） | – |
| 8 | Anti-false-uplift | **已實作並運作中**；**未推送** | `research/b649_loo_oos_validation.py`（worktree @`fcd9015`） |

**Learning-to-rank 在倉庫中完全不存在**，且專案無任何 ML 依賴
（deps 僅 fastapi / pydantic / typer / uvicorn，research extra 僅 ortools）。
`legacy_xgboost_native_portfolios_wave64.py` 是**凍結的 legacy 重放**，不是可訓練 ranker。

**訊號側已關閉**：uniformity Holm min p=0.24、EH01-EH10 NO_SIGNAL、
EH02 transfer entropy Holm p=1.0、CUSUM regime Holm-min p=1.0、
conditional co-occurrence 27/27 cells 低於隨機、8 features 全 MIXED、LOO INSUFFICIENT_POWER。
方向 2/4/6 屬於**已測 null**，不是開放問題。

---

## 5. 候選矩陣（理論潛力 × 實作成本 × OOS 可驗證性）

| 排名 | 候選 | 理論潛力 | 實作成本 | OOS 可驗證性 | 支線 |
|---:|---|---|---|---|---|
| **1** | **降低組合冗餘 / 低重疊 portfolio** | **已實測** K10 +4.67pp (+19%)、K20 +9.77pp (+24%)（vs LIVE，ANY_PRIZE） | **已建好**（三臂 adapter `a329bb2e`） | **決定性**：預期 discordant 717 / 890；z ≈ 3.10 / 5.83 | **2（freeze + 跑）** |
| 2 | 加入**確定性** min-overlap 第四臂 | k-DPP 是 sampler 不是 maximizer，取不到 argmax | 低（constructor 已存在） | 同上 | 6 → 2 |
| 3 | 凸校準 kernel（7 個常數） | 修正線性 kernel 在重疊 1 高估冗餘 5.4x | 低 | 中 | 6 |
| 4 | Uncertainty-penalized consensus **score**（非 tie-break） | 未知 | 低–中 | 需先過第 3 節篩選 | 1 → 2 |
| 5 | Dynamic stream reliability weighting | 低（訊號側已關閉）；但 leverage 高 | 中 + **需修改凍結合約** | 高 | 1 |
| 6 | Learning-to-rank (LightGBM) | 低：公平抽獎下無可學標的；能學到的主要是幾何，而 #1 更便宜 | **高**（新依賴 + pyright strict） | 中 | 3（延後） |
| 7 | Regime gating / interactions | **已測 null** | 已完成 | – | 關閉 |
| 8 | External causal pre-draw metadata | **最高理論上限**，唯一有 causal plausibility | 未知；**目前無資料源** | 先做可行性 | 3 |

---

## 6. 下一步（具體）

1. **支線 2：`BRANCH2_KDPP_THREE_ARM_OOS_EXPERIMENT_FREEZE_R1`** —— 這是 memory 已登記的
   NEXT_TASK，三臂 adapter 已在 `a329bb2e`。這是目前投報率最高的一步。
2. **先把 `b649_loo_oos_validation.py` 推上去** —— 唯一的 OOS harness 只存在於一個未推送的
   worktree，是單點故障。
3. **把第 3 節的 leverage 篩選做成強制前置關卡**（閉式計算）。
4. **加第四臂：確定性 min-overlap constructor**。k-DPP 依 `det(L_S)` **抽樣**，
   不是取最大值；本案目標是 fixed-K 的 argmax，確定性建構器應該更強。
5. **重新校準 memory 中的 fraud/noise 篩選器**（已回寫）。

### 一個可證偽的事前預測

三臂實驗中的 `B649_SEEDED_RANDOM_K_CONTROL` 應該會**贏過** `RAW_MAJORITY`：
ANY_PRIZE 約 **+2.7pp @K10**、**+6.7pp @K20**。
若隨機控制組沒有贏，則本文件第 2 節的分析或該實驗的實作其中之一有問題。
這是一個便宜且強力的 validity check，建議明確寫進 freeze。

---

## 7. 可重現性與限制

計算腳本（本 session 產生，未納入倉庫）：`headroom.py`、`geometry2.py`、`geometry3.py`
（150 組合 × 400,000 期 common random draws）、`power.py`、`diagnose.py`、`ceiling.py`。

**MC 校驗**：隨機建構的 MC 與精確基準差 +0.011 / +0.002 / +0.006 pp（K=5/10/20）；
K=5 不相交建構的 MC = 0.09295 vs 精確 0.09290168（差 4.8e-5）。評分器正確。

**限制**：

- LIVE 是實際歷史開獎的配對重放，幾何基準是對均勻隨機開獎的 MC —— 屬**間接比較**。
  正式確認就是第 6 節第 1 步。
- LIVE 組合有時間序列相關性，其 SE 被低估；K=20 的 z=−5.78 需 design effect > 8 才失去顯著性，
  K=10 的 z=−2.65 較脆弱。
- 第 2.1 節的重疊反推是池寬掃描內插，是近似值。直接量測現行組合的兩兩重疊分佈
  （不只平均）是便宜且應做的確認。
- k > 8 的幾何全域最佳仍未知；本文件給的是下界。
