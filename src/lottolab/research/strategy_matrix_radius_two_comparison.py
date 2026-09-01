"""Run the minimal exact Strategy Matrix radius-two comparison.

The comparison reuses one already-sealed radius-one local-optimum certificate
from Phase 11.  It evaluates the largest supported POWER_LOTTO_ZONE1 rung
through the canonical local-escape registration.  One strict improvement is
sufficient to answer the packet's existential primary question; unevaluated
rows receive no inferred classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Final, cast

from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    canonicalize_portfolio,
)
from lottolab.research.strategy_matrix_local_escape import (
    RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
    RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
    RegisteredLocalEscapeIteration,
    RegisteredLocalEscapeResult,
    StrategyMatrixLocalEscapeMethod,
    evaluate_registered_local_escape,
    registered_local_escape_methods,
)

STUDY_ID: Final = "STRATEGY_MATRIX_RADIUS2_REGISTRATION_AND_COMPARISON_V1"
TASK_ID: Final = "LANE1_MATRIX_RADIUS2_REGISTRATION_AND_COMPARISON_R1"
PINNED_BASE_COMMIT: Final = "4da01c702f2a03f649838abe4fc1f1cf02dc0656"
PINNED_BASE_TREE: Final = "3035df838d342c2c0b0136de4e1639f83d04725f"

SOURCE_AUTHORITY_PATH: Final = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-phase11-t539-p638-zone1-"
    "iterative-exact-1exchange-replication-v1-result.json"
)
SOURCE_AUTHORITY_SHA256: Final = (
    "c7904f716a61fb6b43df2091664ef55a1972b9212cac3490133d0accd4ae7290"
)
SOURCE_STUDY_ID: Final = (
    "STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_"
    "ITERATIVE_EXACT_1EXCHANGE_REPLICATION_V1"
)
SOURCE_TASK_ID: Final = (
    "STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_"
    "ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1"
)
SUPPORTED_K_VALUES: Final = (10, 15, 20)
EVALUATED_K_VALUES: Final = (20,)

STRUCTURE_ID: Final = "POWER_LOTTO_ZONE1"
LOTTERY_TYPE: Final = "POWER_LOTTO"
ZONE: Final = "zone1"
POOL_SIZE: Final = 38
DRAW_SIZE: Final = 6
MINIMUM_MATCHES: Final = 3
EVALUATED_K: Final = 20
EXPECTED_SOURCE_PORTFOLIO_SHA256: Final = (
    "63ca63cac6a94fc956fe344ff026818d3322f6f3610c9ed7d7004c5eec894728"
)
EXPECTED_SOURCE_Q: Final = Fraction(157958, 250971)

OUTPUT_PATH: Final = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-radius2-registration-comparison-r1-result.json"
)

type ProgressCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class RadiusOneCertificate:
    """Validated Matrix authority for the selected radius-one terminal row."""

    source_study_id: str
    source_task_id: str
    source_locator: str
    method_id: str
    structure_id: str
    lottery_type: str
    zone: str | None
    k: int
    portfolio: Portfolio
    portfolio_sha256: str
    exact_q: Fraction


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Return the repository's stable pretty-printed JSON representation."""

    return (json.dumps(payload, indent=2, sort_keys=True).rstrip("\n") + "\n").encode()


