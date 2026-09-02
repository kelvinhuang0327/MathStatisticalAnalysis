# B649 Track D — Frontier V2 Successor After Transfer Failure R1

TASK_ID: B649_TRACK_D_FRONTIER_V2_SUCCESSOR_AFTER_TRANSFER_FAILURE_R1
MODE: READ_ONLY_RESEARCH_DIRECTION_DECISION
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-15
STATUS: COMPLETE
CONTINUATION: Drafted and finalized in one continuous session (no separate crashed agent's
scratch state to recover). A same-session continuation packet subsequently required one
substantive correction — exactly one lottery selected first (T539), not a simultaneous
T539+P638 dispatch — which is reflected below; no other finding changed.

REPO_MUTATION: NONE
DB_MUTATION: NONE
COHORT_V2_PROSPECTIVE_DATA_USED: NO
B_EXPERIMENT_EXECUTED: NO

## CURRENT_STANDING_FINDING

DEVELOPMENT_SIGNAL_TRANSFER_FAILURE. Three independent B649 mechanisms, spanning three
different technique families, all failed chronological transfer on the same 300-target
fixed HELDOUT:

| Mechanism | Family | Search/VALIDATION result | HELDOUT result |
|---|---|---|---|
| Consensus + pairwise residual reranker | portfolio reranking | +24/720 (search) | 56/300 (18.67%), **-11/300 vs consensus**, 0/6 blocks positive |
| EH04 context-tree-weighted symbolic forecaster | information-theoretic temporal | 137/1020 (13.43%) development, **below consensus's 173/1020 (16.96%)** | never reached — `DISJOINT_FUTURE_EVALUATION_AVAILABLE: NO`; `RESEARCH_CLASSIFICATION: NO_SIGNAL` |
| Consensus alignment / trailing-state mechanism | causal state / rolling gate | `trailing_static_m2_rate_50` z=+2.56 (VALIDATION) | **collapses to a degenerate 300/0 split**; best policy +8/335 (VALIDATION) → **-10/300 (HELDOUT)**, 0/3 blocks positive |

Freshest evidence (same day, `B649_TRACK_D_CROSS_EXPERIMENT_WEAK_SIGNAL_META_MINING_R1`,
2026-08-15 02:30, read prior to this task) adds a fourth, structural finding that changes
the shape of the problem: pooling 17 exposure-matched single-ticket series across 10+
mechanism families gives a *lower* oracle M2+ (73.0%) than what pure random ticket-count
diversification alone would achieve for the same K (93.8% theoretical) — the real models
are **more mutually redundant than random tickets would be**, because all of them draw on
the same 133-strategy / consensus-support substrate. `CONDITIONAL_MODEL_SELECTION_POTENTIAL:
LOW`. This independently reproduces, via a completely different route, the foundational
[[biglotto-uniformity-audit-and-baseline-contamination]] result: BigLotto draws are
statistically indistinguishable from fair 6/49 (8-test Holm-corrected battery, min p=0.24)
— no frequency, positional, temporal, carryover, or pair structure is detectable in the
draw process itself.

**Read together, these four results say the bottleneck is not feature choice — every
information-theoretic/temporal lens tried so far (residual, CTW, trailing-state) is
searching the same population that a rigorous fairness battery already found to be
statistically empty, so in-sample "signal" is the expected artifact of flexible search
on finite fair-random history, not evidence a exploitable structure was missed.**

## WHY_B649_SAME_SUBSTRATE_SEARCH_IS_NOW_LOWER_PRIORITY

This is a prioritization inference, not a theorem that B649 is unpredictable. It rests on
three independent, mutually-reinforcing observations, not one:

1. **A direct fairness result.** The 8-test Holm-corrected uniformity battery already
   found B649's own draw process indistinguishable from fair 6/49 (min p=0.24) — no
   frequency, positional, temporal, carryover, or pair structure detectable.
2. **A direct replication of that result inside a sophisticated temporal model.** EH04's
   CTW forecaster — the closest sibling to EH10/EH01/EH02 already built — independently
   found its variable-order symbolic model carried ~0 information over assuming IID on the
   exact strict-prior symbol streams EH10/EH01/EH02 would also consume.
