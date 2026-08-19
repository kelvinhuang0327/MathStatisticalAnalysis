# B649 Track D — Post-Jackpot Era-Confound Successor Reselection R1

TASK_ID: `B649_TRACK_D_POST_JACKPOT_ERA_CONFOUND_SUCCESSOR_RESELECTION_R1`
MODE: `READ_ONLY_RESEARCH_DECISION`
ROLE: `Track D — Research Direction Optimizer`
DATE: `2026-08-16`

## Decision

`NEXT_RESEARCH_DIRECTION: DRAW_ORDER_POSITION_SEMANTIC_AND_COVERAGE_VALIDATION`

This is a small, bounded prerequisite—not a prediction experiment, schema
migration, historical backfill, or Level-2 run. It is selected because
`drawNumberAppear` is the only candidate inspected here that can add a raw
information channel not present in the sorted B649 history used by the prior
research lines. Its semantics are not yet strong enough to authorize a Track B
test, so the next task belongs to Track A.

The fallback is explicitly pre-registered as
`B649_TRACK_B_EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE_R1` if the bounded
semantic/coverage check fails.

## Current evidence and decision boundary

`LATEST_B_RESULT: WEAK_SIGNAL / DO_NOT_ADVANCE`

The pre-draw jackpot/rollover Level-1 result was positive against baseline
(94/300 versus 79/300, +5.00 percentage points), but the real signal was
beaten by the calendar-year era control (104/300). The real feature also beat
the stale and shuffled placebos. Therefore the result supports chronological
or regime information, not an independent jackpot/rollover mechanism.

`ERA_CONFOUND_CONFIRMED_AS_LOAD_BEARING: YES`

The common development benchmark `113000006–115000069` is retained as a
development/comparison/falsification benchmark only. It is not an untouched
holdout or clean confirmation. `COHORT_V2` prospective outcomes are not used.

The bounded local reproduction of the source-readiness evidence passed all 9
checks. The relevant observations are:

- The official API currently returns `drawNumberAppear` alongside
  `drawNumberSize`; a live bounded query returned three August 2026 records.
- Across the seven saved records from 2007, 2015, and 2026,
  `drawNumberAppear` is a permutation of `drawNumberSize` in 7/7 records and
  preserves the special-number last slot in 7/7 records.
- The production adapter reads only `drawNumberSize`, sorts the six main
  numbers, and has no positional field in `ProviderDrawRecord` or the `draws`
  schema. This source is therefore absent from the stored strategy substrate,
  not merely a new transform of an existing stored feature.
- The official draw-process page confirms that B649 is a sequential physical
  draw and that the guest selects the ball-drop order. It does not, however,
  define the API field `drawNumberAppear` or map it to the physical sequence.

### `SEMANTIC_STATUS` for `drawNumberAppear`

`UNKNOWN / NOT_PHYSICAL_ORDER_CONFIRMED`.

What is confirmed: it is non-sorted and set-preserving in the sampled official
payloads. What is not confirmed: whether it is physical ball-drop order,
on-screen reveal order, display order, or an API presentation convention. The
field must not be treated as physical order until the bounded prerequisite
resolves this mapping or explicitly concludes that it cannot be resolved.

Primary-source anchors:

- Official draw process: <https://www.taiwanlottery.com/run_lottery/info/>
- Official B649 result page: <https://apislb.taiwanlottery.com/lotto/result/lotto649/>
- Official API endpoint used by the adapter:
  <https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result>

## Required candidate comparison

The comparison uses the reconciled Frontier artifacts already present in the
workspace. It does not repeat the 49-item Frontier audit.

### Direction A — draw-order/position history

TITLE: `DRAW_ORDER_POSITION_SEMANTIC_AND_COVERAGE_VALIDATION`

TYPE: Genuinely new raw information source, conditional on semantic
verification.

NEW_INFORMATION_SOURCE: The per-draw non-sorted API sequence
`drawNumberAppear`, which is currently discarded before canonical storage.

