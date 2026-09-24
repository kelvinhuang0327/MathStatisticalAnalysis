# pyright: reportPrivateUsage=false

"""Exhaustive K20 3-cycle cross-swap VND, re-closing with the R4 2-ticket search."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Literal, cast

import numpy as np
import numpy.typing as npt

from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as r4,
)
from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner as r4_runner,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    ExactPortfolioProbability,
    evaluate_portfolio,
)

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]
DrawMaskArray = npt.NDArray[np.uint64]
TicketTriple = tuple[int, int, int]
RemovalPositions = tuple[int, int, int]
CycleOrientation = Literal["CYCLE_FORWARD", "CYCLE_REVERSE"]
OrientationIndex = Literal[0, 1]

TASK_ID = "B649_K20_BONFERRONI_FILTERED_3TICKET_CYCLIC_CROSS_SWAP_VND_R1"
RUN_ID = "run1"
BASE_COMMIT = "5ef79bf38b22252caaba4a74206438ef80fc0cb0"
BASE_TREE = "f2f17fb9c2dc54c1278b684c1fb1260915608ece"
R4_TASK_ID = "B649_K20_BONFERRONI_FILTERED_EXHAUSTIVE_2TICKET_CROSS_SWAP_ASCENT_R4"
R4_RUN2_PATH = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-2ticket-cross-swap-ascent-r4/"
    "MathStatisticalAnalysis/.task-data/"
    "B649_K20_BONFERRONI_FILTERED_EXHAUSTIVE_2TICKET_CROSS_SWAP_ASCENT_R4/"
    "run2/run-result.json"
)
R4_RUN2_SHA256 = "c0ca7609075a2df96e32142e8953011596ef2a898c28e6b3a04ca1bfadda92a9"
EXPECTED_R4_PORTFOLIO_SHA256 = "4343a4aa699050f71d5913d26d59b138d637c8aad3528111d9bcf6d69593546b"
EXPECTED_R4_OUTCOME_COUNT = 312_867_226
TOTAL_OFFICIAL_OUTCOMES = r4.TOTAL_OFFICIAL_OUTCOMES
RAW_OPERATIONS_PER_SCAN = 492_480
OPERATIONS_PER_TICKET_TRIPLE = 6**3 * 2
VND_ROUND_CAP = 4
WALL_CLOCK_CAP_SECONDS = 6 * 60 * 60
SEARCH_DEFINITION_VERSION = "b649-k20-3ticket-cyclic-cross-swap-vnd-r1"
ORIENTATIONS: tuple[CycleOrientation, CycleOrientation] = (
    "CYCLE_FORWARD",
    "CYCLE_REVERSE",
)
_PERMUTATION_BY_ORIENTATION: dict[CycleOrientation, tuple[int, int, int]] = {
    "CYCLE_FORWARD": (1, 2, 0),
    "CYCLE_REVERSE": (2, 0, 1),
}

_CANONICAL_EXACT_EVALUATOR = cast(Callable[..., ExactPortfolioProbability], evaluate_portfolio)


def canonical_exact_scorer(
    draws: DrawMaskArray | None = None,
) -> Callable[[Portfolio], ExactPortfolioProbability]:
    """Return the repository's canonical exact OFFICIAL_ANY_PRIZE scorer."""

    resolved_draws = draws if draws is not None else r4_runner._canonical_draw_space()

    def score(portfolio: Portfolio) -> ExactPortfolioProbability:
        return _CANONICAL_EXACT_EVALUATOR(portfolio, draws=resolved_draws)

    return score


@dataclass(frozen=True, slots=True)
class ThreeCycleMove:
    """One labeled 3-cycle over a selected ticket triple."""

    ticket_triple: TicketTriple
    removal_positions: RemovalPositions
    orientation: CycleOrientation

    @property
    def tie_key(self) -> tuple[int, int, int, int, int, int, int]:
        orientation_index: OrientationIndex = 0 if self.orientation == "CYCLE_FORWARD" else 1
        return (*self.ticket_triple, *self.removal_positions, orientation_index)


@dataclass(frozen=True, slots=True)
class ThreeCycleCandidate:
    move: ThreeCycleMove
    portfolio: Portfolio
    removed_numbers: tuple[int, int, int]
    added_numbers: tuple[int, int, int]
    old_changed_indices: frozenset[int]
    new_changed_indices: frozenset[int]

    @property
    def portfolio_sha256(self) -> str:
        return r4.portfolio_sha256(self.portfolio)


@dataclass(slots=True)
class ScanCheckpoint:
    """Durable progress for one complete fixed-origin 3-cycle scan."""

    task_id: str
    source_commit: str
    source_tree: str
    run2_artifact_sha256: str
    round_number: int
    origin_sha256: str
    origin_exact_count: int
    ticket_triple_index: int
    operation_index: int
    seen_log_offset: int
    raw_operation_count: int
    illegal_operation_count: int
    no_op_rejection_count: int
    legal_operation_count: int
    duplicate_result_count: int
    unique_portfolio_count: int
    bonferroni_pruned_count: int
    exact_evaluation_count: int
    best_exact_count: int
    best_portfolio_sha256: str
    best_portfolio: Portfolio
    best_move: ThreeCycleMove | None
    best_u3_count: int | None
    audit_digest: str
    complete: bool = False


@dataclass(frozen=True, slots=True)
class StartingPortfolio:
    portfolio: Portfolio
    portfolio_sha256: str
    exact_outcome_count: int
    exact_fraction: str
    run2_artifact_sha256: str
    incumbent_artifact_blob: str
    incumbent_artifact_sha256: str
    incumbent_source_path: str


@dataclass(frozen=True, slots=True)
class ControlScanResult:
    complete: bool
    best_portfolio: Portfolio
    best_portfolio_sha256: str
    best_exact_count: int
    best_move: ThreeCycleMove | None
    scan_record: dict[str, object]


@dataclass(frozen=True, slots=True)
class ClosureResult:
    complete: bool
    portfolio: Portfolio
    exact_count: int
    accepted_move_count: int
    closure_record: dict[str, object]


def s3_permutation_classes() -> dict[str, tuple[tuple[int, int, int], ...]]:
    """Partition S3 by the number of fixed ticket positions."""

    classes: dict[str, list[tuple[int, int, int]]] = {
        "IDENTITY": [],
        "TRANSPOSITION": [],
        "THREE_CYCLE": [],
    }
    for raw in itertools.permutations(range(3)):
        permutation = cast(tuple[int, int, int], raw)
        fixed_points = sum(index == destination for index, destination in enumerate(permutation))
        label = (
            "IDENTITY"
            if fixed_points == 3
            else "TRANSPOSITION"
            if fixed_points == 1
            else "THREE_CYCLE"
        )
        classes[label].append(permutation)
    return {label: tuple(values) for label, values in classes.items()}


def raw_operation_count(ticket_count: int = 20) -> int:
    """Return the structural raw operation count before candidate filtering."""

    if ticket_count < 3:
        return 0
    return len(tuple(itertools.combinations(range(ticket_count), 3))) * OPERATIONS_PER_TICKET_TRIPLE


def _move_to_json(move: ThreeCycleMove | None) -> dict[str, object] | None:
    if move is None:
        return None
    return {
        "ticket_triple": move.ticket_triple,
        "removal_positions": move.removal_positions,
        "orientation": move.orientation,
    }


def _move_from_json(value: object) -> ThreeCycleMove | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("checkpoint best move must be an object or null")
    payload = cast(dict[str, object], value)
    triple_raw = payload.get("ticket_triple")
    positions_raw = payload.get("removal_positions")
    orientation_raw = payload.get("orientation")
    if not isinstance(triple_raw, list) or not isinstance(positions_raw, list):
        raise ValueError("checkpoint move indices must be arrays")
    triple_items = cast(list[object], triple_raw)
    position_items = cast(list[object], positions_raw)
    if len(triple_items) != 3 or len(position_items) != 3:
        raise ValueError("checkpoint move must identify three tickets and positions")
    if any(type(item) is not int for item in triple_items + position_items):
        raise ValueError("checkpoint move indices must be integers")
    if orientation_raw not in ORIENTATIONS:
        raise ValueError("checkpoint move orientation is invalid")
    triple = cast(TicketTriple, tuple(cast(int, item) for item in triple_items))
    positions = cast(RemovalPositions, tuple(cast(int, item) for item in position_items))
    return ThreeCycleMove(triple, positions, orientation_raw)


