# Cross-Lottery Research Ledger R1 — minimal schema and lifecycle

Status: MINIMAL OPERATIONAL SSOT — appendable, not a finished governance system ｜ 2026-08-14

This is deliberately small. It exists so the matrix can move from "designed
across several conversations" to "a file that gets appended to every time a
hypothesis is tested," not to be a complete 40-field research-control
system. Fields not needed yet were left out; add them when a real need
appears, not speculatively.

## Relationship to A/B/C/D project tracks

The Strategy Matrix is an independent, standing cross-lottery research
program, not a task queue owned by or subordinate to any of this project's
A/B/C/D engineering/operational tracks. A/B/C/D may **produce evidence the
Matrix references** (`source_type: EXTERNAL_PROJECT_RESEARCH_RESULT`), and
the Matrix's own preregistered work (`source_type: STRATEGY_MATRIX_NATIVE`)
may eventually surface an `ENGINEERING_CANDIDATE` worth a new A/B/C/D task —
but the Matrix does not drive any track's queue, and no track drives the
Matrix's selection order. The Matrix never touches production, a cohort, or
prospective activation directly; it only ever proposes.

`docs/research/cross_lottery_research_ledger_r1.json` is the only source of
truth. `docs/research/cross-lottery-research-ledger-r1.md` is generated from
it by `tools/generate_research_ledger_report.py` — never hand-edited.

## Two top-level arrays

