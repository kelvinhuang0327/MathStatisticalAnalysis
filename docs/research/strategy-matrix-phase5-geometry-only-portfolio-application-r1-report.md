# STRATEGY_MATRIX_PHASE5_GEOMETRY_ONLY_PORTFOLIO_APPLICATION_R1 — report

Status: COMPLETE — implementation task, no new combinatorial evidence
generated | 2026-08-16

Converts the already-established low-overlap geometry finding into a
reusable, caller-controlled portfolio-construction capability. This is an
**application** of an existing mechanism, not a new predictor and not a new
evidence cell: it enumerates nothing at real-lottery scale, reads no
historical draw data, and adds no `docs/research/matrix-native-results/`
sealed cell.

## 0. Identity

```text
TASK_ID:   STRATEGY_MATRIX_PHASE5_GEOMETRY_ONLY_PORTFOLIO_APPLICATION_R1
MODE:      IMPLEMENTATION_FIRST
ROLE:      Strategy Matrix — Portfolio Geometry Application
PREVIOUS DECISION: RETAIN_AS_PORTFOLIO_GEOMETRY_ONLY
CLAIM_CLASSIFICATION (input premise from the Owner packet): GEOMETRY_MECHANISM_SUPPORTED
```

## 1. What this delivers

| # | Component | Path |
|---|---|---|
| 1 | `build_low_overlap_portfolio()` — geometry-only constructor | [`src/lottolab/research/low_overlap_portfolio_constructor.py`](../../src/lottolab/research/low_overlap_portfolio_constructor.py) |
| 2 | Same function, score-plus-geometry mode (`optional_scores` param) | same file |
| 3 | `compute_portfolio_geometry_metrics()` — the 5 GEOMETRY OBJECTIVES, computable on any portfolio | same file |
| 4 | Regression tests (42 tests, A–H plus legality/dedup/delegation/per-lottery) | [`tests/unit/test_low_overlap_portfolio_constructor.py`](../../tests/unit/test_low_overlap_portfolio_constructor.py) |
| 5 | This report | this file |

No existing file was modified. No database was touched.

## 2. Design

One function, matching the Owner packet's own example signature exactly:

```python
build_low_overlap_portfolio(candidates, k, lottery_rules, optional_scores=None)
```

`lottery_rules` is a real `LotteryRuleContract`
(`src/lottolab/domain/lottery_rules.py`) — the same authoritative,
provenance-checked object the rest of the codebase already uses, not a new
config surface. The function reads only `main_number_count`,
`main_number_min`, `main_number_max`, and `main_numbers_unique` from it —
main numbers only; Zone-2/special numbers are out of scope, consistent with
the existing `greedy_min_overlap_constructor` family it extends.

**Mode selection is by `optional_scores`, nothing else:**

