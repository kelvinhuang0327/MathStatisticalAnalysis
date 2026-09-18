"""Frozen LOO vs current operational portfolio, strict paired temporal replay.

The principal metric and protocol below were resolved before outcome scoring.
Only this research module writes its explicitly named result; no live forecasts,
DB updates, scheduler actions or candidate changes are performed. Historical
prefix replay is reconstructed from today's canonical dataset, not represented
as a contemporaneously persisted PRE_DRAW forecast.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import cast

from tools.b649_operational_prediction_loop import STRATEGY_STREAMS, StrategyStream

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
from lottolab.research.b649_loo_stability_tiebreak import (
    BUDGETS,
    METHOD_ID,
    build_loo_stability_tiebreak,
)
from lottolab.research.exact_statistics import (
    binomial_two_sided_exact_p_value,
    holm_bonferroni_adjusted,
)
from lottolab.strategies.adapters.base import BetAdapterError, CausalDrawRow, PortfolioBetAdapter

CANDIDATE_HEAD = "fd5cabd8be8d8db564c51efdf2e3d56575a1cea3"
CANDIDATE_TREE = "903345ea425bb39bb49ae167caf6d855473ce7d2"
CANONICAL_HEAD = "bc9d5b4dac571bf361cd82c25213513ecbf191d1"
CANONICAL_TREE = "1759aa35a681599f7452170299bf4bf76240a3db"
PRIMARY_METRIC = "OFFICIAL_ANY_PRIZE"
SUPPORTED_K = (5, 10, 20)
RECENT_WINDOWS = (750, 300, 50)
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 649
MIN_PAIRED_DRAWS = 30
MIN_DISCORDANT_DRAWS = 10
FROZEN_PATHS = (
    "src/lottolab/research/b649_loo_stability_tiebreak.py",
    "src/lottolab/research/b649_rank_stability.py",
)
METRICS = ("official_any_prize", "p_max_hits_ge_3", "p_max_hits_ge_4", "max_hits")


def encoded(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def verify_authority(root: Path) -> dict[str, str]:
    def git(*argv: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(root), *argv])

    if git("rev-parse", CANDIDATE_HEAD + "^{tree}").decode().strip() != CANDIDATE_TREE:
        raise ValueError("UPSTREAM_AUTHORITY_NOT_READY")
    git("merge-base", "--is-ancestor", CANONICAL_HEAD, "HEAD")
    git("merge-base", "--is-ancestor", CANDIDATE_HEAD, "HEAD")
    # Every load-bearing source, including stream dependencies, is frozen.
    changed = git("diff", CANDIDATE_HEAD, "--name-only", "--", "src", "tools").decode().splitlines()
    allowed = "src/lottolab/research/b649_loo_oos_validation.py"
    if any(path != allowed for path in changed):
        raise ValueError("FROZEN_REPLAY_SOURCE_CHANGED")
    hashes: dict[str, str] = {}
    for relative in FROZEN_PATHS:
        expected = git("show", f"{CANDIDATE_HEAD}:{relative}")
        if (root / relative).read_bytes() != expected:
            raise ValueError("FROZEN_CANDIDATE_BYTES_CHANGED")
        hashes[relative] = hashlib.sha256(expected).hexdigest()
    if BUCKET_SIZES != SUPPORTED_K:
        raise ValueError("BASELINE_BUDGET_AUTHORITY_CHANGED")
    return hashes


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


def paired_tickets(
    pool: Sequence[StrategyCandidate],
) -> dict[int, tuple[tuple[Ticket, ...], tuple[Ticket, ...]]]:
    # Preserve the actual incumbent's joint availability, not per-K extrapolation.
    baseline = build_portfolio(pool, {}, bucket_sizes=SUPPORTED_K)
    candidate = build_loo_stability_tiebreak(pool)
    repeated = build_loo_stability_tiebreak(tuple(reversed(pool)))
    if repeated != candidate or baseline != build_portfolio(pool, {}, bucket_sizes=SUPPORTED_K):
        raise ValueError("NONDETERMINISTIC_FROZEN_RANKING")
    candidate_by_k = {result.budget: result.tickets for result in candidate.budgets}
    pairs: dict[int, tuple[tuple[Ticket, ...], tuple[Ticket, ...]]] = {}
    for k in SUPPORTED_K:
        selected = candidate_by_k[k]
        if selected is None or len(selected) != k or len(baseline[k]) != k:
            raise ValueError("SAME_K_PAIRING_VIOLATION")
        pairs[k] = tuple(baseline[k]), selected
    return pairs


def score(tickets: Sequence[Ticket], outcome: SourceDraw, k: int) -> dict[str, object]:
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


def bootstrap_interval(deltas: Sequence[int], alpha: float = 0.05) -> list[float] | None:
    """Paired draw bootstrap, multinomial counts of the empirical delta values.

    This is exactly the n-of-n draw-level bootstrap distribution, sampled by
    conditional binomials for speed. No ticket is an independent observation.
    IID draw resampling does not establish independence of overlapping histories.
    """
    if not deltas:
        return None
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


def summarize(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    n = len(rows)
    result: dict[str, object] = {"paired_draw_count": n}
    for metric in METRICS:
        baseline = [int(cast(dict[str, int], row["baseline"])[metric]) for row in rows]
        candidate = [int(cast(dict[str, int], row["candidate"])[metric]) for row in rows]
        deltas = [c - b for b, c in zip(baseline, candidate, strict=True)]
        base_total, candidate_total = sum(baseline), sum(candidate)
        result[metric] = {
            "baseline_count_or_sum": base_total,
            "candidate_count_or_sum": candidate_total,
            "baseline": base_total / n if n else None,
            "candidate": candidate_total / n if n else None,
            "absolute_delta": sum(deltas) / n if n else None,
            "relative_lift": sum(deltas) / base_total if base_total else None,
            "paired_delta_counts": dict(sorted(Counter(deltas).items())),
            "paired_bootstrap_95_interval": bootstrap_interval(deltas),
        }
        if metric == "official_any_prize":
            positive = deltas.count(1)
            negative = deltas.count(-1)
            result["primary_discordant_draw_count"] = positive + negative
            result["primary_exact_p_value"] = (
                binomial_two_sided_exact_p_value(positive + negative, positive, 0.5)
                if positive + negative
                else 1.0
            )
            result["primary_familywise_interval"] = bootstrap_interval(deltas, 0.05 / 3)
    for side in ("baseline", "candidate"):
        distribution = Counter(
            hit for row in rows for hit in cast(dict[str, list[int]], row[side])["ticket_hits"]
        )
        result[f"{side}_ticket_hit_distribution"] = [distribution[i] for i in range(7)]
    return result


def verdict(summaries: Sequence[dict[str, object]], *, identical_tickets: bool) -> str:
    if not summaries or any(int(cast(int, s["paired_draw_count"])) == 0 for s in summaries):
        return "INSUFFICIENT_EVIDENCE"
    if identical_tickets:
        return "NO_LIFT"
    if all(
        cast(int, s["primary_discordant_draw_count"]) < MIN_DISCORDANT_DRAWS
        or cast(int, s["paired_draw_count"]) < MIN_PAIRED_DRAWS
        for s in summaries
    ):
        return "INSUFFICIENT_EVIDENCE"
    adjusted = holm_bonferroni_adjusted(
        [cast(float, s["primary_exact_p_value"]) for s in summaries]
    )
    directions: list[int] = []
    for summary, p in zip(summaries, adjusted, strict=True):
        bounds = cast(list[float], summary["primary_familywise_interval"])
        adequate = (
            cast(int, summary["paired_draw_count"]) >= MIN_PAIRED_DRAWS
            and cast(int, summary["primary_discordant_draw_count"]) >= MIN_DISCORDANT_DRAWS
        )
        directions.append(
            1
            if adequate and p < 0.05 and bounds[0] > 0
            else -1
            if adequate and p < 0.05 and bounds[1] < 0
            else 0
        )
    if 1 in directions and -1 not in directions:
        return "POSITIVE_LIFT_VALIDATED"
    if -1 in directions and 1 not in directions:
        return "NEGATIVE_LIFT"
    return "UNSTABLE_OR_INCONCLUSIVE"


def evaluate(draws: Sequence[SourceDraw]) -> dict[str, object]:
    streams = tuple(s for s in STRATEGY_STREAMS if s.enabled)
    warmup = max(s.adapter_factory().min_history for s in streams)
    history: list[CausalDrawRow] = []
    paired: dict[int, list[dict[str, object]]] = {k: [] for k in SUPPORTED_K}
    excluded: list[dict[str, object]] = []
    deterministic_stream_targets: list[str] = []
    for index, target in enumerate(draws):
        reason: str | None = None
        if len(history) < warmup:
            reason = "WARMUP_REQUIRES_200_PRIOR_DRAWS"
        else:
            pool: tuple[StrategyCandidate, ...] = ()
            try:
                pool = build_pool(tuple(history), target.draw_number, target.draw_date, streams)
            except BetAdapterError as exc:
                reason = f"STREAM_UNAVAILABLE:{exc}"
            # Unexpected exceptions abort; never conceal broken replay as an exclusion.
            if reason is None:
                if index in (warmup, len(draws) - 1):
                    if pool != build_pool(
                        tuple(history), target.draw_number, target.draw_date, streams
                    ):
                        raise ValueError("NONDETERMINISTIC_STREAM_REPRODUCTION")
                    deterministic_stream_targets.append(target.draw_number)
                distinct = {tuple(sorted(t)) for s in pool for t in s.tickets}
                if len(distinct) < max(SUPPORTED_K):
                    reason = "INCUMBENT_JOINT_K5_K10_K20_UNAVAILABLE_LT20_DISTINCT_TICKETS"
                else:
                    pairs = paired_tickets(pool)
                    # Both complete ticket selections are sealed before joining outcome.
                    pool_hash = digest([(s.strategy_id, s.tickets) for s in pool])
                    history_hash = digest([asdict(row) for row in history])
                    for k, (baseline, candidate) in pairs.items():
                        paired[k].append(
                            {
                                "target_draw": target.draw_number,
                                "target_date": target.draw_date,
                                "cutoff_draw": history[-1].draw,
                                "cutoff_date": history[-1].date,
                                "history_count": len(history),
                                "history_sha256": history_hash,
                                "pool_sha256": pool_hash,
                                "k": k,
                                "baseline_tickets": baseline,
                                "candidate_tickets": candidate,
                                "selection_sha256": digest([baseline, candidate]),
                                "baseline": score(baseline, target, k),
                                "candidate": score(candidate, target, k),
                            }
                        )
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
            print(f"processed {index + 1}/{len(draws)}; paired={len(paired[5])}", file=sys.stderr)
    summaries = [summarize(paired[k]) for k in SUPPORTED_K]
    adjusted = holm_bonferroni_adjusted(
        [cast(float, s["primary_exact_p_value"]) for s in summaries]
    )
    by_k: dict[str, object] = {}
    for k, summary, adjusted_p in zip(SUPPORTED_K, summaries, adjusted, strict=True):
        summary["primary_holm_adjusted_p_value"] = adjusted_p
        views = {
            str(window): summarize(
                [
                    r
                    for r in paired[k]
                    if r["target_draw"] in {d.draw_number for d in draws[-window:]}
                ]
            )
            for window in RECENT_WINDOWS
        }
        by_k[str(k)] = {
            "baseline_identity": {
                "method": PORTFOLIO_METHOD_ID,
                "version": PORTFOLIO_METHOD_VERSION,
                "quality_by_strategy": {},
                "joint_budgets": SUPPORTED_K,
            },
            "valid_paired_draws": len(paired[k]),
            "excluded_draws": len(excluded),
            "coverage": len(paired[k]) / len(draws),
            "eligible_post_warmup_coverage": len(paired[k]) / (len(draws) - warmup)
            if len(draws) > warmup
            else None,
            "full_history": summary,
            "recent_stability": views,
            "paired_draws": paired[k],
        }
    identical = all(
        set(cast(tuple[Ticket, ...], r["baseline_tickets"]))
        == set(cast(tuple[Ticket, ...], r["candidate_tickets"]))
        for rows in paired.values()
        for r in rows
    )
    candidate_verdict = verdict(summaries, identical_tickets=identical)
    return {
        "task": "B649_LOO_STABILITY_TIEBREAK_OOS_OUTCOME_VALIDATION_R1",
        "candidate_head": CANDIDATE_HEAD,
        "candidate_tree": CANDIDATE_TREE,
        "canonical_head": CANONICAL_HEAD,
        "canonical_tree": CANONICAL_TREE,
        "candidate_method": METHOD_ID,
        "candidate_budgets": BUDGETS,
        "supported_k": SUPPORTED_K,
        "unsupported_k": {
            "2": "NO_CURRENT_OPERATIONAL_INCUMBENT",
            "3": "NO_CURRENT_OPERATIONAL_INCUMBENT",
        },
        "primary_success_metric": PRIMARY_METRIC,
        "protocol": {
            "primary_authority": "b649_multi_ticket_records.primary_ranking_criterion",
            "baseline_authority": "b649_goalc_local_scheduler.materialize_predraw_portfolios",
            "eligibility": "ALL_ELEVEN_STREAMS_AND_INCUMBENT_JOINT_K5_K10_K20_AVAILABLE",
            "warmup_prior_draws": warmup,
            "primary_window": "FULL",
            "recent_windows_in_canonical_draws": RECENT_WINDOWS,
            "recent_windows_are_independent_confirmation": False,
            "bootstrap": "PAIRED_DRAW_IID_MULTINOMIAL_PERCENTILE",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "familywise_control": "BONFERRONI_INTERVALS_AND_HOLM_EXACT_MCNEMAR_3_K",
            "min_paired_draws": MIN_PAIRED_DRAWS,
            "min_primary_discordant_draws": MIN_DISCORDANT_DRAWS,
            "advancement": "AT_LEAST_ONE_ADEQUATE_POSITIVE_K_AND_NO_VALIDATED_NEGATIVE_K",
            "serial_dependence": "IID_INTERVALS_DO_NOT_ESTABLISH_TEMPORAL_INDEPENDENCE",
            "history_caveat": "CURRENT_CANONICAL_DATA_RECONSTRUCTED_PREFIX_NOT_VINTAGE_ARCHIVE",
            "prospective_confirmation_draws": 0,
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
        "deterministic_stream_targets": deterministic_stream_targets,
        "ranking_determinism": "ALL_PAIRED_DRAWS_REPEATED_WITH_REVERSED_STREAM_ORDER",
        "leakage_status": "PASS_STRICT_PREFIX_AND_OUTCOME_ISOLATED_SELECTION",
        "outcome_tuning": "NONE",
        "candidate_verdict": candidate_verdict,
        "ready_for_confirmatory_stage": candidate_verdict == "POSITIVE_LIFT_VALIDATED",
        "ready_for_branch6_adoption": False,
        "production_mutation": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    if args.output.exists():
        raise ValueError("RESULT_ALREADY_EXISTS")
    authority = verify_authority(root)
    result = evaluate(load_draws(args.database))
    result["source_database"] = str(args.database)
    result["frozen_source_sha256"] = authority
    result["evaluation_module_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("xb") as handle:
        handle.write(encoded(result))
    print(result["candidate_verdict"])


if __name__ == "__main__":
    main()
