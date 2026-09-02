# B649 Track D — Post Structured-Set Successor Reselection R1

TASK_ID: B649_TRACK_D_POST_STRUCTURED_SET_SUCCESSOR_RESELECTION_R1
MODE: READ_ONLY_RESEARCH_DECISION
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-16 (this pass)

## RECONCILIATION WITH A PRIOR SAME-DAY RUN — read this first

This exact TASK_ID, with the same LATEST_B_RESULT trigger and the same output
path, was **already completed once today** (file mtime ~11:59, originSessionId
`daea898b…`), before this pass started. That run is not discarded — it did
real, careful work — but this pass independently re-derived the answer from
the repository rather than re-stating it, per standard "verify before
trusting a same-day claim" discipline, and it found two things the prior run
did not have:

1. **A resolution to a bookkeeping inconsistency the prior run flagged but
   left open.** It correctly noted a conflict between "the EH collision audit
   logs zero EH executions" and "another memory describes EH04 as already run
   and already showing overfitting." This pass traced it: EH04 genuinely was
   executed, on **2026-08-14**, one day *after* the collision audit's
   Aug-13 snapshot — `.task-data/B649_TRACK_B_EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER_DISCOVERY_R1/report.md`
   exists, dated Aug 14 20:44: `DECISION: DO_NOT_ADVANCE`,
   `RESEARCH_CLASSIFICATION: NO_SIGNAL`, `DEVELOPMENT_OVERFIT_SIGNAL: YES`
   (selected inner-ticket M2+ delta +0.000694 vs. observed outer-ticket delta
   **-0.035294** — the same search-then-reverse signature every other tuned
   Track B mechanism has shown). Not a naming collision with the *unrelated*
   internal `H04` (ridge-logistic per-number producer) — the audit snapshot
   was simply stale by the time the reselection doc cited it as current. This
   also means the "45/49 frontier items unexecuted" figure the prior run
   quoted is stale: by Aug 14, the internal Top-10 wave had executed 9/10
   items (`ORIGINAL_TOP10_EXECUTED_COUNT: 9`, confirmed in
   `.task-data/B649_TRACK_B_H06_DPP_SUBMODULAR_PORTFOLIO_SELECTION_LEVEL1_R1/report.md`)
   plus external EH04 — the qualitative conclusion (far from saturated) still
   holds, the exact count does not.
2. **A real, un-weighed gap:** the recovered execution reconciliation leaves
   12 internal hypotheses open — H11, H13, H15, H16, H18, H20, H22, H23,
   H24, H25, H26, H28. The underlying novelty audit
   (`B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1.md`) classifies 11 of these as
   `HIGH_CONFIDENCE_NOT_TRIED`; H15 is only `LIKELY_NOT_TRIED` because some
   historical optimizer source bodies were unavailable. The prior run's
   TOP_3 never names or weighs any of them, only EH01/EH02/EH10 and
   "remaining Direction-A." That is a real, not cosmetic, omission — see
   Direction 3 below.
3. **A candidate axis outside the "Frontier V2" catalog entirely,** which
   this pass believes is the strongest available option and did not appear in
   the prior run's TOP_3 at all — see Direction 1. The prior run's own
   grounding pass explicitly searched the Track D/B memory chain plus the
   sibling `~/VibeCoding-WorkSpace/*FRONTIER_V2*`/`*EXTERNAL*` files; it did
   not cross into this repository's own git history, which is where Direction
   1's evidence lives. Confirmed by direct grep: none of the Frontier V2
   catalog files (coverage/saturation doc, spec registry, external
   fast-falsification specs) mention Sidon, arm B/C, min-overlap, or
   `matrix-native-results` anywhere — these are two genuinely
   un-cross-referenced "frontier" threads in this program, not duplicates of
   each other.

This pass's own final selection **diverges from the prior run's** (which
picked EH01+EH10). The reasoning is below; the prior run's own analysis of
EH01/EH02/EH10/Direction-A is sound on its own terms and is carried forward
rather than redone, since nothing found here invalidates it — it is simply,
in this pass's judgment, not the strongest available option once the
constructor-frontier evidence is weighed in.

## LATEST_B_RESULT (as given)

STRUCTURED_SET_M2+ = 18.00% | STATIC_CONSENSUS = 22.33% | DELTA = -4.33pp |
POSITIVE_BLOCKS = 1/6 | PLACEBO = 20.33% → DECISION = DO_NOT_ADVANCE. The
**sixth** consecutive Track B mechanism (complementarity stack, residual
rerank, static-consensus alignment, cross-lottery lag, EH04 context-tree,
structured-set-interaction) to show the identical signature: something looks
marginally favorable, a placebo or majority-blocks check kills it.

