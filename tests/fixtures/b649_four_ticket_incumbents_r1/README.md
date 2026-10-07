# Four-ticket incumbent binding witnesses

`current.json` and `historical.json` preserve the exact best portfolio, count,
and declared portfolio hash from the committed research authorities named in
`SOURCE_AUTHORITY`. They are verification inputs; callers select the authority
for each invocation.

| Witness | Source commit | Source artifact SHA256 |
| --- | --- | --- |
| Current | `82e88ada111bf6d0999ac9c0c167a160a6ae5df8` | `0d948aa4556e9493e0c55d9fb8436c7b0aaaa9f2744bb9ecf85f16405c23cc1c` |
| Historical | `e7b472a97c4ab6c87a3f40211b9d97aaaa705b7b` | `d233d6ab14efae0813055cf29699c7dc2a29c33769d1a328d066d845bb6ae078` |

Current source:
`docs/research/matrix-native-results/b649-k20-overlap-block-repartition-12-8-exhaustive-r1-result.json`.
Historical source:
`docs/research/matrix-native-results/b649-k20-v7-three-ticket-global-repair-pilot-r1-result.json`.

The current authority declares artifact-order compact-JSON portfolio SHA256
`10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b`.
The runner normalizes that same K20 portfolio to
`eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c`.
The canonical OFFICIAL_ANY_PRIZE count is `313263888`.

Invocation requires both `--incumbent-artifact` and
`--incumbent-artifact-sha256`. The latter pins the bytes of the exact input
file supplied, including when the authority is an absolute external path.
The reduced witnesses have their own file digests. The loader accepts exactly
one declared portfolio-hash convention: normalized `BEST_SHA256`, or
artifact-order `BEST_PORTFOLIO_SHA256`, with `BEST_PORTFOLIO` and `BEST_COUNT`.
The runner validates K20, independently hashes the portfolio and performs the
canonical recount before accepting it.

`compatibility.json` records the donor commit/tree and byte digests of every
search/evaluator/checkpoint helper outside the binding call chain. Its
historical proposal prefix was characterized by executing donor
`5c06ab6f43067a6e5a5f8a3a308651b0bdb440ec`: the first 64 raw proposals from
each of the first two seeded quadruples, including emitted portfolio hashes.
The focused tests reproduce the exact historical state and prefix, exercise
current-load and rejection gates, and stub the pilot scan when testing the
promotion and result-identity binding. No heavy pilot is required.
