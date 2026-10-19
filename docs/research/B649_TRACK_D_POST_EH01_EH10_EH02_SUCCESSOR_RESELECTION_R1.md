# B649_TRACK_D_POST_EH01_EH10_EH02_SUCCESSOR_RESELECTION_R1

TASK_ID: `B649_TRACK_D_POST_EH01_EH10_EH02_SUCCESSOR_RESELECTION_R1`
MODE: `READ_ONLY_RESEARCH_DECISION`
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-16
REPO_MUTATION: NONE — DB_MUTATION: NONE — COHORT_V2_PROSPECTIVE_DATA_USED: NO

---

## 0. Evidence-freshness notice — the Packet's own priors are partly stale

Before scoring candidates, three same-day artifacts were found that are **not reflected in this task's LATEST EVIDENCE section**, in every case because a concurrent or prior session wrote a report before this task was invoked. This project has hit this exact "orphan report ahead of the memory index" failure mode before ([[b649-track-d-post-metadata-prediction-frontier-reselection-r1]]); treating it as necessary due diligence here, not scope creep.

### 0.1 Candidate A (jackpot/rollover) has already been executed and sealed — it is not an open candidate

`/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/B649_TRACK_B_PREDRAW_JACKPOT_ROLLOVER_PREDICTION_LEVEL1_R1/report.md`, **mtime 2026-08-16 18:12:42 — the single newest file in the entire `.task-data` tree**, newer than every other artifact checked in this task, including the two sibling discovery reports below. `STATUS: WEAK_SIGNAL`, `ACTION: DO_NOT_ADVANCE`.

Design: `derive_pre_draw_jackpot_rollover(...)` reconstructs the advertised pre-draw jackpot as `prior_draw.lastPrize + prior_draw.prize` whenever the prior draw had zero jackpot winners (a legitimately same-draw-causal quantity, not a lag artifact) and uses it to select among three already-existing portfolio generators (`HORIZON_MINIMAX_2`, `DEVIATION_2`, `ZONE_SPLIT_2_OF_3`) via a causal regime lookup. Result on the standard 300-target benchmark:

| Condition | M2+ rate | Δ vs baseline |
|---|---:|---:|
| BASELINE_ONLY | 0.2633 | — |
| BASELINE_PLUS_ROLLOVER (real) | 0.3133 | +0.0500 |
| STALE_PLACEBO | 0.3067 | +0.0433 |
| SHUFFLED_PLACEBO | 0.3067 | +0.0433 |
| ERA_CONTROL (plain calendar-year dummy) | 0.3467 | **+0.0833** |

The real signal beat both the stale and shuffled placebos — but a **plain calendar-year regime dummy beat the real rollover-conditioned model by a wider margin**. `Survives the calendar-year era control: False.` This is the same era-drift signature that has now closed essentially every mechanism tried against this population (EH01, EH04, EH10, both EH02 edges, cross-lottery lagged context, structured-contrastive legal-set, static-consensus alignment — and now this).

**Consequence for this task:** the Packet's own framing of jackpot/rollover as `CURRENT BEST NEW INPUT CANDIDATE` is superseded by newer evidence than the Packet had. It is carried below only as a closed, non-selectable data point (Section 1.0), not scored as a live candidate — selecting it would be exactly the same-exposed-evidence rescue the Packet's own no-rescue rule forbids by extension.

### 0.2 Two rigorous same-day discovery reports already scoped this exact question

