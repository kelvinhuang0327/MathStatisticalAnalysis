# TRACK_D_PREDICTION_ONLY_SUCCESSOR_AFTER_UNIFORMITY_SYNTHESIS_R1

MODE: READ_ONLY_RESEARCH_DIRECTION_DECISION
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-15
STATUS: COMPLETE

REPO_MUTATION: NONE
DB_MUTATION: NONE
B_EXPERIMENT_EXECUTED: NO
COHORT_V2_PROSPECTIVE_DATA_USED: NO

HARD_CONSTRAINT_APPLIED: sole objective is prediction success / P(match) / hit depth.
Prize sharing, jackpot timing, anti-popularity, E[payout|win], and player-choice
modeling are out of primary scope for `NEXT_RESEARCH_DIRECTION` and are carried
below only as the separate, explicitly optional `TRACK_E_EV_RESEARCH` line.

## 0. Why this task exists — reading the packet against its own immediate predecessor

`TRACK_D_CROSS_LOTTERY_UNIFORMITY_SYNTHESIS_AND_NEXT_DIRECTION_R1` (2026-08-15
16:27, this same workspace) is the report this task's own ID names as "after."
That report's own `NEXT_RESEARCH_DIRECTION` was **Option E — anti-popularity /
pari-mutuel payout-asymmetry modeling**, with `NEXT_TASK_ID:
B649_TRACK_E_PRIZE_TIER_DATA_FEASIBILITY_R1`. This task's packet redirects that
choice explicitly: prediction success only, anti-popularity/EV out of primary
scope, that same task ID now demoted to an optional parallel line
(`TRACK_E_EV_RESEARCH`, Section 5 below). This document does not re-litigate
that redirect — it re-runs the selection over the surviving, packet-compliant
candidates from the same evidence base plus one candidate class (`JOINT_STRUCTURAL`)
that no prior Track D document in this chain evaluated.

SOURCES_OPENED this session:
- `docs/research/cross_lottery_research_ledger_r1.json` +
  `cross-lottery-research-ledger-r1.md` + `-schema.md` (Strategy Matrix ledger,
  in-repo)
- `src/lottolab/infrastructure/persistence/draw_schema.py` (canonical `draws`
  table columns, verified live: no ball-order, no machine/equipment, no
  sales/ticket-volume field exists anywhere in the schema)
- `B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1.md` (2026-08-13, 133-strategy
  collision audit, H01–H28)
- `B649_TRACK_D_FRONTIER_V2_SUCCESSOR_SELECTION_R1.md` (08-14 17:11),
  `..._RESELECTION_AFTER_COMPLEMENTARITY_R1.md` (08-14 18:14),
  `..._RESELECTION_AFTER_RESIDUAL_RERANK_R1.md` (08-14 20:16),
  `..._SUCCESSOR_AFTER_TRANSFER_FAILURE_R1.md` (08-15 08:24) — the full B-track
  attempt chain and its three chronological-transfer failures
- `B649_TRACK_D_INFORMATION_FAMILY_GUIDED_NEXT_DIRECTION_R1.md` (08-15 14:15) —
  the 57-family compression result
- `TRACK_D_CROSS_LOTTERY_UNIFORMITY_SYNTHESIS_AND_NEXT_DIRECTION_R1.md` (08-15
  16:27) — immediate predecessor, Option E pick now overridden by this packet
- `docs/research/matrix-native-results/strategy-matrix-phase4-cross-lottery-synthesis-v1-report.md`
  (confirmed this is a *separate* lineage — portfolio-geometry coverage, not
  the uniformity/fairness lineage this task continues; explicitly out of scope
  here as "portfolio geometry")

## 1. What is already exhausted (do not re-select any of this)

| Deprioritized-by-packet category | Concrete instance(s) already run | Result |
|---|---|---|
| Another draw-history temporal transform | EH04 (context-tree-weighted symbolic forecaster) | `IID_minus_CTW = -0.000277684491` — ~0 temporal information vs IID |
| Another consensus reranker/gate | Complementarity-aware candidate stack; consensus+pairwise residual rerank; trailing-state alignment (`trailing_static_m2_rate_50`) | 21.67% < 22.33% consensus; -11/300 vs consensus (0/6 blocks positive, search-overfit); VALIDATION z=+2.56 → HELDOUT degenerate 300/0 split |
| Portfolio geometry | Strategy Matrix Diversification + Constructor-Frontier (Sidon-shift, greedy min-overlap), all `predictive_advantage: NOT_TESTED` by design; separately, Track D's own H06/H14 found `NO_PORTFOLIO_EFFICIENCY_SIGNAL` on predictive outcomes | Confirmed non-predictive by construction and by direct test |
| Simple family diversity | 69 strategies → 57 empirically-independent families (5 similarity views); diverse-family Top-K identical to plain Top-K at K=2/3/5 | `FAMILY_DIVERSITY_ADDED_VALUE: NO` |
| Payout/EV optimization | Option E (anti-popularity/pari-mutuel) | Out of primary scope per this packet; demoted to optional Track E |