def _advance_audit_digest(previous: str, record: dict[str, object]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(bytes.fromhex(previous) + canonical).hexdigest()


def _initial_audit_digest(origin_sha256: str, exact_count: int, round_number: int) -> str:
    seed = f"{SEARCH_DEFINITION_VERSION}:{round_number}:{origin_sha256}:{exact_count}"
    return hashlib.sha256(seed.encode("ascii")).hexdigest()


def _require_int(payload: dict[str, object], key: str, context: str) -> int:
    value = payload.get(key)
    if type(value) is not int:
        raise ValueError(f"{context} {key} must be an integer")
    return value


def _require_str(payload: dict[str, object], key: str, context: str) -> str:
    value = payload.get(key)
    if type(value) is not str:
        raise ValueError(f"{context} {key} must be a string")
    return value


def _json_portfolio(value: object, context: str) -> Portfolio:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{context} portfolio must be an array")
    tickets: list[list[int]] = []
    for raw_ticket in cast(Sequence[object], value):
        if not isinstance(raw_ticket, (list, tuple)):
            raise ValueError(f"{context} ticket must be an integer array")
        numbers = cast(Sequence[object], raw_ticket)
        if any(type(number) is not int for number in numbers):
            raise ValueError(f"{context} ticket must be an integer array")
        tickets.append([cast(int, number) for number in numbers])
    return r4.normalize_portfolio(tickets, expected_ticket_count=20)


def load_run2_starting_portfolio(
    repository: Path,
    artifact_path: Path = R4_RUN2_PATH,
) -> StartingPortfolio:
    """Load the exact named R4 run2 artifact and verify its pinned source/result."""

    if artifact_path != R4_RUN2_PATH:
        raise ValueError("R4 terminal evidence path differs from the authorized locator")
    raw = artifact_path.read_bytes()
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    if artifact_sha256 != R4_RUN2_SHA256:
        raise ValueError("R4 run2 terminal artifact digest differs from the observed locator")
    decoded: object = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError("R4 run2 terminal artifact root must be an object")
    artifact = cast(dict[str, object], decoded)

    required_equal: dict[str, object] = {
        "TASK_STATUS": "COMPLETE",
        "TASK_ID": R4_TASK_ID,
        "RUN_ID": "run2",
        "SOURCE_COMMIT": BASE_COMMIT,
        "SOURCE_TREE": BASE_TREE,
        "FINAL_DECISION": "NO_STRICT_IMPROVEMENT_IN_EXHAUSTED_2TICKET_CROSS_SWAP_NEIGHBORHOOD",
        "K20_2TICKET_CROSS_SWAP_STATUS": "PROVEN_LOCAL_OPTIMUM_FOR_DEFINED_NEIGHBORHOOD",
        "NEIGHBORHOOD_COMPLETENESS": "PROVEN",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "INCUMBENT_OUTCOME_COUNT": EXPECTED_R4_OUTCOME_COUNT,
        "INCUMBENT_EXACT_FRACTION": "519713/998844",
        "INCUMBENT_PORTFOLIO_SHA256": EXPECTED_R4_PORTFOLIO_SHA256,
        "BEST_NEIGHBOR_EXACT_OUTCOME_COUNT": EXPECTED_R4_OUTCOME_COUNT,
        "BEST_NEIGHBOR_DELTA": 0,
        "BEST_NEIGHBOR_PORTFOLIO_SHA256": EXPECTED_R4_PORTFOLIO_SHA256,
        "INCUMBENT_SOURCE_COMMIT": BASE_COMMIT,
    }
    for key, expected in required_equal.items():
        if artifact.get(key) != expected:
            raise ValueError(f"R4 run2 artifact identity/semantics mismatch for {key}")

    tree = _git_stdout(repository, ["rev-parse", f"{BASE_COMMIT}^{{tree}}"])
    if tree != BASE_TREE:
        raise ValueError("pinned R4 source commit tree differs from the required base tree")

    portfolio = _json_portfolio(artifact.get("INCUMBENT_PORTFOLIO"), "R4 run2")
    best_portfolio = _json_portfolio(artifact.get("BEST_NEIGHBOR_PORTFOLIO"), "R4 best neighbor")
    if (
        portfolio != best_portfolio
        or r4.portfolio_sha256(portfolio) != EXPECTED_R4_PORTFOLIO_SHA256
    ):
        raise ValueError("R4 run2 starting portfolio does not match its terminal incumbent")

    incumbent_sha256 = _require_str(artifact, "INCUMBENT_ARTIFACT_SHA256", "R4 run2")
    incumbent_blob = _require_str(artifact, "INCUMBENT_ARTIFACT_BLOB", "R4 run2")
    incumbent_source_path = _require_str(artifact, "INCUMBENT_SOURCE_PATH", "R4 run2")
    validated = r4_runner.load_and_verify_pinned_incumbent(
        repository,
        source_commit=BASE_COMMIT,
        source_path=incumbent_source_path,
        artifact_sha256=incumbent_sha256,
    )
    if (
        validated.artifact_blob != incumbent_blob
        or validated.incumbent.portfolio != portfolio
        or validated.incumbent.portfolio_sha256 != EXPECTED_R4_PORTFOLIO_SHA256
        or validated.exact.official_any_prize_outcome_count != EXPECTED_R4_OUTCOME_COUNT
        or str(validated.exact.official_any_prize) != "519713/998844"
    ):
        raise ValueError("R4 run2 start does not reconstruct from its exact Git-pinned incumbent")

    return StartingPortfolio(
        portfolio=portfolio,
        portfolio_sha256=EXPECTED_R4_PORTFOLIO_SHA256,
        exact_outcome_count=EXPECTED_R4_OUTCOME_COUNT,
        exact_fraction="519713/998844",
        run2_artifact_sha256=artifact_sha256,
        incumbent_artifact_blob=incumbent_blob,
        incumbent_artifact_sha256=incumbent_sha256,
        incumbent_source_path=incumbent_source_path,
    )


def _git_stdout(repository: Path, arguments: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"Git identity query failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _candidate_from_move(
    portfolio: Sequence[Sequence[int]], move: ThreeCycleMove
) -> ThreeCycleCandidate:
    origin = r4.normalize_portfolio(portfolio, expected_ticket_count=20)
    i, j, k = move.ticket_triple
    ai, bj, ck = move.removal_positions
    if not (0 <= i < j < k < len(origin)):
        raise ValueError("ticket triple must be three ascending in-range positions")
    if any(not 0 <= position < BIG_LOTTO_DRAW_SIZE for position in move.removal_positions):
        raise ValueError("removal positions must be in 0..5")
    if move.orientation not in ORIENTATIONS:
        raise ValueError("orientation must be one of the two 3-cycles")

    old_tickets = (origin[i], origin[j], origin[k])
    removed = (old_tickets[0][ai], old_tickets[1][bj], old_tickets[2][ck])
    permutation = _PERMUTATION_BY_ORIENTATION[move.orientation]
    added = tuple(removed[index] for index in permutation)
    positions = (ai, bj, ck)
    new_tickets_list: list[Ticket] = []
    for old_ticket, remove_position, add_number in zip(old_tickets, positions, added, strict=True):
        updated = set(old_ticket)
        updated.remove(old_ticket[remove_position])
        updated.add(add_number)
        new_ticket = tuple(sorted(updated))
        if len(new_ticket) != BIG_LOTTO_DRAW_SIZE:
            raise ValueError("3-cycle would create a duplicate number within a ticket")
        if any(not 1 <= number <= BIG_LOTTO_POOL_SIZE for number in new_ticket):
            raise ValueError("3-cycle ticket numbers must be in 1..49")
        new_tickets_list.append(new_ticket)

    updated_portfolio = list(origin)
    for index, new_ticket in zip(move.ticket_triple, new_tickets_list, strict=True):
        updated_portfolio[index] = new_ticket
    candidate_portfolio = r4.normalize_portfolio(updated_portfolio, expected_ticket_count=20)
    if candidate_portfolio == origin:
        raise ValueError("3-cycle no-op result is rejected")
    new_indices = frozenset(candidate_portfolio.index(ticket) for ticket in new_tickets_list)
    if len(new_indices) != 3:
        raise ValueError("3-cycle outputs must be three distinct portfolio tickets")
    return ThreeCycleCandidate(
        move=move,
        portfolio=candidate_portfolio,
        removed_numbers=removed,
        added_numbers=cast(tuple[int, int, int], added),
        old_changed_indices=frozenset(move.ticket_triple),
        new_changed_indices=new_indices,
    )


def apply_three_cycle(
    portfolio: Sequence[Sequence[int]], move: ThreeCycleMove
) -> ThreeCycleCandidate:
    """Apply one of the two legal 3-cycle orientations; reject every invalid result."""

    return _candidate_from_move(portfolio, move)


def iter_three_cycle_moves(ticket_count: int = 20) -> Iterable[ThreeCycleMove]:
    """Enumerate exactly the two derangements for each removal-position triple."""

    for ticket_triple in itertools.combinations(range(ticket_count), 3):
        triple = ticket_triple
        for positions_raw in itertools.product(range(BIG_LOTTO_DRAW_SIZE), repeat=3):
            positions = cast(RemovalPositions, positions_raw)
            for orientation in ORIENTATIONS:
                yield ThreeCycleMove(triple, positions, orientation)


def incremental_three_ticket_u3(
    origin: Sequence[Sequence[int]],
    candidate: ThreeCycleCandidate,
    base_components: r4.U3Components | None = None,
    old_affected_cache: dict[TicketTriple, r4.U3Components] | None = None,
) -> r4.U3Components:
    """Reuse R4's exact event-intersection terms for a 3-ticket U3 update."""

    normalized_origin = r4.normalize_portfolio(origin, expected_ticket_count=20)
    full = base_components or r4.full_u3_components(normalized_origin)
    cache = old_affected_cache if old_affected_cache is not None else {}
    old_terms = cache.get(candidate.move.ticket_triple)
    if old_terms is None:
        indices = frozenset(candidate.move.ticket_triple)
        old_terms = r4.U3Components(
            s1=r4._affected_sum(normalized_origin, indices, 1),
            s2=r4._affected_sum(normalized_origin, indices, 2),
            s3=r4._affected_sum(normalized_origin, indices, 3),
        )
        cache[candidate.move.ticket_triple] = old_terms
    new_terms = r4.U3Components(
        s1=r4._affected_sum(candidate.portfolio, candidate.new_changed_indices, 1),
        s2=r4._affected_sum(candidate.portfolio, candidate.new_changed_indices, 2),
        s3=r4._affected_sum(candidate.portfolio, candidate.new_changed_indices, 3),
    )
    return r4.U3Components(
        s1=full.s1 - old_terms.s1 + new_terms.s1,
        s2=full.s2 - old_terms.s2 + new_terms.s2,
        s3=full.s3 - old_terms.s3 + new_terms.s3,
    )


def _initial_scan_checkpoint(
    origin: Portfolio,
    origin_exact_count: int,
    run2_artifact_sha256: str,
    round_number: int,
) -> ScanCheckpoint:
    origin_sha256 = r4.portfolio_sha256(origin)
    return ScanCheckpoint(
        task_id=TASK_ID,
        source_commit=BASE_COMMIT,
        source_tree=BASE_TREE,
        run2_artifact_sha256=run2_artifact_sha256,
        round_number=round_number,
        origin_sha256=origin_sha256,
        origin_exact_count=origin_exact_count,
        ticket_triple_index=0,
        operation_index=0,
        seen_log_offset=0,
        raw_operation_count=0,
        illegal_operation_count=0,
        no_op_rejection_count=0,
        legal_operation_count=0,
        duplicate_result_count=0,
        unique_portfolio_count=0,
        bonferroni_pruned_count=0,
        exact_evaluation_count=0,
        best_exact_count=origin_exact_count,
        best_portfolio_sha256=origin_sha256,
        best_portfolio=origin,
        best_move=None,
        best_u3_count=None,
        audit_digest=_initial_audit_digest(origin_sha256, origin_exact_count, round_number),
    )


def _scan_checkpoint_json(state: ScanCheckpoint) -> dict[str, object]:
    return {
        "SCHEMA_VERSION": 1,
        "TASK_ID": state.task_id,
        "SOURCE_COMMIT": state.source_commit,
        "SOURCE_TREE": state.source_tree,
        "RUN2_ARTIFACT_SHA256": state.run2_artifact_sha256,
        "ROUND_NUMBER": state.round_number,
        "ORIGIN_PORTFOLIO_SHA256": state.origin_sha256,
        "ORIGIN_EXACT_OUTCOME_COUNT": state.origin_exact_count,
        "TICKET_TRIPLE_INDEX": state.ticket_triple_index,
        "OPERATION_INDEX": state.operation_index,
        "SEEN_HASH_LOG_OFFSET": state.seen_log_offset,
        "RAW_OPERATION_COUNT": state.raw_operation_count,
        "ILLEGAL_OPERATION_COUNT": state.illegal_operation_count,
        "NO_OP_REJECTION_COUNT": state.no_op_rejection_count,
        "LEGAL_OPERATION_COUNT": state.legal_operation_count,
        "DUPLICATE_RESULT_COUNT": state.duplicate_result_count,
        "UNIQUE_PORTFOLIO_COUNT": state.unique_portfolio_count,
        "BONFERRONI_PRUNED_COUNT": state.bonferroni_pruned_count,
        "EXACT_EVALUATION_COUNT": state.exact_evaluation_count,
        "BEST_EXACT_OUTCOME_COUNT": state.best_exact_count,
        "BEST_PORTFOLIO_SHA256": state.best_portfolio_sha256,
        "BEST_PORTFOLIO": state.best_portfolio,
        "BEST_MOVE": _move_to_json(state.best_move),
        "BEST_MOVE_U3_COUNT": state.best_u3_count,
        "AUDIT_DIGEST": state.audit_digest,
        "COMPLETE": state.complete,
    }


def _scan_state_from_json(value: object) -> ScanCheckpoint:
    if not isinstance(value, dict):
        raise ValueError("3-cycle checkpoint root must be an object")
    payload = cast(dict[str, object], value)
    if payload.get("SCHEMA_VERSION") != 1:
        raise ValueError("3-cycle checkpoint schema version is unsupported")
    if type(payload.get("COMPLETE")) is not bool:
        raise ValueError("3-cycle checkpoint COMPLETE must be boolean")
    best_u3 = payload.get("BEST_MOVE_U3_COUNT")
    if best_u3 is not None and type(best_u3) is not int:
        raise ValueError("3-cycle checkpoint best U3 count must be an integer or null")
    state = ScanCheckpoint(
        task_id=_require_str(payload, "TASK_ID", "checkpoint"),
        source_commit=_require_str(payload, "SOURCE_COMMIT", "checkpoint"),
        source_tree=_require_str(payload, "SOURCE_TREE", "checkpoint"),
        run2_artifact_sha256=_require_str(payload, "RUN2_ARTIFACT_SHA256", "checkpoint"),
        round_number=_require_int(payload, "ROUND_NUMBER", "checkpoint"),
        origin_sha256=_require_str(payload, "ORIGIN_PORTFOLIO_SHA256", "checkpoint"),
        origin_exact_count=_require_int(payload, "ORIGIN_EXACT_OUTCOME_COUNT", "checkpoint"),
        ticket_triple_index=_require_int(payload, "TICKET_TRIPLE_INDEX", "checkpoint"),
        operation_index=_require_int(payload, "OPERATION_INDEX", "checkpoint"),
        seen_log_offset=_require_int(payload, "SEEN_HASH_LOG_OFFSET", "checkpoint"),
        raw_operation_count=_require_int(payload, "RAW_OPERATION_COUNT", "checkpoint"),
        illegal_operation_count=_require_int(payload, "ILLEGAL_OPERATION_COUNT", "checkpoint"),
        no_op_rejection_count=_require_int(payload, "NO_OP_REJECTION_COUNT", "checkpoint"),
        legal_operation_count=_require_int(payload, "LEGAL_OPERATION_COUNT", "checkpoint"),
        duplicate_result_count=_require_int(payload, "DUPLICATE_RESULT_COUNT", "checkpoint"),
        unique_portfolio_count=_require_int(payload, "UNIQUE_PORTFOLIO_COUNT", "checkpoint"),
        bonferroni_pruned_count=_require_int(payload, "BONFERRONI_PRUNED_COUNT", "checkpoint"),
        exact_evaluation_count=_require_int(payload, "EXACT_EVALUATION_COUNT", "checkpoint"),
        best_exact_count=_require_int(payload, "BEST_EXACT_OUTCOME_COUNT", "checkpoint"),
        best_portfolio_sha256=_require_str(payload, "BEST_PORTFOLIO_SHA256", "checkpoint"),
        best_portfolio=_json_portfolio(payload.get("BEST_PORTFOLIO"), "checkpoint"),
        best_move=_move_from_json(payload.get("BEST_MOVE")),
        best_u3_count=best_u3,
        audit_digest=_require_str(payload, "AUDIT_DIGEST", "checkpoint"),
        complete=cast(bool, payload["COMPLETE"]),
    )
    return state


def _load_seen_hashes(path: Path, expected_offset: int, expected_count: int) -> set[str]:
    if not path.is_file():
        raise ValueError("3-cycle seen-portfolio log is missing")
    raw = path.read_bytes()
    if len(raw) < expected_offset:
        raise ValueError("3-cycle seen-portfolio log is shorter than its checkpoint offset")
    committed = raw[:expected_offset]
    if len(raw) > expected_offset:
        with path.open("r+b") as stream:
            stream.truncate(expected_offset)
            stream.flush()
            os.fsync(stream.fileno())
    if committed and not committed.endswith(b"\n"):
        raise ValueError("3-cycle seen-portfolio checkpoint offset splits a hash record")
    hashes = committed.decode("ascii").splitlines()
    if any(
        len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) for digest in hashes
    ):
        raise ValueError("3-cycle seen-portfolio log contains an invalid SHA-256")
    result = set(hashes)
    if len(result) != len(hashes) or len(result) != expected_count:
        raise ValueError("3-cycle seen-portfolio log count does not match its checkpoint")
    return result