3. **A portfolio-level redundancy result.** The same-day meta-mining pass shows 10+
   B649-internal mechanisms, across every method family tried so far, are more mutually
   correlated than random tickets would be — because they all draw on one 133-strategy
   substrate over one already-emptied draw sequence.

None of these individually proves EH10/EH01/EH02 must fail. Together they say the next
marginal unit of research cost buys more information by varying the **population** (has
any lottery this project touches ever been checked for basic fairness or search-transfer
behavior outside B649?) than by varying the **feature lens** on a substrate three
increasingly different lenses have now failed to extract anything from. This is why the
comparison below weights `NEW_INFORMATION_SOURCE`, `ORTHOGONALITY_TO_PRIOR_FAILURES`, and
`FAILURE_INFORMATION_VALUE` above raw model sophistication.

## Candidate comparison (A–F, packet-required)

| Direction | New info vs. already-emptied B649 substrate | Chronological transfer potential | Orthogonality to prior failures | Data readiness | Cost | Failure info value |
|---|---|---|---|---|---|---|
| **D — CROSS_LOTTERY_TRANSFER** | Genuinely new population (different draw mechanism/history) | Tests transfer-generality directly, not a specific model's transfer | HIGH — first-ever variation on population, not feature | HIGH (verified live, below) | LOW | HIGH — symmetric, decision-relevant either way |
| A — EH10 permutation-entropy state gate | None — same B649 draw sequence EH04 just showed carries ~0 temporal info vs IID | Unknown, no structural reason to expect better than EH04 | LOW in practice — same "rolling-window state" shape as the just-collapsed trailing-consensus-rate gate | HIGH (data exists) but target signal itself in doubt | LOW | LOW-MEDIUM — 4th same-substrate null |
| B — EH01 matrix-profile motif/discord allocator | None — same substrate | Unknown | Same rolling-window state-gate shape; `REGIME_STATE` bucket already flagged `DENSELY_EXPLORED`/multiplicity-exposed in Frontier V2's own coverage map | HIGH | MEDIUM (window/distance/neighbor/allocator search surface) | LOW-MEDIUM |
| C — EH02 transfer-entropy directed-lag graph | None — same substrate | Unknown | Same family as B; dominated by EH01 on cost/readiness per prior packet's own table | MEDIUM | MEDIUM | LOW-MEDIUM |
| E — different target representation | Only if it taps a genuinely new source (payout/popularity); relative-rank/exclusion-probability/pair-structure variants are monotonic transforms of the same frequency/pair structure the uniformity battery already tested (incl. pair scan, Holm/1176) and found empty | N/A — blocked upstream | Would be HIGH if payout data existed | **LOW/NONE** — the one variant with new information content (E[payout\|win]) needs per-draw per-tier winner counts; confirmed absent from the repo (`research_ticket_results` has `prize_tier_id` only, `draws.jackpot_amount` empty, 0 rows) | N/A | N/A |
| F — other orthogonal Frontier V2 item | Frontier V2's own saturation audit (`B649_TRACK_D_FRONTIER_V2_COVERAGE_AND_SATURATION_R1`) shows every unsaturated region (STOCHASTIC_PROCESS, NEURAL_REPRESENTATION, UNCERTAINTY, etc.) is still a same-substrate feature variant | N/A | Same substrate-reuse problem as A/B/C by construction | Varies | Varies | LOW — same class of problem as A/B/C |

Deprioritized per packet directive and independently corroborated: consensus gating, era
classifiers, recent-performance thresholds, residual reranking, portfolio geometry — all
already tested (directly or as close analogues) and already failed on this exact
population.

## TOP_3_NEXT_DIRECTIONS

### 1

