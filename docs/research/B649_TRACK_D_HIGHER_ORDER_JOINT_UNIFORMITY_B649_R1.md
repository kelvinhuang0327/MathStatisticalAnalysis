# B649 Track D — Higher-Order Joint Uniformity (Triple/Quadruple), R1

**Task ID:** B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1
**Mode:** READ_ONLY_DISCOVERY_ANALYSIS
**Date:** 2026-08-15

## Purpose

Extends the already-sealed marginal/pairwise B649 uniformity battery (Holm min p=0.24, no detectable departure) to triple-wise and quadruple-wise main-number co-occurrence — a joint-structure dimension marginal and pairwise tests cannot see. The goal is not to prove randomness, but to decide whether higher-order dependence is worth developing into an M2+/M3+ prediction hypothesis.

## Data source and integrity

- Source: `research_draw_bindings` table, `.task-data/BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite` (opened strictly read-only via a `file:...?mode=ro` URI; zero writes attempted or possible).
- 4,178 raw rows → 2,288 distinct `(draw_number, draw_date)` identities for `lottery_type='BIG_LOTTO'` (two `draw_data_version` generations; re-verified live this session — zero content conflicts between them).
- Excluded 150 `DATE_LIKE` contaminant rows — a different, smaller-pool game injected into the same table under the same `lottery_type` label (draw_number literally equals draw_date formatted as `YYYYMMDD`; confined to Mon/Thu, 2009-07-27..2010-12-30). This exact discriminator was independently re-run live against the real file this session and reproduced precisely 150 excluded / 2,138 kept, matching the 2026-08-12 uniformity audit and every subsequent Track D report that cites "2,138 cleaned draws." This is the identical clean-draw definition the sealed pairwise study used, so this result is directly comparable to it.
- **Result: 2,138 clean draws, 2007-03-09 to 2026-07-31.**
- Integrity check (run fresh against the extracted set, not assumed from memory): every draw has exactly 6 unique numbers in 1..49, all 2,138 `(draw_number, draw_date)` keys unique, chronological order intact. **PASS, zero issues.**

## Method

All computation is pure Python stdlib — no numpy/scipy (confirmed not installed on this machine, matching the prior Track D audit) — using `math.comb`-based exact combinatorics. Core primitives (exact subset-inclusion probability, binomial PMF via a stable forward recurrence, exact two-sided binomial p-values, Holm-Bonferroni correction) were validated against brute-force enumeration of a toy 4-of-7 game and hand-worked textbook examples before touching any real data. The full pipeline was then sanity-checked on synthetic data: on pure-random synthetic draws it returned an unremarkable global p-value and 0 Holm survivors; with a deliberately injected dependency (one triple forced into 40 extra synthetic draws) it correctly flagged exactly that triple as the sole Holm survivor (adjusted p≈4e-32). This confirmed the pipeline has real discriminating power before it was pointed at real data.

