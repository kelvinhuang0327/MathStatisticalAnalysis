# B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_P638_R1

MODE: READ_ONLY_DISCOVERY_ANALYSIS (repo-external output write only)
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-15
CONTINUATION: RESUMED_FROM_QUOTA_EXHAUSTED_AGENT — the prior agent's completed preflight (data location, integrity, DB-copy hash match, TEXT-vs-numeric draw_number ordering finding) was independently re-verified from scratch in this session rather than taken on faith, since no partial script/notebook artifacts from that agent were found anywhere in the repo, `.runs/`, or session scratchpad. All numbers in this report are freshly computed.
REPO_MUTATION: NONE (confirmed — no files inside the MathStatisticalAnalysis repository were read, written, or otherwise touched; all working scripts live under the session scratchpad; all data reads were from an out-of-repo `.runs/` SQLite file opened `mode=ro`; the only artifact written is this report, outside the repository)
DB_MUTATION: NONE (source connections opened as `file:...?mode=ro`; only `SELECT` statements were issued)

## 1. Objective

Run the same uniformity/fairness battery previously applied to B649 (BIG_LOTTO 6/49) and replicated on T539 (DAILY_539, 5-of-39) against **P638 zone 1** (SuperLotto638 / 威力彩, 6-of-38 main numbers), and determine whether there is any statistically detectable departure from fair-random draws. Zone 2 (the 1-of-8 second number) is explicitly out of scope for this task and was not analyzed or mixed into this battery's Holm family.

## 2. Data source and integrity

**Source:** `draws` table (columns `run_id`, `draw_number`, `draw_date`, `main_numbers_json`, `second_number`, `source_reference`), `p638_wave1.sqlite3`, at
`/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/p638_wave1.sqlite3`, opened read-only (`file:...?mode=ro`).

**Note on table name:** unlike the T539 wave1 DB (`source_draws`), this P638 wave1 DB names the table `draws`. Confirmed via `.schema` / `PRAGMA table_info` before use — not assumed from naming convention.

