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
