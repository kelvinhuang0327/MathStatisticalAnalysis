# B649 Track B EH02 Parameter-Lock Proposal R1

```text
TASK_ID: B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1
CONTINUES: B649_TRACK_B_EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_R1
TASK_CLASS: PLANNING_ONLY
WORKER_ROUTE: NOT_APPLICABLE
JUDGE_MODE: NOT_APPLICABLE
STATUS: PROPOSAL_FOR_OWNER_REVIEW
LOCK_STATUS: NOT_LOCKED
PREREGISTRATION_HASH: NOT_CREATED
COLLISION_GATE: PASS (re-verified this task; see 1.2)
EH02_EXECUTIONS: 0
PREVIOUS_STOP: none (first attempt at EH02; not a retry)
EXECUTION: NOT_RUN
SCIENTIFIC_DATA_ANALYSIS: NOT_RUN
```

## 0. Decision summary

EH02 ("transfer-entropy directed lag graph") has a conceptual catalog entry but
no numeric design. This proposal recommends one outcome-blind, structurally
identifiable design testing directed conditional information transfer from
T539's and P638 Zone-1's causally available draw history into B649's next
draw, using the same chronological main-number-sum scalar convention already
locked for EH01/EH10, extended to three series with cross-lottery causal
alignment reused verbatim from the already-executed
`B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1` study.

Two separate directed edges are tested, each its own mechanism claim:

```text
EDGE_1: T539  -> B649   (main-number-sum scalar, last strictly-prior draw)
EDGE_2: P638Z1 -> B649  (main-number-sum scalar, last strictly-prior draw)
```

Per the Owner's explicit control requirement, every edge carries two
non-Holm, non-rescuable gates in addition to its Holm-corrected primary/
robustness p-values: a **timing control** (does the real, aligned signal beat
a deliberately 28-day-stale source snapshot — the exact placebo that defeated
the immediately preceding cross-lottery study) and a **directionality
control** (does the forward edge beat its own reverse direction). A `SIGNAL`
classification requires both controls to pass, not just a significant
p-value — this operationalizes the Owner's "do not interpret association as
causal transfer unless directionality + timing controls support that exact
claim" instruction as a hard numeric rule rather than a post-hoc judgment
call.

Recommended locks:

| Item | Recommended lock |
|---|---|
| Target representation | B649 chronological main-number sum, one scalar per draw (identical to EH01/EH10) |
| Source representation | T539 / P638 Zone-1 chronological main-number sum, one scalar per draw |
| Cross-lottery alignment | last strictly-prior source draw by `draw_date < B649_target_date` (date-only, same-day excluded) |
| Lag / embedding | source order 1 (single most-recent strictly-prior draw); target self-order 1; no lag or window grid |
| Discretization | causal expanding-window equal-frequency tertiles (`B=3` bins), independently per series |
| Estimator | discrete plug-in (Schreiber 2000) conditional transfer entropy, natural log |
| Comparator | unconditioned lagged mutual information, same discretization |
| Primary null | `999` source-only permutations (`GLOBAL` policy) |
| Era robustness null | `999` source-only permutations within four fixed contiguous equal-count eligible eras (`ERA4`) |
| Timing control | recompute using last source draw `<= target_date - 28 days`; gate = observed TE > stale TE |
| Directionality control | recompute reverse-direction TE (`B649 -> source`); gate = forward raw p < reverse raw p AND reverse raw p > 0.10 |
| Multiplicity | Holm within a 2-endpoint `GLOBAL` primary family and separately within a 2-endpoint `ERA4` robustness family (one endpoint per edge) |
| Classification | `SIGNAL` at same-edge `GLOBAL` and `ERA4` Holm p `<= 0.05` **and** both gates pass; `WEAK_SIGNAL` at `GLOBAL` Holm p `<= 0.10` when `SIGNAL` is not met; otherwise `NO_SIGNAL`; any stop condition is `INVALID_OR_UNIDENTIFIABLE` |

No joint three-series (T539+P638-combined) model is proposed. The catalog
describes EH02 as a graph of directed **edges**; combining sources is a
different, un-catalogued design and would reopen exactly the kind of
under-specified, sample-hungry, tunable joint model this proposal is built to
avoid. If the Owner wants a combined-source variant, it requires a new
variant ID and its own outcome-blind lock.

## 1. Authority and outcome-blind evidence boundary

### 1.1 Controlling authority

- Spec authority: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md`
  — EH02 section, `## EH02 — Transfer-entropy directed lag graph`.
  Observed SHA-256 during this planning task:
  `79f1adbf006a0f3b24279d57010d0a6c45a5cad606c95798e983dd2133e9ad31`
  (matches the manifest-recorded and previously EH01/EH10-cited hash for the
  same file — unchanged since 2026-08-13).
- Registry authority: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_FRONTIER_V2_SPEC_REGISTRY_R1.csv`,
  row `EH02,TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH,...,execution_authorized=NO`.
  Observed SHA-256: `fa8801edbeb91040d6e189dd7fcb2e8ec5cd8424dacd7f412ffe034f41d1ac43`.
- Collision authority: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL21_FULL_COLLISION_AUDIT_R1.md`,
  `### EH02 — TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH` section: closest internal
  hypotheses H11/H12/H13, five closest historical strategies all rated
  `STRONG_COMPONENT_OVERLAP` or `WEAK_COMPONENT_OVERLAP`, none rated an exact
  duplicate. Observed SHA-256: `9d013e21ceeab6512ee4d5c35eb5cfd353a930f7ddb18e9b5cd16df4b620710d`.
- EH02 authority (from the spec): directed conditional transfer entropy from
  a lagged source stream into a target stream, with causal (training-only)
  edge estimation, surrogate-tested edge stability, and comparison against
  lagged mutual information / co-occurrence / fixed-order Markov controls.
- Program framing authority: `B649_TRACK_D_POST_STRUCTURED_SET_SUCCESSOR_RESELECTION_R1.md`
  line 235-236 already names this exact instantiation "EH02 (cross-lottery
  transfer-entropy)" and flags its "real topical overlap with the
  already-failed lagged-context result" as the reason it was previously
  ranked below other candidates — this is the same concern the Owner's
  packet raises as the mandatory timing/directionality control, not a new
  issue discovered by this task.

### 1.2 Collision re-check (this task)

`[Confirmed]` `hypothesis_id=EH02` in the spec registry:
`local_validation_status` field is absent from that CSV's own schema, but the
paired hypothesis-inventory row (`B649_TRACK_D_EXTERNAL_HYPOTHESIS_INVENTORY_R1.csv`)
records `local_validation_status=NOT_RUN` and
`external_claim_status=EXTERNAL_UNVERIFIED_CLAIM`.

