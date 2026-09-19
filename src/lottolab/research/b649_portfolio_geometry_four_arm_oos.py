"""Frozen four-arm B649 portfolio-geometry OOS replay, strict paired temporal.

The question is causal, not descriptive: does the operational K-ticket
portfolio lose union success because its tickets overlap each other, and does
removing that redundancy recover the loss without any predictive edge?

Four arms select K tickets from one shared pre-draw candidate pool, so every
difference between them is portfolio geometry and nothing else:

* ``RAW_MAJORITY``   -- ARM_A, the operational incumbent;
* ``SEEDED_RANDOM_K``-- ARM_B, the mechanism-validity control;
* ``KDPP``           -- ARM_C, stochastic diversity optimization;
* ``MIN_OVERLAP``    -- ARM_D, deterministic redundancy minimization.

Protocol, arm identities, seeds, K values, primary metric, outcome evaluator,
replay semantics and the validity hypothesis are frozen before any outcome is
read; the freeze commit precedes outcome evaluation. Only this module writes
its explicitly named result. No live forecast, DB write, scheduler action or
candidate change is performed; the canonical database is opened read-only.

Replay reconstructs causal prefixes from today's canonical dataset. It is not
a contemporaneously persisted PRE_DRAW forecast archive.

Statistical procedure (paired-draw bootstrap, exact paired McNemar, Holm
familywise control) is reused unchanged from the Lane-2 OOS harness donor
``4b55d728a807e851ca87ed484edd5722696c8116``
(``src/lottolab/research/b649_loo_oos_validation.py``); ``load_draws``,
``build_pool``, ``score`` and ``bootstrap_interval`` follow that donor exactly
so this result stays comparable to it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import cast

from tools.b649_operational_prediction_loop import STRATEGY_STREAMS, StrategyStream

from lottolab.application.b649_k_dpp_portfolio_selector import (
    HISTORICAL_CAUSAL_REPLAY_V1,
    HISTORY_FINGERPRINT,
    ArmSelection,
    CausalSourceIdentity,
    select_deterministic_min_overlap,
    select_kdpp,
    select_raw_majority_top_k,
    select_seeded_random_k,
)
from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import evaluate_big_lotto_ticket
from lottolab.infrastructure.b649_operational_portfolio_materializer import (
    BUCKET_SIZES,
    PORTFOLIO_METHOD_ID,
    PORTFOLIO_METHOD_VERSION,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)
from lottolab.research.exact_statistics import (
    binomial_two_sided_exact_p_value,
    holm_bonferroni_adjusted,
)
from lottolab.strategies.adapters.base import BetAdapterError, CausalDrawRow, PortfolioBetAdapter

TASK_ID = "BRANCH2_PORTFOLIO_GEOMETRY_FOUR_ARM_OOS_R1"
BASE_HEAD = "947baf9da42a5656a6e6e9577b33cc5e33213347"
BASE_TREE = "109f6ca34db4363f11b378f2ad3cbeb730e6ce99"
KDPP_PRODUCER_COMMIT = "19f15af7a7424bdfc7e04c49055fc4ca41b59635"
ADAPTER_DONOR_COMMIT = "a329bb2e1edf78001dea057dc88bf608427de986"
HARNESS_DONOR_COMMIT = "4b55d728a807e851ca87ed484edd5722696c8116"

INCUMBENT_ARM = "RAW_MAJORITY"
CANDIDATE_ARMS = ("SEEDED_RANDOM_K", "KDPP", "MIN_OVERLAP")
ARMS = (INCUMBENT_ARM, *CANDIDATE_ARMS)
#: Arm-vs-arm contrasts beyond each candidate against the incumbent.
CROSS_CONTRASTS = (
    ("SEEDED_RANDOM_K", "KDPP"),
    ("SEEDED_RANDOM_K", "MIN_OVERLAP"),
    ("KDPP", "MIN_OVERLAP"),
)

PRIMARY_METRIC = "OFFICIAL_ANY_PRIZE"
#: K10/K20 carry acceptance; K5 is diagnostic only and is outside the
#: familywise primary family, because its geometry headroom and discriminating
#: power are both materially weaker.
PRIMARY_K = (10, 20)
DIAGNOSTIC_K = (5,)
SUPPORTED_K = (5, 10, 20)
#: 3 candidate arms x 2 primary K.
PRIMARY_FAMILY_SIZE = len(CANDIDATE_ARMS) * len(PRIMARY_K)

RECENT_WINDOWS = (750, 300, 50)
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 649
MIN_PAIRED_DRAWS = 30
MIN_DISCORDANT_DRAWS = 10
METRICS = ("official_any_prize", "p_max_hits_ge_3", "p_max_hits_ge_4", "max_hits")

GEOMETRY_VALIDITY_HYPOTHESIS = (
    "At K=10 and K=20, SEEDED_RANDOM_K_CONTROL should improve the primary "
    "union-success metric relative to the operational incumbent if excessive "
    "incumbent overlap is the dominant mechanism identified by the historical "
    "geometry analysis."
)
#: Prior point expectations. REFERENCE ONLY -- never an acceptance threshold.
REFERENCE_EXPECTATION_ONLY = {"10": "+2.7pp", "20": "+6.7pp"}

#: Recorded BEFORE any outcome was scored, from an outcome-free dry run over the
#: last three canonical targets. The live eleven-stream pool yields only 21-22
#: distinct candidate tickets, so at K=20 every arm is forced to take almost the
#: whole pool and the arms nearly coincide (observed mean pairwise overlap
#: 1.147 / 1.079 / 1.147 / 1.068 for A / B / C / D), while at K=10 the arms
#: genuinely diverge (1.511 / 1.222 / 1.067 / 0.667). The K20 reference
#: expectation above was derived from free choice over the whole ticket space,
#: not from this pool, so K20 decision leverage is expected to be weak and a
#: null there is uninformative about geometry. ``forced_selection_draws``
#: measures this directly: draws where candidate_count == K admit exactly one
#: portfolio, so every arm is identical by construction.
PRE_OUTCOME_STRUCTURAL_NOTE = (
    "LIVE_POOL_IS_21_TO_22_DISTINCT_TICKETS; K20_NEARLY_SATURATED_LOW_LEVERAGE; "
    "K10_CARRIES_THE_GEOMETRY_CONTRAST"
)


def encoded(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


@dataclass(frozen=True)
class SourceDraw:
    draw_number: str
    draw_date: str
    main_numbers: Ticket
    special_number: int
    normalized_record_hash: str

    @property
    def key(self) -> tuple[date, int]:
        return date.fromisoformat(self.draw_date), int(self.draw_number)

    def history_row(self) -> CausalDrawRow:
        return CausalDrawRow(self.draw_number, self.draw_date, self.main_numbers)


def load_draws(database: Path) -> tuple[SourceDraw, ...]:
    """Donor-identical read-only canonical load with full integrity guards."""

    paths = LocalDataPaths(data_directory=database.parent, database=database)
    if not verify_schema_read_only(paths):
        raise ValueError("CANONICAL_OUTCOME_SCHEMA_UNAVAILABLE")
    with open_database(paths, read_only=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        rows = connection.execute(
            "SELECT draw_number, draw_date, main_numbers_json, special_numbers_json, "
            "normalized_record_hash FROM draws WHERE lottery_type = ? "
            "ORDER BY draw_date, CAST(draw_number AS INTEGER)",
            (LotteryType.BIG_LOTTO.value,),
        ).fetchall()
    draws: list[SourceDraw] = []
    for number, day, main_json, special_json, record_hash in rows:
        main = cast(list[int], json.loads(str(main_json)))
        special = cast(list[int], json.loads(str(special_json)))
        if (
            len(main) != 6
            or len(set(main)) != 6
            or len(special) != 1
            or any(type(n) is not int or not 1 <= n <= 49 for n in main + special)
            or special[0] in main
        ):
            raise ValueError("INVALID_CANONICAL_OUTCOME")
        draws.append(SourceDraw(str(number), str(day), tuple(main), special[0], str(record_hash)))
    keys = [draw.key for draw in draws]
    if (
        not keys
        or keys != sorted(set(keys))
        or len({draw.draw_number for draw in draws}) != len(draws)
    ):
        raise ValueError("CANONICAL_DRAW_ORDER_OR_DUPLICATE_IDENTITY")
    return tuple(draws)


def build_pool(
    history: tuple[CausalDrawRow, ...],
    target_number: str,
    target_date: str,
    streams: Sequence[StrategyStream] = STRATEGY_STREAMS,
) -> tuple[StrategyCandidate, ...]:
    """Outcome-isolated seam: receives only strict history and target identity."""

    target = date.fromisoformat(target_date), int(target_number)
    keys = [(date.fromisoformat(row.date), int(row.draw)) for row in history]
    if not keys or keys != sorted(set(keys)) or keys[-1] >= target:
        raise ValueError("PRE_DRAW_CUTOFF_VIOLATION")
    pool: list[StrategyCandidate] = []
    for stream in streams:
        if not stream.enabled:
            continue
        adapter = stream.adapter_factory()
        if (adapter.strategy_id, adapter.strategy_version) != (
            stream.strategy_id,
            stream.strategy_version,
        ):
            raise ValueError("BASELINE_STREAM_IDENTITY_MISMATCH")
        if isinstance(adapter, PortfolioBetAdapter):
            tickets = adapter.get_bets(history, LotteryType.BIG_LOTTO)
        else:
            ticket, _ = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
            tickets = (ticket,)
        if len(tickets) != stream.native_ticket_count:
            raise ValueError("NATIVE_CARDINALITY_MISMATCH")
        pool.append(StrategyCandidate(stream.strategy_id, tickets))
    return tuple(pool)


def source_identity(
    history: Sequence[CausalDrawRow], target: SourceDraw, history_fingerprint: str
) -> CausalSourceIdentity:
    cutoff = history[-1]
    return CausalSourceIdentity(
        source_mode=HISTORICAL_CAUSAL_REPLAY_V1,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
        history_cutoff_draw_number=cutoff.draw,
        history_cutoff_date=cutoff.date,
        history_identity_kind=HISTORY_FINGERPRINT,
        history_identity=history_fingerprint,
    )


def arm_selections(
    pool: Sequence[StrategyCandidate], source: CausalSourceIdentity, k: int
) -> dict[str, ArmSelection]:
    """Every arm over one shared candidate pool, same source identity, same K."""

    return {
        "RAW_MAJORITY": select_raw_majority_top_k(pool, source=source, k=k),
        "SEEDED_RANDOM_K": select_seeded_random_k(pool, source=source, k=k),
        "KDPP": select_kdpp(pool, source=source, k=k),
        "MIN_OVERLAP": select_deterministic_min_overlap(pool, source=source, k=k),
    }


def score(tickets: Sequence[Ticket], outcome: SourceDraw, k: int) -> dict[str, object]:
    """Donor-identical canonical official-prize scoring of one K-portfolio."""

    if len(tickets) != k or len(set(tickets)) != k:
        raise ValueError("SAME_K_PAIRING_VIOLATION")
    hits: list[int] = []
    wins = 0
    for ticket in tickets:
        result = evaluate_big_lotto_ticket(
            predicted_main_numbers=ticket,
            predicted_special_number=None,
            winning_main_numbers=outcome.main_numbers,
            winning_special_number=outcome.special_number,
        )
        hits.append(result.zone1_hits)
        wins += result.is_winner
    return {
        "max_hits": max(hits),
        "p_max_hits_ge_3": int(max(hits) >= 3),
        "p_max_hits_ge_4": int(max(hits) >= 4),
        "official_any_prize": int(wins > 0),
        "ticket_hits": hits,
        "winning_ticket_count": wins,
    }


def geometry(tickets: Sequence[Ticket]) -> dict[str, object]:
    """Outcome-free portfolio-redundancy diagnostics for one K-portfolio."""

    overlaps = [len(set(a) & set(b)) for a, b in combinations(tickets, 2)]
    numbers = {n for ticket in tickets for n in ticket}
    legal = all(len(t) == 6 and len(set(t)) == 6 and all(1 <= n <= 49 for n in t) for t in tickets)
    return {
        "mean_pairwise_overlap": sum(overlaps) / len(overlaps) if overlaps else None,
        "max_pairwise_overlap": max(overlaps) if overlaps else None,
        "overlap_distribution": [overlaps.count(i) for i in range(7)],
        "unique_main_number_coverage": len(numbers),
        "duplicate_ticket_count": len(tickets) - len(set(tickets)),
        "all_tickets_legal": legal,
    }


def bootstrap_interval(deltas: Sequence[int], alpha: float = 0.05) -> list[float] | None:
    """Donor-identical paired-draw bootstrap over empirical delta values.

    Exactly the n-of-n draw-level bootstrap distribution, sampled by
    conditional binomials. No ticket is an independent observation, and IID
    draw resampling does not establish independence of overlapping histories.
    """

    if not deltas:
        return None
    import random

    counts = sorted(Counter(deltas).items())
    n = len(deltas)
    rng = random.Random(BOOTSTRAP_SEED)
    samples: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        remaining_n, remaining_count, total = n, n, 0
        for value, count in counts[:-1]:
            taken = rng.binomialvariate(remaining_n, count / remaining_count)
            total += taken * value
            remaining_n -= taken
            remaining_count -= count
        total += remaining_n * counts[-1][0]
        samples.append(total / n)
    samples.sort()
    return [
        samples[int(BOOTSTRAP_REPLICATES * alpha / 2)],
        samples[min(BOOTSTRAP_REPLICATES - 1, int(BOOTSTRAP_REPLICATES * (1 - alpha / 2)))],
    ]


def summarize_pair(
    rows: Sequence[dict[str, object]], left: str, right: str, *, family_alpha: float
) -> dict[str, object]:
    """Paired draw-level comparison of ``right`` against ``left`` (the reference)."""

    n = len(rows)
    result: dict[str, object] = {"paired_draw_count": n, "reference_arm": left, "arm": right}
    for metric in METRICS:
        base = [int(cast(dict[str, dict[str, int]], row["scores"])[left][metric]) for row in rows]
        cand = [int(cast(dict[str, dict[str, int]], row["scores"])[right][metric]) for row in rows]
        deltas = [c - b for b, c in zip(base, cand, strict=True)]
        base_total, cand_total = sum(base), sum(cand)
        result[metric] = {
            "reference_count_or_sum": base_total,
            "arm_count_or_sum": cand_total,
            "reference": base_total / n if n else None,
            "arm": cand_total / n if n else None,
            "absolute_delta": sum(deltas) / n if n else None,
            "relative_lift": sum(deltas) / base_total if base_total else None,
            "paired_delta_counts": dict(sorted(Counter(deltas).items())),
            "paired_bootstrap_95_interval": bootstrap_interval(deltas),
        }
        if metric == "official_any_prize":
            positive, negative = deltas.count(1), deltas.count(-1)
            result["primary_discordant_draw_count"] = positive + negative
            result["primary_positive_discordant"] = positive
            result["primary_negative_discordant"] = negative
            result["primary_exact_p_value"] = (
                binomial_two_sided_exact_p_value(positive + negative, positive, 0.5)
                if positive + negative
                else 1.0
            )
            result["primary_familywise_interval"] = bootstrap_interval(deltas, family_alpha)
    changed = sum(
        1
        for row in rows
        if set(cast(dict[str, tuple[Ticket, ...]], row["tickets"])[left])
        != set(cast(dict[str, tuple[Ticket, ...]], row["tickets"])[right])
    )
    result["ticket_set_changed_draws"] = changed
    result["ticket_set_changed_rate"] = changed / n if n else None
    return result


def arm_verdict(summary: dict[str, object], adjusted_p: float) -> str:
    """Per-arm-per-K advancement classification under the predeclared gates."""

    n = cast(int, summary["paired_draw_count"])
    if n == 0:
        return "INSUFFICIENT_EVIDENCE"
    if cast(int, summary["ticket_set_changed_draws"]) == 0:
        return "NO_LIFT"
    discordant = cast(int, summary["primary_discordant_draw_count"])
    if n < MIN_PAIRED_DRAWS or discordant < MIN_DISCORDANT_DRAWS:
        return "INSUFFICIENT_EVIDENCE"
    bounds = cast(list[float], summary["primary_familywise_interval"])
    if adjusted_p < 0.05 and bounds[0] > 0:
        return "POSITIVE_LIFT_VALIDATED"
    if adjusted_p < 0.05 and bounds[1] < 0:
        return "NEGATIVE_LIFT"
    delta = cast(float, cast(dict[str, object], summary["official_any_prize"])["absolute_delta"])
    return "NO_LIFT" if delta == 0 else "UNSTABLE_OR_INCONCLUSIVE"


def evaluate(draws: Sequence[SourceDraw], *, limit: int | None = None) -> dict[str, object]:
    streams = tuple(s for s in STRATEGY_STREAMS if s.enabled)
    warmup = max(s.adapter_factory().min_history for s in streams)
    history: list[CausalDrawRow] = []
    paired: dict[int, list[dict[str, object]]] = {k: [] for k in SUPPORTED_K}
    excluded: list[dict[str, object]] = []
    deterministic_targets: list[str] = []
    infeasible: Counter[str] = Counter()

    for index, target in enumerate(draws):
        if limit is not None and len(paired[SUPPORTED_K[0]]) >= limit:
            break
        reason: str | None = None
        if len(history) < warmup:
            reason = f"WARMUP_REQUIRES_{warmup}_PRIOR_DRAWS"
        else:
            pool: tuple[StrategyCandidate, ...] = ()
            try:
                pool = build_pool(tuple(history), target.draw_number, target.draw_date, streams)
            except BetAdapterError as exc:
                reason = f"STREAM_UNAVAILABLE:{exc}"
            # Unexpected exceptions abort; never conceal broken replay as an exclusion.
            if reason is None:
                distinct = {tuple(sorted(t)) for s in pool for t in s.tickets}
                if len(distinct) < max(SUPPORTED_K):
                    reason = "INCUMBENT_JOINT_K5_K10_K20_UNAVAILABLE_LT20_DISTINCT_TICKETS"
                else:
                    history_fingerprint = digest([asdict(row) for row in history])
                    identity = source_identity(history, target, history_fingerprint)
                    incumbent_buckets = build_portfolio(pool, {}, bucket_sizes=BUCKET_SIZES)
                    verify_here = index in (warmup, len(draws) - 1)
                    if verify_here:
                        if pool != build_pool(
                            tuple(history), target.draw_number, target.draw_date, streams
                        ):
                            raise ValueError("NONDETERMINISTIC_STREAM_REPRODUCTION")
                        deterministic_targets.append(target.draw_number)
                    pool_hash = digest([(s.strategy_id, s.tickets) for s in pool])
                    for k in SUPPORTED_K:
                        selections = arm_selections(pool, identity, k)
                        statuses = {a: s.feasibility_status for a, s in selections.items()}
                        if any(v != "FEASIBLE" for v in statuses.values()):
                            for a, v in statuses.items():
                                if v != "FEASIBLE":
                                    infeasible[f"{a}:{v}"] += 1
                            reason = f"ARM_INFEASIBLE_K{k}"
                            break
                        tickets = {a: s.tickets for a, s in selections.items()}
                        # ARM_A must equal the live materializer's own bucket.
                        if list(tickets["RAW_MAJORITY"]) != list(incumbent_buckets[k]):
                            raise ValueError("INCUMBENT_ARM_NOT_OPERATIONAL_SELECTOR")
                        if verify_here:
                            repeat = arm_selections(pool, identity, k)
                            if {a: s.tickets for a, s in repeat.items()} != tickets:
                                raise ValueError("NONDETERMINISTIC_ARM_SELECTION")
                        # All four complete selections are sealed before outcomes.
                        paired[k].append(
                            {
                                "target_draw": target.draw_number,
                                "target_date": target.draw_date,
                                "cutoff_draw": history[-1].draw,
                                "cutoff_date": history[-1].date,
                                "history_count": len(history),
                                "history_sha256": history_fingerprint,
                                "pool_sha256": pool_hash,
                                "candidate_count": selections["RAW_MAJORITY"].candidate_count,
                                "k": k,
                                "tickets": tickets,
                                "portfolio_sha256": {
                                    a: s.portfolio_sha256 for a, s in selections.items()
                                },
                                "seeds": {
                                    a: (None if s.seed is None else str(s.seed))
                                    for a, s in selections.items()
                                },
                                "geometry": {a: geometry(t) for a, t in tickets.items()},
                                "scores": {a: score(t, target, k) for a, t in tickets.items()},
                            }
                        )
                    if reason is not None:
                        for k in SUPPORTED_K:
                            if paired[k] and paired[k][-1]["target_draw"] == target.draw_number:
                                paired[k].pop()
        if reason is not None:
            excluded.append(
                {
                    "target_draw": target.draw_number,
                    "target_date": target.draw_date,
                    "reason": reason,
                }
            )
        history.append(target.history_row())
        if (index + 1) % 100 == 0:
            print(
                f"processed {index + 1}/{len(draws)}; paired={len(paired[5])}",
                file=sys.stderr,
                flush=True,
            )

    family_alpha = 0.05 / PRIMARY_FAMILY_SIZE
    # Holm over the primary family only: 3 candidate arms x K10/K20.
    family_keys = [(arm, k) for k in PRIMARY_K for arm in CANDIDATE_ARMS]
    family_summaries = {
        (arm, k): summarize_pair(paired[k], INCUMBENT_ARM, arm, family_alpha=family_alpha)
        for arm, k in family_keys
    }
    adjusted = holm_bonferroni_adjusted(
        [cast(float, family_summaries[key]["primary_exact_p_value"]) for key in family_keys]
    )
    adjusted_by_key = dict(zip(family_keys, adjusted, strict=True))

    by_k: dict[str, object] = {}
    for k in SUPPORTED_K:
        rows = paired[k]
        vs_incumbent: dict[str, object] = {}
        for arm in CANDIDATE_ARMS:
            summary = family_summaries.get((arm, k)) or summarize_pair(
                rows, INCUMBENT_ARM, arm, family_alpha=family_alpha
            )
            p = adjusted_by_key.get((arm, k))
            summary["primary_holm_adjusted_p_value"] = p
            summary["in_primary_family"] = k in PRIMARY_K
            summary["verdict"] = (
                arm_verdict(summary, p)
                if p is not None
                else "DIAGNOSTIC_ONLY_NOT_IN_PRIMARY_FAMILY"
            )
            vs_incumbent[arm] = summary
        by_k[str(k)] = {
            "role": "PRIMARY" if k in PRIMARY_K else "DIAGNOSTIC_ONLY",
            "valid_paired_draws": len(rows),
            "mean_candidate_pool_size": (
                sum(cast(int, r["candidate_count"]) for r in rows) / len(rows) if rows else None
            ),
            "forced_selection_draws": sum(1 for r in rows if cast(int, r["candidate_count"]) == k),
            "coverage": len(rows) / len(draws) if draws else None,
            "arm_absolute": {
                arm: {
                    metric: sum(
                        int(cast(dict[str, dict[str, int]], r["scores"])[arm][metric]) for r in rows
                    )
                    / len(rows)
                    if rows
                    else None
                    for metric in METRICS
                }
                for arm in ARMS
            },
            "arm_geometry": {
                arm: {
                    "mean_pairwise_overlap": sum(
                        cast(dict[str, dict[str, float]], r["geometry"])[arm][
                            "mean_pairwise_overlap"
                        ]
                        for r in rows
                    )
                    / len(rows)
                    if rows
                    else None,
                    "mean_unique_main_number_coverage": sum(
                        cast(dict[str, dict[str, int]], r["geometry"])[arm][
                            "unique_main_number_coverage"
                        ]
                        for r in rows
                    )
                    / len(rows)
                    if rows
                    else None,
                    "duplicate_ticket_draws": sum(
                        1
                        for r in rows
                        if cast(dict[str, dict[str, int]], r["geometry"])[arm][
                            "duplicate_ticket_count"
                        ]
                    ),
                    "all_tickets_legal": all(
                        cast(dict[str, dict[str, bool]], r["geometry"])[arm]["all_tickets_legal"]
                        for r in rows
                    ),
                    "overlap_distribution": [
                        sum(
                            cast(dict[str, dict[str, list[int]]], r["geometry"])[arm][
                                "overlap_distribution"
                            ][i]
                            for r in rows
                        )
                        for i in range(7)
                    ],
                }
                for arm in ARMS
            },
            "vs_incumbent": vs_incumbent,
            "cross_contrasts": {
                f"{a}_vs_{b}": summarize_pair(rows, a, b, family_alpha=family_alpha)
                for a, b in CROSS_CONTRASTS
            },
            "recent_stability": {
                str(window): {
                    arm: summarize_pair(
                        [
                            r
                            for r in rows
                            if r["target_draw"] in {d.draw_number for d in draws[-window:]}
                        ],
                        INCUMBENT_ARM,
                        arm,
                        family_alpha=family_alpha,
                    )
                    for arm in CANDIDATE_ARMS
                }
                for window in RECENT_WINDOWS
            },
            "paired_draws": rows,
        }

    random_k10 = cast(
        dict[str, object],
        cast(dict[str, object], cast(dict[str, object], by_k["10"])["vs_incumbent"])[
            "SEEDED_RANDOM_K"
        ],
    )
    random_k20 = cast(
        dict[str, object],
        cast(dict[str, object], cast(dict[str, object], by_k["20"])["vs_incumbent"])[
            "SEEDED_RANDOM_K"
        ],
    )
    deltas = [
        cast(float, cast(dict[str, object], s["official_any_prize"])["absolute_delta"])
        for s in (random_k10, random_k20)
    ]
    geometry_status = (
        "SUPPORTED_DIRECTIONALLY"
        if all(d > 0 for d in deltas)
        else "REFUTED_OR_IMPLEMENTATION_INVALID"
        if all(d <= 0 for d in deltas)
        else "MIXED_DIRECTION"
    )

    return {
        "task": TASK_ID,
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "authorities": {
            "kdpp_producer_commit": KDPP_PRODUCER_COMMIT,
            "adapter_donor_commit": ADAPTER_DONOR_COMMIT,
            "oos_harness_donor_commit": HARNESS_DONOR_COMMIT,
        },
        "incumbent_identity": {
            "arm": INCUMBENT_ARM,
            "method": PORTFOLIO_METHOD_ID,
            "version": PORTFOLIO_METHOD_VERSION,
            "quality_by_strategy": {},
            "joint_budgets": BUCKET_SIZES,
            "equivalence": "ARM_A_EQUALS_BUILD_PORTFOLIO_BUCKET_ASSERTED_EVERY_DRAW_AND_K",
        },
        "arms": ARMS,
        "primary_success_metric": PRIMARY_METRIC,
        "primary_k": PRIMARY_K,
        "diagnostic_k": DIAGNOSTIC_K,
        "geometry_validity_hypothesis": GEOMETRY_VALIDITY_HYPOTHESIS,
        "reference_expectation_only": REFERENCE_EXPECTATION_ONLY,
        "geometry_validity_status": geometry_status,
        "pre_outcome_structural_note": PRE_OUTCOME_STRUCTURAL_NOTE,
        "protocol": {
            "warmup_prior_draws": warmup,
            "eligibility": "ALL_ELEVEN_STREAMS_AND_INCUMBENT_JOINT_K5_K10_K20_AVAILABLE",
            "primary_window": "FULL",
            "recent_windows_in_canonical_draws": RECENT_WINDOWS,
            "recent_windows_are_independent_confirmation": False,
            "bootstrap": "PAIRED_DRAW_IID_MULTINOMIAL_PERCENTILE",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "familywise_control": "HOLM_EXACT_MCNEMAR_OVER_3_ARMS_X_K10_K20",
            "primary_family_size": PRIMARY_FAMILY_SIZE,
            "familywise_interval_alpha": family_alpha,
            "min_paired_draws": MIN_PAIRED_DRAWS,
            "min_primary_discordant_draws": MIN_DISCORDANT_DRAWS,
            "serial_dependence": "IID_INTERVALS_DO_NOT_ESTABLISH_TEMPORAL_INDEPENDENCE",
            "history_caveat": "CURRENT_CANONICAL_DATA_RECONSTRUCTED_PREFIX_NOT_VINTAGE_ARCHIVE",
            "geometry_ceiling": "NO_Q_SIDON_OR_DIVERSIFICATION_TABLE_USED_AS_BOUND_OR_GATE",
        },
        "streams": [
            {
                "strategy_id": s.strategy_id,
                "version": s.strategy_version,
                "native_ticket_count": s.native_ticket_count,
            }
            for s in streams
        ],
        "source_draw_count": len(draws),
        "source_logical_sha256": digest([asdict(d) for d in draws]),
        "source_first_draw": draws[0].draw_number,
        "source_last_draw": draws[-1].draw_number,
        "by_k": by_k,
        "exclusion_reasons": dict(Counter(str(r["reason"]) for r in excluded)),
        "excluded_targets": excluded,
        "arm_infeasibility_counts": dict(infeasible),
        "deterministic_targets": deterministic_targets,
        "leakage_status": "PASS_STRICT_PREFIX_AND_OUTCOME_ISOLATED_SELECTION",
        "outcome_tuning": "NONE",
        "production_mutation": "NONE",
        "ready_for_branch6_adoption": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("RESULT_ALREADY_EXISTS")
    draws = load_draws(args.database)
    result = evaluate(draws, limit=args.limit)
    if digest([asdict(d) for d in load_draws(args.database)]) != result["source_logical_sha256"]:
        raise ValueError("CANONICAL_SOURCE_MUTATED_DURING_REPLAY")
    result["source_database"] = str(args.database)
    result["evaluation_module_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("xb") as handle:
        handle.write(encoded(result))
    print(result["geometry_validity_status"])


if __name__ == "__main__":
    main()
