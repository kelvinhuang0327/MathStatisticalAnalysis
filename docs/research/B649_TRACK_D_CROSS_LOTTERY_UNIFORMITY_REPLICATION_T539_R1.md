# B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1

MODE: READ_ONLY_DISCOVERY_ANALYSIS
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-15
REPO_MUTATION: NONE (confirmed — no files inside the MathStatisticalAnalysis repository were read, written, or otherwise touched; all working scripts live under the session scratchpad, all data reads were from an out-of-repo `.runs/` SQLite file opened `mode=ro`, and the only artifact written is this report, outside the repository)
DB_MUTATION: NONE (source connection opened as `file:...?mode=ro`; only `SELECT` statements were issued)

## 1. Objective

Run the existing B649 uniformity/fairness battery — restricted to the tests applicable to a 5-of-39 game with no special number — against T539's (今彩539 / DAILY_539) full draw history, and determine whether there is any statistically detectable departure from fair-random draws.

## 2. Data source and integrity

**Source:** `source_draws` table, `t539_wave1.sqlite3`, at
`/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3`, opened read-only.

A second, independently-materialized copy exists at `.runs/MathStatisticalAnalysis/T539_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1/t539_wave1.sqlite3`. Both have 5,930 rows in `source_draws`, and a hash of `(draw_date, main_numbers_json)` over all rows, sorted, is **identical** between the two files (`efda8d2320a3db73e176adb011baffef`) — the underlying draw content is confirmed consistent across both candidates even though the files differ at the byte level. The CLEAN_REPRODUCTION_AND_PUBLICATION_R2 copy was used as canonical.

Only `source_draws` (actual historical outcomes) was read. `prediction_tickets`, `prediction_scores`, `target_completion`, and `strategy_coverage` (Cohort V2 / prospective-scoring tables) were not touched, per the DO-NOT constraint.

**Draw integrity check (every one of 5,930 rows):**

| Check | Result |
|---|---|
| `lottery_type == 'DAILY_539'` for all rows | PASS (0 violations) |
| `main_numbers_json` parses, exactly 5 elements | PASS (0 violations) |
| 5 elements are integers in `[1,39]` | PASS (0 violations) |
| 5 elements are distinct (no duplicate within a draw) | PASS (0 violations) |
| `draw_id` unique | PASS (5,930 unique) |
| `draw_date` unique and strictly increasing by `draw_order` | PASS (5,930 unique, 0 out-of-order) |
| `draw_order` unique and contiguous (0..5929) | PASS |

**DATA_INTEGRITY: PASS — 0 issues found across 5,930 rows.**

Date range: **2007-01-01 to 2026-08-01** (5,930 draws), matching the Packet's stated range.

## 3. Methodology — reused from the B649 battery

The B649 uniformity/fairness battery (see prior memory: `biglotto-uniformity-audit-and-baseline-contamination`, run 2026-08-12) is documented as an 8-test battery: main-ball frequency, special-ball frequency, 8-era homogeneity, carryover overlap vs hypergeometric, positional order statistics, sum mean, per-number scan with Holm correction, pair scan with Holm correction — each per-scan test using exact binomial tails, and a single pooled Holm-Bonferroni correction reported as "battery Holm min p."

**Transparency note (methodology provenance):** the literal B649 battery scripts (`uniformity.py`, `era.py`, `contam.py`) were session scratchpad artifacts, not committed to the repository, and no longer exist on disk — confirmed absent from the repo source tree, from every `.task-data/` and `.runs/` archive, and from all other workspace projects searched. This replication therefore **reconstructs the same test family, same null hypothesis (draws are i.i.d. uniform random 5-of-39 subsets, no structure), and the same pooled Holm-Bonferroni procedure**, re-implemented fresh with standard exact/Monte-Carlo statistical methods rather than literally reusing unrecoverable code. No test family was added, removed (beyond the inapplicable special-ball test), or altered to chase significance. All formulas below were independently validated against brute-force enumeration on small toy cases before being applied to the real data (Section 3.4).

