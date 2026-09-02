# B649 Track D — Information-Family-Guided Next Direction R1

TASK_ID: B649_TRACK_D_INFORMATION_FAMILY_GUIDED_NEXT_DIRECTION_R1
MODE: READ_ONLY_RESEARCH_DECISION
DATE: 2026-08-15
STATUS: COMPLETE — CONFIRMS_AND_RATIFIES_PRIOR_UNDISPATCHED_SELECTION

REPO_MUTATION: NONE
DB_MUTATION: NONE
B_EXPERIMENT_EXECUTED: NO
COHORT_V2_PROSPECTIVE_DATA_USED: NO

## Inputs read

- Family compression: `.task-data/B649_TRACK_B_INDEPENDENT_STRATEGY_FAMILY_SIGNAL_COMPRESSION_R1/report.md` (written 2026-08-15 11:31–11:34, **after** everything below).
- Frontier V2 hypothesis map: `B649_TRACK_D_FRONTIER_V2_COVERAGE_AND_SATURATION_R1.md` (2026-08-13).
- Latest Track D decision (newest of ~30 sibling docs by mtime and embedded date, prior to this task): `B649_TRACK_D_FRONTIER_V2_SUCCESSOR_AFTER_TRANSFER_FAILURE_R1.md` (2026-08-15 08:24, STATUS COMPLETE).
- Same-day inputs to that decision: `B649_TRACK_D_CROSS_EXPERIMENT_WEAK_SIGNAL_META_MINING_R1.md` (02:30); `[[biglotto-uniformity-audit-and-baseline-contamination]]`; `[[b649-track-b-static-consensus-alignment-mechanism-r1]]`; `[[b649-track-b-static-consensus-error-atlas-r1]]`; `[[b649-track-d-static-consensus-failure-mode-r1]]`.
- Live repo/branch/PR/`.task-data` check for an active T539 cross-lottery task (this session, via background search agents).

## T539 cross-lottery task check (packet-required)

**T539_CROSS_LOTTERY_TASK_STATUS: SELECTED_BUT_NOT_DISPATCHED — not ACTIVE.**

`B649_TRACK_D_FRONTIER_V2_SUCCESSOR_AFTER_TRANSFER_FAILURE_R1` (finished 08:24 today, three hours before the family-compression report existed) already ran essentially this same comparison and selected `NEXT_TASK_ID: B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1`. Verified live this session: no branch, worktree, or PR matches that task ID — it has not been picked up. Per the packet's instruction, this is **not duplicated** here; it is ratified below rather than re-issued under a new ID, since this task's independent comparison converges on the same answer via an additional (newer) line of evidence.

A separate, unrelated cross-lottery artifact exists and is flagged for awareness, not relied on: branch `codex/cross-lottery-phase0-h04-conditional-r1` (uncommitted, no PR, not cited by any later Track D document) ran a conditional-recency-probability test natively across all three lotteries and found `NO_ZONE_DISTINGUISHABLE_FROM_SIMULATED_NULL` everywhere. It tests one specific hypothesis (H04-conditional recency), not the broader fairness-battery/search-transfer question T539_R1 is scoped for, and its orphaned/uncommitted status means it should be reviewed, not assumed correct, by whoever executes T539_R1.

## Why family diversity changes nothing (the four converging results)

| # | Result | Source | Finding |
|---|---|---|---|
| 1 | Draw process itself is fair | `[[biglotto-uniformity-audit-and-baseline-contamination]]` | 8-test Holm-corrected battery: BIG_LOTTO indistinguishable from fair 6/49 (min p=0.24). No frequency/positional/temporal/carryover/pair structure. |
| 2 | Best single "new lens" tried finds nothing | EH04 (context-tree weighted forecaster) | `IID_minus_CTW = -0.000277684491` — no detectable temporal dependency, essentially zero. |
| 3 | Pooling many mechanisms is *worse* than random | Meta-mining, 2026-08-15 02:30 | 17 single-ticket series oracle = 73.00% M2+ vs a **93.82%** theoretical ceiling for 17 independent random tickets at the same K — real models are *more* mutually redundant than chance, not complementary. `CONDITIONAL_MODEL_SELECTION_POTENTIAL: LOW`. |
| 4 | **Independent-family compression finds the same wall** | Family compression, 2026-08-15 11:31 | 69 strategies → 57 empirically independent families (5 empirical views: output identity, ticket Jaccard, frequency correlation, M2+ overlap, era-rate vector). `TOP_UNIQUE_HIT_FAMILIES: NONE` — zero families hit any target no other family also hits. Top-2/3/5 family-diverse union = **identical** to plain standalone Top-K at every K tested (delta=+0, same_selection=YES). `FAMILY_DIVERSITY_ADDED_VALUE: NO`. |

