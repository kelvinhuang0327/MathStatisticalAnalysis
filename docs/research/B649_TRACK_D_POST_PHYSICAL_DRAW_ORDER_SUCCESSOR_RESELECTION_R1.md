# B649 Track D — Post-Physical Draw Order Successor Reselection R1

TASK_ID: `B649_TRACK_D_POST_PHYSICAL_DRAW_ORDER_SUCCESSOR_RESELECTION_R1`
MODE: `READ_ONLY_RESEARCH_DECISION`
ROLE: `Track D — Research Direction Optimizer`
DATE: `2026-08-16`
STATUS: `COMPLETE — EXACTLY_ONE_DIRECTION_SELECTED`

## Physical-order closeout

PHYSICAL_DRAW_ORDER_LINE_STATUS: `CLOSED`

PHYSICAL_DRAW_ORDER_PREDICTIVE_INCREMENT: `NONE`

[Confirmed] The Level-1 result reports `BASELINE_M2_PLUS=79/300`,
`REAL_ORDER_M2_PLUS=91/300`, `ORDER_SHUFFLED_M2_PLUS=98/300`,
`SET_ONLY_CONTROL_M2_PLUS=92/300`, and `M3_PLUS` values of 11, 9, 12, and 8
for baseline, real order, shuffled order, and set-only respectively. The real
order uplift over baseline therefore cannot be attributed to physical-order
information: the shuffled placebo is higher and the set-only control is
essentially equal.

[Confirmed] The physical-order source semantics and source-side coverage had
already passed Track A validation. This decision therefore closes a predictive
line, not a source-readiness question. The common benchmark
`113000006–115000069` remains development/comparison/falsification data only;
it is not untouched confirmation. Cohort V2 prospective outcomes are not used.

## EH27 authority resolution

EH27_CANONICAL_TITLE: `SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`

EH27_STATUS: `READY_NOW`

EH27_BLOCKER_IF_ANY: `NONE` for a bounded development discovery. The existing
Frontier record marks EH27 `NOT_EXECUTED_PROPOSED_ONLY`, `READY_DERIVABLE`, with
a fast-falsification specification and no exact historical match. A new
implementation is required, but that is ordinary Track B work rather than a
load-bearing data or infrastructure blocker. Untouched/prospective
confirmation remains deferred and is not claimed here.

[Confirmed] EH27 is the external canonical ID above. It must not be confused
with internal `H27`, “Preregistered confirmation of horizon-minimax
disagreement,” whose independent-confirmation status is structurally deferred.
The internal H27 status does not transfer to EH27.

[Inferred] EH27 can legitimately run now as `DEVELOPMENT_DISCOVERY`: its
minimum data are causal standardized residual vectors and predeclared
admissible groups, and the existing common development benchmark is explicitly
allowed for discovery/falsification. No evidence still unavailable is
intrinsic to the mechanism; only later confirmation is unavailable and must
remain a separate claim.

## TOP_3_NEXT_DIRECTIONS

### 1. EH27

TITLE: `SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`

CANONICAL_ID: `EH27`

TYPE: `EXTERNAL_NEW / GENUINELY_NEW_HYPOTHESIS / DERIVED_OUTPUT_ONLY`

NEW_INFORMATION_OR_MECHANISM: A penalized maximum scan over a fixed universe
of sparse subsets of causal standardized residuals, with null-calibrated
penalties, minimum alarm duration, and a fixed conditional allocation or
abstention action. It tests coordinated local effects that a global mean,
maximum single coordinate, or scalar anomaly can hide.

PRIOR_OVERLAP: `LOW–MEDIUM`. The residual/anomaly/gate substrate overlaps
H10, H20, and H22 at the component level, but the sparse cross-sectional scan,
fixed group universe, multiplicity calibration, and delayed action are not an
exact match in the 133-identity audit.

ERA_PROXY_RISK: `LOW–MEDIUM` with train-only calibration, explicit
era-stratified diagnostics, and no post-alarm subgroup renaming. The risk is
not zero because it still consumes the historical B649 substrate.

DATA_READINESS: `4/5 — READY_DERIVABLE`. Existing causal draw/strategy
residual histories and the frozen fast-falsification spec are sufficient for
development; no new source ingestion or database work is required.

