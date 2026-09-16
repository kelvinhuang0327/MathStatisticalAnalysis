# T539 Track D — Higher-Order Joint Uniformity (Triple/Quadruple), R1

**Task ID:** T539_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1
**Mode:** READ_ONLY_DISCOVERY_ANALYSIS
**Date:** 2026-08-15

## Purpose

Extends the already-sealed marginal/pairwise T539 uniformity battery (`B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1`, Holm min adjusted p = 1.0, 0/789 survivors, no detectable departure) to triple-wise and quadruple-wise main-number co-occurrence — a joint-structure dimension marginal and pairwise tests cannot see. This directly parallels `B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1` (run the same day on BIG_LOTTO 6-of-49), reusing its fixed statistic, seed, and Monte Carlo protocol, adapted to T539's 5-of-39 game shape. The goal is not to prove randomness, but to decide whether higher-order dependence is worth developing into an M2+/M3+ prediction hypothesis.

## Data source and integrity

- **Source:** `source_draws` table, `t539_wave1.sqlite3`, at `/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3`, opened strictly read-only via a `file:...?mode=ro` URI. Only `SELECT` statements were issued; no `prediction_tickets` / `prediction_scores` / `target_completion` / `strategy_coverage` (Cohort V2 / prospective) tables were touched.
- A second, independently-materialized copy exists at `.runs/MathStatisticalAnalysis/T539_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1/t539_wave1.sqlite3`. Both files have 5,930 rows, and an MD5 hash of `(draw_date, main_numbers_json)` over all rows sorted by date is **identical** between the two (`8c14dea0478bdc1ff463962b61f5aab3`) — re-verified live this session, independently of the prior replication report's own cross-check.
- **Fresh integrity check (run this session against the extracted set, not assumed from memory or the prior report), all 5,930 rows:**

| Check | Result |
|---|---|
| `lottery_type == 'DAILY_539'` for all rows | PASS (0 violations) |
| exactly 5 unique numbers per draw | PASS (0 violations) |
| all numbers in `[1,39]` | PASS (0 violations) |
| `draw_id` unique | PASS (5,930 unique) |
| `draw_date` unique, strictly increasing by `draw_order` | PASS (5,930 unique, 0 out-of-order) |
| `draw_order` unique, contiguous | PASS |

**Result: 5,930 clean draws, 2007-01-01 to 2026-08-01. DATA_INTEGRITY: PASS, 0 issues.** (Same row count, date range, and 0-issue result as the prior marginal/pairwise replication — re-derived fresh, not copied forward.)

No stray `-wal`/`-shm`/`-journal` file was created next to either DB copy after this session's reads (checked directly), confirming zero write side effects from the read-only connections.

## Method

Pure Python stdlib only — no numpy/scipy (confirmed not installed on this machine: `python3 -c "import numpy"` / `import scipy` both fail). Core primitives (exact subset-inclusion probability, log-space binomial PMF via `math.lgamma`, two-sided exact binomial p-value via the double-the-smaller-exact-tail method, Holm-Bonferroni step-down correction, bijective combination indexing) were validated against brute-force enumeration on six small toy games — (N,k,m) = (9,4,2), (9,4,3), (10,3,2), (12,5,3), (12,5,4), (7,2,2) — using exact `fractions.Fraction` arithmetic, plus a known textbook Holm-correction worked example, all before touching real data (`validate_toy.py`, all checks PASS).

