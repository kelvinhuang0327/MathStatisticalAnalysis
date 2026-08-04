# Legacy single/multi-file historical import parity — R2

This document freezes the concise donor contract, target deviations, and real
acceptance result for `LEGACY_SINGLE_MULTI_FILE_IMPORT_FULL_VERTICAL_MIGRATION_R2`.

## Authority and target

- Donor: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Donor commit: `760de1bb4ab704f8ff0aed914114d5bfb283bb1a`
- Donor tree: `0c5834d9cd5131b29d69ebfe9e22e3df53da7856`
- Donor source paths: `src/core/handlers/FileUploadHandler.js`,
  `src/core/App.js`, `src/core/DataProcessor.js`, `src/services/ApiClient.js`,
  `lottery_api/routes/data.py`, `lottery_api/database.py`,
  `lottery_api/utils/csv_validator.py`, `lottery_api/schemas.py`,
  `lottery_api/app.py`, and `index.html`.
- Target persistence: the existing Historical V2 schema, additively extended
  with import-run/file/chunk/row metadata. No production or canonical DB is
  adopted.

## Parity contract

Single-file input accepts one CSV or ZIP, applies the archive auditor and
lottery rules, previews before persistence, records provenance, reports
per-file and aggregate outcomes, and safely supports repeat invocation.

Multi-file input sorts files deterministically, processes each file/member
independently, continues after a file failure, aggregates accepted candidates,
detects duplicates/conflicts across the batch and existing Historical V2, and
persists accepted rows in independently atomic chunks of at most 500 rows.
Earlier committed chunks survive a later chunk failure.

## Exclusion and deviation ledgers

| Condition | Result |
| --- | --- |
| Bingo filename/member | `BINGO_EXCLUDED` |
| Requested lottery filter mismatch | `LOTTERY_FILTER_MISMATCH` |
| Unknown game | `UNKNOWN_GAME_TYPE` |
| Legacy-only target | `UNSUPPORTED_TARGET_LOTTERY` |
| Unsafe/encrypted archive member | `UNSAFE_ARCHIVE_MEMBER` / `ENCRYPTED_ARCHIVE_MEMBER` |
| Invalid number count/range/duplicate | Stable `INVALID_*` / `DUPLICATE_NUMBER` reason |
| Invalid special/second number | `INVALID_SPECIAL_NUMBER` / `INVALID_SECOND_NUMBER` |
| Empty or unsupported input | `EMPTY_FILE` / `UNSUPPORTED_FILE_TYPE` |
| Unsupported Big Lotto bonus draw | `UNSUPPORTED_BONUS_DRAW` |

Only `DAILY_539`, `BIG_LOTTO`, and `POWER_LOTTO` are persisted. Identical
`(lottery_type, draw_number)` content is `DUPLICATE_SKIPPED`; a same-key row
with different date or numbers is `CONFLICT_REJECTED`, is never overwritten,
and appears in row, file, and aggregate results. Same draw numbers across
different lottery types remain distinct.

Mandatory target deviations are escaped component rendering instead of donor
`innerHTML`; explicit conflict reporting instead of the donor's silent
same-key ignore; the current JSON/base64 upload boundary rather than local
filesystem paths; and current Historical V2 storage without new public
lottery enum values or a parallel database.

## Transaction semantics

Each accepted-row chunk commits or records a failed chunk independently.
Failed file/parser status is retained in the run result even when another file
imports successfully. Preview is read-only; import uses only the task-configured
disposable SQLite database and persists source SHA-256, archive member, source
row, draw identity, normalized record hash, and chunk/run provenance.

## Real 20-ZIP acceptance

Using the packet `DOWNLOAD_ROOT` and disposable databases under the task-owned
runtime root:

- 20 ZIP archives were imported individually and as one multi-file batch.
- 9,657 rows were parsed, valid, and imported; no duplicate, conflict, or
  persistence-failure rows occurred in this clean corpus.
- Individual mode: 20 completed runs, 34 chunks, maximum chunk size 500.
- Multi-file mode: one completed run, 20 chunks, maximum chunk size 500.
- Single-vs-multi accepted content parity: `true`.
- Source reference SHA-256 remained
  `9a697b3384d469f032d0649e8fd05b9a9900beb46e5527b129e3b1a6624d434a`.
- Target reference SHA-256 remained
  `457a52baba575463c78dbe62f0d5b406101d24b250e26bbcc2d0eba648179af4`.

The reference databases are read-only comparison authorities; no production
or canonical database migration/adoption is authorized by this task.
