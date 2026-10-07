"""Exhaust the pinned K20 disjoint F3/F2 and F3/F3 four-slot support trades.

Every unique legal portfolio is scored by the canonical exact evaluator over
one immutable, complete main-draw space. No overlap filter or proxy is used.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import time
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 import (
    canonical_portfolio_bytes,
    normalize_portfolio,
    portfolio_sha256,
)
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type JsonObject = dict[str, Any]
type Family = Literal["F3_F2", "F3_F3"]
type Rejection = Literal["LEGAL", "N1_N2_EQUIVALENT", "ILLEGAL"]

TASK_ID = "B649_K20_12_8_WINNER_MINIMAL_FREQUENCY_SUPPORT_TRADE_R1"
OPERATOR_SIGNATURE = "MINIMAL_DISJOINT_SUPPORT_2X2_EXCHANGE_F3F2_OR_F3F3"
SOURCE_HEAD = "f785f8f5b1af1f4987558caf42180e7c8bc4bf03"
BASELINE_COUNT = 313_263_888
BASELINE_ARTIFACT_SHA = "10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b"
BASELINE_NORMALIZED_SHA = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
BASELINE_SOURCE_FILE_SHA = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
BASELINE_SOURCE_PATH = (
    "/Users/kelvin/.codex/worktrees/b649-k20-12-8-winner-two-ticket-ascent-r1/"
    "MathStatisticalAnalysis/docs/research/matrix-native-results/"
    "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
RESULT_RELATIVE_PATH = (
    "docs/research/matrix-native-results/b649-k20-minimal-frequency-support-trade-r1-result.json"
)
BASELINE: Portfolio = (
    (1, 2, 3, 4, 5, 21),
    (1, 6, 7, 8, 9, 22),
    (2, 10, 11, 12, 13, 22),
    (3, 6, 10, 14, 15, 23),
    (2, 7, 14, 16, 17, 24),
    (4, 8, 10, 16, 18, 25),
    (1, 11, 14, 18, 19, 26),
    (4, 6, 12, 19, 20, 24),
    (5, 7, 11, 15, 20, 25),
    (5, 9, 12, 17, 18, 23),
    (9, 13, 15, 16, 19, 21),
    (3, 8, 13, 17, 20, 26),
    (27, 29, 30, 31, 32, 33),
    (27, 34, 35, 36, 37, 38),
    (27, 39, 40, 41, 42, 43),
    (28, 29, 34, 39, 44, 45),
    (28, 30, 35, 40, 46, 47),
    (28, 31, 36, 41, 48, 49),
    (32, 37, 42, 44, 46, 48),
    (33, 38, 43, 45, 47, 49),
)


@dataclass(frozen=True, slots=True)
class Exchange:
    family: Family
    x: int
    y: int
    a: tuple[int, int]
    b: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Candidate:
    exchange: Exchange
    portfolio: Portfolio
    normalized_sha: str


@dataclass(slots=True)
class Accounting:
    RAW_OPERATOR_INSTANTIATIONS: int = 0
    LEGAL_CANDIDATES: int = 0
    UNIQUE_NORMALIZED_CANDIDATES: int = 0
    EXCLUDED_N1_N2_EQUIVALENT: int = 0
    EXCLUDED_ILLEGAL: int = 0
    DUPLICATE_NORMALIZED_CANDIDATES: int = 0
    F3_F2_CANDIDATES: int = 0
    F3_F3_CANDIDATES: int = 0
    F3_F2_RAW_INSTANTIATIONS: int = 0
    F3_F3_RAW_INSTANTIATIONS: int = 0


def ordered_portfolio(portfolio: Sequence[Sequence[int]]) -> Portfolio:
    """Validate K20 legality without changing the slot order."""

    normalize_portfolio(portfolio, expected_ticket_count=20)
    return tuple(tuple(sorted(ticket)) for ticket in portfolio)


def artifact_sha(portfolio: Portfolio) -> str:
    return hashlib.sha256(json.dumps(portfolio, separators=(",", ":")).encode()).hexdigest()


def supports(portfolio: Portfolio) -> dict[int, tuple[int, ...]]:
    return {n: tuple(i for i, ticket in enumerate(portfolio) if n in ticket) for n in range(1, 50)}


def frequencies(portfolio: Portfolio) -> tuple[int, ...]:
    return tuple(map(len, supports(portfolio).values()))


def changed_slots(baseline: Portfolio, candidate: Portfolio) -> tuple[int, ...]:
    return tuple(i for i, (a, b) in enumerate(zip(baseline, candidate, strict=True)) if a != b)


def iter_exchanges(portfolio: Portfolio) -> Iterator[Exchange]:
    support = supports(portfolio)
    for left, right in itertools.combinations(range(1, 50), 2):
        x, y = left, right
        fx, fy = len(support[x]), len(support[y])
        if (fx, fy) not in ((3, 2), (2, 3), (3, 3)):
            continue
        if not set(support[x]).isdisjoint(support[y]):
            continue
        if fx == 2:
            x, y = y, x
        family: Family = "F3_F2" if len(support[y]) == 2 else "F3_F3"
        for a in itertools.combinations(support[x], 2):
            for b in itertools.combinations(support[y], 2):
                yield Exchange(family, x, y, a, b)


def apply_exchange(portfolio: Portfolio, exchange: Exchange) -> Portfolio:
    tickets = list(portfolio)
    for slot in exchange.a:
        tickets[slot] = tuple(sorted((set(tickets[slot]) - {exchange.x}) | {exchange.y}))
    for slot in exchange.b:
        tickets[slot] = tuple(sorted((set(tickets[slot]) - {exchange.y}) | {exchange.x}))
    return tuple(tickets)


def candidate_acceptance(baseline: Portfolio, candidate: Portfolio) -> Rejection:
    try:
        candidate = ordered_portfolio(candidate)
    except ValueError:
        return "ILLEGAL"
    difference = len(changed_slots(baseline, candidate))
    if difference < 4:
        return "N1_N2_EQUIVALENT"
    if difference != 4 or frequencies(baseline) != frequencies(candidate):
        return "ILLEGAL"
    return "LEGAL"


def deduplicate_candidates(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    seen: dict[str, Candidate] = {}
    for candidate in candidates:
        digest = portfolio_sha256(candidate.portfolio)
        if digest != candidate.normalized_sha:
            raise AssertionError("candidate identity does not match the validated hash helper")
        previous = seen.get(digest)
        if previous is not None:
            if canonical_portfolio_bytes(previous.portfolio) != canonical_portfolio_bytes(
                candidate.portfolio
            ):
                raise AssertionError("SHA collision between distinct normalized ticket sets")
        else:
            seen[digest] = candidate
    return tuple(seen[digest] for digest in sorted(seen))


def enumerate_family(baseline: Portfolio) -> tuple[tuple[Candidate, ...], Accounting]:
    baseline = ordered_portfolio(baseline)
    accounting = Accounting()
    legal: list[Candidate] = []
    for exchange in iter_exchanges(baseline):
        accounting.RAW_OPERATOR_INSTANTIATIONS += 1
        if exchange.family == "F3_F2":
            accounting.F3_F2_RAW_INSTANTIATIONS += 1
        else:
            accounting.F3_F3_RAW_INSTANTIATIONS += 1
        portfolio = apply_exchange(baseline, exchange)
        acceptance = candidate_acceptance(baseline, portfolio)
        if acceptance == "N1_N2_EQUIVALENT":
            accounting.EXCLUDED_N1_N2_EQUIVALENT += 1
        elif acceptance == "ILLEGAL":
            accounting.EXCLUDED_ILLEGAL += 1
        else:
            accounting.LEGAL_CANDIDATES += 1
            legal.append(Candidate(exchange, portfolio, portfolio_sha256(portfolio)))
    unique = deduplicate_candidates(legal)
    accounting.UNIQUE_NORMALIZED_CANDIDATES = len(unique)
    accounting.DUPLICATE_NORMALIZED_CANDIDATES = len(legal) - len(unique)
    accounting.F3_F2_CANDIDATES = sum(c.exchange.family == "F3_F2" for c in unique)
    accounting.F3_F3_CANDIDATES = sum(c.exchange.family == "F3_F3" for c in unique)
    if accounting.RAW_OPERATOR_INSTANTIATIONS != (
        accounting.LEGAL_CANDIDATES
        + accounting.EXCLUDED_N1_N2_EQUIVALENT
        + accounting.EXCLUDED_ILLEGAL
    ):
        raise AssertionError("raw candidate accounting is incomplete")
    return unique, accounting


def canonical_score(
    portfolio: Portfolio,
    draws: DrawMasks,
    *,
    pool_size: int = 49,
    chunk_size: int = 1 << 21,
) -> ExactPortfolioProbability:
    return evaluate_portfolio(portfolio, draws=draws, pool_size=pool_size, chunk_size=chunk_size)


def special_rescue(score: ExactPortfolioProbability) -> int:
    return score.official_any_prize_outcome_count - score.m3_plus_draw_count * score.special_count


def best_index(candidates: Sequence[Candidate], scores: Sequence[ExactPortfolioProbability]) -> int:
    if not candidates or len(candidates) != len(scores):
        raise ValueError("best selection requires one score for every candidate")
    return min(
        range(len(candidates)),
        key=lambda i: (-scores[i].official_any_prize_outcome_count, candidates[i].normalized_sha),
    )


def write_json(path: Path, data: JsonObject) -> None:
    encoded = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if json.loads(encoded) != data:
        raise AssertionError("JSON round-trip changes result semantics")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    if json.loads(path.read_text()) != data:
        raise AssertionError("saved JSON does not match the serialized result")


def run_family() -> JsonObject:
    root = Path(__file__).resolve().parents[3]
    if os.environ.get("FABLE_PROTECTED_RUN_TASK_ID") != TASK_ID:
        raise RuntimeError("launch this exhaustive evaluation through the task's protected runner")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != SOURCE_HEAD:
        raise ValueError("source HEAD differs from the pinned task authority")
    baseline = ordered_portfolio(BASELINE)
    if artifact_sha(baseline) != BASELINE_ARTIFACT_SHA:
        raise AssertionError("baseline artifact-order identity mismatch")
    if portfolio_sha256(baseline) != BASELINE_NORMALIZED_SHA:
        raise AssertionError("baseline normalized-set identity mismatch")
    candidates, accounting = enumerate_family(baseline)
    if not candidates:
        raise ValueError("the defined family has no unique legal candidates")
    checkpoint_path = root / ".fable" / "checkpoints" / TASK_ID / "application.json"
    result_path = root / RESULT_RELATIVE_PATH
    if checkpoint_path.exists() or result_path.exists():
        raise RuntimeError("existing task state requires reconciliation; do not start twice")
    started = time.monotonic()
    draws = all_main_draw_masks(49, 6)
    draws.flags.writeable = False
    baseline_score = canonical_score(baseline, draws)
    if baseline_score.official_any_prize_outcome_count != BASELINE_COUNT:
        raise AssertionError("baseline canonical recount differs from 313263888")
    metadata: JsonObject = {
        "TASK_ID": TASK_ID,
        "OPERATOR_SIGNATURE": OPERATOR_SIGNATURE,
        "SOURCE_HEAD": head,
        "BASELINE_COUNT": BASELINE_COUNT,
        "BASELINE_ARTIFACT_SHA": BASELINE_ARTIFACT_SHA,
        "BASELINE_NORMALIZED_SHA": BASELINE_NORMALIZED_SHA,
        "BASELINE_SOURCE_PATH": BASELINE_SOURCE_PATH,
        "BASELINE_SOURCE_FILE_SHA256": BASELINE_SOURCE_FILE_SHA,
        "BASELINE_CANONICAL_RESCORE": "PASS",
        "BASELINE_M3_PLUS_DRAW_COUNT": baseline_score.m3_plus_draw_count,
        "BASELINE_SPECIAL_RESCUE_OUTCOMES": special_rescue(baseline_score),
        "MAIN_DRAW_COUNT": baseline_score.main_draw_count,
        "SPECIAL_COUNT": baseline_score.special_count,
        "BASELINE_FREQUENCY_HISTOGRAM": {
            str(k): v for k, v in sorted(Counter(frequencies(baseline)).items())
        },
        "DRIVER_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "CANONICAL_EVALUATOR_SHA256": hashlib.sha256(
            Path(__file__).with_name("b649_official_any_prize_exact.py").read_bytes()
        ).hexdigest(),
        "NORMALIZED_HASH_HELPER_MODULE_SHA256": hashlib.sha256(
            Path(__file__)
            .with_name("b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1.py")
            .read_bytes()
        ).hexdigest(),
        "CANDIDATE_MANIFEST_SHA256": hashlib.sha256(
            json.dumps([c.normalized_sha for c in candidates], separators=(",", ":")).encode()
        ).hexdigest(),
        **asdict(accounting),
    }
    score_rows: list[list[str | int]] = []
    checkpoint: JsonObject = {
        **metadata,
        "TASK_STATUS": "ACTIVE",
        "WORKTREE": str(root),
        "AUTHORITATIVE_PACKET_REF": (
            "/Users/kelvin/.codex/attachments/fb6c06b5-2529-4aab-8854-a9b293ac4c3e/"
            "pasted-text-1.txt"
        ),
        "EXACT_SCORED_CANDIDATES": 0,
        "SCORE_ROW_COLUMNS": ["NORMALIZED_SHA", "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT", "M3_PLUS"],
        "SCORE_ROWS": score_rows,
        "ELAPSED_SECONDS": round(time.monotonic() - started, 3),
    }
    write_json(checkpoint_path, checkpoint)
    scores: list[ExactPortfolioProbability] = []
    for i, candidate in enumerate(candidates, start=1):
        score = canonical_score(candidate.portfolio, draws)
        scores.append(score)
        score_rows.append(
            [
                candidate.normalized_sha,
                score.official_any_prize_outcome_count,
                score.m3_plus_draw_count,
            ]
        )
        if i == 1 or i % 10 == 0 or i == len(candidates):
            checkpoint.update(
                EXACT_SCORED_CANDIDATES=i,
                ELAPSED_SECONDS=round(time.monotonic() - started, 3),
                BEST_EXACT_COUNT=max(s.official_any_prize_outcome_count for s in scores),
            )
            write_json(checkpoint_path, checkpoint)
    winner_index = best_index(candidates, scores)
    best = candidates[winner_index]
    best_score = scores[winner_index]
    # Fresh canonical recount with a different chunk partition; no extra baseline recount.
    fresh = canonical_score(best.portfolio, draws, chunk_size=1 << 19)
    if fresh != best_score:
        raise AssertionError("best candidate fresh canonical recount failed exact-count parity")
    if candidate_acceptance(baseline, best.portfolio) != "LEGAL":
        raise AssertionError("best candidate failed final legality/frequency/four-slot checks")
    strict_gain = fresh.official_any_prize_outcome_count > BASELINE_COUNT
    result: JsonObject = {
        "SCHEMA_VERSION": 1,
        **metadata,
        "TASK_STATUS": "EVALUATED_CHECKS_PENDING",
        "EXACT_SCORED_CANDIDATES": len(scores),
        "BEST_EXACT_COUNT": fresh.official_any_prize_outcome_count,
        "BEST_DELTA": fresh.official_any_prize_outcome_count - BASELINE_COUNT,
        "BEST_NORMALIZED_SHA": best.normalized_sha,
        "BEST_ARTIFACT_SHA": artifact_sha(best.portfolio),
        "BEST_M3_PLUS_DRAW_COUNT": fresh.m3_plus_draw_count,
        "BEST_SPECIAL_RESCUE_OUTCOMES": special_rescue(fresh),
        "BEST_TICKETS": [list(ticket) for ticket in best.portfolio],
        "BEST_EXCHANGE": {
            "FAMILY": best.exchange.family,
            "X": best.exchange.x,
            "Y": best.exchange.y,
            "A_ZERO_BASED": list(best.exchange.a),
            "B_ZERO_BASED": list(best.exchange.b),
        },
        "BEST_CHANGED_SLOTS_ZERO_BASED": list(changed_slots(baseline, best.portfolio)),
        "CANONICAL_RESCORE": "PASS",
        "STRICT_GAIN": "YES" if strict_gain else "NO",
        "FAMILY_STATUS": (
            "STRICT_GAIN_FOUND_FOR_DEFINED_MINIMAL_FOUR_TICKET_SUPPORT_TRADE_FAMILY"
            if strict_gain
            else "NO_STRICT_GAIN_FOR_DEFINED_MINIMAL_FOUR_TICKET_SUPPORT_TRADE_FAMILY"
        ),
        "READY_FOR_N1_ASCENT": "YES" if strict_gain else "NO",
        "FOCUSED_TESTS": "NOT_RUN",
        "RUFF": "NOT_RUN",
        "PYRIGHT": "NOT_RUN",
        "DIFF_CHECK": "NOT_RUN",
        "LOCAL_COMMIT": "NOT_CREATED_NO_OWNER_AUTHORIZATION",
        "RESULT_LOCATOR": str(result_path),
        "WORKTREE": str(root),
        "PRODUCTION_MUTATION": "NONE",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "CANDIDATE_SCORE_SHA256": hashlib.sha256(
            json.dumps(score_rows, separators=(",", ":")).encode()
        ).hexdigest(),
        "EVALUATION_SECONDS": round(time.monotonic() - started, 3),
    }
    write_json(result_path, result)
    checkpoint.update(
        TASK_STATUS="EVALUATED_CHECKS_PENDING",
        CANONICAL_RESCORE="PASS",
        RESULT_LOCATOR=str(result_path),
        NEXT_ACTION="FOCUSED_PYTEST_RUFF_PYRIGHT_DIFF_CHECK_THEN_SEAL",
    )
    write_json(checkpoint_path, checkpoint)
    return result


def load_result(path: Path) -> JsonObject:
    result = cast(JsonObject, json.loads(path.read_text()))
    if result["TASK_ID"] != TASK_ID or result["OPERATOR_SIGNATURE"] != OPERATOR_SIGNATURE:
        raise ValueError("result belongs to a different start/operator task")
    if result["BASELINE_NORMALIZED_SHA"] != BASELINE_NORMALIZED_SHA:
        raise ValueError("result uses a different normalized start")
    return result


if __name__ == "__main__":
    print(json.dumps(run_family(), indent=2, sort_keys=True))
