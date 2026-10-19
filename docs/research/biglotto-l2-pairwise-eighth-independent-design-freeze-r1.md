# BIGLOTTO_L2_PAIRWISE_EIGHTH_INDEPENDENT_DESIGN_FREEZE_FROM_NEW_FRONTIER_R1

Status: **DESIGN FROZEN — IMPLEMENTATION PENDING** ｜ 2026-08-26 ｜ no empirical or canonical-database access

```text
TASK_ID:                         BIGLOTTO_L2_PAIRWISE_EIGHTH_INDEPENDENT_DESIGN_FREEZE_FROM_NEW_FRONTIER_R1
CURRENT_REMOTE_MAIN_HEAD:        39180c7f55ffaa2e1f2d2c12fb0ce965d07034b0
CURRENT_REMOTE_MAIN_TREE:        d085fb271f5ceac07882a8bfd8cd7941f145bfb2
REMAINING_FAMILIES:              NF01, NF02, NF05, NF06
EXCLUDED_FAMILIES:               C1-C7 load-bearing families
EMPIRICAL_ACCESS:                NONE
CANONICAL_DB_ACCESS:             NONE
SELECTION_BASIS:                 structural independence + mathematical completeness + deterministic implementability
SELECTED_FAMILY:                 NF01 LAG_BLOCK_HSIC
SELECTED_DESIGN_ID:              BIGLOTTO_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1
METHOD_ID:                       BMSGV1_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1
NEXT_STAGE:                      BIGLOTTO_L2_PAIRWISE_EIGHTH_INDEPENDENT_CANDIDATE_IMPLEMENTATION_FREEZE_R1
IMPLEMENTATION_IN_THIS_STAGE:    NO
EMPIRICAL_EXECUTION_IN_THIS_STAGE: NO
```

This document freezes one implementable mathematical design. It does not
claim predictive value, statistical significance, lottery non-randomness,
historical success, or superiority over any existing family.

## 1. Authority and boundaries

The supplied remote-main identity is the design authority. The live checkout
was observed at local `main` `8121f1b2c445d1d959ac91c25cfd38f2a4246bd7`,
with pre-existing dirty frontend/MCP migration files; those changes are not
part of this freeze and were not used as scientific evidence. The supplied
remote-main commit and tree match the local `origin/main` references.

The freeze covers only the NF01 design specification and its canonical
documentation route. It does not change the runtime, strategy catalog,
production adapters, database, empirical-result artifacts, or canonical
research results. The C1-C7 exclusion is binding: the future implementation
must not import, wrap, call, copy, or tune any C1-C7 implementation or result.

The word **independent** in this task means structurally independent of the
excluded load-bearing families. It does not mean that the lottery numbers or
the resulting time series are statistically independent.

## 2. Frontier decision

The gates are applied lexicographically and qualitatively. No empirical
score, historical result, database row, or canonical ranking is used.

| Family | Structural independence | Mathematical completeness | Deterministic implementability | Disposition |
|---|---|---|---|---|
| NF01 LAG_BLOCK_HSIC | **PASS** — a lag-block kernel dependence functional over raw binary histories; no C1-C7 transform or consumer | **PASS** — fixed window, block length, kernel, centering, estimator, constructor, fallback, and ties are all specified below | **PASS** — finite rational arithmetic and finite exhaustive construction; no randomness, logarithm, or convergence loop | **SELECTED** |
| NF02 TRANSFER_ENTROPY | **CONCERN** — directed conditional-entropy/lag-transition structure is adjacent to the existing entropy and Markov mechanisms | **CONCERN** — state coding, direction, zero-cell handling, smoothing, and log policy require extra choices | **CONCERN** — a fixed implementation is possible, but exact score ordering needs a transcendental/numeric contract | **NOT SELECTED** |
| NF05 CHECKERBOARD_RECURRENCE_COPULA | **PASS** in principle, but only after fixing rank ties, grid resolution, recurrence relation, and boundary policy | **CONCERN** — those choices materially define the statistic and are not supplied by the family label | **CONCERN** — deterministic after additional locks, but tie and partition behavior add avoidable surface area | **NOT SELECTED** |
| NF06 SINKHORN_RECURRENCE_DEPENDENCE | **PASS** in principle as a distinct transport-based dependence functional | **CONCERN** — regularization, zero-marginal support, initialization, and output normalization need additional locks | **CONCERN** — iterative scaling requires a convergence/stopping and numerical-precision contract | **NOT SELECTED** |

NF01 is selected because its finite-sample HSIC can be defined with the
Kronecker-delta kernel and exact `Fraction` arithmetic. The design therefore
has a complete endpoint and a deterministic tie policy without adding a
statistical test, a fitted model, a random seed, or an iterative solver.