## STANDING EVIDENCE (condensed; full citations in the prior run's own text, not repeated)

- Draw-content substrate is **statistically indistinguishable from fair
  sampling** at marginal (Holm min p=0.24), pairwise, triple-, and
  quadruple-wise joint level, across all three lotteries
  (`biglotto-uniformity-audit-and-baseline-contamination`,
  `track-d-cross-lottery-higher-order-synthesis-r1`).
- Existing-family combination headroom is **LOW**, corrected gap negative in
  all 6 fair-exposure groups (`b649-track-b-family-headroom-discovery-r1`).
- Consensus reranking/gating, complementarity stack, residual rerank,
  cross-lottery lag, EH04 context-tree, and structured-set-interaction have
  **all** failed the same way: promising on a slice, reversed or
  placebo-beaten on the full 300-target heldout.
- **Every** predictive-signal attempt in this program's history that this
  pass could find — across draw-history statistics, cross-lottery temporal
  structure, and set-interaction modeling — has ended `DO_NOT_ADVANCE` or
  `NO_SIGNAL`. Zero confirmed wins.
- Separately, and NOT weighed by any prior Track D reselection: the
  **ticket-portfolio-construction / "constructor frontier" line** (Strategy
  Matrix Phase 5, PR #128/#130/#131/#132/#134/#136) has a **confirmed,
  replicated, non-overfitting positive result** — see Direction 1.
- The shared 300-target development window (113000006–115000069) is
  confirmed **COMMON_DEVELOPMENT_BENCHMARK** per current Owner policy — reused
  6 times by draw-content experiments; NOT a clean holdout; real confirmation
  is deferred to genuinely new future targets.

---

## TOP_3_NEXT_DIRECTIONS

### 1. Constructor-Frontier Low-Overlap Geometry Mechanism Study ("Option B") — SELECTED

- TITLE: Explain why the greedy min-overlap ticket constructor ("arm B") beats
  both Sidon-shift and random coverage, and whether the mechanism can be
  sharpened into a stronger constructor
- TYPE: New strategy-generation mechanism (task category 2) — a genuinely
  orthogonal "frontier" thread (category 5), distinct from the EH/H "Frontier
  V2" catalog Direction 2 draws from
- NEW_INFORMATION_SOURCE: Not new information about draw content at all —
  a different lever: multi-ticket portfolio-allocation geometry. Directly
  verified in `docs/research/matrix-native-results/strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-report.md`
  (read in full this pass): a deterministic, algebra-free greedy
  min-overlap rule beats **both** matched-random coverage (Q1) **and** each
  lottery's own sealed Sidon-shift geometry (Q2) at **every tested k>1, in
  all three native lottery structures** (BIG_LOTTO, DAILY_539,
  POWER_LOTTO_zone1) — exact combinatorial arithmetic (`fractions.Fraction`),
  not sampled, re-derived independently in a unit test from the three raw
  source files. Headline: at k=20, POWER_LOTTO_zone1 Q_arm_b=0.61074 vs.
  Q_sidon=0.60548 vs. Q_random=0.54585. The *relative* gain-over-Sidon ratio
  peaks at k=5 in **all three** lotteries, a previously-unstated finding this
  synthesis itself surfaced.
- WHY_IT_COULD_IMPROVE_M2_M3: This is the **only** candidate in the program's
  entire history with a confirmed positive effect already banked, not a bet.
  The primary event tested is literally `M3_PLUS` (m=3) in this cell's own
  terminology — a k-ticket-portfolio "at least one ticket hits" metric,
  which this repository already treats as a legitimate M-plus construct
  elsewhere (`b649-r2-all-prefix-ticket-efficiency-review`'s 5/10/15/20-ticket
  bands; the H06/H14 DPP task's `M3_PLUS_AT_LEAST_ONE_TICKET`). Understanding
  *why* arm B wins is the cheapest lever to try to extend the gain further:
  the source synthesis already half-explains it (a proven
  `Q_greedy(m,k)=Q_sidon(m,k)` identity for m≥4 from `max_pairwise_overlap≤1`
  and `2m-1>draw_size`) and explicitly recommends this exact mechanism study
  over a second heavy bounded-optimizer campaign (§10 of the report:
  `RECOMMENDATION: B`, `EXECUTED: NO`).
  **Honest limitation, stated plainly:** this is a portfolio/multi-ticket
  metric, not the single-ticket `ONE_TICKET_M2_PLUS` metric the immediately
  preceding Track B chain (structured-set, EH04, cross-lottery-lag) used as
  `PRIMARY_SUCCESS_METRIC`. It cannot move that specific number — a
  single-ticket play has no overlap to minimize. See Direction 2 if the Owner
  wants the single-ticket lineage specifically.
- OVERLAP_WITH_PRIOR_FAILED_LINES: **None** of the six "reduce" categories
  apply. It is not a consensus transform, not a set-interaction *predictive*
  model, not a portfolio *selector* (it doesn't choose which numbers — it
  chooses how to spread a fixed pool across tickets), not a recombination of
  the 57 existing strategy families, not a lag/window/state variant, not a
  frequency/gap/deviation tweak. It makes **zero claim about draw
  non-uniformity** — the one property this program has spent 15+ tasks
  repeatedly, robustly disproving.
- TRANSFER_POTENTIAL: **High, structurally.** The result is a property of the
  allocation algorithm against a uniform draw measure (a combinatorial fact,
  bounded but not exhaustive — `GLOBAL_OPTIMUM_STATUS: UNKNOWN`), not a fitted
  statistical pattern — it cannot "drift" the way every era-conditional
  predictive artifact in this program has. It has already passed a
  replication test no other candidate here has attempted: independent
  agreement across 3 lotteries with different (pool, draw-size) parameters,
  not tuned per-lottery.
- DATA_READINESS: **High.** Fully executed and sealed on both local `main`
  and `origin/main` (PR #134, #136 — independently confirmed byte-identical
  by the synthesis task itself, §7 of its own report). The next step
  ("Option B") is already named, scoped, and reasoned in the same commit
  that closed out Phase 5's data-gathering (`4df1034`/`f21dcd5`), explicitly
  **not yet authorized or started**. `origin/main` also already carries an
  unrelated but likely-relevant "portfolio replay session" tool (PR #135,
  `586b76d`), not yet pulled into local `main`.
- IMPLEMENTATION_COST: **Low–medium.** Analysis of already-sealed exact
  JSON geometry fields (`overlap_profile`, `max_pairwise_overlap` per k),
  not a new experimental harness, no new data acquisition, no new
  combinatorial enumeration required to start.

### 2. Ordinal/Temporal-Pattern Fast-Falsification Pair — EH01 + EH10 (prior run's pick; still valid, ranked below Direction 1)

- TITLE: Execute the already-specified, never-run EH01 (matrix-profile
  motif/discord) + EH10 (permutation-entropy ordinal state) pair against
  B649's own draw history
- TYPE: Different predictive target/objective (category 3) — sequence/order
  structure, as opposed to the set-membership structure every marginal/
  pairwise/triple/quadruple/legal-set test so far has targeted
- NEW_INFORMATION_SOURCE: Genuinely untested statistical lens — confirmed
  this pass still `NOT_RUN` (unlike EH04, no `.task-data` execution directory
  exists for EH01 or EH10 under any name this pass could find).
- WHY_IT_COULD_IMPROVE_M2_M3: If draws carry any sequential/temporal
  dependency, an ordinal/motif state-gate re-weights number scores directly —
  same reasoning as the prior run's own writeup, which this pass finds sound.
- OVERLAP_WITH_PRIOR_FAILED_LINES: Low-moderate — methodologically novel, but
  it is still another "look for hidden structure in the same draw-history
  substrate" bet, on a substrate independently confirmed fair at every
  set-level order tried so far. The base rate this program has established
  for that class of bet is, as of this pass, 0 confirmed wins across roughly
  15 attempts (marginal, positional, pairwise, triple, quadruple, consensus
  variants ×3, complementarity, residual rerank, cross-lottery lag, EH04,
  structured-set). Ordinal/temporal structure was never directly tested, so
  it is not a rerun — but it inherits the same substrate's prior.
- TRANSFER_POTENTIAL: Unknown — no prior attempt to calibrate against.
- DATA_READINESS: High — full spec since 2026-08-13, ranked #1/#3 in that
  catalog's own priority queue, needs only already-available draw history.
- IMPLEMENTATION_COST: Low, per the spec's own cost rating.
- **If selected instead of Direction 1:** re-verify current
  `LOCAL_VALIDATION_STATUS` for EH01/EH10 specifically before starting (the
  EH04 case above shows this program's own bookkeeping lags real executions
  by at least a day), and this would be the **7th** reuse of the
  113000006–115000069 window — report it as such.

### 3. Bounded Due-Diligence Audit of the 12 Still-Open Internal Hypotheses (gap-closing, not a bet)

- TITLE: Before locking in any further single-ticket predictive bet, spend a
  cheap pass ranking H11, H13, H15, H16, H18, H20, H22, H23, H24, H25, H26,
  H28 (11 `HIGH_CONFIDENCE_NOT_TRIED`; H15 `LIKELY_NOT_TRIED`, per
  `B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1.md`) by the same six criteria used
  here, since none of them were weighed by name in the prior run
- TYPE: Meta/triage step spanning categories 1–3 (each H-item targets a
  different information source or mechanism; not individually evaluated in
  this pass)
- NEW_INFORMATION_SOURCE: Unknown per item — that is exactly the gap this
  closes. These sit in the same internal catalog that produced the
  already-executed H01/H03/H04/H05/H06(H14)/H07/H08/H09/H10, so they are, in
  principle, comparably "cheap and ready" — but this pass did not open their
  individual specs, and neither, apparently, did the prior run.
- WHY_IT_COULD_IMPROVE_M2_M3: Unknown without opening each spec — the value
  here is making sure a stronger single-ticket candidate than EH01/EH10 isn't
  being silently skipped the same way EH01/EH02/EH10 themselves were skipped
  for several reselection rounds before today.
- OVERLAP_WITH_PRIOR_FAILED_LINES: Unknown per item — plausible some of the
  12 are trivial variants of already-failed lines (would need the same
  "reduce" filter applied one by one).
- TRANSFER_POTENTIAL: Unknown.
- DATA_READINESS: Medium — specs likely exist in the same catalog structure
  as H01-H10's, not independently confirmed complete for all 12 this pass.
- IMPLEMENTATION_COST: Low for the triage/ranking step itself; unknown for
  whatever gets selected afterward.

**Considered and ranked below these three, not re-derived:** EH02
(cross-lottery transfer-entropy) and the remaining Direction-A
externals (calendar, market-state, draw-order, equipment) — the prior run's
own reasoning for ranking these lower (EH02: real topical overlap with the
already-failed lagged-context result; Direction-A: each already closed or
structurally foreclosed with citations) still holds; nothing found this pass
changes either conclusion.

---

## DECISION

**NEXT_RESEARCH_DIRECTION:** Direction 1 — the constructor-frontier
low-overlap geometry mechanism study ("Option B": explain, and attempt to
sharpen, why arm B beats both Sidon-shift and random coverage across
B649/T539/P638-zone1).

**WHY_THIS_DIRECTION_NOW:** Weighed against the required priorities in
order — NEW_INFORMATION_GAIN (a different lever entirely, not one more
statistical lens on an exhaustively-audited-fair substrate);
DIRECT_PATH_TO_M2_M3 (direct and already-proven for the portfolio/multi-ticket
`M3_PLUS`-at-k construct this repo already uses elsewhere, though not for the
single-ticket construct — stated plainly above, not hidden);
CHRONOLOGICAL_TRANSFER_POTENTIAL (structurally robust — a combinatorial
property of an algorithm against a uniform measure, not a fitted pattern
subject to era drift, which is the exact failure mode that has sunk every one
of the ~15 predictive-signal attempts this program has tried);
FAILURE_INFORMATION_VALUE (this is not a null-hunting exercise — it extends
an already-confirmed win); DATA_READINESS (fully sealed, next step already
scoped by its own source report); IMPLEMENTATION_COST (low-medium, reusing
sealed artifacts) — this is the strongest candidate available across the
program's full current evidence, not chosen for having an unfamiliar model
name (per the task's own instruction not to do that — if anything, this is
the *opposite* of novelty-chasing: it is "keep going where something already
worked," against a queue of fifteen "try a new-sounding lens" attempts that
have all failed the same way).

This does mean stepping outside the Track D/B lineage's own established frame
(single-ticket draw-content prediction) into the parallel Strategy Matrix
constructor-frontier lineage. That is a genuine, disclosed judgment call: the
task's own CORE_GOAL asks for the direction most likely to raise B649
M2+/M3+ "from all current research evidence," not "from Track D/B's own
prior candidate list," and explicitly names "new strategy-generation
mechanism" as an encouraged category. Direction 2 (EH01+EH10) remains a fully
valid, ready choice if the Owner wants to keep the single-ticket lineage
moving specifically, or in parallel.

**DISCOVERY_MODE:** Mechanism/explanatory analysis of already-sealed
exact-combinatorial results — not a new statistical hypothesis test, no new
data pull, no parameter search to start. Extend the already-proven m≥4
disjointness identity (`max_pairwise_overlap≤1` and `2m-1>draw_size`) to
explain the m=3 (`M3_PLUS`) `k=5` relative-gain-over-Sidon peak common to all
three lotteries (a previously-unstated finding surfaced by the synthesis
itself, unexplained). If a structural explanation is found, test whether it
suggests a sharper constructor than plain lexicographic-greedy — motivated
by arm C's own B649 result already showing a materially larger bounded-search
gap exists at k≥10, which this candidate does not need to re-run to make
progress on.

**DATA_TO_USE:** The three already-sealed result cells
(`docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-*`,
`greedy-min-overlap-constructor-t539-v1-*`,
`greedy-min-overlap-constructor-p638-zone1-v1-*`) and their exact JSON
geometry fields. No new draw-history pull. No Cohort V2 prospective outcomes.
The already-origin/main "portfolio replay session" tool (PR #135, `586b76d`,
not yet in local `main`) may become useful once/if mechanism understanding
turns into a candidate constructor change — pull it in at that stage, not
before.

**COMMON_DEVELOPMENT_BENCHMARK:** Not used by this direction at all. This
candidate performs no query against B649/T539/P638 draw history or the
113000006–115000069 window, so it neither adds a 7th reuse nor needs the
window's clean-holdout→development-benchmark relabeling to apply to it. (The
relabeling itself is correctly noted and binding on every *other* candidate
in this document, including Direction 2 if chosen instead.)

**FUTURE_CONFIRMATION_PLAN:** This candidate's core claims (Q1/Q2/Q3, the
geometry invariants) are exact combinatorial statements, not sampled
statistics — they do not need a forward holdout to be "confirmed" as stated,
and are not at risk of the placebo-beats-real pattern that has sunk every
predictive candidate. What does need forward/operational confirmation later
is whether routing the operational forward-loop's ticket construction through
the arm-B (or a mechanism-sharpened successor) constructor measurably raises
realized multi-ticket hit rates over enough real future draws — that
validation step belongs in the existing `B649_MULTI_STRATEGY_FORWARD_
OPERATION_R1` shadow-forward-runner infrastructure once enough live draws
accumulate, honoring the same "true confirmation from new real targets"
principle this task's own data policy states for every other candidate.

