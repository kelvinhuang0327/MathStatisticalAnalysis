# P600AB Phase S snapshot stop record

Status: STOPPED — no compliant canonical snapshot was produced

The P600AB R1 snapshot attempt is not valid migration or canonical-data evidence and
must not be used for parity, deployment, or cutover decisions. Although the source
connection requested SQLite `mode=ro` and `PRAGMA query_only=ON`, the canonical
WAL/SHM family did not remain metadata-stable: the SHM modification time advanced
from `2026-07-14T17:20:33+0800` to `2026-07-15T12:27:43+0800`, and WAL/SHM change
times also advanced during the attempt.

The attempted manifest could not detect that side effect. Its
`source_sidecars_before` values were collected only after the source connection had
closed, and its `source_changed_during_backup` flag covered only the main DB file.
The invalid uncommitted manifest had SHA-256
`6ce29227a29acb4f774d726ee139339e67800617c1c5b59143ca861536d5bb82`.
The uncommitted snapshot tool had SHA-256
`9eb5d5574a1ef064f78c26d94412a80848e4434caf2ef2e08158bf294374b909`.
Neither file is part of the accepted migration evidence.

No snapshot retry, SQLite open, checkpoint, WAL cleanup, service operation, or
canonical LotteryNew DB access is authorized by P600B R2. Existing attempted
snapshot bytes remain quarantined under ignored `.local/` storage and were not
opened, copied, hashed, staged, or committed during R2.

P600B R2 is explicitly decoupled from Phase S because its Strategy Catalog request
path is static metadata only. Its fixtures must be regenerated from the pinned
LotteryNew registry source with static parsing, no runtime import, no adapter
execution, and no database dependency.
