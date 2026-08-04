# ADR-0005: Canonical prediction and backtest research store

- Status: Accepted
- Date: 2026-07-30
- Scope: LottoLab research persistence, Phase 1A

## Context

LottoLab already has two checksum-guarded research schemas, but both require a
caller-supplied database path. They correctly served bounded imports and
projections; they did not establish a system of record. Authoritative output was
therefore fragmented, and some output existed only under ephemeral paths.

The next full prediction and backtest rebuild will write millions of ordered
ticket rows over tens of hours. It needs one durable locator, crash-safe
incremental commits, resumability, immutable lineage, and read access that stays
live while a single writer is active. The draw database must retain its exact
schema contract and its read availability.

## Decision

1. **D1 — Dedicated SQLite database.** Research data uses
   `lottolab_research.db`, beside `lottolab.db` in the directory resolved by
   `LOTTOLAB_DATA_DIR` or the durable LottoLab application-support default.
   Research release cycles and write locks do not alter the draw schema.
2. **D2 — Canonical locator.** `resolve_research_data_paths()` is the sole
   production locator. Production output does not depend on caller-selected
   temporary paths; tests may inject isolated paths.
3. **D3 — Draw linkage.** Cross-database linkage is the immutable natural key
   `(lottery_type, draw_number)` plus draw date, canonical number snapshots,
   `draw_sha256`, and `draw_data_version`. No cross-database foreign key exists.
   A changed draw checksum creates retained result versions.
4. **D4 — Ticket authority.** Canonical ticket JSON and `ticket_sha256` are
   authoritative. Native and ordered positions are rows; individual numbers are
   not rows. Native order and duplicate positions are retained. `candidate_k`,
   combination count, and ticket-count prefix remain distinct.
5. **D5 — Append-only history.** Every historical table has triggers rejecting
   `UPDATE` and `DELETE`. `research_run_current_pointer` is the only mutable
   table. Run status and progress changes are appended as events; completed
   targets are terminal markers committed atomically with their tickets.
6. **D6 — Future jobs.** Phase 3 will follow `LocalRuntimeSupervisor` with a
   database-backed job table and CLI worker. Redis and Celery are not adopted;
   job tables are not part of Phase 1A.
7. **D7 — Withdrawn.** No B649 coverage or missing-report surface is built.
8. **D8 — Regeneration identity.** Rebuilt output uses `REGENERATION`. It does
   not inherit a legacy report identity unless the artifact bytes hash
   identically.

Run kinds distinguish live predictions, historical replay/backtest,
regeneration, imported legacy reports, and `REFERENCE_BASELINE`. Reference
baselines remain queryable but default coverage and ranking queries exclude
them. Lifecycle and governance fields are metadata, never execution filters.

All writes use the repository contract, an idempotency key, schema-version and
migration-checksum preconditions, one writer role, short `BEGIN IMMEDIATE`
transactions, and verify-then-ignore target replay. Readers open SQLite with
`mode=ro` and `query_only`. Ordered indexes support deterministic progress,
resume, denominator, coverage, ranking, and pagination queries without scanning
ticket rows.

## Concurrency and durability

SQLite rollback-journal mode (`journal_mode=DELETE`) is mandatory. WAL and SHM
sidecars fail closed. A target and its tickets commit in one short transaction;
an interrupted transaction is invisible and rolls back, while prior targets
remain durable. Readers use a 5-second busy timeout. The repository performs at
most three writer attempts with bounded 10 ms and 50 ms backoff.

This design intentionally accepts one writer per research table family.
Migration to PostgreSQL is triggered by any of:

- sustained demand for more than one concurrent writer;
- database size exceeding 20 GB;
- multi-host access.

## Consequences

Research history is durable, append-only, checksum-verifiable, resumable, and
discoverable from one stable path. The draw database and existing historical
and replay-scoring schemas remain unchanged. SQLite remains operationally
simple, but multi-writer scaling is explicitly deferred to the exit triggers
above.

## Phase 2a amendment — sealed legacy reference baseline

This amendment remains in ADR-0005 because it refines the canonical store's
lineage and atomicity contracts; it does not choose a separate subsystem.

Only the 24,140 `BIG_LOTTO` rows in the sealed
`LOTTOLAB_LEGACY_REFERENCE_CORPUS_V1/tables/strategy_prediction_replays.jsonl`
file may enter Phase 2a, and they enter as `REFERENCE_BASELINE`.
`POWER_LOTTO` (36,104 rows) and `DAILY_539` (35,208 rows) remain deferred to
Phase 5 because no reviewed rule contract exists for either lottery.
`prediction_runs`, `prediction_items`, `prediction_results`, and the sealed
B649 reports remain Phase 2b work.

The importer verifies the replay and raw-draw JSONL files against the corpus
`SHA256SUMS` before parsing either file. The replay file is the run's input
dataset and imported artifact. The independently sealed `draws.jsonl` file
supplies cutoff and target draw bindings and the causal history count; replay
target facts must agree with it semantically. Mixed slash/dash date spelling is
parsed as a date, while the canonical store retains one ISO date value. Missing,
conflicting, or non-causal draw facts fail closed.

