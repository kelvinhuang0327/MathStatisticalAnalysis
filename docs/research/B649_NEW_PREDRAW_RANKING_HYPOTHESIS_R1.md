# B649_NEW_PREDRAW_RANKING_HYPOTHESIS_R1

Outcome-blind structural discriminability of one new pre-draw ranking
hypothesis against the operational incumbent. **No outcome evaluation was run.**

- `TASK_STATUS`: COMPLETE
- `LANE2_OUTCOME_EVALUATION_RUN`: NO
- `OUTCOME_FIELDS_USED`: NO
- `CANDIDATE_HEAD` (candidate freeze commit): `fb7a6e00bfc8a56584b35e6a6a3bed92d3d1f6c4`
- `CANDIDATE_TREE`: `ae86862456155038452f185ec02ad0690c08d624`
- Result artifact: `docs/research/b649-new-predraw-ranking-hypothesis-r1-result.json`

## 1. Candidate identity (frozen before any comparison)

| Field | Value |
| --- | --- |
| `CANDIDATE_NAME` | `B649_MARGINAL_REDUNDANCY_PORTFOLIO_V1` |
| `CANDIDATE_VERSION` | `1.0.0` |
| `CANDIDATE_SOURCE_PATH` | `src/lottolab/research/b649_marginal_redundancy_portfolio.py` |
| `CANDIDATE_SOURCE_SHA256` | `70e11f786fce39a0548680792bf6a94d1176154eac24df7028d5a8f65d205b53` |
| `SUPPORTED_K` | 5, 10, 20 |
| `DETERMINISM_RULE` | `PURE_DETERMINISTIC_NO_RNG`; invariant to stream input order |

### Input authority

Nothing mathematical was invented. The candidate composes two authorities that
already exist on `origin/main`, and modifies neither:

| Role | Authority | Blob at `origin/main` |
| --- | --- | --- |
| Candidate pool | `tools/b649_operational_prediction_loop.py` `STRATEGY_STREAMS` (11 enabled streams) | `7351c269` |
| Base order | `B649_OPERATIONAL_PORTFOLIO_SELECTOR` v1.0.0 | `a3fec31b` |
| Selection rule | `B649_CANDIDATE_SET_LOW_OVERLAP_V1` v1 | `c5025b01` |

The incumbent is called with the production `quality_by_strategy={}` and a
bucket equal to the distinct pool size, so the returned bucket *is* the
incumbent's own complete total order. That order is then handed to the
canonical low-overlap constructor as its `ORIGINAL_RANK` authority.

### Pre-draw features and rank formula

`PRE_DRAW_FEATURES_USED`

1. `MAX_OVERLAP` = `max over s in selected of |numbers(t) & numbers(s)|`
2. `TOTAL_OVERLAP` = `sum over s in selected of |numbers(t) & numbers(s)|`
3. `ORIGINAL_RANK` = index of `t` in the incumbent's full total order

`RANK_FORMULA` — greedy sequential. At each step select the unselected pool
ticket minimizing `(MAX_OVERLAP, TOTAL_OVERLAP, ORIGINAL_RANK)`
lexicographically. This is the frozen `SELECTION_OBJECTIVE` of
`B649_CANDIDATE_SET_LOW_OVERLAP_V1`, unchanged.

`TIE_BREAK_RULE` — `ORIGINAL_RANK`, i.e. the incumbent order
(`-support_count, -summed_quality, ticket ASC`). It is distinct per ticket, so
the induced order is total and no residual tie exists.

Greedy selection does not depend on the budget, so K5, K10 and K20 are nested
prefixes of one total order, matching the incumbent's own nesting. The module
asserts this at runtime rather than assuming it.

### `SUPPORT_COUNT_EQUIVALENT`: NO

The incumbent's key `(-support, -quality, ticket)` is evaluated **pointwise**,
independently per ticket. The candidate's primary key is **context-dependent**:
a ticket's position depends on which tickets were already selected.

This is falsified by construction in
`tests/unit/test_b649_marginal_redundancy_portfolio.py`. The same ticket
`(5, 6, 7, 8, 9, 10)` keeps support count 1, incumbent rank 1 and pool size 5
across two pools, yet its candidate rank moves from 1 to 4. No function of the
incumbent's per-ticket key can produce that, because that key is identical in
both pools.

The empirical run confirms the signal is not a relabelled support count: the
live 11-stream pools are 20-22 distinct tickets of which at most one has
support above 1, so the incumbent's live order is effectively lexicographic,
while the candidate's is driven by number-set redundancy.

## 2. Outcome isolation

`OUTCOME_FIELDS_USED`: **NO**. Three independent invariants, each with a test:

1. The SQL projection is exactly `draw_number, draw_date, main_numbers_json`.
   `special_numbers_json` and every prize, winner and hit column are never
   named, so no such value is ever loaded.
2. `build_pool` raises `PRE_DRAW_CUTOFF_VIOLATION` unless the history is a
   strict prefix ending before the target, so the target's own row cannot
   reach an adapter.
3. Nothing in either module evaluates a ticket. No hit count, prize tier,
   winner label, lift or success rate is computed anywhere.