Special-ball frequency was **removed**: DAILY_539 draws 5 numbers from 1-39 with no special/bonus number, so this test has no analogue.

### 3.1 Test family (7 categories, T539-adapted: N=39, k=5)

1. **Main-ball frequency (omnibus).** H0: each number 1..39 is drawn with marginal probability p=5/39, independently across draws. Statistic `T1 = Σᵢ(Xᵢ - Dp)²/(Dp(1-p))` over the 39 per-number draw counts Xᵢ. Null distribution obtained by Monte Carlo (see 3.3) rather than an assumed asymptotic df, because the Xᵢ are not independent within a draw (exactly 5 of 39 are "hit" each draw).
2. **8-era homogeneity.** History split into K=8 chronologically contiguous, (nearly) equal-size eras by draw order (sizes 742,742,741,741,741,741,741,741 — mechanical split, `5930 // 8` with the remainder assigned to the first eras; K=8 fixed in advance, mirroring the B649 battery's own era count, not searched or tuned for T539). Statistic `T2 = Σᵢ,ₑ(Xᵢₑ-Eᵢₑ)²/Eᵢₑ`, MC null.
3. **Carryover overlap vs hypergeometric.** For each pair of consecutive draws, overlap = count of numbers shared. Under H0 this is exactly Hypergeometric(N=39, K=5, n=5). Statistic `T3 = Σₘ₌₀⁵(Oₘ-Eₘ)²/Eₘ`, MC null.
4. **Positional order statistics.** For each sorted position j=1..5, exact theoretical mean of the j-th order statistic of a random 5-subset of {1..39} is `j(N+1)/(k+1)`. Statistic = observed sample mean of position j; MC two-sided null.
5. **Sum mean.** Exact theoretical mean and variance of the draw sum: `E[S]=k(N+1)/2=100`, `Var[S]=k(N-k)(N+1)/12=566.667`. Statistic = observed sample mean of the draw sum; MC two-sided null (cross-checked against an analytic CLT z-test, Section 4.2).
6. **Per-number scan (39 elementary tests).** For each number i, exact two-sided binomial test (n=5930, p=5/39, "double the smaller exact tail" method) on its observed hit count.
7. **Pair scan (741 elementary tests).** For every unordered pair {i,j}, i<j (all C(39,2)=741), exact two-sided binomial test (n=5930, p=C(37,3)/C(39,5)=0.013495) on its observed co-occurrence count.

### 3.2 Holm-Bonferroni correction

All raw p-values from categories 1-7 above are pooled into **one family of 789 elementary tests** (1+1+1+5+1+39+741), and standard Holm step-down correction is applied once across that whole pooled family (not per-category), matching the B649 battery's own single reported "battery Holm min p." A test is a survivor at α=0.05 if its Holm-adjusted p < 0.05.

### 3.3 Monte Carlo settings (tests 1-5)

Tests 1-5 have no simple closed-form joint null (within-draw negative correlation between numbers), so their p-values were obtained by exact simulation rather than an assumed asymptotic chi-square df: 20,000 independent replications of a full 5,930-draw history under H0 (`random.sample(1..39, 5)` per draw, Python's own PRNG, fixed seed 20260815 for reproducibility), computing all 9 statistics (T1, T2, T3, 5 positional means, sum mean) from each replication in a single pass. MC p-value = (1 + #replications at least as extreme)/(1 + 20,000). Runtime: 208.0s for the full run.

### 3.4 Independent validation performed before running on real data

- All closed-form formulas (position-order-statistic mean, sum mean/variance, per-number and per-pair probabilities, hypergeometric overlap pmf) were verified **exactly** (via `fractions.Fraction`, no floating-point) against brute-force enumeration of all C(N,k) combinations on four small toy cases: (N,k) = (9,4), (10,3), (12,5), (7,2). All matched to the fraction, no mismatches.
- The exact-binomial CDF routine (log-space via `math.lgamma`) was verified to ~1e-15 against independent exact rational-arithmetic computation (n=20, p=1/4).
- The sum-mean MC p-value (0.7228) was cross-checked against an independent analytic CLT z-test using the exact theoretical mean/variance: z = -0.359, two-sided analytic p ≈ 0.719 — closely matches the MC estimate, cross-validating both methods.
- Internal consistency checks on the real data: Σ per-number counts = 29,650 = 5,930×5 ✓; Σ overlap tally = 5,929 = D-1 ✓; distinct pairs observed = 741 = C(39,2) ✓; Σ pair counts = 59,300 = 5,930×10 ✓.

## 4. Results

### 4.1 Omnibus / positional / sum tests (9 tests, Monte Carlo, 20,000 reps)

| Test | Statistic | Expected | Raw p (MC) |
|---|---:|---:|---:|
| Main-ball frequency (omnibus) | T1 = 39.20 | — | 0.4666 |
| 8-era homogeneity (omnibus) | T2 = 276.56 | — | 0.4078 |
| Carryover overlap vs hypergeometric | T3 = 1.285 | — | 0.8643 |
| Position 1 (min) mean | 6.611 | 6.667 | 0.4149 |
| Position 2 mean | 13.247 | 13.333 | 0.3201 |
| Position 3 mean | 19.979 | 20.000 | 0.8223 |
| Position 4 mean | 26.699 | 26.667 | 0.6887 |
| Position 5 (max) mean | 33.352 | 33.333 | 0.7748 |
| Sum mean | 99.889 | 100.000 | 0.7228 |

None of the 9 omnibus/positional/sum tests are individually remarkable even before correction.

### 4.2 Per-number scan (39 tests) — most extreme entries

| Number | Observed | Expected | Direction | Raw p |
|---|---:|---:|---|---:|
| 37 | 823 | 760.26 | excess (+8.3%) | 0.01661 |
| 36 | 789 | 760.26 | excess | 0.2730 |
| 25 | 779 | 760.26 | excess | 0.4771 |
| 22 | 752 | 760.26 | deficit | 0.7665 |

Number 37's raw p (0.0166) would not even survive a Bonferroni correction for 39 comparisons alone (threshold 0.05/39=0.00128), let alone the full 789-test family.

### 4.3 Pair scan (741 tests) — most extreme entries

| Pair | Observed | Expected | Direction | Raw p |
|---|---:|---:|---|---:|
| (22,25) | 55 | 80.03 | deficit | 0.003712 |
| (25,37) | 106 | 80.03 | excess | 0.005936 |
| (36,37) | 106 | 80.03 | excess | 0.005936 |
| (25,36) | 105 | 80.03 | excess | 0.008085 |
| (8,36) | 104 | 80.03 | excess | 0.010917 |
| (23,36) | 104 | 80.03 | excess | 0.010917 |
| (3,32) | 58 | 80.03 | deficit | 0.011574 |
| (10,30) | 59 | 80.03 | deficit | 0.016365 |

7 of the 15 smallest raw p-values in the entire 789-test family involve number 36 or 37 — a visually suggestive cluster. This is exactly the pattern the pooled Holm correction exists to guard against: individually, number 37's own scan is unremarkable (p=0.0166 pre-correction), and 36's is fully unremarkable (p=0.273); pairs involving either number will mechanically drift upward together purely from that shared marginal, without needing any real structure. Pair (22,25), the single smallest raw p in the whole family, is not connected to any individual per-number effect (22: p=0.767; 25: p=0.477) — it reads as an isolated fluctuation among 741 comparisons.

### 4.4 Pooled Holm-Bonferroni correction (full family)

- **HOLM_FAMILY_SIZE: 789**
- **MIN_RAW_P: 0.003712** (pair [22,25], deficit)
- **MIN_ADJUSTED_P: 1.0** — every one of the 789 Holm-adjusted p-values equals 1.0. Even the single smallest raw p in the entire family (0.003712), multiplied by its Holm step-down factor (789, since it is rank 1 of 789), already exceeds 1 (789 × 0.003712 ≈ 2.93 → capped at 1.0), and Holm's monotonicity requirement forces every subsequent rank to at least that value. (The "test name" attached to MIN_ADJUSTED_P in the raw data dump is an artifact of tie-breaking among 789 identical 1.0 values, not a meaningful attribution — MIN_RAW_P's test, pair[22,25], is the informative one.)
- **HOLM_SURVIVORS: 0 / 789** (threshold: Holm-adjusted p < 0.05)

For calibration: under pure H0 with ~789 roughly-uniform p-values, the expected smallest p-value is on the order of 1/790 ≈ 0.00127. The observed minimum (0.0037) is about 3× that — unremarkable, consistent with ordinary sampling variation, not a signal.

## 5. Compliance checklist (DO / DO NOT)

- Draw integrity verified first: YES (Section 2).
- Reused existing B649 test definitions / null semantics / Holm correction: YES, with the provenance caveat in Section 3 (original code unrecoverable; family, nulls, and correction procedure faithfully replicated).
- Special-number test removed (not applicable to T539): YES.
- No new data-driven tests added, no test family changed to chase significance: confirmed — 7 categories in, 7 categories out, K=8 eras fixed a priori (mirrors B649, not tuned).
- No repo/DB mutation: confirmed (Section 0 header).
- No strategy building, no prediction, no parameter tuning, no window search: confirmed — this is measurement only.
- No mixing of B649/P638 statistics: confirmed — only T539's own data was analyzed; the B649 battery's *methodology* was replicated, no B649 *numbers* were combined with T539 numbers anywhere.
- No Cohort V2 / prospective outcomes used: confirmed — only `source_draws` (actual historical outcomes) was read.

## FINAL

```
DRAW_COUNT: 5,930 (2007-01-01 to 2026-08-01)
DATA_INTEGRITY: PASS — 0 issues across all 5,930 rows (exactly 5 unique numbers in 1..39 per draw; unique draw_id/draw_date/draw_order; draw_order contiguous; draw_date strictly increasing; lottery_type=DAILY_539 throughout)
TESTS_RUN: 7 test categories replicated from the B649 battery (special-ball frequency removed, N/A for T539) — main-ball frequency omnibus; 8-era homogeneity omnibus; carryover overlap vs hypergeometric omnibus; positional order statistics (5 positions); sum mean; per-number scan (39); pair scan (741)
HOLM_FAMILY_SIZE: 789
MIN_RAW_P: 0.003712 (pair [22,25], deficit: observed 55 vs expected 80.03)
MIN_ADJUSTED_P: 1.0 (all 789 Holm-adjusted p-values are 1.0)
HOLM_SURVIVORS: 0
UNIFORMITY_VERDICT: NO_DETECTABLE_DEPARTURE
IMPORTANT_EFFECTS: None survive family-wise correction. Two surface patterns are visible only in the uncorrected raw p-values and are worth naming precisely because they look suggestive before correction: (1) number 37 has the largest single per-number excess (823 vs 760.26 expected, raw p=0.0166, not Bonferroni-significant even at the 39-test level); (2) 7 of the 15 smallest raw p-values in the whole 789-test family involve number 36 or 37, a mechanical echo of (1) through shared marginals in the pair scan, not independent evidence. The single smallest raw p in the entire family (pair [22,25], p=0.0037) is unconnected to any individual-number effect and reads as an isolated fluctuation. All 9 omnibus/positional/sum-mean tests are unremarkable even before correction (raw p between 0.32 and 0.86).
INTERPRETATION: T539's 5,930-draw history (2007-2026) is statistically indistinguishable from a fair, i.i.d. uniform-random 5-of-39 draw process under this 789-test battery. This replicates, on a second and structurally different lottery, the same NO_DETECTABLE_DEPARTURE finding the B649 uniformity audit reached for BIG_LOTTO 6/49 (battery Holm min p = 0.24 there). NO_DETECTABLE_DEPARTURE is not PROOF_OF_RANDOMNESS — it means this specific, reasonably comprehensive battery, at this sample size, found nothing; a subtler or differently-shaped effect could still exist undetected. As with B649, no frequency, positional, era, carryover, or pairwise structure was found in T539 that any strategy could exploit to improve P(match) above the fair-random baseline.
```

## NEXT

Per Track D routing: `B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_P638_R1`.
