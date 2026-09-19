"""Outcome-blind structural discriminability of a pre-draw ranking candidate.

Compares the frozen candidate ``B649_MARGINAL_REDUNDANCY_PORTFOLIO_V1`` against
the operational incumbent ``B649_OPERATIONAL_PORTFOLIO_SELECTOR`` v1.0.0 over
historical pre-draw pools, and reports *only* whether the two rankers select
different tickets. It never scores a selection against a draw result.

Outcome isolation
-----------------

The 11 streams are history-driven producers, so prior draws' main numbers are
their unavoidable pre-draw input; that is the same seam the canonical
operational replay uses. Three invariants keep the target's result out:

* the SQL projection never names ``special_numbers_json`` or any prize,
  winner or hit column, so no such value is ever loaded;
* :func:`build_pool` rejects any history that is not a strict prefix ending
  before the target draw, so the target's own row cannot reach an adapter;
* nothing here evaluates a ticket, so no hit count, prize tier, winner label,
  lift or success rate is computed at any point.

Reuse of the prior replay artifact is likewise whitelisted: only its
outcome-free pool, cutoff and incumbent-selection identity fields are read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from statistics import fmean, median
from typing import Final, cast

from tools.b649_operational_prediction_loop import STRATEGY_STREAMS, StrategyStream

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)
from lottolab.research.b649_marginal_redundancy_portfolio import (
    CANDIDATE_NAME,
    CANDIDATE_VERSION,
    build_marginal_redundancy_portfolio,
    candidate_identity,
)
from lottolab.strategies.adapters.base import BetAdapterError, CausalDrawRow, PortfolioBetAdapter

TASK: Final[str] = "B649_NEW_PREDRAW_RANKING_HYPOTHESIS_R1"
INCUMBENT_NAME: Final[str] = "B649_OPERATIONAL_PORTFOLIO_SELECTOR"
INCUMBENT_VERSION: Final[str] = "1.0.0"
SUPPORTED_K: Final[tuple[int, int, int]] = (5, 10, 20)
# pyright narrows StrEnum members to str literals here, which also makes the
# canonical tools/b649_operational_prediction_loop.py report the same error on
# an untouched origin/main tree; the cast restores the real runtime type.
BIG_LOTTO: Final[LotteryType] = cast(LotteryType, LotteryType.BIG_LOTTO)

#: The only columns this module may project. ``special_numbers_json`` and every
#: prize/winner/hit column are deliberately absent.
DRAW_COLUMNS: Final[tuple[str, str, str]] = ("draw_number", "draw_date", "main_numbers_json")
DRAW_QUERY: Final[str] = (
    f"SELECT {', '.join(DRAW_COLUMNS)} FROM draws WHERE lottery_type = ? "
    "ORDER BY draw_date, CAST(draw_number AS INTEGER)"
)

#: Outcome-free fields of a prior replay row. ``baseline`` and ``candidate``
#: hold that replay's scored results and are never read.
REPLAY_WHITELIST: Final[frozenset[str]] = frozenset(
    {
        "target_draw",
        "target_date",
        "cutoff_draw",
        "cutoff_date",
        "history_count",
        "history_sha256",
        "pool_sha256",
        "k",
        "baseline_tickets",
    }
)


def encoded(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def digest(value: object) -> str:
    """Identical canonical encoding to the operational replay, so hashes join."""
    return hashlib.sha256(encoded(value)).hexdigest()


def load_history(database: Path) -> tuple[CausalDrawRow, ...]:
    """Read the canonical draw sequence read-only, main numbers only."""
    paths = LocalDataPaths(data_directory=database.parent, database=database)
    if not verify_schema_read_only(paths):
        raise ValueError("CANONICAL_SCHEMA_UNAVAILABLE")
    with open_database(paths, read_only=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        rows = connection.execute(DRAW_QUERY, (str(BIG_LOTTO),)).fetchall()

    draws: list[CausalDrawRow] = []
    for number, day, main_json in rows:
        main = cast(list[int], json.loads(str(main_json)))
        if len(main) != 6 or len(set(main)) != 6 or any(not 1 <= n <= 49 for n in main):
            raise ValueError("INVALID_CANONICAL_DRAW_ROW")
        draws.append(CausalDrawRow(str(number), str(day), tuple(main)))
    keys = [(date.fromisoformat(row.date), int(row.draw)) for row in draws]
    if not keys or keys != sorted(set(keys)):
        raise ValueError("CANONICAL_DRAW_ORDER_OR_DUPLICATE_IDENTITY")
    return tuple(draws)


def build_pool(
    history: Sequence[CausalDrawRow],
    target_number: str,
    target_date: str,
    streams: Sequence[StrategyStream],
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
            tickets = adapter.get_bets(tuple(history), BIG_LOTTO)
        else:
            ticket, _ = adapter.get_one_bet(tuple(history), BIG_LOTTO)
            tickets = (ticket,)
        if len(tickets) != stream.native_ticket_count:
            raise ValueError("NATIVE_CARDINALITY_MISMATCH")
        pool.append(StrategyCandidate(stream.strategy_id, tickets))
    return tuple(pool)


@dataclass(frozen=True)
class SelectionPair:
    """One target draw's incumbent and candidate selections at one budget."""

    target_draw: str
    target_date: str
    cutoff_draw: str
    history_count: int
    pool_sha256: str
    distinct_pool_size: int
    k: int
    incumbent: tuple[Ticket, ...]
    candidate: tuple[Ticket, ...]

    @property
    def same_set(self) -> bool:
        return set(self.incumbent) == set(self.candidate)

    @property
    def overlap(self) -> int:
        return len(set(self.incumbent) & set(self.candidate))

    @property
    def order_only_difference(self) -> bool:
        return self.same_set and self.incumbent != self.candidate

    @property
    def top_rank_changed(self) -> bool:
        return self.incumbent[0] != self.candidate[0]