Cross-lottery **diagnostic** replication (does the draw process itself depart
from fair-random) is also already complete, not a candidate to re-run:
B649/T539/P638-zone1 all `NO_DETECTABLE_DEPARTURE` under an 7–8-test
Holm-corrected battery (marginal frequency, era-homogeneity, adjacent-draw
overlap vs. hypergeometric, positional order statistics, sum mean, per-number
scan, per-pair scan).

**One mechanism class that battery never covered on any lottery:** the prior
table in `cross_lottery_research_ledger_r1.json` (in-repo) lists
`HIGHER_ORDER_INTERACTION: NOT_TESTED — Only pairwise (2-number) joint
structure was tested; no triples+`, and independently,
`B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1`'s own 133-strategy collision audit
lists `H11 — Pair/triple interaction residuals learned after a frozen
marginal number model` as `HIGH_CONFIDENCE_NOT_TRIED`. Two structurally
different audits (a mechanism-class coverage prior, and a strategy-identity
collision audit) independently converge on the same gap.

## 2. Candidate comparison

Weighted per the packet's own priority order: new information > representation
change > strategy-generation improvement > cross-lottery replication >
chronological transfer potential > cheap falsification.

| Dimension | **A. HIGHER_ORDER_JOINT_STRUCTURE** (triple-wise+ main-number co-occurrence) | B. Structured boundary-promotion (Option C, refined) | C. Cross-field main×special joint structure (H16) |
|---|---|---|---|
| Genuinely new information | HIGH — confirmed `NOT_TESTED` by two independent audits | MEDIUM — reuses already-mined consensus/strategy-support signals; only the *decision structure* is new | HIGH — confirmed `NOT_TESTED` (H16); genuinely untouched field-pair |
| Different target representation | YES — joint/structural vs. marginal | YES — structured low-dimensional assignment vs. 49-dim scalar rerank | YES — cross-field vs. within-field |
| Strategy-generation improvement | YES if positive — biases ticket construction toward high-co-occurrence sets | YES if positive — direct promotion rule | Only for special-number-conditional tiers |
| Cross-lottery replication | Natively designable from t=0 on all 3 lotteries (B649, T539, P638-zone1) | Anomaly is B649-specific; only the *method* travels, needs fresh per-lottery discovery | Only B649 + P638 have a special number; T539 excluded by construction |
| Chronological-transfer risk | **Structurally immune** to the search→reversal failure mode: zero free parameters, exact Holm-corrected combinatorial test, nothing to overfit | Same risk class as the 3 already-failed Track B mechanisms (Track D's own prior doc flags this: "does not obviously escape that failure mode") | Low risk (also parameter-free/exact) but see relevance caveat below |
| Cheap falsification | Extremely — direct parameterization of the already-executed, already-proven pairwise (`JOINT_PAIRWISE`, C(49,2)=1,176 tests) methodology to k=3 (C(49,3)=18,424) | Moderate — needs a new bounded search, same discipline as 3 failed attempts | Cheap — same exact-combinatorial toolkit, needs correct null model for the main/special structural-exclusion relationship (verify official draw mechanism before locking the null) |
| Relevance to primary metric (M2+/M3+) | Direct — operates entirely within the main-number field these metrics are computed on | Direct | **Indirect** — a special-number-conditional finding mainly affects "N+special" tiers, not the main-number M2+/M3+ metrics this task is scored on |
| Track record of this task shape | Matches Track D's own 3-for-3 *successful, trusted* diagnostic lineage (marginal→positional→pairwise→serial→era) | Matches Track B's 3-for-3 *failed* tuned-mechanism lineage | Matches Track D's diagnostic lineage |

Direction A dominates on the two highest-weighted criteria (new information,
representation) while being the *only* candidate structurally immune to the
exact failure mode that has killed every tuned Track B mechanism tried so far
— because it has no fitted parameters to overfit in the first place.

## 3. TOP_3_PREDICTION_DIRECTIONS

### 1. HIGHER_ORDER_JOINT_STRUCTURE — triple-wise (and, conditionally, quadruple-wise) main-number co-occurrence

NEW_INFORMATION_SOURCE: Whether specific 3-number (or 4-number) subsets of the
6 drawn main numbers co-occur more or less often than the exact hypergeometric
null expects, after marginal and pairwise structure are already known to be
clean. Higher-order interaction is not implied or ruled out by lower-order
uniformity — a joint dependency can exist among triples even when every
marginal and every pair is exactly uniform (a standard fact about contingency
tables / copula structure), so this is a genuinely distinct null hypothesis,
not a restatement of the pairwise result.
MECHANISM: Extend the already-sealed `JOINT_PAIRWISE` methodology
(C(49,2)=1,176 exact-hypergeometric, Holm-corrected tests, part of the
already-run 7–8-test battery) to k=3 (C(49,3)=18,424 tests) using the same
Holm-family discipline, or a single global omnibus statistic in the style
already used for the CUSUM change-point cell (`null_replay_percentile`) to
avoid an unwieldy 18,424-way multiplicity correction.
WHY_NOW: It is the one mechanism-class cell the in-repo Strategy Matrix ledger
prior and the external 133-strategy collision audit (H11) both independently
flag as untested, and it extends this project's *proven-trustworthy* lineage
(the uniformity battery, 3-for-3 successful/replicated) rather than its
*proven-unreliable* lineage (tuned Track B mechanisms, 3-for-3 chronological-
transfer failures).
EXPECTED_INFORMATION_GAIN: HIGH — genuinely untested, and unlike every failed
Track B mechanism, cannot produce a spurious in-sample-only result because it
has no fitted parameters.
DATA_READINESS: HIGH — same historical draw data already loaded for the
existing uniformity battery; no new ingestion.
IMPLEMENTATION_COST: LOW — direct generalization of already-written,
already-verified pairwise-scan code.
CROSS_LOTTERY_DESIGN: Natively designable for B649 (C(49,3)), T539 (C(39,3)),
and P638 zone-1 (C(38,3)) from generation 1, matching this project's own
established rollout discipline (design once, replicate immediately).

### 2. Structured/set-level boundary-promotion representation (refined Option C)

Anchored on B649's one real, reproducible, still-unexplained anomaly: static
consensus's 22.33% M2+ rate is genuine (p=0.0003) but confined to POST_2023
targets, with a non-monotonic lift concentrated at ranks 5/6/10/11 (not the
adjacent ranks 4/7). Three independent scalar-rerank mechanisms have already
tried and failed to exploit this out-of-sample. The untested angle is
representing the decision as a small, discrete structured promotion/assignment
choice over the ~4 boundary ranks already implicated — not another 49-
dimensional scalar score fed through the same reranking machinery — and
evaluating it on a **fresh** chronological block (the standard
113000006–115000069 window has now been evaluated against three times and is
no longer a clean blind holdout; whoever executes this must verify live how
many genuinely untouched targets exist past it and reserve them).
WHY_NOW: Directly targets a known, real signal rather than searching blind.
CAVEAT: Track D's own prior document already flagged that changing the lens
"does not obviously escape" the demonstrated TRAIN/HELDOUT-divergence pattern
— ranked #2, not #1, because it is fittable (parameters to select) and
therefore inherits the same overfitting exposure as the three failed
mechanisms, just with a smaller, more disciplined hypothesis space.
RELEVANCE: Direct — main-number field, M2+/M3+-scored.

### 3. Cross-field main×special joint structure (H16)

Whether the special/bonus number's relationship to the main six departs from
what the official draw mechanism alone would predict — confirmed untested by
both the ledger (pairwise prior is explicitly 49-choose-2 main-ball-only) and
the 133-strategy collision audit (H16: "no joint predictive transformation or
legal constructor was recovered").
WHY_NOW: Genuinely new field-pair, cheap (same exact-combinatorial toolkit),
parameter-free.
CAVEAT (why this is #3, not #1): before designing the null, the executing task
must confirm from the official game rule / raw data whether the special
number is drawn from the full 49 or only the remaining 43 after the main six
are removed — a structural exclusion that changes the correct null model. More
importantly: even a confirmed departure here mainly informs the special-number
choice *conditional on* an already-chosen main six, which bears on "N+special"
prize tiers, not on the M2+/M3+ main-number-match metrics this task is scored
against. Legitimate and cheap, but lower relevance to the stated primary
metric than directions 1 and 2.

## 4. Selected direction

NEXT_RESEARCH_DIRECTION: **HIGHER_ORDER_JOINT_STRUCTURE** — exact,
Holm-corrected, parameter-free test for triple-wise (and conditionally
quadruple-wise) joint co-occurrence structure among the 6 main numbers,
extending the already-validated pairwise uniformity methodology, designed
cross-lottery-natively across B649, T539, and P638 zone-1 from the outset.

WHY_IT_CAN_IMPROVE_P_MATCH: If a real higher-order departure exists, it
directly informs which *combinations* of numbers to weight toward in ticket
construction — a mechanism lower-order (marginal, pairwise) analysis is
mathematically incapable of detecting, since higher-order interactions are not
implied or excluded by lower-order uniformity. Because the test has zero
fitted parameters, any positive finding cannot be the same search-then-reverse
artifact that has now sunk three independent tuned Track B mechanisms — a
Holm-corrected departure found here is evidence of the same epistemic quality
as the marginal/pairwise uniformity results this entire program already trusts
enough to act on. A null result is equally valuable: it closes the last
untested static/structural mechanism class in the marginal→positional→
pairwise→serial→higher-order lineage, strengthening (a fourth independent way)
the case that P(match) is not recoverable from B649's within-lottery draw
history under any representation tried so far.

WHY_NOT_DIRECTION_2 (structured boundary-promotion): Real and not rejected —
kept as the designated first pivot if Direction 1 returns null everywhere.
Ranked below Direction 1 because it requires fitted parameters and therefore
inherits nonzero exposure to the exact TRAIN/HELDOUT-divergence pattern that
has now failed three independent times on this same population; Track D's own
prior document already flagged this doubt explicitly.

WHY_NOT_DIRECTION_3 (cross-field main×special): Real and not rejected — kept
as a cheap, parallel, low-cost line since it needs no new data and doesn't
compete for the same evaluation window. Ranked below Directions 1 and 2
because its primary payoff (special-number-conditional tiers) is only
indirectly related to the M2+/M3+ main-number metrics this task is scored
against.

DISCOVERY_MODE: YES — read-only diagnostic. Fixed exact-hypergeometric /
Holm-corrected (or null-replay-percentile omnibus) test, no free parameters to
select or overfit — same design category as the already-sealed marginal,
positional, pairwise, and serial-first-order cells.

DATA_TO_USE: B649's existing cleaned historical draw set already used for the
sealed `JOINT_PAIRWISE` cell and the CUSUM change-point cell (same fast,
parity-verified exact evaluator this program already built and trusts); T539
and P638 zone-1's already-loaded, already-uniformity-tested draw sets for
immediate replication. No new ingestion, no Cohort V2 prospective data.

PRIMARY_SUCCESS_METRIC: This task's own immediate endpoint is a population-
level verdict — `DEPARTS_FROM_FAIR_RANDOM` (Holm-corrected min-p < 0.05, or
equivalent null-replay-percentile threshold) vs. `NO_DETECTABLE_DEPARTURE` for
higher-order joint structure — matching how every prior Track D diagnostic in
this lineage has been scored, and explicitly **not** a ticket-level claim by
itself (this program has repeatedly and correctly refused to conflate a
structural/combinatorial finding with a predictive-advantage claim — see every
`predictive_advantage: NOT_TESTED` diversification cell). **Conditional
downstream metric**, applicable only if a real departure is found and a
follow-on Track B translation task is separately authorized: one-ticket M2+
(secondary: M3+, M4+) versus the matched-random/exact-ticket-count baseline
and versus static consensus, evaluated on a genuinely untouched chronological
block — not the 113000006–115000069 window, which has now been used for
evaluation three times.

STOP_OR_PIVOT:
- No detectable departure on B649 → run the identical parameter-free test on
  T539 and P638 zone-1 before concluding anything (one null population is
  suggestive, not sufficient — same discipline already used for the marginal
  uniformity battery itself).
- No detectable departure on all three → this closes the last untested
  static/structural mechanism class in the marginal→positional→pairwise→
  serial→higher-order lineage. Combined with the three already-failed tuned
  Track B mechanisms, this constitutes the strongest evidence yet that
  P(match) is not recoverable from within-lottery draw history under any
  representation or transform tried on this project's three lotteries.
  First pivot at that point: Direction 2 (structured boundary-promotion),
  explicitly designed with a fresh holdout from the start. Second pivot:
  Direction 3 (cross-field), with its relevance caveat carried forward
  honestly. A pivot toward genuinely external data (Track E or a newly-named
  Option B source) becomes an Owner-level call at that point, not asserted
  here.
- A real, Holm-surviving departure is found in any lottery → open a separate
  Track B translation task to convert the specific departing subset(s) into
  an actual candidate-scoring/ticket-construction rule, evaluated on a fresh
  chronological holdout. Do not backport a lottery-specific finding to the
  other two, and do not skip straight to a ticket-level claim from the
  combinatorial result alone.

NEXT_TASK_TRACK: **D** (read-only, zero-parameter diagnostic — no tuning, no
fitting, no B experiment; matches exactly the shape of this program's already-
completed marginal/pairwise/serial-first-order/change-point cells and the
T539/P638 uniformity-replication tasks, not a Track B discovery-with-search
task).

NEXT_TASK_ID: **B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1** (first
lottery, matching how the marginal/pairwise battery itself was rolled out
B649-first; T539 and P638 zone-1 siblings — e.g.
`..._T539_R1` / `..._P638_R1` — should follow immediately after, using
identical naming, once B649's verdict is in).

## 5. TRACK_E_EV_RESEARCH (separate, optional, parallel — not the prediction direction)

STATUS: OPTIONAL_PARALLEL, unchanged from the immediate predecessor document.

`B649_TRACK_E_PRIZE_TIER_DATA_FEASIBILITY_R1` — the bounded, read-only
feasibility check (does any existing local schema field or public official
Taiwan Lottery endpoint expose per-tier winner-count/payout data) that
`TRACK_D_CROSS_LOTTERY_UNIFORMITY_SYNTHESIS_AND_NEXT_DIRECTION_R1` proposed as
its own top pick before this packet's hard constraint moved anti-popularity/EV
work out of the primary-prediction line. It remains legitimate as an
independent, non-competing track (confirmed live: `draws.jackpot_amount` and
`research_ticket_results.prize_tier_id` exist in schema but are unpopulated;
`TaiwanLotteryDrawProvider` currently discards any prize-tier field the
official API might carry) — it simply cannot be `NEXT_RESEARCH_DIRECTION`
under this task's constraint. May run in parallel without blocking or
competing with Section 4's selected direction; requires separate Owner
ratification of the proposed `B649_TRACK_E_ANTI_POPULARITY_PAYOUT_ASYMMETRY`
track identifier before any ingestion or modeling work.

---

## FINAL

```text
TASK_ID:
TRACK_D_PREDICTION_ONLY_SUCCESSOR_AFTER_UNIFORMITY_SYNTHESIS_R1

STATUS:
COMPLETE

TOP_3_PREDICTION_DIRECTIONS:
1. HIGHER_ORDER_JOINT_STRUCTURE — triple-wise+ main-number co-occurrence (selected)
2. Structured/set-level boundary-promotion representation (Option C, refined) — first pivot
3. Cross-field main×special joint structure (H16) — second pivot, lower relevance to M2+/M3+

NEXT_RESEARCH_DIRECTION:
HIGHER_ORDER_JOINT_STRUCTURE — exact Holm-corrected triple-wise (and
conditionally quadruple-wise) main-number joint co-occurrence test, extending
the already-validated pairwise uniformity methodology, cross-lottery-native
from the outset (B649, T539, P638 zone-1).

NEXT_TASK_TRACK:
D

NEXT_TASK_ID:
B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1

WHY_IT_CAN_IMPROVE_P_MATCH:
Higher-order (k>=3) joint structure is not implied or excluded by the
already-tested marginal and pairwise uniformity results, so it is genuinely
new information; a real departure directly informs which number combinations
to weight in ticket construction, and because the test is exact and
parameter-free it cannot produce the search-then-reverse artifact that sank
the three already-failed tuned Track B mechanisms (complementarity stack,
residual rerank, EH04/trailing-state).

PRIMARY_SUCCESS_METRIC:
Immediate: population-level DEPARTS_FROM_FAIR_RANDOM (Holm-corrected min-p <
0.05) vs. NO_DETECTABLE_DEPARTURE. Conditional downstream (only if departure
found and a Track B translation task is separately authorized): one-ticket
M2+/M3+/M4+ vs. matched-random and static-consensus baselines on a genuinely
fresh chronological holdout, not the three-times-used 113000006-115000069
window.

STOP_OR_PIVOT:
Null on B649 -> replicate on T539 then P638 zone-1 before concluding. Null on
all three -> closes the last untested static/structural mechanism class;
first pivot = Direction 2 (structured boundary-promotion, fresh holdout from
the start); second pivot = Direction 3 (cross-field, relevance-caveated).
Real departure found -> separate Track B translation task on a fresh holdout,
no backporting across lotteries.

TRACK_E_EV_RESEARCH:
OPTIONAL_PARALLEL
B649_TRACK_E_PRIZE_TIER_DATA_FEASIBILITY_R1
(carried unchanged from the immediate predecessor synthesis; not the
prediction direction under this task's hard constraint; requires separate
Owner ratification)

COHORT_V2_PROSPECTIVE_DATA_USED:
NO

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

END
```