SEMANTIC_READINESS: `UNRESOLVED`; source presence is `CONFIRMED` in bounded
official payloads, physical-order mapping is `UNKNOWN`, and historical
coverage is `PARTIAL` rather than exhaustive.

ERA_PROXY_RISK: `LOW` a priori for a within-draw order channel. Apply the
standard era-stratified check after acquisition; do not assume physical
stability across ball-set or equipment regimes.

OVERLAP_WITH_PRIOR_FAILED_LINES: `NONE` at the raw-information level. Prior
frequency/gap/deviation, temporal/state, consensus, cross-lottery-lag,
structured legal-set, and jackpot/rollover lines use sorted outcomes or
derived strategy emissions. They do not retain this order-like field.

DIRECT_M2_M3_PATH: Uncertain but direct after the prerequisite. If the field
is verified as causal prior-draw order, test a fixed order-transition or
position-bias scorer that emits exactly one legal B649 ticket. The mechanism
could be a stable ball/position bias, but ball-set selection makes that a
hypothesis rather than an assumption.

TRANSFER_POTENTIAL: `MEDIUM-HIGH` if a physical or source-stable ordering
property is found; the same idea could be checked on T539/P638 only after
their endpoint semantics and coverage are independently verified.

IMPLEMENTATION_COST: `LOW` for the bounded read-only prerequisite; `MEDIUM`
for a conditional schema-versioned ingestion/backfill and Track B test.

### Direction B — best remaining unexecuted Frontier hypothesis

TITLE: `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`

TYPE: New statistical mechanism over existing information; not a new raw
information source.

NEW_INFORMATION_SOURCE: None. It scans the existing causal B649 draw/strategy
residual substrate for a sparse localized departure and gates an existing
candidate action.

SEMANTIC_READINESS: `READY_DERIVABLE`; no new source semantics or ingestion is
needed. The reconciled Frontier record marks EH27
`NOT_EXECUTED_PROPOSED_ONLY`, with a fast-falsification specification and no
exact match in the full 133-identity collision comparison.

ERA_PROXY_RISK: `LOW-MEDIUM` only with train-only calibration and explicit
era-stratified controls. The gate/action shape has already produced repeated
era/stale-control failures on this population, including the current jackpot
result.

OVERLAP_WITH_PRIOR_FAILED_LINES: `LOW-MEDIUM` semantically. Sparse subset
scanning is not the same as global uniformity, ordinary frequency/gap, or a
fixed change-point detector, but it still consumes the same sorted history and
ends in the same regime-gate/action family.

DIRECT_M2_M3_PATH: `INDIRECT`. It can select or abstain among existing ticket
generators; it does not create a new ticket signal. Any experiment must use one
fixed scan specification, one fixed action, and one-ticket M2+ as the primary
endpoint with M3+ non-deterioration.

TRANSFER_POTENTIAL: `MEDIUM`; the localized-departure idea is portable, but
transfer remains exposed to the same chronological regime problem.

IMPLEMENTATION_COST: `LOW-MEDIUM`; standard scan-statistic/higher-criticism
machinery plus a causal read-only replay and placebo controls.

### Direction C — genuinely new external pre-target information

TITLE: `PRE_CUTOFF_PER_NUMBER_CROWD_CHOICE_OR_SALES_TELEMETRY_DISCOVERY`

TYPE: Potentially genuinely new external pre-target information source, but
currently a feasibility candidate rather than a runnable research direction.

NEW_INFORMATION_SOURCE: Per-number or per-combination player-choice/sales
telemetry observed before the target betting cutoff. This would be distinct
from historical winning-number transforms, calendar/era labels, strategy
emissions, and post-draw winner-count metadata.