def _save_scan_checkpoint(
    checkpoint_path: Path,
    seen_hash_path: Path,
    state: ScanCheckpoint,
    pending_hashes: list[str],
    *,
    on_checkpoint: Callable[[Path, Path, ScanCheckpoint], None] | None,
) -> None:
    if pending_hashes:
        payload = "".join(f"{digest}\n" for digest in pending_hashes).encode("ascii")
        with seen_hash_path.open("ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        state.seen_log_offset += len(payload)
        pending_hashes.clear()
    r4._write_json_atomically(checkpoint_path, _scan_checkpoint_json(state))
    if on_checkpoint is not None:
        on_checkpoint(checkpoint_path, seen_hash_path, state)


def _validate_scan_state(
    state: ScanCheckpoint,
    origin: Portfolio,
    incumbent_exact_count: int,
    run2_artifact_sha256: str,
    round_number: int,
    seen_hash_count: int,
) -> None:
    if (
        state.task_id != TASK_ID
        or state.source_commit != BASE_COMMIT
        or state.source_tree != BASE_TREE
        or state.run2_artifact_sha256 != run2_artifact_sha256
        or state.round_number != round_number
        or state.origin_sha256 != r4.portfolio_sha256(origin)
        or state.origin_exact_count != incumbent_exact_count
    ):
        raise ValueError("3-cycle checkpoint identity does not match this scan")
    ticket_triple_count = len(tuple(itertools.combinations(range(20), 3)))
    if not 0 <= state.ticket_triple_index <= ticket_triple_count:
        raise ValueError("3-cycle checkpoint ticket-triple cursor is out of range")
    if not 0 <= state.operation_index < OPERATIONS_PER_TICKET_TRIPLE and not (
        state.ticket_triple_index == ticket_triple_count and state.operation_index == 0
    ):
        raise ValueError("3-cycle checkpoint operation cursor is out of range")
    if state.raw_operation_count != (
        state.ticket_triple_index * OPERATIONS_PER_TICKET_TRIPLE + state.operation_index
    ):
        raise ValueError("3-cycle checkpoint cursor disagrees with raw operation count")
    if state.unique_portfolio_count != seen_hash_count:
        raise ValueError("3-cycle checkpoint unique count disagrees with its hash log")
    if state.raw_operation_count != state.illegal_operation_count + state.legal_operation_count:
        raise ValueError("3-cycle checkpoint legal/illegal accounting does not balance")
    if state.legal_operation_count != state.duplicate_result_count + state.unique_portfolio_count:
        raise ValueError("3-cycle checkpoint legal/deduplicated accounting does not balance")
    if state.unique_portfolio_count != (
        state.bonferroni_pruned_count + state.exact_evaluation_count
    ):
        raise ValueError("3-cycle checkpoint bound/exact accounting does not balance")
    expected_complete = state.ticket_triple_index == ticket_triple_count
    if state.complete != expected_complete:
        raise ValueError("3-cycle checkpoint completion flag disagrees with its cursor")


def _incremental_u3_for_candidate(
    origin: Portfolio,
    candidate: ThreeCycleCandidate,
    base: r4.U3Components,
    old_affected_cache: dict[TicketTriple, r4.U3Components],
) -> r4.U3Components:
    return incremental_three_ticket_u3(origin, candidate, base, old_affected_cache)


def _raw_operation_identity(move: ThreeCycleMove) -> dict[str, object]:
    return {
        "ticket_triple": move.ticket_triple,
        "removal_positions": move.removal_positions,
        "orientation": move.orientation,
    }


def scan_three_cycle_neighborhood(
    origin: Sequence[Sequence[int]],
    incumbent_exact_count: int,
    *,
    checkpoint_path: Path,
    seen_hash_path: Path,
    run2_artifact_sha256: str,
    round_number: int,
    exact_scorer: Callable[[Portfolio], ExactPortfolioProbability],
    resume: bool = False,
    deadline_epoch: float | None = None,
    now_fn: Callable[[], float] = time.time,
    max_raw_operations: int | None = None,
    on_checkpoint: Callable[[Path, Path, ScanCheckpoint], None] | None = None,
) -> ScanCheckpoint:
    """Run/resume one complete fixed-origin scan with block and 60-second checkpoints."""

    normalized_origin = r4.normalize_portfolio(origin, expected_ticket_count=20)
    if raw_operation_count(len(normalized_origin)) != RAW_OPERATIONS_PER_SCAN:
        raise AssertionError("K20 3-cycle raw operation count is not 492480")
    if incumbent_exact_count < 0 or incumbent_exact_count > TOTAL_OFFICIAL_OUTCOMES:
        raise ValueError("incumbent exact score is outside the official outcome space")
    if round_number < 1:
        raise ValueError("VND round number must be positive")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    if resume:
        if not checkpoint_path.is_file():
            raise ValueError("resume requested but 3-cycle checkpoint does not exist")
        if not seen_hash_path.is_file():
            raise ValueError("resume requested but 3-cycle seen-portfolio log does not exist")
        decoded: object = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        state = _scan_state_from_json(decoded)
        seen = _load_seen_hashes(
            seen_hash_path, state.seen_log_offset, state.unique_portfolio_count
        )
        _validate_scan_state(
            state,
            normalized_origin,
            incumbent_exact_count,
            run2_artifact_sha256,
            round_number,
            len(seen),
        )
    else:
        if checkpoint_path.exists() or seen_hash_path.exists():
            raise ValueError("3-cycle checkpoint already exists; resume explicitly")
        seen_hash_path.write_bytes(b"")
        state = _initial_scan_checkpoint(
            normalized_origin, incumbent_exact_count, run2_artifact_sha256, round_number
        )
        seen: set[str] = set()
        _save_scan_checkpoint(
            checkpoint_path, seen_hash_path, state, [], on_checkpoint=on_checkpoint
        )

    if state.complete:
        return state
    if max_raw_operations is not None and max_raw_operations < 0:
        raise ValueError("max_raw_operations must be non-negative")
    if max_raw_operations == 0:
        return state

    base_components = r4.full_u3_components(normalized_origin)
    old_affected_cache: dict[TicketTriple, r4.U3Components] = {}
    pending_hashes: list[str] = []
    started_raw_count = state.raw_operation_count
    last_saved_at = now_fn()
    ticket_triples = tuple(itertools.combinations(range(20), 3))
    processed_this_call = 0

    while state.ticket_triple_index < len(ticket_triples):
        triple = ticket_triples[state.ticket_triple_index]
        moves = tuple(
            ThreeCycleMove(triple, cast(RemovalPositions, positions), orientation)
            for positions in itertools.product(range(6), repeat=3)
            for orientation in ORIENTATIONS
        )
        while state.operation_index < len(moves):
            if deadline_epoch is not None and now_fn() >= deadline_epoch:
                state.complete = False
                _save_scan_checkpoint(
                    checkpoint_path,
                    seen_hash_path,
                    state,
                    pending_hashes,
                    on_checkpoint=on_checkpoint,
                )
                return state

            move = moves[state.operation_index]
            state.raw_operation_count += 1
            processed_this_call += 1
            record = _raw_operation_identity(move)
            record["status"] = "ILLEGAL"
            try:
                candidate = _candidate_from_move(normalized_origin, move)
            except ValueError as exc:
                state.illegal_operation_count += 1
                if "no-op" in str(exc):
                    state.no_op_rejection_count += 1
                    record["status"] = "NO_OP_REJECTED"
                else:
                    record["status"] = "ILLEGAL"
                    record["reason"] = str(exc)
            else:
                state.legal_operation_count += 1
                digest = candidate.portfolio_sha256
                record["candidate_sha256"] = digest
                if digest in seen:
                    state.duplicate_result_count += 1
                    record["status"] = "DUPLICATE_RESULT"
                else:
                    seen.add(digest)
                    pending_hashes.append(digest)
                    state.unique_portfolio_count += 1
                    components = _incremental_u3_for_candidate(
                        normalized_origin, candidate, base_components, old_affected_cache
                    )
                    record["u3_outcome_count"] = components.u3
                    if r4.should_safe_prune(components.u3, incumbent_exact_count):
                        state.bonferroni_pruned_count += 1
                        record["status"] = "SAFE_BONFERRONI_PRUNE"
                    else:
                        exact = exact_scorer(candidate.portfolio)
                        exact_count = exact.official_any_prize_outcome_count
                        exact_total = exact.main_draw_count * exact.special_count
                        if exact_total != TOTAL_OFFICIAL_OUTCOMES:
                            raise ValueError(
                                "canonical exact scorer returned a non-B649 outcome space"
                            )
                        if not 0 <= exact_count <= TOTAL_OFFICIAL_OUTCOMES:
                            raise ValueError(
                                "canonical exact scorer returned an invalid outcome count"
                            )
                        if components.u3 < exact_count:
                            raise AssertionError(
                                "BONFERRONI_SAFETY_REFUTED: U3 is below canonical exact score"
                            )
                        state.exact_evaluation_count += 1
                        exact_fraction = str(exact.official_any_prize)
                        record["exact_outcome_count"] = exact_count
                        record["exact_fraction"] = exact_fraction
                        record["status"] = "EXACT_SCORED"
                        if exact_count > state.best_exact_count or (
                            exact_count == state.best_exact_count
                            and exact_count > incumbent_exact_count
                            and (state.best_move is None or move.tie_key < state.best_move.tie_key)
                        ):
                            state.best_exact_count = exact_count
                            state.best_portfolio_sha256 = digest
                            state.best_portfolio = candidate.portfolio
                            state.best_move = move
                            state.best_u3_count = components.u3

            state.audit_digest = _advance_audit_digest(state.audit_digest, record)
            state.operation_index += 1
            block_complete = state.operation_index == OPERATIONS_PER_TICKET_TRIPLE
            if block_complete:
                state.ticket_triple_index += 1
                state.operation_index = 0
            now = now_fn()
            hit_call_limit = (
                max_raw_operations is not None and processed_this_call >= max_raw_operations
            )
            hit_checkpoint_interval = now - last_saved_at >= 60
            if block_complete or hit_checkpoint_interval or hit_call_limit:
                state.complete = state.ticket_triple_index == len(ticket_triples)
                _save_scan_checkpoint(
                    checkpoint_path,
                    seen_hash_path,
                    state,
                    pending_hashes,
                    on_checkpoint=on_checkpoint,
                )
                last_saved_at = now
            if hit_call_limit:
                return state
            if block_complete:
                break
            if deadline_epoch is not None and now >= deadline_epoch:
                state.complete = False
                if state.operation_index != 0 and not block_complete:
                    _save_scan_checkpoint(
                        checkpoint_path,
                        seen_hash_path,
                        state,
                        pending_hashes,
                        on_checkpoint=on_checkpoint,
                    )
                return state

    state.complete = state.ticket_triple_index == len(ticket_triples)
    if state.complete:
        if state.raw_operation_count != RAW_OPERATIONS_PER_SCAN:
            raise AssertionError("complete 3-cycle scan did not enumerate 492480 operations")
        if state.raw_operation_count != state.illegal_operation_count + state.legal_operation_count:
            raise AssertionError("3-cycle raw/legal operation accounting does not balance")
        if (
            state.legal_operation_count
            != state.duplicate_result_count + state.unique_portfolio_count
        ):
            raise AssertionError("3-cycle legal/unique portfolio accounting does not balance")
        if state.unique_portfolio_count != (
            state.bonferroni_pruned_count + state.exact_evaluation_count
        ):
            raise AssertionError("3-cycle bound/exact accounting does not balance")
    _save_scan_checkpoint(
        checkpoint_path,
        seen_hash_path,
        state,
        pending_hashes,
        on_checkpoint=on_checkpoint,
    )
    if state.raw_operation_count < started_raw_count:
        raise AssertionError("3-cycle raw operation count moved backwards")
    return state


def select_three_cycle_bound_fixtures(
    portfolio: Sequence[Sequence[int]],
    *,
    exact_scorer: Callable[[Portfolio], ExactPortfolioProbability],
    fixture_count: int = 3,
) -> tuple[tuple[ThreeCycleCandidate, int, int], ...]:
    """Choose legal 3-cycle fixtures and discriminate U3 from exact scoring."""

    origin = r4.normalize_portfolio(portfolio, expected_ticket_count=20)
    if fixture_count <= 0:
        raise ValueError("fixture_count must be positive")
    base = r4.full_u3_components(origin)
    affected_cache: dict[TicketTriple, r4.U3Components] = {}
    seen: set[str] = set()
    fixtures: list[tuple[ThreeCycleCandidate, int, int]] = []
    strict_bound_gap = False
    for move in iter_three_cycle_moves(20):
        try:
            candidate = _candidate_from_move(origin, move)
        except ValueError:
            continue
        if candidate.portfolio_sha256 in seen:
            continue
        seen.add(candidate.portfolio_sha256)
        bound = incremental_three_ticket_u3(origin, candidate, base, affected_cache).u3
        exact = exact_scorer(candidate.portfolio).official_any_prize_outcome_count
        full_bound = r4.full_u3_components(candidate.portfolio).u3
        if bound != full_bound:
            raise AssertionError("3-ticket incremental U3 differs from full recomputation")
        if bound < exact:
            raise AssertionError("BONFERRONI_SAFETY_REFUTED on a 3-ticket fixture")
        fixtures.append((candidate, bound, exact))
        strict_bound_gap |= bound > exact
        if len(fixtures) >= fixture_count and strict_bound_gap:
            break
    if len(fixtures) < fixture_count or not strict_bound_gap:
        raise AssertionError("3-ticket fixtures did not discriminate a safe U3 upper bound")
    return tuple(fixtures)


def _scan_record(state: ScanCheckpoint) -> dict[str, object]:
    return {
        "round": state.round_number,
        "complete": state.complete,
        "raw_operation_count": state.raw_operation_count,
        "legal_operation_count": state.legal_operation_count,
        "illegal_operation_count": state.illegal_operation_count,
        "no_op_rejection_count": state.no_op_rejection_count,
        "duplicate_result_count": state.duplicate_result_count,
        "unique_portfolio_count": state.unique_portfolio_count,
        "bonferroni_pruned_count": state.bonferroni_pruned_count,
        "exact_evaluation_count": state.exact_evaluation_count,
        "best_exact_outcome_count": state.best_exact_count,
        "best_portfolio_sha256": state.best_portfolio_sha256,
        "best_move": _move_to_json(state.best_move),
        "audit_digest": state.audit_digest,
    }


def _relative_delta(delta: int, starting_exact: int) -> str:
    if starting_exact == 0:
        return "UNDEFINED_STARTING_SCORE_ZERO"
    return str(Fraction(delta, starting_exact))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_artifact_hashes(
    repository: Path,
    paths: Iterable[str],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in sorted(set(paths)):
        artifact = Path(relative)
        path = artifact if artifact.is_absolute() else repository / artifact
        if path.is_file():
            hashes[relative] = _sha256_file(path)
    return hashes


def _write_manifest(
    repository: Path,
    manifest_path: Path,
    *,
    command_argv: list[str],
    command_argv_history: list[list[str]],
    run2_artifact_sha256: str,
    runtime_artifact_paths: Iterable[str],
    canonical_result_path: Path,
    manifest_status: str,
) -> None:
    try:
        manifest_label = str(manifest_path.relative_to(repository))
    except ValueError:
        manifest_label = str(manifest_path)
    artifact_paths = sorted(set(runtime_artifact_paths) - {manifest_label})
    artifact_hashes = _runtime_artifact_hashes(repository, artifact_paths)
    if canonical_result_path.is_file():
        artifact_hashes[str(canonical_result_path.relative_to(repository))] = _sha256_file(
            canonical_result_path
        )
    payload: dict[str, object] = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "source_commit": BASE_COMMIT,
        "source_tree": BASE_TREE,
        "terminal_evidence_locator": str(R4_RUN2_PATH),
        "terminal_evidence_sha256": run2_artifact_sha256,
        "command_argv": command_argv,
        "command_argv_history": command_argv_history,
        "canonical_result_relative_path": str(canonical_result_path.relative_to(repository)),
        "runtime_artifact_relative_paths": artifact_paths,
        "sha256_by_artifact": dict(sorted(artifact_hashes.items())),
        "digest_construction_procedure": (
            "SHA-256 is computed over the raw bytes of each listed artifact. "
            "The terminal evidence digest is over the exact named run2 JSON bytes. "
            "Portfolio SHA-256 is over UTF-8 compact JSON for the normalized portfolio. "
            "The manifest excludes its own digest."
        ),
        "manifest_status": manifest_status,
        "updated_at_epoch_seconds": time.time(),
    }
    r4._write_json_atomically(manifest_path, payload)


def _save_vnd_state(path: Path, state: dict[str, object]) -> None:
    r4._write_json_atomically(path, state)


def _load_vnd_state(path: Path, run2_sha256: str, starting: StartingPortfolio) -> dict[str, object]:
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("VND run checkpoint root must be an object")
    state = cast(dict[str, object], decoded)
    if (
        state.get("schema_version") != 1
        or state.get("task_id") != TASK_ID
        or state.get("source_commit") != BASE_COMMIT
        or state.get("source_tree") != BASE_TREE
        or state.get("run2_artifact_sha256") != run2_sha256
        or state.get("starting_portfolio_sha256") != starting.portfolio_sha256
        or state.get("starting_exact_outcome_count") != starting.exact_outcome_count
    ):
        raise ValueError("VND run checkpoint identity does not match the authorized task")
    current = _json_portfolio(state.get("current_portfolio"), "VND run checkpoint")
    if r4.portfolio_sha256(current) != state.get("current_portfolio_sha256"):
        raise ValueError("VND run checkpoint current portfolio digest is invalid")
    if type(state.get("current_exact_outcome_count")) is not int:
        raise ValueError("VND run checkpoint exact score is invalid")
    if (
        state.get("round_cap") != VND_ROUND_CAP
        or state.get("wall_clock_cap_seconds") != WALL_CLOCK_CAP_SECONDS
    ):
        raise ValueError("VND run checkpoint bounds differ from the authorized packet")
    return state


def _new_vnd_state(starting: StartingPortfolio, now: float) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "source_commit": BASE_COMMIT,
        "source_tree": BASE_TREE,
        "run2_artifact_sha256": starting.run2_artifact_sha256,
        "starting_portfolio_sha256": starting.portfolio_sha256,
        "starting_exact_outcome_count": starting.exact_outcome_count,
        "started_at_epoch_seconds": now,
        "round_cap": VND_ROUND_CAP,
        "wall_clock_cap_seconds": WALL_CLOCK_CAP_SECONDS,
        "next_action": "THREE_TICKET_SCAN",
        "current_round": 1,
        "rounds_completed": 0,
        "current_portfolio": starting.portfolio,
        "current_portfolio_sha256": starting.portfolio_sha256,
        "current_exact_outcome_count": starting.exact_outcome_count,
        "accepted_three_ticket_moves": [],
        "accepted_two_ticket_reclosure_move_count": 0,
        "reclosure_records": [],
        "completed_scan_records": [],
        "active_reclosure": None,
        "incomplete_scan_record": None,
        "terminal_disposition": None,
        "combined_local_optimum_status": "NOT_PROVEN",
        "global_k20_optimum_status": "UNKNOWN",
        "runtime_artifact_paths": [],
        "command_argv": [],
        "command_argv_history": [],
    }


