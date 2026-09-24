# pyright: reportPrivateUsage=false
"""One fixed-origin, exhaustive atomic two-ticket/two-number exchange sweep.

The existing exact U3 bound and exact OFFICIAL_ANY_PRIZE scorer are reused
unchanged. Family size describes the enumerated candidates only; it is not a
parameter of the bound. No outcome/history data or stochastic search is used.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import cast

from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as u3,
)
from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner as pinned,
)
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

TASK_ID = "B649_K20_EXHAUSTIVE_2TICKET_DOUBLE_CROSS_SWAP_R1"
SEARCH_DEFINITION_VERSION = "b649-atomic-two-ticket-two-number-exchange-u3-v1"
SOURCE_COMMIT = "b24646d1ba86690bffd1acdf21fec5b64c56834d"
SOURCE_TREE = "d2fe5f0ef46c4518ff960f9e10d8ba1f3e14c4d8"
SOURCE_PATH = "docs/research/matrix-native-results/b649-k20-cross-swap-champion-r1.json"
STARTING_COUNT = 312_867_226
STARTING_FRACTION = "519713/998844"
STARTING_SHA256 = "4343a4aa699050f71d5913d26d59b138d637c8aad3528111d9bcf6d69593546b"
EXPECTED_RAW_COUNT = 31_125
EXPECTED_OVERLAPS = ((0, 97), (1, 93))


@dataclass(frozen=True, slots=True)
class DoubleCrossSwapMove:
    ticket_a_index: int
    ticket_b_index: int
    numbers_from_a: tuple[int, int]
    numbers_from_b: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Candidate:
    move: DoubleCrossSwapMove
    changed: u3.CrossSwapCandidate
    sha256: str


@dataclass(frozen=True, slots=True)
class Neighborhood:
    origin: u3.Portfolio
    pair_overlaps: tuple[tuple[int, int], ...]
    raw_count: int
    legal_count: int
    illegal_count: int
    duplicate_count: int
    unchanged_count: int
    candidates: tuple[Candidate, ...]
    digest: str

    @property
    def family_size(self) -> int:
        """Accounting only: the actual unique legal non-incumbent portfolios."""

        return len(self.candidates)


@dataclass(frozen=True, slots=True)
class Evaluation:
    candidate_sha256: str
    u3_outcome_count: int
    exact_outcome_count: int | None


def generate_moves(portfolio: Sequence[Sequence[int]]) -> Iterator[DoubleCrossSwapMove]:
    """Enumerate pairs, X, then Y lexicographically against one immutable origin."""

    origin = u3.normalize_portfolio(portfolio)
    for a, b in itertools.combinations(range(len(origin)), 2):
        da = sorted(set(origin[a]) - set(origin[b]))
        db = sorted(set(origin[b]) - set(origin[a]))
        for x in itertools.combinations(da, 2):
            for y in itertools.combinations(db, 2):
                yield DoubleCrossSwapMove(a, b, x, y)


def apply_double_cross_swap(
    portfolio: Sequence[Sequence[int]], move: DoubleCrossSwapMove
) -> u3.CrossSwapCandidate:
    """Apply both two-element set exchanges atomically, without intermediate moves."""

    origin = u3.normalize_portfolio(portfolio)
    a, b = move.ticket_a_index, move.ticket_b_index
    if type(a) is not int or type(b) is not int or not 0 <= a < b < len(origin):
        raise ValueError("ticket indices must identify an ascending distinct pair")
    old_a, old_b = origin[a], origin[b]
    for numbers, available in (
        (move.numbers_from_a, set(old_a) - set(old_b)),
        (move.numbers_from_b, set(old_b) - set(old_a)),
    ):
        if (
            len(numbers) != 2
            or any(type(number) is not int for number in numbers)
            or len(set(numbers)) != 2
            or not set(numbers) <= available
        ):
            raise ValueError("each exchanged subset must contain two exclusive numbers")
    x, y = set(move.numbers_from_a), set(move.numbers_from_b)
    new_a = tuple(sorted((set(old_a) - x) | y))
    new_b = tuple(sorted((set(old_b) - y) | x))
    updated = list(origin)
    updated[a], updated[b] = new_a, new_b
    candidate = u3.normalize_portfolio(updated, expected_ticket_count=len(origin))
    return u3.CrossSwapCandidate(candidate, (old_a, old_b), (new_a, new_b))


def enumerate_neighborhood(portfolio: Sequence[Sequence[int]]) -> Neighborhood:
    """Materialize the entire legal, deduplicated family before any scoring."""

    origin = u3.normalize_portfolio(portfolio)
    overlaps = Counter(len(set(a) & set(b)) for a, b in itertools.combinations(origin, 2))
    seen = {origin}
    hashes = {u3.portfolio_sha256(origin): origin}
    candidates: list[Candidate] = []
    raw = legal = illegal = duplicates = unchanged = 0
    digest = hashlib.sha256(SEARCH_DEFINITION_VERSION.encode("ascii"))
    for move in generate_moves(origin):
        raw += 1
        try:
            changed = apply_double_cross_swap(origin, move)
        except ValueError:
            illegal += 1
            continue
        legal += 1
        if changed.portfolio in seen:
            duplicates += 1
            unchanged += changed.portfolio == origin
            continue
        seen.add(changed.portfolio)
        sha256 = u3.portfolio_sha256(changed.portfolio)
        if sha256 in hashes:
            raise AssertionError("distinct complete portfolios have the same SHA256")
        hashes[sha256] = changed.portfolio
        candidates.append(Candidate(move, changed, sha256))
        digest.update(bytes.fromhex(sha256))
    if raw != legal + illegal or legal != duplicates + len(candidates):
        raise AssertionError("neighborhood accounting mismatch")
    return Neighborhood(
        origin,
        tuple(sorted(overlaps.items())),
        raw,
        legal,
        illegal,
        duplicates,
        unchanged,
        tuple(candidates),
        digest.hexdigest(),
    )


def load_champion(repository: Path) -> u3.Portfolio:
    """Reconstruct the authorized champion from its immutable Git blob."""

    tree = (
        pinned._git_stdout(
            repository, ["rev-parse", f"{SOURCE_COMMIT}^{{tree}}"], "source tree unavailable"
        )
        .decode("ascii")
        .strip()
    )
    if tree != SOURCE_TREE:
        raise ValueError("source tree differs from the authorized tree")
    _, raw = pinned._read_git_artifact(repository, SOURCE_COMMIT, SOURCE_PATH)
    artifact = u3._require_json_object(json.loads(raw), "champion artifact")
    portfolio = u3._require_json_portfolio(artifact.get("TERMINAL_TICKETS"), 20)
    expected = {
        "SCIENTIFIC_OBJECTIVE": "OFFICIAL_ANY_PRIZE",
        "TERMINAL_K20_OUTCOME_COUNT": STARTING_COUNT,
        "TERMINAL_K20_EXACT_PROBABILITY": STARTING_FRACTION,
        "TERMINAL_K20_PORTFOLIO_SHA256": STARTING_SHA256,
        "TOTAL_OFFICIAL_OUTCOMES": u3.TOTAL_OFFICIAL_OUTCOMES,
    }
    if any(artifact.get(key) != value for key, value in expected.items()):
        raise ValueError("champion artifact disagrees with the authorized identity")
    if u3.portfolio_sha256(portfolio) != STARTING_SHA256:
        raise ValueError("champion tickets disagree with the authorized SHA256")
    if str(Fraction(STARTING_COUNT, u3.TOTAL_OFFICIAL_OUTCOMES)) != STARTING_FRACTION:
        raise ValueError("champion count/fraction mismatch")
    return portfolio


def validate_champion_neighborhood(neighborhood: Neighborhood) -> None:
    if (
        u3.portfolio_sha256(neighborhood.origin) != STARTING_SHA256
        or neighborhood.pair_overlaps != EXPECTED_OVERLAPS
        or neighborhood.raw_count != EXPECTED_RAW_COUNT
    ):
        raise ValueError("STOP: champion identity, overlap distribution or raw count discrepancy")


@cache
def _draws() -> DrawMasks:
    return all_main_draw_masks(49, 6)


def canonical_exact_score(portfolio: u3.Portfolio) -> ExactPortfolioProbability:
    return evaluate_portfolio(portfolio, draws=_draws())


def _identity(neighborhood: Neighborhood, incumbent_count: int) -> dict[str, object]:
    return {
        "task_id": TASK_ID,
        "search_definition_version": SEARCH_DEFINITION_VERSION,
        "incumbent_sha256": u3.portfolio_sha256(neighborhood.origin),
        "incumbent_outcome_count": incumbent_count,
        "neighborhood_sha256": neighborhood.digest,
        "family_size": neighborhood.family_size,
        "raw_move_count": neighborhood.raw_count,
        "legal_move_count": neighborhood.legal_count,
        "illegal_move_count": neighborhood.illegal_count,
        "duplicate_result_count": neighborhood.duplicate_count,
        "unchanged_result_count": neighborhood.unchanged_count,
    }


def _checkpoint_payload(
    neighborhood: Neighborhood, incumbent_count: int, evaluations: Sequence[Evaluation]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "identity": _identity(neighborhood, incumbent_count),
        "evaluations": [asdict(evaluation) for evaluation in evaluations],
        "complete": len(evaluations) == neighborhood.family_size,
    }


def _load_evaluations(
    raw: bytes, neighborhood: Neighborhood, incumbent_count: int
) -> list[Evaluation]:
    payload = u3._require_json_object(json.loads(raw), "checkpoint")
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported checkpoint schema")
    if payload.get("identity") != _identity(neighborhood, incumbent_count):
        raise ValueError("checkpoint identity differs from this neighborhood")
    rows = payload.get("evaluations")
    if not isinstance(rows, list):
        raise ValueError("checkpoint evaluations must be a bounded array")
    rows = cast(list[object], rows)
    if len(rows) > neighborhood.family_size:
        raise ValueError("checkpoint evaluations must be a bounded array")
    evaluations: list[Evaluation] = []
    for candidate, item in zip(neighborhood.candidates, rows, strict=False):
        row = u3._require_json_object(item, "evaluation")
        if row.get("candidate_sha256") != candidate.sha256:
            raise ValueError("checkpoint evaluation order/portfolio mismatch")
        bound = u3._require_json_int(row, "u3_outcome_count")
        if bound < 0:
            raise ValueError("checkpoint U3 must be nonnegative")
        count = row.get("exact_outcome_count")
        if u3.should_safe_prune(bound, incumbent_count):
            if count is not None:
                raise ValueError("safely pruned candidate must not have an exact score")
        elif type(count) is not int or not 0 <= count <= min(bound, u3.TOTAL_OFFICIAL_OUTCOMES):
            raise ValueError("every U3 survivor requires a valid exact score below its bound")
        evaluations.append(Evaluation(candidate.sha256, bound, count))
    if type(payload.get("complete")) is not bool or payload["complete"] != (
        len(evaluations) == neighborhood.family_size
    ):
        raise ValueError("checkpoint completion/accounting mismatch")
    return evaluations


def run_sweep(
    neighborhood: Neighborhood,
    incumbent_count: int,
    *,
    checkpoint_path: Path,
    exact_scorer: Callable[[u3.Portfolio], ExactPortfolioProbability] = canonical_exact_score,
    resume: bool = False,
    checkpoint_every: int = 250,
    max_candidates: int | None = None,
) -> list[Evaluation]:
    """Score one fixed family; resume only its validated, completed prefix."""

    if type(incumbent_count) is not int or not 0 <= incumbent_count <= u3.TOTAL_OFFICIAL_OUTCOMES:
        raise ValueError("incumbent count is outside the canonical outcome space")
    if checkpoint_every <= 0 or (max_candidates is not None and max_candidates < 0):
        raise ValueError("invalid checkpoint interval or candidate limit")
    evaluations: list[Evaluation]
    if resume:
        expected_bytes = checkpoint_path.read_bytes()
        evaluations = _load_evaluations(expected_bytes, neighborhood, incumbent_count)
    else:
        if checkpoint_path.exists():
            raise ValueError("checkpoint already exists; use explicit resume")
        evaluations = []
        expected_bytes = u3._write_json_atomically(
            checkpoint_path, _checkpoint_payload(neighborhood, incumbent_count, evaluations)
        )
    start = len(evaluations)
    stop = (
        neighborhood.family_size
        if max_candidates is None
        else min(neighborhood.family_size, start + max_candidates)
    )
    if start == neighborhood.family_size:
        return evaluations
    origin_components = u3.full_u3_components(neighborhood.origin)

    def save() -> None:
        nonlocal expected_bytes
        if checkpoint_path.read_bytes() != expected_bytes:
            raise ValueError("checkpoint changed outside this sweep")
        expected_bytes = u3._write_json_atomically(
            checkpoint_path, _checkpoint_payload(neighborhood, incumbent_count, evaluations)
        )

    for index in range(start, stop):
        candidate = neighborhood.candidates[index]
        changed = candidate.changed
        bound = u3.incremental_u3_components(
            neighborhood.origin,
            changed.portfolio,
            origin_components,
            changed.old_changed_tickets,
            changed.new_changed_tickets,
        ).u3
        exact_count: int | None = None
        if not u3.should_safe_prune(bound, incumbent_count):
            exact = exact_scorer(changed.portfolio)
            exact_count = exact.official_any_prize_outcome_count
            if exact.main_draw_count * exact.special_count != u3.TOTAL_OFFICIAL_OUTCOMES:
                raise ValueError("exact scorer returned a noncanonical outcome space")
            if type(exact_count) is not int or not 0 <= exact_count <= u3.TOTAL_OFFICIAL_OUTCOMES:
                raise ValueError("exact scorer returned an invalid outcome count")
            if exact_count > bound:
                raise AssertionError("exact U3 upper bound is below the exact score")
        evaluations.append(Evaluation(candidate.sha256, bound, exact_count))
        if len(evaluations) % checkpoint_every == 0:
            save()
    save()
    return evaluations


def build_report(
    neighborhood: Neighborhood, incumbent_count: int, evaluations: Sequence[Evaluation]
) -> dict[str, object]:
    # Apply the same strict record/accounting validation to resumed and fresh results.
    encoded = json.dumps(_checkpoint_payload(neighborhood, incumbent_count, evaluations)).encode()
    validated = _load_evaluations(encoded, neighborhood, incumbent_count)
    exact_records: list[dict[str, object]] = []
    best_count = incumbent_count
    best_portfolio = neighborhood.origin
    best_sha = u3.portfolio_sha256(best_portfolio)
    pruned = 0
    for candidate, evaluation in zip(neighborhood.candidates, validated, strict=False):
        count = evaluation.exact_outcome_count
        if count is None:
            pruned += 1
            continue
        exact_records.append(
            {
                **asdict(evaluation),
                "portfolio": candidate.changed.portfolio,
                "move": asdict(candidate.move),
                "exact_fraction": str(Fraction(count, u3.TOTAL_OFFICIAL_OUTCOMES)),
                "delta_from_starting_champion": count - incumbent_count,
            }
        )
        if count > best_count or (
            count == best_count and count > incumbent_count and candidate.sha256 < best_sha
        ):
            best_count, best_sha = count, candidate.sha256
            best_portfolio = candidate.changed.portfolio
    complete = len(validated) == neighborhood.family_size
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE" if complete else "IN_PROGRESS",
        "SEARCH_DEFINITION_VERSION": SEARCH_DEFINITION_VERSION,
        "INCUMBENT_PORTFOLIO_SHA256": u3.portfolio_sha256(neighborhood.origin),
        "INCUMBENT_OUTCOME_COUNT": incumbent_count,
        "TICKET_PAIR_COUNT": sum(count for _, count in neighborhood.pair_overlaps),
        "PAIR_OVERLAP_DISTRIBUTION": dict(neighborhood.pair_overlaps),
        "RAW_MOVE_COUNT": neighborhood.raw_count,
        "LEGAL_MOVE_COUNT": neighborhood.legal_count,
        "ILLEGAL_MOVE_COUNT": neighborhood.illegal_count,
        "DUPLICATE_RESULT_COUNT": neighborhood.duplicate_count,
        "UNCHANGED_RESULT_COUNT": neighborhood.unchanged_count,
        "UNIQUE_PORTFOLIO_COUNT": neighborhood.family_size,
        "FAMILY_SIZE": neighborhood.family_size,
        "BONFERRONI_FAMILY_SIZE": neighborhood.family_size,
        "FAMILY_SIZE_ROLE": "ACCOUNTING_ONLY",
        "BONFERRONI_PRUNED_COUNT": pruned,
        "BONFERRONI_SURVIVOR_COUNT": len(exact_records),
        "EXACTLY_RESCORED_COUNT": len(exact_records),
        "UNPROCESSED_UNIQUE_COUNT": neighborhood.family_size - len(validated),
        "RESULT": (
            "INCOMPLETE"
            if not complete
            else "STRICT_IMPROVEMENT_FOUND"
            if best_count > incumbent_count
            else "NO_STRICT_IMPROVEMENT_IN_COMPLETE_DEFINED_DOUBLE_CROSS_SWAP_NEIGHBORHOOD"
        ),
        "BEST_OUTCOME_COUNT": best_count,
        "BEST_EXACT_FRACTION": str(Fraction(best_count, u3.TOTAL_OFFICIAL_OUTCOMES)),
        "BEST_PORTFOLIO_SHA256": best_sha,
        "BEST_PORTFOLIO": best_portfolio,
        "DELTA_FROM_STARTING_CHAMPION": best_count - incumbent_count,
        "NEIGHBORHOOD_COMPLETENESS": "PROVEN" if complete else "NOT_PROVEN",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "NEIGHBORHOOD_SHA256": neighborhood.digest,
        "EVALUATIONS_SHA256": hashlib.sha256(encoded).hexdigest(),
        "EXACT_SURVIVOR_RECORDS": exact_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[3]
    output = args.output_directory.resolve()
    allowed = (repository / ".task-data" / TASK_ID).resolve()
    if output != allowed and allowed not in output.parents:
        raise ValueError("output directory must be inside this task's allowlisted data root")
    neighborhood = enumerate_neighborhood(load_champion(repository))
    validate_champion_neighborhood(neighborhood)
    checkpoint_path = output / "sweep-checkpoint.json"
    result_path = output / "run-result.json"
    if result_path.exists() and not args.resume:
        raise ValueError("result already exists; use explicit resume")
    evaluations = run_sweep(
        neighborhood,
        STARTING_COUNT,
        checkpoint_path=checkpoint_path,
        resume=args.resume,
    )
    report = build_report(neighborhood, STARTING_COUNT, evaluations)
    report.update(
        {
            "CANONICAL_SOURCE_AUTHORITY": SOURCE_COMMIT,
            "SOURCE_TREE": SOURCE_TREE,
            "CHAMPION_ARTIFACT": SOURCE_PATH,
            "CHAMPION_IDENTITY_EVIDENCE": "REUSED_EXACT_TREE_EVIDENCE",
            "EXACT_SCORER": "lottolab.research.b649_official_any_prize_exact.evaluate_portfolio",
            "SWEEP_COUNT": 1,
            "CHECKPOINT_SHA256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        }
    )
    u3._write_json_atomically(result_path, report)
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"EXACT_SURVIVOR_RECORDS", "BEST_PORTFOLIO"}
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