SEMANTIC_READINESS: `UNAVAILABLE / UNVERIFIED`. The official payloads inspected
contain aggregate sales and settled prize fields, not pre-cutoff per-number
choice data. Same-draw `winnerCount`, `perPrize`, and realized sales fields
cannot be promoted to pre-target inputs; they are post-draw or lag-only.

ERA_PROXY_RISK: `LOW` only if the source is genuinely per-draw, pre-cutoff,
and timestamped. A vendor index or slowly changing market proxy would be
`HIGH` risk and would fail this candidate's novelty requirement.

OVERLAP_WITH_PRIOR_FAILED_LINES: `NONE` in concept, but there is no verified
usable source to test. The already-tested advertised jackpot/rollover state is
excluded: it is closed as `WEAK_SIGNAL / DO_NOT_ADVANCE` and is not a rescue
candidate.

DIRECT_M2_M3_PATH: `WEAK / UNKNOWN`. Player choice can plausibly affect payout
sharing or combination exposure, but no verified mechanism says it changes the
physical B649 draw distribution. It must not substitute payout/EV for the
required one-ticket M2+ metric.

TRANSFER_POTENTIAL: `LOW-MEDIUM`, dependent on finding an operator- or
vendor-independent source with equivalent pre-cutoff semantics in other
lotteries.

IMPLEMENTATION_COST: `HIGH / UNKNOWN`; source discovery, provenance, historical
coverage, timestamp alignment, and likely access constraints come before any
predictor. No large scraping project is authorized by this packet.

### Direction D — materially different prediction objective/generation

TITLE: `H16_JOINT_MAIN_SPECIAL_CONDITIONAL_LEGAL_TICKET_GENERATOR`

TYPE: Different prediction objective and generation mechanism from the failed
structured legal-set quality target.

NEW_INFORMATION_SOURCE: None; it uses the existing B649 draw history. Its
novelty is a joint main-number/special-number conditional output and a legal
full-ticket generator, not a new data source.

SEMANTIC_READINESS: `PARTIAL`. Main and special outcomes exist, but the
reconciled Frontier record reports no canonical joint legal-ticket output
contract and marks H16 `NOT_EXECUTED`.

ERA_PROXY_RISK: `LOW-MEDIUM` under strict chronological folds, but it inherits
the same finite sorted-history substrate and must include era-stratified
diagnostics.

OVERLAP_WITH_PRIOR_FAILED_LINES: `LOW` at the exact target/generator level;
the joint special-aware contract is materially different from structured
main-number candidate-set quality. It still shares the same raw history, so a
positive result would not establish a new external cause.

DIRECT_M2_M3_PATH: `MEDIUM` after a new legal constructor is specified. The
main-number component can affect M2+/M3+; the special component is mainly a
secondary depth/contract dimension and cannot be allowed to obscure the main
ticket metric.

TRANSFER_POTENTIAL: `LOW-MEDIUM`; special-number semantics do not transfer
directly to T539, and P638 has a different special/zone contract.

IMPLEMENTATION_COST: `MEDIUM-HIGH`; it requires a new joint output schema,
legal constructor, score semantics, and causal replay.

## TOP_3_NEXT_DIRECTIONS

1. `DRAW_ORDER_POSITION_SEMANTIC_AND_COVERAGE_VALIDATION` — only candidate with
   a genuinely new raw channel; the unresolved semantic and coverage questions
   are bounded and load-bearing.
2. `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE` — best immediately
   researchable Frontier survivor, but same-substrate and indirect.
3. `H16_JOINT_MAIN_SPECIAL_CONDITIONAL_LEGAL_TICKET_GENERATOR` — materially
   different objective/generation fallback, but partial contract readiness and
   higher cost make it a long shot.

The external pre-cutoff crowd-choice/sales candidate is intentionally not in
the top three: it is genuinely distinct in concept but has no verified source,
timestamped history, or direct M2+/M3+ mechanism. It should not be turned into
a speculative scraping project.

## Selection

