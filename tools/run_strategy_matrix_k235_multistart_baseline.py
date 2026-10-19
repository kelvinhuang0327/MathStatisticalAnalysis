"""Run the canonical exact one-exchange baseline for k=2, 3, and 5.

The freeze phase materializes four deterministic legal starts per native
lottery/cardinality cell without evaluating the exact objective.  The execute
phase reads that immutable manifest and runs the existing exact
best-improvement one-number-exchange ascent once for every retained start.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.research.cyclic_sidon_shift import (
    sidon_shift_portfolio as sidon_shift_portfolio_b649,
)
from lottolab.research.cyclic_sidon_shift_p638 import (
    sidon_shift_portfolio as sidon_shift_portfolio_p638,
)
from lottolab.research.cyclic_sidon_shift_t539 import (
    sidon_shift_portfolio as sidon_shift_portfolio_t539,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    canonicalize_portfolio,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    ExactOneExchangeAscentIteration,
    ExactOneExchangeAscentResult,
    iterative_exact_one_exchange_ascent,
)

STUDY_ID = "STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1"
TASK_ID = "STRATEGY_MATRIX_K235_MULTISTART_BASELINE_R1"
OWNER_AUTHORIZATION = "AUTHORIZE_STRATEGY_MATRIX_K235_MULTISTART_BASELINE_R1"
REFINEMENT_METHOD_ID = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
OBJECTIVE_ID = "EXACT_PORTFOLIO_M3_PLUS_COVERAGE"

PINNED_BASE_COMMIT = "07a5c3479123c03fd91b6f1ae2402046b5f16c2a"
PINNED_BASE_TREE = "cff549183e67ad49f12afb5076a11b1f8b712dde"
REQUESTED_K_SCOPE = (2, 3, 5)
SUPPORTED_K_SCOPE = (2, 3, 5)
MAX_CPU_WORKERS = 2

START_IDS = (
    "CYCLIC_SIDON_SHIFT_OFFSET0_V1",
    "CYCLIC_SIDON_SHIFT_OFFSET1_V1",
    "CYCLIC_SIDON_SHIFT_OFFSET2_V1",
    "CYCLIC_SIDON_SHIFT_OFFSET3_V1",
)
START_OFFSETS = (0, 1, 2, 3)

RESULTS_DIR = Path("docs/research/matrix-native-results")
PREREGISTRATION_PATH = RESULTS_DIR / (
    "strategy-matrix-k235-multistart-baseline-v1-preregistration.md"
)
START_MANIFEST_PATH = RESULTS_DIR / (
    "strategy-matrix-k235-multistart-baseline-v1-starts.json"
)
OUTPUT_PATH = RESULTS_DIR / "strategy-matrix-k235-multistart-baseline-v1-result.json"

# These two locks are filled after the preregistration and objective-free start
# manifest are materialized, before execute() is allowed to run.
LOCKED_PREREGISTRATION_SHA256 = (
    "3a842c8b4a16a6427216b187317dba5edc49638b8cd39f9ea5a3b70b351b4a98"
)
LOCKED_START_MANIFEST_SHA256 = (
    "107cb53080b45569c761a81ecd6c5924236f4376e69596c115baac41bb60acfc"
)

LOCKED_SOURCE_FILE_SHA256 = {
    "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py": (
        "01e634924797355d4f19487a7abfaeed8910bc3b0c5ee8a6d95ebe617a368577"
    ),
    "src/lottolab/research/cyclic_sidon_shift.py": (
        "b4b9891c076bf403efd0b3072d52a2547f2d817580926ac97099d07eb27e281a"
    ),
    "src/lottolab/research/cyclic_sidon_shift_t539.py": (
        "4e950e25618876b3ff4aed426e26ad1800ab6f22550a88061087010766a426dd"
    ),
    "src/lottolab/research/cyclic_sidon_shift_p638.py": (
        "0c7a686b89554898a0bd7d8fb60b15aa8b658275d37f591a4fa04e3c65532d56"
    ),
}

TicketConstructor = Callable[[int], Portfolio]


@dataclass(frozen=True, slots=True)
class StructureSpec:
    structure_id: str
    lottery_type: str
    zone: str | None
    pool_size: int
    draw_size: int
    primary_event: str
    cyclic_constructor: TicketConstructor


@dataclass(frozen=True, slots=True)
class SearchTask:
    structure_id: str
    k: int
    pool_size: int
    draw_size: int
    start_id: str
    seed_portfolio: Portfolio


@dataclass(frozen=True, slots=True)
class CompletedStart:
    structure_id: str
    k: int
    start_id: str
    ascent: ExactOneExchangeAscentResult


STRUCTURES: tuple[StructureSpec, ...] = (
    StructureSpec(
        structure_id="BIG_LOTTO",
        lottery_type="BIG_LOTTO",
        zone=None,
        pool_size=49,
        draw_size=6,
        primary_event="M3_PLUS",
        cyclic_constructor=sidon_shift_portfolio_b649,
    ),
    StructureSpec(
        structure_id="DAILY_539",
        lottery_type="DAILY_539",
        zone=None,
        pool_size=39,
        draw_size=5,
        primary_event="M3_PLUS",
        cyclic_constructor=sidon_shift_portfolio_t539,
    ),
    StructureSpec(
        structure_id="POWER_LOTTO_ZONE1",
        lottery_type="POWER_LOTTO",
        zone="ZONE1",
        pool_size=38,
        draw_size=6,
        primary_event="ZONE1_M3_PLUS",
        cyclic_constructor=sidon_shift_portfolio_p638,
    ),
)


def canonical_json_bytes(payload: object) -> bytes:
    """Return deterministic pretty JSON bytes with one final LF."""

    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def portfolio_sha256(portfolio: Portfolio) -> str:
    return sha256_bytes(json.dumps(portfolio, separators=(",", ":")).encode("utf-8"))


def rational(value: Fraction) -> dict[str, int | str]:
    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def _portfolio_json(portfolio: Portfolio) -> list[list[int]]:
    return [list(ticket) for ticket in portfolio]


def _parse_portfolio(
    payload: object,
    *,
    locator: str,
    pool_size: int,
    draw_size: int,
    k: int,
) -> Portfolio:
    if not isinstance(payload, list):
        raise ValueError(f"{locator} must be an array")
    tickets: list[tuple[int, ...]] = []
    for ticket_index, raw_ticket in enumerate(cast(list[object], payload)):
        if not isinstance(raw_ticket, list):
            raise ValueError(f"{locator}[{ticket_index}] must be an array")
        raw_numbers = cast(list[object], raw_ticket)
        if any(type(number) is not int for number in raw_numbers):
            raise ValueError(f"{locator}[{ticket_index}] contains a non-integer")
        tickets.append(tuple(cast(list[int], raw_numbers)))
    portfolio = canonicalize_portfolio(tickets)
    validate_portfolio(
        portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
        ticket_count=k,
    )
    return portfolio


def validate_portfolio(
    portfolio: Portfolio,
    *,
    pool_size: int,
    draw_size: int,
    ticket_count: int,
) -> None:
    if len(portfolio) != ticket_count or len(set(portfolio)) != ticket_count:
        raise ValueError(f"portfolio must contain exactly {ticket_count} unique tickets")
    if portfolio != canonicalize_portfolio(portfolio):
        raise ValueError("portfolio must use canonical ticket order")
    for ticket in portfolio:
        if len(ticket) != draw_size or len(set(ticket)) != draw_size:
            raise ValueError("illegal ticket shape")
        if ticket != tuple(sorted(ticket)):
            raise ValueError("ticket must be ascending")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError(f"ticket number outside 1..{pool_size}")


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_current_base_identity() -> dict[str, str]:
    observed = {
        "commit": _git_value("rev-parse", f"{PINNED_BASE_COMMIT}^{{commit}}"),
        "tree": _git_value("rev-parse", f"{PINNED_BASE_COMMIT}^{{tree}}"),
    }
    if observed != {"commit": PINNED_BASE_COMMIT, "tree": PINNED_BASE_TREE}:
        raise ValueError(f"CANONICAL_BASE_IDENTITY_MISMATCH: {observed}")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PINNED_BASE_COMMIT, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("CANONICAL_BASE_ANCESTRY_MISMATCH")
    return observed


def verify_file_identities(expected: Mapping[str, str]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for raw_path, expected_sha256 in expected.items():
        actual_sha256 = sha256_file(Path(raw_path))
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"FILE_IDENTITY_MISMATCH {raw_path}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        observed[raw_path] = actual_sha256
    return observed


def _mapping(payload: object, *, locator: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{locator} must be an object")
    return cast(dict[str, Any], payload)


def _frozen_starts(spec: StructureSpec, k: int) -> dict[str, Portfolio]:
    cyclic_family = spec.cyclic_constructor(k + max(START_OFFSETS))
    starts: dict[str, Portfolio] = {}
    for start_id, offset in zip(START_IDS, START_OFFSETS, strict=True):
        starts[start_id] = canonicalize_portfolio(cyclic_family[offset : offset + k])
    return starts


def build_start_manifest() -> dict[str, object]:
    """Build all starts without importing or invoking the exact objective evaluator."""

    base_identity = verify_current_base_identity()
    source_identities = verify_file_identities(LOCKED_SOURCE_FILE_SHA256)
    structures: dict[str, object] = {}
    for spec in STRUCTURES:
        per_k: dict[str, object] = {}
        for k in SUPPORTED_K_SCOPE:
            starts_by_id = _frozen_starts(spec, k)
            starts: list[dict[str, object]] = []
            start_ids_by_hash: defaultdict[str, list[str]] = defaultdict(list)
            for start_id, offset in zip(START_IDS, START_OFFSETS, strict=True):
                portfolio = starts_by_id[start_id]
                validate_portfolio(
                    portfolio,
                    pool_size=spec.pool_size,
                    draw_size=spec.draw_size,
                    ticket_count=k,
                )
                start_hash = portfolio_sha256(portfolio)
                start_ids_by_hash[start_hash].append(start_id)
                starts.append(
                    {
                        "CONSTRUCTOR_OR_SOURCE_ID": start_id,
                        "RANDOM_DERIVED": False,
                        "SEED_PORTFOLIO": _portfolio_json(portfolio),
                        "SEED_PORTFOLIO_SHA256": start_hash,
                        "START_ID": start_id,
                        "START_OFFSET": offset,
                    }
                )
            if len(start_ids_by_hash) != len(START_IDS):
                raise ValueError(f"START_PORTFOLIOS_NOT_DISTINCT {spec.structure_id} k={k}")
            per_k[str(k)] = {
                "START_COUNT": len(starts),
                "STARTS": starts,
                "UNIQUE_START_PORTFOLIO_COUNT": len(start_ids_by_hash),
            }
        structures[spec.structure_id] = {
            "draw_size": spec.draw_size,
            "lottery_type": spec.lottery_type,
            "per_k": per_k,
            "pool_size": spec.pool_size,
            "primary_event": spec.primary_event,
            "zone": spec.zone,
        }

    return {
        "canonical_base": base_identity,
        "canonical_method": {
            "method_id": REFINEMENT_METHOD_ID,
            "objective_id": OBJECTIVE_ID,
            "path": "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py",
            "sha256": LOCKED_SOURCE_FILE_SHA256[
                "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py"
            ],
        },
        "owner_authorization": OWNER_AUTHORIZATION,
        "requested_k_scope": list(REQUESTED_K_SCOPE),
        "seed_policy": {
            "all_predeclared_starts_retained": True,
            "objective_evaluated_during_freeze": False,
            "random_derived_starts": "NONE",
            "start_ids": list(START_IDS),
            "start_offsets": list(START_OFFSETS),
        },
        "source_file_sha256": source_identities,
        "structures": structures,
        "study_id": STUDY_ID,
        "supported_k_scope": list(SUPPORTED_K_SCOPE),
        "task_id": TASK_ID,
        "unsupported_scope": {
            "POWER_LOTTO_ZONE2": {
                "SUPPORTED": False,
                "STATUS": "OUT_OF_SCOPE_NOT_RUN",
                "reason": "This task covers POWER_LOTTO_ZONE1 only",
            },
            "K_10_20": {
                "SUPPORTED": False,
                "STATUS": "PHASE13_OWNED_NOT_RUN",
                "reason": "k=10 and k=20 remain owned by Phase13",
            },
        },
    }


def freeze_start_manifest() -> str:
    payload = build_start_manifest()
    output = canonical_json_bytes(payload)
    if START_MANIFEST_PATH.exists():
        existing = START_MANIFEST_PATH.read_bytes()
        if existing != output:
            raise ValueError("FROZEN_START_MANIFEST_ALREADY_EXISTS_WITH_DIFFERENT_BYTES")
    else:
        START_MANIFEST_PATH.write_bytes(output)
    manifest_sha256 = sha256_bytes(output)
    print(f"FROZEN_START_MANIFEST: {START_MANIFEST_PATH}", flush=True)
    print(f"FROZEN_START_MANIFEST_SHA256: {manifest_sha256}", flush=True)
    print("OBJECTIVE_EVALUATED_DURING_FREEZE: NO", flush=True)
    return manifest_sha256


def _verify_locked_file(file_path: Path, expected_sha256: str, *, label: str) -> str:
    if expected_sha256.startswith("TO_BE_FROZEN"):
        raise ValueError(f"{label}_NOT_FROZEN")
    actual_sha256 = sha256_file(file_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"{label}_IDENTITY_MISMATCH: expected {expected_sha256}, got {actual_sha256}"
        )
    return actual_sha256


def load_frozen_start_manifest() -> dict[str, Any]:
    _verify_locked_file(
        PREREGISTRATION_PATH,
        LOCKED_PREREGISTRATION_SHA256,
        label="PREREGISTRATION",
    )
    _verify_locked_file(
        START_MANIFEST_PATH,
        LOCKED_START_MANIFEST_SHA256,
        label="START_MANIFEST",
    )
    raw_payload: object = json.loads(START_MANIFEST_PATH.read_bytes())
    if not isinstance(raw_payload, dict):
        raise ValueError("start manifest root must be an object")
    return cast(dict[str, Any], raw_payload)


def _manifest_search_tasks(manifest: Mapping[str, Any]) -> tuple[SearchTask, ...]:
    raw_structures = _mapping(manifest.get("structures"), locator="manifest.structures")
    tasks: list[SearchTask] = []
    for spec in STRUCTURES:
        structure = _mapping(
            raw_structures.get(spec.structure_id),
            locator=f"manifest.structures.{spec.structure_id}",
        )
        per_k = _mapping(structure.get("per_k"), locator=f"{spec.structure_id}.per_k")
        for k in SUPPORTED_K_SCOPE:
            cell = _mapping(per_k.get(str(k)), locator=f"{spec.structure_id}.per_k.{k}")
            raw_starts = cell.get("STARTS")
            if not isinstance(raw_starts, list):
                raise ValueError(f"FROZEN_STARTS_MALFORMED {spec.structure_id} k={k}")
            start_rows = cast(list[object], raw_starts)
            if len(start_rows) != len(START_IDS):
                raise ValueError(f"FROZEN_START_COUNT_MISMATCH {spec.structure_id} k={k}")
            seen_ids: list[str] = []
            for index, raw_start in enumerate(start_rows):
                start = _mapping(
                    raw_start,
                    locator=f"{spec.structure_id}.per_k.{k}.STARTS[{index}]",
                )
                start_id = start.get("START_ID")
                if not isinstance(start_id, str):
                    raise ValueError(f"FROZEN_START_ID_MALFORMED {spec.structure_id} k={k}")
                seen_ids.append(start_id)
                portfolio = _parse_portfolio(
                    start.get("SEED_PORTFOLIO"),
                    locator=f"{spec.structure_id}.per_k.{k}.{start_id}.SEED_PORTFOLIO",
                    pool_size=spec.pool_size,
                    draw_size=spec.draw_size,
                    k=k,
                )
                if portfolio_sha256(portfolio) != start.get("SEED_PORTFOLIO_SHA256"):
                    raise ValueError(f"FROZEN_START_HASH_MISMATCH {spec.structure_id} k={k}")
                tasks.append(
                    SearchTask(
                        structure_id=spec.structure_id,
                        k=k,
                        pool_size=spec.pool_size,
                        draw_size=spec.draw_size,
                        start_id=start_id,
                        seed_portfolio=portfolio,
                    )
                )
            if tuple(seen_ids) != START_IDS:
                raise ValueError(f"FROZEN_START_ORDER_MISMATCH {spec.structure_id} k={k}")
    return tuple(tasks)


def _run_search_task(task: SearchTask) -> CompletedStart:
    ascent = iterative_exact_one_exchange_ascent(
        pool_size=task.pool_size,
        draw_size=task.draw_size,
        minimum_matches=3,
        seed_portfolio=task.seed_portfolio,
    )
    return CompletedStart(
        structure_id=task.structure_id,
        k=task.k,
        start_id=task.start_id,
        ascent=ascent,
    )


def run_all_searches(tasks: tuple[SearchTask, ...], workers: int) -> tuple[CompletedStart, ...]:
    if workers not in (1, 2) or workers > MAX_CPU_WORKERS:
        raise ValueError("workers must be 1 or 2 under the shared-workstation budget")
    completed: list[CompletedStart] = []
    if workers == 1:
        for task in tasks:
            started = time.perf_counter()
            result = _run_search_task(task)
            completed.append(result)
            print(
                f"COMPLETED {task.structure_id} k={task.k} {task.start_id} "
                f"moves={result.ascent.move_count} seconds={time.perf_counter() - started:.6f}",
                flush=True,
            )
    else:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
            futures = {executor.submit(_run_search_task, task): task for task in tasks}
            for future in as_completed(futures):
                task = futures[future]
                result = future.result()
                completed.append(result)
                print(
                    f"COMPLETED {task.structure_id} k={task.k} {task.start_id} "
                    f"moves={result.ascent.move_count}",
                    flush=True,
                )
    if len(completed) != len(tasks):
        raise ValueError("HIDDEN_OR_DISCARDED_START_RESULT")
    return tuple(sorted(completed, key=lambda item: (item.structure_id, item.k, item.start_id)))


def _serialize_iteration(iteration: ExactOneExchangeAscentIteration) -> dict[str, object]:
    return {
        "ACCEPTED_MOVE": iteration.accepted_move,
        "BEST_NEIGHBOR_EXACT_Q": rational(iteration.best_neighbor_q),
        "BEST_NEIGHBOR_PORTFOLIO": _portfolio_json(iteration.best_neighbor_portfolio),
        "BEST_NEIGHBOR_PORTFOLIO_SHA256": portfolio_sha256(
            iteration.best_neighbor_portfolio
        ),
        "DELTA": rational(iteration.delta),
        "INPUT_EXACT_Q": rational(iteration.input_q),
        "INPUT_PORTFOLIO": _portfolio_json(iteration.input_portfolio),
        "INPUT_PORTFOLIO_SHA256": portfolio_sha256(iteration.input_portfolio),
        "ITERATION_INDEX": iteration.iteration_index,
        "UNIQUE_LEGAL_NEIGHBOR_COUNT": iteration.unique_legal_neighbor_count,
    }


def serialize_completed_start(result: CompletedStart) -> dict[str, object]:
    ascent = result.ascent
    if not ascent.iterations:
        raise ValueError("ascent trace must contain a terminal iteration")
    if ascent.move_count != len(ascent.iterations) - 1:
        raise ValueError("ascent move/iteration count mismatch")
    for expected_index, iteration in enumerate(ascent.iterations):
        if iteration.iteration_index != expected_index:
            raise ValueError("ascent iteration index mismatch")
        if expected_index < ascent.move_count:
            if not iteration.accepted_move or iteration.delta <= 0:
                raise ValueError("accepted ascent move is not a strict exact improvement")
        elif iteration.accepted_move:
            raise ValueError("terminal ascent iteration accepted a move")
    terminal = ascent.iterations[-1]
    if terminal.input_portfolio != ascent.terminal_portfolio:
        raise ValueError("terminal portfolio contradicts final iteration")
    if terminal.input_q != ascent.terminal_q or terminal.best_neighbor_q > ascent.terminal_q:
        raise ValueError("terminal exact local-optimum certificate failed")
    return {
        "ITERATION_COUNT": len(ascent.iterations),
        "ITERATIONS": [_serialize_iteration(item) for item in ascent.iterations],
        "MOVE_COUNT": ascent.move_count,
        "SEED_EXACT_Q": rational(ascent.seed_q),
        "SEED_PORTFOLIO": _portfolio_json(ascent.seed_portfolio),
        "SEED_PORTFOLIO_SHA256": portfolio_sha256(ascent.seed_portfolio),
        "START_ID": result.start_id,
        "TERMINAL_CERTIFICATE": {
            "ALL_ACCEPTED_MOVES_STRICT_EXACT_IMPROVEMENTS": True,
            "STATUS": "PASS",
            "TERMINAL_BEST_NEIGHBOR_LTE_TERMINAL": True,
            "TERMINAL_ITERATION_ACCEPTED_MOVE": False,
        },
        "TERMINAL_EXACT_Q": rational(ascent.terminal_q),
        "TERMINAL_PORTFOLIO": _portfolio_json(ascent.terminal_portfolio),
        "TERMINAL_PORTFOLIO_SHA256": portfolio_sha256(ascent.terminal_portfolio),
    }


def _cell_result(
    spec: StructureSpec,
    k: int,
    completed: tuple[CompletedStart, ...],
) -> dict[str, object]:
    if len(completed) != len(START_IDS):
        raise ValueError(f"START_RESULT_COUNT_MISMATCH {spec.structure_id} k={k}")
    if tuple(item.start_id for item in completed) != START_IDS:
        raise ValueError(f"START_RESULT_ID_MISMATCH {spec.structure_id} k={k}")
    serialized = [serialize_completed_start(item) for item in completed]

    terminal_groups: defaultdict[Portfolio, list[CompletedStart]] = defaultdict(list)
    for item in completed:
        terminal_groups[item.ascent.terminal_portfolio].append(item)
    unique_terminals: list[dict[str, object]] = []
    for portfolio in sorted(terminal_groups):
        members = terminal_groups[portfolio]
        objective_values = {member.ascent.terminal_q for member in members}
        if len(objective_values) != 1:
            raise ValueError("identical terminal portfolio has conflicting exact Q values")
        exact_q = next(iter(objective_values))
        unique_terminals.append(
            {
                "EXACT_Q": rational(exact_q),
                "START_IDS": sorted(member.start_id for member in members),
                "TERMINAL_PORTFOLIO": _portfolio_json(portfolio),
                "TERMINAL_PORTFOLIO_SHA256": portfolio_sha256(portfolio),
            }
        )

    best = min(
        completed,
        key=lambda item: (
            -item.ascent.terminal_q,
            item.ascent.terminal_portfolio,
            item.start_id,
        ),
    )
    all_certified = all(
        item.ascent.iterations
        and item.ascent.iterations[-1].best_neighbor_q <= item.ascent.terminal_q
        and not item.ascent.iterations[-1].accepted_move
        for item in completed
    )
    if not all_certified:
        raise ValueError(f"LOCAL_OPTIMUM_CERTIFICATE_FAILED {spec.structure_id} k={k}")
    best_q = best.ascent.terminal_q
    return {
        "BEST_EXACT_Q": rational(best_q),
        "BEST_START_ID": best.start_id,
        "BEST_START_IDS_AT_Q": sorted(
            item.start_id for item in completed if item.ascent.terminal_q == best_q
        ),
        "BEST_TERMINAL_PORTFOLIO": _portfolio_json(best.ascent.terminal_portfolio),
        "BEST_TERMINAL_PORTFOLIO_SHA256": portfolio_sha256(
            best.ascent.terminal_portfolio
        ),
        "GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
        "LOCAL_OPTIMUM_STATUS": "EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM",
        "NO_HIDDEN_RESTART_DISCARDED": True,
        "START_COUNT": len(completed),
        "STARTS": serialized,
        "UNIQUE_TERMINAL_COUNT": len(unique_terminals),
        "UNIQUE_TERMINALS": unique_terminals,
    }


def build_result_payload(
    manifest: Mapping[str, Any],
    completed: tuple[CompletedStart, ...],
) -> dict[str, object]:
    by_cell: defaultdict[tuple[str, int], list[CompletedStart]] = defaultdict(list)
    for item in completed:
        by_cell[(item.structure_id, item.k)].append(item)
    manifest_structures = _mapping(manifest.get("structures"), locator="manifest.structures")
    structures: dict[str, object] = {}
    for spec in STRUCTURES:
        manifest_structure = _mapping(
            manifest_structures.get(spec.structure_id),
            locator=f"manifest.structures.{spec.structure_id}",
        )
        manifest_per_k = _mapping(
            manifest_structure.get("per_k"),
            locator=f"manifest.structures.{spec.structure_id}.per_k",
        )
        per_k: dict[str, object] = {}
        for k in SUPPORTED_K_SCOPE:
            manifest_cell = _mapping(
                manifest_per_k.get(str(k)),
                locator=f"manifest.structures.{spec.structure_id}.per_k.{k}",
            )
            if manifest_cell.get("START_COUNT") != len(START_IDS):
                raise ValueError(f"MANIFEST_START_COUNT_MISMATCH {spec.structure_id} k={k}")
            cell_completed = tuple(
                sorted(by_cell[(spec.structure_id, k)], key=lambda item: item.start_id)
            )
            per_k[str(k)] = _cell_result(spec, k, cell_completed)
        structures[spec.structure_id] = {
            "draw_size": spec.draw_size,
            "lottery_type": spec.lottery_type,
            "per_k": per_k,
            "pool_size": spec.pool_size,
            "primary_event": spec.primary_event,
            "zone": spec.zone,
        }

    return {
        "canonical_base": {
            "commit": PINNED_BASE_COMMIT,
            "tree": PINNED_BASE_TREE,
        },
        "canonical_method": {
            "method_id": REFINEMENT_METHOD_ID,
            "neighborhood": "COMPLETE_LEGAL_EXACT_ONE_NUMBER_EXCHANGE",
            "objective_id": OBJECTIVE_ID,
            "path": "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py",
            "sha256": LOCKED_SOURCE_FILE_SHA256[
                "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py"
            ],
            "tie_break": "LEXICOGRAPHIC_COMPLETE_PORTFOLIO",
        },
        "gate": {
            "ALL_FROZEN_STARTS_RETAINED": True,
            "ALL_LOCAL_OPTIMUM_CERTIFICATES": "PASS",
            "GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "HIDDEN_RESTARTS_DISCARDED": False,
            "MULTISTART_EXECUTION_GATE": "PASS",
            "RANDOM_DERIVED_STARTS": "NONE",
            "STARTS_FROZEN_BEFORE_SCORING": True,
        },
        "owner_authorization": OWNER_AUTHORIZATION,
        "reproduction_policy": {
            "canonical_json": "UTF-8, indent=2, sort_keys=True, LF terminal newline",
            "deterministic_fresh_process_byte_identity_required": True,
            "performance_measurements_in_payload": False,
            "random_number_generator": "NONE",
            "worker_count_semantic_effect": "NONE",
        },
        "scope": {
            "requested_k_scope": list(REQUESTED_K_SCOPE),
            "supported_k_scope": list(SUPPORTED_K_SCOPE),
            "unsupported_scope": manifest.get("unsupported_scope"),
        },
        "source_file_sha256": dict(LOCKED_SOURCE_FILE_SHA256),
        "start_manifest": {
            "path": str(START_MANIFEST_PATH),
            "sha256": LOCKED_START_MANIFEST_SHA256,
        },
        "preregistration": {
            "path": str(PREREGISTRATION_PATH),
            "sha256": LOCKED_PREREGISTRATION_SHA256,
        },
        "structures": structures,
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
    }


def execute(workers: int) -> dict[str, object]:
    verify_current_base_identity()
    verify_file_identities(LOCKED_SOURCE_FILE_SHA256)
    manifest = load_frozen_start_manifest()
    tasks = _manifest_search_tasks(manifest)
    expected_count = len(STRUCTURES) * len(SUPPORTED_K_SCOPE) * len(START_IDS)
    if len(tasks) != expected_count:
        raise ValueError(f"FROZEN_TASK_COUNT_MISMATCH: expected {expected_count}, got {len(tasks)}")
    completed = run_all_searches(tasks, workers)
    payload = build_result_payload(manifest, completed)
    output = canonical_json_bytes(payload)
    OUTPUT_PATH.write_bytes(output)
    print(f"WROTE_RESULT: {OUTPUT_PATH}", flush=True)
    print(f"RESULT_SHA256: {sha256_bytes(output)}", flush=True)
    payload_structures = cast(dict[str, Any], payload["structures"])
    for spec in STRUCTURES:
        structure = cast(dict[str, Any], payload_structures[spec.structure_id])
        per_k = cast(dict[str, Any], structure["per_k"])
        for k in SUPPORTED_K_SCOPE:
            cell = cast(dict[str, Any], per_k[str(k)])
            print(f"{spec.structure_id} k={k}", flush=True)
            for field_name in (
                "START_COUNT",
                "UNIQUE_TERMINAL_COUNT",
                "BEST_START_ID",
                "BEST_TERMINAL_PORTFOLIO",
                "BEST_EXACT_Q",
                "LOCAL_OPTIMUM_STATUS",
                "GLOBAL_OPTIMUM_STATUS",
            ):
                print(
                    f"{field_name}: {json.dumps(cell[field_name], separators=(',', ':'))}",
                    flush=True,
                )
    print("MULTISTART_EXECUTION_GATE: PASS", flush=True)
    print("GLOBAL_OPTIMUM_STATUS: UNKNOWN", flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freeze-starts",
        action="store_true",
        help="materialize deterministic starts only; never evaluate the exact objective",
    )
    parser.add_argument(
        "--workers",
        type=int,
        choices=(1, 2),
        default=2,
        help="CPU-bound worker count, capped at the shared-workstation maximum of 2",
    )
    arguments = parser.parse_args()
    if arguments.freeze_starts:
        freeze_start_manifest()
    else:
        execute(arguments.workers)


if __name__ == "__main__":
    main()
