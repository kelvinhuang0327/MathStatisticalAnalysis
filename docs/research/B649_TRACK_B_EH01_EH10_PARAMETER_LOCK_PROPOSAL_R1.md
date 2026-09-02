# B649 Track B EH01/EH10 Parameter-Lock Proposal R1

```text
TASK_ID: B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1
CONTINUES: B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_FALSIFICATION_R1
TASK_CLASS: PLANNING_ONLY
WORKER_ROUTE: NOT_APPLICABLE
JUDGE_MODE: NOT_APPLICABLE
STATUS: PROPOSAL_FOR_OWNER_REVIEW
LOCK_STATUS: NOT_LOCKED
PREREGISTRATION_HASH: NOT_CREATED
COLLISION_GATE: PASS (INHERITED; NOT_REOPENED)
EH01_EXECUTIONS: 0
EH10_EXECUTIONS: 0
PREVIOUS_STOP: STOP_EH01_EH10_SPEC_AUTHORITY_INCOMPLETE
EXECUTION: NOT_RUN
SCIENTIFIC_DATA_ANALYSIS: NOT_RUN
```

## 0. Decision summary

This proposal recommends one outcome-blind, structurally identifiable design for
EH01 and EH10. Both hypotheses use the same chronological scalar input: the sum
of the six B649 main numbers for each draw; the special number is excluded. The
proposal tests temporal ordering structure only. It does not test ticket quality,
strategy loss, allocation benefit, prize value, or future predictive advantage.

The EH01 frozen-strategy comparator is removed from this proposed variant, with
no proxy. The current source tree and inspected replay schema do not identify a
frozen out-of-fold residual stream, fold provenance, or a frozen per-origin loss
contract. Preserving that comparator would therefore require new infrastructure
or an unvalidated substitution. The narrower structural claim is the smallest
identifiable claim supported by the available representation.

Recommended locks:

| Item | Recommended lock |
|---|---|
| EH01 representation | chronological main-number sum, one scalar per draw |
| EH01 distance | strict-left, non-overlapping, subsequence-wise z-normalized Euclidean distance |
| EH01 lengths | exactly `26`, `52`, `104` draws |
| EH01 primary endpoints | motif minimum and discord maximum at each length; six endpoints total |
| EH10 orders | exactly `3`, `4`, `5`, unit delay |
| EH10 rolling window | `124` draws |
| EH10 primary endpoints | maximum rolling normalized-permutation-entropy deficit at each order; three endpoints total |
| Primary null | `999` global chronology permutations |
| Era robustness null | `999` permutations within four fixed contiguous equal-count eras |
| Multiplicity | Holm within EH01's six-endpoint family and separately within EH10's three-endpoint family |
| Classification | `SIGNAL` at adjusted `p <= 0.05` under both primary and era nulls for the same endpoint; `WEAK_SIGNAL` at primary adjusted `p <= 0.10` when `SIGNAL` is not met; otherwise `NO_SIGNAL` |

Owner approval of the narrowed structural claim is required before a final
preregistration is locked. If the Owner instead requires the original
comparator-relative allocator claim, execution remains stopped until an already
existing, separately authorized frozen OOF residual source is identified.

## 1. Authority and outcome-blind evidence boundary

### 1.1 Controlling authority

- Spec authority:
  `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md`
- Observed SHA-256 during this planning task:
  `79f1adbf006a0f3b24279d57010d0a6c45a5cad606c95798e983dd2133e9ad31`
- EH01 authority: matrix-profile motif/discord regime allocator, with causal
  subsequences, no query/future-overlap matches, and later Track B validation.
- EH10 authority: permutation-entropy ordinal state gate, with allowed orders
  `3`–`5`, causal values, and no full-history normalization.

### 1.2 Inspected evidence

`[Confirmed]` The project rule contract defines B649 as six distinct main
numbers from `1` through `49` plus one distinct special number.

`[Confirmed]` The official operator's current schedule states that B649 is
normally drawn on Tuesday and Friday. The three proposed EH01 lengths therefore
span approximately 13, 26, and 52 normal draw-weeks without interpolating
calendar gaps.

`[Confirmed]` The project's prior locked preregistration uses deterministic
seed ledgers, four contiguous chronological blocks for stability reporting,
Holm correction for endpoint families, and strict separation between primary
classification and diagnostics.

`[Confirmed]` The tracked project dependency declaration contains no
matrix-profile or permutation-entropy package.

`[Confirmed]` An exact tracked-source search found no OOF/residual-stream
contract. The inspected replay table has strategy/run/result fields but no OOF
fold identity, frozen loss definition, or causal residual-stream identity.

`[Unknown]` An untracked or external frozen OOF residual artifact may exist.
This proposal does not assume that it exists and does not search outside the
authorized current surface to preserve the comparator.

### 1.3 Explicitly not inspected or run

- No B649 main-number or special-number values were read.
- No EH01/EH10 statistic was computed.
- No historical signal, result table, or hypothesis outcome was inspected.
- No surrogate, permutation, model, backtest, or allocation was run.
- No collision audit was reopened.
- No Frontier V2 hypothesis beyond EH01/EH10 was audited.
- EH04 and EH02 remain out of scope.

## 2. Shared exact input representation and chronology contract

Let the final preregistered, authority-pinned eligible history contain draws
`t = 1, ..., n` in ascending `(draw_date, numeric_draw_id)` order. For draw `t`,
let its six main numbers be `b_(t,1), ..., b_(t,6)` and define

