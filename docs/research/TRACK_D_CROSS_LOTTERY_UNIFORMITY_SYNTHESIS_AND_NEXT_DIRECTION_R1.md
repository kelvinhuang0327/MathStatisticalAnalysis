# TRACK_D_CROSS_LOTTERY_UNIFORMITY_SYNTHESIS_AND_NEXT_DIRECTION_R1

Read-only research-direction decision. No repo/DB mutation. No new experiment run. No
uniformity battery re-run. No Cohort V2 prospective data used.

## CROSS_LOTTERY_FINDING

Three structurally different games — B649 (6/49, 2,138 cleaned draws), T539 (5/39,
5,930 draws), P638 zone-1 (6/38, 1,933 draws) — have each independently run the same
kind of comprehensive, pre-registered, Holm-corrected uniformity/fairness battery
(frequency, era-homogeneity, adjacent-draw overlap, positional order statistics, sum
mean, per-number scan, per-pair scan) against their full draw history, and all three
returned **NO_DETECTABLE_DEPARTURE**:

| Lottery | Game | Draws | Holm family | Survivors | Min raw p |
|---|---|---|---|---|---|
| B649 | 6/49 | 2,138 | 8-test battery, per-scan Holm | 0 | — (min p=0.2435 on the clean set) |
| T539 | 5/39 | 5,930 | 789 | 0 | 0.00371 |
| P638 zone-1 | 6/38 | 1,933 | 751 | 0 | 0.001717 |

This is the third and final planned replication of this specific battery; the designed
next step was always a synthesis across the three, not a fourth per-lottery run.

## WHAT_IT_SUPPORTS

- Under each lottery's fixed diagnostic battery and current sample size, no
  statistically significant departure from a fair/uniform draw process was detected,
  in any of frequency, era-homogeneity, adjacent-draw overlap, positional order,
  sum-mean, or per-number/per-pair structure.
- This converges with an independent line of evidence from B649's own strategy-mining
  history: exhaustive attempts to extract a stable predictive edge from the *same*
  underlying draw-history substrate — temporal/state signals, consensus reranking,
  cross-model complementarity, portfolio/family diversity — have also come back null
  or have failed chronological transfer, every time they were tested against a
  genuine held-out block rather than only a validation split.
- Taken together (uniformity diagnostics on raw draws + repeated substrate-mining
  failures on derived signals), the marginal expected value of investing further
  research budget in "mine the existing temporal/consensus/portfolio substrate harder,
  on the same underlying draw-outcome target" is low across all three lotteries tested.

## WHAT_IT_DOES_NOT_PROVE

- **Not proof of randomness.** Failing to detect a departure under a fixed battery
  and current sample size is not equivalent to proving no departure exists.
- **Not proof prediction is impossible.** The battery only tests whether raw draw
  statistics deviate from a uniform/fair process; it says nothing about other
  representations of the same data, other information sources, or non-hit-rate
  notions of predictive success.
- **Does not generalize to P638 zone-2** (the 1-of-8 special number), which was
  explicitly out of scope for the P638 run and was never pooled into its Holm family.
- **Does not mean every future direction is doomed** — it specifically deprioritizes
  continued investment in the substrate already exhausted (within-lottery temporal
  mining, consensus reranking, portfolio-diversity variants on the same draw-outcome
  target), not research in general.

## TOP_3_NEXT_DIRECTIONS

### 1. TITLE: Anti-popularity / pari-mutuel payout-asymmetry modeling (Option E)

- **NEW_INFORMATION_SOURCE:** Yes, categorically. Every direction tested so far
  (temporal, consensus, portfolio) targets the same estimand — P(the ticket matches
  the drawn numbers) — computed from the same draw-history substrate. This direction
  targets a completely different, non-overlapping question: E[payout | match], which
  is governed by *other players'* number-selection behavior, not by the physical draw
  process. Human number-selection bias toward small/birthday numbers and sequential
  patterns is a well-documented phenomenon in lottery economics generally; it has
  never been tested here because nothing in this project's history has looked at it.
- **WHY_NOW:** A prior independent analysis on this exact project
  ([[biglotto-uniformity-audit-and-baseline-contamination]], 2026-08-12) already
  concluded, from the B649 uniformity result alone, that "the only remaining lever is
  E[payout | win], not P(win)." Today's synthesis reinforces that conclusion twice
  over (T539, P638 zone-1 independently null too), and B649's separate mining-failure
  history removes the last plausible alternative (that a cleverer feature/consensus
  method would still find P(match) signal). Three independent lines of evidence now
  converge on the same place.
