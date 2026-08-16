# EH01 / EH10 — B649 Track B ordinal/temporal — result

Status: SEALED — NO_SIGNAL (both hypotheses) ｜ 2026-08-16 ｜ B649 Track B

Preregistration (locked before any EH01/EH10 statistic was computed):
`eh01-eh10-b649-ordinal-temporal-v1-preregistration.md`.
Preregistration hash: `f12ef1314e4fd6cadcd28154b332f04afa46bb9593a23733708540ae3302c8f7`
(recorded in `eh01-eh10-b649-ordinal-temporal-v1-preregistration-hash.json`;
the execution script re-verifies this hash before running and refuses to
proceed if it doesn't match). Full machine-readable result:
`eh01-eh10-b649-ordinal-temporal-v1-result.json`. Attempt ledger:
`eh01-eh10-b649-ordinal-temporal-v1-attempt-ledger.json`. Result hash:
`0263e55b7fe0dc85797608aad283eac3d6013d4f9e41fae7847449ef03652bf3`.

## Identity

```text
TASK_ID:              B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1
HYPOTHESIS_FAMILY_ID: HIGHER_ORDER_TEMPORAL_STRUCTURE
EH01_VARIANT_ID:       EH01_MATRIX_PROFILE_MOTIF_DISCORD_B649_V1
EH10_VARIANT_ID:       EH10_PERMUTATION_ENTROPY_ORDINAL_B649_V1
LOTTERY_TYPE:          BIG_LOTTO
```

## Data provenance

Same clean BIG_LOTTO baseline used throughout this research program: 2,138
contamination-excluded draws (150 `DATE_LIKE` rows excluded — a different,
mislabeled game), 2007-03-09 to 2026-07-31. Read-only throughout
(`PRAGMA query_only`); no DB mutation. Logical content hash
`a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918`,
independently matching both the 2026-08-12 contamination audit and the
sealed `REGIME_CHANGE_POINT_CUSUM_B649_V1` cell's own provenance.

## EH01 result — causal matrix-profile motif/discord

| Endpoint | Observed | Global raw p | Global Holm p | ERA4 raw p | ERA4 Holm p |
|---|---:|---:|---:|---:|---:|
| motif_26 | -3.169 | 0.328 | 1.000 | 0.287 | 1.000 |
| motif_52 | -6.406 | 0.445 | 1.000 | 0.425 | 1.000 |
| motif_104 | -11.183 | 0.968 | 1.000 | 0.958 | 1.000 |
| discord_26 | 5.844 | 0.898 | 1.000 | 0.915 | 1.000 |
| discord_52 | 8.778 | 0.703 | 1.000 | 0.731 | 1.000 |
| **discord_104** | **13.078** | **0.117** | **0.702** | **0.124** | **0.744** |

`discord_104` (the length-104 causal discord — the query whose nearest
causal neighbor 26-104 weeks earlier is most distant) is the closest of the
six endpoints to significance and still falls far short of both the
`SIGNAL` (adjusted p <= 0.05 under both nulls) and `WEAK_SIGNAL` (adjusted p
<= 0.10 under the primary null) thresholds. Its era-local diagnostics show
no concentration in any one era either (observed percentile within that
era's own null: era1 0.877, era2 0.827, era3 0.498, era4 0.189 — bouncing
around the middle of the null distribution, not trending toward an extreme
in any one slice).

**Classification: `NO_SIGNAL`.** Every endpoint has global Holm-adjusted p >
0.10.

## EH10 result — causal rolling permutation entropy

| Endpoint | Observed `T_PE,d` | Global raw p | Global Holm p | ERA4 raw p | ERA4 Holm p |
|---|---:|---:|---:|---:|---:|
| pe_3 | 0.0190 | 0.995 | 1.000 | 0.999 | 1.000 |
| pe_4 | 0.0523 | 0.940 | 1.000 | 0.943 | 1.000 |
| pe_5 | 0.1416 | 0.979 | 1.000 | 0.988 | 1.000 |

Every order's observed low-entropy deficit falls in the *upper* tail of raw
p (i.e. the observed value is smaller/less extreme than nearly all 999
surrogates -- B649's rolling ordinal complexity is, if anything, slightly
*more* uniform than the exchangeable null typically produces, not less).
Era-local diagnostics for `pe_5` (the order closest to any structure) show
the same pattern in every era (percentiles 0.108-0.321, all comfortably
inside the null's bulk).

**Classification: `NO_SIGNAL`.** Every endpoint has global Holm-adjusted p >
0.10.

## Permutation ledger

```text
GLOBAL:  999 replicates, all pairwise distinct, ledger digest
         1fd6fe54cf6f8a58cd3f351afc6bc31cbdaf9a432630d1ec9396bc7e25006b89
ERA4:    999 replicates, all pairwise distinct, ledger digest
         94423febb85fc494b15c563a701db601fc2a87b40480cab2915f7246c4766222
```

No `STOP_PERMUTATION_LEDGER_MISMATCH` condition was hit in either policy.

## Joint interpretation

EH01 and EH10 are separate mechanism claims, evaluated independently, with
no combined statistic, vote, or omnibus effect (proposal sections 6.1,
14.4) -- a `NO_SIGNAL` outcome for one is not evidence about the other.

```text
WHAT_IS_SUPPORTED:     NONE_AT_THE_LOCKED_SIGNAL_THRESHOLD
WHAT_IS_NOT_SUPPORTED: predictive_advantage, allocation_benefit,
                        prize_value_advantage, economic_optimality,
                        combined_eh01_eh10_effect
```

Both negative results reject only these exact locked designs (this scalar
representation, these horizons/orders, this causal convention, this null) --
not the whole temporal/ordinal mechanism family in general, and not the
presence of any motif/discord or ordinal structure under a different
representation or horizon. This is consistent with, and adds two more
data points to, this research program's broader finding that B649's draw
sequence is not distinguishable from a fair, exchangeable process by the
methods tried so far (see the 2026-08-12 uniformity audit and the sealed
`REGIME_CHANGE_POINT_CUSUM_B649_V1` cell).

## Causality / leakage audit

Both statistics use only strict-prior information at every evaluated point
(EH01's strict-left non-overlap admissibility rule; EH10's rolling window
assigned to the next origin after its final draw). Both are retrospective
structural tests over the full fixed historical sequence, not
forward-prediction claims -- there is no held-out future to leak into. The
methodological risk this design controls is post-hoc statistic/threshold
selection, closed by the preregistration hash above, verified by the
execution script before it loaded a single draw value.

## No-rescue statement

The locked representation (chronological main-number sum), EH01's three
lengths (26/52/104) and causal profile definition, EH10's three orders
(3/4/5) and 124-draw window, the `GLOBAL`/`ERA4` null policies, the 999
permutation count per policy, the Holm correction, and the
`0.05`/`0.10` classification thresholds were not changed after this result
was seen. No alternate surrogate, extra lag/grid search, or parameter
rescue was performed. A different design would require a new variant ID
and a new outcome-blind Owner approval before data access (proposal section
14.1).

## Execution provenance

```text
worker_count:              9 (stdlib multiprocessing, an execution-
                            engineering choice; never affects any locked
                            statistic, seed, or ordering)
replicate_computation_sec: 1240.5
total_runtime_sec:         1244.4
implementation:            pure Python 3.13 stdlib only (no numpy/scipy/
                            matrix-profile package added)
synthetic_fixture_check:   PASS (66/66 tests before real data was read)
```