NEXT_RESEARCH_DIRECTION: `DRAW_ORDER_POSITION_SEMANTIC_AND_COVERAGE_VALIDATION`

WHY_THIS_DIRECTION_NOW:

The jackpot result closes the current advertised-rollover hypothesis and
confirms that era control is load-bearing. The remaining saturated lines keep
reusing sorted B649 outcomes, slow state labels, or strategy-family outputs.
`drawNumberAppear` is the only bounded candidate here that may expose a raw
within-draw channel not represented in that substrate. A null result would also
close a real, previously unexamined data channel rather than repeat another
model transform. Because the field's semantics and coverage are unresolved,
the correct next action is a small prerequisite rather than an immediate Track
B experiment.

WHY_NOT_DIRECTION_2:

EH27 is a credible open Frontier hypothesis and remains the explicit fallback,
but it changes the detector/gate, not the information set. It therefore
inherits the current population's repeated stale/era-control failure mode and
has no new-ticket-content path. It should run only if the order source fails
the prerequisite or after the order line is closed.

WHY_NOT_DIRECTION_3:

H16 is more materially different from the failed structured legal-set target,
but its legal joint main/special contract is not ready and its implementation
cost is materially higher. It also remains a same-history method, so it does
not address the primary post-jackpot question of finding genuinely new raw
information.

WHY_NOT_EXTERNAL_PRE_TARGET_DIRECTION:

The only plausible external pre-target source found in the bounded inventory
would be genuine per-number crowd-choice/sales telemetry. It was not found in
the official API, local schema, or existing strategy provenance. Aggregate
post-draw winner/payout fields and the already-failed jackpot state are not
valid substitutes. Without a verified source and mechanism, it is not a
research-ready direction.

REQUIRED_PREREQUISITE:

Run a bounded, read-only Track A validation before any ingestion or predictor:

1. Query the same official `Lotto649Result` endpoint across a stratified sample
   covering all established B649 era blocks, not only the three existing spot
   windows.
2. Check period alignment, field presence, same-multiset integrity,
   non-degeneracy, special-slot behavior, pagination/`totalSize` semantics, and
   missingness.
3. Search the official process/result documentation and perform only a small
   number of targeted broadcast/result cross-checks for the mapping from
   `drawNumberAppear` to physical drop order.
4. Stop without schema migration, bulk backfill, Track B scoring, Level 2, or
   Cohort V2 use if the mapping cannot be resolved or coverage is materially
   era-concentrated.

DISCOVERY_MODE: `BOUNDED_READ_ONLY_SEMANTIC_AND_COVERAGE_PREREQUISITE`

DATA_TO_USE:

- Existing canonical/sealed B649 history for period/date joins.
- Fresh read-only official API payloads for `drawNumberAppear` and
  `drawNumberSize`, stratified across the history.
- Official draw-process/result documentation and a bounded broadcast cross-check
  only if needed for semantics.
- Exclude Cohort V2 prospective outcomes, target-draw order, post-draw fields,
  production DB writes, schema migration, and large scraping.

PRIMARY_SUCCESS_METRIC:

Downstream, one-ticket M2+ improvement versus a locked no-order-feature
baseline on newly available forward targets; the prerequisite pass metric is
verified broad historical coverage and resolved physical-order semantics.

SECONDARY_SUCCESS_METRIC: M3+ must not materially deteriorate versus the locked
baseline.

STOP_OR_PIVOT:

Stop the order line before ingestion or Track B if the field is missing or
degenerate in material eras, API pagination cannot be trusted, or physical
order semantics remain unresolved after the bounded primary-source check.
Pivot to `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE` under a separately
authorized Track B packet. A positive feasibility result does not authorize a
prediction experiment by itself.

NEXT_TASK_TRACK: `TRACK_A`
NEXT_TASK_ID: `B649_TRACK_A_DRAW_ORDER_POSITION_COVERAGE_VALIDATION_R1`

## Final