```text
x_t = sum_{r=1}^{6} b_(t,r)
```

`canonical_draw_id` means the ASCII base-10 rendering of
`int(authority_draw_id)`, with no sign and no leading zeroes. This exact
serialization is used by every hash key below.

The special number, jackpot, sales, prize, strategy result, and any future
field are excluded. One draw produces exactly one integer observation.

The time axis is draw order, not elapsed days. No synthetic rows are inserted
for holidays, exceptional extra draws, missing calendar dates, or schedule
changes. A duplicated draw identity, ambiguous chronology, invalid main-number
set, or unpinned eligible-history rule is a future execution stop.

This representation is intentionally shared by EH01 and EH10. It avoids a
post-result choice among many summaries, preserves the temporal question in
the authority spec, and yields one low-dimensional design that is feasible for
both methods. Any different summary is a new preregistered variant.

## 3. EH01 locked proposal

### 3.1 Claim being tested

EH01-R1 tests whether the chronological main-number-sum series contains a
causal repeated-subsequence motif or causal discord more extreme than expected
when draw order is exchangeable, at the three locked horizons.

It does **not** test whether a motif/discord gate improves strategy loss or
whether a fallback action is beneficial. `SIGNAL` below means
`EH01_STRUCTURAL_SIGNAL_AT_LOCKED_REPRESENTATION_AND_HORIZON` only.

### 3.2 Window grid

```text
M_EH01 = {26, 52, 104} draws
```

These are exactly three geometrically doubled horizons. At the normal
twice-weekly cadence they correspond to approximately 13, 26, and 52 weeks.
No inner-fold or post-result length selection is permitted.

### 3.3 Exact distance and causal profile

For a subsequence `a = (a_1, ..., a_m)`, define the population-standardized
vector

```text
z(a)_k = (a_k - mean(a)) / sqrt(sum((a_j - mean(a))^2) / m)
```

and, for two valid nonconstant subsequences of the same length, define

```text
d_m(a, c) = sqrt(sum_{k=1}^{m} (z(a)_k - z(c)_k)^2)
```

This is the standard unscaled z-normalized Euclidean convention; it is not
divided by `sqrt(m)`. Each length has its own null calibration, so no
cross-length distance pooling occurs.

For query window `Q_(i,m) = (x_i, ..., x_(i+m-1))`, an admissible comparison
window begins at `j` only when

```text
j + m - 1 < i
```

so the comparison window is strictly earlier and shares no draw with the
query. This strict-left non-overlap rule is stronger than the usual symmetric
`m/2` trivial-match exclusion and implements the spec's causal leakage guard.

Only query starts with at least `m` admissible earlier candidate starts are
eligible. Equivalently, within a segment indexed from 1, `i >= 2m`. For each
eligible valid query,

```text
P_(i,m) = min over admissible valid j of d_m(Q_(i,m), Q_(j,m))
```

The nearest-neighbor index is the earliest `j` on an exact distance tie.
Constant subsequences are invalid because z-normalization is undefined; they
are omitted as both queries and candidates. If a required segment has fewer
than one eligible finite profile entry, execution stops rather than changing
the distance rule.

### 3.4 Motif and discord statistics

For each `m`:

```text
M_m = min_i P_(i,m)
T_motif,m = -M_m                 # larger is more motif-like

D_m = max_i P_(i,m)
T_discord,m = D_m                # larger is more discord-like
```

The motif location is the earliest query `i`, then earliest neighbor `j`,
among exact ties at `M_m`. The discord location is the earliest query `i`
among exact ties at `D_m`.

The six primary EH01 endpoints are therefore

```text
{T_motif,26, T_motif,52, T_motif,104,
 T_discord,26, T_discord,52, T_discord,104}
```

No data-dependent motif radius is introduced. A motif support count may be
reported only as `2` for the canonical pair plus exact-distance ties at the
same global minimum; it is diagnostic and cannot affect classification. This
avoids inventing an arbitrary distance threshold solely to increase support.

### 3.5 EH01 null, robustness, and classification

The shared null construction in section 5 is applied to the entire input
series. Each surrogate is recomputed from the permuted series through the full
causal-profile pipeline; the observed profile is never permuted after feature
construction.

Primary raw one-sided p-values use the `GLOBAL` permutation policy. The six
raw p-values form one Holm family. The same six endpoints, recomputed under
the `ERA4` policy, form a separate six-endpoint robustness family.

EH01 classification uses section 7 verbatim. Four era-local diagnostic tables
are also required. Each diagnostic recomputes the profile using only windows
fully contained in that era and reports observed statistic, surrogate median,
surrogate interquartile range, and surrogate percentile. Era-local values do
not create extra primary tests and cannot promote or rescue a result.

### 3.6 Comparator decision

```text
EH01_COMPARATOR_DECISION: REMOVE_UNAVAILABLE_FROZEN_STRATEGY_COMPARATOR
PROXY_SUBSTITUTION: PROHIBITED
CLAIM_DOWNGRADE: STRUCTURAL_TEMPORAL_PRECONDITION_ONLY
```

The H19-style changepoint, H20-style scalar gate, and ungated best frozen
strategy are not reinterpreted as structural surrogates. In particular, the
current variant cannot claim the original `paired-loss improvement versus all
three controls` success condition. If the Owner requires that original claim,
the future execution must stop until an existing frozen OOF stream with exact
strategy versions, folds, origins, loss, and coverage is separately identified
and authorized. No infrastructure is to be created solely to preserve it.