- **EXPECTED_INFORMATION_GAIN:** High, conditional on data existing. This is not
  speculative pattern-hunting in a process already shown to look fair — it is testing
  a different, independently well-established real-world phenomenon (asymmetric human
  choice), which has a much stronger prior than "maybe there is hidden temporal
  structure we have not found yet."
- **DATA_READINESS:** Not currently ready, and this must be stated plainly, not
  glossed over. Confirmed live this session: `jackpot_amount` is referenced nowhere in
  `src/` (matches the 2026-08-12 memory that this column is empty/zero rows), and
  `TaiwanLotteryDrawProvider` (`src/lottolab/infrastructure/taiwan_lottery_draw_provider.py`)
  extracts only `period` / `lotteryDate` / `drawNumberSize` from the official API
  response — it discards any prize-tier, winner-count, or payout field even if the
  raw response happens to carry one. Whether the upstream public API (or another
  official Taiwan Lottery page) exposes per-tier winner-counts/payouts at all is
  **[Unknown]** and unverified as of this report — that is the cheap first step,
  not an assumption to build on.
- **IMPLEMENTATION_COST:** Low for the feasibility gate (one read-only inspection of
  an existing or adjacent public endpoint); moderate afterward if data exists, since
  it is a genuinely new pipeline (ingestion + a new discovery-only analysis), not a
  reuse of existing consensus/portfolio machinery.

### 2. TITLE: Different target representation (Option C)

- **NEW_INFORMATION_SOURCE:** Partial. No new raw data — same draw-history substrate
  — but a structurally different estimand (e.g. relative number ranking, exclusion/
  negative target, pair/triple conditional target, candidate-quality objective instead
  of exact-combo match). Explicitly distinct from "mine more temporal features," which
  is why the packet separates it from Option A rather than treating it as a variant.
- **WHY_NOW:** B649 has one specific, still-unresolved anomaly this could directly
  probe: static consensus's 22.33% M2+ rate is real and reproducible but confined to
  POST_2023 targets, with a lift concentrated at ranks 5/6/10/11 (not the adjacent
  ranks 4/7) — a non-monotonic, era-conditional pattern that 17 tested features and
  three independent mechanisms (temporal CTW, pairwise residual rerank, trailing-state)
  all failed to explain or exploit out-of-sample. A different target representation
  (e.g., modeling rank-conditional promotion directly, rather than a swap/rerank score)
  is untested and could expose whether the anomaly is structural or an artifact of how
  the current representation pools ranks.
- **EXPECTED_INFORMATION_GAIN:** Moderate. Directly targets a known, real, unexplained
  signal (era-conditional consensus lift) rather than searching blind, but three prior
  independent mechanisms on this same population have already shown a strong pattern
  of promising VALIDATION-period signal reversing on a genuine chronological HELDOUT —
  a new representation does not obviously escape that failure mode, it only changes
  what is being mined.
- **DATA_READINESS:** High — reuses data, candidates, and the sealed static-consensus
  chain already computed by the Track B error-atlas / alignment-mechanism work; zero
  new ingestion required.
- **IMPLEMENTATION_COST:** Low-to-moderate — mostly a new objective/label on an
  existing feature and data pipeline; must reserve a genuine chronological holdout
  from the start given the project's own repeated TRAIN/VALIDATION-overfit lesson.

### 3. TITLE: Strategy-generation information from a genuinely new feature source (Option B)

- **NEW_INFORMATION_SOURCE:** Conditional. Only as good as the specific new source
  named. B649 already compressed 69 strategy IDs into ~57 information families, and
  simple family-diversity selection plus portfolio geometry both added zero predictive
  value — so another strategy that still derives from draw-history temporal signal,
  merely computed differently, would land in the explicitly deprioritized bucket
  ("another temporal feature mined only because it is mathematically different").
- **WHY_NOW:** Nothing currently rules this out, but nothing currently identifies a
  concrete non-temporal candidate source either — it is the least-specified of the
  three. If Option E's feasibility check turns up additional data fields (e.g. sales
  volume, ticket-count metadata) as a byproduct, some of that could feed this option
  directly rather than requiring separate sourcing work.