`[Confirmed]` Priority ranking (`B649_TRACK_D_EXTERNAL_PRIORITY_RANKING_R1.csv`):
`rank=12,hypothesis_id=EH02,...,local_validation_status=NOT_RUN`.

`[Confirmed]` No file or directory anywhere under this repository's
`.task-data/` (two entries: `B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1`,
`B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1`) or
`docs/research/` mentions EH02 or transfer entropy.

`[Confirmed]` The separate, already-sealed
`B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1` study
(2026-08-15, `WEAK_SIGNAL`/`DO_NOT_ADVANCE`, artifacts at
`/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1/`)
tested a **different, non-catalogued** mechanism — a ridge-regression
predictive uplift using windowed T539/P638 features — not conditional
transfer entropy, not EH02, and not registered under any `EH` identifier in
the Frontier V2 catalog. It is reused here only as a source of already-vetted
causal-alignment and placebo-design conventions (§2, §8), not as a prior
execution of EH02 itself. No collision.

`[Confirmed]` No `EH02` execution artifact, preregistration, or result file
exists anywhere under `~/VibeCoding-WorkSpace` matching `*EH02*` or
`*TRANSFER_ENTROPY*` in its name.

**Conclusion: `STOP_EH02_ALREADY_EXECUTED_OR_COLLISION` does not apply.**

### 1.3 Inspected evidence

`[Confirmed]` The project rule contracts (`src/lottolab/domain/lottery_rules.py`)
define: `BIG_LOTTO` (B649) — 6 main numbers from 1-49, unique, plus 1 special
number from 1-49; `DAILY_539` (T539) — 5 main numbers from 1-39, unique, no
special number; `POWER_LOTTO` (P638) — 6 main "Zone-1" numbers from 1-38,
unique, plus 1 "Zone-2" special number from 1-8.

`[Confirmed]` The already-sealed cross-lottery lag study established and
verified (`leakage_audit: PASS`, `causal joins: PASS`) a working, date-only,
strictly-prior causal alignment between B649 targets and T539/P638 Zone-1
source draws, using `cross_draw_date < B649_target_date` with same-day
results conservatively excluded. Its `locked_config.json` records exact
window/placebo conventions (`STALE_DAYS = 28`, shuffled-prior-date placebo,
feature-count-matched placebo) that are directly reusable as project
convention for EH02's own controls.

`[Confirmed]` The tracked project dependency declaration
(`pyproject.toml`) and the active `python3` do not provide `numpy` or
`scipy` — reconfirmed this task (`ModuleNotFoundError: No module named
'numpy'`), consistent with the EH01/EH10 lock-execute task's finding.

`[Confirmed]` EH01/EH10's locked and executed preregistration
(`docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-preregistration.md`,
hash `f12ef1314e4f...`) establishes this program's live conventions for
deterministic SHA-256 hash-sort permutation generation, Holm step-down
multiplicity, four-era robustness partitioning, and `SIGNAL`/`WEAK_SIGNAL`/
`NO_SIGNAL` dual-null gating — reused directly below rather than re-derived.

