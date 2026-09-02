# B649_TRACK_D_STATIC_CONSENSUS_FAILURE_MODE_AND_FEATURE_OPPORTUNITY_MINING_R1

TASK_CLASS: READ_ONLY_RESEARCH
MODE: READ_ONLY_DISCOVERY_ANALYSIS
GOVERNANCE: MINIMUM
DATE: 2026-08-14

COHORT_V2_PROSPECTIVE_DATA_USED: NO
B_EH04_INTERIM_DATA_USED: NO (the EH04 task directory was never opened)
REPO_MUTATION: NONE
DB_MUTATION: NONE

---

## 0. WHAT WAS ACTUALLY READ, AND HOW IT WAS VERIFIED

No artifact stores the STATIC_CONSENSUS full 1..49 score vector — `score_ticket()`
builds `scores=[0.0]*50` in memory and returns only the top-6 tuple. The vector was
therefore **rebuilt from the pinned emission artifacts**, not re-predicted.

Inputs (all read-only):

| Input | Detail |
|---|---|
| `.task-data/B649_STRATEGY_K_HISTORICAL_MATRIX_AUTHORITY_R1/ordered_candidates/` | 6,600 held-out emission files, **every one SHA-256 verified** against `manifest.json` |
| same, full grid | 1,417 targets x 22 eligible streams = 31,174 emissions loaded |
| `.task-data/B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2/draw_index.csv` | 3,149 draw rows (outcomes) |
| `.task-data/B649_TRACK_B_COMPLEMENTARITY_AWARE_.../heldout_predictions.csv` | used only as the reproduction oracle |

Reconstructed rule (from `reproduce_analysis.py:229-246`): equal weight `1/22`,
`rank_linear` `(6-r+1)/6`, `candidate_k=6`, top-6 by `sorted((-score, number))`.

**REPRODUCTION GATE: 0 / 300 mismatches** against the stored canonical
`static_consensus_ticket` column.

> One methodological note worth keeping: the first reconstruction produced 20/300
> mismatches caused purely by float associativity — `W*(7-r)/6` vs the original
> `W*((6-r+1)/6)`. Because ~24% of targets have an **exact score tie at the
> rank-6/rank-7 boundary**, sub-ULP differences flip real ticket slots. Any future
> re-implementation of this aggregator must preserve the exact expression.

---

## 1. CURRENT_BASELINE

| Arm | M2+ | Rate |
|---|---|---|
| STATIC_CONSENSUS (held-out 300) | 67/300 | **22.33%** |
| Random 6/49, analytic | — | 15.10% |
| `exact_random` arm (same 300) | 31/300 | 10.33% |
| Uniform-draw null, 4,000 reps | mean 45.3, p97.5 = 58 | 15.09% |

Held-out M1+ 180, M2+ 67, M3+ 8, M4+ 1, mean hits 0.8533.

**Reproduced exactly. But the baseline does not survive contact with a larger sample.**

STATIC_CONSENSUS has **no fitted parameters** and the 22 eligible streams were selected
by *data completeness*, not performance. The rule is therefore legitimately evaluable on
the 1,117 search-period targets, which no prior task did:

| Period | n | M2+ | Rate | Uniform-null mean | p |
|---|---|---|---|---|---|
| HELD-OUT 300 | 300 | 67 | **22.33%** | 45.3 | **0.0010** |
| SEARCH 1117 | 1117 | 164 | **14.68%** | 168.8 | **0.6675** |
| ALL 1417 | 1417 | 231 | 16.30% | 214.0 | 0.1155 |

On 1,117 independent targets the identical rule performs **below random and is
indistinguishable from chance**. Two-proportion test between periods: z = +3.19.

Splitting chronologically rather than by the protocol boundary shows the structure is a
**step change at calendar year 2023**, which straddles the search/held-out split:

| Era | n | M2+ | Rate | Shuffle-null (real draws, same block) | p |
|---|---|---|---|---|---|
| PRE-2023 (2014-2022) | 996 | 137 | **13.76%** | mean 154.0 | 0.947 |
| POST-2023 (2023-2026) | 421 | 94 | **22.33%** | mean 67.3 | **0.0003** |