Legacy strategy source commits, strategy-source hashes, runtime fingerprints,
parameters, and seed protocols never existed. Schema version 2 therefore
represents them as null fields paired with the typed
`LEGACY_UNAVAILABLE` provenance status. It never stores a hash-shaped
placeholder. Stable `strategy_id`, `strategy_name`, and `strategy_version`
remain snapshot identity. The legacy `provenance_hash` and
`provenance_source` vary by ticket, so they are retained verbatim on ticket
rows together with a canonical copy and real SHA-256 of the complete legacy
record. Legacy-reported hit numbers, hit count, and special-hit flag are
retained on result rows and are not replaced by recomputation.

For imported scored targets, the target, ordered tickets, and legacy result
rows commit in one repository transaction. `commit_ticket_results` remains a
public verification/versioning path and must treat those already-committed
results as a verified no-op. This closes the first-real-data shakedown finding
that a process interruption between the earlier two public calls could
otherwise expose a terminal target without its results.

Phase 2a is scratch-only. It does not create, initialize, open, verify, or
write the default canonical research store. A complete import, forced
interruption/resume, idempotent rerun, conflicting-payload rejection,
append-only attempts, reference-baseline query exclusion, performance
measurement, and `verify_store()` health check must pass in an explicitly
selected, task-owned scratch directory outside the repository and `/tmp`. The
importer CLI requires that explicit destination and refuses to fall back to
the default canonical locator. A scratch store is retained for inspection;
immutable rows are never patched in place.

The `SCHEMA_FINDINGS` recorded from Phase 2a must be reviewed and any blockers
closed before canonical bootstrap is considered. The importer/schema PR must
be merged first. Canonical bootstrap — creating, initializing, or writing the
default canonical research store for the first time — is a separate,
separately authorised lifecycle task; it is not a continuation this importer
performs on its own.

`REFERENCE_BASELINE` rows retain legacy-reported scoring semantics exactly as
imported. Rebuilt runs use versioned current-scorer semantics. The two are
distinct scoring systems: they must never be presented as directly normalized
or directly comparable rankings without an explicit, documented
transformation between them.

## M2a amendment — resumable native historical backtests

M2a adds one application-owned BIG_LOTTO historical-backtest runner. A
caller-supplied canonical
`BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1` fixes the ordered target and
strategy matrix, draw-snapshot checksum, history bounds, dataset identity, and
replicate. The deterministic run identity also binds the exact runner commit,
runner version, resolved native strategy-source bytes, runtime fingerprint, and
the current versioned rule/scorer contract.

The CLI requires explicit manifest, draw-data, and research-data paths. It
never consults ambient `LOTTOLAB_DATA_DIR` and rejects the production canonical
research destination. The draw database remains read-only; the explicitly
selected research database is the only writable database.

Source checksum, every target identity, causal history availability, every
strategy identity, executability, BIG_LOTTO compatibility, and COMPLETE native
provenance are validated before the research repository is created or any
research write begins. Every accepted target must have at least one real source
row strictly earlier in the pinned canonical order. A target with zero prior
rows rejects the entire manifest with
`TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY`; no synthetic or target-equal cutoff is
permitted. A target with nonzero history below the manifest minimum remains a
terminal `INSUFFICIENT_HISTORY` attempt with its real cutoff and history count.

Each target × strategy attempt becomes visible through one `commit_target`
transaction containing the terminal target, its ordered ticket, current-scorer
result, or typed closure. SIGTERM requests a pause only after a completed
target transaction. The appended progress cursor carries reconciled run and
per-strategy status counts; resume pages the complete natural-key set and never
uses the aggregate count to select work. A completed identical invocation
returns an exact no-op before any repository write, summary, or terminal event.

Native historical backtests use `VERSIONED_CURRENT_SCORER`; reference baselines
remain `LEGACY_REPORTED`. M2a stores audit and per-strategy coverage summaries
with `rank_value = null` and does not perform promotion, ranking, portfolio
construction, or current-pointer mutation.

## M2b amendment — explicit, fail-closed production entrypoint

M2b adds an explicit `--production` mode to the M2a runner CLI, alongside the
existing scratch mode. Exactly one of `--research-data-dir` (scratch) or
`--production` must be selected; both or neither fails before any database
access. Production mode never accepts an explicit research-data path and never
falls back to a caller-supplied scratch path.

Production mode resolves its destination only through the same
`resolve_research_data_paths()` canonical locator D2 already names, never
through an ambient-only shortcut or a second entrypoint. It requires an
already-existing, schema-valid store: `verify_schema_read_only()` runs before
any writer is constructed, and a missing store fails closed with a distinct
reason code rather than being created. `SQLiteResearchRepository` is
constructed with `initialize=False`, so production mode can never create or
migrate the canonical store — bootstrap remains the separate, separately
authorised lifecycle task D2 and the Phase 2a amendment already describe.

A disk preflight also runs before writer construction, comparing
`shutil.disk_usage` on the resolved data directory against
`max(2 GiB, database size × 8)` free bytes required; insufficient space fails
closed and the error surfaces only the required and available byte counts.

This amendment is scope-limited to the CLI entrypoint. It does not run an M2b
pilot, does not open or write either production database, and does not by
itself authorize one. Actual production execution against the canonical store
remains a separate, separately authorised task.