`[Unknown]` Whether the B649 draw-history convention used by the
already-sealed EH01/EH10 chain (`research_draw_bindings`,
`canonical-full-history-2382-draws-v1`, `EXCLUDE_DATE_LIKE`, 2,138 clean
draws, 2007-03-09..2026-07-31) and the convention used by the cross-lottery
lag study (a separately sourced "sealed historical foundation" via a legacy
strategy's raw ticket export, 2,145 draws, 2007-01-02..2026-07-10) are
reconcilable, or which one is authoritative for a Track B falsification task.
This proposal does not resolve that discrepancy (§11 item 2) and does not
assume either is correct.

`[Unknown]` Whether the T539 (5,913 draws, 2007-01-01..2026-07-13) and P638
Zone-1 (1,928 draws, 2008-01-24..2026-07-13) counts recorded by the
cross-lottery lag study match this program's most current canonical/contamination-checked
history for those two lotteries. Not independently re-verified this task.

### 1.4 Explicitly not inspected or run

- No B649, T539, or P638 main-number values were read.
- No transfer-entropy, mutual-information, or any other EH02 statistic was
  computed.
- No historical signal, result table, or hypothesis outcome was inspected.
- No surrogate, permutation, model, backtest, or allocation was run.
- No Frontier V2 hypothesis beyond EH02 was audited; EH01, EH10, EH03-EH09,
  EH11+ remain untouched and out of scope.
- The Frontier V2 catalog governance (priority list, discovery waves,
  saturation report) was read only to confirm EH02's identity, ranking, and
  non-execution — not to re-rank or re-select a hypothesis.

## 2. Shared exact input representation and cross-lottery chronology contract

### 2.1 Per-lottery scalar series

For lottery `L` with main-number count `k_L` (`k_B649=6`, `k_T539=5`,
`k_P638Z1=6`), let draw `τ` have main numbers `m_(L,τ,1), ..., m_(L,τ,k_L)`
and define

```text
s_L(τ) = sum_{r=1}^{k_L} m_(L,τ,r)
```

`canonical_draw_id(L, τ)` means the ASCII base-10 rendering of
`int(authority_draw_id)` for that lottery/draw, no sign, no leading zeroes —
identical convention to the EH01/EH10 lock. P638 Zone-2 (the 1-of-8 special
number) and B649's own special number are excluded from every series, exactly
as in EH01/EH10 and the cross-lottery lag study.

### 2.2 B649 target index and eligibility

Let the final preregistered, authority-pinned B649 chain contain targets
`t = 1, ..., n` in ascending `(draw_date, draw_id)` order, with
`x_t = s_B649(t)`.

### 2.3 Cross-lottery causal alignment

For each B649 target `t`, define, separately for `T539` and for `P638Z1`:

```text
prior_L(t) = the draw τ of lottery L with the maximum draw_date
             such that draw_date_L(τ) < draw_date_B649(t)
```

Equality is excluded (same-day source results are conservatively treated as
unavailable, not as prior information) — this is the exact rule already
verified leak-free in the cross-lottery lag study (`Strict-order failures: 0`
there). If `prior_L(t)` does not exist (no earlier `L` draw at all), `t` is
not eligible for that edge.

### 2.4 Eligible index set and burn-in

`t` is eligible for **edge `L -> B649`**'s primary analysis only if all of:

1. `t - 1 >= 1` (a B649 self-history value `x_(t-1)` exists),
2. `prior_L(t)` exists,
3. `t` is at least the `201`st chronologically eligible target under
   conditions 1-2 for that edge (a `200`-observation causal burn-in; see
   §9 for the exact rationale), used only to seed the expanding-window
   discretization in §3.2, not to fit or select anything else.

The two edges (`T539 -> B649`, `P638Z1 -> B649`) have their own eligible
index sets; they are not forced to share eligibility, and no draw is dropped
from one edge merely because it is ineligible for the other.

### 2.5 What this representation deliberately avoids

This mirrors EH01/EH10's own shared-representation rationale: one
low-dimensional, already-precedented summary per lottery avoids a
post-result choice among many possible cross-lottery features (the
window-aggregated, multi-feature-pack design the ridge-regression study used
is a different, already-tested, already-failed-its-own-gate mechanism, not
reused here). Any different summary, any multi-draw window, or any joint
combined-source design is a new preregistered variant, not this one.

## 3. Discretization and the transfer-entropy estimator

### 3.1 Bin count

Each of the three scalar series (`x` = B649, `y` = source `L`) is
independently discretized into `B = 3` bins (tertiles) per series. `B=3`
keeps the primary joint state space at `3^3 = 27` cells for the three
variables used in a single edge's conditional transfer entropy
(`x_(t+1), x_t, y_prior(t)`), which is the smallest state space that is not
a degenerate binary split, while remaining estimable at this program's B649
scale (~2,000 causal targets; §10).

### 3.2 Causal (expanding-window) bin edges

For eligible target `t` on edge `L -> B649`, the bin edges for **each**
series are computed from that series' own empirical tertiles using only
observations strictly before `t` in the eligible sequence for that edge —
never `t`'s own or any later value. This is the same "no full-history
normalization, strictly causal at each point" discipline EH10 already locked
for its rolling entropy computation, applied here to quantile estimation
instead of an entropy window. Bin edges are therefore not fixed once, and
not computed from the full series in hindsight.

### 3.3 Deterministic tie handling

Scalar sums are discrete and ties are expected. For lottery `L`, draw `τ`,
edge context `E` (`E` distinguishes which of the possible tie situations this
key is used for — B649 target ties, or source ties):

```text
tie_key(E, L, draw_id) = SHA256(
  UTF8("6490110|EH02|TIE_V1|" + E + "|" + L + "|" + canonical_draw_id)
)
```

Within a discretization step, values tied on `s_L` are ordered by
`(s_L, tie_key(E, L, draw_id))` before assigning tertile boundaries. Unequal
sums are never perturbed. This is a direct extension of EH10's own seeded
SHA-256 tie-break convention (§4.3 of the EH01/EH10 preregistration), salted
per-lottery so that B649, T539, and P638Z1 ties are broken independently
rather than sharing one key.

### 3.4 Discrete plug-in transfer entropy (Schreiber 2000)

For edge `L -> B649`, let `X' = bin(x_t)`, `X = bin(x_(t-1))`,
`Y = bin(prior value of L at prior_L(t))`, over the edge's eligible,
post-burn-in index set. Empirical joint probabilities `p(x', x, y)` are
formed by counting occurrences across that eligible set. The primary
statistic is

```text
TE(L -> B649) = sum_{x',x,y} p(x',x,y) * ln( p(x'|x,y) / p(x'|x) )
```

the standard discrete conditional transfer entropy definition (Schreiber
2000, source S04). A term with `p(x,y) = 0` is omitted (undefined context,
no data); a term with `p(x,y) > 0` and `p(x',x,y) = 0` contributes exactly
`0` by the standard `0 * ln(0/c) = 0` convention, matching EH10's own
`0 * ln(0) = 0` rule. Natural log is locked, matching EH10's project
convention; the log base does not affect which surrogate rank the observed
statistic falls at, so it cannot affect any p-value or classification.

No bias-correction term (e.g. Miller-Madow) is added. The permutation null
in §5 applies the identical plug-in estimator to every surrogate, so the
finite-sample plug-in bias is common to the observed statistic and its null
distribution and cancels in the resulting p-value — the standard
justification (used since Schreiber's original paper) for testing
information-theoretic plug-in statistics via surrogates rather than via a
bias-corrected point estimate.

### 3.5 Comparator: lagged mutual information

```text
MI(L ; B649) = sum_{x',y} p(x',y) * ln( p(x',y) / (p(x') * p(y)) )
```

using the same discretization, eligible set, and zero-term convention. This
directly implements the spec's named "lagged mutual information" comparator:
the gap between `TE` and `MI` shows whether conditioning on B649's own prior
value changes the picture. `MI` is diagnostic — reported alongside `TE` but
not part of any Holm family and cannot promote or rescue a classification.

## 4. Two locked edges

### 4.1 Claim being tested

For each of `EDGE_1: T539 -> B649` and `EDGE_2: P638Z1 -> B649`, this design
tests whether `L`'s causally available last-strictly-prior draw contains
directed conditional information about B649's next main-number-sum tertile,
beyond what B649's own immediately preceding value already predicts, under
the locked representation, discretization, and both required controls.

It does **not** test predictive advantage, ticket quality, strategy loss, or
prize value. `SIGNAL` below means
`EH02_DIRECTED_INFORMATION_TRANSFER_AT_LOCKED_REPRESENTATION_LAG_AND_CONTROLS`
only, per edge.

### 4.2 Lag and embedding (shared by both edges)

```text
source lag: 1 (single last strictly-prior draw of L; no multi-draw window)
target self-order: 1 (single immediately preceding B649 value)
```

No lag grid, no window-size grid, no embedding-order grid. This is the
single locked design for both edges; it is the smallest embedding that
still distinguishes "transfer" (conditioning on B649's own last value) from
raw lagged correlation (§3.5's `MI` comparator omits that conditioning). A
richer embedding (longer B649 self-history, more than one prior source draw)
is explicitly out of scope for this variant (§14).

## 5. Exact null/surrogate and deterministic seed policy

### 5.1 Primary conditional null: `GLOBAL` (source-only permutation)

The null hypothesis for edge `L -> B649` is that, conditional on B649's own
history, the source value `y_prior_L(t)` carries no directional information
about `x_t` — i.e., the true pairing between eligible target `t` and its
`prior_L(t)` value is exchangeable. Each surrogate independently permutes
the **source-value assignment only** across the edge's eligible index set,
leaving every `(x_(t-1), x_t)` pair exactly as observed. This is the
standard directed surrogate for testing `TE(Y -> X)`: it destroys the
source-target correspondence while exactly preserving B649's own marginal,
its own serial (auto-)structure, and the source series' own marginal
distribution.

### 5.2 Era-preserving robustness null: `ERA4`

Partition each edge's own eligible, post-burn-in index sequence (indexed
`1, ..., n_E` in eligibility order, not raw B649 draw order) into four
contiguous, equal-count eras using

```text
era(i) = min(4, floor(4 * (i - 1) / n_E) + 1),  i = 1, ..., n_E
```

Within each surrogate, permute the source-value assignment independently
inside each era and concatenate the four eras in original order. `ERA4` is
robustness evidence only; per §7 it can confirm but never create `SIGNAL`.

### 5.3 Deterministic permutation generation

```text
MASTER_SEED: 6490110
REPLICATE_INDEX: b = 0, ..., 998
PERMUTATIONS_PER_POLICY: 999
```

For edge identifier `EDGE_ID` in
`{T539_TO_B649, P638Z1_TO_B649, B649_TO_T539_REVERSE, B649_TO_P638Z1_REVERSE}`,
policy `P` in `{GLOBAL, ERA4}`, and replicate `b`:

```text
perm_key(EDGE_ID, P, b, i) = SHA256(
  UTF8("6490110|EH02|" + EDGE_ID + "|" + P + "|" + zero_padded_b + "|" + i)
)
```

`zero_padded_b` is exactly three ASCII decimal digits (`000`-`998`); `i` is
the eligible-index position (ASCII decimal, no leading zeroes). Sort eligible
positions ascending by this 256-bit key (within each era, for `ERA4`) to
obtain the permutation applied to the source-value array. Each `EDGE_ID` is
salted separately, so the four possible edges/directions never share a
permutation even at the same `(P, b)`. If two replicate indices produce the
same complete permutation within a policy/edge, or the generated
index-ledger digest differs between preregistration verification and
execution, stop; do not silently generate replacements.

### 5.4 Raw p-value

For `TE` (always larger-is-more-extreme), let `B` be the count among the
`999` surrogate statistics with `TE_surrogate >= TE_observed`:

```text
p_raw = (B + 1) / (999 + 1)
```

Minimum attainable raw p-value: `0.001`. This is a Monte Carlo approximation
to the full conditional-permutation null, not exhaustive enumeration.

## 6. Timing control (required, non-Holm gate)

### 6.1 Construction

For edge `L -> B649` at target `t`, define the deliberately misaligned
source value using the exact `STALE_DAYS = 28` convention already used and
leakage-audited in the immediately preceding cross-lottery study:

```text
stale_prior_L(t) = the draw τ of L with the maximum draw_date such that
                    draw_date_L(τ) <= draw_date_B649(t) - 28 days
```

`TE_stale(L -> B649)` is computed with the identical estimator, eligible set
(restricted to targets where `stale_prior_L(t)` also exists), discretization,
and `GLOBAL` permutation procedure as the real edge (§3-§5), substituting
`stale_prior_L(t)` for `prior_L(t)` throughout.

### 6.2 Gate

```text
TIMING_CONTROL_PASS(edge) := TE_observed(edge) > TE_stale(edge)
```

A real, causally aligned directed dependency should not be exceeded by a
28-day-stale snapshot of the same source lottery; if it is, that is direct
evidence the detected structure is closer to slow era drift than to genuine
short-lag transfer — precisely the failure mode the Owner's IMPORTANT
CONTROL section names from the immediately preceding study. This is a point
comparison of observed statistics, not a p-value, and carries no additional
multiplicity correction; it cannot be used to rescue a `NO_SIGNAL` result
and is evaluated exactly once, on the locked design, never re-run at a
different stale offset.

## 7. Directionality control (required, non-Holm gate)

### 7.1 Construction

For edge `L -> B649`, also compute the reverse-direction statistic
`TE(B649 -> L)`: source series is now B649 (`X = bin(x_(t-1))` becomes the
conditioning/target-self term for `L`'s own series), target series is `L`,
using `L`'s own draw index as the base timeline and B649's last
strictly-prior draw (by the same date-only, same-day-excluded rule, mirrored)
as the "source." Same discretization (bin edges recomputed causally on each
series in its new role), same estimator, same `GLOBAL` permutation procedure
(salted `B649_TO_T539_REVERSE` / `B649_TO_P638Z1_REVERSE` per §5.3). `ERA4`
is not computed for the reverse direction — it is a diagnostic control, not
a primary/robustness endpoint.

### 7.2 Gate

```text
DIRECTIONALITY_CONTROL_PASS(edge) :=
  p_raw(forward) < p_raw(reverse)  AND  p_raw(reverse) > 0.10
```

A genuine directed-transfer claim requires the forward direction to look
more extreme than the reverse direction, and the reverse direction to not
itself look like a real effect. This is a prespecified, symmetric,
point/threshold rule — not a formal two-sample test — evaluated exactly
once per edge and reported honestly regardless of outcome.

## 8. Additional non-Holm diagnostic (descriptive only)

Recompute the primary `TE` (both edges, `GLOBAL` null only) using `B = 2`
(median-split) bins instead of `B = 3`, otherwise identical design. Reported
as a descriptive robustness view alongside the era-local diagnostics; it has
no p-value role, cannot promote a `NO_SIGNAL`/`WEAK_SIGNAL` result, and is
not itself subject to a "does the alternate binning pass" gate. Its purpose
is transparency about bin-count sensitivity, not an alternate primary.

## 9. Multiplicity policy

### 9.1 Families

```text
F_EH02_PRIMARY: 2 raw p-values
  = TE(T539 -> B649), TE(P638Z1 -> B649), under GLOBAL

F_EH02_ROBUSTNESS: 2 raw p-values
  = the same two edges, under ERA4
```

Timing-control point comparisons (§6), directionality-control p-values (§7),
the `MI` comparator (§3.5), and the alternate-binning diagnostic (§8) are
never members of either family and receive no Holm adjustment.

### 9.2 Holm adjustment

Within each family of size `K = 2`, sort raw p-values `p_(1) <= p_(2)`. The
step-down threshold at rank `r` is `alpha / (K - r + 1)`, and

```text
p_holm,(r) = min(1, max_{j <= r} ((K - j + 1) * p_(j)))
```

mapped back to the original edges. At familywise `alpha = 0.05`, first-step
raw thresholds are `0.05/2 = 0.025`; at exploratory `alpha = 0.10`,
`0.10/2 = 0.05`. `EDGE_1` and `EDGE_2` remain separate mechanism claims
within a shared family only for multiplicity accounting — there is no
combined two-edge statistic, vote, or omnibus effect.

## 10. Numeric classification rules

Applied separately to `EDGE_1` and `EDGE_2`. Uses the Owner packet's own
label set (`SIGNAL`, `WEAK_SIGNAL`, `NO_SIGNAL`, `INVALID_OR_UNIDENTIFIABLE`),
not the EH01/EH10 preregistration's `UNCLASSIFIED` label.

### `SIGNAL`

All of the following, for the same edge:

```text
GLOBAL Holm-adjusted p <= 0.05
AND ERA4 Holm-adjusted p <= 0.05
AND TIMING_CONTROL_PASS
AND DIRECTIONALITY_CONTROL_PASS
```

### `WEAK_SIGNAL`

`SIGNAL` is not met, and `GLOBAL` Holm-adjusted p `<= 0.10` for that edge.
This is the only outcome for an edge that clears the primary p-value bar but
fails either control — the same shape of result the immediately preceding
cross-lottery study produced, now capped by design rather than requiring a
post-hoc judgment call.

### `NO_SIGNAL`

`GLOBAL` Holm-adjusted p `> 0.10` for that edge. Timing/directionality
controls cannot change this label.

### `INVALID_OR_UNIDENTIFIABLE`

Any stop condition in §13, a non-finite endpoint, an incomplete family, or an
execution-contract breach. Never reported as `NO_SIGNAL`.

Both edges are reported individually. Concordant labels do not form a joint
EH02 effect; discordant labels do not permit reporting only the more
favorable edge.

## 11. Robustness and geometry checks

1. Recompute both primary endpoints under `ERA4`; can confirm but not create
   `SIGNAL` (§10).
2. Report each edge's timing-control point estimates (`TE_observed`,
   `TE_stale`) and directionality-control p-values (`p_raw(forward)`,
   `p_raw(reverse)`) regardless of which classification results.
3. Report the `B=2` alternate-binning `TE`/p-value as a descriptive
   diagnostic (§8).
4. Report the `MI` comparator alongside `TE` for both edges (§3.5).
5. Do not add a fifth era partition, an alternate stale-day offset, an
   alternate lag/window, an alternate bin count as a rescue, a parametric
   null, or a post-result sensitivity analysis to change a label.

Data-geometry preconditions, checked once eligible sets are built:

```text
Each edge's total eligible (post-burn-in) index count: >= 800
Each of the four ERA4 partitions for that edge: >= 30 eligible indices
Burn-in seed window before the first eligible index: 200 observations
```

The `200`-observation burn-in gives at least `~66` observations per tertile
for the earliest causal quantile estimate. The `>=800`-total / `>=30`-per-era
bounds are the minimum needed for the 27-cell joint histogram to be
non-degenerate in every era; they are deliberately not a "well-powered"
target, because `ERA4` is confirmatory-only (§10) and a thin era can only
make `SIGNAL` harder to reach, never easier. If either bound fails after the
dataset is pinned, stop before reading number values and return the
corresponding prelock issue rather than lowering the bound.

## 12. Rationale table for every free parameter

Only the four permitted rationale classes are used.

| Free parameter or decision | Lock | Rationale class | Outcome-blind rationale |
|---|---:|---|---|
| B649 scalar | sum of six main numbers | `PROJECT_CONVENTION` | Identical to the already-locked EH01/EH10 representation; avoids summary shopping. |
| T539 scalar | sum of five main numbers | `PROJECT_CONVENTION` | Directly analogous to B649's locked convention, using T539's own rule-contract main-number count. |
| P638Z1 scalar | sum of six Zone-1 main numbers | `PROJECT_CONVENTION` | Same convention; Zone-2 excluded exactly as the cross-lottery lag study already excluded it. |
| Cross-lottery join rule | `draw_date < target_date`, same-day excluded | `PROJECT_CONVENTION` | Reused verbatim from the already leakage-audited (`PASS`) cross-lottery lag study; not re-derived. |
| Source lag | 1 (last strictly-prior draw only) | `PROJECT_CONVENTION` | Matches the predecessor study's core causal-state definition; explicitly avoids reopening a window-size choice, which is exactly the axis the Owner's control section warns against re-tuning. |
| Target self-order | 1 | `STANDARD_STATISTICAL_CONVENTION` | Minimal Markov conditioning order needed for a "transfer" (conditional) claim to be distinguishable from a "correlation" (unconditioned `MI`) claim. |
| Bin count `B` | `3` (tertiles) | `DATA_GEOMETRY_BOUND` | Smallest non-binary split; keeps the 3-variable joint state space (`27` cells) estimable at this program's B649 scale. |
| Bin edges | causal expanding-window, per series | `PROJECT_CONVENTION` | Extends EH10's "no full-history normalization" rule from entropy windows to quantile estimation. |
| Tie handling | seeded per-series SHA-256 key | `PROJECT_CONVENTION` | Direct extension of EH10's own tie convention; salted per lottery to avoid coupling B649/T539/P638 tie order. |
| TE estimator | discrete plug-in, Schreiber 2000 | `STANDARD_STATISTICAL_CONVENTION` | The foundational, most-cited transfer-entropy definition (source S04); tractable without numpy/scipy. |
| Logarithm | natural | `PROJECT_CONVENTION` | Matches EH10's locked convention; base is immaterial to any p-value or classification. |
| Bias correction | none (surrogate-implicit) | `STANDARD_STATISTICAL_CONVENTION` | Plug-in bias is common to observed and surrogate statistics under the identical-estimator surrogate test; a separate correction term would be redundant. |
| Comparator | unconditioned lagged mutual information | `PROJECT_CONVENTION` | Directly implements the catalog's own named comparator with the same discretization. |
| Primary null | source-only permutation | `STANDARD_STATISTICAL_CONVENTION` | The standard directed surrogate for `TE(Y->X)` significance (shuffle the putative source, preserve the target's own dynamics), discussed in the foundational reference itself. |
| Robustness null | source-only permutation within 4 eligibility-ordered eras | `PROJECT_CONVENTION` | Direct extension of EH01/EH10's `ERA4` mechanism to this edge's own eligible-index timeline. |
| Permutations per policy | `999` | `PROJECT_CONVENTION` | Identical to EH01/EH10's locked count; gives the same `0.001` p-grid and Holm-threshold headroom at family size 2. |
| Master seed / generator | `6490110`, SHA-256 hash-sort | `PROJECT_CONVENTION` | Reuses EH01/EH10's exact deterministic mechanism, extended with an `EDGE_ID` salt so the four possible edges/directions never share a permutation. |
| Timing-control offset | `28` days | `PROJECT_CONVENTION` | The exact stale-offset already used, executed, and leakage-audited in the immediately preceding cross-lottery study — not a new invented number. |
| Timing-control gate | `TE_observed > TE_stale` | `PROJECT_CONVENTION` | Directly operationalizes the Owner's named failure mode from that same predecessor study as a hard pre-registered rule. |
| Directionality-control gate | `p_fwd < p_rev AND p_rev > 0.10` | `STANDARD_STATISTICAL_CONVENTION` | Operationalizes the classical transfer-entropy directionality/asymmetry criterion (Schreiber 2000) as a prespecified point rule. |
| Burn-in | `200` eligible observations | `DATA_GEOMETRY_BOUND` | Gives `~66` observations per tertile at the earliest eligible causal quantile estimate. |
| Era/geometry floor | `>=800` total, `>=30` per era | `DATA_GEOMETRY_BOUND` | Minimum for the 27-cell joint histogram to be non-degenerate in every era; deliberately conservative since `ERA4` is confirmatory-only. |
| Holm familywise threshold | `0.05` | `STANDARD_STATISTICAL_CONVENTION` | Matches EH01/EH10's locked confirmatory threshold. |
| Weak threshold | `0.10` | `STANDARD_STATISTICAL_CONVENTION` | Matches EH01/EH10's locked exploratory threshold. |
| Family size | `2` per family | `DATA_GEOMETRY_BOUND` | Derived exactly from two catalogued source lotteries (T539, P638Z1); not chosen. |
| Joint/combined-source model | none | `PROJECT_CONVENTION` | The catalog frames EH02 as a directed-edge graph; a joint source model is a materially different, un-catalogued design requiring its own variant ID. |
| Alternate-bin diagnostic | `B=2`, descriptive only | `DATA_GEOMETRY_BOUND` | Shows bin-count sensitivity without opening a "which bin count wins" rescue path. |

## 13. Computational feasibility

### 13.1 Evaluation count

Per edge: `999` (`GLOBAL` primary) + `999` (`ERA4` robustness) + `999`
(reverse-direction directionality control, `GLOBAL` only) = `2,997`
permutation evaluations, plus one observed-statistic pass and one
`TE_stale` point-estimate pass. Across both edges: `5,994` permutation
evaluations. Adding the `B=2` descriptive diagnostic (`999` `GLOBAL` reps
per edge): `7,992` permutation evaluations total.

### 13.2 Complexity and expected order

Every evaluation is a single pass over an eligible index set of order
`~1,000-2,000` (bounded by the B649 draw count, well under either candidate
dataset's size per §1.3), building a `27`-cell (or `8`-cell for `MI`, or
`8`-cell for the `B=2` diagnostic) count table and summing a closed-form
entropy expression — `O(n)` per evaluation, no pairwise distance sweep and
no k-NN search (unlike a continuous KSG-style transfer-entropy estimator,
which this proposal deliberately avoids). Total work is on the order of
`8,000 * n` scalar counting operations, expected to run in low single-digit
seconds to at most a few minutes in pure Python — no numpy/scipy dependency
is required, unlike EH01's matrix-profile capability gap. This is a resolved
design choice, not an open prelock issue.

### 13.3 Capability note

The discrete plug-in estimator, causal expanding-quantile discretization,
and hash-sort permutation generator can all be implemented with the Python
standard library alone (`hashlib`, `math.log`, `bisect`), consistent with
this project's tracked dependency declaration. Before execution, the Owner
must still approve a pinned implementation route and a small synthetic
fixture check (e.g., a hand-computable 3-symbol synthetic source/target pair
with a known injected lag-1 dependency) before any scientific data is read —
same discipline as EH01/EH10's synthetic-fixture gate, cheaper to satisfy
here because the estimator itself is much simpler.

## 14. Unresolved infrastructure dependencies and prelock issues

1. **Owner scope decision** — approve or reject the proposed two-edge,
   single-lag, dual-control design in place of a joint/combined-source or
   multi-lag alternative.
2. **Dataset pin (B649)** — two candidate B649 authorities are in current use
   by this program (`research_draw_bindings` `EXCLUDE_DATE_LIKE` clean chain,
   2,138 draws, 2007-03-09..2026-07-31; vs. the cross-lottery lag study's
   sealed historical-foundation chain, 2,145 draws, 2007-01-02..2026-07-10).
   The final preregistration must pin exactly one, with its source path,
   cutoff, row count, and logical SHA-256, before any number values are read.
3. **Dataset pin (T539 / P638 Zone-1)** — the cross-lottery lag study's own
   counts (5,913 / 1,928 draws) are not independently re-verified as this
   program's current canonical/contamination-checked history for either
   lottery in this task. Must be pinned and hash-verified before execution.
4. **Implementation route** — pin exact module path, runtime, and dependency
   lock (none required beyond the standard library per §13.3) before
   execution.
5. **Synthetic fixture** — construct and pin a small hand-verifiable
   synthetic 3-symbol source/target pair with a known injected lag-1
   dependency; the implementation must reproduce the known-correct `TE`
   value before any real data is read.
6. **Code identity** — pin repository path, branch, commit, and tree for any
   later runner, plus the `.task-data` output root for this task.
7. **Final lock artifact** — canonical preregistration JSON, its digest, and
   the permutation-index ledger do not yet exist and must not be created
   until the Owner approves this proposal.

None of these issues authorizes EH02 execution now.

## 15. Future preregistration schema

After Owner approval, create one canonical machine-readable preregistration
with at least the following fields. `TBD_BEFORE_DATA_READ` values are
mandatory pre-execution pins, not post-result options.

```yaml
schema_version: 1
task_id: B649_TRACK_B_EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_R1
approval:
  owner_decision_id: TBD_BEFORE_DATA_READ
  approved_at: TBD_BEFORE_DATA_READ
authority:
  spec_path: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md
  spec_sha256: 79f1adbf006a0f3b24279d57010d0a6c45a5cad606c95798e983dd2133e9ad31
dataset:
  b649_authority_mode: TBD_BEFORE_DATA_READ
  b649_source_path: TBD_BEFORE_DATA_READ
  t539_source_path: TBD_BEFORE_DATA_READ
  p638_zone1_source_path: TBD_BEFORE_DATA_READ
  eligible_history_rule: TBD_BEFORE_DATA_READ
  cutoff: TBD_BEFORE_DATA_READ
  row_counts: TBD_BEFORE_DATA_READ
  logical_sha256: TBD_BEFORE_DATA_READ
input:
  target_lottery: BIG_LOTTO
  source_lotteries: [DAILY_539, POWER_LOTTO_ZONE1]
  order: [draw_date_ascending, draw_id_ascending]
  scalar: sum_of_main_numbers
  include_special_or_zone2: false
alignment:
  rule: last_strictly_prior_by_draw_date
  same_day_policy: excluded
  timestamp_granularity: date_only
representation:
  bins: 3
  bin_edge_policy: causal_expanding_window_per_series
  tie_policy: sha256_secondary_key_v1_per_series
  burn_in_observations: 200
edges:
  - edge_id: T539_TO_B649
    source_lag_draws: 1
    target_self_order: 1
  - edge_id: P638Z1_TO_B649
    source_lag_draws: 1
    target_self_order: 1
estimator:
  method: discrete_plugin_conditional_transfer_entropy
  reference: schreiber_2000
  log: natural
  bias_correction: none_surrogate_implicit
comparator:
  method: unconditioned_lagged_mutual_information
null:
  primary_policy: source_only_permutation_global
  robustness_policy: source_only_permutation_within_four_eligibility_eras
  permutations_per_policy: 999
  master_seed: 6490110
  generator: sha256_hash_sort_edge_salted
  raw_p: (extreme_count_plus_1)/1000
  tail: one_sided_larger_or_equal
controls:
  timing:
    stale_days: 28
    gate: observed_te_greater_than_stale_te
  directionality:
    reverse_edges: [B649_TO_T539_REVERSE, B649_TO_P638Z1_REVERSE]
    gate: forward_raw_p_less_than_reverse_raw_p_and_reverse_raw_p_greater_than_0.10
diagnostics:
  alternate_bins: 2
  comparator_reported: true
multiplicity:
  method: Holm_step_down
  primary_family_size: 2
  robustness_family_size: 2
  cross_edge_family: none
classification:
  signal_requires: [global_holm_le_0.05, era4_holm_le_0.05, timing_pass, directionality_pass]
  weak_signal_requires: [not_signal, global_holm_le_0.10]
  no_signal_requires: [global_holm_gt_0.10]
  stop_result: INVALID_OR_UNIDENTIFIABLE
geometry_floor:
  eligible_total_minimum: 800
  eligible_per_era_minimum: 30
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
  retain_timing_and_directionality_diagnostics: true
  retain_raw_scientific_rows: false_unless_separately_authorized
claim_boundaries:
  predictive_advantage: NOT_TESTED
  allocation_benefit: NOT_TESTED
  prize_value_advantage: NOT_TESTED
  universal_cross_lottery_causality: NOT_TESTED
  arbitrary_lag_generalization: NOT_TESTED
preregistration_sha256: null_until_owner_approval
```

The final hash must be computed only after every `TBD_BEFORE_DATA_READ`
field is resolved and before any scientific number values are loaded. It
must not be created from this proposal.

## 16. Future execution stop conditions

Any stop returns `INVALID_OR_UNIDENTIFIABLE`, records `EXECUTION: NOT_RUN` if
no statistic started or `EXECUTION: STOPPED_INVALID` if computation started,
and performs no parameter rescue.

| Stop code | Exact trigger |
|---|---|
| `STOP_SPEC_AUTHORITY_MISMATCH` | Spec path or SHA-256 differs from the approved preregistration. |
| `STOP_OWNER_APPROVAL_ABSENT` | This proposal's design is not explicitly approved. |
| `STOP_DATASET_AUTHORITY_UNPINNED` | Any of the three lotteries' path, mode, cutoff, row count, or SHA-256 is unresolved. |
| `STOP_DATASET_AUTHORITY_MISMATCH` | Live dataset identity differs from the preregistered identity. |
| `STOP_OUTCOME_BLINDNESS_BREACH` | Any EH02 result was inspected before final lock/hash. |
| `STOP_IMPLEMENTATION_UNPINNED` | Runner, runtime, dependency lock, commit, or tree is unresolved. |
| `STOP_SYNTHETIC_FIXTURE_FAIL` | Implementation disagrees with the preregistered synthetic fixture. |
| `STOP_CHRONOLOGY_INVALID` | Duplicate/ambiguous draw identity or invalid ordering in any of the three lotteries. |
| `STOP_EH02_GEOMETRY_INSUFFICIENT` | Either edge's eligible total or any era falls below §11's floor. |
| `STOP_PERMUTATION_LEDGER_MISMATCH` | Fewer than 999 unique permutations per policy/edge, or index-array digests drift. |
| `STOP_NONFINITE_ENDPOINT` | Any primary, robustness, timing, or directionality statistic is missing or nonfinite. |
| `STOP_MULTIPLICITY_CONTRACT_BREACH` | A p-value is omitted, moved between families, or adjusted with a non-Holm rule. |
| `STOP_CONTROL_SCOPE_EXPANSION` | Execution substitutes a different stale offset, a different reverse-edge design, or otherwise alters either control after seeing results. |
| `STOP_PARAMETER_DRIFT` | Any representation, lag, bin count, tie rule, estimator, null, seed, count, threshold, or era rule differs from the approved hash. |
| `STOP_EH02_POST_LOCK_CHANGE_REQUIRED` | Any change to the locked design is needed after preregistration lock, per the Owner packet's own instruction. |
| `STOP_OUT_OF_SCOPE_HYPOTHESIS` | Execution attempts EH01, EH10, another Frontier V2 hypothesis, or a combined/joint-source EH02 variant. |

## 17. No-rescue and claim boundaries

### 17.1 No-rescue commitment

After the final preregistration is locked, do not change the scalar
representation, the lag/embedding, the bin count, the tie rule, the
estimator, either null, the stale-day offset, the directionality gate, the
simulation count, era partitioning, or classification thresholds in response
to any result. A materially different design requires a new variant ID and a
new outcome-blind Owner approval before data access. This explicitly forbids
re-running the timing control at a different offset or re-running the
directionality control with a different embedding after seeing a
disappointing result — the exact "parameter rescue" and "stale-lag rescue"
patterns the Owner packet names.

### 17.2 Positive-result boundary

A `SIGNAL` is exploratory evidence of directed conditional information at a
single named representation, lag, and control set. It does not show that
B649 outcomes are predictable, that a strategy can exploit the structure,
that an allocation gate improves loss, or that any ticket has positive
expected value. It cannot trigger production, prospective activation,
promotion, or a cohort. It also does not establish "universal cross-lottery
causality" or validity at any other lag — both are explicitly `NOT_TESTED`
in §15.

### 17.3 Weak/null-result boundary

`WEAK_SIGNAL` is not confirmation and cannot be promoted by diagnostics or by
re-running either control differently. `NO_SIGNAL` falsifies the locked
mechanism only at the tested representation, lag, estimator, and null for
that edge — it does not prove the universal absence of cross-lottery
information transfer at every possible lag or representation. A negative
result closes this exact EH02 variant only, per the Owner packet.

### 17.4 Cross-edge boundary

`EDGE_1` (`T539 -> B649`) and `EDGE_2` (`P638Z1 -> B649`) are reported
separately. Concordant labels do not form a joint effect; discordant labels
do not permit choosing the more favorable edge as the program result.

### 17.5 Directionality boundary

Passing `DIRECTIONALITY_CONTROL_PASS` shows the forward direction looks more
extreme than the reverse direction under this exact design; it is not, by
itself, proof of physical/mechanistic causality between two lottery
drawings, which this program has no mechanism to establish.

## 18. Method and project references

- Schreiber, *Measuring Information Transfer* (2000):
  <https://arxiv.org/abs/nlin/0001042> — foundational discrete
  transfer-entropy definition and shuffled-surrogate significance testing
  (catalog source `S04`).
- Java Information Dynamics Toolkit (`jlizier/JIDT`):
  <https://github.com/jlizier/jidt> — cited by the catalog (`S03`) as
  conceptual inspiration only; not used as an implementation dependency
  (project has no JVM/Java runtime dependency and no adopted efficacy
  result from this source per the source registry).
- Holm, *A Simple Sequentially Rejective Multiple Test Procedure* (1979):
  <https://doi.org/10.2307/4615733>
- Phipson and Smyth, *Permutation P-values Should Never Be Zero* (2010):
  <https://gksmyth.github.io/pubs/PermPValuesPreprint.pdf>
- Project rule contracts:
  `src/lottolab/domain/lottery_rules.py::BIG_LOTTO_RULE_CONTRACT`,
  `::DAILY_539_RULE_CONTRACT`, `::POWER_LOTTO_RULE_CONTRACT`.
- EH01/EH10 locked preregistration (shared conventions reused here):
  `docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-preregistration.md`.
- Immediately preceding cross-lottery study (causal-alignment and placebo
  conventions reused here):
  `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1/report.md`.
- EH02 catalog authority:
  `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md`.
- Project research-ledger schema:
  `docs/research/cross-lottery-research-ledger-r1-schema.md`.

## 19. Required return block

```text
EH02_EDGE1_PARAMETER_LOCK_PROPOSAL:
  T539_TO_B649; SUM_SCALAR_REPRESENTATION; LAST_STRICTLY_PRIOR_DRAW;
  SOURCE_LAG_1_TARGET_SELF_ORDER_1; TERTILE_DISCRETIZATION;
  SCHREIBER_PLUGIN_TRANSFER_ENTROPY; DIRECTED_INFORMATION_CLAIM_ONLY

EH02_EDGE2_PARAMETER_LOCK_PROPOSAL:
  P638_ZONE1_TO_B649; SUM_SCALAR_REPRESENTATION; LAST_STRICTLY_PRIOR_DRAW;
  SOURCE_LAG_1_TARGET_SELF_ORDER_1; TERTILE_DISCRETIZATION;
  SCHREIBER_PLUGIN_TRANSFER_ENTROPY; DIRECTED_INFORMATION_CLAIM_ONLY

NULL_SURROGATE_POLICY:
  PRIMARY_GLOBAL_SOURCE_ONLY_PERMUTATION;
  ROBUSTNESS_WITHIN_FOUR_ELIGIBILITY_ORDERED_ERAS;
  MONTE_CARLO_CONDITIONAL_PERMUTATION_APPROXIMATION

PERMUTATION_COUNT:
  999_PER_POLICY_PER_EDGE_PER_DIRECTION

REQUIRED_CONTROLS:
  TIMING_CONTROL_28_DAY_STALE_SOURCE_GATE_OBSERVED_GT_STALE;
  DIRECTIONALITY_CONTROL_REVERSE_TE_GATE_FWD_P_LT_REV_P_AND_REV_P_GT_0.10;
  BOTH_REQUIRED_FOR_SIGNAL_NOT_JUST_FOR_WEAK_SIGNAL

MULTIPLICITY_POLICY:
  HOLM_WITHIN_2_ENDPOINT_PRIMARY_FAMILY_AND_2_ENDPOINT_ROBUSTNESS_FAMILY;
  NO_COMBINED_EDGE1_EDGE2_FAMILY_OR_EFFECT;
  TIMING_AND_DIRECTIONALITY_GATES_NOT_HOLM_MEMBERS

CLASSIFICATION_THRESHOLDS:
  SIGNAL = SAME_EDGE_GLOBAL_P_HOLM_LE_0.05_AND_ERA4_P_HOLM_LE_0.05_AND_BOTH_GATES_PASS;
  WEAK_SIGNAL = NOT_SIGNAL_AND_GLOBAL_P_HOLM_LE_0.10;
  NO_SIGNAL = GLOBAL_P_HOLM_GT_0.10;
  STOP_OR_INCOMPLETE_FAMILY = INVALID_OR_UNIDENTIFIABLE

COMPUTATIONAL_FEASIBILITY:
  FEASIBLE_WITH_STANDARD_LIBRARY_ONLY_NO_NUMPY_SCIPY_REQUIRED;
  O_N_PER_EVALUATION_COUNTING_ESTIMATOR_NOT_ON2_DISTANCE_SWEEP;
  EXPECTED_LOW_SINGLE_DIGIT_SECONDS_TO_A_FEW_MINUTES_TOTAL;
  COST_ESTIMATE_NON_LOAD_BEARING

UNRESOLVED_PRELOCK_ISSUES:
  OWNER_APPROVAL_OF_TWO_EDGE_SINGLE_LAG_DUAL_CONTROL_DESIGN;
  B649_DATASET_AUTHORITY_DISCREPANCY_BETWEEN_TWO_CANDIDATE_CHAINS_UNRESOLVED;
  T539_P638_ZONE1_DATASET_AUTHORITY_NOT_INDEPENDENTLY_REVERIFIED_THIS_TASK;
  PINNED_RUNNER_RUNTIME_COMMIT_AND_TREE;
  SYNTHETIC_FIXTURE_ACCEPTANCE;
  FINAL_CANONICAL_PREREGISTRATION_AND_HASH_NOT_YET_CREATED

EXECUTION: NOT_RUN
SCIENTIFIC_DATA_ANALYSIS: NOT_RUN
FINAL_CLASSIFICATION:
  EH02_PARAMETER_LOCK_PROPOSAL_READY_FOR_OWNER_REVIEW
```

STOP.
