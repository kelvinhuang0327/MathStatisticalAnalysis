# LotteryNew → LottoLab non-multiticket web parity R1

This matrix is limited to `LOTTERYNEW_TO_LOTTOLAB_NON_MULTITICKET_WEB_PARITY_R1`.
The legacy checkout at `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` remained read-only, and
LottoLab never reads or falls back to legacy runtime data. Every feature record below uses the
Planner Packet's required field schema and `parity_status` vocabulary.

## Data Center — CSV preview and explicit commit

```yaml
legacy_page: Data ingestion panels
legacy_action: Upload or submit draw data
legacy_input: CSV draw rows
legacy_data_source: LotteryNew upload and ingest routes
legacy_filter: Lottery type and submitted file
legacy_sort: Input row order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No submitted rows
legacy_error_state: Route-specific validation or database error
legacy_write_effect: May insert uploaded draw data directly
legacy_known_defect: Browser submission and mutation authority are not cleanly separated
new_core: DrawCsvParser plus PreviewDrawCsv and CommitDrawCsv
new_api: POST /api/v1/draw-data/preview and POST /api/v1/draw-data/commit
new_page: "#/data-center"
new_tests: tests/contract/test_draw_data_api.py; frontend/tests/data-center.test.ts
parity_status: PARITY_VERIFIED
```

## Data Center — multi-file batch

```yaml
legacy_page: Data ingestion panels
legacy_action: No stable cross-file batch action identified
legacy_input: Individual CSV submissions
legacy_data_source: LotteryNew upload and ingest routes
legacy_filter: Per submitted file
legacy_sort: Input row order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No submitted file
legacy_error_state: Per-request error
legacy_write_effect: Individual request mutations
legacy_known_defect: No explicit per-file batch transaction or aggregate-result contract
new_core: Per-file preview state and independent CommitDrawCsv transaction
new_api: Existing preview and commit routes invoked once per file
new_page: "#/data-center input[multiple], preview all, commit all valid, commit selected valid, cancel"
new_tests: frontend/tests/data-center.test.ts
parity_status: PARITY_VERIFIED
```

## Data Center — manual synchronization

```yaml
legacy_page: Ingestion panel
legacy_action: Fetch latest draw data
legacy_input: Lottery/source selection
legacy_data_source: LotteryNew fetcher and POST /api/ingest/fetch-latest
legacy_filter: Latest-source range
legacy_sort: Source response order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No source rows
legacy_error_state: Fetcher or ingest error
legacy_write_effect: Fetch and persist draw data
legacy_known_defect: Source access and persistence are coupled to legacy runtime behavior
new_core: DrawDataProvider plus FetchDrawData with MANUAL_SYNC audit trigger
new_api: POST /api/v1/draw-data/sync/manual
new_page: "#/data-center"
new_tests: tests/unit/test_draw_automation.py; tests/contract/test_non_multiticket_web_parity_api.py
parity_status: PAGE_READY
```

## Data Center — missing-draw scan

```yaml
legacy_page: Ingestion panel
legacy_action: Scan missing draws
legacy_input: Lottery and requested range
legacy_data_source: LotteryNew missing-issue detector and GET /api/ingest/scan-missing
legacy_filter: Missing issues in requested scope
legacy_sort: Legacy issue order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No missing issues
legacy_error_state: Fetcher or detector error
legacy_write_effect: Legacy flow may couple scan and source refresh
legacy_known_defect: Read and source-refresh responsibilities are mixed
new_core: ScanMissingDraws with MISSING_DRAW_SCAN audit trigger
new_api: POST /api/v1/draw-data/sync/missing-scan
new_page: "#/data-center"
new_tests: tests/unit/test_draw_automation.py; tests/contract/test_non_multiticket_web_parity_api.py
parity_status: PAGE_READY
```

## Data Center — bounded backfill

```yaml
legacy_page: Ingestion panel
legacy_action: Backfill historical draw range
legacy_input: Lottery and date range
legacy_data_source: LotteryNew fetcher and POST /api/ingest/backfill
legacy_filter: Requested historical range
legacy_sort: Source response order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No rows in range
legacy_error_state: Fetcher, validation, or database error
legacy_write_effect: Fetch and persist historical draw rows
legacy_known_defect: Legacy endpoint does not define the target 366-day safety boundary
new_core: BackfillDrawRange with maximum 366 inclusive days and no-overwrite persistence
new_api: POST /api/v1/draw-data/sync/backfill
new_page: "#/data-center"
new_tests: tests/unit/test_draw_automation.py; tests/contract/test_non_multiticket_web_parity_api.py
parity_status: PAGE_READY
```

## Data Center — scheduled synchronization trigger