- **`priors`**: mechanism-level coverage facts from program-wide audits
  (currently: Phase -1's `PRIOR_COVERAGE_MAP`). Not a hypothesis result —
  a statement about what has and has not been tested at all, that
  individual cells can cite.
- **`cells`**: one row per `(hypothesis_variant_id, lottery_type, zone)`
  evidence attempt.

## Cell fields

| Field | Meaning |
|---|---|
| `cell_id` | Stable identifier, `{hypothesis_variant_id}__{lottery_type}[_{zone}]` |
| `hypothesis_family_id` | The research question, generation-independent |
| `hypothesis_variant_id` | The exact design version this cell tested |
| `mechanism_class` | `MARGINAL` / `POSITIONAL` / `JOINT_PAIRWISE` / `SERIAL_FIRST_ORDER` / `CONDITIONAL` / `REGIME` / `ALLOCATION` / `STRUCTURAL` — cross-referenced against `priors` |
| `mechanism_family` | The coarser 8-family research-space taxonomy (`ALLOCATION_EXPOSURE`, `REGIME_CHANGE_POINT`, `JOINT_CONDITIONAL_STRUCTURE`, `TICKET_PORTFOLIO_STRUCTURE`, `DIVERSIFICATION`, `HIGHER_ORDER_TEMPORAL_STRUCTURE`, `META_SELECTION`, `MARGINAL_PER_NUMBER`, or `UNCLASSIFIED_DEFERRED`) used to prioritize what the Strategy Matrix studies next — independent of which A/B/C/D track (if any) produced a given cell's underlying evidence |
| `source_type` | `STRATEGY_MATRIX_NATIVE` (this ledger's own preregistered work) \| `EXTERNAL_PROJECT_RESEARCH_RESULT` (referenced from an A/B/C/D track's own task lifecycle; the Matrix does not own or drive that track's queue) |
| `lottery_type`, `zone` | `zone` is null except for POWER_LOTTO |
| `generation` | 1 for every cell in this ledger so far |
| `record_state` | `REPORTED_LEGACY` (predates this ledger, never R1-preregistered) \| `SEALED` (R1 two-phase-locked and complete) \| `DESIGN_ABANDONED` (native design work happened but correctly stopped before locking — e.g. the question turned out not to be separately identifiable from another mechanism; see `decision_state: STRUCTURALLY_DEFERRED` and `deferral_reason`) \| `INVALIDATED` \| `SUPERSEDED` |
| `preregistration_grade` | `NOT_PREREGISTERED_UNDER_R1` \| `R1_PREREGISTERED` — legacy cells can never claim the second value retroactively, regardless of how good their artifacts turn out to be |
| `evidence_grade` | `REPORTED_UNVERIFIED` (claim only, not independently checked against an artifact in a current session) \| `LOCAL_VERIFIED` (this session read/ran the actual artifact) |
| `descriptive_classification` | For R1-preregistered cells, computed by that cell's own frozen rule. For legacy cells, the label as reported historically — not re-derived. |
| `decision_state` | `DO_NOT_ADVANCE` \| `REPLICATION_REQUIRED` \| `ADVANCE_TO_NEXT_LEVEL` \| `STRUCTURALLY_DEFERRED` |
| `global_mechanism_status`, `exhausted` | Optional, cell-level statement about the *`hypothesis_family_id`*, not just this cell: `RETAINED_FOR_FUTURE_GENERATIONS` (nothing found; the question stays open) or `RETAIN_AND_REPLICATE` (a positive result was found in this lottery — actively route to the replication queue, not just leave open) / `exhausted: false` means sealing this exact variant does not close the research question. Only ever set `exhausted: true` with a stated declared-edge power justification, never by default. |
| `evidence_type` | `EXACT_COMBINATORIAL` (complete enumeration / exact closed form, zero sampling error) vs the implicit default of statistical evidence (Holm-corrected p-values, simulation percentiles). Matrix cells are not required to be phrased as `SIGNAL`/`NO_SIGNAL` findings — a precise combinatorial-design result is a different, equally legitimate evidence type. |
| `uncertainty` | Free text; `"NONE -- exact enumeration / exact closed form"` for `EXACT_COMBINATORIAL` cells, otherwise describes the relevant statistical uncertainty. |
| `predictive_advantage`, `prize_value_advantage`, `economic_optimality` | Explicit `NOT_TESTED` markers so a positive combinatorial-coverage result is never misread as a predictive or economic claim it did not make. |
| `primary_endpoint_value`, `primary_endpoint_definition` | Nullable — absent for legacy cells with no recoverable exact number |
| `artifact_paths` | Repo-relative paths backing the cell; empty list is honest for unverified legacy cells |
| `experiment_run`, `result`, `deferral_reason` | Only present on `record_state: DESIGN_ABANDONED` cells. `experiment_run: false`, `result: "NOT_FAILED"` — a deferral is not a negative result, and must never be read as one. `deferral_reason` states the specific identification problem in full, not just a label. |
| `related_legacy_evidence` | Optional list of legacy `cell_id`s this cell's research question is related to but is **not** a rerun of — required whenever a Matrix-native variant's `hypothesis_family_id` overlaps a legacy family's territory, so the ledger never reads as "the same experiment ran twice" when the exact design differs. Citing a legacy cell here never changes that cell's own `evidence_grade`. |
| `retest_eligible`, `retest_triggers` | Whether/why a new generation could reopen this exact `hypothesis_family_id` (never this exact `hypothesis_variant_id` — that would be a rescue) |
| `next_priority` | `HIGH` \| `MEDIUM` \| `LOW` \| `NONE` — research-resource ordering, never a claim that the family is closed |
| `source_note` | Where this cell's content came from |
| `last_reviewed_at` | ISO date |

## Lifecycle

```text
UNTESTED -> PREREGISTRATION_LOCKED -> RESULT_APPENDED -> SEALED
                                                            |
                                                   decision_state assigned
```

`INVALIDATED` preserves the row (never deleted); a corrected rerun is a new
`cell_id` with `supersedes_cell_id` pointing back, per the no-rescue rule
already frozen in `docs/research/phase0-h04-conditional-preregistration.md`
§14 — an `hypothesis_variant_id` never gets edited in place after any
outcome was inspected.

## Two queues, not one

The ledger does not track queue membership as its own field -- both queues
are simply views over `decision_state`, so they cannot drift out of sync
with the cells themselves:

- **Discovery queue**: cells still being sought for a given lottery --
  effectively "what hasn't been tried yet." Driven by `next_priority`
  across `record_state != SEALED` mechanism families, or `SEALED` cells
  whose `decision_state` is `DO_NOT_ADVANCE` (nothing found, still open
  for a different design).
- **Replication queue**: `SEALED` cells with `decision_state:
  REPLICATION_REQUIRED` -- a positive result exists in one lottery and
  needs testing in another before it means anything cross-lottery. This
  queue takes priority over starting a new discovery-queue mechanism in
  the same lottery: a Matrix that only ever discovers and never
  replicates cannot tell a lottery-specific finding from a general one.

## What this ledger does not do

No promotion, cohort, or prospective decision follows from any cell here.
No `minimum_operationally_meaningful_effect` or Level-3 multiplicity policy
is set here — those remain the open Owner/statistical decisions recorded in
prior sessions. Legacy cells are carried forward for continuity, not
re-litigated: `NOT_PREREGISTERED_UNDER_R1` plus `REPORTED_UNVERIFIED` is
the honest, final grade they get unless someone later does the Phase
-1-style rebuild work to earn a better one.