DIRECT_M2_M3_PATH: `MEDIUM-DIRECT`. A fixed alarm can select one fixed legal
ticket action or abstain; evaluate one-ticket M2+ as primary and require
M3+ non-deterioration. It is more direct than a governance-only gate, but it
does not create a new ticket generator by itself.

IMPLEMENTATION_COST: `MEDIUM` — bounded scan-statistic/higher-criticism
implementation, causal replay, null calibration, and locked controls.

### 2. EH15

TITLE: `CHANGEPOINT_TRIGGERED_META_SELECTION`

CANONICAL_ID: `EH15`

TYPE: `EXTERNAL_COMBINATION / COMBINATION_OF_EXISTING / DERIVED_OUTPUT_ONLY`

NEW_INFORMATION_OR_MECHANISM: One prespecified causal ADWIN or Page-Hinkley
alarm changes the selector horizon or eligible frozen-strategy set, followed
by local competence estimation. The novelty is the alarm-to-selector action,
not a new raw information source.

PRIOR_OVERLAP: `MEDIUM–HIGH`. It combines the already-exposed changepoint,
meta-selection, consensus, and gating families; it is not an exact duplicate,
but its terminal action is close to several deprioritized lines.

ERA_PROXY_RISK: `MEDIUM–HIGH`. A detected break can be a calendar-era proxy,
and the selector can inherit the same post-2023 or pre-cutoff instability seen
in prior B649 gates. Strict prior residuals and era-stratified controls are
mandatory.

DATA_READINESS: `5/5 — READY_DERIVABLE`. Frozen-strategy out-of-fold residual
streams and a causal state feature are available in the Frontier design.

DIRECT_M2_M3_PATH: `MEDIUM-DIRECT` through a selected existing one-ticket
strategy, but it depends on the same candidate-quality surface that has already
produced weak transfer.

IMPLEMENTATION_COST: `LOW` for the prescribed one-detector, one-action,
minimal 2×2 ablation.

### 3. EH03

TITLE: `RECURRENCE_QUANTIFICATION_STATE_GATE`

CANONICAL_ID: `EH03`

TYPE: `EXTERNAL_NEW / GENUINELY_NEW_HYPOTHESIS / DERIVED_OUTPUT_ONLY`

NEW_INFORMATION_OR_MECHANISM: Recurrence-rate, determinism, laminarity,
trapping-time, and diagonal-length descriptors from a causal delay embedding
of ordered draw/residual states, used to gate a fixed strategy or abstention.

PRIOR_OVERLAP: `MEDIUM`. The recurrence geometry is new relative to H18/H20,
but the output is still a regime/state gate over the existing B649 substrate.

ERA_PROXY_RISK: `MEDIUM–HIGH`. Embedding and radius choices can encode finite
era structure; blocked outer folds, minimum support, and a fixed radius policy
are required.

DATA_READINESS: `4/5 — READY_DERIVABLE`. The Frontier spec defines the required
ordered multivariate histories and bounded outer-fold design; no new database
source is required.

DIRECT_M2_M3_PATH: `LOW–MEDIUM / INDIRECT`. It gates an existing ticket
generator rather than producing candidate content, so its M2+/M3+ route is
less direct than EH27.

IMPLEMENTATION_COST: `LOW–MEDIUM` — bounded recurrence descriptors with one
predeclared embedding/radius policy and causal controls.

EH18 remains lower for this prediction-specific selection: its target is
research promotion/continuation/demotion or abstention under optional stopping,
not a direct number or ticket prediction path.

## Decision

NEXT_RESEARCH_DIRECTION: `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`

WHY_THIS_DIRECTION_NOW: EH27 is the strongest successor after the physical
order null because it changes the mechanism in a load-bearing way: it tests a
sparse coordinated cross-sectional effect rather than another positional,
frequency, gap, consensus, portfolio, or generic era transform. It has a
frozen specification, no exact historical identity match, derivable data, and a
bounded path to a fixed one-ticket action. The result is valuable in either
direction: a null closes a clearly defined sparse-edge mechanism, while a
positive result must survive global/max-coordinate controls, multiplicity,
chronological stability, and era diagnostics before any advancement.