- **Null model:** fair uniform 5-of-39 draw (numbers 1..39, no replacement), draws independent.
- **Exact triple-inclusion probability (re-derived for 5-of-39, not reused from B649's 6-of-49 constants):** p₃ = C(36,2)/C(39,5) = 630/575,757 = C(5,3)/C(39,3) = 10/9,139 = 0.0010942116 → expected count per triple E₃ = N·p₃ = 5,930 × 0.0010942116 = **6.488675**. (Cross-checked exactly: total triple-hits = 5,930×C(5,3) = 59,300, and 59,300/9,139 triples = 6.488675 — same value via two independent routes.)
- **Exact quadruple-inclusion probability:** p₄ = C(35,1)/C(39,5) = 35/575,757 = C(5,4)/C(39,4) = 5/82,251 = 0.0000607895 → E₄ = N·p₄ = **0.360482**. (Cross-check: 5,930×C(5,4) = 29,650; 29,650/82,251 = 0.360482 ✓.)
- **Global omnibus statistic** (fixed before running, identical semantic to the B649 higher-order task, zero tuning): χ² = Σ(Oᵢ−E)²/E over all C(39,3) = **9,139 triples**, and separately over all C(39,4) = **82,251 quadruples**.
- **Null distribution:** fixed-seed Monte Carlo, **seed = 20260815** (same literal seed value as the B649 higher-order task, per the Packet's reuse instruction), **R = 20,000 replications** of N = 5,930 independent uniform 5-of-39 draws each (`random.sample(1..39, 5)` per draw, Python's own PRNG). Throughput calibrated first on a small R=100 synthetic run (19.81 ms/replication, extrapolated ≈396s for R=20,000); the full real run took **391.1s (6.52 min)**, computing both χ²₃ and χ²₄ from the same simulated draws in a single pass (replications reused between the triple and quadruple statistics, matching the B649 precedent's approach). MC p-value = (1 + #{replications ≥ observed}) / (R + 1).
- **Local scan:** exact two-sided binomial test per triple. All 9,139 triples share identical (n=5,930, p=p₃) under the null, so one shared log-space PMF/tail lookup table was computed once (0.001s) and applied to all 9,139 observed counts — not recomputed per triple. Holm-Bonferroni-corrected across the full family, family-wise α = 0.05. Per the Packet's explicit instruction, **no local quadruple scan was run** ("不做逐 quadruple fishing scan") — quadruples were tested only via the single global omnibus statistic.

## Results

### Global triple omnibus (primary verdict)
Observed χ²₃ = 8,975.88 vs. Monte Carlo null mean 9,129.65 (range across 20,000 replications: 8,562.55–9,761.56).
**p = 0.8413** — the observed statistic sits in the upper-middle of the null distribution, in neither tail.

### Global quadruple omnibus
Observed χ²₄ = 82,172.52 vs. null mean 82,250.63 (range: 80,752.20–83,953.47).
**p = 0.5763** — almost exactly centered in the null distribution, unremarkable.

### Local triple scan
Family size 9,139. Min raw p = 8.367×10⁻⁴ (two triples tied at this value: {4,11,22} and {21,33,35}, both observed count = 17 vs expected 6.49), min Holm-adjusted p = 1.0. **0/9,139 Holm survivors** at α=0.05. For calibration: with ~9,139 roughly-uniform p-values under pure H0, the expected smallest raw p is on the order of 1/9,140 ≈ 1.09×10⁻⁴; the observed minimum (8.37×10⁻⁴) is about 7.7× that scale — a mildly small but unremarkable minimum for a family this size, not evidence of a real effect. Per the Packet's own caveat, 0 local survivors alone would not be sufficient to conclude no structure; the global omnibus is the load-bearing verdict, and the two agree here.

### Effect description
- **Concentration:** max observed triple count = 17, tied between {4,11,22} and {21,33,35} (expected 6.49); min = 0 (17 triples never observed, of 9,139 — also expected under Poisson(6.49), where P(count=0) ≈ 0.00152 × 9,139 ≈ 13.9). The full count histogram (0 through 17) tracks a Poisson(6.4887) approximation closely at every level:

  | count | observed | Poisson approx |
  |---:|---:|---:|
  | 0 | 17 | 13.9 |
  | 3 | 635 | 632.7 |
  | 6 | 1,469 | 1,440.5 |
  | 9 | 748 | 780.8 |
  | 12 | 165 | 161.6 |
  | 17 | 2 | 2.5 |

  No dramatic excess mass anywhere in the distribution.
- **Dispersion:** observed variance of counts across all 9,139 triples = 6.3729, essentially equal to (very slightly below) the expected value 6.4887 — consistent with the global χ² landing below the null mean rather than above it (same qualitative pattern as the B649 higher-order result).
- **Tail behavior:** the two largest deviations (count 17 vs expected 6.49, ≈2.6×) are the extreme values of 9,139 trials and are fully absorbed by the Holm correction (adjusted p=1.0); nothing in the tail survives multiplicity correction.
- **Driven by few combinations?** No. Among the top-15 smallest-raw-p triples (a mix of high-count and zero-count entries), the most-recurring single number is **3**, appearing in 4 of the 15 (in 45 number-slots total, an average of ~1.15 appearances per number is expected by chance alone). Number 3 was **not** among the notable entries (37, 36, 25, 22) flagged in the prior marginal/pairwise per-number scan — this recurrence is unconnected to any individual-number marginal effect, plausibly just combinatorial spread from shared partners rather than real structure, the same interpretation the B649 higher-order report reached for its own top-15 list.
- **Temporal stability:** splitting the 5,930 draws chronologically into two equal halves (2,965 each) and correlating per-triple deviations from expectation between halves gives **r = −0.0079** — no relationship. Spot-checking the top-9 "excess/deficit" triples individually: their counts split unevenly and inconsistently across the two halves (e.g. {4,11,22}: 6 vs 11; {17,25,37}: 11 vs 5; {10,12,34}: 10 vs 6) rather than both halves independently confirming the same "hot" triples — the signature of noise that happened to sum to a locally high or low total, not a stable effect.

## Verdict

**NO_DETECTABLE_HIGHER_ORDER_DEPARTURE.** Global triple and quadruple omnibus tests, the Holm-corrected local scan, and every effect-description angle (concentration, dispersion, tail, temporal stability) agree: T539's triple-wise and quadruple-wise main-number co-occurrence structure is indistinguishable from a fair uniform 5-of-39 draw process. This extends — not just repeats — the existing marginal/pairwise null result (789-test battery, Holm min adjusted p = 1.0) to two additional orders of joint structure, and replicates, on a second and structurally different lottery, the same pattern the B649 higher-order task found for BIG_LOTTO 6/49 (triple p=0.9295, quad p=0.8551).

Per the Packet's own caveat: NO_DETECTABLE ≠ proof of randomness. This is a bounded, pre-registered diagnostic at one fixed statistic and one fixed Monte Carlo protocol — it does not rule out other higher-order forms this design wasn't built to detect.

## Predictive interpretation

None. No M2+/M3+ prediction hypothesis is supported by this result — if anything the opposite: it removes triple/quadruple-wise joint structure from the list of untested mechanism classes for T539, joining marginal and pairwise structure as already-ruled-out. Per the Packet's explicit instruction, this finding is not being used to promote any specific triple (e.g. {4,11,22} or {21,33,35}) into a candidate-scoring experiment — their deviation is well within chance range once corrected for 9,139 comparisons.

## Scope discipline

- No repo files modified; no DB writes (both source copies opened strictly read-only via `mode=ro` URI; confirmed no `-wal`/`-shm`/`-journal` files were created).
- No strategy development, no parameter/window search — the statistic and Monte Carlo protocol (seed, R) were fixed and validated on toy data before any real-data computation, reusing the B649 higher-order task's exact semantic design rather than tuning a new one.
- No Cohort V2 prospective outcomes used — only `source_draws` (actual historical outcomes) was read.
- No mixing of B649/T539/P638 p-values — this result stands alone; the B649 report's numbers are cited only as a qualitative cross-lottery comparison, never combined into a joint statistic.
- No large governance package built — one report, no manifest/matrix/registry scaffolding.
- All working scripts (`common.py`, `validate_toy.py`, `step1_load_and_observed.py`, `step2_mc.py`) were written fresh to this session's scratchpad, not to the repository.
- Repository provenance note: main's HEAD drifted from `baf65ac1c` (task start) to `94590f2e1` during this task, and the untracked-file set changed (from unrelated concurrent P638 zone-1 activity on the shared repo) — not from this task, which made zero commits or edits and never read any repository source file as analysis input (only the external `t539_wave1.sqlite3`, outside the repo). Noted for transparency, not because it affects this result.

---

FINAL:

TASK_ID:
T539_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1

STATUS:
COMPLETE

LOTTERY:
T539

GAME:
5-of-39

DRAW_COUNT:
5930

DATA_INTEGRITY:
PASS (0 issues across all 5,930 rows: exactly 5 unique numbers in 1..39 per draw; unique draw_id/draw_date/draw_order; draw_order contiguous; draw_date strictly increasing; lottery_type=DAILY_539 throughout; cross-checked identical against a second independently-materialized DB copy)

TRIPLES_TESTED:
9139

GLOBAL_TRIPLE_OMNIBUS_METHOD:
Fixed zero-tuning chi-square dispersion statistic sum((O-E)^2/E) over all 9,139 triples (E3=5930*C(5,3)/C(39,3)=6.488675 per triple); null distribution via fixed-seed (seed=20260815) Monte Carlo, R=20,000 replications of N=5,930 independent uniform 5-of-39 draws; MC p = (1+#{replications>=observed})/(R+1). Semantic design and seed/R reused unchanged from B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1; only the game-shape-dependent inclusion probability was re-derived for 5-of-39.

GLOBAL_TRIPLE_OMNIBUS_P:
0.8413 (observed chi2=8975.88 vs null mean 9129.65, range 8562.55-9761.56 across 20,000 replications)

LOCAL_HOLM_FAMILY_SIZE:
9139

MIN_RAW_P:
8.367e-04

MIN_ADJUSTED_P:
1.0

LOCAL_HOLM_SURVIVORS:
0

QUADRUPLE_GLOBAL_OMNIBUS:
RUN

QUADRUPLE_P:
0.5763 (observed chi2=82172.52 vs null mean 82250.63, range 80752.20-83953.47; same seed/R, replications reused from the triple run; E4=5930*C(5,4)/C(39,4)=0.360482 per quadruple)

UNIFORMITY_VERDICT:
NO_DETECTABLE_HIGHER_ORDER_DEPARTURE

IMPORTANT_EFFECTS:
Max triple count 17 (tied: {4,11,22} and {21,33,35}) vs expected 6.49, fully absorbed by Holm correction (adjusted p=1.0); full count histogram tracks a Poisson(6.4887) approximation closely at every level; observed count variance (6.3729) approx. equals expected (6.4887); split-half temporal-deviation correlation approx. 0 (r=-0.0079) with top "excess/deficit" triples splitting unevenly and inconsistently across the two halves (e.g. {4,11,22}: 6 vs 11; {17,25,37}: 11 vs 5) -- no stable "hot" triple signature; mild recurrence of number 3 (4x) in the top-15 raw-p list is plausibly combinatorial spread, not structure, and does not correspond to any of the notable per-number marginal effects (37/36/25/22) found in the prior T539 marginal/pairwise replication.

INTERPRETATION:
T539's 5,930-draw history (2007-2026) shows no detectable triple-wise or quadruple-wise joint departure from a fair, i.i.d. uniform-random 5-of-39 draw process, under this pre-registered statistic and Monte Carlo protocol. This extends the already-sealed marginal/pairwise NO_DETECTABLE_DEPARTURE result (789-test battery, Holm min adjusted p=1.0) to two additional orders of joint structure, and replicates -- on a second, structurally different lottery -- the same higher-order finding pattern the B649 task reached for BIG_LOTTO 6/49 (triple p=0.9295, quad p=0.8551). NO_DETECTABLE_HIGHER_ORDER_DEPARTURE is not PROOF_OF_RANDOMNESS: this is a bounded, pre-registered diagnostic at one fixed statistic and protocol, and 0 local Holm survivors alone would not by itself have been sufficient evidence -- the global omnibus is the load-bearing verdict, and it agrees with the local scan here. No triple/quadruple-wise M2+/M3+ prediction hypothesis is supported for T539 by this evidence.

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

NEXT:
P638_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1

END
