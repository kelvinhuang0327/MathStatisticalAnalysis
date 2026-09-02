# B649_TRACK_D_PRE_CUTOFF_ORTHOGONAL_INFORMATION_RESELECTION_R1

MODE: READ_ONLY_RESEARCH_DECISION
ROLE: Track D — Research Direction Optimizer
DATE: 2026-08-15
STATUS: COMPLETE

REPO_MUTATION: NONE
DB_MUTATION: NONE
LIVE_EXPERIMENT_EXECUTED: NO

## 0. Why this task exists

The immediately preceding task
(`[[b649-track-d-ball-set-assignment-bounded-acquisition-r1]]`) resolved the
one candidate the prior recon had ranked highest — ball-set ID — to
`PRE_DRAW_BUT_AFTER_BETTING_CUTOFF`: Taiwan Lottery's own FAQ states the
20:30 draw time exists specifically because 30 minutes must be reserved
*after* the 20:00 sales cutoff for sales-statistics computation before the
draw procedure (including machine/ball-set/loading-order selection) can even
start. So ball-set ID is not usable as a live predictor, and this packet asks
Track D to re-search for a genuinely different pre-cutoff information source,
under a hard filter, and to select exactly one next direction — or, if
nothing clears the filter, to say so and pivot to a different predictive
target representation or other genuinely orthogonal research.

## 1. Sources opened this session

Repo-external Track D lineage (read in full or targeted-grepped):
`B649_TRACK_D_ORTHOGONAL_DRAW_METADATA_FEASIBILITY_RECON_R1.md`,
`B649_TRACK_D_BALL_SET_ASSIGNMENT_BOUNDED_ACQUISITION_R1.md`,
`TRACK_D_CROSS_LOTTERY_UNIFORMITY_SYNTHESIS_AND_NEXT_DIRECTION_R1.md`,
`TRACK_D_PREDICTION_ONLY_SUCCESSOR_AFTER_UNIFORMITY_SYNTHESIS_R1.md`,
`B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1.md`,
`B649_TRACK_D_INFORMATION_FAMILY_GUIDED_NEXT_DIRECTION_R1.md`,
`B649_TRACK_D_POST2023_CONSENSUS_ALIGNMENT_MECHANISM_R1.md`,
`B649_TRACK_D_EXTERNAL_HYPOTHESIS_INVENTORY_R1.csv`,
`B649_TRACK_D_EXTERNAL_SOURCE_REGISTRY_R1.csv`,
`B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2*.csv`,
`B649_TRACK_D_RESEARCH_SURFACE_R1.md` (grep-checked for equipment/venue/RNG
terms — no hits beyond unrelated "machine learning" library references),
plus the memory index for this project.

External, this session (read-only web research, no accounts, no downloads):
official Taiwan Lottery draw-process page (`taiwanlottery.com/run_lottery/info/`),
Taiwan Lottery FAQ (already cited by the predecessor task), Legislative Yuan
public page on lottery-issuance history, and general search results on lottery
draw schedule, venue, and equipment-testing practice. Full source list is
inline below each finding.

## 2. Hard filter applied to every named category