TITLE: CROSS_LOTTERY_UNIFORMITY_AND_SEARCH-TRANSFER REPLICATION — T539 FIRST
ORIGIN: Packet Option D; not present anywhere in Frontier V2's 49-hypothesis catalog —
confirmed by reading `B649_TRACK_D_FRONTIER_V2_COVERAGE_AND_SATURATION_R1`: every one of
its 17 information-source regions is a within-B649 feature/mechanism axis, none is a
population axis. Independently flagged as promising by the same-day meta-mining report's
own `TOP_3_NEW_RESEARCH_HYPOTHESES` #2 ("a productive next candidate... e.g. cross-lottery
structure already validated in [[pr128-strategy-matrix-p638-diversification-merged]]").
NEW_INFORMATION_SOURCE: A structurally different population — T539 (5-of-39, 5,930 draws,
2007-01-01 to 2026-08-01, near-daily), verified live this session via direct schema/row
queries, not from memory. Never tested for basic distributional fairness or for whether a
search-period signal survives chronological holdout. (P638 is the natural second
replication once T539's result is in — see `WHY_THIS_LOTTERY_FIRST` below; the packet
requires exactly one next task, not a simultaneous T539+P638 dispatch.)
ERA_PROXY_RISK: LOW. This is not a rolling-window/trailing-state design (the demonstrated
B649 failure mode) — it is a between-population replication check. Residual caveat:
T539's own within-history era-homogeneity must still be checked independently before
trusting any finding inside it; do not assume T539 shares B649's specific contamination
pattern (the 150 mislabeled `DATE_LIKE` rows, the format-contaminated pre-cutoff blocks).
EXPECTED_INFORMATION_GAIN: HIGH. Both outcomes are decision-relevant: (a) if T539 shows no
detectable departure from fair-random, that is the first evidence outside B649 itself that
"search finds in-sample structure that doesn't transfer" is an expected property of
flexible search on this project's lotteries, not a B649 quirk — motivating the same check
on P638 before any Owner-level pivot; (b) if T539 shows a real, Holm-surviving departure,
that already tells us B649's failure is not a universal lottery property, independent of
what P638 later shows.
DATA_READINESS: HIGH — verified live, not inferred. `t539_wave1.sqlite3`
(`T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`): `source_draws` 5,930 rows plus
`strategy_coverage`/`prediction_tickets`/`prediction_scores`/`target_completion` (46,710
rows), read-only accessible outside git under `.runs/MathStatisticalAnalysis/`.
IMPLEMENTATION_COST: LOW. Reuses 7 of the B649 uniformity battery's 8 tests as-is (main-ball
frequency, era homogeneity, carryover overlap vs hypergeometric, positional order
statistics, sum mean, per-number scan with Holm correction, pair scan with Holm
correction); the 8th (special-ball frequency) does not apply — T539 draws 5 numbers only,
no special/bonus number — which is one fewer test to design, not a gap. Pure Python, zero
new dependencies, no modeling, no fitting, no free parameters to overfit. No repo or DB
writes required.
WHY_IT_MAY_TRANSFER_BETTER: It does not need to "transfer a signal" to succeed — its
output is informative regardless of direction, because it tests whether the transfer
*pattern itself* generalizes, which none of the three failed B649 mechanisms (or A/B/C
below) can address by construction, since all of them hold the population fixed at B649.

### 2

