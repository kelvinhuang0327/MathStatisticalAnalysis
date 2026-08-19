# B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1

STATUS: COMPLETE — semantic, source coverage, join, and pagination validation completed.

This is a bounded data/metadata validation. It does not train a predictor,
run a backtest, redesign ingestion, change the database, migrate schema, or
use Cohort V2 outcomes.

## Decision

`drawNumberAppear` is classified as `PHYSICAL_DRAW_ORDER` for the official
source representation. The primary evidence chain is: Taiwan Lottery's
official process page says B649 uses sequentially opened numbers and has a
selected ball-drop order; the official history renderer passes
`drawNumberAppear` to the opening-order display; and the official CTBC result
page directly shows period 115000079's opening sequence matching the API.
The 2007, 2015, and 2026 exact-period API rows all satisfy the same official
opening-order mapping and are non-sorted permutations.

The source-side coverage check is exhaustive over the official API result set
returned by the correctly parameterized 2007-01 through 2026-08 query: six
pages, 2161 unique periods, no duplicate periods, and
2161 populated `drawNumberAppear` fields. This is
an exhaustive check of the API result set, not a claim that an undocumented
API total is independent ground truth.

The pagination risk is `HIGH` for a broad call through the current
provider-shaped query: the official UI uses `month`, while the provider code
uses `startMonth`, and the one-page broad probe returned
400 of 2161 rows. A future
replay/backfill must use correct `month`/`endMonth` paging or separate bounded
windows and assert the returned union.

## Required final fields

```text
TASK_ID: B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1
STATUS: COMPLETE — VALIDATION COMPLETE; ACTIVE HEAD REF CAVEAT RECORDED

DRAW_NUMBER_APPEAR_FIELD_FOUND: YES
SEMANTIC_CLASSIFICATION: PHYSICAL_DRAW_ORDER

PRIMARY_EVIDENCE: official Taiwan Lottery process page + official history-result renderer + official CTBC result page + official TLCAPIWeB payloads
DRAWS_CROSS_CHECKED: 3 (EARLY 2007, MID 2015, RECENT 2026)

PHYSICAL_ORDER_MATCH_COUNT: 3
SORTED_ORDER_MATCH_COUNT: 0
OTHER_ORDER_MATCH_COUNT: 0

FIRST_AVAILABLE_DRAW: 96000001
LAST_AVAILABLE_DRAW: 115000079

TOTAL_DRAWS_CHECKED: 2161
FIELD_PRESENT_COUNT: 2161
FIELD_MISSING_COUNT: 0
COVERAGE_RATE: 100.0000%

FORMAT_STABILITY: PASS
PERMUTATION_INVARIANT: PASS

JOIN_QUALITY: exact API-period join 2160/2161 (99.9537%); date-aligned join 2160/2160 (100.0000%) against read-only local DB snapshot

PAGINATION_METADATA_STATUS: QUERY_DEPENDENT
PAGINATION_COVERAGE_RISK: HIGH

CURRENT_TARGET_ALLOWED: NO
LAGGED_HISTORY_ALLOWED: YES

INGEST_CURRENTLY_PRESERVES_FIELD: YES — confirmed on origin/main PR #137 ref 4a106bf84273b354a0b8c51f0e076d8d4976c082 via additive research metadata sidecar; active local HEAD e8de3bff6985a156f0902f8012713f5e8768709c is divergent and does not contain that PR, so the distinction is retained explicitly.
RESEARCH_READINESS: READY_NOW for the PR #137 upstream storage reference, conditional on the pagination prerequisite above

REQUIRED_PREREQUISITE: Track B must consume the preserved source-order tuple from the research sidecar, use only history strictly before target t, and fetch broad ranges with official month/endMonth pagination (or bounded per-month windows) with returned-union assertions.

DECISION: ADVANCE

NEXT_TASK_TRACK: TRACK_B
NEXT_TASK_ID: B649_TRACK_B_LAGGED_PHYSICAL_DRAW_ORDER_LEVEL1_R1

FALLBACK_IF_CLOSED: EH27

COHORT_V2_PROSPECTIVE_DATA_USED: NO
REPO_MUTATION: TASK_DATA_ONLY
DB_MUTATION: NONE
```

## Evidence and observed results

### Semantic evidence

| Sample | API `drawNumberSize` main / special | API `drawNumberAppear` | Classification |
|---|---|---|---|
| EARLY 96000026 (2007-03-30) | `[14,31,33,40,45,46]` / `49` | `[14,45,46,40,33,31,49]` | YES physical-order mapping; sorted=NO |
| MID 104000057 (2015-06-30) | `[18,19,32,35,46,48]` / `47` | `[18,35,19,48,46,32,47]` | YES physical-order mapping; sorted=NO |
| RECENT 115000079 (2026-08-14) | `[5,12,25,33,34,35]` / `27` | `[35,25,5,12,34,33,27]` | YES physical-order mapping; sorted=NO |

Official primary-source flags observed:

- Process page: `落球順序`=True, B649 sequential rule=True, opened-order preservation=True.
- History renderer: reads `drawNumberAppear`=True, reads `drawNumberSize`=True, passes both to the number renderer=True.
- CTBC direct recent page parse: status=PASS, period=115000079, sorted main=`[5,12,25,33,34,35]`, opening main=`[35,25,5,12,34,33]`, special=`27`, direct API match=True.

No manual video labeling was needed for this bounded semantic check because
the official process and official result presentation directly define the
reported order. Video evidence was therefore not treated as silently
observed; it is recorded as not used.

### Coverage and join

| Scope | Rows | Field present | Missing | Coverage | Permutation | Duplicates | Exact join |
|---|---:|---:|---:|---:|---:|---:|---:|
| OVERALL | 2161 | 2161 | 0 | 100.0000% | 2161/2161 | 0 | 2160/2161 (99.9537%) |
| EARLY_2007_01_TO_03 | 26 | 26 | 0 | 100.0000% | 26/26 | 0 | 26/26 (100.0000%) |
| MID_2015_06 | 9 | 9 | 0 | 100.0000% | 9/9 | 0 | 9/9 (100.0000%) |
| RECENT_2026_08 | 4 | 4 | 0 | 100.0000% | 4/4 | 0 | 3/4 (75.0000%) |

The local DB was opened read-only at `/Users/kelvin/Library/Application Support/LottoLab/lottolab.db` (`READ_ONLY_PASS`). Its latest
canonical B649 date is `2026-08-11`, so the single exact
join miss is the source row for the later 2026-08-14 draw. The local DB also
contains 998 periods not in this official B649 API
result set; those rows are not silently treated as source coverage.

### Pagination

- Correct official full query: `{"month":"2007-01","endMonth":"2026-08","pageSize":400}`.
- Page union: `2161` returned rows against `totalSize=2161`; page-1 repeat hash equals page-1 hash: `True`.
- Official bounded windows returned early=26, mid=9, recent=4 rows with the same field present in each returned row.
- Provider-shaped single-window probes returned cumulative/out-of-window rows (mid `totalSize=899`, recent `totalSize=2161`), demonstrating query dependence.
- Provider-shaped full-range page 1 returned `400` rows while `totalSize=2161`; this is an actual coverage risk if the caller does not page.

### Causal boundary

`drawNumberAppear(t)` is post-draw metadata for the draw it describes. It is
not allowed as an input for target `t`; only lagged values from draws strictly
before `t` may be used. This task ran no predictor, strategy, signal, or
backtest.

### Storage reference and repository caveat

`origin/main` at `4a106bf84273b354a0b8c51f0e076d8d4976c082` contains PR #137's additive
research metadata path. The upstream provider's `_metadata_record` stores
`drawNumberAppear` as `draw_number_appear=tuple(draw_number_appear)` and the
sidecar encoder writes the same tuple as a JSON list while retaining raw JSON.
The active workspace `HEAD` is `e8de3bff6985a156f0902f8012713f5e8768709c` on branch `main`
and does not contain PR #137; this task did not merge, cherry-pick, or alter
that source. Existing worktree changes were preserved.

## Reproduction

Live bounded collection and report generation:

```bash
python3 .task-data/B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1/reproduce_analysis.py
```

Offline re-derivation from the compact captured snapshot:

```bash
python3 .task-data/B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1/reproduce_analysis.py --offline
```

Generated artifacts:

- `semantic_crosscheck.csv`
- `coverage_checks.csv`
- `pagination_checks.csv`
- `fixtures/source_snapshot.json` (compact 4-field row snapshot, 2,161 rows)
- `fixtures/semantic_samples.json`, `fixtures/pagination_probes.json`, and `fixtures/official_evidence.json` (bounded provenance/hashes)

## Unknowns and limits

- `[Confirmed]` The official source's reported opening-order representation is a non-sorted permutation of the six canonical numbers, with the special number kept in the seventh slot, in all 2161 returned rows.
- `[Confirmed]` The official API result-set coverage is complete for the six-page query run and has 0 field omissions.
- `[Inferred]` The source-side history is research-ready for lagged replay once the pagination prerequisite is respected.
- `[Unknown]` The official API does not expose a separate field dictionary that uses the English phrase “physical ball order”; the physical interpretation rests on the official Chinese process/UI labels and one direct official result-page comparison, not on manually labeled video frames.
- `[Unknown]` The active local HEAD does not itself preserve PR #137's sidecar until that divergent-ref state is reconciled by an owner-authorized integration.

## Fable execution record

ROUTE: STANDARD
CHANGED: `.task-data/B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1/` only
VERIFIED: live official API paging, exact-period samples, official process/renderer/CTBC evidence, read-only DB join, and offline reproduction
NOT RUN / BLOCKED: no predictor/backtest/video labeling; no DB or ingestion mutation by task contract
RISKS: pagination query-shape/one-page risk; active HEAD versus origin/main PR #137 divergence

INTENT: code does bounded source/evidence collection and deterministic report generation; the check/task expects semantic, coverage, join, and pagination validation; the opened packet says to preserve source order, avoid ingestion redesign, and decide whether to advance to lagged Track B.
