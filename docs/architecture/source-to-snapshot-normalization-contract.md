# Source-to-Snapshot Normalization Contract

Status: deterministic synthetic derivation foundation, version 1.0.0.

## Scope and claims

This contract proves one closed derivation chain:

```text
exact supplied source bytes
  -> synthetic_draw_csv 1.0.0
  -> lottolab_source_to_snapshot 1.0.0
  -> deterministic DatasetSnapshot
  -> deterministic DatasetNormalizationManifest
  -> byte-identical replay
```

It proves deterministic derivation only. It does not prove source authority,
production-source correctness, ingestion approval, persistence, canonical
evidence, metric validity, or ranking validity. It creates no default data,
database, network source, API, CLI, scheduler, or service endpoint.

## Adopted owner decisions

All eight owner decisions use Option A:

- D1: use a standalone `DatasetNormalizationManifest`; do not extend snapshot
  or provenance models with normalization lineage.
- D2: support only a closed synthetic CSV format; select no production source.
- D3: reject the whole run when any record is rejected; expose no partial
  snapshot or manifest.
- D4: require each source sequence to equal its zero-based logical-record index.
- D5: reject identical and conflicting duplicate IDs or sequences; never
  deduplicate or select a winning row.
- D6: use `IDENTITY_ORDER_PRESERVING`; do not create per-record lineage.
- D7: keep the implementation Git OID optional and omit it when absent.
- D8: defer source-authority approval to a future ingestion approval artifact;
  create no authority registry here.

## Artifact graph

The manifest references the exact input declaration and normalized snapshot
hash. The snapshot does not reference the manifest. This direction prevents a
hash cycle and keeps `DatasetSnapshot` a content identity rather than a
derivation-event identity.

The manifest is timeless. It contains no timestamp, person, host, machine path,
process identifier, database identity, ingestion state, authority status,
registry status, metric, or ranking value.

## Closed identities

| Identity | Exact value |
| --- | --- |
| Manifest schema ID | `lottolab.normalization.dataset_normalization_manifest` |
| Manifest schema version | `1.0.0` |
| Source format ID | `synthetic_draw_csv` |
| Source format version | `1.0.0` |
| Normalizer ID | `lottolab_source_to_snapshot` |
| Normalizer version | `1.0.0` |
| Mapping kind | `IDENTITY_ORDER_PRESERVING` |
| Format definition | `contracts/normalization/formats/synthetic_draw_csv_v1.json` |
| Normalizer contract | `docs/architecture/source-to-snapshot-normalization-contract.md` |

There is no aliasing or auto-detection. A semantic change requires a future
contract or format version.

## Pure in-memory boundary

`normalize()` accepts source bytes, the exact format identity, closed
normalization parameters, a `DatasetProvenance`, and an optional declared
implementation Git OID. It uses only its arguments, closed module constants,
deterministic standard-library operations, evidence models and canonical JSON,
and the committed domain rule contract.

The function does not open or write files, inspect Git or repository state,
read environment/locale/timezone/clock/randomness/host/process state, invoke a
subprocess, access a database or network, create a data directory, or emit an
artifact. Definition-file bytes are hashed at development time and pinned as
closed constants; the pure function never reads those files.

## Parameters and rule binding

`NormalizationParameters` contains only `dataset_id`, `dataset_version`, and
`lottery_type`. Only `BIG_LOTTO` may pass version 1.0.0. Its rule is resolved
through `resolve_lottery_rule_contract` and must be complete, active, primary,
and bound without overrides. Count, range, uniqueness, overlap, canonical
ordering, and rule version come only from that resolved contract.

Synthetic provenance requires a `dataset_id` beginning `SYNTHETIC_`;
non-synthetic provenance forbids that prefix. The supplied provenance is copied
field-for-field into both the snapshot and manifest. For
`LOCAL_COMMITTED_FILE`, the SHA-256 of exact supplied bytes must equal
`source_file_sha256` before parsing starts. `SYNTHETIC` and
`EXTERNAL_DECLARED` inputs are hashed without upgrading their trust.

## Synthetic CSV 1.0.0 grammar

The byte limit is 1,048,576. Only ASCII graphic bytes `0x20` through `0x7E`
and LF `0x0A` are allowed. BOM, CR/CRLF, tab, NUL, non-ASCII bytes, invalid
UTF-8, and other controls reject the source. Input ends with exactly one LF,
contains no blank physical line, and includes at least one data record.

The header is exactly:

```text
draw_id,draw_sequence,draw_date,main_numbers,special_numbers
```

