# Strategy Matrix k=2/3/5 exact one-exchange multistart baseline — preregistration

## Frozen question

For each supported native lottery structure and ticket cardinality `k` in
`{2, 3, 5}`, what exact terminal portfolio and exact `Q` value are obtained
when the unchanged best-improvement one-number-exchange ascent is run from
four deterministic legal starts?  The result is a finite multistart local
baseline.  It makes no global-optimum claim.

## Scope and authority

```text
STUDY_ID:                    STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1
TASK_ID:                     STRATEGY_MATRIX_K235_MULTISTART_BASELINE_R1
OWNER_AUTHORIZATION:         AUTHORIZE_STRATEGY_MATRIX_K235_MULTISTART_BASELINE_R1
BASE_COMMIT:                 07a5c3479123c03fd91b6f1ae2402046b5f16c2a
BASE_TREE:                   cff549183e67ad49f12afb5076a11b1f8b712dde
REQUESTED_K_SCOPE:           [2, 3, 5]
SUPPORTED_K_SCOPE:           [2, 3, 5]
STRUCTURES:                  BIG_LOTTO, DAILY_539, POWER_LOTTO_ZONE1
POWER_LOTTO_ZONE2:           OUT_OF_SCOPE_NOT_RUN
K_10_20:                     PHASE13_OWNED_NOT_RUN
GLOBAL_OPTIMUM_STATUS:       UNKNOWN
```

The product semantics support exactly the three executed structures at all
three requested cardinalities.  Zone-2 is not a 6-number pool and is not
fabricated as a supported cell.  k=10 and k=20 are not evaluated here.

## Frozen starts

Each of the nine structure/cardinality cells uses exactly these four starts,
in this order:

1. `CYCLIC_SIDON_SHIFT_OFFSET0_V1`
2. `CYCLIC_SIDON_SHIFT_OFFSET1_V1`
3. `CYCLIC_SIDON_SHIFT_OFFSET2_V1`
4. `CYCLIC_SIDON_SHIFT_OFFSET3_V1`

For each structure, these are contiguous windows of the existing
lottery-native cyclic-Sidon constructor: `T_offset .. T_(offset+k-1)` for
offsets `0, 1, 2, 3`.  The offset-0 and offset-1 identities are the
deterministic constructor starts already used by Phase12.  Offsets 2 and 3
are the same existing constructor family, added because the missing k cells
have no prior Phase10/11 terminal comparator to occupy the remaining frozen
start identities.  All four starts are legal and distinct in every executed
cell.  No prior terminal is invented, no start is sampled, and no start is
added or removed after scoring.

The objective-free manifest is materialized separately at:

```text
docs/research/matrix-native-results/strategy-matrix-k235-multistart-baseline-v1-starts.json
```

```text
START_MANIFEST_SHA256:       107cb53080b45569c761a81ecd6c5924236f4376e69596c115baac41bb60acfc
```

## Unchanged exact search semantics

```text
OBJECTIVE_ID:                EXACT_PORTFOLIO_M3_PLUS_COVERAGE
REFINEMENT_METHOD_ID:        ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
CANONICAL_METHOD_PATH:       src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py
CANONICAL_METHOD_SHA256:     01e634924797355d4f19487a7abfaeed8910bc3b0c5ee8a6d95ebe617a368577
```

Every frozen start runs the complete legal one-number-exchange neighborhood
through the existing exact best-improvement ascent.  A move is accepted only
when its exact `Q` is strictly larger.  Exact ties use the unchanged
lexicographically smallest complete portfolio.  Search continues until the
best legal neighbor is no better than the current portfolio; that final
iteration is the local-optimum certificate.

Terminal portfolios are canonicalized and deduplicated for reporting.  The
best terminal is selected by exact `Q`, then canonical terminal portfolio,
then start ID.  All start traces and terminal exact-Q values remain in the
canonical result.

## Reproducibility and claim boundary

The result is canonical UTF-8 JSON with sorted keys, two-space indentation,
and one final LF.  Runtime measurements are excluded from the artifact, and
completion order cannot affect serialization.  A fresh-process replay must
produce byte-identical result bytes.

```text
RANDOM_DERIVED_STARTS:        NONE
MONTE_CARLO:                  NONE
SAMPLING:                    NONE
SECOND_EXCHANGE:             NOT_RUN
GLOBAL_OPTIMUM_STATUS:        UNKNOWN
PREDICTIVE_OR_ECONOMIC_CLAIM: NOT_CLAIMED
PRODUCTION_MUTATION:          NOT_AUTHORIZED
```