def rational(value: Fraction) -> dict[str, int | str]:
    """Serialize one exact Fraction without floating-point loss."""

    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def portfolio_sha256(portfolio: Portfolio) -> str:
    """Return the stable identity used by the existing Matrix runners."""

    raw = json.dumps(portfolio, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _mapping(value: object, *, locator: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{locator} must be an object")
    return cast(dict[str, Any], value)


def _rows(value: object, *, locator: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{locator} must be an array")
    raw_rows = cast(list[object], value)
    if not all(isinstance(row, dict) for row in raw_rows):
        raise ValueError(f"{locator} rows must be objects")
    return [cast(dict[str, Any], row) for row in raw_rows]


def _fraction(value: object, *, locator: str) -> Fraction:
    mapping = _mapping(value, locator=locator)
    numerator = mapping.get("numerator")
    denominator = mapping.get("denominator")
    if type(numerator) is not int or type(denominator) is not int:
        raise ValueError(f"{locator} numerator/denominator must be integers")
    result = Fraction(numerator, denominator)
    if mapping.get("exact") != f"{result.numerator}/{result.denominator}":
        raise ValueError(f"{locator} exact string is inconsistent")
    return result


def _portfolio(value: object, *, locator: str) -> Portfolio:
    if not isinstance(value, list):
        raise ValueError(f"{locator} must be an array")
    tickets: list[tuple[int, ...]] = []
    for raw_ticket in cast(list[object], value):
        if not isinstance(raw_ticket, list):
            raise ValueError(f"{locator} ticket must be an array")
        raw_numbers = cast(list[object], raw_ticket)
        if not all(type(number) is int for number in raw_numbers):
            raise ValueError(f"{locator} ticket numbers must be integers")
        tickets.append(tuple(cast(list[int], raw_numbers)))
    portfolio = tuple(tickets)
    if canonicalize_portfolio(portfolio) != portfolio:
        raise ValueError(f"{locator} must be a canonical portfolio")
    return portfolio


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_current_base_identity() -> dict[str, str]:
    """Require the packet's exact base and its ancestry of the task tree."""

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


def load_radius_one_certificate() -> RadiusOneCertificate:
    """Load and validate the one selected, already-measured Matrix row."""

    authority_bytes = SOURCE_AUTHORITY_PATH.read_bytes()
    observed_sha256 = hashlib.sha256(authority_bytes).hexdigest()
    if observed_sha256 != SOURCE_AUTHORITY_SHA256:
        raise ValueError(
            "SOURCE_RADIUS1_AUTHORITY_SHA256_MISMATCH: "
            f"expected {SOURCE_AUTHORITY_SHA256}, got {observed_sha256}"
        )
    payload = _mapping(json.loads(authority_bytes), locator="source authority")
    if payload.get("study_id") != SOURCE_STUDY_ID:
        raise ValueError("SOURCE_RADIUS1_STUDY_ID_MISMATCH")
    if payload.get("task_id") != SOURCE_TASK_ID:
        raise ValueError("SOURCE_RADIUS1_TASK_ID_MISMATCH")
    if payload.get("refinement_method_id") != RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID:
        raise ValueError("SOURCE_RADIUS1_METHOD_ID_MISMATCH")
    if payload.get("exposure_ladder") != list(SUPPORTED_K_VALUES):
        raise ValueError("SOURCE_RADIUS1_K_SCOPE_MISMATCH")

    gate = _mapping(payload.get("gate"), locator="source authority gate")
    if gate.get("phase11_execution_gate") != "PASS":
        raise ValueError("SOURCE_RADIUS1_EXECUTION_GATE_NOT_PASS")
    structures = _mapping(payload.get("structures"), locator="source structures")
    structure = _mapping(structures.get(STRUCTURE_ID), locator=STRUCTURE_ID)
    if structure.get("lottery_type") != LOTTERY_TYPE:
        raise ValueError("SOURCE_RADIUS1_LOTTERY_TYPE_MISMATCH")
    if structure.get("zone") != ZONE:
        raise ValueError("SOURCE_RADIUS1_ZONE_MISMATCH")
    if structure.get("pool_size") != POOL_SIZE or structure.get("draw_size") != DRAW_SIZE:
        raise ValueError("SOURCE_RADIUS1_DIMENSION_MISMATCH")
    if structure.get("primary_event_minimum_matches") != MINIMUM_MATCHES:
        raise ValueError("SOURCE_RADIUS1_OBJECTIVE_MISMATCH")

    per_k = _mapping(structure.get("per_k"), locator=f"{STRUCTURE_ID}.per_k")
    row = _mapping(per_k.get(str(EVALUATED_K)), locator=f"{STRUCTURE_ID}.k={EVALUATED_K}")
    if row.get("k") != EVALUATED_K:
        raise ValueError("SOURCE_RADIUS1_ROW_K_MISMATCH")
    if row.get("terminal_classification") != "TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED":
        raise ValueError("SOURCE_RADIUS1_CLASSIFICATION_MISMATCH")
    certificate = _mapping(
        row.get("terminal_certificate"), locator="source terminal certificate"
    )
    if certificate.get("status") != "PASS":
        raise ValueError("SOURCE_RADIUS1_CERTIFICATE_NOT_PASS")
    if certificate.get("terminal_iteration_accepted_move") is not False:
        raise ValueError("SOURCE_RADIUS1_TERMINAL_ACCEPTANCE_MISMATCH")

    portfolio = _portfolio(row.get("terminal_portfolio"), locator="terminal portfolio")
    observed_portfolio_sha256 = portfolio_sha256(portfolio)
    if observed_portfolio_sha256 != row.get("terminal_portfolio_sha256"):
        raise ValueError("SOURCE_RADIUS1_PORTFOLIO_ROW_HASH_MISMATCH")
    if observed_portfolio_sha256 != EXPECTED_SOURCE_PORTFOLIO_SHA256:
        raise ValueError("SOURCE_RADIUS1_PORTFOLIO_PIN_MISMATCH")
    exact_q = _fraction(row.get("terminal_exact_q"), locator="terminal exact Q")
    if exact_q != EXPECTED_SOURCE_Q:
        raise ValueError("SOURCE_RADIUS1_EXACT_Q_MISMATCH")

    iterations = _rows(row.get("iterations"), locator="source iterations")
    if not iterations:
        raise ValueError("SOURCE_RADIUS1_TRACE_EMPTY")
    terminal_iteration = iterations[-1]
    if terminal_iteration.get("accepted_move") is not False:
        raise ValueError("SOURCE_RADIUS1_TRACE_NOT_TERMINAL")
    if _portfolio(
        terminal_iteration.get("input_portfolio"), locator="terminal trace input"
    ) != portfolio:
        raise ValueError("SOURCE_RADIUS1_TRACE_PORTFOLIO_MISMATCH")
    if _fraction(
        terminal_iteration.get("exact_input_q"), locator="terminal trace input Q"
    ) != exact_q:
        raise ValueError("SOURCE_RADIUS1_TRACE_Q_MISMATCH")

    return RadiusOneCertificate(
        source_study_id=SOURCE_STUDY_ID,
        source_task_id=SOURCE_TASK_ID,
        source_locator=f"structures.{STRUCTURE_ID}.per_k.{EVALUATED_K}",
        method_id=RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
        structure_id=STRUCTURE_ID,
        lottery_type=LOTTERY_TYPE,
        zone=ZONE,
        k=EVALUATED_K,
        portfolio=portfolio,
        portfolio_sha256=observed_portfolio_sha256,
        exact_q=exact_q,
    )


def _portfolio_json(portfolio: Portfolio) -> list[list[int]]:
    return [list(ticket) for ticket in portfolio]


def _registration_json(
    registration: StrategyMatrixLocalEscapeMethod,
) -> dict[str, object]:
    return {
        "exchange_radius": registration.exchange_radius,
        "exchange_semantics": registration.exchange_semantics,
        "global_optimum_status": registration.global_optimum_status,
        "implementation_path": registration.implementation_path,
        "implementation_symbol": registration.implementation_symbol,
        "method_id": registration.method_id,
        "objective_id": registration.objective_id,
    }


def _iteration_json(
    iteration: RegisteredLocalEscapeIteration,
) -> dict[str, object]:
    return {
        "accepted_move": iteration.accepted_move,
        "best_endpoint_exact_q": rational(iteration.best_endpoint_q),
        "best_endpoint_portfolio": _portfolio_json(iteration.best_endpoint_portfolio),
        "best_endpoint_portfolio_sha256": portfolio_sha256(
            iteration.best_endpoint_portfolio
        ),
        "delta": rational(iteration.delta),
        "first_level_candidate_count": iteration.first_level_candidate_count,
        "input_exact_q": rational(iteration.input_q),
        "input_portfolio": _portfolio_json(iteration.input_portfolio),
        "input_portfolio_sha256": portfolio_sha256(iteration.input_portfolio),
        "iteration_index": iteration.iteration_index,
        "single_replacement_endpoint_count": (
            iteration.single_replacement_endpoint_count
        ),
        "two_replacement_endpoint_count": iteration.two_replacement_endpoint_count,
        "unique_endpoint_count": iteration.unique_endpoint_count,
    }


def _certificate(
    source: RadiusOneCertificate,
    result: RegisteredLocalEscapeResult,
) -> dict[str, Any]:
    terminal_iteration = result.iterations[-1]
    body: dict[str, Any] = {
        "accepted_strict_moves_only": all(
            iteration.accepted_move and iteration.delta > 0
            for iteration in result.iterations[:-1]
        ),
        "best_exact_q": rational(result.terminal_q),
        "best_portfolio": _portfolio_json(result.terminal_portfolio),
        "best_portfolio_sha256": portfolio_sha256(result.terminal_portfolio),
        "complete_endpoint_enumeration": "PASS",
        "delta": rational(result.terminal_q - source.exact_q),
        "input_exact_q": rational(source.exact_q),
        "input_portfolio": _portfolio_json(source.portfolio),
        "input_portfolio_sha256": source.portfolio_sha256,
        "move_count": result.move_count,
        "no_intermediate_score_filter": True,
        "no_sampling": True,
        "status": "PASS",
        "terminal_best_endpoint_lte_terminal": (
            terminal_iteration.best_endpoint_q <= result.terminal_q
        ),
        "terminal_iteration_accepted_move": terminal_iteration.accepted_move,
        "trace": [_iteration_json(iteration) for iteration in result.iterations],
        "unique_endpoints_evaluated": result.unique_endpoints_evaluated,
    }
    body_bytes = canonical_json_bytes(body)
    return {
        **body,
        "certificate_identity": {
            "algorithm": "SHA256",
            "scope": "canonical_json(certificate_without_certificate_identity)",
            "sha256": hashlib.sha256(body_bytes).hexdigest(),
        },
    }


def result_payload_sha256(payload: dict[str, Any]) -> str:
    """Recompute the declared deterministic result identity."""

    identity_free = dict(payload)
    identity_free.pop("result_identity", None)
    return hashlib.sha256(canonical_json_bytes(identity_free)).hexdigest()


def build_comparison_payload(
    *,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Execute and serialize the single canonical exact comparison row."""

    base_identity = verify_current_base_identity()
    source = load_radius_one_certificate()
    result = evaluate_registered_local_escape(
        RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
        pool_size=POOL_SIZE,
        draw_size=DRAW_SIZE,
        minimum_matches=MINIMUM_MATCHES,
        seed_portfolio=source.portfolio,
        progress=progress,
    )
    if result.seed_portfolio != source.portfolio or result.seed_q != source.exact_q:
        raise ValueError("RADIUS2_INPUT_EXACT_REPLAY_MISMATCH")
    if not result.iterations:
        raise ValueError("RADIUS2_TRACE_EMPTY")
    if result.iterations[-1].accepted_move:
        raise ValueError("RADIUS2_TRACE_MISSING_TERMINAL_ITERATION")
    if result.move_count != sum(
        1 for iteration in result.iterations if iteration.accepted_move
    ):
        raise ValueError("RADIUS2_MOVE_COUNT_MISMATCH")

    delta = result.terminal_q - source.exact_q
    strict_improvement = delta > 0
    if strict_improvement is not (result.move_count > 0):
        raise ValueError("RADIUS2_STRICT_ACCEPTANCE_MISMATCH")
    classification = (
        "RADIUS2_STRICT_IMPROVEMENT"
        if strict_improvement
        else "RADIUS2_NO_IMPROVEMENT"
    )
    certificate = _certificate(source, result)
    row: dict[str, Any] = {
        "accepted": strict_improvement,
        "best_exact_radius2_objective": rational(result.terminal_q),
        "best_radius2_portfolio": _portfolio_json(result.terminal_portfolio),
        "best_radius2_portfolio_sha256": portfolio_sha256(result.terminal_portfolio),
        "certificate": certificate,
        "exact_delta": rational(delta),
        "global_optimum_status": "UNKNOWN",
        "input_exact_objective": rational(source.exact_q),
        "k": source.k,
        "lottery_type": source.lottery_type,
        "outcome_classification": classification,
        "radius2_iteration_count": len(result.iterations),
        "radius2_move_count": result.move_count,
        "row_id": f"{source.structure_id}__K{source.k}__RADIUS2_VS_RADIUS1",
        "source_reference": {
            "method_id": source.method_id,
            "portfolio_sha256": source.portfolio_sha256,
            "result_sha256": SOURCE_AUTHORITY_SHA256,
            "row_locator": source.source_locator,
            "study_id": source.source_study_id,
            "task_id": source.source_task_id,
        },
        "source_reference_portfolio": _portfolio_json(source.portfolio),
        "structure_id": source.structure_id,
        "unique_radius2_endpoints_evaluated": result.unique_endpoints_evaluated,
        "zone": source.zone,
    }
    payload: dict[str, Any] = {
        "canonical_base": base_identity,
        "comparison_contract": {
            "candidate_method_id": RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
            "evaluated_k_values": list(EVALUATED_K_VALUES),
            "evaluation_window": "COMPLETE_STATIC_WINNING_SPACE",
            "objective": "EXACT_M3_PLUS_FRACTION",
            "population": "POWER_LOTTO_ZONE1_ALL_C(38,6)_DRAWS",
            "primary_question": (
                "Does exact radius-two escape strictly improve an existing "
                "radius-one local-optimum certificate?"
            ),
            "row_selection_policy": (
                "Evaluate one canonical largest-supported exposure row; a strict "
                "improvement settles the existential question, and no outcome is "
                "imputed to unevaluated rows."
            ),
            "source_method_id": RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
            "supported_k_values": list(SUPPORTED_K_VALUES),
            "tie_break": "LEXICOGRAPHIC_COMPLETE_PORTFOLIO",
        },
        "gate": {
            "complete_endpoint_enumeration": "PASS",
            "global_optimum_status": "UNKNOWN",
            "matrix_method_registration": "PASS",
            "predictive_success_claims": "NONE",
            "radius1_source_certificate": "PASS",
            "radius2_comparison": "PASS",
        },
        "matrix_method_registration": [
            _registration_json(registration)
            for registration in registered_local_escape_methods()
        ],
        "rows": [row],
        "source_authority": {
            "path": str(SOURCE_AUTHORITY_PATH),
            "sha256": SOURCE_AUTHORITY_SHA256,
            "study_id": SOURCE_STUDY_ID,
            "task_id": SOURCE_TASK_ID,
        },
        "study_id": STUDY_ID,
        "summary": {
            "best_observed_delta": rational(delta),
            "evaluated_row_count": 1,
            "radius2_no_improvement_count": int(not strict_improvement),
            "radius2_strict_improvement_count": int(strict_improvement),
        },
        "task_id": TASK_ID,
    }
    payload["result_identity"] = {
        "algorithm": "SHA256",
        "scope": "canonical_json(result_without_result_identity)",
        "sha256": result_payload_sha256(payload),
    }
    return payload


def _progress(message: str) -> None:
    """Emit bounded progress for the long exact single-process evaluation."""

    if message.startswith("single slot="):
        completed, total = message.split()[1].split("=")[1].split("/")
        if completed == total:
            print(f"RADIUS2_PROGRESS: {message}", flush=True)
        return
    if message.startswith("pair="):
        completed_text, total_text = message.split()[0].split("=")[1].split("/")
        completed = int(completed_text)
        total = int(total_text)
        if completed == 1 or completed == total or completed % 25 == 0:
            print(f"RADIUS2_PROGRESS: {message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="recompute and require byte identity with the canonical result",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    payload = build_comparison_payload(progress=_progress)
    output_bytes = canonical_json_bytes(payload)
    if args.check:
        if not OUTPUT_PATH.exists():
            raise FileNotFoundError(f"comparison result missing: {OUTPUT_PATH}")
        if OUTPUT_PATH.read_bytes() != output_bytes:
            raise ValueError("DETERMINISTIC_RESULT_IDENTITY_MISMATCH")
        print(f"DETERMINISTIC_RESULT_CHECK: PASS {OUTPUT_PATH}", flush=True)
    else:
        if not OUTPUT_PATH.parent.is_dir():
            raise FileNotFoundError(f"canonical output directory missing: {OUTPUT_PATH.parent}")
        if OUTPUT_PATH.exists() and OUTPUT_PATH.read_bytes() != output_bytes:
            raise ValueError("REFUSING_TO_OVERWRITE_CHANGED_COMPARISON_RESULT")
        OUTPUT_PATH.write_bytes(output_bytes)
        print(f"WROTE_MATRIX_RESULT: {OUTPUT_PATH}", flush=True)

    elapsed = time.perf_counter() - started
    peak_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = _mapping(payload["summary"], locator="summary")
    print(
        "RADIUS2_COMPARISON_SUMMARY: "
        f"strict={summary['radius2_strict_improvement_count']} "
        f"no_improvement={summary['radius2_no_improvement_count']} "
        f"best_delta={_mapping(summary['best_observed_delta'], locator='delta')['exact']}",
        flush=True,
    )
    print(f"RUNTIME_SECONDS: {elapsed:.6f}", flush=True)
    print(f"PEAK_MEMORY_RUSAGE_RAW: {peak_memory}", flush=True)


if __name__ == "__main__":
    main()
