# Track D — Cross-Lottery Higher-Order Synthesis and Next Direction, R1

TASK_ID: TRACK_D_CROSS_LOTTERY_HIGHER_ORDER_SYNTHESIS_AND_NEXT_DIRECTION_R1
MODE: READ_ONLY_RESEARCH_DECISION
DATE: 2026-08-15
REPO_MUTATION: NONE
DB_MUTATION: NONE
COHORT_V2_PROSPECTIVE_DATA_USED: NO

## Provenance verification (done first, per packet)

All three source reports read directly from disk:

- `B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1.md` (completed 18:06)
- `T539_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1.md` (completed 19:08)
- `P638_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1.md` (completed 19:36)

All three exist and all three report `NO_DETECTABLE_HIGHER_ORDER_DEPARTURE`.
The P638 report still carried a "no B649/T539 precedent exists" conflict
note, accurate at the moment P638 started (B649/T539 hadn't finished yet).
Methodology check confirms semantic consistency across all three: a fixed
zero-tuning chi-square-type global omnibus statistic (B649/T539 use the
direct `Σ(O-E)²/E` form; P638 uses an algebraically equivalent `S_k`/`T_k`
pairwise-shortcut form — proven affine-equivalent in its own report), a
fixed-seed Monte Carlo null with R=20,000 replications each, an exact
per-triple two-sided binomial local scan with Holm-Bonferroni correction at
α=0.05, and no local quadruple fishing scan in any of the three. Only the
game-shape-dependent inclusion probabilities differ (49/6, 39/5, 38/6), as
expected. Per the packet's instruction, **only the provenance description
was corrected** (a short addendum appended to the P638 report, historical
conflict narrative left intact) — no statistics were rerun.

## CROSS_LOTTERY_FINDING

```
B649   (6-of-49, N=2,138): triple omnibus p=0.9295, quad omnibus p=0.8551, 0/18,424 Holm survivors
T539   (5-of-39, N=5,930): triple omnibus p=0.8413, quad omnibus p=0.5763, 0/9,139  Holm survivors
P638-1 (6-of-38, N=1,933): triple omnibus p=0.4181, quad omnibus p=0.3223, 0/8,436  Holm survivors
```

All three: **NO_DETECTABLE_HIGHER_ORDER_DEPARTURE**, on three structurally
different games (different pool sizes, different pick counts), using the
same fixed pre-registered statistic/protocol family, with zero Holm
survivors across 35,999 combined local tests and all six global omnibus
p-values landing unremarkably mid-distribution (no one-tailed clustering
near 0 or 1 across the six numbers).

## WHAT_IT_SUPPORTS

This triple/quadruple result does not stand alone — it is the newest layer
of a now-consistent stack of null and negative findings on the same
draw-history substrate:

1. Marginal + pairwise + positional + serial + era structure: already
   NO_DETECTABLE_DEPARTURE for B649 (Holm min p=0.24) and replicated for
   T539/P638-1 ([[biglotto-uniformity-audit-and-baseline-contamination]],
   [[b649-track-d-cross-lottery-uniformity-replication-series]]).
2. Triple/quadruple structure: NO_DETECTABLE_HIGHER_ORDER_DEPARTURE, this
   report, on all three lotteries.
3. Three independent *tuned* Track B mechanisms built on this same
   substrate (temporal context-tree forecaster, pairwise residual reranker,
   trailing-state/F1-low conditional gate) all showed the identical
   search-then-reverse signature: promising in SEARCH/VALIDATION, reversing
   on the fixed 300-target HELDOUT
   ([[b649-track-b-static-consensus-alignment-mechanism-r1]],
   [[b649-track-b-static-consensus-error-atlas-r1]],
   [[b649-track-d-static-consensus-failure-mode-r1]]).
4. Combining/ensembling the existing 57-family, 69-strategy catalog has
   **negative** corrected combination headroom in all 6 fair-exposure groups
   tested, all eras ([[b649-track-b-family-headroom-discovery-r1]]).

Four independent lines of evidence, four different methodologies, converge
on one conclusion: **further transforms of the same draw-sequence
substrate — whatever the order, window, entropy measure, or tuned
mechanism — have declining expected information gain.** This is exactly the
research-priority claim the task packet asked to be tested, and it holds.

## WHAT_IT_DOES_NOT_PROVE

- **Not proof of randomness.** Each diagnostic is a bounded, pre-registered
  test at one fixed statistic/protocol, orders 3-4 only (order 5-6 untested,
  combinatorially expensive), and cannot rule out non-i.i.d. forms outside
  its design (e.g., non-linear/non-count-based dependence).
- **Not proof prediction is impossible.** A mechanism outside draw-sequence
  structure, or a genuinely new representation, remains untested — that is
  exactly the fork this report resolves below.
- **Does not generalize the Track B failures beyond what was tested.** Only
  three specific mechanism families were tried, only on B649. The shared
  "search-then-reverse" pattern and the now-quadruple-confirmed uniformity
  substrate they all sit on make further B649-style tuned search low-prior,
  not formally refuted for every conceivable mechanism.
- **P638-1 only covers zone-1** (6-of-38); zone-2 (1-of-8 special) was never
  read into any of these diagnostics.

## TOP_3_NEXT_DIRECTIONS

Evaluated against categories A-E, with the explicit deprioritize list
(another entropy/window/motif transform, another consensus reranker/gate,
another portfolio-diversity method, family-diversity ensemble, EV/payout
optimization) applied:

**1. (Selected) D — orthogonal draw-metadata feasibility recon.** The only
category structurally capable of adding information the four evidence
lines above haven't already tested, *if* a real orthogonal field exists.
No such field is currently confirmed to exist in this program's reach — a
repo grep found no machine/ball-set/session identifier anywhere in the
draw schema or the Taiwan Lottery provider
([[draw-automation-provider-gap]]) — so this is scoped as a cheap,
bounded, read-only reconnaissance task, not a statistical study, to avoid
recommending a direction resting on an unverified data source.

**2. A/B (considered, not selected) — new strategy-generation info /
different target representation.** A is already exhaustively covered by
the existing 57-family catalog with negative combination headroom found
(#4 above); no untried variant was identified that isn't itself another
transform of the same substrate. B (exclusion targets, relative candidate
quality, conditional pair/set targets) is mathematically a re-labeling of
the same draw-sequence numbers already confirmed uniform through order 4 —
under a confirmed-near-uniform generating process, changing what is
predicted (not what data it's predicted from) cannot manufacture signal
that isn't there. Both deprioritized on the same logic as the excluded
"another transform" categories, just one level more abstract.

**3. C (considered, not selected) — cross-lottery predictive-mechanism
transfer.** Testing whether an actual mechanism (not a fairness statistic)
transfers across lotteries is conceptually different from what's been
tested here, but it presupposes there is a per-lottery signal to transfer
in the first place — and all three lotteries individually show none, at
every order tested. Worth revisiting only if #1's recon surfaces a real
new signal to test transferability of; not worth pursuing against an
empty signal set today.

**Not ranked but running in parallel, non-blocking:** the forward-observer
prospective loop ([[b649-forward-operation-goal-c-state]],
[[ceo-review-2026-08-12-forward-observer-reorder]]) is calendar-gated, not
compute-gated, and is the only source of genuinely new information (real
future draws) that no retrospective transform of the historical corpus can
substitute for. It is already an Owner-approved, actively running Goal
(not a new task this report needs to select) — this synthesis's job is
retrospective-mining priority, and it explicitly does not compete with or
block that loop.

## NEXT_RESEARCH_DIRECTION

**D — Orthogonal draw-metadata feasibility reconnaissance**, scoped
narrowly: inventory what fields the existing pipeline already has access
to (official API responses already fetched by
`taiwan_lottery_draw_provider.py`, and the sqlite draw tables for all three
lotteries) beyond the 6-number(+special) draw outcome already mined to
exhaustion above, and determine which (if any) are (a) genuinely orthogonal
to draw-sequence structure, (b) available with sufficient history to test,
and (c) not EV/popularity/anti-popularity (Track E, explicitly out of
scope). This is a feasibility gate, not a promise of signal.

## WHY_THIS_DIRECTION_NOW

Four independent evidence lines (marginal/pairwise/serial/era,
triple/quadruple, three tuned Track B mechanisms, portfolio-combination
headroom) all returned null or negative results on the same draw-sequence
substrate. A/B/C either re-transform that same substrate or presuppose a
signal within it that isn't there. D is the only category not already
refuted — but recommending a *specific* external data source without first
checking it exists would repeat the exact mistake this task was designed
to catch (the P638 report's own conflict section, and
[[p638-zone1-track-d-higher-order-r1]]'s memory, both flag "don't assume a
citable artifact/precedent exists without checking"). A cheap recon task
resolves that uncertainty before any compute is spent on a new statistical
design.

## NEW_INFORMATION_SOURCE

Official per-draw metadata fields already present in Taiwan Lottery API
responses and/or the existing sqlite schemas, but never used as prediction
features — status of each field's existence is `[Unknown]` until the recon
runs. Explicitly excludes ticket-sales/popularity data (Track E/EV scope)
and anything requiring new external integration.

## DISCOVERY_MODE

READ_ONLY_FEASIBILITY_RECON — inventory and classify only; no statistical
testing, no MC protocol, no strategy development in this next task. Design
any actual test only after confirming a field exists, has adequate
history, and is orthogonal to draw-sequence structure.

## DATA_TO_USE

- Raw JSON payloads already fetched by
  `src/lottolab/infrastructure/taiwan_lottery_draw_provider.py`
  (`Lotto649Result`, `Daily539Result`, `SuperLotto638Result` endpoints) —
  full response shape, not just the parsed 6-number/special fields the
  pipeline currently extracts.
- Existing `draws` / `source_draws` sqlite schemas for B649, T539, P638
  (the same baseline databases the higher-order diagnostics read), checked
  read-only for any ingested-but-unused column.
- No Cohort V2 prospective data, no new network calls beyond what the
  provider already does in its existing tests/fixtures.

## PRIMARY_SUCCESS_METRIC

Binary feasibility gate for this recon task: does at least one field exist
that is (a) not already implied by the 6-number+special outcome, (b) not
EV/popularity-related, and (c) has enough history to test. This recon does
not itself move P(match)/M2+/M3+ — it determines whether a follow-on task
that could is worth designing. If the gate is NO, the honest fallback
(stated up front, not discovered later) is to explicitly deprioritize
further retrospective draw-history mining and let the already-running
forward-observer prospective loop be the primary ongoing source of new
evidence.

## STOP_OR_PIVOT

**PIVOT.** Stop investing further compute in draw-sequence retrospective
transforms (entropy/window/motif variants, consensus rerankers/gates,
portfolio-diversity/ensemble methods, additional joint-order scans) — four
independent lines of evidence now agree this substrate is exhausted at
current statistical power. Pivot to the bounded D recon above before
committing to any new statistical design, and do not block or compete with
the already-running forward-observer loop, which remains the CEO-ranked P1
source of calendar-gated new evidence regardless of this recon's outcome.

## NEXT_TASK_TRACK

D

## NEXT_TASK_ID

B649_TRACK_D_ORTHOGONAL_DRAW_METADATA_FEASIBILITY_RECON_R1

(cross-lottery-native from the outset: B649, T539, P638, same convention as
the higher-order diagnostic this report synthesizes)