- `.task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/report.md` (2026-08-16 15:57) — screened five candidate sources (calendar/schedule, verified draw order/position, realized crowd popularity, jackpot/sales state, equipment/ball-set) for historical existence, causal timestamp, and acquisition cost. Explicitly did not select or execute anything. Directly informs Sections 1.3 and 1.4 below (better evidence than this task's own first-pass sub-agent search produced, and used in preference to it where the two disagree).
- `.task-data/B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1/report.md` (2026-08-15 21:30) — confirmed all five of the sources above sit at **0/69** production-strategy usage (genuinely unused by any current strategy), and separately found the 69-strategy catalog is heavily saturated in frequency/gap/hot-cold/deviation/Markov/zone transforms (58/69 IDs). Its own top-candidate ranking (cross-lottery-lag > calendar > draw-order > popularity+jackpot > equipment) predates today's jackpot-rollover null and does not weight era-proxy risk as heavily as this task's own selection criteria require — Section 1.3 explains why this task's ranking of calendar diverges from it.
- `.task-data/B649_TRACK_B_CATALOG_BLIND_SPOT_NEW_INFORMATION_DISCOVERY_R1/report.md` (2026-08-15 21:26, one directory level further out) — re-sliced existing 57-strategy-family emissions for blind-spot structure. `NEW_INFORMATION_SOURCE_SIGNAL: NONE`; explicitly "does not select or start D's next Frontier hypothesis." One more confirmation that transformations of the *existing* draw-history/strategy-output space are saturated — it does not compete with or preempt this task.

### 0.3 The Frontier V2 catalog is not "49 EH hypotheses" — and the 45-unexecuted count is stale

The catalog referenced by [[b649-track-d-post-structured-set-successor-reselection-r1]] lives off-repo at `~/VibeCoding-WorkSpace/B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_NORMALIZED_R1.csv` and siblings. **49 = 28 pre-existing internal "H" hypotheses + 21 literature-sourced external "EH" survivors** (6 more EH candidates, EH19–EH24, were rejected pre-execution as exact/near duplicates of internal H items). The "45/49 unexecuted" figure is a static 2026-08-13 snapshot. As of today, after EH01/EH02/EH10 (and EH04, executed 08-14, one day before EH01/EH10):

- External EH side: **4/21 executed** (EH01, EH02, EH04, EH10), all NO_SIGNAL — **17 EH candidates remain**.
- Internal H side: 9 of a top-10 wave executed; **12 confirmed still fully open** (H11, H13, H15, H16, H18, H20, H22, H23, H24, H25, H26, H28).
- Reconciled open count today: **≈29 of 49**, not 45 — still far from saturated, but the qualitative "not saturated" conclusion is unchanged.

### 0.4 Operational note

Multiple concurrent-session artifacts were observed and left completely untouched, matching this program's established convention: `tools/b649_operational_prediction_loop.py` (modified), `.task-data/` (untracked), `docs/research/strategy-matrix-phase5-geometry-only-portfolio-application-r1-report.md`, `src/lottolab/research/cyclic_sidon_shift_p638_zone1.py`, `src/lottolab/research/low_overlap_portfolio_constructor.py` + its test (all untracked). None were read for content beyond what is cited above, none were modified.

---

## 1. Candidate comparison

### 1.0 (Reference only — not scored, not selectable) PRE-DRAW_JACKPOT_ROLLOVER_STATE

STATUS: **ALREADY_EXECUTED — SEALED WEAK_SIGNAL / DO_NOT_ADVANCE** (Section 0.1). Included here only because the Packet named it the current-best candidate and an honest reselection must show why it is gone, not silently drop it.

Independent of today's result, its mechanism story was also weaker than the Packet's framing assumed: a fair, notary-witnessed mechanical draw process (independently verified via primary sources in [[b649-track-d-pre-cutoff-orthogonal-information-reselection-r1]]) has no physical channel by which the advertised jackpot amount could influence *which numbers* get drawn. Its only plausible causal role is prize-value/EV optimization (avoiding crowded combinations when many people play a large jackpot) — a different estimand from this task's stated PRIMARY_SUCCESS_METRIC (M2+ hit-rate) — and that exact estimand (`ALLOCATION_EXPOSURE_EFFICIENCY_B649_V1`) was already separately marked `DESIGN_ABANDONED`/data-infeasible in this project's own research ledger before today's execution. Two independent reasons it was never going to be the answer, now joined by a third: the direct experiment itself failed.

### 1.1 Candidate B — BEST_REMAINING_UNEXECUTED_FRONTIER_HYPOTHESIS: EH27

TITLE: `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`
TYPE: New statistical mechanism over existing information (not a new information source)
NEW_INFORMATION_SOURCE: None — operates on the same sealed B649 draw history and existing per-strategy residual outputs every prior null result already used.
PRIOR_OVERLAP: Low-medium. Targets a specific blind spot the existing Holm-corrected marginal/pairwise/triple/quadruple battery is structurally underpowered against — a *small, localized* coordinated departure — rather than re-testing the same global-uniformity null EH01/EH04/EH10 already closed. Not a lag/window/parameter variant of any sealed hypothesis.
ERA_PROXY_RISK: Low-medium if implemented with this program's now-standard train-only calibration plus an explicit era-stratified diagnostic (required given four independent era-drift findings already surfaced this program: post-2023 static-consensus jump, EH02's stale-beats-real result on both edges, cross-lottery-lag's stale-beats-real result, and today's jackpot-rollover era-control failure).
DATA_READINESS: High — zero new ingestion; uses draw history and existing strategy residual streams already in the repo.
DIRECT_M2_M3_PATH: Indirect. Like EH01/EH04/EH10 and the static-consensus-alignment study, it is a regime-detection *gate* (allocate vs. abstain / which existing candidate to trust) rather than a source of new ticket content. This exact "detect state, gate a decision" shape is now 0-for-roughly-9 on this population for single-ticket M2+ improvement.
TRANSFER_POTENTIAL: Moderate — a genuine methodological blind-spot argument (localized vs. global departure) has a real, if modest, chance of surviving where broad-uniformity tests structurally cannot, but inherits the same population that has resisted every mechanism tried so far.
IMPLEMENTATION_COST: Low-medium — standard scan-statistic/higher-criticism machinery, no exotic infrastructure, similar cost class to EH02.