def compare_target(
    history: Sequence[CausalDrawRow],
    target: CausalDrawRow,
    streams: Sequence[StrategyStream],
) -> tuple[SelectionPair, ...]:
    """Both rankers over one shared pool. The target's numbers are never read."""
    pool = build_pool(history, target.draw, target.date, streams)
    distinct = {tuple(sorted(t)) for stream in pool for t in stream.tickets}
    if len(distinct) < max(SUPPORTED_K):
        raise ValueError("INCUMBENT_JOINT_K5_K10_K20_UNAVAILABLE_LT20_DISTINCT_TICKETS")

    incumbent = build_portfolio(pool, {}, bucket_sizes=SUPPORTED_K)
    portfolio = build_marginal_redundancy_portfolio(pool, budgets=SUPPORTED_K)
    repeated = build_marginal_redundancy_portfolio(tuple(reversed(pool)), budgets=SUPPORTED_K)
    if repeated.tickets_by_k != portfolio.tickets_by_k or incumbent != build_portfolio(
        pool, {}, bucket_sizes=SUPPORTED_K
    ):
        raise ValueError("NONDETERMINISTIC_FROZEN_RANKING")

    pool_hash = digest([(stream.strategy_id, stream.tickets) for stream in pool])
    return tuple(
        SelectionPair(
            target_draw=target.draw,
            target_date=target.date,
            cutoff_draw=history[-1].draw,
            history_count=len(history),
            pool_sha256=pool_hash,
            distinct_pool_size=len(distinct),
            k=k,
            incumbent=tuple(incumbent[k]),
            candidate=portfolio.tickets_by_k[k],
        )
        for k in SUPPORTED_K
    )


def summarize(pairs: Sequence[SelectionPair]) -> dict[str, object]:
    """Structural difference only. No outcome quantity is computed here."""
    comparable = len(pairs)
    different = [pair for pair in pairs if not pair.same_set]
    overlaps = [pair.overlap for pair in pairs]
    k = pairs[0].k if pairs else 0
    return {
        "K": k,
        "COMPARABLE_DRAWS": comparable,
        "SAME_SELECTION_DRAWS": comparable - len(different),
        "DIFFERENT_SELECTION_DRAWS": len(different),
        "SELECTION_DISAGREEMENT_RATE": len(different) / comparable if comparable else None,
        "TICKET_SET_OVERLAP_SUMMARY": {
            "min": min(overlaps) if overlaps else None,
            "median": median(overlaps) if overlaps else None,
            "mean": fmean(overlaps) if overlaps else None,
            "max": max(overlaps) if overlaps else None,
            "distribution": dict(sorted(Counter(overlaps).items())),
            "mean_changed_tickets_per_draw": (k - fmean(overlaps)) if overlaps else None,
            "mean_changed_tickets_per_differing_draw": (
                fmean([k - pair.overlap for pair in different]) if different else None
            ),
        },
        "ORDER_ONLY_DIFFERENCE_COUNT": sum(pair.order_only_difference for pair in pairs),
        "TOP_RANK_CHANGE_COUNT": sum(pair.top_rank_changed for pair in pairs),
        "TOP_RANK_CHANGE_RATE": (
            sum(pair.top_rank_changed for pair in pairs) / comparable if comparable else None
        ),
    }


def load_replay_crosscheck(path: Path) -> dict[tuple[str, int], dict[str, object]]:
    """Whitelisted outcome-free rows of the prior operational replay artifact.

    Only the pool/cutoff/incumbent-selection identity fields are read, so the
    artifact's scored ``baseline``/``candidate`` payloads never enter memory
    beyond the raw parse, and the prior candidate's own selections are ignored.
    """
    document = cast(dict[str, object], json.loads(path.read_text()))
    by_k = cast(Mapping[str, Mapping[str, object]], document["by_k"])
    rows: dict[tuple[str, int], dict[str, object]] = {}
    for bucket in by_k.values():
        for raw in cast(Sequence[Mapping[str, object]], bucket["paired_draws"]):
            row = {key: value for key, value in raw.items() if key in REPLAY_WHITELIST}
            if frozenset(row) != REPLAY_WHITELIST:
                raise ValueError("REPLAY_ARTIFACT_SCHEMA_CHANGED")
            rows[(str(row["target_draw"]), int(cast(int, row["k"])))] = row
    return rows