## 4. EH10 locked proposal

### 4.1 Claim being tested

EH10-R1 tests whether the chronological main-number-sum series contains a
causal rolling ordinal-complexity deficit more extreme than expected under
exchangeable draw order, at the three locked ordinal orders.

It does **not** test predictive advantage, strategy loss, abstention benefit,
or superiority to Shannon entropy, sample entropy, or raw variance.
`SIGNAL` means
`EH10_ORDINAL_STRUCTURAL_SIGNAL_AT_LOCKED_REPRESENTATION_ORDER_AND_WINDOW`
only.

### 4.2 Orders, delay, and rolling window

```text
D_EH10 = {3, 4, 5}
ordinal delay tau = 1 draw
rolling window W = 124 draws
rolling step = 1 draw
```

For order `d = 5`, a window of `W = 124` contains
`W - d + 1 = 120 = 5!` overlapping ordinal words. Thus missing order-5
patterns are not forced merely because there are fewer word slots than the
`5!` possible patterns. Surrogate calibration handles the remaining
finite-window bias. Orders `3`–`5` are the allowed range and match the
foundational method's practical low-order recommendation.

Every rolling window is assigned to the next origin after its final draw; it
therefore uses strict-prior values only. The full-history normalization or
selection of a favorable origin is prohibited. The scan across all eligible
rolling windows is itself part of the locked statistic and is repeated inside
every surrogate.

### 4.3 Deterministic tie handling

Main-number sums are discrete, so ties are expected and cannot be ignored.
For each immutable draw identity, define a 256-bit secondary key

```text
tie_key(draw_id) = SHA256(
  UTF8("6490110|EH10|TIE_V1|" + canonical_draw_id)
)
```

Within an ordinal word, observations are ranked lexicographically by
`(x_t, tie_key(draw_id_t))`. Unequal sums are never perturbed. Equal sums are
ordered by the outcome-independent hash key. On the impossible event of a
hash collision within a word, the canonical draw ID is the final tie-break.

When observations are permuted, the draw identity and its tie key travel with
the sum. No fresh tie noise is generated per surrogate. A temporal-index
tie-break is prohibited because it would systematically encode time order.

### 4.4 Normalized permutation entropy

For a rolling window and order `d`, form all overlapping unit-delay words of
length `d`, map each to one of the `d!` strict ordinal patterns using section
4.3, and let `c_pi` be the count for pattern `pi`. With
`N_d = W - d + 1`, define

```text
p_pi = c_pi / N_d
H_d = -sum over pi with c_pi > 0 of p_pi * ln(p_pi)
Hnorm_d = H_d / ln(d!)
```

The logarithm base is immaterial after normalization; natural logarithms are
locked for implementation. `0 * ln(0)` contributes zero. The resulting value
is in `[0, 1]`.

For each order `d`, let `Hmin_d` be the minimum `Hnorm_d` across all eligible
rolling windows. The primary endpoint is

```text
T_PE,d = 1 - Hmin_d
```

so larger values are more extreme in the prespecified low-entropy direction.
The earliest rolling-window start is selected on an exact minimum tie.

At that locked minimum location, report ordinal-pattern occupancy
`count(c_pi > 0) / d!` and missing-pattern count
`d! - count(c_pi > 0)` as diagnostics. They are not extra tests and cannot
alter the primary classification.

### 4.5 EH10 null, robustness, and classification

Primary raw one-sided p-values use the `GLOBAL` permutation policy for
`T_PE,3`, `T_PE,4`, and `T_PE,5`. Those three raw p-values form one Holm
family. The same three endpoints under `ERA4` form a separate three-endpoint
robustness family.

EH10 classification uses section 7 verbatim. Four era-local diagnostic tables
are also required. Rolling windows must be fully contained within an era.
The tables report entropy statistic, occupancy, missing-pattern count,
surrogate median, surrogate interquartile range, and surrogate percentile.
They cannot promote or rescue a result.

## 5. Exact null/surrogate and deterministic seed policy

### 5.1 Primary conditional null: `GLOBAL`

The null hypothesis is that the observed `(x_t, draw_id_t)` pairs are
exchangeable in chronological position. Each surrogate uniformly permutes the
`n` observation pairs over the `n` fixed draw-order positions. This preserves
the exact observed one-draw marginal distribution and exact tie multiplicities
while destroying serial ordering. No synthetic lottery outcomes are generated.

### 5.2 Era-preserving robustness null: `ERA4`

Partition the chronological positions into four contiguous, equal-count eras
using

```text
era(t) = min(4, floor(4 * (t - 1) / n) + 1),  t = 1, ..., n
```

Era sizes differ by at most one. Within each surrogate, permute observation
pairs independently inside each era and concatenate the four eras in their
original order. This preserves era-specific marginal distributions and fixed
era boundaries while destroying within-era serial order.

`ERA4` is robustness evidence only. It cannot create a `SIGNAL` when the
primary `GLOBAL` family does not qualify.

### 5.3 Deterministic permutation generation

```text
MASTER_SEED: 6490110
REPLICATE_INDEX: b = 0, ..., 998
PERMUTATIONS_PER_POLICY: 999
```

For policy `P` and replicate `b`, assign each draw the key

```text
perm_key(P, b, draw_id) = SHA256(
  UTF8("6490110|" + P + "|" + zero_padded_b + "|" + canonical_draw_id)
)
```