### 1.2 Candidate C — CALENDAR_SCHEDULE_OR_OTHER_READY_NEW_CONTEXT

TITLE: `CALENDAR_SCHEDULE_CONTEXT_FEATURE`
TYPE: Re-derivation of already-stored metadata (draw date), not new information
NEW_INFORMATION_SOURCE: None — `draw_date` is already 100%-populated in the canonical schema; a weekday/month/holiday feature is pure local computation, zero acquisition cost.
PRIOR_OVERLAP: High, in substance if not in literal form. The *deeper* version of this question — is there a temporal/regime effect in B649 — has already been investigated multiple times and closed without a mechanism: the post-2023 static-consensus M2+ step (13.76%→22.33%, [[b649-track-d-static-consensus-failure-mode-r1]]) survived an internal-cause search ([[b649-track-b-static-consensus-alignment-mechanism-r1]]: no feature transfers TRAIN→HELDOUT) and an external-cause search ([[b649-track-d-concession-protocol-era-mechanism-feasibility-r1]]: `EVIDENCE_INSUFFICIENT`, explicit "do not use year>=2024 as a predictor"). A plain literal `day_of_week`/`month` feature was never coded before today, but the mechanism space it would probe has been.
ERA_PROXY_RISK: **High, and partially already realized.** Today's readiness-discovery report adds a sharper, concrete finding: B649's weekday composition is itself non-stationary — 643 non-Tue/Fri draws in 2007–2013 alone (2010: every week had a Mon+Wed+Thu draw) versus only 110 non-Tue/Fri draws across the following 12 years (2014–2026). A weekday feature built without explicitly scoping to post-2014 (or modeling the pre-2014 block as its own regime) mechanically confounds calendar with era by construction, not by coincidental correlation.
DATA_READINESS: `READY_NOW` — highest of all four candidates.
DIRECT_M2_M3_PATH: Weak. No physical mechanism is known: venue, notary process, and draw ceremony are independently verified constant and identical across the full history and across all three lotteries ([[b649-track-d-pre-cutoff-orthogonal-information-reselection-r1]]), leaving no known channel by which draw-day could affect which numbers are drawn.
TRANSFER_POTENTIAL: Low — if a calendar effect appears, the base rate established by this program (4 independent "real signal loses to an era/stale control" findings, including today's) says the most likely explanation is regime drift, not a durable chronologically-transferable pattern.
IMPLEMENTATION_COST: Very low.

**Required sub-answer — predictive mechanism vs. era/slow-drift proxy:** based on this program's own record, these two cannot currently be distinguished for B649. Every attempt to explain the post-2023 boundary as a real mechanism (internal cause, external/concession cause) has come back null or insufficient, and every other "real-looking" effect tested this program that wasn't explicitly calendar has independently turned out to be an era artifact when checked. The only defensible test design would require an effect to hold up *within* each already-identified homogeneous era block separately (not pooled across the whole history) before it could be credited as more than drift — a high bar this candidate has not been built to clear and that materially lowers its expected value relative to Candidates B and D.

### 1.3 Candidate D — DRAW_ORDER_LIKE_HISTORY: verified draw-order/position (`drawNumberAppear`)

TITLE: `DRAW_ORDER_POSITION_FEASIBILITY_AND_NATIVE_SIGNAL`
TYPE: Genuinely new raw information source (not a new lens on existing information)
NEW_INFORMATION_SOURCE: **Yes — the strongest of any candidate.** Every B649 draw-content analysis this entire research program has ever run (marginal/pairwise/triple/quadruple co-occurrence, motif/discord, permutation entropy, context-tree weighting, regime changepoint, uniformity audit, structured legal-set, static-consensus alignment) operates on the **sorted six-number set**, which [[b649-rank-authority-absent-combination-semantics]] already established carries "zero rank information" by construction (100% ascending-sorted in the sealed foundation, adapters explicitly discard order via `return tuple(sorted(...))`). The official API's `drawNumberAppear` field is independently confirmed (today's readiness-discovery report, three real bounded GETs against `api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result` spanning 2007-01/03, 2015-06, and 2026-08) to be a genuine, non-sorted **permutation** of the same six-plus-special numbers, with the special number consistently in the same relative slot across every sampled record — this is the first candidate in the program's history to offer a data channel none of the ~10 prior null mechanisms ever looked at.
PRIOR_OVERLAP: None identified — `draw_order_position` is confirmed at 0/69 production-strategy usage and was never a feature in any Track B/D task to date.
ERA_PROXY_RISK: Low a priori — a within-draw positional/ordering signal has no obvious calendar-alignment mechanism the way recent-window-vs-reference-window statistics do. Still requires the program's standard era-stratified diagnostic as a matter of discipline, not because a specific risk is already known.
DATA_READINESS: The weakest dimension, and the reason this is not immediately Track B. **Not ingested anywhere** — 0/3,158 canonical rows, 0/3,149 legacy-snapshot rows have any slot for it; the production ingestion adapter (`taiwan_lottery_draw_provider.py`) fetches this field over the wire on every sync today and silently discards it before storage. It **is** present at the source with `MEDIUM-HIGH` trust (same official regulator endpoint the whole pipeline already keys on for winning numbers) across three widely-separated real historical spot-checks, but that is 7 records against roughly 2,900 actual BIG_LOTTO draws in that span — classified `PARTIAL`, not `CONFIRMED`, coverage. The upstream `totalSize` field also returned three mutually inconsistent values (26, 899, 2,161) across those three queries that remain unexplained and are not relied on for any claim. Field semantics (physical ball-drop order vs. some other reveal/display convention) are circumstantially well-supported (consistent special-slot placement, genuine reordering at all three eras) but **not FAQ-confirmed** — the Packet's own caveat against over-claiming this is fully warranted and is preserved into the prerequisite design below.
DIRECT_M2_M3_PATH: Genuinely uncertain, and honestly exploratory rather than pre-committed to a single causal story — this is the correct and expected profile for a first look at a data channel with no prior work to build on. The most concrete mechanism hypothesis (a stable per-ball physical bias — manufacturing weight/wear asymmetry — producing a systematic early/late emergence tendency for a given number) is complicated by the fact that ball-*sets* (not individual balls) are selected fresh before each draw via a live ceremony, meaning any such bias could be set-conditional rather than a single stable per-number effect. This nuance must be established empirically, not assumed either way, before a confirmatory hypothesis is designed.
TRANSFER_POTENTIAL: If a genuine physical/hardware-linked bias exists, it is structurally the kind of property that does **not** era-drift the way a fitted statistical pattern does — closer in kind to why the (separately validated, already-landed) Constructor-Frontier portfolio-geometry result is durable: a property of physical objects or an algorithm, not a fitted trend. This is the strongest transfer-potential story of the three live candidates, conditioned on the coverage/semantics prerequisite actually clearing.
IMPLEMENTATION_COST: Low for the immediate next step (a bounded, scripted historical-coverage validation pass); medium for the conditional follow-on (schema v3 migration + backfill — the project's schema verification is exact-match/strict, so this is a deliberate migration, not a casual `ALTER TABLE`) if validation clears.

---

## 2. TOP_3_NEXT_DIRECTIONS

Ranked. Candidate A (jackpot/rollover) is excluded from this table per Section 0.1/1.0 — already executed and sealed, not an available option — shown above for transparency rather than silently dropped.

| Rank | Candidate | One-line verdict |
|---|---|---|
| 1 | D — Draw-order/position (`drawNumberAppear`) feasibility-first | Only candidate offering genuinely new raw information; data-readiness gap is real but bounded and tractable |
| 2 | B — EH27 (sparse subset-scan conditional edge gate) | Immediately executable, zero new data, sound blind-spot argument; inherits a 0-for-9 mechanism-shape base rate |
| 3 | C — Calendar/schedule context | Cheapest to build, but the deeper version of this question is already closed twice without a mechanism, and today's evidence sharpens the era-confound risk further |

---

## 3. NEXT_RESEARCH_DIRECTION

NEXT_RESEARCH_DIRECTION: **D — Verified draw-order/position (`drawNumberAppear`) feasibility validation, native to B649**

WHY_THIS_DIRECTION_NOW:
It is the only candidate that is a genuinely new information source rather than a new statistical lens on data this program has already exhausted with roughly nine null results in the "detect a regime, gate an existing candidate" shape — a count that grew by one again today (jackpot/rollover). All nine of those failures share a specific, now well-characterized signature: a real-looking effect beaten by a stale/shuffled/era-level control. Candidate D cannot yet be shown to share or escape that signature because it has never been tested — which is exactly the point: it is the last remaining place in this research program where a null result would still close real, previously-unexamined search space rather than reconfirm an already-well-established finding (the sorted-set draw content is very thoroughly characterized as indistinguishable from fair sampling; the *order* channel is not characterized at all). The Packet's own selection-criteria ordering places genuine novelty and transfer potential ahead of data readiness and cost, which is precisely the trade this candidate asks the Owner to make.

WHY_NOT_DIRECTION_2 (EH27):
Not wrong, and preserved below as the pre-registered fallback — but it is a new mechanism on the same information every prior single-ticket M2+ attempt has used, in the same "regime gate" shape that is now 0-for-9 on this exact population. Its methodological blind-spot argument (power against localized departures) is real and distinguishes it from a simple frequency/gap reframing, but it does not change what data is being looked at, only how.

WHY_NOT_DIRECTION_3 (calendar/schedule):
The narrow literal feature (weekday/month) was never coded, but the broader mechanism question it would actually be testing — is there a temporal/regime effect in B649 — has already been investigated from both an internal-cause and external-cause angle and closed both times without an explanation. Today's finding that B649's own weekday composition changed structurally at 2014 (a different, sharper boundary than the previously-known 2023 one) adds a second, independently-discovered calendar/era entanglement rather than reducing the risk. Pursuing this now would very likely re-surface an already-known, already-unexplained confound rather than find something new.

REQUIRED_PREREQUISITE:
A bounded, read-only historical-coverage-and-semantics validation of `drawNumberAppear` — NOT yet a schema migration or backfill. Specifically: (a) query the same official `Lotto649Result` endpoint the production adapter already calls, systematically across a stratified historical sample large enough to bound coverage with real precision (not 3 spot-points) — e.g. one query per calendar year 2007–2026, or a denser sample if the per-request cost is low — and confirm `drawNumberAppear` is present, non-degenerate (not silently identical to the sorted array), and internally consistent (same multiset as `drawNumberSize`, stable special-number slot) at each point; (b) make a best-effort, evidence-bounded semantic determination — check for any official field documentation, or a small number of targeted broadcast-archive cross-checks in the style already used successfully for ball-set-ID — without over-claiming "verified physical draw order" if that bound cannot be reached; (c) resolve the unexplained `totalSize` field inconsistency (26/899/2,161 across three prior queries) enough to trust or explicitly distrust API pagination/coverage semantics before treating any later gap as a true missing-data gap rather than a query artifact.

DISCOVERY_MODE: Two-phase, explicitly not conflated. Phase 1 (this prerequisite) is descriptive feasibility discovery only — no hypothesis test, no p-value, no predictor. Phase 2 (downstream Track B, contingent on Phase 1 clearing its bar) is a fully preregistered confirmatory single-ticket M2+ test carrying this program's now-standard placebo battery (shuffled-order placebo, stale/misaligned-order placebo) plus an explicit era-stratified control gate — the same discipline that correctly caught today's jackpot-rollover false lead, applied here from the start rather than retrofitted after a promising-looking result.

DATA_TO_USE: The existing canonical/sealed B649 draw history (`research_draw_bindings`, `EXCLUDE_DATE_LIKE`, 2,138 clean draws, 2007-03-09..2026-07-31 — this program's independently-reconfirmed-four-times pin) joined by `draw_number`/`period` to fresh, read-only queries of the official `Lotto649Result` API's `drawNumberAppear` field, the same production endpoint `taiwan_lottery_draw_provider.py` already calls for `drawNumberSize`. No Cohort V2 prospective outcomes; no production DB writes at the validation stage.

PRIMARY_SUCCESS_METRIC:
For this prerequisite specifically: `drawNumberAppear` coverage fraction against the 2,138-draw clean history, distributed across all four of this program's established ERA blocks (not concentrated in one, avoiding the ball-set-ID trap of a 2024-only floor). A reasonable bar to propose (for the Owner to confirm before execution, per this program's no-self-authorized-parameter convention): coverage clearing a large majority of the clean history with no ERA block left materially uncovered. For the downstream, contingent Track B test: one-ticket M2+ uplift versus a locked no-order-feature baseline, required to beat all three of a shuffled-order placebo, a stale/misaligned-order placebo, and an explicit era-stratified control — mirroring the exact gate structure that just correctly closed jackpot/rollover.

STOP_OR_PIVOT:
If the coverage validation finds `drawNumberAppear` concentrated in only one or two ERA blocks (structurally similar to ball-set-ID's 2024-only floor), or finds the field is frequently missing/degenerate outside the three already-checked spot-points, or the semantic question proves irreducibly unresolvable (no plausible basis beyond "an arbitrary API-internal convention") — STOP before any ingestion or Track B design, and fall back to `NEXT_TASK_ID` = the Candidate B pick (EH27) as the pre-registered pivot, following this program's established stop-then-pivot discipline ([[b649-track-d-post-metadata-prediction-frontier-reselection-r1]], [[b649-track-d-direction2-reselection-after-cross-lottery-lag-r1]]).

NEXT_TASK_TRACK: **TRACK_A** — this direction needs a small amount of causal metadata validated/acquired before any Track B hypothesis test is interpretable; Track B follows conditionally, not automatically.

NEXT_TASK_ID: `B649_TRACK_A_DRAW_ORDER_POSITION_COVERAGE_VALIDATION_R1`
(Fallback if this stops: `B649_TRACK_B_EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE_R1`)

---

## FINAL

```
TASK_ID: B649_TRACK_D_POST_EH01_EH10_EH02_SUCCESSOR_RESELECTION_R1
STATUS: COMPLETE — EXACTLY_ONE_DIRECTION_SELECTED
EH01_STATUS: NO_SIGNAL / DO_NOT_ADVANCE_EXACT_VARIANT
EH10_STATUS: NO_SIGNAL / DO_NOT_ADVANCE_EXACT_VARIANT
EH02_V1_STATUS: NO_SIGNAL / DO_NOT_ADVANCE_THIS_EXACT_VARIANT
TOP_3_NEXT_DIRECTIONS:
  1. D — Draw-order/position (drawNumberAppear) feasibility validation, native to B649
  2. B — EH27 sparse subset-scan conditional edge gate (best remaining unexecuted Frontier hypothesis)
  3. C — Calendar/schedule context (high era-proxy risk, sharpened by today's pre-2014 schedule-regime finding)
  [Reference, not ranked — already executed, sealed WEAK_SIGNAL/DO_NOT_ADVANCE today: A, pre-draw jackpot/rollover state]
NEXT_RESEARCH_DIRECTION: D — Verified draw-order/position (drawNumberAppear) feasibility validation
WHY_THIS_DIRECTION_NOW: only candidate offering genuinely new raw information rather than a new lens on a population that has now produced 9 same-shaped null results (most recently today's jackpot/rollover, which also newly closed Candidate A)
REQUIRED_PREREQUISITE: bounded read-only historical-coverage-and-semantics validation of drawNumberAppear against the official Lotto649Result API (stratified across all 4 ERA blocks, not 3 spot-points) before any ingestion or hypothesis test
NEXT_TASK_TRACK: TRACK_A
NEXT_TASK_ID: B649_TRACK_A_DRAW_ORDER_POSITION_COVERAGE_VALIDATION_R1
COHORT_V2_PROSPECTIVE_DATA_USED: NO
REPO_MUTATION: NONE
DB_MUTATION: NONE
```