There is no trimming, case folding, aliasing, field reordering, optional field,
unknown field, duplicate field, quoting, escaping, or multiline record. Each
physical line is one logical record. The limit is 10,000 data records, 512 bytes
per record excluding LF, 128 bytes per field, and exactly five fields.

`draw_id` matches `^[A-Z0-9][A-Z0-9_-]{0,63}$`. Integers match
`^(0|[1-9][0-9]*)$` using ASCII digits and contain at most ten digits. Leading
zeros, signs, whitespace, underscores, full-width digits, decimals, separators,
and empty tokens reject. Dates match exact `YYYY-MM-DD` form and must be real
Gregorian calendar dates; no timestamp, timezone, alternate separator, or
conversion is accepted.

Number lists use only `|`. Source numbers must already be ascending; the
normalizer never sorts. Counts, ranges, uniqueness, and main/special overlap
are checked against the bound rule contract.

This grammar intentionally diverges from the tolerant application import path
in `src/lottolab/infrastructure/imports/csv_draws.py`. That path may strip a
BOM, trim fields, accept leading zeros, sort numbers, ignore unknown columns,
and return partial rows. The evidence-grade normalizer does none of those and
does not import or reuse that parser.

## Mapping, completeness, duplicates, and dates

Finding ordinals are one-based for data rows and zero for run-level findings.
Output sequence is zero-based: source ordinal `n` maps to sequence `n - 1`.
Output order is source order. No sorting, byte-offset table, row hash table, or
mapping table exists.

A pass satisfies all of these equalities:

```text
source_record_count = accepted_record_count + rejected_record_count
accepted_record_count = source_record_count
rejected_record_count = 0
normalized_draw_count = accepted_record_count
normalized_draw_count = len(snapshot.draws)
```

Blank or malformed rows are never skipped. Duplicate IDs, duplicate sequences,
identical repeated records, conflicting repeated records, gaps, reordering,
ordinal mismatches, and decreasing dates reject the entire run. Equal dates are
allowed when IDs and sequences remain unique and dates are non-decreasing.

## Outcome precedence and findings

Outcome precedence is:

1. `NORMALIZATION_INPUT_UNVERIFIED`
2. `NORMALIZATION_CONTRACT_FAILURE`
3. `NORMALIZATION_REJECTED_SOURCE`
4. `NORMALIZATION_OUTPUT_HASH_MISMATCH`
5. `NORMALIZATION_PASS`

Findings use only the `NRM_SRC_*`, `NRM_REC_*`, `NRM_DUP_*`, `NRM_RULE_*`,
`NRM_SEQ_*`, `NRM_LIN_*`, and `NRM_REPLAY_*` namespaces. They are sorted by
source ordinal, reason code, and field. Messages are bounded printable ASCII
and never contain raw rows, full source bytes, paths, tracebacks, or raw parser,
OS, or validation exceptions.

The stable version-1 reason-code vocabulary is:

| Boundary | Codes |
| --- | --- |
| Input and format | `NRM_SRC_INPUT_HASH_MISMATCH`, `NRM_SRC_TOO_LARGE`, `NRM_SRC_INVALID_BYTE_DOMAIN`, `NRM_SRC_FINAL_LF_REQUIRED`, `NRM_SRC_EXTRA_FINAL_LF`, `NRM_SRC_BLANK_RECORD`, `NRM_SRC_HEADER_MISMATCH`, `NRM_SRC_RECORD_LIMIT_EXCEEDED`, `NRM_SRC_RECORD_TOO_LARGE`, `NRM_SRC_FIELD_COUNT_MISMATCH`, `NRM_SRC_FIELD_TOO_LARGE`, `NRM_SRC_QUOTING_FORBIDDEN`, `NRM_SRC_FORMAT_ID_UNSUPPORTED`, `NRM_SRC_FORMAT_VERSION_UNSUPPORTED` |
| Record lexical form | `NRM_REC_DRAW_ID_INVALID`, `NRM_REC_SEQUENCE_LEXICAL_INVALID`, `NRM_REC_DATE_LEXICAL_INVALID`, `NRM_REC_DATE_INVALID`, `NRM_REC_INTEGER_LEXICAL_INVALID`, `NRM_REC_NUMERIC_TOKEN_TOO_LONG` |
| Duplicates | `NRM_DUP_DRAW_ID`, `NRM_DUP_SEQUENCE`, `NRM_DUP_RECORD_CONFLICT` |
| Rule binding | `NRM_RULE_CONTRACT_UNAVAILABLE`, `NRM_RULE_UNSUPPORTED_LOTTERY`, `NRM_RULE_MAIN_COUNT_MISMATCH`, `NRM_RULE_SPECIAL_COUNT_MISMATCH`, `NRM_RULE_NUMBER_OUT_OF_RANGE`, `NRM_RULE_NUMBER_ORDER_INVALID`, `NRM_RULE_DUPLICATE_NUMBER`, `NRM_RULE_MAIN_SPECIAL_OVERLAP` |
| Sequence and date | `NRM_SEQ_ORDINAL_MISMATCH`, `NRM_SEQ_GAP`, `NRM_SEQ_DATE_REGRESSION` |
| Lineage and output | `NRM_LIN_COUNT_MISMATCH`, `NRM_LIN_SOURCE_MIRROR_MISMATCH`, `NRM_LIN_DATASET_HASH_MISMATCH`, `NRM_LIN_MANIFEST_HASH_MISMATCH`, `NRM_LIN_PARAMETERS_INVALID`, `NRM_LIN_IMPLEMENTATION_OID_INVALID`, `NRM_LIN_CONTRACT_IDENTITY_MISMATCH` |
| Replay | `NRM_REPLAY_SNAPSHOT_MISMATCH`, `NRM_REPLAY_MANIFEST_MISMATCH` |