- **Null model:** fair uniform 6-of-49 draw (numbers 1..49, no replacement), draws independent.
- **Exact triple-inclusion probability:** p₃ = C(46,3)/C(49,6) = 0.00108554 → expected count per triple E₃ = N·p₃ = 2.3209.
- **Exact quadruple-inclusion probability:** p₄ = C(45,2)/C(49,6) = 0.00007080 → E₄ = 0.15136.
- **Global omnibus statistic** (fixed before running, zero tuning): χ² = Σ(Oᵢ−E)²/E over all 18,424 triples, and separately over all 211,876 quadruples.
- **Null distribution:** fixed-seed Monte Carlo, seed=20260815, R=20,000 replications of N=2,138 independent uniform 6-of-49 draws each (throughput calibrated first on synthetic data: ~0.012s/replication, ~228s for the full real run). MC p-value = (1 + #{replications ≥ observed}) / (R + 1).
- **Local scan:** exact two-sided binomial test per triple. All 18,424 triples share identical (n, p) under the null, so one shared PMF/p-value lookup table was computed once, then applied to all 18,424 observed counts — not recomputed per triple. Holm-Bonferroni-corrected across the full family, family-wise α = 0.05.

## Results

### Global triple omnibus (primary verdict)
Observed χ²₃ = 18,055.57 vs. Monte Carlo null mean 18,405.38 (range across 20,000 replications: 17,427.36–19,379.21).
**p = 0.9295** — the observed statistic sits in the lower-middle of the null distribution, in neither tail.

### Global quadruple omnibus
Observed χ²₄ = 211,068.78 vs. null mean 211,864.51.
**p = 0.8551** — same pattern, unremarkable.

### Local triple scan
Family size 18,424. Min raw p = 3.145×10⁻⁵, min Holm-adjusted p = 0.5795. **0/18,424 Holm survivors** at α=0.05. A minimum raw p this small is exactly what pure-chance order statistics predict for a family of 18,424 tests (≈1/18,424 ≈ 5.4×10⁻⁵ scale for the smallest of that many roughly-uniform p-values under the null) — not evidence of a real effect. Per the Packet's own caveat, 0 local survivors alone would not be sufficient to conclude no structure; the global omnibus is the load-bearing verdict, and the two agree here.

### Effect description
- **Concentration:** max observed triple count = 11 (triple {9,25,35}), min = 0 (many triples never observed, as expected). The full count histogram (0 through 11 occurrences across all 18,424 triples) tracks a naive Poisson(2.32) approximation closely at every level (e.g. count=2: observed 4,943 vs ≈4,872 expected; count=5: observed 1,035 vs ≈1,015; count=11: observed 1 vs ≈0.5) — no dramatic excess mass anywhere in the distribution.
- **Dispersion:** observed variance of counts across all 18,424 triples = 2.274, essentially equal to (very slightly below) the expected value 2.321 — consistent with the omnibus χ² landing below the null mean rather than above it.
- **Tail behavior:** the single largest deviation (count 11 vs expected 2.32, ≈4.7×) is the extreme value of 18,424 trials and is fully absorbed by the Holm correction (adjusted p=0.58); nothing in the tail survives multiplicity correction.
- **Driven by few combinations?** No. Among the top-15 "excess" triples, only numbers 1 and 2 recur more than twice (5× and 4× respectively across those 15 triples) — plausibly just combinatorial spread from those numbers pairing with many partners, not shared structure, especially since single-number marginal frequency already showed no detectable departure (sealed pairwise study, Holm min p=0.24).
- **Temporal stability:** splitting the 2,138 draws chronologically into two equal halves (1,069 each) and correlating per-triple deviations from expectation between halves gives **r = −0.010** — no relationship. Spot-checking the top-9 "excess" triples individually: their counts split unevenly and inconsistently across the two halves (e.g. {4,10,45}: 3 vs 7; {1,16,41}: 7 vs 2; {15,30,38}: 3 vs 6) rather than both halves independently confirming the same "hot" triples. This is the signature of noise that happened to sum to a locally high total, not a stable effect.

## Verdict

**NO_DETECTABLE_HIGHER_ORDER_DEPARTURE.** Global triple and quadruple omnibus tests, the Holm-corrected local scan, and every effect-description angle (concentration, dispersion, tail, temporal stability) agree: B649's triple-wise and quadruple-wise main-number co-occurrence structure is indistinguishable from a fair uniform 6-of-49 draw process. This extends — not just repeats — the existing marginal/pairwise null result to two additional orders of joint structure.

Per the Packet's own caveat: NO_DETECTABLE ≠ proof of randomness. This is a bounded, pre-registered diagnostic at one fixed statistic and one fixed Monte Carlo protocol — it does not rule out other higher-order forms this design wasn't built to detect.

## Predictive interpretation

None. No M2+/M3+ prediction hypothesis is supported by this result — if anything the opposite: it removes triple/quadruple-wise joint structure from the list of untested mechanism classes, joining marginal and pairwise structure as already-ruled-out for B649. Per the Packet's explicit instruction, this finding is not being used to promote any specific triple (e.g. {9,25,35}) into a candidate-scoring experiment — its deviation is well within chance range once corrected for 18,424 comparisons.

## Scope discipline

- No repo files modified; no DB writes (source opened strictly read-only via `mode=ro` URI, confirmed by successful read/close with no lock or journal file created).
- No strategy development, no parameter/window search — the statistic and Monte Carlo protocol (seed, R) were fixed and calibrated on synthetic data before any real-data computation.
- No Cohort V2 prospective outcomes used.
- No mixing of B649/T539/P638 p-values — this result stands alone; cross-lottery comparison is explicitly the next step, not done here.
- Did not touch or depend on the uncommitted `B649_UNIFORMITY_DEPENDENCE_AUDIT_REBUILD_R1` worktree found during reconnaissance (different branch, 24 commits behind origin/main, apparently in-progress from another session) — this task's scripts were written fresh in this session's scratchpad, per the established Track D convention of re-deriving rather than depending on another session's uncommitted work.
- Repository provenance note: main's HEAD drifted from `1aee753` (session start) to `9b60007` during this task, and additional untracked P638 zone-1 constructor files appeared, from unrelated concurrent activity on the shared repo — not from this task, which made zero commits or edits and never read any repo source file as analysis input (only the external `baseline.sqlite`, outside the repo). Noted for transparency, not because it affects this result.

---

FINAL:

TASK_ID:
B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1

STATUS:
COMPLETE

LOTTERY:
B649

GAME:
6-of-49

DRAW_COUNT:
2138

DATA_INTEGRITY:
PASS

TRIPLES_TESTED:
18424

EXPECTED_TRIPLE_COUNT_UNDER_NULL:
2.3209 per triple (N=2138 × C(46,3)/C(49,6) = 2138 × 0.00108554)

GLOBAL_TRIPLE_OMNIBUS_METHOD:
Fixed zero-tuning chi-square dispersion statistic sum((O-E)^2/E) over all 18,424 triples; null distribution via fixed-seed (seed=20260815) Monte Carlo, R=20,000 replications of N=2,138 independent uniform 6-of-49 draws; MC p = (1+#{replications>=observed})/(R+1)

GLOBAL_TRIPLE_OMNIBUS_P:
0.9295 (observed chi2=18055.57 vs null mean 18405.38, range 17427.36-19379.21 across 20,000 replications)

LOCAL_HOLM_FAMILY_SIZE:
18424

MIN_RAW_P:
3.145e-05

MIN_ADJUSTED_P:
0.5795

LOCAL_HOLM_SURVIVORS:
0

QUADRUPLE_GLOBAL_OMNIBUS:
RUN

QUADRUPLE_P:
0.8551 (observed chi2=211068.78 vs null mean 211864.51; same seed/R, replications reused from the triple run)

UNIFORMITY_VERDICT:
NO_DETECTABLE_HIGHER_ORDER_DEPARTURE

IMPORTANT_EFFECTS:
Max triple count 11 vs expected 2.32 (triple {9,25,35}), fully absorbed by Holm correction (adjusted p=0.58); full count histogram tracks a Poisson(2.32) approximation closely at every level; observed count variance (2.274) approx. equals expected (2.321); split-half temporal-deviation correlation approx. 0 (r=-0.010) with top "excess" triples splitting unevenly and inconsistently across the two halves -- no stable "hot" triple signature; mild recurrence of numbers 1/2 in the top-15 excess list is plausibly combinatorial spread, not structure, given marginal frequency already cleared (Holm min p=0.24 in the sealed pairwise study).

PREDICTIVE_INTERPRETATION:
None supported. This result rules out (does not suggest) a triple/quadruple-wise M2+/M3+ prediction hypothesis for B649; no specific triple should be promoted to a candidate-scoring experiment on this evidence.

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

COHORT_V2_PROSPECTIVE_DATA_USED:
NO

NEXT:
T539_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1

END