def _as_list_of_dicts(state: dict[str, object], key: str) -> list[dict[str, object]]:
    value = state.get(key)
    if not isinstance(value, list):
        raise ValueError(f"VND run checkpoint {key} must be an array of objects")
    items = cast(list[object], value)
    if any(not isinstance(item, dict) for item in items):
        raise ValueError(f"VND run checkpoint {key} must be an array of objects")
    return cast(list[dict[str, object]], value)


def _runtime_paths(state: dict[str, object]) -> list[str]:
    value = state.get("runtime_artifact_paths")
    if not isinstance(value, list):
        raise ValueError("VND run checkpoint runtime artifact paths are invalid")
    items = cast(list[object], value)
    if any(type(item) is not str for item in items):
        raise ValueError("VND run checkpoint runtime artifact paths are invalid")
    return cast(list[str], value)


def _add_runtime_path(state: dict[str, object], repository: Path, path: Path) -> None:
    try:
        relative = str(path.relative_to(repository))
    except ValueError:
        relative = str(path)
    paths = _runtime_paths(state)
    if relative not in paths:
        paths.append(relative)


def _record_accepted_three_cycle(
    state: dict[str, object],
    move: ThreeCycleMove,
    candidate: ThreeCycleCandidate,
    prior_exact: int,
    new_exact: int,
) -> None:
    if new_exact <= prior_exact:
        raise ValueError("a 3-ticket move is accepted only for a strict exact improvement")
    records = _as_list_of_dicts(state, "accepted_three_ticket_moves")
    delta = new_exact - prior_exact
    records.append(
        {
            "round": state["current_round"],
            "ticket_triple": move.ticket_triple,
            "removal_positions": move.removal_positions,
            "removed_numbers": candidate.removed_numbers,
            "cycle_orientation": move.orientation,
            "added_numbers": candidate.added_numbers,
            "prior_exact_outcome_count": prior_exact,
            "new_exact_outcome_count": new_exact,
            "absolute_delta": delta,
            "relative_delta": _relative_delta(delta, prior_exact),
            "portfolio_sha256": candidate.portfolio_sha256,
        }
    )
    state["accepted_three_ticket_moves"] = records