`zero_padded_b` is exactly three ASCII decimal digits (`000` through `998`).
Sort ascending by the 256-bit key, with canonical draw ID as collision
tie-break. For `ERA4`, sort separately inside each era. This hash-sort policy
defines the permutation without a library-specific RNG. It is independent of
the number values. All generated index arrays and their digests must be
recorded in the future execution ledger.

If two replicate indices produce the same complete permutation within a
policy, or the generated index-ledger digest differs between preregistration
verification and execution, stop; do not silently generate replacements.

### 5.4 Raw p-value

For an endpoint statistic whose extreme direction is always larger, let `B`
be the count among the `999` surrogate statistics satisfying
`T_surrogate >= T_observed`. The raw p-value is

```text
p_raw = (B + 1) / (999 + 1)
```

Equality is included. The minimum attainable raw p-value is `0.001`. The same
permutation arrays are used for every endpoint under a policy, but EH01 and
EH10 retain separate statistical families and no combined effect is computed.

This is a Monte Carlo approximation to the full conditional permutation null,
not exhaustive enumeration of `n!` orders and not an exact parametric lottery
null.

## 6. Multiplicity policy

### 6.1 Families

```text
F_EH01_PRIMARY: 6 raw p-values
  = 2 statistics x 3 lengths under GLOBAL

F_EH01_ROBUSTNESS: 6 raw p-values
  = the same endpoints under ERA4

F_EH10_PRIMARY: 3 raw p-values
  = 3 orders under GLOBAL

F_EH10_ROBUSTNESS: 3 raw p-values
  = the same endpoints under ERA4
```

EH01 and EH10 are separate mechanism claims and remain separate Holm families.
There is no combined EH01+EH10 statistic, vote, omnibus effect, or cross-family
promotion rule.

### 6.2 Holm adjustment

Within each family of size `K`, sort raw p-values
`p_(1) <= ... <= p_(K)`. The step-down rejection threshold at ordered rank
`r` is

```text
alpha / (K - r + 1)
```

and the monotone Holm-adjusted p-value is

```text
p_holm,(r) = min(1, max_{j <= r} ((K - j + 1) * p_(j)))
```

then mapped back to the original endpoints. At familywise `alpha = 0.05`, the
first-step raw thresholds are `0.05/6 = 0.008333...` for EH01 and
`0.05/3 = 0.016666...` for EH10. At exploratory `alpha = 0.10`, they are
`0.10/6 = 0.016666...` and `0.10/3 = 0.033333...`, respectively.

Era-local descriptive tables, motif location/support diagnostics, ordinal
occupancy, and missing-pattern counts have no inferential p-values and do not
belong to a family. They cannot be substituted for a failed primary endpoint.

## 7. Numeric classification rules

Apply the following rule separately to EH01 and EH10.

### `SIGNAL`

At least one named endpoint has both:

```text
GLOBAL Holm-adjusted p <= 0.05
AND
ERA4 Holm-adjusted p <= 0.05
```

The qualifying endpoint must be the same statistic/length for EH01 or the same
order for EH10. An era-only result cannot qualify.

### `WEAK_SIGNAL`

`SIGNAL` is not met, and at least one endpoint has

```text
GLOBAL Holm-adjusted p <= 0.10
```

This includes a primary `p <= 0.05` endpoint that fails the same-endpoint
`ERA4 <= 0.05` robustness condition. Era robustness cannot promote a primary
result but may prevent the stronger label.

### `NO_SIGNAL`

Every endpoint has

```text
GLOBAL Holm-adjusted p > 0.10
```

An `ERA4` result with primary adjusted `p > 0.10` cannot change this label.

### `UNCLASSIFIED`

Any stop condition, invalid statistic, authority mismatch, incomplete family,
or execution-contract breach yields `UNCLASSIFIED`, never `NO_SIGNAL`.

These labels concern only the narrowed structural claims in sections 3.1 and
4.1. They do not satisfy the original comparator-relative allocation success
conditions.

## 8. Robustness and era checks

Required robustness evidence is fixed before execution:

1. Recompute the full primary endpoint families under `ERA4`; these adjusted
   p-values can confirm `SIGNAL` but cannot create it.
2. Recompute every statistic separately inside each of the four eras, using
   only windows fully contained in that era.
3. Report era-local observed statistic, surrogate median, surrogate
   interquartile range, and surrogate percentile. EH10 additionally reports
   occupancy and missing-pattern count.
4. Report which endpoint qualified under `GLOBAL` and whether that exact
   endpoint qualified under `ERA4`; do not switch endpoints between policies.
5. Do not add a fifth era partition, calendar-year split, alternate window,
   alternate order, alternate tie rule, parametric null, or post-result
   sensitivity analysis to rescue a label.

Data-geometry preconditions for the diagnostics are:

```text
EH01: every era length >= 3 * 104 = 312 draws
EH10: every era length >= 2 * 124 = 248 draws
```

The EH01 bound permits at least one length-104 query after the locked prior
candidate-support requirement. The EH10 bound provides at least `W + 1`
rolling starts per era. If either bound fails after the dataset is pinned,
stop before reading number values and return the corresponding prelock issue.

## 9. Rationale table for every free parameter

Only the four permitted rationale classes are used.

