# Strategy Matrix static lineage and redundancy map R1

## Scope and interpretation

This is a deterministic, DB-free static-source classification of the canonical
registered executable strategy universe. It evaluates implementation diversity only.
It does not evaluate historical behavior, statistical independence, predictive
advantage, prize probability, profitability, or production promotion.

- Study: `STRATEGY_MATRIX_STATIC_LINEAGE_REDUNDANCY_MAP_R1`
- Catalog: `src/lottolab/strategies/catalog.py:_PRODUCTION_DESCRIPTORS`
- Executable registry: `src/lottolab/strategies/executable_registry.py:ExecutableRegistry`
- Method: Python AST/static declarations only; LottoLab modules are not imported
- DB access/write: `NO` / `NO`
- Historical replay: `NOT RUN`
- Result SHA-256: `f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad`

## Aggregate summary

| Scope | Total | Resolved | Unresolved | Exact groups | IDs in exact groups | Parameterized families | DISTINCT_BINDING identities |
|---|---:|---:|---:|---:|---:|---:|---:|
| Overall | 135 | 131 | 4 | 0 | 0 | 2 | 122 |
| B649 | 123 | 119 | 4 | 0 | 0 | 1 | 117 |
| T539 | 2 | 2 | 0 | 0 | 0 | 0 | 2 |
| P638 | 10 | 10 | 0 | 0 | 0 | 1 | 3 |

## Exact identical bindings

No exact-identical binding group was statically established.

## Same callable, different static bindings

- `callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f` (7 IDs): `power_c01_recency_decay_1bet`, `power_c02_gap_overdue_1bet`, `power_c03_pair_centrality_1bet`, `power_c04_zone_balanced_1bet`, `power_c05_dispersion_match_1bet`, `power_c06_regime_cusum_1bet`, `power_c07_borda_ensemble_1bet`
- `callable-sha256:c3cf2b67e21ebb397b3fe49f754cf80b27242a5bee95255774bb1253fb270684` (2 IDs): `legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a`, `legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669`

## Dynamic or unresolved

- `legacy_biglotto__test_ces__78d17c530ab8`: `CONSTRUCTOR_REQUIRES_RUNTIME_ARGUMENTS:wave26_authority`
- `legacy_biglotto__test_dms__b63442289bd5`: `CONSTRUCTOR_REQUIRES_RUNTIME_ARGUMENTS:wave26_authority`
- `legacy_biglotto__test_greedy_optimizer__82df7f878ece`: `CONSTRUCTOR_REQUIRES_RUNTIME_ARGUMENTS:wave26_authority`
- `legacy_biglotto__test_mwsc__ba37643d6a3b`: `CONSTRUCTOR_REQUIRES_RUNTIME_ARGUMENTS:wave26_authority`

## Scientific boundary

`IDENTICAL_BINDING` means identical structural source binding and static payload.
`SAME_CALLABLE_DIFFERENT_BINDING` identifies parameter/configuration siblings and
does not call them duplicates. `DISTINCT_BINDING` means only that structural
binding identities differ. Normalized AST equality is not semantic equivalence,
historical-behavior equality, or statistical independence.