WHY_NOT_DIRECTION_2: EH15 is cheaper and ranks higher in the older external
priority table, but it is a close combination of already-deprioritized
changepoint/meta-selection/gating families. Its alarm can simply rediscover a
calendar-era break, and its failure would provide less new information after
the physical-order and other state/gate results. EH27 has the cleaner new
target and better failure attribution.

WHY_NOT_DIRECTION_3: EH03 supplies a genuinely different recurrence
representation, but its output is still an indirect regime gate with more
embedding/radius sensitivity and a higher era-proxy burden. It does not improve
the direct M2+/M3+ path enough to outrank the fixed sparse-scan action.

REQUIRED_PREREQUISITE: `NONE` as a load-bearing data or infrastructure step.
Track B must lock the admissible group universe, residual standardization,
scan penalty, null threshold, minimum alarm duration, fixed action, comparator
arms, chronological folds, and era-stratified diagnostics before reading each
outer outcome. This is protocol locking inside the discovery task, not a
separate prerequisite route.

DISCOVERY_MODE: `DEVELOPMENT_DISCOVERY_ONLY`. The common benchmark may be used
for discovery and falsification, never called untouched confirmation. Future
independent/prospective confirmation remains deferred; Cohort V2 is excluded.

DATA_TO_USE: Existing B649 causal draw and frozen-strategy residual histories;
predeclared admissible groups; strict-prior expanding-window folds; and the
common development benchmark `113000006–115000069`. Do not use Cohort V2,
target-draw order, post-target fields, or database writes.

PRIMARY_SUCCESS_METRIC: One-ticket M2+ improvement versus the locked global
mean, maximum-single-coordinate, and H20 scalar-anomaly controls, with M3+
non-deterioration and replicated delayed group-effect evidence as required
supporting gates.

STOP_OR_PIVOT: Stop EH27 with `DO_NOT_ADVANCE` if alarms are post hoc or
unstable, subgroup identities are renamed after outcomes, the delayed group
effect is absent, the fixed action does not improve the locked controls, or
the apparent gain is only an era-specific benchmark result. Do not rescue by
retuning or move to Level 2. Pivot to a genuinely different information source
or an Owner-level hold; do not reopen the closed physical-order line or another
same-benchmark positional/gate variant.

NEXT_TASK_TRACK: `TRACK_B`

NEXT_TASK_ID: `B649_TRACK_B_EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE_R1`

## Evidence and execution boundary

Opened/read during this bounded decision:

- `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/B649_TRACK_B_LAGGED_PHYSICAL_DRAW_ORDER_LEVEL1_R1/report.md`
- `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1/report.md`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_FRONTIER_V2_SPEC_REGISTRY_R1.csv`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_NORMALIZED_R1.csv`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_HYPOTHESIS_INVENTORY_R1.csv`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_PRIORITY_RANKING_R1.csv`
- `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md`
- `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/B649_TRACK_D_POST_JACKPOT_ERA_CONFOUND_SUCCESSOR_RESELECTION_R1.md`

EXPERIMENT_EXECUTED: `NO`

COHORT_V2_PROSPECTIVE_DATA_USED: `NO`

REPO_MUTATION: `NONE`

DB_MUTATION: `NONE`

TASK_CREATED_FILE: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_POST_PHYSICAL_DRAW_ORDER_SUCCESSOR_RESELECTION_R1.md`

The report artifact is the only file written for this bounded decision. No
source, test, configuration, strategy registry, Git state, or database was
modified.

## Final

TASK_ID: `B649_TRACK_D_POST_PHYSICAL_DRAW_ORDER_SUCCESSOR_RESELECTION_R1`

STATUS: `COMPLETE — EXACTLY_ONE_DIRECTION_SELECTED`

PHYSICAL_DRAW_ORDER_LINE_STATUS: `CLOSED`

PHYSICAL_DRAW_ORDER_PREDICTIVE_INCREMENT: `NONE`

EH27_STATUS: `READY_NOW — DEVELOPMENT_DISCOVERY_ONLY; FUTURE_CONFIRMATION_DEFERRED`

TOP_3_NEXT_DIRECTIONS:
1. `EH27` — `SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`
2. `EH15` — `CHANGEPOINT_TRIGGERED_META_SELECTION`
3. `EH03` — `RECURRENCE_QUANTIFICATION_STATE_GATE`

NEXT_RESEARCH_DIRECTION: `EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE`