| Free parameter or decision | Lock | Rationale class | Outcome-blind rationale |
|---|---:|---|---|
| Main-number count/range | `6` from `1..49` | `PROJECT_CONVENTION` | Inherited from the pinned B649 rule contract, not selected from outcomes. |
| Scalar input | sum of six main numbers | `PROJECT_CONVENTION` | A prior locked project preregistration already defines this deterministic B649 summary; using one shared scalar prevents summary shopping. |
| Special number | excluded | `PROJECT_CONVENTION` | The rule contract separates the six main numbers from the special number; the pinned EH specs permit scalar draw summaries. |
| Time index | one step per draw | `DATA_GEOMETRY_BOUND` | The source data are draw-indexed and cadence may contain calendar exceptions; no interpolation is needed. |
| EH01 length count | exactly `3` | `DATA_GEOMETRY_BOUND` | The authority requires three prespecified lengths. |
| EH01 lengths | `26, 52, 104` | `DATA_GEOMETRY_BOUND` | At the official twice-weekly cadence they span approximately a quarter-, half-, and full-year; geometric doubling limits multiplicity. |
| EH01 normalization | subsequence mean and population SD (`ddof=0`) | `STANDARD_STATISTICAL_CONVENTION` | This is the matrix-profile paper's z-normalized Euclidean convention. |
| EH01 neighbor count | `1` nearest neighbor | `STANDARD_STATISTICAL_CONVENTION` | The matrix profile is defined by each subsequence's nearest-neighbor distance. |
| EH01 overlap exclusion | candidate must end before query starts | `PROJECT_CONVENTION` | Implements the spec's strict causal/no-future-overlap guard. |
| EH01 candidate support | at least `m` prior starts | `DATA_GEOMETRY_BOUND` | Prevents the causal profile's earliest, tiny candidate pools from determining the extrema; scales support with the tested length. |
| EH01 motif statistic | negative global profile minimum | `STANDARD_STATISTICAL_CONVENTION` | Matrix-profile minima identify motif pairs; negation fixes a common larger-is-more-extreme p-value direction. |
| EH01 discord statistic | global profile maximum | `STANDARD_STATISTICAL_CONVENTION` | Matrix-profile maxima identify discords. |
| EH01 distance rescaling | none | `STANDARD_STATISTICAL_CONVENTION` | Uses the published Euclidean scale; each length is calibrated separately. |
| EH10 orders | `3, 4, 5` | `STANDARD_STATISTICAL_CONVENTION` | Within the allowed range and the foundational paper's recommended practical low orders. |
| EH10 delay | `1` | `STANDARD_STATISTICAL_CONVENTION` | Tests consecutive ordinal structure without introducing a lag grid. |
| EH10 rolling window | `124` | `DATA_GEOMETRY_BOUND` | `124 - 5 + 1 = 5!`, the smallest window with at least one word slot per possible order-5 pattern. |
| EH10 rolling step | `1` | `DATA_GEOMETRY_BOUND` | Uses every causally available origin and locks the scan into the statistic. |
| EH10 tie handling | seeded SHA-256 secondary key | `PROJECT_CONVENTION` | The scalar series is discrete; deterministic outcome-independent tie breaking avoids temporal-index bias and seed drift. |
| EH10 logarithm | natural log | `STANDARD_STATISTICAL_CONVENTION` | Entropy is normalized by `ln(d!)`, so the base does not affect the value. |
| EH10 normalization | divide by `ln(d!)` | `STANDARD_STATISTICAL_CONVENTION` | Maps each order's entropy to `[0,1]` and matches the foundational normalized definition. |
| EH10 primary direction | maximum low-entropy deficit `1 - min(Hnorm)` | `STANDARD_STATISTICAL_CONVENTION` | IID ordinal patterns maximize entropy; scanning is repeated inside every surrogate. |
| Primary null | global permutation | `STANDARD_STATISTICAL_CONVENTION` | Conditional exchangeability test preserves observed margins/ties and removes order. |
| Robustness null | permutation within `4` eras | `PROJECT_CONVENTION` | Four contiguous blocks are the program's established stability diagnostic and preserve era margins. |
| Permutations per policy | `999` | `COMPUTATIONAL_BOUND` | Gives p-grid `0.001`, fine enough for EH01's first Holm threshold `0.00833`, while bounding repeated matrix-profile cost. |
| Raw p correction | `(B+1)/(999+1)` | `STANDARD_STATISTICAL_CONVENTION` | Valid nonzero Monte Carlo/permutation p-value convention. |
| Master seed | `6490110` | `PROJECT_CONVENTION` | Fixed administrative encoding of B649/EH01/EH10; carries no outcome information. |
| Holm familywise threshold | `0.05` | `STANDARD_STATISTICAL_CONVENTION` | Conventional confirmatory familywise error threshold and the program's established Holm policy. |
| Weak threshold | `0.10` | `STANDARD_STATISTICAL_CONVENTION` | Prespecified exploratory tier; it cannot produce the stronger label. |
| EH01 family size | `6` | `DATA_GEOMETRY_BOUND` | Derived exactly from two statistics times three lengths. |
| EH10 family size | `3` | `DATA_GEOMETRY_BOUND` | Derived exactly from the three allowed orders. |
| Cross-hypothesis family | none | `PROJECT_CONVENTION` | EH01 and EH10 make distinct mechanism claims; no combined scientific effect is proposed. |
| Era-local feasibility | EH01 `>=312`; EH10 `>=248` per era | `DATA_GEOMETRY_BOUND` | Derived from the locked largest EH01 horizon/candidate support and EH10 rolling window. |
| Frozen-strategy proxy | none | `PROJECT_CONVENTION` | The Owner forbids inventing infrastructure solely to preserve an unidentifiable comparator. |

## 10. Computational feasibility

### 10.1 Evaluation count

