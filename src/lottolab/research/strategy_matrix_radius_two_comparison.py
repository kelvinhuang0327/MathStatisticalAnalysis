"""Run exact Strategy Matrix radius-two comparisons.

The legacy path preserves the original k=20 registration comparison.  The
supported-k expansion evaluates k=10 and k=15 through the same frozen exact
registration, then combines them with the identity-validated canonical k=20
result without rerunning that expensive search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Final, cast

from lottolab.research.exact_radius_two_local_escape import PackedWinningSpace
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

SUPPORTED_K_STUDY_ID: Final = "STRATEGY_MATRIX_RADIUS2_SUPPORTED_K_EXPANSION_V1"
SUPPORTED_K_TASK_ID: Final = "LANE1_RADIUS2_SUPPORTED_K_EXPANSION_R1"
SUPPORTED_K_PINNED_BASE_COMMIT: Final = "eb64efb6f3c33eb8b71b2ab49fec895de2a004c1"
SUPPORTED_K_PINNED_BASE_TREE: Final = "c516b048c7a1e1eb7e31ba91c772e8dcd8d26814"

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
SUPPORTED_K_EXECUTED_VALUES: Final = (10, 15)
SUPPORTED_K_REUSED_VALUES: Final = (20,)

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
EXPECTED_SOURCE_PORTFOLIO_SHA256_BY_K: Final = {
    10: "47b8b68929e3ac99a9fb5029fc4465dafe9cefbbe2202e25c3a2d0b8ab342a57",
    15: "be4dfc831ba8ccf31b6c85e869970b51f3ea8472d5283e4bbc42b2127d0d755c",
    20: EXPECTED_SOURCE_PORTFOLIO_SHA256,
}
EXPECTED_SOURCE_Q_BY_K: Final = {
    10: Fraction(331675, 920227),
    15: Fraction(465452, 920227),
    20: EXPECTED_SOURCE_Q,
}

OUTPUT_PATH: Final = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-radius2-registration-comparison-r1-result.json"
)
OUTPUT_SHA256: Final = "39f8228136a9516942353ac3745cfbc43c25c2c891d35b64f35566eb46f9fdc7"
OUTPUT_RESULT_IDENTITY_SHA256: Final = (
    "956071071146a2bf03595fa4a719748480a89cc6fc04a9bcffd52df8a50bd87b"
)
OUTPUT_K20_CERTIFICATE_SHA256: Final = (
    "0328162a8da6d6a1b511a35837e753d2a75aceebe5a432375fa839d711fe367d"
)
SUPPORTED_K_OUTPUT_PATH: Final = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-radius2-supported-k-expansion-r1-result.json"
)
SUPPORTED_K_RESULT_IDENTITY_SHA256: Final = (
    "6d59d4d8ad6266309d0d22302a3f197a00cab9a8dbfcd6ae7e58c5396ea4b3a1"
)

type ProgressCallback = Callable[[str], None]
type SupportedKProgressCallback = Callable[[int, str], None]


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


def verify_supported_k_base_identity() -> dict[str, str]:
    """Require the supported-k packet base and its ancestry of the task tree."""

    observed = {
        "commit": _git_value("rev-parse", f"{SUPPORTED_K_PINNED_BASE_COMMIT}^{{commit}}"),
        "tree": _git_value("rev-parse", f"{SUPPORTED_K_PINNED_BASE_COMMIT}^{{tree}}"),
    }
    expected = {
        "commit": SUPPORTED_K_PINNED_BASE_COMMIT,
        "tree": SUPPORTED_K_PINNED_BASE_TREE,
    }
    if observed != expected:
        raise ValueError(f"SUPPORTED_K_CANONICAL_BASE_IDENTITY_MISMATCH: {observed}")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SUPPORTED_K_PINNED_BASE_COMMIT, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("SUPPORTED_K_CANONICAL_BASE_ANCESTRY_MISMATCH")
    return observed


def load_radius_one_certificate(k: int = EVALUATED_K) -> RadiusOneCertificate:
    """Load and validate one supported, already-measured Matrix row."""

    if k not in SUPPORTED_K_VALUES:
        raise ValueError(f"unsupported source radius-one k: {k}")

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
    row = _mapping(per_k.get(str(k)), locator=f"{STRUCTURE_ID}.k={k}")
    if row.get("k") != k:
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
    if observed_portfolio_sha256 != EXPECTED_SOURCE_PORTFOLIO_SHA256_BY_K[k]:
        raise ValueError("SOURCE_RADIUS1_PORTFOLIO_PIN_MISMATCH")
    exact_q = _fraction(row.get("terminal_exact_q"), locator="terminal exact Q")
    if exact_q != EXPECTED_SOURCE_Q_BY_K[k]:
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
        source_locator=f"structures.{STRUCTURE_ID}.per_k.{k}",
        method_id=RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
        structure_id=STRUCTURE_ID,
        lottery_type=LOTTERY_TYPE,
        zone=ZONE,
        k=k,
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


def _validate_radius_two_result(
    source: RadiusOneCertificate,
    result: RegisteredLocalEscapeResult,
) -> None:
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
    if (result.terminal_q > source.exact_q) is not (result.move_count > 0):
        raise ValueError("RADIUS2_STRICT_ACCEPTANCE_MISMATCH")


def _comparison_row(
    source: RadiusOneCertificate,
    result: RegisteredLocalEscapeResult,
) -> dict[str, Any]:
    _validate_radius_two_result(source, result)
    delta = result.terminal_q - source.exact_q
    strict_improvement = delta > 0
    classification = (
        "RADIUS2_STRICT_IMPROVEMENT"
        if strict_improvement
        else "RADIUS2_NO_IMPROVEMENT"
    )
    return {
        "accepted": strict_improvement,
        "best_exact_radius2_objective": rational(result.terminal_q),
        "best_radius2_portfolio": _portfolio_json(result.terminal_portfolio),
        "best_radius2_portfolio_sha256": portfolio_sha256(result.terminal_portfolio),
        "certificate": _certificate(source, result),
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
    delta = result.terminal_q - source.exact_q
    strict_improvement = delta > 0
    row = _comparison_row(source, result)
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


def _row_result_sha256(row: dict[str, Any]) -> str:
    identity_free = dict(row)
    identity_free.pop("row_result_identity", None)
    return hashlib.sha256(canonical_json_bytes(identity_free)).hexdigest()


def _enrich_supported_k_row(
    row: dict[str, Any],
    *,
    evidence_origin: str,
) -> dict[str, Any]:
    enriched = cast(dict[str, Any], json.loads(json.dumps(row)))
    certificate = _mapping(enriched.get("certificate"), locator="row certificate")
    trace = _rows(certificate.get("trace"), locator="row certificate trace")
    if not trace:
        raise ValueError("RADIUS2_TRACE_EMPTY")
    terminal = trace[-1]
    enriched["evidence_origin"] = evidence_origin
    enriched["terminal_best_endpoint"] = {
        "exact_q": terminal["best_endpoint_exact_q"],
        "portfolio": terminal["best_endpoint_portfolio"],
        "portfolio_sha256": terminal["best_endpoint_portfolio_sha256"],
    }
    enriched["terminal_delta"] = terminal["delta"]
    enriched["row_result_identity"] = {
        "algorithm": "SHA256",
        "scope": "canonical_json(row_without_row_result_identity)",
        "sha256": _row_result_sha256(enriched),
    }
    return enriched


def load_reused_k20_row() -> dict[str, Any]:
    """Validate and return the existing k=20 row without re-executing it."""

    raw = OUTPUT_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != OUTPUT_SHA256:
        raise ValueError("K20_AUTHORITY_ARTIFACT_SHA256_MISMATCH")
    payload = _mapping(json.loads(raw), locator="k20 authority")
    if canonical_json_bytes(payload) != raw:
        raise ValueError("K20_AUTHORITY_NOT_CANONICAL_JSON")
    if payload.get("study_id") != STUDY_ID or payload.get("task_id") != TASK_ID:
        raise ValueError("K20_AUTHORITY_STUDY_IDENTITY_MISMATCH")
    result_identity = _mapping(
        payload.get("result_identity"), locator="k20 result identity"
    )
    if result_identity.get("sha256") != OUTPUT_RESULT_IDENTITY_SHA256:
        raise ValueError("K20_AUTHORITY_RESULT_IDENTITY_PIN_MISMATCH")
    if result_payload_sha256(payload) != OUTPUT_RESULT_IDENTITY_SHA256:
        raise ValueError("K20_AUTHORITY_RESULT_IDENTITY_RECOMPUTE_MISMATCH")

    rows = _rows(payload.get("rows"), locator="k20 rows")
    if len(rows) != 1 or rows[0].get("k") != 20:
        raise ValueError("K20_AUTHORITY_ROW_SCOPE_MISMATCH")
    row = rows[0]
    if row.get("outcome_classification") != "RADIUS2_STRICT_IMPROVEMENT":
        raise ValueError("K20_AUTHORITY_CLASSIFICATION_MISMATCH")
    if _fraction(row.get("input_exact_objective"), locator="k20 source Q") != (
        EXPECTED_SOURCE_Q
    ):
        raise ValueError("K20_AUTHORITY_SOURCE_Q_MISMATCH")
    if _fraction(row.get("best_exact_radius2_objective"), locator="k20 terminal Q") != (
        Fraction(579401, 920227)
    ):
        raise ValueError("K20_AUTHORITY_TERMINAL_Q_MISMATCH")
    if _fraction(row.get("exact_delta"), locator="k20 delta") != Fraction(5, 20757):
        raise ValueError("K20_AUTHORITY_DELTA_MISMATCH")
    if row.get("radius2_move_count") != 10:
        raise ValueError("K20_AUTHORITY_MOVE_COUNT_MISMATCH")
    if row.get("unique_radius2_endpoints_evaluated") != 78_724_800:
        raise ValueError("K20_AUTHORITY_ENDPOINT_COUNT_MISMATCH")

    certificate = _mapping(row.get("certificate"), locator="k20 certificate")
    certificate_identity = _mapping(
        certificate.get("certificate_identity"), locator="k20 certificate identity"
    )
    if certificate_identity.get("sha256") != OUTPUT_K20_CERTIFICATE_SHA256:
        raise ValueError("K20_AUTHORITY_CERTIFICATE_IDENTITY_PIN_MISMATCH")
    certificate_body = dict(certificate)
    certificate_body.pop("certificate_identity")
    if hashlib.sha256(canonical_json_bytes(certificate_body)).hexdigest() != (
        OUTPUT_K20_CERTIFICATE_SHA256
    ):
        raise ValueError("K20_AUTHORITY_CERTIFICATE_IDENTITY_RECOMPUTE_MISMATCH")
    return _enrich_supported_k_row(row, evidence_origin="REUSED_CANONICAL_K20_RESULT")


def supported_k_result_payload_sha256(payload: dict[str, Any]) -> str:
    """Hash deterministic evidence while excluding observed execution metrics."""

    identity_free = dict(payload)
    identity_free.pop("execution_metrics", None)
    identity_free.pop("result_identity", None)
    return hashlib.sha256(canonical_json_bytes(identity_free)).hexdigest()


def _peak_memory_bytes() -> int:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024


def _evaluate_supported_k_row(
    k: int,
    *,
    progress: SupportedKProgressCallback | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = load_radius_one_certificate(k)
    started = time.perf_counter()
    result = evaluate_registered_local_escape(
        RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
        pool_size=POOL_SIZE,
        draw_size=DRAW_SIZE,
        minimum_matches=MINIMUM_MATCHES,
        seed_portfolio=source.portfolio,
        progress=(None if progress is None else lambda message: progress(k, message)),
    )
    elapsed = time.perf_counter() - started
    peak_memory_bytes = _peak_memory_bytes()
    row = _enrich_supported_k_row(
        _comparison_row(source, result),
        evidence_origin="EXECUTED_EXACT_THIS_TASK",
    )
    metrics = {
        "measurement_status": "MEASURED_THIS_TASK",
        "peak_memory_bytes": peak_memory_bytes,
        "peak_memory_scope": "PROCESS_HIGH_WATER_MARK_AT_ROW_COMPLETION",
        "runtime_scope": "ROW_WALL_CLOCK_PERF_COUNTER",
        "runtime_seconds": float(f"{elapsed:.6f}"),
    }
    return row, metrics


def _family_cross_k_classification(rows: list[dict[str, Any]]) -> str:
    classifications = {
        cast(int, row["k"]): cast(str, row["outcome_classification"]) for row in rows
    }
    if "RESOURCE_BOUND" in classifications.values():
        return "RESOURCE_LIMITED"
    strict_k = {
        k
        for k, classification in classifications.items()
        if classification == "RADIUS2_STRICT_IMPROVEMENT"
    }
    if strict_k == set(SUPPORTED_K_VALUES):
        return "CROSS_K_STRONG"
    if len(strict_k) > 1:
        return "CROSS_K_MIXED"
    if strict_k == {20}:
        return "K20_ONLY_SIGNAL"
    if not strict_k.intersection(SUPPORTED_K_EXECUTED_VALUES):
        return "NO_ADDITIONAL_SIGNAL"
    raise ValueError(f"unsupported cross-k classification state: {strict_k}")


def build_supported_k_comparison_payload(
    *,
    progress: SupportedKProgressCallback | None = None,
) -> dict[str, Any]:
    """Execute k=10/k=15 exactly and combine them with validated reused k=20."""

    base_identity = verify_supported_k_base_identity()
    reused_k20_row = load_reused_k20_row()
    rows: list[dict[str, Any]] = []
    metrics_by_k: dict[str, Any] = {}
    for k in SUPPORTED_K_EXECUTED_VALUES:
        row, metrics = _evaluate_supported_k_row(k, progress=progress)
        rows.append(row)
        metrics_by_k[str(k)] = metrics
    rows.append(reused_k20_row)
    metrics_by_k["20"] = {
        "measurement_status": "UNKNOWN_NOT_RECORDED_IN_REUSED_ARTIFACT",
        "peak_memory_bytes": None,
        "peak_memory_scope": "NOT_AVAILABLE_IN_REUSED_ARTIFACT",
        "runtime_scope": "NOT_AVAILABLE_IN_REUSED_ARTIFACT",
        "runtime_seconds": None,
    }

    classifications = {
        str(row["k"]): cast(str, row["outcome_classification"]) for row in rows
    }
    strict_count = sum(
        classification == "RADIUS2_STRICT_IMPROVEMENT"
        for classification in classifications.values()
    )
    no_improvement_count = sum(
        classification == "RADIUS2_NO_IMPROVEMENT"
        for classification in classifications.values()
    )
    resource_bound_count = sum(
        classification == "RESOURCE_BOUND" for classification in classifications.values()
    )
    payload: dict[str, Any] = {
        "canonical_base": base_identity,
        "comparison_contract": {
            "candidate_method_id": RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
            "combined_k_values": list(SUPPORTED_K_VALUES),
            "evaluation_window": "COMPLETE_STATIC_WINNING_SPACE",
            "executed_exact_k_values": list(SUPPORTED_K_EXECUTED_VALUES),
            "objective": "EXACT_M3_PLUS_FRACTION",
            "population": "POWER_LOTTO_ZONE1_ALL_C(38,6)_DRAWS",
            "primary_question": (
                "Does the exact radius-two improvement observed at k=20 also "
                "occur at k=10 and/or k=15?"
            ),
            "reused_exact_k_values": list(SUPPORTED_K_REUSED_VALUES),
            "source_method_id": RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
            "supported_k_values": list(SUPPORTED_K_VALUES),
            "tie_break": "LEXICOGRAPHIC_COMPLETE_PORTFOLIO",
        },
        "execution_metrics": {
            "by_k": metrics_by_k,
            "identity_disposition": "EXCLUDED_FROM_DETERMINISTIC_RESULT_IDENTITY",
        },
        "gate": {
            "complete_endpoint_enumeration_k10_k15": "PASS",
            "global_optimum_status": "UNKNOWN",
            "k20_evidence_reuse": "PASS",
            "matrix_method_registration": "PASS",
            "predictive_success_claims": "NONE",
            "radius1_source_certificates": "PASS",
            "supported_k_comparison": "PASS",
        },
        "k20_reuse_authority": {
            "artifact_path": str(OUTPUT_PATH),
            "artifact_sha256": OUTPUT_SHA256,
            "certificate_sha256": OUTPUT_K20_CERTIFICATE_SHA256,
            "evidence_reused": True,
            "exact_search_rerun": False,
            "result_identity_sha256": OUTPUT_RESULT_IDENTITY_SHA256,
        },
        "matrix_method_registration": [
            _registration_json(registration)
            for registration in registered_local_escape_methods()
        ],
        "rows": rows,
        "source_authority": {
            "path": str(SOURCE_AUTHORITY_PATH),
            "sha256": SOURCE_AUTHORITY_SHA256,
            "study_id": SOURCE_STUDY_ID,
            "task_id": SOURCE_TASK_ID,
        },
        "study_id": SUPPORTED_K_STUDY_ID,
        "summary": {
            "accepted_moves_by_k": {
                str(row["k"]): row["radius2_move_count"] for row in rows
            },
            "best_delta_by_k": {str(row["k"]): row["exact_delta"] for row in rows},
            "endpoint_evaluations_by_k": {
                str(row["k"]): row["unique_radius2_endpoints_evaluated"]
                for row in rows
            },
            "family_cross_k_classification": _family_cross_k_classification(rows),
            "no_improvement_k_count": no_improvement_count,
            "resource_bound_k_count": resource_bound_count,
            "result_by_k": classifications,
            "strict_improvement_k_count": strict_count,
        },
        "task_id": SUPPORTED_K_TASK_ID,
    }
    payload["result_identity"] = {
        "algorithm": "SHA256",
        "scope": (
            "canonical_json(result_without_result_identity_and_execution_metrics)"
        ),
        "sha256": supported_k_result_payload_sha256(payload),
    }
    return payload


def validate_supported_k_output() -> dict[str, Any]:
    """Validate the materialized cross-k artifact without rerunning any exact search."""

    raw = SUPPORTED_K_OUTPUT_PATH.read_bytes()
    payload = _mapping(json.loads(raw), locator="supported-k result")
    if canonical_json_bytes(payload) != raw:
        raise ValueError("SUPPORTED_K_RESULT_NOT_CANONICAL_JSON")
    if payload.get("study_id") != SUPPORTED_K_STUDY_ID:
        raise ValueError("SUPPORTED_K_RESULT_STUDY_ID_MISMATCH")
    if payload.get("task_id") != SUPPORTED_K_TASK_ID:
        raise ValueError("SUPPORTED_K_RESULT_TASK_ID_MISMATCH")
    if payload.get("canonical_base") != {
        "commit": SUPPORTED_K_PINNED_BASE_COMMIT,
        "tree": SUPPORTED_K_PINNED_BASE_TREE,
    }:
        raise ValueError("SUPPORTED_K_RESULT_BASE_IDENTITY_MISMATCH")
    result_identity = _mapping(
        payload.get("result_identity"), locator="supported-k result identity"
    )
    if result_identity.get("sha256") != SUPPORTED_K_RESULT_IDENTITY_SHA256:
        raise ValueError("SUPPORTED_K_RESULT_IDENTITY_PIN_MISMATCH")
    if supported_k_result_payload_sha256(payload) != SUPPORTED_K_RESULT_IDENTITY_SHA256:
        raise ValueError("SUPPORTED_K_RESULT_IDENTITY_MISMATCH")

    rows = _rows(payload.get("rows"), locator="supported-k rows")
    if [row.get("k") for row in rows] != list(SUPPORTED_K_VALUES):
        raise ValueError("SUPPORTED_K_RESULT_ROW_SCOPE_MISMATCH")
    if rows[-1] != load_reused_k20_row():
        raise ValueError("SUPPORTED_K_RESULT_REUSED_K20_ROW_MISMATCH")

    space = PackedWinningSpace.build(POOL_SIZE, DRAW_SIZE)
    classifications: dict[str, str] = {}
    for row in rows:
        k = cast(int, row["k"])
        source = load_radius_one_certificate(k)
        source_portfolio = _portfolio(
            row.get("source_reference_portfolio"),
            locator=f"k={k} source portfolio",
        )
        terminal_portfolio = _portfolio(
            row.get("best_radius2_portfolio"),
            locator=f"k={k} terminal portfolio",
        )
        if source_portfolio != source.portfolio:
            raise ValueError(f"SUPPORTED_K_K{k}_SOURCE_PORTFOLIO_MISMATCH")
        if row.get("best_radius2_portfolio_sha256") != portfolio_sha256(
            terminal_portfolio
        ):
            raise ValueError(f"SUPPORTED_K_K{k}_TERMINAL_PORTFOLIO_HASH_MISMATCH")
        input_q = _fraction(row.get("input_exact_objective"), locator=f"k={k} input Q")
        terminal_q = _fraction(
            row.get("best_exact_radius2_objective"), locator=f"k={k} terminal Q"
        )
        delta = _fraction(row.get("exact_delta"), locator=f"k={k} delta")
        if input_q != source.exact_q or space.exact_portfolio_q(source_portfolio) != input_q:
            raise ValueError(f"SUPPORTED_K_K{k}_SOURCE_Q_MISMATCH")
        if space.exact_portfolio_q(terminal_portfolio) != terminal_q:
            raise ValueError(f"SUPPORTED_K_K{k}_TERMINAL_Q_MISMATCH")
        if delta != terminal_q - input_q:
            raise ValueError(f"SUPPORTED_K_K{k}_DELTA_MISMATCH")

        classification = cast(str, row["outcome_classification"])
        expected_classification = (
            "RADIUS2_STRICT_IMPROVEMENT"
            if delta > 0
            else "RADIUS2_NO_IMPROVEMENT"
        )
        if classification != expected_classification:
            raise ValueError(f"SUPPORTED_K_K{k}_CLASSIFICATION_MISMATCH")
        classifications[str(k)] = classification
        if row.get("accepted") is not (delta > 0):
            raise ValueError(f"SUPPORTED_K_K{k}_ACCEPTANCE_MISMATCH")
        if row.get("global_optimum_status") != "UNKNOWN":
            raise ValueError(f"SUPPORTED_K_K{k}_GLOBAL_OPTIMUM_CLAIM_MISMATCH")

        certificate = _mapping(row.get("certificate"), locator=f"k={k} certificate")
        certificate_identity = _mapping(
            certificate.get("certificate_identity"),
            locator=f"k={k} certificate identity",
        )
        certificate_body = dict(certificate)
        certificate_body.pop("certificate_identity")
        if certificate_identity.get("sha256") != hashlib.sha256(
            canonical_json_bytes(certificate_body)
        ).hexdigest():
            raise ValueError(f"SUPPORTED_K_K{k}_CERTIFICATE_IDENTITY_MISMATCH")
        if certificate.get("complete_endpoint_enumeration") != "PASS":
            raise ValueError(f"SUPPORTED_K_K{k}_ENDPOINT_ENUMERATION_MISMATCH")
        trace = _rows(certificate.get("trace"), locator=f"k={k} certificate trace")
        if not trace or trace[-1].get("accepted_move") is not False:
            raise ValueError(f"SUPPORTED_K_K{k}_TERMINAL_TRACE_MISMATCH")
        if row.get("radius2_iteration_count") != len(trace):
            raise ValueError(f"SUPPORTED_K_K{k}_ITERATION_COUNT_MISMATCH")
        if row.get("radius2_move_count") != sum(
            iteration.get("accepted_move") is True for iteration in trace
        ):
            raise ValueError(f"SUPPORTED_K_K{k}_MOVE_COUNT_MISMATCH")
        if row.get("unique_radius2_endpoints_evaluated") != sum(
            cast(int, iteration["unique_endpoint_count"]) for iteration in trace
        ):
            raise ValueError(f"SUPPORTED_K_K{k}_ENDPOINT_COUNT_MISMATCH")
        if _fraction(certificate.get("best_exact_q"), locator=f"k={k} certificate Q") != (
            terminal_q
        ):
            raise ValueError(f"SUPPORTED_K_K{k}_CERTIFICATE_Q_MISMATCH")

        terminal_endpoint = _mapping(
            row.get("terminal_best_endpoint"), locator=f"k={k} terminal endpoint"
        )
        terminal_trace = trace[-1]
        if terminal_endpoint != {
            "exact_q": terminal_trace["best_endpoint_exact_q"],
            "portfolio": terminal_trace["best_endpoint_portfolio"],
            "portfolio_sha256": terminal_trace["best_endpoint_portfolio_sha256"],
        } or row.get("terminal_delta") != terminal_trace.get("delta"):
            raise ValueError(f"SUPPORTED_K_K{k}_TERMINAL_ENDPOINT_MISMATCH")
        row_identity = _mapping(
            row.get("row_result_identity"), locator=f"k={k} row result identity"
        )
        if row_identity.get("sha256") != _row_result_sha256(row):
            raise ValueError(f"SUPPORTED_K_K{k}_ROW_RESULT_IDENTITY_MISMATCH")

    summary = _mapping(payload.get("summary"), locator="supported-k summary")
    if summary.get("result_by_k") != classifications:
        raise ValueError("SUPPORTED_K_SUMMARY_RESULT_BY_K_MISMATCH")
    if summary.get("family_cross_k_classification") != _family_cross_k_classification(
        rows
    ):
        raise ValueError("SUPPORTED_K_FAMILY_CLASSIFICATION_MISMATCH")
    if summary.get("strict_improvement_k_count") != sum(
        value == "RADIUS2_STRICT_IMPROVEMENT" for value in classifications.values()
    ):
        raise ValueError("SUPPORTED_K_STRICT_COUNT_MISMATCH")
    if summary.get("no_improvement_k_count") != sum(
        value == "RADIUS2_NO_IMPROVEMENT" for value in classifications.values()
    ):
        raise ValueError("SUPPORTED_K_NO_IMPROVEMENT_COUNT_MISMATCH")
    if summary.get("resource_bound_k_count") != 0:
        raise ValueError("SUPPORTED_K_RESOURCE_BOUND_COUNT_MISMATCH")

    execution_metrics = _mapping(
        payload.get("execution_metrics"), locator="supported-k execution metrics"
    )
    metrics_by_k = _mapping(execution_metrics.get("by_k"), locator="metrics by k")
    for k in SUPPORTED_K_EXECUTED_VALUES:
        metrics = _mapping(metrics_by_k.get(str(k)), locator=f"k={k} metrics")
        runtime_seconds = metrics.get("runtime_seconds")
        peak_memory_bytes = metrics.get("peak_memory_bytes")
        if not isinstance(runtime_seconds, int | float) or runtime_seconds <= 0:
            raise ValueError(f"SUPPORTED_K_K{k}_RUNTIME_METRIC_MISMATCH")
        if type(peak_memory_bytes) is not int or peak_memory_bytes <= 0:
            raise ValueError(f"SUPPORTED_K_K{k}_MEMORY_METRIC_MISMATCH")
    reused_metrics = _mapping(metrics_by_k.get("20"), locator="k=20 metrics")
    if reused_metrics.get("runtime_seconds") is not None or reused_metrics.get(
        "peak_memory_bytes"
    ) is not None:
        raise ValueError("SUPPORTED_K_K20_REUSED_METRIC_MISMATCH")
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


def _supported_k_progress(k: int, message: str) -> None:
    if message.startswith("single slot="):
        completed, total = message.split()[1].split("=")[1].split("/")
        if completed == total:
            print(f"K{k}_RADIUS2_PROGRESS: {message}", flush=True)
        return
    if message.startswith("pair="):
        completed_text, total_text = message.split()[0].split("=")[1].split("/")
        completed = int(completed_text)
        total = int(total_text)
        if completed == 1 or completed == total or completed % 25 == 0:
            print(f"K{k}_RADIUS2_PROGRESS: {message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="recompute and require byte identity with the canonical result",
    )
    mode.add_argument(
        "--supported-k-expansion",
        action="store_true",
        help="execute exact k=10/k=15 and reuse the canonical k=20 result",
    )
    mode.add_argument(
        "--check-supported-k-expansion",
        action="store_true",
        help="validate the supported-k artifact without rerunning an exact search",
    )
    args = parser.parse_args()

    if args.check_supported_k_expansion:
        payload = validate_supported_k_output()
        identity = _mapping(payload["result_identity"], locator="result identity")
        print(
            "SUPPORTED_K_DETERMINISTIC_IDENTITY_CHECK: PASS "
            f"{identity['sha256']} {SUPPORTED_K_OUTPUT_PATH}",
            flush=True,
        )
        return

    if args.supported_k_expansion:
        if not SUPPORTED_K_OUTPUT_PATH.parent.is_dir():
            raise FileNotFoundError(
                f"canonical output directory missing: {SUPPORTED_K_OUTPUT_PATH.parent}"
            )
        if SUPPORTED_K_OUTPUT_PATH.exists():
            raise ValueError("REFUSING_TO_OVERWRITE_SUPPORTED_K_COMPARISON_RESULT")
        started = time.perf_counter()
        payload = build_supported_k_comparison_payload(progress=_supported_k_progress)
        SUPPORTED_K_OUTPUT_PATH.write_bytes(canonical_json_bytes(payload))
        validated = validate_supported_k_output()
        elapsed = time.perf_counter() - started
        summary = _mapping(validated["summary"], locator="supported-k summary")
        identity = _mapping(validated["result_identity"], locator="result identity")
        print(f"WROTE_SUPPORTED_K_RESULT: {SUPPORTED_K_OUTPUT_PATH}", flush=True)
        print(
            "SUPPORTED_K_COMPARISON_SUMMARY: "
            f"strict={summary['strict_improvement_k_count']} "
            f"no_improvement={summary['no_improvement_k_count']} "
            f"resource_bound={summary['resource_bound_k_count']} "
            f"family={summary['family_cross_k_classification']}",
            flush=True,
        )
        print(
            f"SUPPORTED_K_RESULT_IDENTITY_SHA256: {identity['sha256']}",
            flush=True,
        )
        print(f"SUPPORTED_K_TOTAL_RUNTIME_SECONDS: {elapsed:.6f}", flush=True)
        print(f"SUPPORTED_K_PROCESS_PEAK_MEMORY_BYTES: {_peak_memory_bytes()}", flush=True)
        return

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
