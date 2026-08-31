# T539 prospective stack integration R1

> Synthetic cross-contract acceptance only. No real future outcome, draw refresh, database,
> historical replay, or production runtime is used.

## Integrated authorities

- Protocol commit: `acdb979c8351e6a1221296d399b0ed3cb1e5944c`
- Protocol tree: `2b8bcc8ca2293cdf144e3a4498393a8a788d59f9`
- Harness commit: `fbf020bd61c1d12205fb4a00dd7cc9b576a91592`
- Harness tree: `2776ecb8447395dc13d17a19f04e23609ca3a516`
- Common freeze ancestor: `be43b2add0416de016a0f3c9e9ea899d99067d17`
- Protocol JSON SHA-256: `694ee84e50b393b3ad3e3b40cf44ab4cbb269e5973c24b88accae44730ca43c8`
- Freeze manifest SHA-256: `f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8`
- Rule fingerprint: `eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446`
- Metric: `OFFICIAL_ANY_PRIZE_TARGET_RATE`

The protocol and harness load the same local freeze bytes and enforce the same rule fingerprint.
No interface adapter or compatibility repair is required.

## Sparse materialization

The worktree uses non-cone exact-path sparse checkout. Its materialized stack contains only:

- `pyproject.toml`
- the protocol builder, focused test, JSON artifact, and Markdown artifact;
- the shared freeze manifest;
- the observer source, focused test, and harness specification;
- this report and the cross-contract integration test.

No package, dependency, environment, or adjacent configuration path was added.

## Frozen harness equivalence

The three imported paths retain the exact harness-commit Git blob identities:

| Path | Git blob | SHA-256 |
|---|---|---|
| `tools/run_t539_prospective_shadow_observer.py` | `3d51b814a8e963f92b717aa60871f5ee792a9c4c` | `3c2378a34d52b241091959578651d4b55dd5e391d1c1bc28227ade8017a78bf6` |
| `tests/unit/test_t539_prospective_shadow_observer.py` | `5fa4c00a355c6a012c19ec04613fe52f7f96dbc6` | `af55e097d5bd382db1b269a9538828b0fcde4345efdf0a93995cf99512fd1312` |
| `docs/research/t539-prospective-shadow-observer-harness-r1.md` | `fcdb8be6644ba0d31b07cf9026944d61ec16b269` | `39e76f5d68b5961da91da686147b5e4fe7f7aa6e483956e84eb6b05cbf82c275` |

## Cross-contract acceptance

`tests/unit/test_t539_prospective_stack_integration.py` proves with a deterministic synthetic
target and outcome that:

1. protocol and harness freeze SHA and rule fingerprint are identical;
2. the protocol contains exactly 30 ordered K-by-window experiments;
3. PRETARGET materializes those 30 experiments and exactly 90 arm records;
4. every protocol K/window has the three corresponding observer arms;
5. PRETARGET exposes no target-outcome parameter and rejects outcome-shaped input;
6. POSTTARGET requires an existing snapshot and cannot rerun selection or prediction generation;
7. POSTTARGET leaves the snapshot and every prediction byte unchanged;
8. snapshot tampering fails with `SNAPSHOT_HASH_MISMATCH`;
9. `MISSED_PRETARGET_SEAL` maps to the protocol exclusion and cannot enter the valid cohort;
10. one complete valid synthetic observation maps to all 30 protocol records using only
    `B_MINUS_A` and `B_MINUS_C` exact paired differences;
11. no cross-K/window composite, weighted score, rank, or winner selection is present; and
12. the execution uses only the in-test synthetic target/outcome and local frozen artifacts.

Observed surface result: `30 experiments / 90 arm records`, with arms
`ORIGINAL_ROLLING`, `CALLABLE_FAMILY_DEDUP_ROLLING`, and
`CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE` in every experiment.

## Focused verification

- Cache-disabled focused pytest: `41 passed in 3.71s` across the protocol, harness, and
  integration test modules.
- Ruff with `--no-cache`: `All checks passed!` on the five stack Python paths.
- Pyright on the same five paths: `0 errors, 0 warnings, 0 informations`.
- The integration module's initial isolated acceptance run: `5 passed in 1.06s`.

## Boundary statement

```text
REAL_FUTURE_OUTCOME_ACCESS = NO
REAL_PROSPECTIVE_OBSERVATIONS = 0
RETROACTIVE_BACKFILL = NO
PROTOCOL_CHANGED = NO
FREEZE_CHANGED = NO
NEW_SELECTOR = NO
SIGNIFICANCE_RULE = NOT DEFINED
PROMOTION_RULE = NOT DEFINED
DB_ACCESS = NO
DB_WRITE = NO
PRODUCTION_RUNTIME_MUTATION = NONE
```