TITLE: EH10_PERMUTATION_ENTROPY_ORDINAL_STATE_GATE
ORIGIN: EXISTING_FRONTIER_V2_EH10; pre-committed as the Track B `STOP_OR_PIVOT` fallback
in `B649_TRACK_D_FRONTIER_V2_SUCCESSOR_RESELECTION_AFTER_RESIDUAL_RERANK_R1` ("On failure,
pivot to EH10") after EH04 was selected over it.
NEW_INFORMATION_SOURCE: NONE, in practice. EH10 computes ordinal-pattern complexity over
the same strict-prior draw/residual symbol streams EH04 already used. EH04's own sealed
result (`TEMPORAL_INFORMATION_DELTA: IID_minus_CTW = -0.000277684491`) shows a sibling
information-theoretic method found **no detectable temporal dependency structure** in that
exact stream — CTW was marginally worse than assuming IID. EH10 mines the same vein with a
different summary statistic.
ERA_PROXY_RISK: HIGH. EH10's own spec (`TEMPORAL_DESIGN: Window/order fixed in inner
folds; each value uses data through t-1`) is structurally the same "rolling-window state
used to gate a conditional decision" shape as `trailing_static_m2_rate_50` — the feature
that, this same day, was shown to collapse into a degenerate calendar-era split on HELDOUT
(`B649_TRACK_B_STATIC_CONSENSUS_ALIGNMENT_MECHANISM_DISCOVERY_R1`), explicitly because
"recent performance" state variables can silently proxy calendar era even while never
reading a date. B649's history carries at least one confirmed regime break (pre-cutoff
format contamination) and one unexplained one (the post-2023 STATIC_CONSENSUS lift) for
any trailing-window statistic to latch onto.
EXPECTED_INFORMATION_GAIN: LOW-MEDIUM. A positive result is antecedently unlikely given
EH04's sibling-method null; a negative result is the 4th same-substrate replication of an
already-well-supported conclusion.
DATA_READINESS: HIGH (data exists) but the target structure itself is now in doubt.
IMPLEMENTATION_COST: LOW.
WHY_IT_MAY_TRANSFER_BETTER: No structural reason found. Retained at #2 only because it was
already pre-committed and remains the cheapest within-B649 option if the Owner prefers to
stay on a single lottery.

### 3

TITLE: EH01_MATRIX_PROFILE_MOTIF_DISCORD_REGIME_ALLOCATOR
ORIGIN: EXISTING_FRONTIER_V2_EH01.
NEW_INFORMATION_SOURCE: NONE, in practice — same substrate as EH10, different transform
(motif/discord recurrence rather than ordinal entropy).
ERA_PROXY_RISK: HIGH — same rolling-window "regime allocator" shape as EH10 (three
prespecified window lengths, trailing computation); Frontier V2's own coverage map already
classifies EH01's `REGIME_STATE` bucket as `DENSELY_EXPLORED` with the caveat "regime
surfaces are extensive but multiplicity-exposed."
EXPECTED_INFORMATION_GAIN: LOW-MEDIUM, for the same reason as EH10, plus a wider
window/distance/neighbor/allocator search surface (flagged MEDIUM cost, weaker failure
attribution in the prior packet's own comparison table).
DATA_READINESS: HIGH.
IMPLEMENTATION_COST: MEDIUM.
WHY_IT_MAY_TRANSFER_BETTER: No structural reason found beyond "not yet tried on B649."

---

## Selected direction

NEXT_RESEARCH_DIRECTION: CROSS_LOTTERY_UNIFORMITY_AND_SEARCH-TRANSFER_REPLICATION — T539 first

ORIGIN: Packet Option D (cross-lottery), scoped by this task to reuse the existing
B649 uniformity-battery *mechanism* rather than port the full 133-strategy consensus
pipeline — "test the same mechanism" is read here as the same statistical-testing
methodology applied to a new population, which is the cheapest, least assumption-laden
way to answer the packet's actual question ("is B649 failure lottery-specific?") without
first building new per-lottery predictive machinery whose own search process could
introduce a fresh multiplicity problem.

WHY_THIS_LOTTERY_FIRST: Compared T539 against P638 on the six factors the continuation
packet named, using data verified live this session (not assumed):

| Factor | T539 | P638 | Edge |
|---|---|---|---|
| Draw count | 5,930 | 1,933 (3.1x fewer) | T539 — tighter confidence intervals, more conclusive null if found |
| Game structure | single zone, 5-of-39, no special number | two zones: 6-of-38 main + 1-of-8 special | T539 — reuses 7/8 B649 tests unmodified; P638 forces a zone-1-vs-joint scoping call before Stage 1 can even start |
| Historical coverage | 2007-01-01 → 2026-08-01 (~19.6y, near-daily) | 2008-01-24 → 2026-07-30 (~18.5y, ~2/week) | T539 — slightly longer, much denser era-homogeneity sub-checks |
| Replay readiness | `target_completion` 46,710 rows | `strategy_targets` 15,464 rows | T539 — ~3x more existing strategy-execution history if a Stage 2 is later authorized |
| Information gain | verdict is cleaner: no zone-scoping ambiguity | verdict inherits a scope judgment call (which zone counts) | T539 |
| Implementation cost | zero new design decisions | needs an explicit zone choice (PR128 precedent: test zone-1 `6-of-38` only, mark zone-2 `NOT_TESTED`, exactly as `pr128-strategy-matrix-p638-diversification-merged` already did for a different mechanism) | T539 |

All six factors favor T539; none favor P638. This is not the packet's suggested default
applied mechanically — P638's second zone is real but not fatal (there is already a clean
precedent for scoping it to zone-1-only), it is simply one more decision T539 does not
require. **P638 is queued as the direct next replication once T539's verdict is in**, using
the same zone-1-only scoping PR128 already established, not dropped from the research line.

NEW_INFORMATION_SOURCE: T539's own draw history (5,930 draws, 5-of-39, 2007–2026) —
independent draw mechanism/operator/history from B649, never before tested for basic
distributional fairness or for whether development-period signal search survives
chronological holdout.

ERA_PROXY_RISK: LOW (not a rolling-state design; see caveat above on checking T539's own
era-homogeneity independently — do not assume it shares B649's specific contamination).

WHY_THIS_DIRECTION_NOW: Three B649-internal mechanisms across three technique families
have failed transfer, and the same-day meta-mining pass shows this is not a "haven't found
the right feature" problem — 10+ mechanisms pooled together are *more* mutually redundant
than random ticket diversification would be, because they all draw on one substrate the
uniformity audit already proved carries no detectable structure. EH04, the most directly
comparable "new information source" already tried, confirms this at the finest grain: its
CTW-vs-IID information delta was essentially zero. Cross-lottery replication is the only
candidate that varies the population instead of the lens, is cheap (reuses a
zero-dependency, already-proven methodology), and is informative regardless of outcome.
Full reasoning: see `WHY_B649_SAME_SUBSTRATE_SEARCH_IS_NOW_LOWER_PRIORITY` above.

WHY_NOT_DIRECTION_2 (EH10): No structural reason to expect success where a sibling
information-theoretic method (EH04) already failed on the identical strict-prior symbol
stream (`IID_minus_CTW = -0.000277684491`, i.e. no detectable temporal dependency). Worse,
EH10 is by design a trailing-window "state gate" (`TEMPORAL_DESIGN: Window/order fixed in
inner folds; each value uses data through t-1`) — the exact shape of
`trailing_static_m2_rate_50`, the feature that, this same day, was shown to collapse into a
degenerate calendar-era split on HELDOUT. B649's history has a confirmed regime break
(pre-cutoff format contamination) and an unexplained one (post-2023 consensus lift) for any
such rolling state to latch onto. Retained at #2 only as the cheapest within-B649 fallback
if the Owner prefers to stay on a single lottery.

WHY_NOT_DIRECTION_3 (EH01): Same substrate, same rolling-window "regime allocator" shape,
same era-proxy exposure as EH10, plus a wider window/distance/neighbor/allocator search
surface (flagged `MEDIUM` cost by the prior packet's own comparison table, versus EH10's
`LOW`) and Frontier V2's own coverage map already classifies its `REGIME_STATE` bucket
`DENSELY_EXPLORED`/multiplicity-exposed. Strictly dominated by EH10 on cost with no
offsetting orthogonality advantage.

WHAT_PRIOR_FAILED_DIRECTIONS_DO_NOT_TEST: Whether transfer failure is a property of
B649's specific data/pipeline (known contamination: 150 mislabeled `DATE_LIKE` rows, a
format-contaminated pre-cutoff block, an unexplained post-2023 STATIC_CONSENSUS lift) or a
general property of running flexible signal search against any fair-random lottery's
finite chronological history. Every prior failure, and every remaining Frontier V2 item
compared above (A/B/C/F), varies only the feature/mechanism while holding the population
fixed at B649 — none of them can distinguish these two explanations.

DISCOVERY_MODE: YES — read-only diagnostic, not a tuned predictive model. The uniformity
battery has no free parameters to select or overfit (fixed binomial/permutation tests with
Holm correction, identical design to the sealed B649 methodology).

DATA_TO_USE: T539 `source_draws` (5,930 rows, `t539_wave1.sqlite3`,
`T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), under `.runs/MathStatisticalAnalysis/`,
outside git, read-only. No Cohort V2 data; unrelated to B649's prospective line. P638
`draws` (1,933 rows, `p638_wave1.sqlite3`, `P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`)
is confirmed ready and queued for the immediate next task after T539, not touched by this one.

