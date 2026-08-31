# T539 PRETARGET external seal authority — Owner decision R1

This is the durable record of the already-approved Owner decision for
`T539_PRETARGET_EXTERNAL_SEAL_RECEIPT_R1`. It contains no credential, signing secret, private
key, or real prospective observation.

## Authorization and scope

- Owner authorization: `AUTHORIZE_T539_PRETARGET_EXTERNAL_SEAL_RECEIPT_R1`
- Authorization status: `PRESENT`
- Task class: `STATE_CHANGING_IMPLEMENTATION`
- Worker route: `STANDARD_JUDGED`
- Real Rekor publication: `NOT AUTHORIZED`
- Real Rekor lookup: `NOT REQUIRED FOR ACCEPTANCE`
- Network tests: `NO`
- Real future-outcome access: `NO`
- Database access/write: `NO` / `NO`
- Production runtime mutation: `NONE`

The external seal begins only after an existing valid `PreOutcomeTargetRegistration` and a
deterministic PRETARGET snapshot exist. The existing registration service/store and its
`registration_digest`, `prediction_input_identity`, and `outcome_binding_identity` remain the
authority and are not replaced or redefined.

## External authority

- External timestamp trust root: Sigstore public-good TUF root
- Rekor service: `https://rekor.sigstore.dev`
- Rekor entry kind: `hashedrekord`
- Receipt lookup: UUID / Rekor EntryID
- Signing-key policy: ephemeral key only
- Secret retention: `NONE`
- Receipt retention: `PERMANENT`
- Outcome-time authority: official `DAILY_539` schedule lower bound
- Normal schedule: `20:30 Asia/Taipei`
- Reschedule authority: official Taiwan Lottery announcement
- Late-seal policy: `MISSED_PRETARGET_SEAL`
- Retroactive backfill: `FORBIDDEN`
- Duplicate policy: `FIRST_VALID_EXTERNAL_RECEIPT_WINS`
- Conflict policy: `FAIL_CLOSED`

Only successfully verified server-side Rekor integrated/log authority time may qualify a seal,
and it must be strictly earlier than the official outcome-authority time. Equality is late.
Local clocks, filesystem metadata, Git author/committer dates, mutable SQLite timestamps, and
caller-supplied external timestamps are not seal authority.

## Frozen research identity

- Lottery type: `DAILY_539`
- Freeze boundary: `115000186`
- Freeze manifest SHA-256:
  `f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8`
- Rule fingerprint:
  `eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446`
- Integrated stack commit: `1fdb2d53a7ef62baa8bdbd5ce962f7aeb0176c62`
- Integrated stack tree: `7a3e0a6892cf666ef9f20826225ccfffab455e07`

## Canonical seal decision

`T539_PRETARGET_SEAL_V1` binds exactly:

- `schema_version`
- `target.lottery_type`, `target.draw_number`, and `target.draw_date`
- `snapshot_content_hash`
- `rule_fingerprint`
- `freeze_boundary`
- `freeze_manifest_sha256`
- `integrated_stack_commit`
- `integrated_stack_tree`
- `pre_outcome_registration_digest`

Canonical bytes are sorted-key compact UTF-8 JSON with no trailing newline.
`seal_digest = SHA256(canonical seal bytes)`. No timestamp or outcome number is part of the
canonical seal identity.

## Receipt and lifecycle decision

A UUID alone is never a qualifying receipt. The retained UUID must equal the RFC 6962 leaf hash
of the verified canonical entry body. The permanently retained record must also include the
log/shard identity when present, log index, Rekor integrated time, canonical entry body and hash,
exact seal digest, signing/bundle identity, signed-entry/inclusion material, and the identity plus
canonical SHA-256 version of the exact trust root used for successful verification.

The first structurally valid, externally verified, timely receipt wins. An exact retry is
idempotent and retains the original Rekor authority time. A competing seal, snapshot, or receipt
is `CONFLICT` and cannot overwrite the winner. If the window closes without a qualifying
receipt, the durable state is `MISSED_PRETARGET_SEAL`; it can never be backfilled into a valid
prospective observation.

After restart, the implementation must load the existing registration, deterministic snapshot,
and local record; reverify the seal and external evidence; compare the fresh successful
trust-root/verifier reference with the retained reference; and never mint a replacement merely
because the process restarted. A missing snapshot after outcome time fails closed.

## Dependency decision

Hand-written TUF, Merkle-proof, or signature cryptography is forbidden. The only authorized new
cryptographic trust implementation dependency, if required, is `sigstore>=4.5,<5`, using the
official Sigstore Python client for trust-root and transparency verification.