Per year z vs random: 2014 +0.45, 2015 +0.14, 2016 -1.26, 2017 +0.19, 2018 -0.08,
2019 -0.77, 2020 -0.51, 2021 -1.36, 2022 -0.32, **2023 +1.94, 2024 +3.13, 2025 +2.10**,
2026 (partial) +0.87.

**The 22.33% "baseline" is not a property of STATIC_CONSENSUS. It is a property of the
post-2023 window.** For nine consecutive years the same rule sat at chance.

---

## 2. CONSENSUS_ERROR_ANATOMY

Winner ranks across 300 targets x 6 winners = 1,800 winner slots. Random expectation for
any single rank slot is 6/49 = 0.1224.

| Rank | Hits/300 | Rate | Lift |
|---|---|---|---|
| 1 | 37 | 0.1233 | **+0.0009** |
| 2 | 43 | 0.1433 | +0.0209 |
| 3 | 45 | 0.1500 | +0.0276 |
| 4 | 38 | 0.1267 | +0.0043 |
| 5 | 53 | 0.1767 | +0.0543 |
| 6 | 40 | 0.1333 | +0.0109 |
| 7 | 33 | 0.1100 | -0.0124 |
| 8 | 39 | 0.1300 | +0.0076 |
| 9 | 38 | 0.1267 | +0.0043 |
| 10 | 41 | 0.1367 | +0.0143 |
| 11 | 42 | 0.1400 | +0.0176 |
| 12 | 35 | 0.1167 | -0.0057 |

**A. BOUNDARY_MISS** — present but worthless (see §3).

**B. HIGH_CONFIDENCE_WRONG — CONFIRMED, and it is the sharpest error mode.**
The consensus's single most-confident pick hits **37/300 = 12.33%** against a random
expectation of 36.7. The rank-1 slot carries **literally zero edge**. Rank 5 outperforms
rank 1. The internal ordering *within* the top 6 is not merely weak — it is unordered.
Cumulative: top-1 0.1233, top-2 0.1333, top-3 0.1389 — the lift *increases* with depth.

**C. LOW_SUPPORT_WINNER — no rescueable structure.** 257/1,800 winners had zero support
from all 22 strategies; 739/1,800 had support <= 2. Their win rates (0.1171 and ~0.116)
sit *below* random, i.e. the low-support region is genuinely depleted, not hiding signal.

**D/E. FAMILY_CONCENTRATION / DIVERSITY — no effect** (§5).

**F. DISAGREEMENT_FAILURE — no effect.** `strategy_disagreement` r = -0.034 with M2+;
median split 0.227 vs 0.220.

**G. MARGIN_FAILURE — no effect.** `rank6_minus_rank7_margin` r = +0.048, tertile trend
-0.01, marginal p = 0.89.

**H. TEMPORAL — see §7.**

**I. NUMBER-LEVEL REPEATED ERROR — CONFIRMED, and severe (§6).**

---

## 3. TOP6_BOUNDARY_FINDINGS

This was the designated high-priority question. **The answer is a clean negative, and it
retires an entire class of hypotheses.**

Ranks 7-12 pooled: 228 winners in 1,800 slots = 0.1267 vs random 0.1224 (z = +0.55).
**The consensus rank ordering has no resolving power at all below rank 6.**

Oracle vs a *matched random pool* control (400 sims per cell) — the control is the part
prior boundary reasoning was missing:

| Pool | Oracle M2+, 1 replacement | Random pool of same size | Verdict |
|---|---|---|---|
| ranks 7-8 | 92 | **92.2** (p97.5 = 101) | identical |
| ranks 7-10 | 120 | 112.4 (p97.5 = 122) | within noise |
| ranks 7-12 | 135 | 129.2 (p97.5 = 139) | within noise |
| ranks 7-20 | 168 | 165.9 (p97.5 = 173) | identical |

With 2 replacements the picture is the same (top-8: 95 vs 94.1; top-20: 244 vs 243.9).

**Answering §7 of the packet directly: the oracle uplift from 67 -> 92 -> 135 is entirely
an artifact of being allowed to add more numbers. Consensus ranks 7-20 contain no more
winners than randomly chosen numbers do.** BOUNDARY_CORRECTION and any Top-8/Top-12/Top-16
reranking is **not worth researching**. This is the mechanical reason
CONSENSUS_RESIDUAL_RERANKER (K=16 pool) returned 18.67% — it was reranking noise.