VALIDATION_DESIGN (CHRONOLOGICAL_VALIDATION): Not a train/holdout split — a population-
level statistical test evaluated once over T539's full available history, identical in form
to the already-published B649 battery (main-ball frequency, era homogeneity, carryover
overlap vs hypergeometric, positional order statistics, sum mean, per-number scan with Holm
correction, pair scan with Holm correction — 7 of B649's 8 tests; special-ball frequency
does not apply). Report T539's Holm-corrected battery min-p on its own — never pooled with
B649's 0.24, never pre-combined with P638's future result — per the packet's explicit
instruction that different-lottery results must be interpreted independently. If Stage 1
does not settle the question (e.g., an ambiguous near-threshold result), a Stage 2
signal-search follow-on should reuse the expanding-window, strict-prior discipline already
established by the EH04 packet — fit inside folds, lock one configuration, touch a
held-out block exactly once.

PRIMARY_BASELINE: Exact hypergeometric fair-lottery null for 5-of-39 (confirmed live from
sampled draw rows, not assumed from public rules).

PRIMARY_SUCCESS_METRIC: Not "beats consensus." The Stage-1 output is a single verdict —
`DEPARTS_FROM_FAIR_RANDOM` (Holm-corrected battery min-p < 0.05) vs.
`NO_DETECTABLE_DEPARTURE` — for T539 alone. A ticket-level metric (one-ticket M2+ vs. T539's
own naive baseline) only applies if a Stage 2 follow-on is later authorized because T539
shows real departure.

