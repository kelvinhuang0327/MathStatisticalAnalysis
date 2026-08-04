# Downloaded lottery archive audit contract

`tools/audit_downloaded_lottery_archives.py` is a deterministic, read-only
audit tool for ZIP archives containing historical lottery CSV files. It
provides corroboration evidence for future review; it does not import rows,
adopt a source database, or alter the repository's canonical databases.

## Supported data

The auditor classifies a member from its CSV headers and row content rather
than its filename.

- `POWER_LOTTO` (`威力彩`): six unique zone-1 integers from 1–38 and one zone-2
  integer from 1–8. Zone-1 order is preserved and reported when it is not
  ascending; zone-1 comparison is set-based. Zone-1/zone-2 overlap is valid.
- `DAILY_539` (`今彩539`): five unique integers from 1–39 and no second-zone
  value.
- `BIG_LOTTO` (`大樂透`): six unique integers from 1–49 and one special number
  from 1–49. The special number may not overlap the six main numbers.
- `OTHER` and `UNKNOWN`: inventoried with raw game names, headers, member
  hashes, and row counts. No unsupported game mapping is invented.

CSV input is streamed directly from the ZIP member. UTF-8 and UTF-8 with BOM
are accepted; decoding uses strict errors. Supported Gregorian dates are
normalized to ISO `YYYY-MM-DD`, while raw date text and raw number order are
retained. Unsafe member names, corrupt archives, duplicate names, non-CSV
members, and structural issues are reported without extraction or repair.

## Safety contract

The tool never extracts files into the download directory, executes archive
content, follows URLs, accesses the network, installs dependencies, or writes
ZIP/CSV inputs. Reference SQLite files are opened with a read-only immutable
URI (`mode=ro&immutable=1`) and connection-level `PRAGMA query_only=ON`.
Neither reference database nor any WAL/SHM companion is written.

All paths are explicit command-line arguments. Runtime reports are written
only below the caller-provided `--output-dir`; the real-data verification for
this task uses its task-owned `.runs/.../LOTTERY_DOWNLOAD_ARCHIVE_AUDIT_PIPELINE_R1`
directory.

## CLI

```bash
python tools/audit_downloaded_lottery_archives.py \
  --download-root /path/to/archives \
  --source-db /path/to/source.sqlite3 \
  --target-db /path/to/target.sqlite3 \
  --output-dir /path/to/output
```

Required outputs are:

- `audit_summary.json`: sorted-key machine-readable inventory, validation,
  reconciliation, coverage, and hash-invariance evidence;
- `audit_report.md`: stable human-readable summary.

The bounded `mismatches.json` and `member_inventory.json` files contain the
detail rows used by the summary. No archive or CSV bytes are copied to the
output directory. `--no-human-report` suppresses only the Markdown output.

Exit codes are stable:

- `0`: audit completed without reference or overlapping candidate conflicts;
- `2`: operational error, corrupt archive, malformed reference authority, or
  database byte drift;
- `3`: the two reference databases have a semantic conflict;
- `4`: overlapping candidate/reference POWER_LOTTO values conflict;
- `5`: `--fail-on-conflict` was requested and reported candidate findings remain.

Missing candidate rows alone are not a conflict. They produce
`PARTIAL_CORROBORATION_ONLY` and exit 0 when all overlapping rows match. This
status must not be treated as source authority: the reference databases remain
the verified authority, and adoption or migration is a separate explicit
decision.

## Determinism

For identical input bytes and arguments, inventories, classifications,
mismatch ordering, missing ranges, JSON keys, and Markdown summaries are
stable. Filesystem enumeration order, timestamps, random identifiers, and
execution-specific values are not included in comparison output. Database
SHA-256 and byte-size values are recorded both before and after the read-only
audit so byte invariance is observable.