def _accept_three_cycle(state: dict[str, object], scan: ScanCheckpoint) -> None:
    if not scan.complete or scan.best_move is None:
        raise ValueError("only a complete improving 3-cycle scan can be accepted")
    prior_exact = cast(int, state["current_exact_outcome_count"])
    if scan.best_exact_count <= prior_exact:
        raise ValueError("3-cycle scan did not produce a strict exact improvement")
    candidate = _candidate_from_move(cast(Portfolio, state["current_portfolio"]), scan.best_move)
    if (
        candidate.portfolio_sha256 != scan.best_portfolio_sha256
        or candidate.portfolio != scan.best_portfolio
    ):
        raise ValueError("best 3-cycle move identity does not reconstruct its portfolio")
    _record_accepted_three_cycle(
        state, scan.best_move, candidate, prior_exact, scan.best_exact_count
    )
    state["current_portfolio"] = scan.best_portfolio
    state["current_portfolio_sha256"] = scan.best_portfolio_sha256
    state["current_exact_outcome_count"] = scan.best_exact_count
    state["next_action"] = "R4_TWO_TICKET_RECLOSURE"
    state["active_reclosure"] = {
        "round": state["current_round"],
        "starting_exact_outcome_count": scan.best_exact_count,
        "starting_portfolio_sha256": scan.best_portfolio_sha256,
        "accepted_move_count": 0,
        "scan_index": 1,
    }