The two policies require `999 + 999 = 1,998` deterministic permutations. The
same permutation index sets may be reused across endpoints without combining
their statistical families.

For EH01:

```text
full-sequence profile evaluations:
  999 GLOBAL * 3 lengths + 999 ERA4 * 3 lengths = 5,994

era-local diagnostic profile evaluations:
  999 ERA4 * 4 eras * 3 lengths = 11,988

surrogate profile evaluations total = 17,982
observed profile evaluations = 3 full-sequence + 12 era-local
```

For EH10:

```text
full-sequence order scans:
  999 GLOBAL * 3 orders + 999 ERA4 * 3 orders = 5,994

era-local diagnostic order scans:
  999 ERA4 * 4 eras * 3 orders = 11,988
```

### 10.2 Complexity and expected order

- EH01 exact matrix profiles are `O(n^2)` time and `O(n)` working memory per
  length/profile with an optimized STOMP/STUMP-class implementation. Across
  the fixed surrogate set, total time is
  `O(999 * 2 * 3 * n^2)` plus smaller era-local profiles.
- EH10 rolling ordinal scans are approximately linear in series length for
  fixed `W` and orders and are expected to be much cheaper than EH01.
- Serial working memory is `O(n)` for EH01 plus small endpoint summaries; a
  `q`-worker implementation is `O(q*n)`. Full per-surrogate distance profiles
  need not be retained—only extrema, locations, and audit summaries.
- Expected wall-clock order is tens of minutes to low single-digit CPU-hours
  for EH01 on a modern optimized CPU implementation; EH10 should be seconds to
  minutes. This estimate is non-load-bearing and must not change parameters.
- The null is a Monte Carlo permutation approximation. Exact enumeration of
  `n!` orders is not attempted.

### 10.3 Capability note

The current project dependency declaration does not contain a matrix-profile
library. This proposal does not add one. Before execution, the Owner must
approve a pinned implementation route, and that implementation must be checked
against a small synthetic brute-force fixture without reading scientific data.
Failure to establish that route is a pre-execution stop, not permission to
reduce the permutation count or alter the statistics.

## 11. Unresolved infrastructure dependencies and prelock issues

1. **Owner scope decision** — approve or reject the proposed downgrade from
   allocator/comparator efficacy to structural temporal precondition for EH01
   and EH10.
2. **Dataset pin** — the final preregistration must identify the exact B649
   authority mode, source path, eligible-history rule, cutoff, row count, and
   logical dataset SHA-256 before any number values are read.
3. **EH01 implementation route** — pin an exact causal left-profile
   implementation and dependency/runtime versions; none is currently declared
   in the project.
4. **EH10 implementation route** — pin the exact ordinal-pattern enumeration,
   hash-key encoding, and canonical draw-ID serialization.
5. **Code identity** — pin repository path, branch, commit, tree, and clean
   execution surface for any later runner.
6. **Comparator source** — no identifiable frozen OOF residual stream exists
   on the inspected surface. It is removed in this proposal. It remains a
   blocker only if the Owner requires the original allocation claim.
7. **Final lock artifact** — canonical preregistration JSON, its digest, and the
   permutation-index ledger do not yet exist and must not be created until the
   Owner approves this proposal.

None of these issues authorizes EH01/EH10 execution now.

## 12. Future preregistration schema

After Owner approval, create one canonical machine-readable preregistration
with at least the following fields. Values shown as `TBD_BEFORE_DATA_READ` are
mandatory pre-execution pins, not post-result options.

```yaml
schema_version: 1
task_id: B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_FALSIFICATION_R1
approval:
  owner_decision_id: TBD_BEFORE_DATA_READ
  approved_at: TBD_BEFORE_DATA_READ
authority:
  spec_path: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md
  spec_sha256: 79f1adbf006a0f3b24279d57010d0a6c45a5cad606c95798e983dd2133e9ad31
dataset:
  authority_mode: TBD_BEFORE_DATA_READ
  source_path: TBD_BEFORE_DATA_READ
  eligible_history_rule: TBD_BEFORE_DATA_READ
  cutoff: TBD_BEFORE_DATA_READ
  row_count: TBD_BEFORE_DATA_READ
  logical_sha256: TBD_BEFORE_DATA_READ
input:
  lottery_type: BIG_LOTTO
  order: [draw_date_ascending, numeric_draw_id_ascending]
  scalar: sum_of_six_main_numbers
  include_special: false
  calendar_gap_policy: no_interpolation
eh01:
  claim: structural_temporal_precondition_only
  lengths: [26, 52, 104]
  distance: subsequence_z_normalized_euclidean_ddof0
  distance_scale: unscaled
  candidate_side: strict_left
  overlap: prohibited
  minimum_prior_candidate_starts: m
  constant_subsequence_policy: omit_and_stop_if_family_incomplete
  motif_statistic: negative_global_profile_minimum
  discord_statistic: global_profile_maximum
  comparator: removed_unidentifiable_no_proxy
eh10:
  claim: ordinal_structural_precondition_only
  orders: [3, 4, 5]
  delay: 1
  rolling_window: 124
  rolling_step: 1
  tie_policy: sha256_secondary_key_v1
  entropy_log: natural
  entropy_normalizer: ln_factorial_order
  statistic: one_minus_minimum_rolling_normalized_entropy
null:
  primary_policy: global_observation_pair_permutation
  robustness_policy: within_four_equal_contiguous_eras
  permutations_per_policy: 999
  master_seed: 6490110
  generator: sha256_hash_sort
  raw_p: (extreme_count_plus_1)/1000
  tail: one_sided_larger_or_equal
multiplicity:
  method: Holm_step_down
  eh01_primary_family_size: 6
  eh01_robustness_family_size: 6
  eh10_primary_family_size: 3
  eh10_robustness_family_size: 3
  cross_hypothesis_family: none
classification:
  signal_primary_adjusted_p_max: 0.05
  signal_same_endpoint_era_adjusted_p_max: 0.05
  weak_primary_adjusted_p_max: 0.10
  no_signal_primary_adjusted_p_strictly_above: 0.10
  stop_result: UNCLASSIFIED
implementation:
  repository: TBD_BEFORE_DATA_READ
  commit: TBD_BEFORE_DATA_READ
  tree: TBD_BEFORE_DATA_READ
  runtime: TBD_BEFORE_DATA_READ
  dependency_lock_sha256: TBD_BEFORE_DATA_READ
  runner_path: TBD_BEFORE_DATA_READ
  synthetic_fixture_check: PASS_REQUIRED
outputs:
  retain_observed_endpoints: true
  retain_raw_and_holm_p_values: true
  retain_surrogate_summary: true
  retain_permutation_index_digests: true
  retain_era_diagnostics: true
  retain_raw_scientific_rows: false_unless_separately_authorized
claim_boundaries:
  predictive_advantage: NOT_TESTED
  allocation_benefit: NOT_TESTED
  prize_value_advantage: NOT_TESTED
  economic_optimality: NOT_TESTED
  prospective_validity: NOT_TESTED
preregistration_sha256: null_until_owner_approval
```