- **EXPECTED_INFORMATION_GAIN:** Unclear until a specific source is named; could be
  high (if genuinely orthogonal) or zero (if it collapses back into more temporal
  reprocessing of the same substrate that has already saturated).
- **DATA_READINESS:** Low-to-moderate and source-dependent — not assessable in the
  abstract.
- **IMPLEMENTATION_COST:** Moderate-to-high — needs a new generation/scoring pipeline,
  not just a new label on existing features.

**Explicitly reviewed and ranked outside the top 3:**

- **Option A (more within-lottery temporal mining — entropy/motif/state/lag):**
  Lowest priority. This is the only option with *demonstrated negative* chronological
  transfer, not merely untested status — three independent B649 mechanisms already
  failed this exact test (temporal CTW forecaster: NO_SIGNAL; pairwise residual
  rerank: SEARCH +24/720 → HELDOUT -11/300; trailing-state/F1-low: VALIDATION
  z=+2.56 → HELDOUT collapses to a degenerate split). It also matches, almost by
  definition, the pattern the task brief explicitly deprioritizes.
- **Option D (cross-lottery strategy replication):** Premature. There is currently no
  single-lottery mechanism that has *itself* survived a genuine chronological holdout,
  so there is nothing validated worth replicating across lotteries yet. Running this
  now would also repeat the same "replicate the same battery/method across lotteries"
  shape this synthesis exists to move past, per its own designated next step. Revisit
  once Option E or C produces a within-lottery-validated candidate mechanism.

## NEXT_RESEARCH_DIRECTION

**Anti-popularity / pari-mutuel payout-asymmetry modeling** (Option E, scoped to B649
first) — starting with a single bounded, read-only feasibility check: does any
existing or adjacent official Taiwan Lottery public endpoint expose per-tier
winner-count or payout data, and does the local schema already carry (even if empty)
a place to store it. Nothing beyond that check is authorized by this decision.

### WHY_THIS_DIRECTION_NOW

It is the only option that scores well on the top-weighted criterion
(NEW_INFORMATION_SOURCE) with a real-world basis stronger than "hope for hidden
structure": human number-selection bias is independently well-established, not a
speculative hypothesis native to this project. It is also the direction a completely
separate, earlier analysis on this exact codebase already converged on for exactly
this reason, before today's cross-lottery synthesis existed to confirm the P(match)
side twice more. Framing note for the Owner: this reframes "predictive success" from
hit-rate (P(match), now well-evidenced as flat across all three lotteries and
exhausted as a B649 substrate) to expected value conditional on a match
(E[payout | match]) — a deliberate scope decision, not a silent substitution, and one
worth confirming explicitly since it changes what "success" means going forward.

### WHY_NOT_DIRECTION_2

Option C (different target representation) is the strongest fallback and is not
rejected — it needs no new data and directly probes B649's one remaining unresolved
anomaly (era-conditional consensus lift). It ranks second because it still targets
P(match) on the same draw-outcome data the cross-lottery synthesis and B649's own
mining history give the least remaining reason to expect new signal from, and because
its chronological-transfer risk is not obviously lower than the three mechanisms that
already failed that exact test on this population — changing the lens does not by
itself change the demonstrated TRAIN/HELDOUT-divergence pattern.

### WHY_NOT_DIRECTION_3

Option B (new strategy-generation feature source) ranks third because it is
currently unscoped — its entire value depends on naming a source that is genuinely
not a reprocessing of draw-history temporal signal, and no such source is identified
anywhere in the assembled evidence yet. Committing budget here before a concrete
source exists risks landing in the explicitly deprioritized "mathematically different
temporal feature" bucket by default.

### DISCOVERY_MODE

Bounded, read-only feasibility check first (does the data exist anywhere, local or
public); only if that resolves positively, proceed to a discovery-only exploratory
pass (no production integration, no ticket/UI changes) with a genuine chronological
train/heldout split reserved from the start — this project has now demonstrated the
train-validation-overfit failure mode three independent times on related work, and
any new mechanism must be designed to survive that check, not just pass validation.

### DATA_TO_USE