```yaml
legacy_page: Scheduler and ingestion runtime
legacy_action: Start recurring ingestion jobs
legacy_input: Scheduler configuration
legacy_data_source: LotteryNew scheduler modules
legacy_filter: Scheduler-owned range
legacy_sort: Scheduler execution order
legacy_pagination: NOT_PRESENT
legacy_empty_state: Scheduler has no due work
legacy_error_state: Background scheduler or fetch failure
legacy_write_effect: Background process can fetch and persist data
legacy_known_defect: Construction-time scheduler ownership can create hidden side effects
new_core: ScheduledDrawSync with SCHEDULED_SYNC audit trigger and no construction-time job
new_api: POST /api/v1/draw-data/sync/scheduled
new_page: "#/data-center explicit trigger"
new_tests: tests/unit/test_draw_automation.py; tests/contract/test_non_multiticket_web_parity_api.py
parity_status: PAGE_READY
```

The four provider operations are locally implemented, bounded, audited, and fail closed with
`AUTOMATION_NOT_CONFIGURED`. Official-source certification, production scheduler ownership, and
traffic cutover remain external conditions, so these records do not claim `PARITY_VERIFIED`.

## Ingestion audit

```yaml
legacy_page: Ingest-log panels and routes
legacy_action: Inspect ingestion activity
legacy_input: Run or log selection
legacy_data_source: LotteryNew ingest logs
legacy_filter: Legacy route-specific filters
legacy_sort: Legacy log order
legacy_pagination: Route-specific
legacy_empty_state: No ingest logs
legacy_error_state: Log or database error
legacy_write_effect: Read action may coexist with legacy maintenance controls
legacy_known_defect: Trigger, provider, conflict, and failure structure is not one stable contract
new_core: Append-only ingestion run, context, item, conflict, and failure records
new_api: GET /api/v1/ingestion-runs and GET /api/v1/ingestion-runs/{run_id}
new_page: "#/history — Ingestion History"
new_tests: tests/contract/test_non_multiticket_web_parity_api.py; frontend/tests/non-multiticket-workspaces.test.ts
parity_status: PARITY_VERIFIED
```

## Draw History

```yaml
legacy_page: History page
legacy_action: Browse draw history
legacy_input: Lottery, date, and draw filters
legacy_data_source: LotteryNew history API and runtime database
legacy_filter: Lottery/date/draw criteria
legacy_sort: Legacy history order
legacy_pagination: Legacy page controls
legacy_empty_state: No matching draws
legacy_error_state: History route or database error
legacy_write_effect: Legacy read can refresh scheduler state
legacy_known_defect: A nominal read can have scheduler side effects
new_core: QueryDrawHistory read model
new_api: GET /api/v1/draws
new_page: "#/history — Draw History"
new_tests: tests/contract/test_draw_history_api.py; frontend/tests/draw-history.test.ts
parity_status: PARITY_VERIFIED
```

## Ingestion History

```yaml
legacy_page: Ingestion history and log panels
legacy_action: Filter runs and inspect one run
legacy_input: Status, operation, source, date range, and run identity
legacy_data_source: LotteryNew ingest logs
legacy_filter: Route-specific legacy filters
legacy_sort: Newest available activity first
legacy_pagination: Legacy route-specific
legacy_empty_state: No matching activity
legacy_error_state: Log or database error
legacy_write_effect: NONE
legacy_known_defect: No single bounded run/detail contract
new_core: QueryIngestionRuns and QueryIngestionRunDetail
new_api: GET /api/v1/ingestion-runs and GET /api/v1/ingestion-runs/{run_id}
new_page: "#/history — Ingestion History"
new_tests: tests/contract/test_non_multiticket_web_parity_api.py; frontend/tests/non-multiticket-workspaces.test.ts stale-list/detail race
parity_status: PARITY_VERIFIED
```

## Historical Import Runs

```yaml
legacy_page: Historical data and report surfaces
legacy_action: Inspect import-run metadata
legacy_input: Completed import run
legacy_data_source: LotteryNew historical artifacts and reports
legacy_filter: Completed import identity
legacy_sort: Completed time descending
legacy_pagination: Bounded run page
legacy_empty_state: No completed imports
legacy_error_state: Historical storage unavailable or invalid
legacy_write_effect: NONE
legacy_known_defect: Metadata and replay/outcome concepts are heterogeneous
new_core: QueryHistoricalRuns metadata-only read model
new_api: GET /api/v1/historical-results/runs
new_page: "#/history — Historical Import Runs"
new_tests: tests/integration/test_historical_results_repository.py; frontend/tests/non-multiticket-workspaces.test.ts
parity_status: PARITY_VERIFIED
```