TASK_ID: `B649_TRACK_D_POST_JACKPOT_ERA_CONFOUND_SUCCESSOR_RESELECTION_R1`
STATUS: `COMPLETE — EXACTLY_ONE_DIRECTION_SELECTED`

LATEST_B_RESULT: `WEAK_SIGNAL / DO_NOT_ADVANCE`
ERA_CONFOUND_CONFIRMED_AS_LOAD_BEARING: `YES`
TOP_3_NEXT_DIRECTIONS:
  1. `DRAW_ORDER_POSITION_SEMANTIC_AND_COVERAGE_VALIDATION`
  2. `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`
  3. `H16_JOINT_MAIN_SPECIAL_CONDITIONAL_LEGAL_TICKET_GENERATOR`
NEXT_RESEARCH_DIRECTION: `DRAW_ORDER_POSITION_SEMANTIC_AND_COVERAGE_VALIDATION`
WHY_THIS_DIRECTION_NOW: only bounded candidate with a potentially genuinely new
raw information channel after the jackpot/era-confound result
REQUIRED_PREREQUISITE: read-only, stratified official-source coverage and
physical-order semantic validation of `drawNumberAppear`
NEXT_TASK_TRACK: `TRACK_A`
NEXT_TASK_ID: `B649_TRACK_A_DRAW_ORDER_POSITION_COVERAGE_VALIDATION_R1`
COHORT_V2_PROSPECTIVE_DATA_USED: `NO`
REPO_MUTATION: `NONE` — no source, test, config, strategy, Git, or database
mutation; this file is the required task report artifact
DB_MUTATION: `NONE`

## Evidence ledger

Opened/read during this task:

- `.task-data/B649_TRACK_B_PREDRAW_JACKPOT_ROLLOVER_PREDICTION_LEVEL1_R1/report.md`
- `.task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/report.md`
- `.task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/reproduce_analysis.py`
- `.task-data/B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1/report.md`
- `src/lottolab/infrastructure/taiwan_lottery_draw_provider.py`
- `src/lottolab/application/draw_automation.py`
- `src/lottolab/infrastructure/persistence/draw_schema.py`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_POST_EH01_EH10_EH02_SUCCESSOR_RESELECTION_R1.md`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_NORMALIZED_R1.csv`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1.md`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_REMAINING18_FAST_FALSIFICATION_SPECS_R1.md`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_PRE_CUTOFF_ORTHOGONAL_INFORMATION_RESELECTION_R1.md`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_CONCESSION_PROTOCOL_ERA_MECHANISM_FEASIBILITY_R1.md`

Verification run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 .task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/reproduce_analysis.py
SUMMARY: 9 checks, 9 passed, 0 failed, 0 skipped
```

External read-only source checks:

- A live bounded `curl` query to the official API returned `rtCode: 0`, three
  B649 rows, and both `drawNumberSize` and `drawNumberAppear`.
- The official process page was opened; it confirms sequential B649 draw
  handling and guest-selected ball-drop order, but not the API-field mapping.

Unknowns retained honestly:

- Full historical API coverage and `totalSize`/pagination semantics are not
  confirmed.
- `drawNumberAppear` physical-order semantics are not confirmed.
- No predictive advantage is claimed for order, EH27, H16, or any external
  market source.

Filesystem accounting:

```text
FILES_WRITTEN_DURING_TASK: B649_TRACK_D_POST_JACKPOT_ERA_CONFOUND_SUCCESSOR_RESELECTION_R1.md
FILES_RETAINED_AT_END: B649_TRACK_D_POST_JACKPOT_ERA_CONFOUND_SUCCESSOR_RESELECTION_R1.md
FILES_DELETED_BEFORE_END: NONE
PRE_EXISTING_FILES_RETAINED_UNCHANGED: all pre-existing dirty paths and task artifacts
REPOSITORY_FILES_MODIFIED: NONE — required report artifact only
DB_MUTATION: NONE
```