## 3. Frozen NF01 mathematical design

### 3.1 Input and causal boundary

The future implementation exposes the following primary operation:

```text
analyze(history, cutoff) -> AnalysisResult
```

`history` is a finite, ordered, random-access sequence of completed
BIG_LOTTO draws. `cutoff` is the number of completed draws visible to this
invocation. It is a non-boolean integer satisfying
`0 <= cutoff <= len(history)`.

The number domain and draw contract are fixed:

```text
NUMBER_DOMAIN = {1, 2, ..., 49}
DRAW_SIZE     = 6
WINDOW_SIZE   = 256
BLOCK_LENGTH  = 8
OBSERVATION_COUNT = WINDOW_SIZE - BLOCK_LENGTH + 1 = 249
PAIR_COUNT    = C(49, 2) = 1,176
TICKET_COUNT  = C(49, 6) = 13,983,816 candidate six-sets
```

For `cutoff >= WINDOW_SIZE`, only the exact causal window

```text
Y_r = history[cutoff - WINDOW_SIZE + r],  r = 0, ..., 255
```

may be read. Draw order inside each draw is canonicalized by sorting its six
validated values; chronological order is never sorted or repaired. No value
at or after the cutoff is read. Data outside the selected window is not needed
for the result.

For `cutoff < WINDOW_SIZE`, the operation returns the specified fallback and
does not read a draw element. This is a deterministic insufficient-history
state, not an empirical result.

### 3.2 Binary event streams and lag blocks

For each number \(v \in \{1,\ldots,49\}\), define the binary event stream

\[
x_{v,r} = \mathbf{1}\{v \in Y_r\}, \qquad r=0,\ldots,255.
\]

For each block row \(a=0,\ldots,N-1\), with \(N=249\), define the ordered
eight-draw lag block

\[
z_{v,a} = (x_{v,a}, x_{v,a+1}, \ldots, x_{v,a+7}) \in \{0,1\}^{8}.
\]

The block is an ordered state vector; it is not converted to a count, a
frequency rank, a Markov transition, an entropy, or a graph edge. Overlap
between adjacent blocks is intentional and fixed by this definition.

### 3.3 Exact delta-kernel HSIC pair weight

Use the fixed Kronecker-delta kernel on lag blocks:

\[
k(u,u') = \mathbf{1}\{u=u'\}.
\]

For each number \(v\), form the \(N \times N\) Gram matrix

\[
K^{(v)}_{ab}=k(z_{v,a},z_{v,b}).
\]

Use the exact centering matrix

\[
H_{ab}=\mathbf{1}\{a=b\}-\frac{1}{N},
\qquad a,b=0,\ldots,N-1.
\]

For every unordered pair \(i<j\), define the **biased finite-sample HSIC
pair weight**

\[
w_{ij}=\frac{1}{N^2}\operatorname{tr}
       \left(K^{(i)} H K^{(j)} H\right).
\]

The matrix product order above is the frozen computation. \(w_{ji}\) is the
same unordered value; no second directed estimate is created. The candidate
must evaluate \(H\), matrix products, traces, and comparisons with exact
rational arithmetic. Every weight is a reduced rational number; floating
point, logarithms, kernel bandwidths, p-values, permutation nulls, and
post-result coefficients are out of scope.

The score is an association weight only. It is not interpreted as evidence
that the two number streams are causally related or non-independent in the
population.

### 3.4 Deterministic six-number constructor

For a legal six-set \(S=(s_1<\cdots<s_6)\), define

\[
Q(S)=\sum_{1\le p<q\le 6} w_{s_p s_q}.
\]

The ticket is the lexicographically smallest six-tuple among all legal
six-sets attaining the maximum exact value of \(Q(S)\):

\[
Q^* = \max_{S\subseteq\{1,\ldots,49\},\ |S|=6} Q(S),
\qquad
S^* = \min_{\mathrm{lex}}\{S: |S|=6,\ Q(S)=Q^*\}.
\]

Operationally, enumerate `combinations(range(1, 50), 6)` in ascending tuple
order, replace the incumbent only for a strictly larger `Q`, and keep the
first tuple on an exact tie. This fully determines the constructor even when
all pair weights are zero. The all-zero case therefore returns
`(1, 2, 3, 4, 5, 6)`.

The result must retain all 1,176 pair weights, the exact ticket objective, the
selected sorted ticket, the fixed constants, and the status. Optional number
aggregates may be emitted as diagnostics, but they must not alter the ticket
objective.