A pass has a snapshot and manifest and no findings. Every non-pass has findings
and exposes neither artifact. No exception message becomes a reason code.

## Snapshot construction

The existing evidence `DatasetSnapshot`, `DrawEntry`, `RuleParameters`, and
`DatasetProvenance` models are unchanged. The snapshot copies parameter
identity, resolved rule binding, supplied provenance, deterministic draws, and
the existing evidence schema identity. `special_numbers` is always serialized
as an array. The dataset hash is LCJ-1 SHA-256 of the snapshot with only
`dataset_sha256` removed.

The generated snapshot must satisfy the existing semantic checks: rule binding
self-hash, dataset self-hash, contiguous zero-based sequences, unique IDs,
non-decreasing dates, and bound number constraints.

## Manifest fields

| Field | Meaning |
| --- | --- |
| `schema_id`, `schema_version` | Closed standalone manifest identity |
| `source` | Exact supplied `DatasetProvenance` |
| `source_input_sha256` | SHA-256 of exact supplied bytes |
| source format fields | Exact format ID, version, path, and raw-file hash |
| normalizer fields | Exact normalizer ID, version, path, and raw-file hash |
| `normalizer_implementation_git_oid` | Optional 40-character lowercase Git OID |
| `normalization_parameters` | Closed dataset ID/version/lottery parameters |
| `record_mapping_kind` | `IDENTITY_ORDER_PRESERVING` |
| count fields | Complete pass counts only |
| `normalized_dataset_sha256` | Exact generated snapshot identity |
| `manifest_sha256` | Self-key-removed LCJ-1 manifest identity |

The manifest adds no parameters hash, lineage table, duplicate count,
rejection-summary hash, source byte count, timestamp, or producer metadata.

## Canonical bytes and replay

Snapshot and manifest in-memory bytes are compact, key-sorted LCJ-1 UTF-8 with
no trailing LF. Committed bytes add exactly one LF. No BOM, CR, null value,
binary float, or Unicode normalization is introduced. Definition hashes cover
the raw committed definition files including their one LF; neither definition
contains its own hash.

`verify_replay()` compares exact committed snapshot and manifest bytes. A
snapshot mismatch yields `NRM_REPLAY_SNAPSHOT_MISMATCH`; a manifest mismatch
yields `NRM_REPLAY_MANIFEST_MISMATCH`; both are deterministically ordered. Any
mismatch returns `NORMALIZATION_OUTPUT_HASH_MISMATCH` with no artifacts. A
non-pass is returned unchanged and exact matches preserve the original pass.

Identical arguments yield identical outcome, findings, canonical bytes, and
committed bytes. Changing only the declared implementation OID leaves snapshot
content unchanged and changes manifest lineage.

## Trust ladder and ingestion boundary

Normalization never upgrades trust. Synthetic output remains synthetic and may
support only synthetic-test evidence. External-declared output remains
unverified. Local committed provenance binds exact supplied bytes but does not
by itself grant authority. Registry injection cannot override these states.

Source-authority review, ingestion approval, persistence, registry population,
production-source support, and authoritative data selection are separate
future artifacts and tasks. This contract emits no ingestion status and makes
no claim about real lottery data.

## Accepted limitations

Version 1 supports one synthetic CSV grammar, one proven BIG_LOTTO rule
contract, identity/order-preserving lineage, no per-row lineage table, and an
optional implementation OID. It validates deterministic derivation, not the
truth, completeness, authority, or production fitness of a source.