This page exposes only run ID, import identity, source, status, strategy/draw/portfolio counts,
timestamps, and the idempotent-import flag. It exposes no tickets, portfolio outcomes, strategy
replay, multi-ticket ranking, or 10/15/20-ticket results.

## Strategy catalog and canonical evidence availability

```yaml
legacy_page: Strategy overview
legacy_action: Inspect strategy state
legacy_input: Strategy identity
legacy_data_source: Legacy strategy and result sources
legacy_filter: Strategy selection
legacy_sort: Legacy presentation order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No strategy records
legacy_error_state: Legacy result-source failure
legacy_write_effect: NONE
legacy_known_defect: Catalog lifecycle and result-derived claims can be visually conflated
new_core: StrategyCatalog plus committed canonical-evidence registry reader
new_api: GET /api/v1/strategy-evidence
new_page: "#/strategy-evidence"
new_tests: tests/contract/test_non_multiticket_web_parity_api.py; frontend/tests/non-multiticket-workspaces.test.ts
parity_status: PARITY_VERIFIED
```

## Best Strategy unavailable block

```yaml
legacy_page: Strategy overview
legacy_action: View a derived best-strategy concept
legacy_input: Legacy strategy results
legacy_data_source: Legacy best_strategy_overview result sources
legacy_filter: Legacy result eligibility
legacy_sort: Derived result order
legacy_pagination: NOT_PRESENT
legacy_empty_state: No eligible result
legacy_error_state: Legacy artifact unavailable
legacy_write_effect: NONE
legacy_known_defect: Presentation may imply ranking authority not present in the catalog
new_core: Fixed unavailable block with NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE
new_api: GET /api/v1/strategy-evidence
new_page: "#/strategy-evidence"
new_tests: tests/contract/test_non_multiticket_web_parity_api.py; frontend/tests/non-multiticket-workspaces.test.ts
parity_status: PARITY_VERIFIED
```

## D3 availability

```yaml
legacy_page: Historical and derived metric surfaces
legacy_action: Inspect D3-like reporting
legacy_input: Legacy result artifacts
legacy_data_source: Legacy reports
legacy_filter: Legacy result selection
legacy_sort: NOT_PRESENT
legacy_pagination: NOT_PRESENT
legacy_empty_state: No D3 value
legacy_error_state: Artifact unavailable
legacy_write_effect: NONE
legacy_known_defect: Missing values may not carry a canonical definition state
new_core: Committed D3 definition reader
new_api: GET /api/v1/strategy-evidence
new_page: "#/strategy-evidence"
new_tests: tests/contract/test_non_multiticket_web_parity_api.py; frontend/tests/non-multiticket-workspaces.test.ts
parity_status: PARITY_VERIFIED
```

D3 is `RESERVED_UNAVAILABLE` and its value is `NOT_AVAILABLE`; unavailable is never represented as
zero.

## Strategy Combination Hit Rate

```yaml
legacy_page: Multi-strategy result surfaces
legacy_action: Inspect combination hit rate
legacy_input: Multi-ticket strategy results
legacy_data_source: Active multi-ticket agent scope
legacy_filter: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_sort: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_pagination: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_empty_state: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_error_state: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_write_effect: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_known_defect: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
new_core: Fixed exclusion block only
new_api: GET /api/v1/strategy-evidence returns exclusion metadata only
new_page: "#/strategy-evidence exclusion block"
new_tests: tests/contract/test_non_multiticket_web_parity_api.py; frontend/tests/non-multiticket-workspaces.test.ts
parity_status: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
```

## Replay, backtest, portfolio, ranking, and ticket matrices

```yaml
legacy_page: Multi-ticket research and result surfaces
legacy_action: Replay, backtest, rank, optimize, or render ticket matrices
legacy_input: Multi-ticket artifacts
legacy_data_source: Active multi-ticket agent scope
legacy_filter: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_sort: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_pagination: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_empty_state: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_error_state: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_write_effect: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
legacy_known_defect: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
new_core: NOT_PRESENT
new_api: NOT_PRESENT
new_page: NOT_PRESENT
new_tests: Changed-path exclusion review
parity_status: EXCLUDED_ACTIVE_MULTITICKET_SCOPE
```

## Cutover statement

`NON_MULTITICKET_IMPLEMENTATION_STATUS: COMPLETE` means the local target contract is implemented and
locally testable. `LEGACY_PARITY_STATUS: PARTIAL` remains mandatory because official draw-source
certification, production scheduler ownership, deployed health checks, traffic switching, exact-head
CI, and a rollback exercise are not established by this local branch. LotteryNew retirement is not
claimed.