Prior draws' main numbers are the 11 streams' unavoidable pre-draw input; that
is the same seam the canonical operational replay uses. The target draw's own
main numbers and special number are never read.

The prior replay artifact is reused only through a field whitelist covering
pool, cutoff and incumbent-selection identity. Its scored `baseline` and
`candidate` payloads, and the prior LOO candidate's own selections, are not
read. The loader fails closed if that schema changes.

## 3. Comparability

| Check | Result |
| --- | --- |
| Source | canonical `lottolab.db`, 2,171 BIG_LOTTO draws, 96000001 - 115000089 |
| Eligibility | 200-draw warmup and joint K5/K10/K20 availability, identical to the operational replay |
| Excluded | 200 warmup, 191 with fewer than 20 distinct tickets |
| Comparable targets | 1,780 |
| Rows cross-checked against the prior replay artifact | 5,337 of 5,337 |
| Same `pool_sha256` | 5,337 / 5,337 |
| Same cutoff | 5,337 / 5,337 |
| Same incumbent selection | 5,337 / 5,337 |
| Source invariant during run | yes, verified by content hash before and after |

The cross-check is exact: this harness reproduces the canonical incumbent's
pool hashes and its selected tickets on every overlapping row, so both rankers
are demonstrably ranking the same pool at the same cutoff.

The one extra target versus the prior replay's 1,779 is 115000089, which the
database has gained since. The restricted subset is reported below so the
figures compare directly against the prior candidate's denominators.

## 4. Structural discriminability

Distinct pool size across the 1,780 comparable targets: 20 on 626 draws,
21 on 832, 22 on 322.

| K | Comparable | Same | Different | Disagreement rate | Overlap (min/median/mean) | Order-only | Top-rank change | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 1,780 | 0 | 1,780 | 100.000% | 1 / 2 / 1.96 | 0 | 0.000% | `MEANINGFULLY_DIFFERENT` |
| 10 | 1,780 | 0 | 1,780 | 100.000% | 2 / 5 / 5.09 | 0 | 0.000% | `MEANINGFULLY_DIFFERENT` |
| 20 | 1,780 | 626 | 1,154 | 64.832% | 18 / 19 / 19.18 | 626 | 0.000% | `MEANINGFULLY_DIFFERENT` |

Restricted to targets at or below 115000088 (the prior replay's exact
denominator of 1,779): K5 1,779/1,779 = 100.000%, K10 1,779/1,779 = 100.000%,
K20 1,153/1,779 = 64.812%.

### Why K20 is not 100%, and why it is still meaningfully different

A budget can only disagree when the distinct pool exceeds it. Split by pool
size, K20 behaves as:

| Distinct pool | Surplus over K20 | Draws | Different | Rate |
| --- | --- | --- | --- | --- |
| 20 | 0 | 626 | 0 | 0.000% |
| 21 | 1 | 832 | 832 | 100.000% |
| 22 | 2 | 322 | 322 | 100.000% |

On the 626 draws where the pool holds exactly 20 distinct tickets, both
rankers must play all 20; no ranker could differ. Those draws contribute the
626 order-only differences and nothing else. On the 1,154 draws where any
selection freedom exists, the candidate changes the played set on **every
single one**.

### Descriptive reading

- The candidate replaces about 3.0 of 5 tickets at K5 and about 4.9 of 10 at
  K10, on every comparable draw.
- The top-ranked ticket never changes at any K. This is by construction: with
  an empty selected prefix every overlap is zero, so `ORIGINAL_RANK` decides
  rank 1. Divergence begins at rank 2.
- The mechanism is visible in the live pools. The incumbent's order is
  effectively lexicographic, which makes it select near-duplicates: in one
  sampled target it played both `(1,3,4,5,6,9)` and `(1,3,4,5,6,10)`, which
  share five of six numbers. The candidate declines the second.

This is a different order of magnitude from the prior candidate. `LOO_STABILITY_TIEBREAK_V1`
changed the set on 2.305% of draws at K5, 2.080% at K10 and 0% at K20. This
candidate changes it on 100%, 100%, and on 100% of the draws where change is
structurally possible.

## 5. Disposition

`CANDIDATE_DISPOSITION`: **`ELIGIBLE_FOR_SEPARATE_OOS_FREEZE_REVIEW`**

The candidate demonstrably changes prediction decisions, so an outcome test
would be measuring a real difference rather than noise. Whether those changed
decisions are *better* is not established and was not investigated here.

`LANE2_OUTCOME_EVALUATION_RUN`: NO

## 6. Limitations

- Structural difference is not evidence of merit. Nothing here supports
  promotion, Branch-6 adoption, or any claim about success rate.
- The pre-draw pools are reconstructed from today's canonical dataset by
  strict prefix replay. They are not contemporaneously persisted PRE_DRAW
  forecasts, the same caveat the operational replay carries.
- The 626 zero-freedom draws at K20 cap that budget's achievable
  disagreement rate at 64.832% regardless of the ranking rule.
- The Fable protected-run launcher was unavailable in this environment
  (`scripts/` is absent from the installed skill), so the replay was launched
  directly and received no duplicate-execution protection.