Result 4 is not a new discovery so much as the same population-level emptiness (#1) showing up a fourth way — this time surviving an aggressive, empirically-driven de-duplication (not just "different strategy names," but genuinely distinct information sources by 5 independent similarity views) and still finding nothing extra to combine. The family-compression report's own scope statement agrees: *"NEXT: Provide family-level information to the next D-selected B experiment. Do not select the next hypothesis."* It was not designed to, and does not, override the standing direction — it removes the last plausible objection to it (`"maybe we just haven't diversified across strategies enough yet"`).

## Candidate comparison (packet-required: A/B/C x 5 dimensions)

| Dimension | A. NEW_INFORMATION_SOURCE (EH10/EH01/EH02, same B649 substrate) | B. CONDITIONAL_FAMILY_USE (pre-target context gating) | C. CROSS_LOTTERY (T539 fairness/transfer replication) |
|---|---|---|---|
| NEW_INFORMATION_GAIN | LOW — same draw sequence EH04 (sibling method) already showed carries ~0 temporal info vs IID | LOW — pre-target conditioning already tried 3 independent ways on this population (trailing-state, boundary-swap, meta-mining's 8-feature cluster test) | HIGH — first-ever variation of *population*, not feature/lens; genuinely untested question |
| TRANSFER_POTENTIAL | LOW — EH10/EH01 are rolling-window "state gates," structurally identical to `trailing_static_m2_rate_50`, which collapsed to a degenerate 300/0 HELDOUT split via era-proxying | LOW — meta-mining's `PRE_TARGET_CLUSTER_SIGNAL: NO`; effect sizes ≤0.26, several **sign-flip** between MEGA/BROAD windows — "the signature of noise, not signal" | N/A in the predictive sense — reframes as "does the null generalize," which is the actual open question |
| DATA_READINESS | HIGH (data exists) but target signal itself in doubt | HIGH (features/tooling exist) | HIGH — live-verified same day: `t539_wave1.sqlite3`, 5,930 rows, 2007-01-01→2026-08-01 |
| IMPLEMENTATION_COST | LOW–MEDIUM | LOW–MEDIUM (reuse existing feature sets) | LOW — reuses 7/8 of the existing uniformity battery unchanged, zero new dependencies, no fitting |
| FAILURE_INFORMATION_VALUE | LOW–MEDIUM — a 4th same-substrate null | LOW — a 4th replication of an already well-established null | HIGH — symmetric, decision-relevant regardless of outcome |

EH04 (already run, NO_SIGNAL) and EH10/EH01/EH02 (confirmed absent from the repo — `NOT_RUN`, genuinely proposed-but-not-built) were independently reconfirmed live this session. EH02 is not in Frontier V2's own `CHEAP_EXTERNAL_CANDIDATES_VISIBLE` set (only EH10/EH04/EH01/EH15/EH18 are); it ranks below EH01 on cost per the prior comparison and adds nothing to Direction A's verdict.

## TOP_3_NEXT_DIRECTIONS

1. **CROSS_LOTTERY_UNIFORMITY_AND_SEARCH-TRANSFER_REPLICATION — T539 first.** Selected. Ratifies existing `NEXT_TASK_ID: B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1`.
2. **EH10_PERMUTATION_ENTROPY_ORDINAL_STATE_GATE.** Cheapest same-substrate fallback (Direction A) if the Owner prefers to stay single-lottery; no structural reason to expect success where sibling method EH04 already found ~0 signal, and its rolling-window shape inherits the freshly-demonstrated era-proxy failure mode.
3. **Era-gated (not feature-gated) conditional check.** The one narrower, cheaper Direction-B variant not yet directly falsified: meta-mining's own `TOP_3_NEW_RESEARCH_HYPOTHESES` #3 — test whether *any* candidate's rescue rate, conditioned only on calendar era (the one reproducible split found across every audit so far), clears the random floor under a pre-registered, multiplicity-corrected test. Still ranked below #1 on new-information-gain.

## NEXT_RESEARCH_DIRECTION

CROSS_LOTTERY_UNIFORMITY_AND_SEARCH-TRANSFER_REPLICATION — T539 first.

## WHY_THIS_DIRECTION_NOW

Four independent lines of evidence — draw-level fairness, best-tried single new lens (EH04), cross-mechanism pooled redundancy, and now family-compressed redundancy — all land on the same conclusion: the B649 draw substrate, however it is sliced, recombined, or de-duplicated, has no additional independent signal left to extract by varying the feature/mechanism lens. The only untested axis left that could distinguish "B649 is fundamentally unpredictable" from "flexible search always looks like this on finite fair-random history, regardless of lottery" is the *population* itself. That test is cheap (reuses an existing zero-dependency methodology), data-ready (verified live the same day), and informative symmetrically — a null result on T539 raises the prior that this is a general property worth an Owner-level pivot; a real departure on T539 tells us B649's failure is not universal, which is equally decision-relevant.

## HOW_57_FAMILY_MAP_CHANGES_THE_PLAN

It does not change the plan; it removes the last standing objection to it. Before this report, one could still argue "the within-B649 searches failed because they kept re-testing near-duplicate strategies, not because the substrate is empty." The family compression closes that gap: even after collapsing 69 IDs to 57 *empirically independent* families (5 similarity views, not naming/provenance), diverse family selection is bit-for-bit identical to plain top-performer selection at K=2/3/5, and zero families contribute a unique hit no other family also reaches. Family-level analysis was the most promising remaining "maybe we combined things wrong" hypothesis for staying within B649, and it returned the same answer as everything else. This is why Direction C now dominates Directions A and B more clearly than it did three hours ago, at the prior Track D task.

## NEW_INFORMATION_SOURCE

T539's own draw history — a structurally different population (5-of-39, ~5,930 draws, near-daily, 2007–2026, single zone, no special number) never tested for basic distributional fairness or whether development-period search signal survives chronological holdout. Data readiness carried forward from the prior task's same-day live verification, not independently re-verified in this read-only session.

## DISCOVERY_MODE

YES — read-only statistical diagnostic. Fixed binomial/permutation tests with Holm correction, no free parameters, no fitting, no tuning; reuses 7 of B649's existing 8-test uniformity battery unchanged (main-ball frequency, era homogeneity, carryover-vs-hypergeometric, positional order statistics, sum mean, per-number Holm scan, pair-scan Holm correction). The 8th test (special-ball frequency) does not apply to T539's single-zone structure.

## DATA_TO_USE

T539 `source_draws` (5,930 rows, `t539_wave1.sqlite3`, `T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), under `.runs/MathStatisticalAnalysis/`, outside git, read-only. Not Cohort V2 data; unrelated to B649's own prospective line. P638 (`p638_wave1.sqlite3`, 1,933 rows) is confirmed ready and queued as the immediate second replication once T539's verdict lands — not touched by this task or its immediate successor.

## PRIMARY_SUCCESS_METRIC

A single population-level verdict for T539 alone: `DEPARTS_FROM_FAIR_RANDOM` (Holm-corrected battery min-p < 0.05) vs. `NO_DETECTABLE_DEPARTURE` — not "beats consensus." A ticket-level M2+-vs-baseline metric only becomes relevant if a separately authorized Stage-2 follow-on is opened because T539 shows real departure.

## STOP_OR_PIVOT

- T539 shows no detectable departure (matches B649's 0.24) → dispatch the identical diagnostic to P638 next (zone-1 6-of-38 only, per the `[[pr128-strategy-matrix-p638-diversification-merged]]` scoping precedent) before any Owner-level conclusion.
- Both T539 and P638 show no detectable departure → recommend an Owner-level pivot away from further within-lottery temporal/information-theoretic feature-hunting (any EH-series hypothesis, any of the three lotteries) toward either reframing around E[payout|win] (blocked today — per-draw per-tier winner-count data confirmed absent from the repo) or halting active search on this axis pending new data. This session's family-compression result adds a fourth reason this pivot would be well-supported, not merely a repeat of the same three.
- T539 shows a real, Holm-surviving departure → B649's failure is not a universal lottery property; open a new, separately scoped task to characterize T539's departure. Do not backport the finding to B649 or forward-assume it onto P638.
- A fair-random verdict on T539 does not by itself prove EH10/EH01 must fail on B649 — it only removes the presumption that more B649-internal feature/family variants is the highest-value next step.

## NEXT_TASK_TRACK

TRACK_D (read-only diagnostic, no tuning, no B experiment)

## NEXT_TASK_ID

B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1 — pre-existing ID assigned by `B649_TRACK_D_FRONTIER_V2_SUCCESSOR_AFTER_TRANSFER_FAILURE_R1`; ratified, not reissued.

---

FINAL:

TASK_ID:
B649_TRACK_D_INFORMATION_FAMILY_GUIDED_NEXT_DIRECTION_R1

STATUS:
COMPLETE — CONFIRMS_AND_RATIFIES_PRIOR_UNDISPATCHED_SELECTION

INDEPENDENT_INFORMATION_FAMILIES:
57

FAMILY_DIVERSITY_ADDED_VALUE:
NO

TOP_3_NEXT_DIRECTIONS:
1. CROSS_LOTTERY_UNIFORMITY_AND_SEARCH-TRANSFER_REPLICATION — T539 first (selected)
2. EH10_PERMUTATION_ENTROPY_ORDINAL_STATE_GATE (cheapest same-substrate fallback, low expected value)
3. Era-gated (not feature-gated) conditional rescue-rate check (narrowest surviving Direction-B variant, still low priority)

NEXT_RESEARCH_DIRECTION:
CROSS_LOTTERY_UNIFORMITY_AND_SEARCH-TRANSFER_REPLICATION — T539 first

WHY_THIS_DIRECTION_NOW:
Four independent lines of evidence (draw-level fairness battery, EH04's near-zero temporal information delta, meta-mining's cross-mechanism redundancy finding, and this task's family-compression confirmation) all converge on one root cause: the B649 substrate carries no extractable independent signal regardless of how it is sliced or recombined. Only a population change, not another feature lens, can now distinguish "B649-specific defect" from "expected property of flexible search on any fair-random lottery," and that test is cheap, data-ready, and symmetric in value.

HOW_57_FAMILY_MAP_CHANGES_THE_PLAN:
It does not change the direction; it removes the last open objection to it. Even after empirically compressing 69 strategies to 57 independent families (5 similarity views), family-diverse Top-K selection is identical to plain Top-K at K=2/3/5 (delta=+0) and zero families contribute a unique hit no other family reaches — closing off "we just haven't diversified enough within B649" as a live alternative to Direction C.

NEW_INFORMATION_SOURCE:
T539's own draw history (5-of-39, ~5,930 draws, 2007–2026) — a structurally different population never tested for basic fairness or development-to-holdout search-transfer, verified data-ready live by the prior same-day task.

DISCOVERY_MODE:
YES — read-only statistical diagnostic, zero free parameters, reuses 7/8 of B649's existing uniformity battery.

DATA_TO_USE:
T539 `source_draws` (5,930 rows) in `t539_wave1.sqlite3` (`T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), outside git, read-only; P638 queued second, not touched.

PRIMARY_SUCCESS_METRIC:
Single population verdict for T539 alone — DEPARTS_FROM_FAIR_RANDOM (Holm-corrected min-p < 0.05) vs. NO_DETECTABLE_DEPARTURE — not a ticket-level "beats consensus" metric.

STOP_OR_PIVOT:
No departure on T539 → run P638 next (zone-1 only). No departure on both → recommend Owner-level pivot away from within-lottery feature-hunting toward E[payout|win] (currently data-blocked) or a search halt on this axis. Real departure on T539 → B649's failure is not universal; open a separately scoped characterization task; do not backport to B649 or pre-assume onto P638.

NEXT_TASK_TRACK:
TRACK_D

NEXT_TASK_ID:
B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1

COHORT_V2_PROSPECTIVE_DATA_USED:
NO

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

END