A second, independently-materialized copy exists at `.runs/MathStatisticalAnalysis/P638_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1/p638_wave1.sqlite3`. Both contain exactly **1,933 rows**, single `run_id = p638-wave1-0f2f67c21f7a1921` in both. An MD5 hash of the sorted `(draw_date, sorted main_numbers_json)` tuple set is **identical** between the two files (`093380cd87b41fb5df2491c1c371b192`) — re-derived independently in this session (not copied from the prior agent's claim). The CLEAN_REPRODUCTION_AND_PUBLICATION_R2 copy was used as canonical for all analysis below. `source_reference` confirms the provenance: Taiwan Lottery official API, `SuperLotto638Result` endpoint.

Only zone-1 main numbers (`main_numbers_json`) and `draw_date`/`draw_number` were read. `second_number` (zone 2) was read only to confirm it stays within its own `[1,8]` range and was not otherwise used. No prediction/strategy/replay tables in this database were touched.

**Draw integrity check (every one of 1,933 rows, independently re-run this session):**

| Check | Result |
|---|---|
| `main_numbers_json` parses, exactly 6 elements | PASS (0 violations) |
| 6 elements are integers in `[1,38]` | PASS (0 violations) |
| 6 elements are distinct (no duplicate within a draw) | PASS (0 violations) |
| `second_number` in `[1,8]` | PASS (0 violations) |
| `draw_number` unique | PASS (1,933 unique) |
| `draw_date` unique | PASS (1,933 unique) |
| Numeric `draw_number` order strictly matches increasing `draw_date` | PASS (0 out-of-order pairs) |
| Cross-copy content hash match | PASS (identical MD5 across both DB files) |

**DATA_INTEGRITY: PASS — 0 issues found across 1,933 rows.**

Date range: **2008-01-24 to 2026-07-30** (1,933 draws).

**Resolved finding on `draw_number` ordering (confirmed, not a data defect):** `draw_number` is stored as TEXT and mixes 8-digit values (e.g. `"97000001"`, Republic-of-China calendar year 97 = 2008) with 9-digit values from ROC year 100 (2011) onward (e.g. `"100000001"`). Plain TEXT/lexicographic sort places `"100000001"` before `"97000001"` (because `'1' < '9'` as the first character), which is chronologically wrong. Sorting by `int(draw_number)` instead — as this analysis does throughout — gives an order that is exactly strictly increasing with `draw_date` (verified: 0 violations across all 1,932 adjacent pairs). This is a TEXT-comparison artifact of the storage format, not a data-integrity error, and it does not affect any result below since all chronological operations (era split, adjacent-draw overlap) use the numeric order.

## 3. Methodology — reused from the B649/T539 battery, adapted to N=38, k=6

Test categories, null semantics, and the pooled Holm-Bonferroni procedure are carried over unchanged from `B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1.md`. Every constant that depends on the game shape (N=38 numbers, k=6 drawn, vs. T539's N=39, k=5) was **re-derived from first principles for 6-of-38**, not copied from the T539 report, and independently validated against brute-force enumeration before use (Section 3.4). Zone 2 (1-of-8 special number) has no analogue test in this battery, consistent with T539 dropping the special-ball test for the same structural reason (T539 also has no special number).

### 3.1 Test family (7 categories, N=38, k=6)

1. **Main-ball frequency (omnibus).** H0: each number 1..38 is drawn with marginal probability p=6/38=3/19≈0.157895, independently across draws. Statistic `T1 = Σᵢ(Xᵢ - Dp)²/(Dp(1-p))` over the 38 per-number draw counts Xᵢ. MC null (Xᵢ are not independent within a draw — exactly 6 of 38 are "hit" each draw).
2. **8-era homogeneity.** History split into K=8 chronologically contiguous eras by numeric draw order: sizes 242×5, 241×3 (mechanical split, `1933 // 8 = 241` remainder 5, remainder assigned to the first eras — K=8 fixed in advance to mirror the B649/T539 battery, not tuned for P638). Statistic `T2 = Σᵢ,ₑ(Xᵢₑ-Eᵢₑ)²/Eᵢₑ`, MC null.
3. **Carryover overlap vs hypergeometric.** For each of the 1,932 consecutive-draw pairs, overlap = count of shared numbers. Under H0 (independent draws), overlap ~ Hypergeometric(N=38, K=6, n=6). Statistic `T3 = Σₘ₌₀⁶(Oₘ-Eₘ)²/Eₘ`, MC null.
4. **Positional order statistics (6 positions, not 5).** For sorted position j=1..6, exact theoretical mean of the j-th order statistic of a random 6-subset of {1..38} is `j(N+1)/(k+1) = 39j/7`. Statistic = observed sample mean of position j; MC two-sided null (distance from theoretical mean).
5. **Sum mean.** Exact theoretical mean and variance of the draw sum: `E[S]=k(N+1)/2=117`, `Var[S]=k(N-k)(N+1)/12=624`. Statistic = observed sample mean of the draw sum; MC two-sided null, cross-checked against an analytic CLT z-test (Section 4.2).
6. **Per-number scan (38 elementary tests).** For each number i, exact two-sided binomial test (n=1,933, p=6/38, "double the smaller exact tail" method) on its observed hit count.
7. **Pair scan (703 elementary tests).** For every unordered pair {i,j}, i<j (all C(38,2)=703), exact two-sided binomial test (n=1,933, p=6·5/(38·37)=30/1406=15/703≈0.021337) on its observed co-occurrence count.

### 3.2 Holm-Bonferroni correction

All raw p-values from categories 1–7 are pooled into **one family of 751 elementary tests** (1+1+1+6+1+38+703), and standard Holm step-down correction is applied once across the whole pooled family (not per-category). A test is a survivor at α=0.05 if its Holm-adjusted p < 0.05.

### 3.3 Monte Carlo settings (tests 1–5)

Tests 1–5 have no simple closed-form joint null (within-draw negative correlation between numbers), so their p-values were obtained by exact simulation: **20,000 independent replications** of a full 1,933-draw history under H0 (`random.sample(1..38, 6)` per draw, Python's own PRNG, fixed seed **20260815** — reused from the T539 replication for cross-report consistency of convention; this is purely a seed-value choice and does not pool or share any data or p-values between the T539 and P638 analyses), computing all 10 statistics (T1, T2, T3, 6 positional means, sum mean) from each replication in a single pass. MC p-value = (1 + #replications at least as extreme)/(1 + 20,000). Runtime: **129.3s** for the full run.

### 3.4 Independent validation performed before running on real data

- All closed-form formulas (position-order-statistic mean, sum mean/variance, per-number and per-pair probabilities, hypergeometric overlap pmf) were verified **exactly** (via `fractions.Fraction`, no floating-point) against brute-force enumeration of all C(N,k) combinations on five small toy cases: (N,k) = (9,4), (10,3), (12,5), (7,2), and **(13,6)** — the last one chosen specifically to match this task's k=6 shape. All matched to the exact fraction, no mismatches, for every one of: per-number probability, per-pair probability, all order-statistic means, sum mean, sum variance, and the full hypergeometric overlap pmf (validated against a full brute-force double-enumeration over all pairs of k-subsets, not just its mean).
- At the real scale (N=38, k=6), the overlap pmf's own expectation, computed two independent ways (Σm·pmf(m) vs. the closed form k²/N=18/19), matched exactly (both `18/19 = 0.947368...`, as exact `Fraction`s).
- The exact-binomial CDF routine (log-space via `math.lgamma`) was verified to `1.03e-15` against independent exact rational-arithmetic computation (n=20, p=1/4) — same toy check as the T539 report, same tolerance order.
- The sum-mean MC p-value (0.6741) was cross-checked against an independent analytic CLT z-test using the exact theoretical mean/variance: z = -0.4225, two-sided analytic p ≈ 0.6727 — closely matches the MC estimate, cross-validating both methods.
- Internal consistency checks on the real data: Σ per-number counts = 11,598 = 1,933×6 ✓; Σ overlap tally = 1,932 = D-1 ✓; distinct pairs observed = 703 = C(38,2) ✓; Σ pair counts = 28,995 = 1,933×15 ✓.

## 4. Results

### 4.1 Omnibus / positional / sum tests (10 tests, Monte Carlo, 20,000 reps)

| Test | Statistic | Expected | Raw p (MC) |
|---|---:|---:|---:|
| Main-ball frequency (omnibus) | T1 = 39.60 | — | 0.4040 |
| 8-era homogeneity (omnibus) | T2 = 250.93 | — | 0.5825 |
| Carryover overlap vs hypergeometric | T3 = 1.508 | — | 0.8692 |
| Position 1 (min) mean | 5.529 | 5.571 | 0.6712 |
| Position 2 mean | 11.028 | 11.143 | 0.3711 |
| Position 3 mean | 16.689 | 16.714 | 0.8575 |
| Position 4 mean | 22.192 | 22.286 | 0.5094 |
| Position 5 mean | 27.899 | 27.857 | 0.7450 |
| Position 6 (max) mean | 33.423 | 33.429 | 0.9602 |
| Sum mean | 116.760 | 117.000 | 0.6741 |

None of the 10 omnibus/positional/sum tests are individually remarkable even before correction (raw p between 0.37 and 0.96).

### 4.2 Per-number scan (38 tests) — most extreme entries

| Number | Observed | Expected | Direction | Raw p |
|---|---:|---:|---|---:|
| 9 | 268 | 305.21 | deficit (-12.2%) | 0.020233 |
| 24 | 341 | 305.21 | excess (+11.7%) | 0.029602 |
| 5 | 275 | 305.21 | deficit | 0.061277 |
| 38 | 333 | 305.21 | excess | 0.091151 |
| 32 | 279 | 305.21 | deficit | 0.106208 |
| 2 | 280 | 305.21 | deficit | 0.120752 |
| 3 | 330 | 305.21 | excess | 0.131992 |
| 34 | 282 | 305.21 | deficit | 0.154414 |

Number 9's raw p (0.0202) would not survive a Bonferroni correction for 38 comparisons alone (threshold 0.05/38=0.00132), let alone the full 751-test family.

### 4.3 Pair scan (703 tests) — most extreme entries

| Pair | Observed | Expected | Direction | Raw p |
|---|---:|---:|---|---:|
| (4,16) | 63 | 41.24 | excess | 0.001717 |
| (6,38) | 61 | 41.24 | excess | 0.004242 |
| (2,34) | 24 | 41.24 | deficit | 0.004782 |
| (23,33) | 24 | 41.24 | deficit | 0.004782 |
| (7,28) | 60 | 41.24 | excess | 0.006517 |
| (3,24) | 59 | 41.24 | excess | 0.009857 |
| (17,32) | 26 | 41.24 | deficit | 0.014111 |
| (28,30) | 26 | 41.24 | deficit | 0.014111 |

The single smallest raw p in the entire 751-test family is pair (4,16), p=0.001717 — but number 4's own per-number scan is fully unremarkable (p=0.3097) and number 16's is equally unremarkable (p=0.5591). Like T539's most-extreme pair, this reads as an isolated fluctuation among 703 comparisons, not the echo of any individual-number effect.

A milder, genuinely mechanical echo is visible around number 24: three of the fifteen smallest raw p-values in the whole family are pairs involving 24 — (3,24) p=0.0099, (1,24) p=0.0147, (15,24) p=0.0147 — and 24 itself has the second-most-extreme per-number result (p=0.0296, excess). This is the same pattern the T539 report flagged for numbers 36/37: a mildly elevated single-number marginal mechanically drags every pair containing that number upward in the ranking, without that being independent evidence of pairwise structure. 24's own per-number effect is not Bonferroni-significant even at the 38-test level (threshold 0.00132 vs. observed 0.0296).

### 4.4 Overlap distribution detail (adjacent-draw carryover, informing T3)

| Overlap (m) | Observed | Expected (Hypergeometric × 1,932 pairs) |
|---:|---:|---:|
| 0 | 639 | 634.18 |
| 1 | 847 | 845.57 |
| 2 | 381 | 377.49 |
| 3 | 61 | 69.42 |
| 4 | 4 | 5.21 |
| 5 | 0 | 0.13 |
| 6 | 0 | 0.0004 |

Observed and expected track closely at every overlap size; T3's high raw p (0.8692) is consistent with this table.

### 4.5 Pooled Holm-Bonferroni correction (full family)

- **HOLM_FAMILY_SIZE: 751** (1 + 1 + 1 + 6 + 1 + 38 + 703)
- **MIN_RAW_P: 0.001717** (pair [4,16], excess)
- **MIN_ADJUSTED_P: 1.0** — every one of the 751 Holm-adjusted p-values equals 1.0. The single smallest raw p (0.001717), multiplied by its Holm step-down factor (751, rank 1 of 751), already exceeds 1 (751 × 0.001717 ≈ 1.289 → capped at 1.0), and Holm's monotonicity requirement forces every subsequent rank to at least that value.
- **HOLM_SURVIVORS: 0 / 751** (threshold: Holm-adjusted p < 0.05)

For calibration: under pure H0 with ~751 roughly-uniform p-values, the expected smallest p-value is on the order of 1/752 ≈ 0.00133. The observed minimum (0.001717) is about 1.29× that — unremarkable, well within ordinary sampling variation, not a signal.

## 5. Compliance checklist (DO / DO NOT)

- Draw integrity verified first, independently re-run this session (not taken on the prior agent's claim alone): YES (Section 2).
- Reused existing B649/T539 test definitions / null semantics / Holm correction: YES, with all N=38,k=6 constants re-derived and independently validated (Section 3.4), none copied numerically from T539.
- Zone 2 (1-of-8 second number) excluded from this battery and its Holm family: confirmed — Section 1, Section 3.
- No new data-driven tests added, no test family changed to chase significance: confirmed — 7 categories in, 7 categories out, K=8 eras fixed a priori (mirrors B649/T539, not tuned).
- No repo/DB mutation: confirmed (header, Section 2).
- No strategy building, no prediction, no parameter tuning, no window search: confirmed — this is measurement only.
- No pooling of B649/T539/P638 p-values or Holm correction, no cross-lottery result used to select or alter a P638 test or subgroup: confirmed — Section 6 below.
- No prediction/strategy/replay tables read: confirmed — only `draws` (actual historical outcomes) was read.

## 6. Cross-lottery firewall

```
B649_RESULT_USED_AS_DATA: NO
T539_RESULT_USED_AS_DATA: NO
```

B649 and T539 results are cited in Section 1/7 only as research background/narrative context (i.e., "this replicates a prior finding on a different lottery"). No p-value, test statistic, subgroup selection, or Holm correction from B649 or T539 was combined with, or used to influence, any P638 test, threshold, or family membership in this report.

## 7. FINAL

```
DRAW_COUNT: 1,933 (2008-01-24 to 2026-07-30)
DATA_INTEGRITY: PASS — 0 issues across all 1,933 rows (exactly 6 unique zone-1 numbers in 1..38 per draw; unique draw_number/draw_date; numeric draw_number order strictly increasing with draw_date; cross-copy content hash identical)
TESTS_RUN: 7 test categories replicated from the B649/T539 battery, re-derived for N=38,k=6 — main-ball frequency omnibus; 8-era homogeneity omnibus; carryover overlap vs hypergeometric omnibus; positional order statistics (6 positions); sum mean; per-number scan (38); pair scan (703)
HOLM_FAMILY_SIZE: 751
MONTE_CARLO_REPS: 20,000 (fixed seed 20260815, runtime 129.3s, reproducible)
MIN_RAW_P: 0.001717 (pair [4,16], excess: observed 63 vs expected 41.24)
MIN_ADJUSTED_P: 1.0 (all 751 Holm-adjusted p-values are 1.0)
HOLM_SURVIVORS: 0
UNIFORMITY_VERDICT: NO_DETECTABLE_DEPARTURE
IMPORTANT_EFFECTS: None survive family-wise correction. Two surface patterns are visible only in the uncorrected raw p-values, worth naming precisely because they look suggestive before correction: (1) number 9 has the largest single per-number deficit (268 vs 305.21 expected, raw p=0.0202, not Bonferroni-significant even at the 38-test level); (2) three of the fifteen smallest raw p-values in the whole 751-test family are pairs involving number 24, a mechanical echo of 24's own mildly-elevated (and itself non-significant) per-number marginal, not independent pairwise evidence. The single smallest raw p in the entire family (pair [4,16], p=0.0017) is unconnected to any individual-number effect (4: p=0.310; 16: p=0.559) and reads as an isolated fluctuation. All 10 omnibus/positional/sum-mean tests are unremarkable even before correction (raw p between 0.37 and 0.96). The adjacent-draw overlap distribution tracks its hypergeometric expectation closely at every value 0-6.
INTERPRETATION: P638 zone-1's 1,933-draw history (2008-2026) is statistically indistinguishable from a fair, i.i.d. uniform-random 6-of-38 draw process under this 751-test battery. This replicates, on a third and structurally different lottery, the same NO_DETECTABLE_DEPARTURE finding reached for BIG_LOTTO 6/49 (B649, battery Holm min p = 0.24) and DAILY_539 5-of-39 (T539, HOLM_SURVIVORS = 0/789). NO_DETECTABLE_DEPARTURE is not PROOF_OF_RANDOMNESS — it means this specific, pre-registered battery, at this sample size, found nothing; a subtler or differently-shaped effect could still exist undetected. As with B649 and T539, no frequency, positional, era, carryover, or pairwise structure was found in P638 zone-1 that any strategy could exploit to improve P(match) above the fair-random baseline.
B649_RESULT_USED_AS_DATA: NO
T539_RESULT_USED_AS_DATA: NO
P638_ZONE2_USED: NO
REPO_MUTATION: NONE
DB_MUTATION: NONE
```

## NEXT

Per Track D routing: since UNIFORMITY_VERDICT = NO_DETECTABLE_DEPARTURE, the designated next step is **Track D cross-lottery synthesis** — B649 + T539 + P638 together — followed by an explicit decision on whether to deprioritize further within-lottery temporal-structure mining across all three lotteries, given that three structurally different games (6/49 no-special, 5/39 no-special, 6/38+1/8) have now each independently produced the same null result under comprehensive, pre-registered, Holm-corrected batteries.
