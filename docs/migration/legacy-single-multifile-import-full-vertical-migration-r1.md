# Legacy single-/multi-file import full vertical migration R1

This migration extends the existing LottoLab draw-data import boundary to the
owner-authorized legacy import scope. It does not migrate prediction, strategy,
replay, or historical-results contracts.

## Authority and donor

- Owner authorization: `AUTHORIZE_LEGACY_SINGLE_MULTI_FILE_IMPORT_FULL_VERTICAL_MIGRATION_R1`.
- The packet-named legacy root was absent. The recovered read-only donor is
  `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` at commit
  `760de1bb4ab704f8ff0aed914114d5bfb283bb1a`.
- Only the packet-authorized text source paths were inspected from that donor.
  Donor databases and binary artifacts were not read.
- The donor semantics cover single CSV, multi-file sequential parsing, UTF-8/
  Big5 decoding, Daily 539 TXT, validation, duplicate handling, and upload
  routes. ZIP traversal is a target addition that reuses LottoLab's bounded
  archive boundary and does not claim donor ZIP parity.

## Target contract

The existing `/api/v1/draw-imports/preview` and `/commit` routes remain intact.
The new batch routes use the same draw-import family:

- `POST /api/v1/draw-imports/batch/preview`
- `POST /api/v1/draw-imports/batch/commit`

Inputs are explicit bounded base64 payloads for `.csv`, `.txt`, and `.zip`
files. ZIP members are sorted deterministically and accept only bounded CSV/TXT
members. Unsafe paths, symbolic links, unsupported extensions, corrupt archives,
Big Lotto bonus files, Bingo, and unsupported lottery labels are reported per
file/member and never reach persistence.

The importable contracts are `BIG_LOTTO`, `DAILY_539`, and `POWER_LOTTO`.
Daily/Power contracts are an explicit owner-authorized deviation from the
pre-task registry, which contained only the Big Lotto prize contract. This
change is limited to import validation; it does not alter prediction or
strategy mechanics.

## Persistence and audit

Preview is database-free. Commit re-parses the exact payload set, verifies the
manifest digest and parser version, then applies accepted rows in one SQLite
transaction. Semantically identical existing rows are `SKIPPED_DUPLICATE`.
Any existing-draw conflict rolls back all new draw writes and records one
FAILED ingestion audit with per-row dispositions. Source provenance retains the
archive/member locator and leaf filename without copying raw source files into
the repository.

The explicit CLI is:

```bash
lottolab import-legacy-draw-files \
  --input /absolute/path/to/archive.zip \
  --database /absolute/path/to/task-owned/lottolab.db
```

Use `--preview-only` for a DB-free report. Production/reference databases and
download archives remain outside the write scope.

## Verification scope

Focused tests cover the three rule shapes, donor CSV/TXT decoding, ZIP safety,
all required exclusions, deterministic batch manifests, API preview/commit,
mixed-lottery persistence, duplicate semantics, and atomic conflict rollback.
Real archive verification is performed only under the task-owned run root
`LEGACY_SINGLE_MULTI_FILE_IMPORT_FULL_VERTICAL_MIGRATION_R1`.