The final hash must be computed only after every `TBD_BEFORE_DATA_READ` field is
resolved and before any scientific number values are loaded. It must not be
created from this proposal.

## 13. Future execution stop conditions

Any stop returns `UNCLASSIFIED`, records `EXECUTION: NOT_RUN` if no statistic
started or `EXECUTION: STOPPED_INVALID` if computation started, and performs no
parameter rescue.

| Stop code | Exact trigger |
|---|---|
| `STOP_SPEC_AUTHORITY_MISMATCH` | Spec path or SHA-256 differs from the approved preregistration. |
| `STOP_OWNER_APPROVAL_ABSENT` | The narrowed claim and comparator removal are not explicitly approved. |
| `STOP_DATASET_AUTHORITY_UNPINNED` | Dataset path, mode, cutoff, row count, eligible-history rule, or SHA-256 is unresolved. |
| `STOP_DATASET_AUTHORITY_MISMATCH` | Live dataset identity differs from the preregistered identity. |
| `STOP_OUTCOME_BLINDNESS_BREACH` | Any EH01/EH10 result or historical signal was inspected before final lock/hash. |
| `STOP_IMPLEMENTATION_UNPINNED` | Runner, runtime, dependency lock, commit, or tree is unresolved. |
| `STOP_SYNTHETIC_FIXTURE_FAIL` | Optimized EH01 or EH10 implementation disagrees with the preregistered brute-force synthetic fixture. |
| `STOP_CHRONOLOGY_INVALID` | Duplicate/ambiguous draw identity, invalid ordering, or invalid B649 main-number row exists. |
| `STOP_EH01_GEOMETRY_INSUFFICIENT` | Full series or an era cannot produce every required finite length/profile endpoint under the locked support rule. |
| `STOP_EH10_GEOMETRY_INSUFFICIENT` | Full series or an era cannot produce every required order/window endpoint. |
| `STOP_PERMUTATION_LEDGER_MISMATCH` | Fewer than 999 unique permutations exist per policy or index-array digests drift. |
| `STOP_NONFINITE_ENDPOINT` | Any member of a primary or robustness family is missing or nonfinite. |
| `STOP_MULTIPLICITY_CONTRACT_BREACH` | A p-value is omitted, moved between families, or adjusted with a non-Holm rule. |
| `STOP_COMPARATOR_SCOPE_EXPANSION` | Execution attempts to substitute a proxy or build new infrastructure for the removed OOF comparator. |
| `STOP_PARAMETER_DRIFT` | Any representation, length, order, tie rule, statistic, null, seed, count, threshold, or era rule differs from the approved hash. |
| `STOP_OUT_OF_SCOPE_HYPOTHESIS` | Execution attempts EH02, EH04, another Frontier V2 hypothesis, or a combined EH01+EH10 effect. |

## 14. No-rescue and claim boundaries

### 14.1 No-rescue commitment

After the final preregistration is locked, do not change the scalar summary,
add/remove a window or order, switch tie handling, add a lag, change the null,
increase simulations selectively, repartition eras, substitute a comparator,
or change classification thresholds in response to any result. A materially
different design requires a new variant ID and a new outcome-blind owner
approval before data access.

### 14.2 Positive-result boundary

A `SIGNAL` is exploratory evidence of temporal structure at a single named
representation and endpoint. It does not show that lottery outcomes are
predictable, that a strategy can exploit the structure, that an allocation
gate improves loss, or that any ticket has positive expected value. It cannot
trigger production, prospective activation, promotion, or a cohort.

### 14.3 Weak/null-result boundary

`WEAK_SIGNAL` is not confirmation and cannot be promoted by diagnostics.
`NO_SIGNAL` falsifies the locked structural mechanism only at the tested
summary, horizons/orders, causal convention, and null. It does not prove the
universal absence of motifs, discords, ordinal structure, or nonrandomness.

### 14.4 Cross-hypothesis boundary