STOP_OR_PIVOT:
- If T539 shows **no detectable departure** from fair-random (matching B649's 0.24):
  dispatch the identical Stage-1 diagnostic to P638 next (zone-1 `6-of-38` only, per the
  PR128 scoping precedent) before drawing any Owner-level conclusion — one fair-random
  lottery is suggestive, not sufficient, to generalize the pattern.
- If **both** T539 and P638 (once run) show no detectable departure: treat "search finds
  in-sample structure that fails chronological holdout" as an expected, general property of
  flexible search on this project's lotteries, not a fixable B649 defect. Recommend the
  Owner-level pivot away from further within-lottery temporal/information-theoretic feature
  hunting (EH01/EH02/EH03/EH10/EH11/EH12 and other state-gate hypotheses, on any of the
  three lotteries) toward either reframing around E[payout|win] if popularity/winner-count
  data can ever be sourced, or halting active search on this axis pending new data.
- If T539 shows a real, Holm-surviving departure: that alone already tells us B649's
  failure is not a universal lottery property. Open a new, separately scoped task to
  characterize T539's specific departure before deciding whether any B649-style mechanism
  is worth re-testing there. Do not copy the finding back onto B649 or forward-assume it
  onto P638.
- A fair-random verdict on T539 does not by itself "prove" EH10/EH01 must fail on B649 — it
  only removes the presumption that more B649-internal feature variants is the highest-value
  next step. EH10 remains legitimately falsifiable on its own terms if the Owner chooses to
  run it anyway.

NEXT_TASK_TRACK: TRACK_D (read-only diagnostic, no tuning, no B experiment — matches the
shape of Track D's own already-completed uniformity audit and meta-mining passes, not a
Track B discovery-with-tuning task)

NEXT_TASK_ID: B649_TRACK_D_CROSS_LOTTERY_UNIFORMITY_REPLICATION_T539_R1

COHORT_V2_PROSPECTIVE_DATA_USED: NO

REPO_MUTATION: NONE

DB_MUTATION: NONE

BLOCKERS: NONE

INTENT: three independent B649 transfer failures plus a same-day meta-mining pass show
the open problem is population-level (a provably fair-random substrate), not feature
choice; this task selects the one candidate that tests population-generality directly,
using an already-proven zero-dependency methodology, over two pre-committed same-substrate
alternatives (EH10, EH01) that inherit a freshly-demonstrated era-proxy risk without
offering a structural reason to expect better transfer than EH04 already showed; T539 is
picked over P638 for this first dispatch on a clean sweep of six evidence-checked factors
(draw count, game structure, historical coverage, replay readiness, information gain,
implementation cost), not a hard-coded default, with P638 queued as the immediate next
replication once T539's verdict is in.

END