## 4. Edge and serialization contract

The next-stage implementation must preserve these cases exactly:

1. A cutoff below 256 returns `FALLBACK_INSUFFICIENT_HISTORY`, 1,176 zero
   pair weights, a zero ticket objective, and `(1, 2, 3, 4, 5, 6)` without
   reading a draw element.
2. A sufficient window validates every accessed draw as exactly six distinct
   non-boolean integers in `1..49`; malformed input fails closed before score
   construction.
3. Constant or otherwise zero-centered streams produce an exact zero HSIC
   contribution; no division by variance is introduced.
4. Pair keys are emitted once in numeric `(i, j)` order with `i < j`.
5. Rational values are serialized as reduced
   `{"numerator": N, "denominator": D}` objects in canonical numeric pair
   order. The compact UTF-8 JSON object has this exact top-level key order:
   `method_id`, `design_name`, `status`, `window_size`, `block_length`,
   `observation_count`, `pair_weights`, `ticket_objective`, `ticket`.
   Pair keys are strings `"i-j"` in ascending `(i, j)` order; each rational
   object uses `numerator` before `denominator`; arrays use numeric ascending
   order; and no insignificant whitespace is emitted.
6. Repeating the same valid input and cutoff must produce byte-identical
   canonical output. No clock, process identity, hash-randomized iteration,
   random source, database, network, or environment variable may influence it.

The fallback is intentionally explicit. It is not a claim that the default
ticket is better than any other ticket.

## 5. Structural independence firewall

The implementation-freeze stage must add a standalone research module and
tests only. The module must:

- consume only the validated completed-draw window described above;
- use raw membership indicators solely to form the fixed lag-block vectors;
- avoid imports from strategy adapters, the strategy catalog, C1-C7, replay,
  persistence, API, or frontend code;
- avoid co-draw graph construction, frequency ranking, conditional-entropy
  scoring, Markov transition matrices, Bayesian fitting, copula grids,
  Sinkhorn iteration, or any legacy method wrapper;
- avoid database, filesystem, network, clock, random, empirical-result, and
  canonical-database access; and
- fail closed on malformed input instead of silently falling back from an
  invalid sufficient window.

This firewall establishes architectural separation. It cannot establish a
population-level statistical independence claim, which is intentionally not
part of this task.

## 6. Next-stage implementation freeze

`BIGLOTTO_L2_PAIRWISE_EIGHTH_INDEPENDENT_CANDIDATE_IMPLEMENTATION_FREEZE_R1`
may implement this design only after preserving the constants, formulas,
causal boundary, fallback, output fields, and tie behavior verbatim.

The next stage acceptance should include:

- hand-computable delta-kernel HSIC fixtures, including identical, constant,
  and differing lag-block streams;
- exact symmetry and non-negativity checks for all unordered pair weights;
- a brute-force/reference calculation of the centered trace on a small fixture;
- cutoff and future-read guards proving that only the 256-draw causal window
  is accessed;
- deterministic repeated-run and canonical-serialization checks;
- exhaustive six-set tie behavior, including the all-zero fallback; and
- an architecture/dependency test proving there is no C1-C7 or runtime/data
  dependency.

No empirical execution, canonical database read, historical ranking, catalog
registration, production publication, or predictive conclusion is authorized
by this design freeze.

## 7. Final disposition

```text
AUTHORITY_STATUS:                 RESOLVED_FROM_SUPPLIED_REMOTE_MAIN
SELECTION_STATUS:                 SELECTED_NF01
DESIGN_FREEZE_STATUS:             COMPLETE
DESIGN_NAME:                      BIGLOTTO_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1
METHOD_ID:                        BMSGV1_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1
STRUCTURAL_INDEPENDENCE:          PASS_BY_DESIGN_FIREWALL
MATHEMATICAL_COMPLETENESS:        PASS
DETERMINISTIC_IMPLEMENTABILITY:   PASS
IMPLEMENTATION_STATUS:            NOT_STARTED
EMPIRICAL_EXECUTION:              NOT RUN — EMPIRICAL_ACCESS NONE
CANONICAL_DB_READ:                NOT RUN — CANONICAL_DB_ACCESS NONE
PREDICTIVE_OR_PERFORMANCE_CLAIM:  NONE
NEXT_STAGE:                       BIGLOTTO_L2_PAIRWISE_EIGHTH_INDEPENDENT_CANDIDATE_IMPLEMENTATION_FREEZE_R1
```

The only selected outcome is the NF01 design. NF02, NF05, and NF06 remain
unimplemented alternatives and must not be smuggled into the next-stage
module as hybrid terms or fallback heuristics.