Criteria (packet's own numbering): (1) pre-cutoff available, (2) historically
recoverable or forward-collectible, (3) not leaked from the target, (4) not
just another transform of historical winning numbers, (5) plausible mechanism
for P(match)/candidate quality, (6) not pure payout/EV.

### A. EQUIPMENT / PROTOCOL — FAILS (1) at per-draw grain, narrow exception carried forward

Verified directly from Taiwan Lottery's own draw-process page: an independent
notary ("公正人士") inspects the draw machine and number balls, then a draw
guest live-selects the draw machine, ball set, **and** ball-drop order, as one
bundled, on-air ceremony — not three separately-timed events. This is the same
mechanism the predecessor task already dated to after the 20:00 cutoff, so
machine ID and loading order/direction share ball-set ID's exact timing
problem; the packet's own instruction not to switch to them "just because
visible in video" is confirmed correct rather than merely assumed. No
published *fixed* rotation/assignment schedule exists anywhere found — the
official page is silent on total machine/ball-set inventory size, and the
live-guest-selection design is itself the anti-gaming mechanism (you cannot
game equipment-specific bias if which equipment will run tonight is unknown
until after betting closes). Maintenance/replacement history at per-draw grain:
not disclosed anywhere found.

One narrow sub-question survives at a *different* grain — not per-draw
assignment, but whether the physical equipment *pool itself* was ever replaced
at a period boundary. Carried forward as Direction 2 below, not dropped
silently.

### B. OPERATIONAL ENVIRONMENT — FAILS (5): available but constant, not discriminating

Verified: fixed weekly schedule (威力彩/P638 Mon+Thu; 大樂透/B649 Tue+Fri;
今彩539/T539 Mon–Sat), one venue for all three games (SET News — 三立新聞台
— Studio 5), one broadcast window (20:30–21:00), independent-notary
supervision. All of this is published well ahead of any cutoff and covers the
full sample — so it passes (1) and (2) trivially. It fails (5): venue,
time-slot structure, and supervision protocol are the same for essentially
every draw of a given game across the entire sample. A covariate that does not
vary cannot explain variation in an outcome; this is a structural
information-content failure, not a data-availability one, so no further
acquisition work would change the verdict.

### C. STRATEGY-EXTERNAL PUBLIC DATA — FAILS (5) by construction, not pursued deeper

Considered: public equipment-procurement or inventory disclosure (Taiwan
Lottery operates under public-procurement rules in principle). Not deep-dived,
because even if such records are public, they would at best reveal *pool
size* (how many machines/ball-sets exist in rotation) — not *which one* runs
on a specific future date, since Category A already confirms that selection is
a live, guest-run, notary-witnessed draw-within-the-draw. A known pool size
under confirmed uniform-random selection matches, rather than beats, the null
model this project's own uniformity battery has already exhaustively failed
to reject. Going further here would be "hunting harder for metadata" after the
mechanism that would make it useful is already ruled out — exactly what the
packet says not to do.

### D. CROSS-LOTTERY NATIVE INFORMATION — CLOSED (verified, not merely unchecked)

This is the one category with a genuinely new empirical answer this session.
Verified directly from the official draw-process page: 今彩539 (T539) is
explicitly listed together with 大樂透 (B649) and 威力彩 (P638) as one of the
"依序開出" (sequentially-drawn) games — i.e. **the same mechanical,
mediated-by-live-guest ball-draw ceremony**, not a different computerized or
electronic process. All three share venue, notary process, and (by the
predecessor task's already-established FAQ finding) the same cutoff-to-draw
timing gap. There is no B649-lacks/T539-or-P638-has asymmetry at the
equipment/ceremony/venue level. This closes D with evidence, rather than
leaving it an open question, which is itself a useful (if negative) result.

### E. DIFFERENT PREDICTIVE TARGET REPRESENTATION — NOT RE-SELECTED (already adjudicated today)

This category was already run down and explicitly rejected earlier the same
day by this project's own most recent same-substrate synthesis
(`[[track-d-cross-lottery-higher-order-synthesis-r1]]`), immediately *after*
triple- and quadruple-wise joint-uniformity tests came back
`NO_DETECTABLE_HIGHER_ORDER_DEPARTURE` on all three lotteries. Checking the
packet's own E examples against that finding:

- "pair/set conditional target" is exactly what the already-run,
  already-null `C(49,2)`/`C(49,3)`/`C(49,4)` Holm-corrected joint-structure
  battery tested directly.
- "exclusion/negative target" (predict what will *not* be drawn) is the exact
  complement of the already-confirmed-uniform "drawn" indicator —
  `P(excluded) = 1 − P(included)` — so it carries the same, already-absent,
  information.
- "relative candidate quality" (pairwise preference between two tickets)
  reduces to the difference of two already-confirmed-uniform absolute match
  probabilities, zero in expectation under the same null.

I re-derive this independently rather than take the prior document's
conclusion on faith, because its own phrasing ("mathematically can't add
information") overstates the case: matching uniform on all order-≤4 structure
does not *formally* rule out a departure that appears only at order 5 or 6 —
that is a real, narrow logical gap (this is a known fact about combinatorial
designs — you can construct a distribution over k-subsets that is uniform on
every margin up to some order and still non-uniform jointly). But producing
that specific signature — invisible below order 5, present only at order 6 —
requires a deliberately, adversarially constructed combinatorial code. A
physical, notary-witnessed, tolerance-certified mechanical process (ball
weight tested to 0.1 mg, diameter/surface-uniformity checked, per standard
industry practice) has no known way to produce that surgical a signature by
accident; real physical biases show up at low orders first, which is exactly
where this project's battery already looked hardest and found nothing. So the
practical conclusion holds even with the overclaim removed: expected value is
very low, not formally zero. E is not re-selected here — not because it is
forbidden, but because re-selecting it would silently ignore this project's
own same-day, already-reasoned rejection without adding anything new.

## 3. Prior-pass candidate ranking (recovered, superseded by Section 4)

### 1. Post-2023 external regime/provenance reconciliation (prior-pass rank 1)

TITLE: Reconcile the already-observed, still-unexplained post-2023
static-consensus M2+ step against two newly-verified external facts, instead
of treating it as an unexplained internal statistical artifact.

INFORMATION_SOURCE: Two independently verified, non-draw-history facts, both
landing on the same boundary this project has already been staring at without
an external explanation: (a) Taiwan's public-lottery concession was awarded
for its 5th term on **2022-08-15**, effective **2024-01-01**, per the
Ministry of Finance's own selection-committee record (same operator,
中國信託-led consortium, continuing across all three terms since 2007 — this
is a contract renewal, not an operator swap); (b) the official 全民i彩券
livestream archive — already used by the predecessor ball-set task — starts
its "oldest" sort at exactly `【20240101】`, i.e. the same date. Neither fact
is asserted here as confirmed cause; both are newly on the table as candidate
explanations that nobody in this lineage checked, because
`B649_TRACK_D_POST2023_CONSENSUS_ALIGNMENT_MECHANISM_R1` explicitly checked
only *internal* candidates ("No strategy availability, identity, family-mix,
implementation-version, schema, or consensus-composition boundary coincides
with 2023") and stopped there.

PRE_CUTOFF_AVAILABLE: YES — the concession term and the livestream channel's
existence are public administrative facts, known from 16+ months before
2024-01-01 onward; this is not information about any single future draw, it
is a fixed calendar fact usable to explain a *historical* discontinuity and to
scope which historical window is valid to model from, going forward.

HISTORICAL_COVERAGE: Full — both facts are already fixed, public record, and
the boundary they land on is already inside this project's existing,
already-computed pre/post-2023 statistics.

WHY_ORTHOGONAL: Neither fact is a transform of the draw-number sequence, is
leaked from any target outcome, or is payout/EV information. Both are
external administrative/data-pipeline facts about the *lottery operator and
this project's own ingestion*, not about which numbers came up.

WHY_IT_COULD_IMPROVE_P_MATCH: Indirectly, and this must be stated plainly
rather than oversold — this is not a new predictive feature. The already-noted
caveat in the alignment-mechanism report itself is correct: "calendar date
itself already reveals era, so era classification is not a useful prediction
product" — you cannot bet on knowing what today's date is. The value is in
resolving *which* of three explanations is true, because each has a different,
real downstream consequence for P(match)-relevant modeling: (i) if the step
tracks a genuine, ongoing regime change tied to the 5th concession term
(which runs through 2033), that argues for treating post-2024 draws as the
only valid training population for any future B-track mechanism — a
legitimate, non-speculative reason to discard nothing but stop diluting a
possibly-real recent regime with a possibly-different older one; (ii) if the
step instead tracks a data-provenance discontinuity in this project's own
historical corpus (plausible: the same memory index already flags this
lottery's history as "46% format-contaminated" elsewhere in this lineage, and
this exact boundary is also where the project's own data-source infrastructure
changed), that is a data-quality finding, arguing for remediation or explicit
discounting of the post-2023 anomaly rather than building on it; (iii) if
neither, this is coincidence and the anomaly is further downgraded. All three
outcomes are decision-relevant; none of them is "just re-deriving that it's
currently past a certain date."

DATA_READINESS: HIGH for the recon step itself (both external facts are
already verified this session; the existing pre/post-2023 statistics already
exist in-repo/in-workspace) — but the recon must first verify one thing this
session did not have scope to check: whether the "post-2023" boundary in the
original static-consensus mining work was chosen a priori or discovered via
search over candidate cutpoints. If it was search-discovered, the coincidence
with the verified concession-term date is far less informative (a searched
"recent vs. older" split in a ~19-year sample will often land near "the last
2–3 years" for reasons having nothing to do with lottery administration), and
that must be stated in the recon's own output, not glossed over.

IMPLEMENTATION_COST: LOW — no new data ingestion, no fitting, no B experiment;
reuses already-computed pre/post-2023 statistics and adds one boundary-
provenance check plus one data-pipeline-provenance check (does this project's
own draw-source ingestion change at the same date, independent of the
official archive's own start date).

### 2. Equipment-pool replacement at concession-term boundaries (Category A, narrow exception)

TITLE: Verify whether Taiwan Lottery has ever publicly disclosed an actual
physical ball-set/machine *pool* replacement, particularly at the 2014 or 2024
concession-term boundaries — a different grain than the per-draw live
assignment Category A closes above.

INFORMATION_SOURCE: Public disclosure (press release, annual report, or
government procurement announcement), if any exists, of physical draw-
equipment replacement tied to a concession renewal.

PRE_CUTOFF_AVAILABLE: Would be YES if such disclosures exist and precede the
relevant draws by the normal public-notice lag — unconfirmed either way this
session.

HISTORICAL_COVERAGE: Unknown — not located this session; the official
draw-process page is silent on equipment inventory and turnover.

WHY_ORTHOGONAL: Same reasoning as Direction 1 — public administrative/
procurement record, not a draw-number transform, not EV.

WHY_IT_COULD_IMPROVE_P_MATCH: Same weak, indirect mechanism as Category A/B in
general (a possible physical bias shift at a verified date) — ranked below
Direction 1 because the operator itself is confirmed unchanged across all
three concession terms (same 中國信託-led entity since 2007; this is a
contract renewal, not a new operator with new equipment by default), so a
physical-equipment-turnover event at these specific dates is an unconfirmed,
weaker bet than Direction 1's already-partially-evidenced anomaly.

DATA_READINESS: LOW — would need a small, bounded search of Taiwan Lottery
press releases/annual reports and, if relevant, the public government
e-procurement system, before anything else.

IMPLEMENTATION_COST: LOW for the recon; NOT SCOPED beyond it.

### 3. T539/P638 cross-lottery equipment-ceremony check (Category D, documented closure)

TITLE: Confirm whether T539 or P638 carries any pre-cutoff equipment/ceremony
asymmetry B649 lacks.

INFORMATION_SOURCE: Official Taiwan Lottery draw-process documentation.

PRE_CUTOFF_AVAILABLE: N/A — resolved negative; no asymmetry found.

HISTORICAL_COVERAGE: N/A.

WHY_ORTHOGONAL: N/A — included for completeness because the packet explicitly
asked this category be checked "at least."

WHY_IT_COULD_IMPROVE_P_MATCH: None — CLOSED. All three lotteries share one
ceremony, one venue, one notary-supervision process, and (per the predecessor
task) the same cutoff-to-draw timing gap. Ranked third only because it is
already resolved, not because it is weak; a definitive negative answer here
is real research value, matching this project's own established practice of
reporting closures as first-class results rather than silently dropping them.

DATA_READINESS: N/A — answered.

IMPLEMENTATION_COST: NONE — no further work warranted on this specific
question.

## 4. Continuation validation and final selection

This section is the bounded continuation delta requested after the prior
agent exhausted quota. It does not reopen the document inventory or the
ball-set feasibility work.

### 4.1 Concession boundary and pre-cutoff status — CONFIRMED

- [Confirmed] The [Ministry of Finance/National Treasury Administration award
  release](https://www.nta.gov.tw/singlehtml/238?cntId=3615ac87a1ae43b1892868261ed7c2d6)
  records the selection meeting on **2022-08-15**, ChinaTrust's award, and the
  fifth-term operating period **2024-01-01 through 2033-12-31**.
- [Confirmed] The NTA's [lottery-business history](https://www.nta.gov.tw/singlehtml/244?cntId=nta_17272_244)
  and Taiwan Lottery's [official results archive](https://apislb.taiwanlottery.com/lotto/history/result_download/)
  independently partition the fourth term as 2014–2023 and the fifth as
  2024–2033. The operator remains ChinaTrust; this is a concession-term
  boundary, not an operator replacement.
- [Confirmed] The boundary was public more than sixteen months before it took
  effect. `CONCESSION_TERM / PROTOCOL_VERSION ERA` is therefore genuinely
  pre-betting-cutoff metadata. This does **not** make the calendar boundary a
  physical predictor by itself.

### 4.2 Equipment/protocol change at the boundary — UNKNOWN

- [Confirmed] Taiwan Lottery's [official FAQ](https://apislb.taiwanlottery.com/customer_service/faq/)
  says that from 2024 (`113年`) draws were broadcast through Sanli iNews and
  Ernst & Young served as the independent draw-and-payout witness. That is a
  real operating/oversight arrangement aligned with the concession boundary.
- [Confirmed] The same FAQ explicitly says the on-site draw workflow remained
  unchanged from before. It identifies current machines as Smartplay equipment
  under monthly maintenance and annual manufacturer inspection, but gives no
  acquisition, fleet-replacement, or ball-inventory turnover date.
- [Confirmed] The [official draw-process page](https://www.taiwanlottery.com/run_lottery/info/)
  still describes the same notary inspection followed by live selection of
  machine, ball set, and loading order. Those per-draw selections remain
  after the betting cutoff and therefore unusable for live prediction.
- [Not found] This bounded search located no official record of a 2024 machine-
  fleet replacement, ball-inventory refresh, venue change, or changed physical
  draw sequence.
- [Unknown] Whether an undisclosed equipment-pool or ball-inventory turnover
  occurred near 2024. Absence from the bounded public search is not proof that
  it did not occur.

`UNKNOWN` is therefore the truthful aggregate status required by the handoff:
a preannounced administrative boundary and a boundary-aligned, non-physical
broadcast/notary arrangement are verified, but an equipment or on-site
draw-protocol change capable of supplying a P(match) mechanism is not.

### 4.3 Decision

Select **PROTOCOL_CONCESSION_ERA_MECHANISM_FEASIBILITY** as one cheap,
read-only follow-up. The task is a timeline/evidence reconstruction only:
determine whether the 2024 transition coincided with an externally verifiable
change in equipment, machine fleet, ball inventory, venue, draw protocol, or
operating procedure that was knowable before draws. Do not fit `year >= 2024`,
an era classifier, or any prediction model.

The existing post-2023 consensus lift, concession transition, and official
livestream start form an **observed development association**, not causal
evidence. If the feasibility task finds no physically or procedurally relevant
change, close this line as `NO_USEFUL_PRE_CUTOFF_EXTERNAL_METADATA_FOUND`.

## 5. What was explicitly not done

No large-scale scraper engineering. No acquisition of ball-set/machine footage
beyond what the predecessor task already sampled. No repo or DB writes. No
statistical re-test executed — this is a direction selection, not the
reconciliation itself. No re-litigation of already-closed higher-order,
family-diversity, or tuned-mechanism findings.

---

## FINAL

```text
TASK_ID:
B649_TRACK_D_PRE_CUTOFF_ORTHOGONAL_INFORMATION_RESELECTION_R1

STATUS:
PASS

CONTINUATION:
RESUMED_FROM_QUOTA_EXHAUSTED_AGENT

BALL_SET_LIVE_RESEARCH:
DEPRIORITIZED

CONCESSION_BOUNDARY:
2024-01-01

CONCESSION_PREANNOUNCED:
YES

CONSENSUS_PERIOD_ALIGNMENT:
OBSERVED_DEVELOPMENT_ASSOCIATION

EQUIPMENT_OR_PROTOCOL_CHANGE_AT_BOUNDARY:
UNKNOWN -- a non-physical 2024 broadcast/notary arrangement is verified, but
a machine-fleet, ball-inventory, venue, or physical draw-procedure change is
NOT_FOUND in the bounded public search and remains UNKNOWN as an undisclosed
event.

TOP_3_NEXT_DIRECTIONS:
1. PROTOCOL_CONCESSION_ERA_MECHANISM_FEASIBILITY -- SELECTED; cheap external
   evidence/timeline reconstruction only.
2. POST_2023_EXTERNAL_REGIME_AND_DATA_PROVENANCE_RECONCILIATION -- previously
   supported secondary direction, but broader than the missing final check.
3. NO_USEFUL_PRE_CUTOFF_EXTERNAL_METADATA_FOUND -- closure outcome if #1 finds
   no P(match)-relevant physical or procedural change.

NEXT_RESEARCH_DIRECTION:
PROTOCOL_CONCESSION_ERA_MECHANISM_FEASIBILITY

WHY_THIS_DIRECTION_NOW:
The concession boundary is official and preannounced, and a boundary-aligned
broadcast/notary arrangement is verified, while the physical equipment and
on-site protocol question remains unresolved. One bounded mechanism check is
therefore justified before either closing external metadata or interpreting
the observed post-2023 alignment. The alignment is not stated as causation.

PRE_BETTING_CUTOFF_AVAILABLE:
YES -- for the concession term and any publicly announced operating change.
NO -- for per-draw machine, ball-set, and loading-order selection, which
remains post-cutoff.

WHY_IT_COULD_AFFECT_P_MATCH:
Only a verified change in the physical equipment pool, ball inventory, or
draw procedure could define a different physical regime and justify revising
which historical draws are comparable for P(match) work. The concession date,
broadcaster, and notary identity alone do not change P(match) and must not be
used as predictors.

DATA_READINESS:
MEDIUM for cheap mechanism feasibility: official concession, current process,
broadcast, and oversight records are available. LOW / NOT READY for predictive
use because equipment-fleet and ball-inventory turnover evidence is absent.

NEXT_TASK_TRACK:
D

NEXT_TASK_ID:
B649_TRACK_D_CONCESSION_PROTOCOL_ERA_MECHANISM_FEASIBILITY_R1

COHORT_V2_PROSPECTIVE_DATA_USED:
NO

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

OUTPUT:
B649_TRACK_D_PRE_CUTOFF_ORTHOGONAL_INFORMATION_RESELECTION_R1.md

BLOCKERS:
NONE

END
```
