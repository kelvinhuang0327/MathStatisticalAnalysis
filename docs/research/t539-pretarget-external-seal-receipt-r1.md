# T539 PRETARGET external seal receipt R1

This implementation supplies the outcome-free external receipt boundary for the existing T539
prospective stack. Verification is synthetic and offline. It creates no Rekor entry, accesses no
future outcome, and writes no database or production runtime state.

## Canonical identity

`T539_PRETARGET_SEAL_V1` is a closed nine-field object. Its `target` is the closed
`lottery_type` / `draw_number` / `draw_date` identity, and the remaining fields bind the exact
snapshot, rule, freeze manifest/boundary, integrated stack commit/tree, and existing pre-outcome
registration digest. Serialization is sorted-key compact UTF-8 JSON without a newline; the
external artifact digest is SHA-256 of those exact bytes.

The canonical example in the focused test has seal digest:

```text
2e3b8849fc80103feefecf0eab125114dae12a49f86f2712d293374f4ecef998
```

No local, filesystem, Git, database, or caller timestamp appears in the seal. No outcome number,
outcome hash, or outcome payload appears in it.

## Registration and snapshot binding

The service reads the existing `PreOutcomeTargetRegistration`; it does not create or replace one.
Each durable record retains the existing `prediction_input_identity` and
`outcome_binding_identity`, while the seal binds the existing `registration_digest`.

The deterministic snapshot projection independently recomputes `snapshot_content_hash`, rejects
target-outcome-shaped keys, requires `DAILY_539`, requires the target strictly after
`115000186`, and matches the approved rule, freeze manifest, and target registration before a
seal can be built.

## Rekor evidence and verification

`RekorReceiptEvidence` persists:

- the lowercase Rekor UUID derived as the RFC 6962 leaf hash of the exact canonicalized entry
  body, plus log ID, log index, and integrated time;
- `hashedrekord` kind/version;
- canonicalized entry body plus its SHA-256;
- the exact seal digest;
- signing certificate/material SHA-256;
- signed-entry timestamp when present;
- the complete inclusion proof;
- the complete canonical Sigstore bundle and its SHA-256; and
- a self-verifying receipt identity.

The verification reference separately records the approved Sigstore public-good TUF root
identity and the `sha256:` fingerprint of the exact canonical trusted-root object used by the
successful verification, plus official client identity/version. Secret-shaped fields are
rejected before persistence; no private signing material is retained.

`SigstoreRekorReceiptVerifier` cross-checks every persisted receipt field against the supplied
bundle, including the derived Rekor UUID, then delegates artifact signature,
certificate/trust-root, Rekor body consistency, inclusion proof/checkpoint, and trusted-time
verification to the official `sigstore` client. The artifact given to Sigstore is the canonical
seal bytes, so the hashedrekord artifact digest is the exact `seal_digest`. The production
backend loads `ClientTrustConfig.production(offline=True)`, builds the official `Verifier` from
that exact root, and returns the root/client reference from the same successful verification
operation. An explicit caller-supplied certificate policy remains required. The backend has no
sign, publish, or network-lookup method.

## Create-once and restart behavior

The application service accepts only a `VerifiedRekorReceipt` returned by the injected verifier.
Rekor integrated time must be strictly earlier than the official schedule time retained by the
existing registration. Equality and later times create `MISSED_PRETARGET_SEAL`, not a seal.

The filesystem store writes and fsyncs a task-owned temporary file, hard-links it atomically to
the canonical target record name without replacement, fsyncs the directory, and then removes the
temporary link. Exact bytes are idempotent; different bytes conflict. Records use a bounded,
self-hashed canonical envelope and are revalidated on every read. Restart recovery reloads the
registration and snapshot, validates the stored seal, reruns receipt verification, and requires
the freshly returned trust-root/verifier reference to equal the persisted reference. It never
mints a replacement receipt.

## Synthetic acceptance boundary

The focused tests cover exact bytes/SHA, wrong lottery/boundary, registration/snapshot/rule/
freeze/stack mismatches, timely acceptance, raw/unverified rejection, non-authoritative local
time, equality/later rejection, exact retry, competing receipt/snapshot, restart, missing/late
receipt behavior, outcome/secret exclusion, exact reassociation, unrelated-EntryID rejection,
forged persisted-verification-reference rejection, tamper failure, and forced offline use of the
official verifier. All evidence is deterministic synthetic fixture data.

```text
REAL_REKOR_PUBLICATION = NO
REAL_FUTURE_OUTCOME_ACCESS = NO
REAL_PROSPECTIVE_OBSERVATIONS = 0
RETROACTIVE_BACKFILL = NO
LOCAL_TIME_AUTHORITY = NO
GIT_TIME_AUTHORITY = NO
SQLITE_TIME_AUTHORITY = NO
DB_WRITE = NO
PRODUCTION_RUNTIME_MUTATION = NONE
```
