# REGIME_CHANGE_POINT_CUSUM_B649_V1 — locked preregistration

Status: LOCKED before any data was loaded ｜ 2026-08-14 ｜ Strategy Matrix Phase 1

## 0. Identity (explicit separation from legacy H07/H19)

```text
HYPOTHESIS_FAMILY_ID:      REGIME_CHANGE_POINT
MATRIX_VARIANT_ID:         REGIME_CHANGE_POINT_CUSUM_B649_V1
SOURCE_TYPE:                STRATEGY_MATRIX_NATIVE
RELATED_LEGACY_EVIDENCE:   H07_H19_CHANGE_POINT__BIG_LOTTO (ledger cell)
RELATED_LEGACY_EVIDENCE_GRADE: REPORTED_UNVERIFIED  (unchanged by this task)
```

This experiment's detector, trim rule, split-point search, null-calibration
method, and classification thresholds were designed from scratch in this
task (see the selection document,
`docs/research/strategy-matrix-phase1-b649-mechanism-selection-r1.md`).
None of it was derived from, or verified to match, whatever exact
detector/threshold/endpoint the legacy `H07/H19` cell used. **This is not a
rerun of H07/H19.** It shares only a research question (does BIG_LOTTO
exhibit a regime change?) and a `mechanism_family`. The ledger cell this
task produces must never be written under a `H07_H19*` identity, and the
legacy cell's own grade (`REPORTED_UNVERIFIED`) is not touched or upgraded
by anything in this document.

*(This identity separation itself is a fix made before any data was
touched — an earlier draft of the selection document loosely wrote
"hypothesis family H07_H19," which would have conflated the two. Corrected
here, not after seeing a result.)*

## 1. Scientific claim

BIG_LOTTO's draw-generating process is a single stationary process
throughout its Phase -1-verified eligible history (2007-03-09 to
2026-07-31, 2,138 contamination-excluded draws), rather than exhibiting an
unannounced structural break at some point.

## 2. Statistics (exact definitions)

Let `S_1, ..., S_n` be the chronologically ordered per-draw sum-of-six
values (`n = 2138`). Let `mu = 150` be the exact null mean and
`sigma_sq = finite_population_sum_variance(49, 6) = 1075` the exact null
per-draw variance (both already implemented and unit-tested in
`exact_statistics.py`).

**Primary statistic — global CUSUM.** Define the cumulative sum path
`C_t = sum_{i=1}^{t} (S_i - mu)` for `t = 1..n`. The test statistic is
`T_global = max_{t in TRIM} |C_t|`, where `TRIM` is the set of candidate
split points with at least 15% of `n` draws on both sides (a disclosed,
fixed trimming rule against degenerate edge splits — `t` in
`[round(0.15n), round(0.85n)]` — chosen once, here, not tuned after seeing
a result).

**Secondary statistic family — per-number CUSUM (diagnostic only).** For
each main-ball number `k` in `1..49`, let `I_{k,i} = 1` if `k` was drawn at
position `i` else `0`, null mean `p = 6/49`. Define
`C_{k,t} = sum_{i=1}^t (I_{k,i} - p)`, statistic
`T_k = max_{t in TRIM} |C_{k,t}|`. 49 statistics, Holm-corrected against
their own null-replay distributions (§4). This family answers a related
but distinct question — did any *individual* number's rate break, even if
the aggregate did not — and is reported as diagnostic evidence only. **It
does not drive the primary classification (§5).** This precedence was
undefined in the draft selection document and is resolved here, before any
data was loaded: an experiment with two candidate primary statistics and no
stated precedence would let either one be picked after the fact depending
on which looked more interesting, which is exactly what preregistration
exists to prevent.