Secondary finding: **71/300 targets (23.67%) have an exact score tie spanning the
rank-6/rank-7 boundary** (mean 1.5 numbers tied at the rank-6 score, max block 4). Every
such tie is resolved by *"lower number wins"*. In roughly one target in four, a ticket
slot is decided by an arbitrary sort key.

---

## 4. SUPPORT_SHAPE_FINDINGS

Eighteen pre-target descriptors were screened against M2+/M3+/hits. Because 18 features
were screened, a **family-wise permutation test** (4,000 label shuffles, statistic =
max |tertile trend| across all 18) is the only honest read.

**FAMILY-WISE p = 0.1052. No support-shape descriptor survives correction.**

Best candidate was `n_supported_numbers` (count of distinct numbers receiving any support):
trend T3-T1 = -0.16, marginal p = 0.0065, held-out quartiles 30.7% / 26.7% / 14.7% / 17.3%.

It was then **pre-specified and tested on the 1,117 search targets**:

| | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| HELD-OUT 300 | 0.307 | 0.267 | 0.147 | 0.173 |
| SEARCH 1117 | 0.129 | 0.140 | 0.172 | 0.146 |

Search-period trend **+0.0265, p = 0.3175 — sign reversed. REFUTED.**

Every other descriptor (margin, entropy, HHI, disagreement, family breadth, top-1 score,
support mass, mean gap, freq30) had marginal p >= 0.18. There is **no usable
CONSENSUS_STRONG_CONTEXT / CONSENSUS_WEAK_CONTEXT gate** in the support shape. The only
real conditioning variable found in this entire study is **calendar era** (§1).

Support level does show a non-monotone profile — support 0-4 all *below* random
(0.117-0.121), support 5-7 above (0.143 / 0.159 / 0.148), support 11 collapsing to 0.077
(n=39) — but the peak cells are small and this is the same screen that fails family-wise.

---

## 5. FAMILY_FINDINGS