def _result_from_state(
    state: dict[str, object],
    starting: StartingPortfolio,
    *,
    current_scan: ScanCheckpoint | None = None,
) -> dict[str, object]:
    current = _json_portfolio(state.get("current_portfolio"), "VND result")
    current_exact = cast(int, state["current_exact_outcome_count"])
    delta = current_exact - starting.exact_outcome_count
    completed_records = _as_list_of_dicts(state, "completed_scan_records")
    scan_records = list(completed_records)
    if current_scan is not None and not current_scan.complete:
        scan_records.append(_scan_record(current_scan))
    elif current_scan is None and isinstance(state.get("incomplete_scan_record"), dict):
        scan_records.append(cast(dict[str, object], state["incomplete_scan_record"]))
    totals = {
        key: sum(cast(int, record.get(key, 0)) for record in scan_records)
        for key in (
            "raw_operation_count",
            "legal_operation_count",
            "unique_portfolio_count",
            "bonferroni_pruned_count",
            "exact_evaluation_count",
        )
    }
    moves = _as_list_of_dicts(state, "accepted_three_ticket_moves")
    closures = _as_list_of_dicts(state, "reclosure_records")
    disposition = cast(str | None, state.get("terminal_disposition"))
    if disposition is None:
        disposition = "BOUNDED_PROGRESS_NOT_CONVERGED"
    combined = cast(str, state["combined_local_optimum_status"])
    return {
        "TASK_STATUS": (
            "COMPLETE"
            if combined == "PROVEN_FOR_DEFINED_2TICKET_PLUS_3CYCLE_NEIGHBORHOODS"
            else "BOUNDED_PROGRESS"
        ),
        "TASK_ID": TASK_ID,
        "RUN_ID": RUN_ID,
        "BASE_HEAD": BASE_COMMIT,
        "BASE_TREE": BASE_TREE,
        "SOURCE_COMMIT": BASE_COMMIT,
        "SOURCE_TREE": BASE_TREE,
        "TERMINAL_EVIDENCE_LOCATOR": str(R4_RUN2_PATH),
        "TERMINAL_EVIDENCE_SHA256": starting.run2_artifact_sha256,
        "START_PORTFOLIO_SHA256": starting.portfolio_sha256,
        "START_EXACT": starting.exact_outcome_count,
        "RAW_3CYCLE_OPERATIONS_PER_SCAN": RAW_OPERATIONS_PER_SCAN,
        "RAW_OPERATION_COUNT": totals["raw_operation_count"],
        "LEGAL_3CYCLE_OPERATIONS": totals["legal_operation_count"],
        "UNIQUE_3CYCLE_PORTFOLIOS": totals["unique_portfolio_count"],
        "BONFERRONI_PRUNED": totals["bonferroni_pruned_count"],
        "EXACT_EVALUATIONS": totals["exact_evaluation_count"],
        "VND_ROUNDS_COMPLETED": state["rounds_completed"],
        "VND_SCAN_RECORDS": scan_records,
        "ACCEPTED_3TICKET_MOVES": moves,
        "ACCEPTED_2TICKET_RECLOSURE_MOVES": state["accepted_two_ticket_reclosure_move_count"],
        "TWO_TICKET_RECLOSURES": closures,
        "INCOMPLETE_TWO_TICKET_RECLOSURE": state.get("incomplete_reclosure_record"),
        "FINAL_EXACT": current_exact,
        "ABSOLUTE_DELTA": delta,
        "RELATIVE_DELTA": _relative_delta(delta, starting.exact_outcome_count),
        "FINAL_PORTFOLIO": current,
        "FINAL_PORTFOLIO_SHA256": r4.portfolio_sha256(current),
        "FINAL_DISPOSITION": disposition,
        "COMBINED_LOCAL_OPTIMUM_STATUS": combined,
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "BONFERRONI_FILTER": "REUSED_R4_U3_SAFE_UPPER_BOUND",
        "EXACT_ACCEPTANCE_AUTHORITY": "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT",
        "ROUND_CAP": VND_ROUND_CAP,
        "WALL_CLOCK_CAP_SECONDS": WALL_CLOCK_CAP_SECONDS,
        "R4_2TICKET_SEMANTICS_CHANGED": False,
        "OFFICIAL_ANY_PRIZE_SEMANTICS_CHANGED": False,
        "NEXT_TASK_STARTED": "NO",
    }