**PRIMARY_SUCCESS_METRIC:** Q(k) — probability that at least one ticket in a
k-ticket portfolio achieves the primary tested event (m=3, `M3_PLUS`/
`ZONE1_M3_PLUS` in this repo's own cell terminology), for a fixed candidate
pool, measured as gain of the arm-B constructor over both Sidon-shift and
matched-random allocation at fixed k. **Explicitly not** the single-ticket
`ONE_TICKET_M2_PLUS` metric the immediately-preceding Track B chain used.
[Confirmed] The three source reports and raw result schemas expose `m=3` as
the primary event and only `m>=4` secondary lanes; no `m=2` lane is reported.
Therefore the banked result is direct evidence for portfolio M3+, not M2+.

**STOP_OR_PIVOT:** Not a null-triggered stop condition — this direction
starts from an already-banked, replicated positive result, unlike every
other candidate in this document. Pivot condition: if the mechanism study
finds arm B's win is a non-generalizable artifact of this specific
lexicographic tie-break rule with no structural explanation and no way to
sharpen it further, that is still a complete, useful outcome — stop
mechanism-hunting there and route straight to applying the existing
validated constructor operationally, rather than continuing to search for an
explanation. If the Owner instead prioritizes the single-ticket predictive
lineage, Direction 2 (EH01+EH10, `NEXT_TASK_ID
B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_FALSIFICATION_R1`, already fully
specified by the prior same-day run) is the ready fallback — re-verify its
`LOCAL_VALIDATION_STATUS` first per the EH04 lesson above.

**NEXT_TASK_TRACK:** Strategy Matrix — Phase 5 constructor-frontier
mechanism lineage (explicitly *not* Track D or Track B; those remain
available in parallel via Direction 2 if the Owner wants them).

**NEXT_TASK_ID:** STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_STUDY_R1

---

## FINAL

TASK_ID: B649_TRACK_D_POST_STRUCTURED_SET_SUCCESSOR_RESELECTION_R1
STATUS: COMPLETE — EXACTLY_ONE_SUCCESSOR_SELECTED

CONTINUATION: RESUMED_LATEST_REANALYSIS

EXISTING_REPORT_FOUND: YES

EXISTING_REPORT_VERSION: LATEST_REANALYSIS_VERSION

OLD_SELECTION: EH01 + EH10 ordinal/temporal fast-falsification pair

NEW_EVIDENCE_MATERIALLY_CHANGES_SELECTION: YES

PREVIOUS_DIRECTION: EH01 matrix-profile motif/discord + EH10 permutation-entropy ordinal-state falsification

SUPERSEDED_BY: Constructor-Frontier Low-Overlap Geometry Mechanism Study (Option B)

WHY: Frontier V2 remains unsaturated and EH01/EH10 remain genuinely unexecuted, but they are still a new lens on the repeatedly null draw-history substrate. The separately-developed constructor frontier supplies a fixed-budget, exact-combinatorial M3+ coverage gain already reproduced across BIG_LOTTO, DAILY_539, and POWER_LOTTO Zone-1. That direct, chronological-drift-free path outweighs another same-substrate predictive bet. This selection does not use payout/EV and does not treat portfolio diversity itself as sufficient evidence.

UNEXECUTED_INTERNAL_HYPOTHESES_CONFIRMED: 12 still-open items recovered — H11, H13, H15, H16, H18, H20, H22, H23, H24, H25, H26, H28. Evidence strength: 11 HIGH_CONFIDENCE_NOT_TRIED; H15 LIKELY_NOT_TRIED.

CONSTRUCTOR_FRONTIER_RELATIONSHIP: INDEPENDENT

EH04_BOOKKEEPING_DISCREPANCY: RESOLVED

TOP_3_NEXT_DIRECTIONS:

1. Constructor-Frontier Low-Overlap Geometry Mechanism Study (Option B) — SELECTED
2. EH01 + EH10 ordinal/temporal fast falsification — valid single-ticket fallback
3. Bounded due-diligence audit of the 12 still-open internal hypotheses — gap-closing, not yet a direct bet

NEXT_RESEARCH_DIRECTION: Constructor-Frontier Low-Overlap Geometry Mechanism Study — explain and attempt to sharpen why arm B (greedy min-overlap) beats Sidon-shift and matched-random coverage across B649/T539/P638-zone1.

WHY_THIS_DIRECTION_NOW: It is the only top-three option whose load-bearing M3+ effect is already exact, positive, and cross-lottery replicated. It uses no draw-history pattern, so it has chronological transfer potential and avoids the search-then-reverse failure signature of the Track B predictive line. The next mechanism question is already scoped and can be studied from sealed artifacts at low-medium cost. The proven scope is fixed-k multi-ticket M3+ coverage only — not single-ticket M2+, predictive advantage on real draws, profitability, prize value, or global constructor optimality.

WHY_NOT_DIRECTION_2: EH01/EH10 are novel and ready, but remain an unvalidated bet on the same draw-history substrate that has produced zero confirmed predictive wins; they would also reuse the common 300-target development benchmark again. Their failure information value is good, but their direct success prior is lower than the constructor direction's already-banked exact M3+ gain.

WHY_NOT_DIRECTION_3: The 12-item audit closes a real omission, but it is a triage step rather than a direct M2+/M3+ mechanism. Per-item orthogonality, readiness, and predictive path remain unresolved, and H15 is only LIKELY_NOT_TRIED. It does not outrank a low-cost mechanism study grounded in an already-replicated exact M3+ result.

CORE_EMPIRICAL_CLAIM_VERIFICATION: PASS — the focused synthesis test independently re-derived all headline fractions from the three sealed source JSON files; 10 tests passed. The evidence type is EXACT_COMBINATORIAL, not realized-draw predictive evidence.

NEXT_TASK_TRACK: Strategy Matrix — Phase 5 constructor-frontier mechanism lineage (not Track D/B)

NEXT_TASK_ID: STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_STUDY_R1

COHORT_V2_PROSPECTIVE_DATA_USED: NO

REPO_MUTATION: NONE

DB_MUTATION: NONE

OUTPUT: B649_TRACK_D_POST_STRUCTURED_SET_SUCCESSOR_RESELECTION_R1.md

BLOCKERS: NONE

END