def crosscheck(
    pairs: Sequence[SelectionPair], replay: Mapping[tuple[str, int], dict[str, object]]
) -> dict[str, object]:
    """Same-pool / same-cutoff comparability against the prior replay artifact."""
    matched = pool_ok = cutoff_ok = incumbent_ok = 0
    mismatches: list[dict[str, object]] = []
    for pair in pairs:
        row = replay.get((pair.target_draw, pair.k))
        if row is None:
            continue
        matched += 1
        pool_same = row["pool_sha256"] == pair.pool_sha256
        cutoff_same = (
            str(row["cutoff_draw"]) == pair.cutoff_draw
            and int(cast(int, row["history_count"])) == pair.history_count
        )
        incumbent_same = (
            tuple(tuple(t) for t in cast(Sequence[Sequence[int]], row["baseline_tickets"]))
            == pair.incumbent
        )
        pool_ok += pool_same
        cutoff_ok += cutoff_same
        incumbent_ok += incumbent_same
        if not (pool_same and cutoff_same and incumbent_same) and len(mismatches) < 20:
            mismatches.append(
                {
                    "target_draw": pair.target_draw,
                    "k": pair.k,
                    "pool_sha256_match": pool_same,
                    "cutoff_match": cutoff_same,
                    "incumbent_selection_match": incumbent_same,
                }
            )
    return {
        "MATCHED_ROWS": matched,
        "SAME_POOL_SHA256": pool_ok,
        "SAME_CUTOFF": cutoff_ok,
        "SAME_INCUMBENT_SELECTION": incumbent_ok,
        "COMPARABLE": matched > 0 and pool_ok == cutoff_ok == incumbent_ok == matched,
        "MISMATCH_SAMPLE": mismatches,
    }


def run(
    database: Path,
    replay_artifact: Path | None,
    streams: Sequence[StrategyStream] = STRATEGY_STREAMS,
) -> dict[str, object]:
    enabled = tuple(stream for stream in streams if stream.enabled)
    warmup = max(stream.adapter_factory().min_history for stream in enabled)
    draws = load_history(database)
    source_hash = digest([asdict(row) for row in draws])

    pairs: list[SelectionPair] = []
    excluded: Counter[str] = Counter()
    for index, target in enumerate(draws):
        history = draws[:index]
        if len(history) < warmup:
            excluded[f"WARMUP_REQUIRES_{warmup}_PRIOR_DRAWS"] += 1
            continue
        try:
            pairs.extend(compare_target(history, target, enabled))
        except (BetAdapterError, ValueError) as error:
            reason = str(error).split(":")[0]
            if reason not in {
                "INCUMBENT_JOINT_K5_K10_K20_UNAVAILABLE_LT20_DISTINCT_TICKETS",
                "STREAM_UNAVAILABLE",
            } and not isinstance(error, BetAdapterError):
                raise
            excluded[reason] += 1

    if digest([asdict(row) for row in load_history(database)]) != source_hash:
        raise ValueError("SOURCE_MUTATED_DURING_REPLAY")

    by_k = {str(k): summarize([p for p in pairs if p.k == k]) for k in SUPPORTED_K}
    result: dict[str, object] = {
        "task": TASK,
        "candidate": candidate_identity(),
        "incumbent": {"name": INCUMBENT_NAME, "version": INCUMBENT_VERSION},
        "outcome_fields_used": "NO",
        "outcome_isolation": (
            "PROJECTION_EXCLUDES_SPECIAL_AND_PRIZE_COLUMNS; "
            "STRICT_PRE_DRAW_CUTOFF_ENFORCED; NO_TICKET_EVALUATED"
        ),
        "projected_columns": list(DRAW_COLUMNS),
        "source_database": str(database),
        "source_draw_count": len(draws),
        "source_first_draw": draws[0].draw,
        "source_last_draw": draws[-1].draw,
        "source_logical_sha256": source_hash,
        "source_invariant_during_run": True,
        "warmup_prior_draws": warmup,
        "streams": [
            {
                "strategy_id": stream.strategy_id,
                "version": stream.strategy_version,
                "native_ticket_count": stream.native_ticket_count,
            }
            for stream in enabled
        ],
        "excluded_targets": dict(sorted(excluded.items())),
        "distinct_pool_size_distribution": dict(
            sorted(Counter(p.distinct_pool_size for p in pairs if p.k == 5).items())
        ),
        "by_k": by_k,
    }
    if replay_artifact is not None:
        result["same_pool_same_cutoff_crosscheck"] = crosscheck(
            pairs, load_replay_crosscheck(replay_artifact)
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--replay-artifact", type=Path, default=None)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run(args.database, args.replay_artifact)
    args.output.write_bytes(encoded(result))
    print(json.dumps(result["by_k"], indent=2))
    print(f"candidate={CANDIDATE_NAME}@{CANDIDATE_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