def _record_closure_result(
    state: dict[str, object],
    *,
    complete: bool,
    accepted_move_count: int,
) -> None:
    active = state.get("active_reclosure")
    if not isinstance(active, dict):
        raise ValueError("VND state has no active R4 two-ticket reclosure")
    active_payload = cast(dict[str, object], active)
    start_exact = active_payload.get("starting_exact_outcome_count")
    if type(start_exact) is not int:
        raise ValueError("R4 reclosure starting exact score is invalid")
    portfolio = _json_portfolio(state.get("current_portfolio"), "R4 reclosure")
    record: dict[str, object] = {
        "round": active_payload.get("round"),
        "starting_exact_score": start_exact,
        "ending_exact_score": state["current_exact_outcome_count"],
        "accepted_2ticket_move_count": accepted_move_count,
        "final_portfolio_sha256": r4.portfolio_sha256(portfolio),
        "complete": complete,
    }
    if complete:
        closures = _as_list_of_dicts(state, "reclosure_records")
        closures.append(record)
        state["reclosure_records"] = closures
    else:
        state["incomplete_reclosure_record"] = record


def run_task(
    repository: Path,
    *,
    run_data_dir: Path,
    canonical_result_path: Path,
    resume: bool = False,
    command_argv: list[str] | None = None,
    now_fn: Callable[[], float] = time.time,
    wall_clock_cap_seconds: int = WALL_CLOCK_CAP_SECONDS,
    round_cap: int = VND_ROUND_CAP,
) -> dict[str, object]:
    """Verify the exact R4 start, run bounded VND, and seal its result and manifest."""

    if repository.resolve() != Path(__file__).resolve().parents[3]:
        raise ValueError("runner repository root differs from this exact worktree")
    if wall_clock_cap_seconds != WALL_CLOCK_CAP_SECONDS or round_cap != VND_ROUND_CAP:
        raise ValueError("VND bounds must match the authorized 4-round / 6-hour packet")
    if _git_stdout(repository, ["rev-parse", "HEAD"]) != BASE_COMMIT:
        raise ValueError("runner HEAD differs from the exact pinned R4 source commit")
    if _git_stdout(repository, ["rev-parse", "HEAD^{tree}"]) != BASE_TREE:
        raise ValueError("runner HEAD tree differs from the exact pinned R4 source tree")

    starting = load_run2_starting_portfolio(repository)
    run_data_dir.mkdir(parents=True, exist_ok=True)
    if (
        canonical_result_path
        != repository / "docs/research/b649-k20-3ticket-cyclic-cross-swap-vnd-r1-result.json"
    ):
        raise ValueError("canonical result path differs from the authorized packet")
    state_path = run_data_dir / "vnd-state.json"
    manifest_path = run_data_dir / "run-manifest.json"
    try:
        state_rel = str(state_path.relative_to(repository))
        manifest_rel = str(manifest_path.relative_to(repository))
    except ValueError:
        state_rel = str(state_path)
        manifest_rel = str(manifest_path)
    if resume:
        if not state_path.is_file():
            raise ValueError("resume requested but VND state checkpoint does not exist")
        state = _load_vnd_state(state_path, starting.run2_artifact_sha256, starting)
        if state.get("next_action") == "DONE":
            decoded_result: object = json.loads(canonical_result_path.read_text(encoding="utf-8"))
            if not isinstance(decoded_result, dict):
                raise ValueError("terminal VND result must be a JSON object")
            return cast(dict[str, object], decoded_result)
    else:
        if state_path.exists():
            raise ValueError("VND state checkpoint already exists; pass --resume explicitly")
        state = _new_vnd_state(starting, now_fn())
        state["runtime_artifact_paths"] = [state_rel]
        state["command_argv"] = command_argv or []
        state["command_argv_history"] = [command_argv or []]
        _save_vnd_state(state_path, state)

    runtime_paths = _runtime_paths(state)
    if state_rel not in runtime_paths:
        runtime_paths.append(state_rel)
    if manifest_rel not in runtime_paths:
        runtime_paths.append(manifest_rel)
    if command_argv is not None:
        history_value = state.get("command_argv_history", [])
        if not isinstance(history_value, list):
            raise ValueError("VND command argv history is invalid")
        history = cast(list[list[str]], history_value)
        if command_argv not in history:
            history.append(command_argv)
        state["command_argv_history"] = history
        state["command_argv"] = command_argv
    command_argv = cast(list[str], state.get("command_argv", []))
    command_history = cast(list[list[str]], state.get("command_argv_history", []))
    last_manifest_update = [float("-inf")]

    def write_manifest(manifest_status: str, *, force: bool = False) -> None:
        now = now_fn()
        if not force and now - last_manifest_update[0] < 60:
            return
        _write_manifest(
            repository,
            manifest_path,
            command_argv=command_argv,
            command_argv_history=command_history,
            run2_artifact_sha256=starting.run2_artifact_sha256,
            runtime_artifact_paths=runtime_paths,
            canonical_result_path=canonical_result_path,
            manifest_status=manifest_status,
        )
        last_manifest_update[0] = now

    write_manifest("IN_PROGRESS", force=True)
    _save_vnd_state(state_path, state)

    draws = r4_runner._canonical_draw_space()
    scorer = canonical_exact_scorer(draws)
    started_at = cast(float, state["started_at_epoch_seconds"])
    deadline = started_at + wall_clock_cap_seconds
    latest_scan: ScanCheckpoint | None = None
    while state.get("next_action") != "DONE":
        if now_fn() >= deadline:
            if state.get("next_action") == "R4_TWO_TICKET_RECLOSURE":
                active_value = state.get("active_reclosure")
                if isinstance(active_value, dict):
                    active_payload = cast(dict[str, object], active_value)
                    _record_closure_result(
                        state,
                        complete=False,
                        accepted_move_count=cast(int, active_payload["accepted_move_count"]),
                    )
            state["terminal_disposition"] = "BOUNDED_PROGRESS_NOT_CONVERGED"
            state["combined_local_optimum_status"] = "NOT_PROVEN"
            _save_vnd_state(state_path, state)
            break
        current_portfolio = _json_portfolio(state.get("current_portfolio"), "VND current state")
        current_exact = cast(int, state["current_exact_outcome_count"])
        current_round = cast(int, state["current_round"])
        if state.get("next_action") == "THREE_TICKET_SCAN":
            scan_dir = run_data_dir / f"three-cycle-round-{current_round:02d}"
            scan_checkpoint = scan_dir / "checkpoint.json"
            seen_hash_path = scan_dir / "seen-portfolios.sha256"
            for path in (scan_checkpoint, seen_hash_path):
                _add_runtime_path(state, repository, path)
            _save_vnd_state(state_path, state)

            def on_scan_checkpoint(
                checkpoint: Path, seen_path: Path, _scan_state: ScanCheckpoint
            ) -> None:
                _add_runtime_path(state, repository, checkpoint)
                _add_runtime_path(state, repository, seen_path)
                _save_vnd_state(state_path, state)
                write_manifest("IN_PROGRESS")

            latest_scan = scan_three_cycle_neighborhood(
                current_portfolio,
                current_exact,
                checkpoint_path=scan_checkpoint,
                seen_hash_path=seen_hash_path,
                run2_artifact_sha256=starting.run2_artifact_sha256,
                round_number=current_round,
                exact_scorer=scorer,
                resume=scan_checkpoint.is_file(),
                deadline_epoch=deadline,
                now_fn=now_fn,
                on_checkpoint=on_scan_checkpoint,
            )
            if not latest_scan.complete:
                state["incomplete_scan_record"] = _scan_record(latest_scan)
                state["terminal_disposition"] = "BOUNDED_PROGRESS_NOT_CONVERGED"
                state["combined_local_optimum_status"] = "NOT_PROVEN"
                _save_vnd_state(state_path, state)
                break

            scans = _as_list_of_dicts(state, "completed_scan_records")
            scans.append(_scan_record(latest_scan))
            state["completed_scan_records"] = scans
            state["rounds_completed"] = current_round
            if latest_scan.best_exact_count <= current_exact:
                state["terminal_disposition"] = (
                    "NO_3TICKET_IMPROVEMENT_FROM_R4_LOCAL_OPTIMUM"
                    if not _as_list_of_dicts(state, "accepted_three_ticket_moves")
                    else "STRICT_IMPROVEMENT_FOUND_AND_VND_CONVERGED"
                )
                state["combined_local_optimum_status"] = (
                    "PROVEN_FOR_DEFINED_2TICKET_PLUS_3CYCLE_NEIGHBORHOODS"
                )
                state["next_action"] = "DONE"
                _save_vnd_state(state_path, state)
                break

            _accept_three_cycle(state, latest_scan)
            _save_vnd_state(state_path, state)
            continue

        if state.get("next_action") == "R4_TWO_TICKET_RECLOSURE":
            active = state.get("active_reclosure")
            if not isinstance(active, dict):
                raise ValueError("VND state requires an active R4 reclosure record")
            active_payload = cast(dict[str, object], active)
            scan_index = active_payload.get("scan_index")
            if type(scan_index) is not int or scan_index < 1:
                raise ValueError("R4 reclosure scan index is invalid")
            closure_path = run_data_dir / (
                f"r4-reclosure-round-{current_round:02d}-scan-{scan_index:03d}.json"
            )
            _add_runtime_path(state, repository, closure_path)
            _save_vnd_state(state_path, state)
            closure_task_id = f"{TASK_ID}_R{current_round}_S{scan_index}"
            r4_state = r4.run_cross_swap_sweep(
                current_portfolio,
                current_exact,
                checkpoint_path=closure_path,
                exact_scorer=scorer,
                task_id=closure_task_id,
                resume=closure_path.is_file(),
                checkpoint_every=25,
                max_raw_moves=25,
                expected_ticket_count=20,
            )
            write_manifest("IN_PROGRESS")
            if not r4_state.complete:
                if now_fn() >= deadline:
                    _record_closure_result(
                        state,
                        complete=False,
                        accepted_move_count=cast(int, active["accepted_move_count"]),
                    )
                    state["terminal_disposition"] = "BOUNDED_PROGRESS_NOT_CONVERGED"
                    state["combined_local_optimum_status"] = "NOT_PROVEN"
                    _save_vnd_state(state_path, state)
                    break
                continue
            if r4_state.best_exact_count > current_exact:
                active["accepted_move_count"] = cast(int, active["accepted_move_count"]) + 1
                active["scan_index"] = scan_index + 1
                state["current_portfolio"] = r4_state.best_portfolio
                state["current_portfolio_sha256"] = r4_state.best_portfolio_sha256
                state["current_exact_outcome_count"] = r4_state.best_exact_count
                state["accepted_two_ticket_reclosure_move_count"] = (
                    cast(int, state["accepted_two_ticket_reclosure_move_count"]) + 1
                )
                _save_vnd_state(state_path, state)
                continue

            accepted_count = cast(int, active["accepted_move_count"])
            _record_closure_result(state, complete=True, accepted_move_count=accepted_count)
            state["active_reclosure"] = None
            if cast(int, state["rounds_completed"]) >= round_cap:
                state["terminal_disposition"] = "BOUNDED_PROGRESS_NOT_CONVERGED"
                state["combined_local_optimum_status"] = "NOT_PROVEN"
                state["next_action"] = "DONE"
            else:
                state["current_round"] = cast(int, state["rounds_completed"]) + 1
                state["next_action"] = "THREE_TICKET_SCAN"
            _save_vnd_state(state_path, state)
            continue

        raise ValueError(f"unknown VND next action: {state.get('next_action')}")

    result = _result_from_state(state, starting, current_scan=latest_scan)
    result["START_EXACT_FRACTION"] = starting.exact_fraction
    result["FINAL_EXACT_FRACTION"] = str(
        Fraction(cast(int, result["FINAL_EXACT"]), TOTAL_OFFICIAL_OUTCOMES)
    )
    result["R4_INCUMBENT_ARTIFACT_BLOB"] = starting.incumbent_artifact_blob
    result["R4_INCUMBENT_ARTIFACT_SHA256"] = starting.incumbent_artifact_sha256
    result["R4_INCUMBENT_SOURCE_PATH"] = starting.incumbent_source_path
    result["STARTED_AT_EPOCH_SECONDS"] = state["started_at_epoch_seconds"]
    result["COMPLETED_AT_EPOCH_SECONDS"] = now_fn()
    _save_vnd_state(state_path, state)
    _write_json_result(canonical_result_path, result)
    write_manifest(
        "COMPLETE"
        if state.get("combined_local_optimum_status")
        == "PROVEN_FOR_DEFINED_2TICKET_PLUS_3CYCLE_NEIGHBORHOODS"
        else "BOUNDED_PROGRESS_NOT_CONVERGED",
        force=True,
    )
    return result


def _write_json_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    r4._write_json_atomically(path, payload)