EH01 and EH10 are reported separately. Concordant labels do not form a joint
effect; discordant labels do not permit choosing the more favorable one as the
program result.

## 15. Method and project references

- Yeh et al., *Matrix Profile I: All Pairs Similarity Joins for Time Series*
  (2016): <https://mcyeh.github.io/paper/2016_icdm_all_pairs_similarity.pdf>
- STUMPY primary implementation repository:
  <https://github.com/stumpy-dev/stumpy>
- Bandt and Pompe, *Permutation Entropy: A Natural Complexity Measure for
  Time Series* (2002): <https://doi.org/10.1103/PhysRevLett.88.174102>
- Cuesta-Frau et al., *Patterns with Equal Values in Permutation Entropy: Do
  They Really Matter for Biosignal Classification?* (2018):
  <https://doi.org/10.1155/2018/1324696>
- Phipson and Smyth, *Permutation P-values Should Never Be Zero* (2010):
  <https://gksmyth.github.io/pubs/PermPValuesPreprint.pdf>
- Holm, *A Simple Sequentially Rejective Multiple Test Procedure* (1979):
  <https://doi.org/10.2307/4615733>
- Taiwan Lottery official draw schedule:
  <https://www.taiwanlottery.com/run_lottery/schedule/>
- Project rule contract:
  `src/lottolab/domain/lottery_rules.py::BIG_LOTTO_RULE_CONTRACT`
- Project preregistration convention:
  `docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-preregistration.md`
- Project research-ledger schema:
  `docs/research/cross-lottery-research-ledger-r1-schema.md`

## 16. Required return block

```text
EH01_PARAMETER_LOCK_PROPOSAL:
  SHARED_MAIN_SUM_REPRESENTATION; STRICT_LEFT_NONOVERLAP_ZNORM_EUCLIDEAN;
  LENGTHS_26_52_104; MOTIF_MINIMUM_AND_DISCORD_MAXIMUM; STRUCTURAL_CLAIM_ONLY

EH10_PARAMETER_LOCK_PROPOSAL:
  ORDERS_3_4_5; DELAY_1; WINDOW_124; SEEDED_HASH_TIE_BREAK;
  NORMALIZED_PE_OVER_LN_FACTORIAL; MAXIMUM_ROLLING_ENTROPY_DEFICIT;
  STRUCTURAL_CLAIM_ONLY

NULL_SURROGATE_POLICY:
  PRIMARY_GLOBAL_OBSERVATION_PAIR_PERMUTATION;
  ROBUSTNESS_WITHIN_FOUR_EQUAL_CONTIGUOUS_ERAS;
  MONTE_CARLO_CONDITIONAL_PERMUTATION_APPROXIMATION

PERMUTATION_COUNT:
  999_PER_POLICY; 1998_TOTAL_INDEX_PERMUTATIONS

MULTIPLICITY_POLICY:
  HOLM_WITHIN_EH01_6_ENDPOINT_PRIMARY_AND_6_ENDPOINT_ROBUSTNESS_FAMILIES;
  HOLM_WITHIN_EH10_3_ENDPOINT_PRIMARY_AND_3_ENDPOINT_ROBUSTNESS_FAMILIES;
  NO_COMBINED_EH01_EH10_FAMILY_OR_EFFECT

CLASSIFICATION_THRESHOLDS:
  SIGNAL = SAME_ENDPOINT_GLOBAL_P_HOLM_LE_0.05_AND_ERA4_P_HOLM_LE_0.05;
  WEAK_SIGNAL = NOT_SIGNAL_AND_ANY_GLOBAL_P_HOLM_LE_0.10;
  NO_SIGNAL = ALL_GLOBAL_P_HOLM_GT_0.10;
  STOP_OR_INCOMPLETE_FAMILY = UNCLASSIFIED

EH01_COMPARATOR_DECISION:
  REMOVE_UNIDENTIFIABLE_FROZEN_STRATEGY_OOF_COMPARATOR;
  NO_PROXY; NO_NEW_INFRASTRUCTURE; DOWNGRADE_TO_STRUCTURAL_PRECONDITION_CLAIM

COMPUTATIONAL_FEASIBILITY:
  FEASIBLE_IN_PRINCIPLE_WITH_PINNED_OPTIMIZED_MATRIX_PROFILE_IMPLEMENTATION;
  EH01_EXPECTED_TENS_OF_MINUTES_TO_LOW_SINGLE_DIGIT_CPU_HOURS;
  EH10_EXPECTED_SECONDS_TO_MINUTES; O_N_WORKING_MEMORY_PER_SERIAL_PROFILE;
  COST_ESTIMATE_NON_LOAD_BEARING

UNRESOLVED_PRELOCK_ISSUES:
  OWNER_APPROVAL_OF_NARROWED_CLAIMS;
  FINAL_DATASET_AUTHORITY_CUTOFF_ROW_COUNT_AND_SHA256;
  PINNED_EH01_EH10_RUNNER_RUNTIME_DEPENDENCIES_COMMIT_AND_TREE;
  SYNTHETIC_FIXTURE_ACCEPTANCE;
  FINAL_CANONICAL_PREREGISTRATION_AND_HASH_NOT_YET_CREATED

EXECUTION: NOT_RUN
SCIENTIFIC_DATA_ANALYSIS: NOT_RUN
FINAL_CLASSIFICATION:
  EH01_EH10_PARAMETER_LOCK_PROPOSAL_READY_FOR_OWNER_REVIEW
```

STOP.
