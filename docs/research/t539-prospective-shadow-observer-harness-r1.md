# T539 prospective shadow observer harness R1

> Implementation harness only. Verification uses synthetic fixtures. This work observes no
> real target after the freeze boundary and establishes neither predictive advantage nor
> profitability.

## Frozen identity

- Freeze manifest: `docs/research/matrix-native-results/t539-callable-family-dedup-prospective-shadow-freeze-r1.json`
- Freeze manifest SHA-256: `f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8`
- Freeze boundary: `115000186`
- Rule fingerprint: `eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446`
- Sealed pilot commit: `0a4355cfcd13b26451e6d6c74bc873ca2b12fcdd`
- Sealed pilot result SHA-256: `1a4fbd067f3d9b4735a4a1143b3694222f38f05eb3ec91e4e8b782e0e90c5c86`

The runner verifies the manifest bytes before either phase. It fails with
`FREEZE_IDENTITY_DRIFT` if that artifact changes. The manifest remains read-only.

## Structural phase boundary

The implementation has two public Python interfaces:

```python
pretarget_prepare(
    *,
    target_identity: str,
    pretarget_inputs: Mapping[str, Any],
    freeze_path: Path = DEFAULT_FREEZE_PATH,
) -> dict[str, Any]

posttarget_score(
    *,
    snapshot: Mapping[str, Any] | None,
    official_outcome: Mapping[str, Any],
    pretarget_seal_status: str = MISSED_PRETARGET_SEAL,
    freeze_path: Path = DEFAULT_FREEZE_PATH,
) -> dict[str, Any]
```

`pretarget_prepare` has no official-outcome parameter. Its input is closed-schema JSON, and
known target-outcome fields are rejected recursively with
`TARGET_OUTCOME_PRESENT_DURING_PRETARGET`. Unknown fields are also rejected. The only
outcome-shaped data it accepts are historical selector metrics whose target identities are
validated as strictly less than the explicit prospective target.

`posttarget_score` receives no pretarget input bundle and has no strategy registry, selector
universe, or prediction generator argument. It reads only predictions already sealed in the
snapshot. Snapshot verification deliberately validates selector state without selecting again.

## PRETARGET input authority

The Phase-1 authority is an explicit JSON bundle with schema
`T539_PROSPECTIVE_PRETARGET_INPUT_V1`:

```json
{
  "authority_identity": "OPAQUE_LOGICAL_IDENTITY",
  "cells": [
    {
      "history": [
        {
          "candidate_metrics": [
            {
              "identity": ["SOURCE", "T539", "strategy_id", "strategy_version"],
              "prize_tier_counts": [0, 0, 0, 1],
              "success": true,
              "winning_ticket_count": 1
            }
          ],
          "target_identity": "STRICTLY_EARLIER_TARGET"
        }
      ],
      "k": 1,
      "lottery_id": "T539",
      "predictions": [
        {
          "identity": ["SOURCE", "T539", "strategy_id", "strategy_version"],
          "tickets": [[1, 2, 3, 4, 5]]
        }
      ]
    }
  ],
  "outcome_presence": "ABSENT",
  "schema_version": "T539_PROSPECTIVE_PRETARGET_INPUT_V1"
}
```

The bundle must contain exactly the ten frozen K cells. Every cell must provide at least 750
strictly earlier, numerically ordered historical targets. The final 750 target identities must
match across cells. Every historical target and target-prediction set must cover the complete
frozen original candidate universe for that K. This makes missing-candidate selection drift fail
closed.

Predictions are generated before the harness is called and while the target outcome is absent.
The harness validates and normalizes their native T539 tickets, then copies only the selected
prediction into the snapshot. It never calls production strategy code or a database. The opaque
logical authority identity cannot be an absolute filesystem path. Phase 1 computes the authority
hash from compact, sorted-key JSON of the fully normalized bundle, so the snapshot records both:

- `input_authority.identity`
- `input_authority.sha256`

## Frozen selector reproduction

For each K and each W50/W300/W750 experiment, Phase 1 takes the exact trailing window from the
supplied complete history. Candidate ordering reproduces the sealed pilot:

1. historical any-prize success count, descending;
2. historical prize-tier count vector `[hits5, hits4, hits3, hits2]`, descending
   lexicographically;
3. historical winning-ticket count, descending;
4. strategy ID, ascending.

All candidates in a cell have the same window denominator and native ticket count, so the pilot's
rate ordering is exactly the count ordering above.

The 30 K×window experiments each contain, in fixed order:

1. `ORIGINAL_ROLLING`
2. `CALLABLE_FAMILY_DEDUP_ROLLING`
3. `CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE`

The original arm uses the manifest's complete original universe. The deduplicated rolling arm
uses only the manifest's 26 fixed lexical callable representatives across cells. The frozen arm
uses the exact per-cell/window baseline identity in the manifest. No representative, K, window,
arm, or selection rule is inferred or optimized by the harness.

## PRETARGET snapshot and hash

The output schema is `T539_PROSPECTIVE_PRETARGET_SNAPSHOT_V1`. It contains:

- target identity;
- freeze ID, boundary, manifest SHA, and sealed pilot result SHA;
- immutable rule fingerprint;
- input authority logical identity, schema, and normalized content hash;
- the exact 30-experiment and 90-arm surface description;
- deterministic experiment and arm indices;
- every exact history target identity used by each experiment;
- the arm's frozen candidate-universe hash and candidate count;
- selected strategy identity and callable identity;
- aggregated selector statistics for each rolling candidate;
- exact normalized native ticket predictions;
- `snapshot_content_hash`.

The snapshot hash is SHA-256 over UTF-8 compact JSON with sorted keys and no trailing newline,
after removing only `snapshot_content_hash`. The snapshot contains no wall-clock time, PID,
absolute path, worktree path, object address, or environment-derived metadata. Human-readable
serialization uses sorted keys, two-space indentation, UTF-8, and one trailing newline. Identical
input therefore produces byte-identical output.

## POSTTARGET scoring

The official-outcome input is closed-schema JSON:

```json
{
  "schema_version": "T539_OFFICIAL_OUTCOME_V1",
  "target_identity": "THE_SAME_TARGET_AS_THE_SNAPSHOT",
  "winning_numbers": [1, 2, 3, 4, 5]
}
```

Before scoring, Phase 2 verifies the snapshot hash, freeze identity, rule fingerprint, target,
30-experiment ordering, all three arms, frozen universe identities/hashes, history boundaries,
window suffix relationships, native ticket counts, and deterministic ticket ordering. It then
computes only raw target-level fields from each sealed ticket:

- matched numbers and hit count per ticket;
- official any-prize target success (`2..5` hits on at least one ticket);
- official winning-ticket count;
- official prize-tier count vector `[hits5, hits4, hits3, hits2]`.

The result contains no cumulative winner, window weighting, composite score, significance rule,
promotion decision, predictive claim, or profitability claim. Its deterministic
`result_content_hash` uses the same compact canonicalization rule and excludes only itself.

## Prospective classification

Filesystem creation time is not prospective evidence. The external publication/timestamp
mechanism is intentionally outside this implementation. Phase 2 therefore requires an explicit
seal classification:

- `PRETARGET_SEAL_CONFIRMED_BEFORE_OUTCOME` produces
  `VALID_PROSPECTIVE_OBSERVATION` and sets
  `counts_as_valid_prospective_observation` to `true`.
- `MISSED_PRETARGET_SEAL` still permits a structurally valid raw score for diagnosis, but preserves
  the same status and sets `counts_as_valid_prospective_observation` to `false`.

The fail-closed default is `MISSED_PRETARGET_SEAL`. A reconstructed snapshot cannot silently
become a prospective observation. The external authority—not this harness—must establish and
retain evidence that a seal existed before outcome availability.

## CLI

```text
uv run python tools/run_t539_prospective_shadow_observer.py pretarget-prepare \
  --target-identity SYNTHETIC_TARGET \
  --input-json SYNTHETIC_PRETARGET_INPUT.json \
  --snapshot-json SYNTHETIC_PRETARGET_SNAPSHOT.json

uv run python tools/run_t539_prospective_shadow_observer.py posttarget-score \
  --snapshot-json SYNTHETIC_PRETARGET_SNAPSHOT.json \
  --outcome-json SYNTHETIC_OUTCOME.json \
  --result-json SYNTHETIC_TARGET_SCORE.json \
  --pretarget-seal-status MISSED_PRETARGET_SEAL
```

The CLI does not create parent directories. Callers choose output paths. This task did not invoke
the CLI with real data.

## Implementation verification boundary

```text
REAL_FUTURE_OUTCOME_ACCESS = NO
REAL_PROSPECTIVE_OBSERVATIONS = 0
RETROACTIVE_BACKFILL = NO
DB_WRITE = NO
PRODUCTION_RUNTIME_MUTATION = NONE
NEW_SELECTOR = NO
PREDICTIVE_ADVANTAGE = NOT ESTABLISHED
PROFITABILITY = NOT ESTABLISHED
```