**Chronological stability diagnostic (descriptive only).** Split the
eligible history into 4 equal contiguous blocks (a disclosed, deliberately
different round number from Phase -1's 8-era choice, so this is legibly a
new, independent check, not a relabeling of that one). For each block,
report its mean sum-of-six and the asymptotic-normal z/p-value of that
block's mean against the exact global null (`normal_two_sided_p_value`,
already implemented), Holm-corrected across the 4 blocks. This answers
"does any evidence concentrate in one narrow slice of history" and is
required output per the Owner's task packet, but is explicitly **not**
part of the primary classification rule (§5) — it is context for reading
the result, not a second vote on it.

## 3. Why no train/calibrate/evaluate split

Unlike Phase 0's H04-conditional design, this is not a forward-prediction
claim — it is a retrospective test of whether the *fixed historical
sequence itself* came from one stationary process or from ≥2 regimes
separated by an unknown break. That question is answered using the whole
sequence, by construction (a change-point search needs to see the whole
timeline to search over candidate break locations); there is no "held-out
future" to leak into, because nothing here claims to predict any specific
future draw. The methodological risk in a design like this is not causal
leakage in the Phase-0 sense, but *post-hoc statistic/threshold selection*
— which is exactly what locking the statistic, trim rule, simulation count,
and classification thresholds before loading any data (this document)
exists to close off.

## 4. Null calibration

100 synthetic null chains via `generate_null_draw_chain` at
`BIG_LOTTO_RULE_CONTRACT`, `draw_count=2138`, seeds `0..99` (identical
mechanism to Phase 0). For each synthetic chain, compute `T_global` and all
49 `T_k` the identical way as for the real chain. This yields one empirical
null distribution for `T_global` and 49 empirical null distributions (one
per number) for the `T_k` family, each backed by 100 replicates.

## 5. Primary classification rule (frozen, deterministic)

Percentile of `T_global` = fraction of the 100 null replicates whose
`T_global` is `<=` the real chain's `T_global`. **Direction note, stated
now and only now:** a genuine regime break produces a *larger* `T_global`
than chance, so a *high* percentile (near 1.0) is the unusual direction
here — the opposite of Phase 0's Brier-delta convention, where low was
unusual. Stating this now, before data, is specifically so the direction
cannot be silently chosen to match whatever the real result turns out to
be.

| Condition | `descriptive_classification` |
|---|---|
| percentile >= 0.95 | `LIKELY_REGIME_CHANGE` |
| 0.75 <= percentile < 0.95 | `POSSIBLE_REGIME_CHANGE` |
| percentile < 0.75 | `NO_EVIDENCE_OF_REGIME_CHANGE` |

**Result mapping** (per Owner packet): `NO_EVIDENCE_OF_REGIME_CHANGE` ->
`NO_SIGNAL` path (seal, return to Matrix selection).
`POSSIBLE_REGIME_CHANGE` or `LIKELY_REGIME_CHANGE` -> `PROMISING` path
(return only `REPLICATION_CANDIDATE: YES`; no auto-expansion).

## 6. Scope boundary

`REGIME_DETECTION`: in scope. `ALLOCATION_EXPOSURE` / any exposure-sizing
action: out of scope — a positive result here answers "does a regime
change exist," never "what to do about it." T539: not run. P638: not run.
Cross-lottery replication: not run. No production, cohort, or prospective
work follows from any outcome of this task.

## 7. No-rescue commitment

If `NO_EVIDENCE_OF_REGIME_CHANGE`: record it and stop. No new trim
fraction, split-point rule, block count, statistic, or threshold for this
`MATRIX_VARIANT_ID`. A different design is a new variant ID under a new
generation, preregistered before touching data, exactly as this document
was.

## 8. Preregistration hash

Computed over the canonical JSON of every locked parameter in §2, §4, §5
(statistic definitions' numeric constants, trim fraction, block count,
simulation count, seed range, classification thresholds) — recorded in
`docs/research/regime-changepoint-cusum-b649-v1-preregistration-hash.json`
by `tools/hash_preregistration.py`, generated together with this document
and never regenerated after any result exists.