- **GEOMETRY_ONLY** (`optional_scores=None`) — pure legal low-overlap
  selection.
  - `candidates=None`: delegates directly to the sealed, unmodified
    `greedy_min_overlap_portfolio(pool_size, draw_size, k)`
    (`src/lottolab/research/greedy_min_overlap_constructor.py`, merged via
    PR #132) — real reuse, proven by an identity check
    (`constructor_module.greedy_min_overlap_portfolio is greedy_min_overlap_portfolio`)
    and a delegation-wiring test, matching the same monkeypatch-stub
    convention the existing T539/P638 Zone-1 wrapper tests already use.
  - `candidates=<list>`: the same min-max-overlap greedy rule, restricted to
    (and lexicographically ordered within) the given candidate pool. This
    is new code — the sealed function only ever enumerates the full legal
    space, it does not accept a candidate list — but it is the same rule,
    generalized to an arbitrary upstream source, per the packet's
    PRIMARY DESIGN PRINCIPLE.
- **SCORE_PLUS_GEOMETRY** (`optional_scores` given, same length as
  `candidates`) — candidate priority is by descending score (ties broken
  lexicographically), but the same min-max-overlap rule still governs which
  candidate is actually picked at each step. A high score alone cannot force
  a pick that collapses the portfolio into near-duplicate tickets — see the
  worked example in test G below. Scores are only ever read via indexing;
  nothing in the function assigns into the caller's `optional_scores` or
  `candidates` containers.

`k` has no default and no internal ladder — every call site supplies it.
Nothing in this module reads `k` from a config, a prior result, or a
benchmark. An illegal candidate, a length mismatch, or a `k` beyond the
number of unique legal candidates is a `ValueError` — exposure is always
exactly `k` tickets or a clear error, never a silently short portfolio.

### Geometry objectives implemented (`compute_portfolio_geometry_metrics`)

| Packet objective | Field |
|---|---|
| pairwise ticket overlap | `max_pairwise_overlap`, `mean_pairwise_overlap`, `overlap_profile` |
| union size | `union_size` |
| duplicate pair exposure | `duplicate_pair_exposure` — count of 2-number sub-combinations recurring in ≥2 tickets |
| duplicate triple exposure | `duplicate_triple_exposure` — same, for 3-number sub-combinations |
| coverage concentration | `coverage_concentration` — population stdev of per-number use counts across the full pool |

Descriptive only — computing these metrics never feeds back into
construction; the constructor's own greedy rule (not this function) is what
governs ticket selection.

## 3. Regression tests

All 42 tests pass (`uv run pytest tests/unit/test_low_overlap_portfolio_constructor.py`, 0.10s). Ruff and `pyright --strict` both clean.

| Test | Representative test name(s) |
|---|---|
| A. exactly K tickets returned | `test_a_returns_exactly_k_tickets(_with_scores)` |
| B. every ticket lottery-legal | `test_b_every_ticket_is_lottery_legal` |
| C. deterministic with fixed input | `test_c_deterministic_across_repeated_calls(_with_scores_too)` |
| D. no duplicate tickets | `test_d_no_duplicate_tickets_in_output` |
| E. geometry-only needs no outcome/future data | `test_e_signature_has_no_outcome_or_draw_parameter`, `test_e_module_imports_no_draw_outcome_or_database_dependency`, `test_e_geometry_only_works_on_synthetic_candidates_unrelated_to_any_draw` |
| F. score-plus-geometry doesn't mutate upstream scores | `test_f_optional_scores_sequence_is_not_mutated`, `test_f_candidates_sequence_is_not_mutated` |
| G. low-overlap ≤ naive top-K on fixed fixtures | `test_g_low_overlap_portfolio_beats_naive_top_k_by_score` |
| H. exposure remains exactly matched | `test_h_exposure_is_exactly_k_never_a_silent_shortfall`, `test_h_k_exceeding_unique_legal_candidates_raises_instead_of_shorting`, `test_h_total_numbers_bet_matches_k_times_draw_size` |

**Test G, concretely** (the "geometry constraint prevents portfolio
collapse" claim, not just asserted but shown): 5 toy candidates, 3 of which
share the sub-pair `(1,2)` and dominate by score. Naive top-3-by-score picks
all 3 of them — `max_pairwise_overlap=2`. `build_low_overlap_portfolio` with
the same scores instead picks the fully disjoint optimum —
`max_pairwise_overlap=0`, `mean_pairwise_overlap=0.0` — strictly better on
both metrics, not merely tied.

Also covered, beyond the lettered list: legality rejection (wrong ticket
length, out-of-range number, duplicate-within-ticket, non-integer),
candidate deduplication, `k=0`, `lottery_rules` type-checking, and `k` as a
free parameter across the packet's own tested ladder `{1,3,5,10,15,20}`
(`test_k_is_a_free_caller_controlled_exposure_parameter`) — the ladder is
used only as a set of *test* values, not hard-coded anywhere in the
constructor itself.

## 4. Per-lottery fixed-K checks (isolated, not pooled)

Each lottery uses its own real `LotteryRuleContract`
(`BIG_LOTTO_RULE_CONTRACT` / `DAILY_539_RULE_CONTRACT` /
`POWER_LOTTO_RULE_CONTRACT`) and a small synthetic candidate pool (60
lexicographic tickets from that lottery's own real pool/draw size — cheap,
not the full `C(pool,draw)` space), `k=5`, both GEOMETRY_ONLY and
SCORE_PLUS_GEOMETRY:

```text
B649_FIXED_K_CHECK   (pool=49, draw=6): PASS — test_b649_fixed_k_check_geometry_only, test_b649_fixed_k_check_score_plus_geometry
T539_FIXED_K_CHECK   (pool=39, draw=5): PASS — test_t539_fixed_k_check_geometry_only, test_t539_fixed_k_check_score_plus_geometry
P638_FIXED_K_CHECK   (pool=38, draw=6, Zone-1 only): PASS — test_p638_zone1_fixed_k_check_geometry_only, test_p638_zone1_fixed_k_check_score_plus_geometry
```

Each check asserts independently: exactly 5 tickets, no duplicates, every
ticket the lottery's own draw size, every number within that lottery's own
pool bounds. No cross-lottery pooling anywhere in these assertions.

## 5. Application validation — regression confirmation against existing sealed artifacts

Per the packet's instruction, this section **cites already-sealed evidence,
re-derives no threshold/K search, and keeps every lottery's numbers
separate.** Source: `docs/research/matrix-native-results/strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-report.md`
(§1), which itself synthesizes three already-sealed, merged,
`EXACT_COMBINATORIAL` (exact-fraction, not simulated) cells:

- `DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1` (PR #132)
- `GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1`
- `GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1`

`Q_ARM_B` there is exact-space `greedy_min_overlap_portfolio` coverage — the
same GEOMETRY_ONLY / `candidates=None` mechanism this task's constructor
delegates to directly, not a different algorithm. RANDOM vs. LOW-OVERLAP
same-K, primary event m=3, kept per-lottery:

**BIG_LOTTO** (pool=49, draw=6)

| k | Q_ARM_B (low-overlap) | Q_RANDOM | Δ | rel. lift |
|---:|---:|---:|---:|---:|
| 1 | 0.01863755 | 0.01863755 | +0.00000000 | +0.0000% |
| 3 | 0.05582682 | 0.05487704 | +0.00094978 | +1.7307% |
| 5 | 0.09290168 | 0.08977829 | +0.00312339 | +3.4790% |
| 10 | 0.18167144 | 0.17149647 | +0.01017497 | +5.9330% |
| 15 | 0.26065632 | 0.24587816 | +0.01477816 | +6.0104% |
| 20 | 0.33536361 | 0.31358200 | +0.02178161 | +6.9461% |

**DAILY_539** (pool=39, draw=5)

| k | Q_ARM_B | Q_RANDOM | Δ | rel. lift |
|---:|---:|---:|---:|---:|
| 1 | 0.01004069 | 0.01004069 | +0.00000000 | +0.0000% |
| 3 | 0.03012208 | 0.02982070 | +0.00030138 | +1.0107% |
| 5 | 0.05020347 | 0.04920556 | +0.00099792 | +2.0281% |
| 10 | 0.09928147 | 0.09599032 | +0.00329115 | +3.4286% |
| 15 | 0.14679630 | 0.14047338 | +0.00632293 | +4.5012% |
| 20 | 0.19349830 | 0.18276794 | +0.01073036 | +5.8710% |

**POWER_LOTTO Zone-1** (pool=38, draw=6, Zone-1 only)

| k | Q_ARM_B | Q_RANDOM | Δ | rel. lift |
|---:|---:|---:|---:|---:|
| 1 | 0.03869806 | 0.03869806 | +0.00000000 | +0.0000% |
| 3 | 0.11565951 | 0.11165955 | +0.00399995 | +3.5823% |
| 5 | 0.19204138 | 0.17908342 | +0.01295797 | +7.2357% |
| 10 | 0.35290206 | 0.32609621 | +0.02680585 | +8.2202% |
| 15 | 0.48961289 | 0.44678160 | +0.04283129 | +9.5866% |
| 20 | 0.61074351 | 0.54585434 | +0.06488917 | +11.8876% |

Low-overlap beats random at every tested `k>1`, independently, in all three
lotteries (`delta_random_b_positive_for_every_tested_k_gt_1: true` per
lottery in the cited source). This is the mechanism
`build_low_overlap_portfolio` generalizes — not re-measured here, cited.

**Caution carried forward, per the packet's own flag:** the *sealed
deterministic Constructor-Frontier* ticket sequence itself was found
unstable at small realized k in prior replication work — meaning "replay
this exact historical ticket list" is not a robust strategy. That is exactly
why this task's deliverable is the *generalized constraint*
(min-max-overlap selection, reusable against any candidate pool and any
`k`), not a wrapper that replays the frontier's own fixed ticket sequence.
`build_low_overlap_portfolio` never reproduces that specific sequence; it
reruns the same rule fresh against whatever candidates and `k` the caller
supplies.

## 6. Claim boundary

**May say:** `LOW_OVERLAP_PORTFOLIO_GEOMETRY_SUPPORTED`.

**May NOT say, and this report does not say:** single-ticket predictive
edge, future-number prediction improved, profitability improved, or payout
EV improved. This module spends no ticket it wasn't asked for — `k` is
always exactly what the caller passes, so a larger `k` is never silently
substituted for a claimed strategy improvement.

## FINAL

```text
TASK_ID: STRATEGY_MATRIX_PHASE5_GEOMETRY_ONLY_PORTFOLIO_APPLICATION_R1
STATUS: COMPLETE

IMPLEMENTED_COMPONENTS:
  - src/lottolab/research/low_overlap_portfolio_constructor.py
      (build_low_overlap_portfolio, compute_portfolio_geometry_metrics,
      PortfolioGeometryMetrics)
  - tests/unit/test_low_overlap_portfolio_constructor.py (42 tests)
  - docs/research/strategy-matrix-phase5-geometry-only-portfolio-application-r1-report.md

LOTTERIES_SUPPORTED: B649, T539, P638 Zone-1

GEOMETRY_ONLY_AVAILABLE: YES
SCORE_PLUS_GEOMETRY_AVAILABLE: YES
CALLER_CONTROLLED_K: YES
EXPOSURE_PRESERVED: YES
FUTURE_DATA_REQUIRED: NO

REGRESSION_TESTS: PASS (42/42)
B649_FIXED_K_CHECK: PASS
T539_FIXED_K_CHECK: PASS
P638_FIXED_K_CHECK: PASS

CLAIM_BOUNDARY: PORTFOLIO_GEOMETRY_ONLY

REPO_MUTATION:
  - 1 new module (src/lottolab/research/low_overlap_portfolio_constructor.py)
  - 1 new test file (tests/unit/test_low_overlap_portfolio_constructor.py)
  - 1 new report (this file)
  - 0 existing files modified

DB_MUTATION: NONE

NEXT_TASK_TRACK: STRATEGY_MATRIX_PHASE5_PORTFOLIO_GEOMETRY
NEXT_TASK_ID: (none selected by this task — application-only, per scope)
```