Existing local schema fields already present but currently unpopulated
(`draws.jackpot_amount`, `research_ticket_results.prize_tier_id`); the existing
official Taiwan Lottery API integration family (same endpoint class as
`Lotto649Result` / `NextDrawDate`, already used elsewhere in this project) as the
candidate public source for per-tier winner-count/payout data, pending verification
that it actually exposes such fields. Explicitly **not** Cohort V2 prospective
outcomes, and not a new uniformity battery.

### PRIMARY_SUCCESS_METRIC

Feasibility gate (binary, first): a verified per-tier winner-count or payout time
series can legitimately be obtained (local schema already has a place for it, or a
public official source exposes it) without new experimentation on the draw process
itself. Only if that gate passes, the discovery-stage metric becomes: combinations
built from below-median-popularity numbers show a statistically distinguishable
(Holm-corrected, chronologically held-out) reduction in same-tier winner-count or
jackpot-sharing versus a matched random-combination baseline — notably, this metric
does not require predicting the winning numbers at all, only predicting which
combinations other players are least likely to also hold.

### STOP_OR_PIVOT

**PIVOT.** Move off further investment in mining the existing
temporal/consensus/portfolio substrate for P(match) signal (Options A and, for now,
D), onto a structurally different question (E[payout | match] via other players'
selection bias), gated by one cheap verification step before any build commitment.

### NEXT_TASK_TRACK

`B649_TRACK_E_ANTI_POPULARITY_PAYOUT_ASYMMETRY` (new track letter; distinct from the
existing Track B [static-consensus mechanism mining] and Track D [uniformity/
cross-lottery] tracks — proposed name, not yet an Owner-ratified identifier).

### NEXT_TASK_ID

`B649_TRACK_E_PRIZE_TIER_DATA_FEASIBILITY_R1` — a single bounded, read-only check of
whether per-tier winner-count/payout data exists anywhere (local schema or public
official source) before any ingestion, modeling, or governance work is authorized.

---

## FINAL

```
TASK_ID:
TRACK_D_CROSS_LOTTERY_UNIFORMITY_SYNTHESIS_AND_NEXT_DIRECTION_R1

STATUS:
COMPLETE

CROSS_LOTTERY_RESULT:
B649 = NO_DETECTABLE_DEPARTURE
T539 = NO_DETECTABLE_DEPARTURE
P638_ZONE1 = NO_DETECTABLE_DEPARTURE

WITHIN_LOTTERY_TEMPORAL_MINING_PRIORITY:
LOW

TOP_3_NEXT_DIRECTIONS:
1. Anti-popularity / pari-mutuel payout-asymmetry modeling (Option E, B649-scoped)
2. Different target representation (Option C)
3. Strategy-generation information from a genuinely new feature source (Option B)

NEXT_RESEARCH_DIRECTION:
Anti-popularity / pari-mutuel payout-asymmetry modeling (Option E)

NEW_INFORMATION_SOURCE:
Other players' number-selection behavior (pari-mutuel payout-sharing dynamics) —
categorically distinct from the temporal/consensus/portfolio substrate already mined
against P(match) on the same draw-outcome data.

WHY_THIS_DIRECTION_NOW:
Only option with a real-world-grounded (not speculative) new-information basis;
independently converged on by a prior analysis on this exact project before today's
synthesis reinforced the P(match) side twice more; reframes success toward
E[payout|match], a scope decision flagged explicitly for Owner confirmation.

DISCOVERY_MODE:
Bounded read-only feasibility check first; discovery-only exploratory pass with a
genuine chronological holdout only if the gate passes.

DATA_TO_USE:
Existing local schema fields (draws.jackpot_amount, research_ticket_results.prize_tier_id)
plus the existing official Taiwan Lottery API integration family, pending verification
of per-tier winner-count/payout availability. Not Cohort V2 prospective outcomes.

PRIMARY_SUCCESS_METRIC:
Binary feasibility gate first (data obtainable without new draw-process experimentation);
then Holm-corrected, chronologically held-out reduction in matched-tier winner-count
for below-median-popularity combinations vs. a random baseline.

STOP_OR_PIVOT:
PIVOT

NEXT_TASK_TRACK:
B649_TRACK_E_ANTI_POPULARITY_PAYOUT_ASYMMETRY (proposed, not yet Owner-ratified)

NEXT_TASK_ID:
B649_TRACK_E_PRIZE_TIER_DATA_FEASIBILITY_R1

COHORT_V2_PROSPECTIVE_DATA_USED:
NO

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

END
```