Slot precision per family (a family's emitted number-slots that were winners), against
random 0.1224:

| Family | Strategies | Slots | Precision | Lift |
|---|---|---|---|---|
| statistical | 5 | 9,000 | 0.1339 | +0.0114 |
| deviation_gap | 5 | 9,000 | 0.1332 | +0.0108 |
| frequency | 1 | 1,800 | 0.1317 | +0.0092 |
| graph | 2 | 3,600 | 0.1300 | +0.0076 |
| zone | 3 | 5,400 | 0.1291 | +0.0066 |
| hot_cold | 3 | 5,400 | 0.1278 | +0.0053 |
| ml_like | 1 | 1,800 | 0.1239 | +0.0014 |
| ensemble | 1 | 1,800 | 0.1194 | -0.0030 |
| social | 1 | 1,800 | 0.1094 | -0.0130 |

**Uniform-draw family-wise permutation (4,000 reps): p = 0.3038.** Observed max |lift|
0.0130 against a null mean max of 0.0113. **No family is distinguishable from random.**
There is no FAMILY_COMPLEMENTARITY to exploit and no family worth dropping.

**CONSENSUS_FAILURE_RESCUER_CANDIDATES: none exist.** On the 233 consensus-failure
targets, the best individual strategy rescued 42 (18.03%). The uniform-null distribution
of *the maximum rescue rate over 22 strategies* has mean **18.53%** and p97.5 = 21.6%.
**Family-wise p = 0.6098** — the best observed rescuer is *below* what 22 random tickets
would produce. Apparent family rescue rates (deviation_gap 48%, ml_like 7.7%) track
family *headcount*, not skill.

Confirming this: on 215/233 failure targets *some* strategy reached M2+, but 22
independent random tickets would achieve that 97.3% of the time versus the observed
92.3%. The 22 streams are **worse than 22 random tickets** at covering the space, because
they are mutually correlated.

---

## 6. MINORITY_SIGNAL_FINDINGS

**MINORITY_SIGNAL_RESCUE is not supported.** Support <= 2 numbers win at 0.1134-0.1179
vs random 0.1224. The support x family-breadth joint cells show nothing: the best
low-support cell (`sup3_fam3`) is +0.0023.

But this section produced the study's second-largest structural finding — **not a minority
signal, but minority *annihilation*.**

Consensus top-6 slot allocation across 300 targets (1,800 slots):

| Band | Consensus slots | Expected | Ratio | Actual winners |
|---|---|---|---|---|
| 1-12 | 805 | 440.8 | **x1.83** | 430 |
| 13-24 | 453 | 440.8 | x1.03 | 448 |
| 25-36 | 404 | 440.8 | x0.92 | 445 |
| 37-42 | 121 | 220.4 | x0.55 | 230 |
| **43-49** | **17** | **257.1** | **x0.07** | **247** |

Numbers **42, 43, 44 and 48 were never selected once in 300 targets.** Per-number
selection sd = 30.57; the draws' own per-number win sd = 6.02 (uniform expectation 5.68).
**The consensus is ~5x more concentrated than the process it is predicting**, while the
actual winners are dead-on uniform in every band.

The cause is aggregation, not absence of coverage. Raw strategy emissions contain
numbers >= 43 at **15.92%** of slots (uniform expectation 14.29%) — the band is covered.
But that coverage is dominated by a single dissenting stream,
`biglotto_social_wisdom_anti_popularity` (1,500 of its 1,800 slots are >= 43), while
`zone_split_3bet_bet1/bet2` emit **zero**. A number carried by one strategy has weight
1/22 and can never outrank numbers carried by five to seven. **Majority-style aggregation
deletes 14% of the number space**, and no downstream reweighting of these 22 streams can
restore it.

---

## 7. TEMPORAL_CONTEXT_FINDINGS

The held-out gap analysis initially showed a long-gap lift (gap 35-39: 0.2414, family-wise
p = 0.011). **Testing it on the full draw history refuted it and exposed a data defect.**

Extending gap-vs-win to all draws produced a `gap_40plus` bucket with 18,885 cells at a
0.9% win rate — impossible under 6/49 (P(gap >= 40) ~ 0.5%). Cause:

**`draw_index.csv` (3,149 rows) is a mixed corpus. 46.1% of the history available to every
strategy at the first held-out target is not BigLotto data.**

| Block | n | Cadence | mean(max number) | Verdict |
|---|---|---|---|---|
| ROC 96-99 (2007-2010) | 418 | ~104/yr | 42.8 | clean 6/49 |
| **date-keyed 2009-07..2010-12** | **375** | daily | **22.5** | **not 6/49** |
| **ROC 100-102 (2011-2013)** | **939** | **313/yr** | **29.3** | **not 6/49** |
| ROC 103-115 (2014-2026) | 1,417 | ~110/yr | 42.8 | clean 6/49 |

A genuine 6/49 draw has E[max] ~ 43.0. Both clean blocks sit at 42.8. The two suspect
blocks sit at 22.5 and 29.3, and ROC years 100-102 carry 313 draws/year against
BigLotto's ~104. 358 calendar dates appear more than once. In the suspect rows, mean
per-number frequency is **287.8 for numbers <= 24 versus 39.1 for numbers >= 25**.

Association with the consensus's number bias:

- corr(consensus selection count, **suspect**-history frequency) = **+0.478**
- corr(consensus selection count, **clean**-history frequency) = **+0.043**
- corr(suspect frequency, clean frequency) = +0.006

The consensus's number preferences track the contaminated block and are essentially
uncorrelated with genuine BigLotto history. This is strong associational evidence, not
proof of causation — proving it requires re-running the strategies on a cleaned history,
which is precisely the recommended next experiment.

**Genuine temporal structure in the draws: none.** Consecutive-draw repeat rate is 0.1250
pre-2023 (z = +0.59) and 0.1250 post-2023 (z = +0.39) against 0.1224 expected. Per-number
win sd is uniform-consistent in both eras (9.32 vs 10.35; 6.83 vs 6.73). **The draws are
marginally uniform and serially independent throughout** — consistent with the existing
uniformity audit.

---

## 8. MOST_IMPORTANT_NEW_CLUE

**The 22.33% baseline is confined to post-2023 targets, and under the measured properties
of the draws it should not exist at all.**

The chain:

1. Pre-2023, over **996 targets**, STATIC_CONSENSUS scores 13.76% — at or below chance,
   shuffle-null p = 0.947.
2. Post-2023, over **421 targets**, it scores 22.33% — shuffle-null p = 0.0003.
3. The draws are marginally uniform **and** serially independent in *both* eras.
4. Consensus ticket churn is unchanged across the boundary (4.11 vs 4.00 of 6 overlap
   with the previous target's ticket).
5. Under (3), no predictor restricted to strictly-prior information can exceed 6/49 in
   expectation. So the post-2023 lift requires an explanation outside the strictly-prior
   information set.

Overlap of the ticket built for target *t* against draw *t+k* (chance 0.1224):

| era | t-3 | t-2 | t-1 | **t** | t+1 | t+2 | t+3 |
|---|---|---|---|---|---|---|---|
| PRE-2023 | .1746 | .1633 | .1987 | **.1215** | .1220 | .1206 | .1185 |
| z | +12.3 | +9.6 | +18.0 | **-0.2** | -0.1 | -0.4 | -0.9 |
| POST-2023 | .1932 | .1781 | .2146 | **.1441** | .1369 | .1400 | .1415 |
| z | +10.9 | +8.5 | +14.1 | **+3.3** | +2.2 | +2.7 | +2.9 |

This profile **argues against simple target look-ahead leakage**: a leak of the target
would spike at k=0 only, whereas post-2023 the ticket is elevated roughly uniformly
against *all* forward draws (k = 0,+1,+2,+3), with only a modest k=0 excess
(.1441 vs ~.1395). Yet a whole-window static bias is also insufficient, because the
within-block shuffle — which preserves the block's draw composition — still yields
p = 0.0003.

So there is a **genuine, unexplained short-range forward alignment present only after
2023**, and it is the only place in 1,417 targets where an edge could live. Resolving
what it is must gate every downstream conclusion: if it is an artifact, the
22.33% target and all five arms benchmarked against it are void; if it is real, it is
short-range and forward-persistent, which is a fundamentally different modelling target
than anything Track B has attempted.

---

## 9. TOP_10_FEATURE_OPPORTUNITIES

| # | Feature / signal | Why it may help | What consensus misses | Data ready | Cost | Info gain |
|---|---|---|---|---|---|---|
| 1 | **Era / regime indicator (pre-2023 vs post-2023)** | The only variable in this study that separates chance from signal (13.76% vs 22.33%) | Consensus is era-blind; 9 years of dead targets dilute every fit | YES | LOW | **HIGH** |
| 2 | **Forward-persistence window descriptor** (alignment of a ticket with draws t..t+3) | Isolates the post-2023 anomaly; distinguishes artifact from real short-range structure | Never measured; consensus has no notion of multi-draw alignment | YES | LOW | **HIGH** |
| 3 | **Cleaned-history re-emission** (drop the 1,314 non-BigLotto rows) | 46.1% of every strategy's input is another game | All 22 streams inherit a 7.4x low-number frequency skew | PARTIAL (needs strategy re-run) | MEDIUM | **HIGH** |
| 4 | **Band-coverage constraint / stratified selection over 1-12, 13-24, 25-36, 37-42, 43-49** | Consensus picks band 43-49 at x0.07 while it wins at x0.96 | 14% of the number space is unreachable | YES | LOW | MEDIUM |
| 5 | **Minority-carrier flag** (numbers supported by only 1-2 streams but by a *dissenting* family) | Identifies exactly the numbers majority voting deletes | Weight 1/22 can never reach top-6 | YES | LOW | MEDIUM |
| 6 | **Explicit tie-break signal at the rank-6/7 boundary** | 23.67% of targets currently resolve a ticket slot by "lower number wins" | A pure sort artifact decides ~1 slot in 4 targets | YES | LOW | MEDIUM |
| 7 | **Rank-depth reweighting within the top 6** | Rank 1 hits at 0.1233 (= chance); rank 5 at 0.1767 | The aggregator asserts an ordering it does not possess | YES | LOW | MEDIUM |
| 8 | **Stream-correlation / effective-N descriptor** | 22 streams cover less than 22 random tickets would (92.3% vs 97.3%) | Consensus treats correlated streams as independent votes | YES | LOW | MEDIUM |
| 9 | **Per-number selection-vs-win calibration residual** | Numbers 1,2,7,20 are over-selected by 55-65 net; 42,43,44,48 never selected | No feedback loop from realised precision to selection | YES | LOW | LOW |
| 10 | **Special-number context** | Special sits in consensus top-6 29 times vs 36.7 expected; mean rank 25.69 vs 25.0 | Quick check only — no relationship found | YES | LOW | **LOW (negative)** |

---

## 10. TOP_5_NEW_HYPOTHESES

Each is supported by a measurement above; none is a formal B experiment and none is
authorized here.

**H1 — REGIME_PARTITIONED_EVALUATION_INTEGRITY (highest priority).**
Every B649 result to date is an average over a period in which the rule demonstrably does
not work (996 pre-2023 targets at chance) and one in which it does (421 post-2023). Before
any successor is trained, establish *why* the 2023 boundary exists. Concretely: audit the
replay harness's history truncation for post-2023 targets, and re-measure all five
existing arms partitioned by era. Expected outcome is binary and decisive either way.

**H2 — CONTAMINATED_HISTORY_RE_EMISSION.**
Re-run the 22 streams with the 375 date-keyed rows and the 939 ROC-100-102 rows excluded,
then recompute STATIC_CONSENSUS. Prediction: the 1-12 over-selection (x1.83) and the
43-49 exclusion (x0.07) shrink materially. This is the only tested route to restoring
14% of the number space, and it is upstream of every reweighting experiment.

**H3 — BAND_STRATIFIED_CONSENSUS.**
Replace global top-6 with per-band selection quotas matched to the uniform band
distribution. Justified by the measured x1.83 / x0.07 distortion against dead-uniform
actual winners. Cheap, and it directly tests whether the concentration is costing
anything or is merely cosmetic.

**H4 — MINORITY_CARRIER_PROMOTION.**
Give a number carried by a small number of *low-overlap* streams a weight bonus over one
carried by the same count of mutually-correlated streams. Motivated by the finding that
22 streams cover the space worse than 22 random tickets. Note the honest caveat: raw
low-support numbers win at *below* random, so this must be tested as a diversity
correction, not as a "rare signal" hypothesis.

**H5 — INFORMED_BOUNDARY_TIE_BREAK.**
Replace `sorted((-score, number))` with a tie-break driven by an external descriptor at
the 23.67% of targets with an exact rank-6/7 tie. Deliberately scoped *narrowly*: §3
proves ranks 7-12 carry no signal, so this must draw on a signal outside the consensus
ranking (band coverage, stream diversity), not on rerank scores.

**Explicitly NOT recommended**, each retired by a control in this report:
boundary/Top-K reranking (§3, oracle == random pool); per-family reweighting (§5,
family-wise p = 0.3038); conditional rescue routing to a single strategy (§5, family-wise
p = 0.6098); support-shape confidence gating (§4, family-wise p = 0.1052 and the best
candidate sign-reversed out of sample).

---

## 11. LIMITS OF THIS ANALYSIS

- Development-data discovery only. Nothing here is a confirmation result and the 300
  targets can no longer serve as UNTOUCHED_CONFIRMATION.
- The contamination -> consensus-bias link is associational (corr +0.478 vs +0.043);
  causation requires H2's re-emission.
- The post-2023 anomaly is characterised but **not explained**. Look-ahead leakage is
  argued against by the flat k-offset profile but not excluded — the replay harness was
  not read.
- Family taxonomy is the ad hoc 9-bucket `family_for()` heuristic from the Track B script,
  which is not reconciled with the 221-catalog `method_family` field.
- The `SUPPORT_X_BREADTH` top cell is a ">= 5 / >= 4" bucket, not exactly 5/4.
- No successor selected, no model trained, no ADVANCE declared, no B hypothesis dispatched.

---

## 12. ARTIFACTS

- This report.
- `B649_TRACK_D_STATIC_CONSENSUS_FAILURE_FEATURES_R1.csv` — 1,417 rows x 48 columns,
  one row per target (both periods, era-tagged), carrying the reconstructed consensus
  ticket, outcome, all support-shape descriptors, winner ranks/supports, band counts,
  and tie flags.

No manifest package, no SHA ledger, no Judge, no PR, no DB table.
