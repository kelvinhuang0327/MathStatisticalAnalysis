"""Run the sealed Phase 10 iterative exact 1-exchange ascent for B649.

The three rungs are executed sequentially and independently from the immutable
Phase 9 best-neighbor portfolios.  The canonical JSON contains deterministic
scientific authority only; elapsed time and peak memory are printed separately.
"""

from __future__ import annotations

import hashlib
import json
import resource
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    canonicalize_portfolio,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    ExactOneExchangeAscentIteration,
    ExactOneExchangeAscentResult,
    iterative_exact_one_exchange_ascent,
)

STUDY_ID = "STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1"
TASK_ID = "STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1"
REFINEMENT_METHOD_ID = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
OWNER_AUTHORIZATION = (
    "AUTHORIZE_STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1"
)

PINNED_BASE_COMMIT = "d024c52895b68191f20564c7d7494782f374ca4a"
PINNED_BASE_TREE = "df025ea5a9c52a4fe06325c68c97dad4508b964b"

PREREGISTRATION_PATH = Path(
    "docs/research/matrix-native-results/"
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-preregistration.md"
)
PHASE9_RESULT_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-result.json"
)

LOCKED_PREREGISTRATION_SHA256 = (
    "593dc33d34190063c5be5817a36bab4bfd3d64a9b98dac2ca1d942d06b567cfd"
)
LOCKED_PHASE9_RESULT_SHA256 = (
    "5c45204d227cc3750b9efe68ec9afeb3d83d6bd72104acbe319897fc94013e00"
)


@dataclass(frozen=True, slots=True)
class FrozenSeedAuthority:
    k: int
    portfolio: Portfolio
    portfolio_sha256: str
    q: Fraction
    method_e_q: Fraction


FROZEN_SEED_IDENTITIES: dict[int, tuple[str, Fraction]] = {
    10: (
        "4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5",
        Fraction(90995, 499422),
    ),
    15: (
        "ba6f516af65c31246550827ddcdcff2fcbf3f588be336e6de959a59dc898d1c8",
        Fraction(464027, 1747977),
    ),
    20: (
        "a107d9cb5c7e0def7b19ccf2a6d02306b25bc0efe3443ea9899f3a4755429a4a",
        Fraction(171323, 499422),
    ),
}


def rational(value: Fraction) -> dict[str, int | str]:
    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def portfolio_sha256(portfolio: Portfolio) -> str:
    payload = json.dumps(portfolio, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    serialized = json.dumps(payload, indent=2, sort_keys=True).rstrip("\n") + "\n"
    return serialized.encode("utf-8")


def _parse_rational(payload: Any, *, locator: str) -> Fraction:
    if not isinstance(payload, dict):
        raise ValueError(f"{locator} must be an object")
    mapping = cast(dict[str, Any], payload)
    numerator = mapping.get("numerator")
    denominator = mapping.get("denominator")
    exact = mapping.get("exact")
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise ValueError(f"{locator} numerator/denominator must be integers")
    value = Fraction(numerator, denominator)
    if exact != f"{value.numerator}/{value.denominator}":
        raise ValueError(f"{locator} exact string is inconsistent")
    return value


def _parse_portfolio(payload: Any, *, locator: str) -> Portfolio:
    if not isinstance(payload, list):
        raise ValueError(f"{locator} must be an array")
    tickets: list[tuple[int, ...]] = []
    for ticket_index, ticket_payload in enumerate(cast(list[Any], payload)):
        if not isinstance(ticket_payload, list):
            raise ValueError(f"{locator}[{ticket_index}] must be an array")
        numbers = cast(list[Any], ticket_payload)
        if not all(isinstance(number, int) for number in numbers):
            raise ValueError(f"{locator}[{ticket_index}] must contain only integers")
        tickets.append(tuple(cast(int, number) for number in numbers))
    return canonicalize_portfolio(tickets)


def verify_preregistration_lock() -> str:
    if not PREREGISTRATION_PATH.exists():
        raise FileNotFoundError(f"preregistration file missing: {PREREGISTRATION_PATH}")
    computed = hashlib.sha256(PREREGISTRATION_PATH.read_bytes()).hexdigest()
    if computed != LOCKED_PREREGISTRATION_SHA256:
        raise ValueError(
            "preregistration sha256 mismatch: "
            f"expected {LOCKED_PREREGISTRATION_SHA256}, got {computed}"
        )
    return computed


def load_and_verify_phase9_seed_authority() -> dict[int, FrozenSeedAuthority]:
    """Verify all frozen Phase 9 SHA/Q identities before Phase 10 execution."""
    if not PHASE9_RESULT_PATH.exists():
        raise FileNotFoundError(f"Phase 9 authority missing: {PHASE9_RESULT_PATH}")
    phase9_bytes = PHASE9_RESULT_PATH.read_bytes()
    phase9_sha256 = hashlib.sha256(phase9_bytes).hexdigest()
    if phase9_sha256 != LOCKED_PHASE9_RESULT_SHA256:
        raise ValueError(
            "PHASE9_AUTHORITY_IDENTITY_MISMATCH: "
            f"expected {LOCKED_PHASE9_RESULT_SHA256}, got {phase9_sha256}"
        )

    raw_payload: Any = json.loads(phase9_bytes)
    if not isinstance(raw_payload, dict):
        raise ValueError("Phase 9 authority root must be an object")
    payload = cast(dict[str, Any], raw_payload)
    if payload.get("study_id") != "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1":
        raise ValueError("Phase 9 study identity mismatch")
    raw_per_k = payload.get("per_k")
    if not isinstance(raw_per_k, dict):
        raise ValueError("Phase 9 per_k authority missing")
    per_k = cast(dict[str, Any], raw_per_k)

    authorities: dict[int, FrozenSeedAuthority] = {}
    for k in (10, 15, 20):
        raw_entry = per_k.get(str(k))
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Phase 9 k={k} entry missing")
        entry = cast(dict[str, Any], raw_entry)
        portfolio = _parse_portfolio(
            entry.get("best_neighbor_portfolio"),
            locator=f"per_k.{k}.best_neighbor_portfolio",
        )
        if len(portfolio) != k:
            raise ValueError(f"Phase 9 k={k} portfolio length mismatch")

        expected_sha256, expected_q = FROZEN_SEED_IDENTITIES[k]
        artifact_sha256 = entry.get("best_neighbor_portfolio_sha256")
        computed_sha256 = portfolio_sha256(portfolio)
        if artifact_sha256 != expected_sha256 or computed_sha256 != expected_sha256:
            raise ValueError(
                f"PHASE9_SEED_IDENTITY_MISMATCH k={k}: "
                f"expected {expected_sha256}, artifact {artifact_sha256}, "
                f"computed {computed_sha256}"
            )

        q = _parse_rational(entry.get("q_best_neighbor"), locator=f"per_k.{k}.q_best_neighbor")
        if q != expected_q:
            raise ValueError(
                f"PHASE9_SEED_Q_MISMATCH k={k}: expected {expected_q}, got {q}"
            )
        method_e_q = _parse_rational(
            entry.get("q_reference_e"), locator=f"per_k.{k}.q_reference_e"
        )
        authorities[k] = FrozenSeedAuthority(
            k=k,
            portfolio=portfolio,
            portfolio_sha256=expected_sha256,
            q=q,
            method_e_q=method_e_q,
        )

    if set(authorities) != {10, 15, 20}:
        raise ValueError("Phase 9 authority did not yield exactly k={10,15,20}")
    return authorities


def _portfolio_json(portfolio: Portfolio) -> list[list[int]]:
    return [list(ticket) for ticket in portfolio]


def _serialize_iteration(iteration: ExactOneExchangeAscentIteration) -> dict[str, Any]:
    return {
        "accepted_move": iteration.accepted_move,
        "best_neighbor_portfolio": _portfolio_json(iteration.best_neighbor_portfolio),
        "best_neighbor_portfolio_sha256": portfolio_sha256(
            iteration.best_neighbor_portfolio
        ),
        "delta": rational(iteration.delta),
        "exact_best_neighbor_q": rational(iteration.best_neighbor_q),
        "exact_input_q": rational(iteration.input_q),
        "input_portfolio": _portfolio_json(iteration.input_portfolio),
        "input_portfolio_sha256": portfolio_sha256(iteration.input_portfolio),
        "iteration_index": iteration.iteration_index,
        "unique_legal_neighbor_count": iteration.unique_legal_neighbor_count,
    }


def _serialize_rung(
    authority: FrozenSeedAuthority,
    ascent: ExactOneExchangeAscentResult,
) -> dict[str, Any]:
    if ascent.seed_portfolio != authority.portfolio:
        raise ValueError(f"k={authority.k} ascent seed portfolio changed")
    if ascent.seed_q != authority.q:
        raise ValueError(
            f"k={authority.k} exact seed Q mismatch: expected {authority.q}, got {ascent.seed_q}"
        )
    if not ascent.iterations:
        raise ValueError(f"k={authority.k} missing terminal iteration")

    accepted_iterations = tuple(
        iteration for iteration in ascent.iterations if iteration.accepted_move
    )
    terminal_iteration = ascent.iterations[-1]
    accepted_moves_strict = all(iteration.delta > 0 for iteration in accepted_iterations)
    terminal_best_lte = terminal_iteration.best_neighbor_q <= ascent.terminal_q
    terminal_rejected = not terminal_iteration.accepted_move
    move_count_consistent = ascent.move_count == len(accepted_iterations)
    terminal_certificate_pass = all(
        (
            accepted_moves_strict,
            terminal_best_lte,
            terminal_rejected,
            move_count_consistent,
            terminal_iteration.input_portfolio == ascent.terminal_portfolio,
            terminal_iteration.input_q == ascent.terminal_q,
        )
    )
    if not terminal_certificate_pass:
        raise ValueError(f"k={authority.k} terminal certificate failed")

    return {
        "delta_terminal_vs_method_e": rational(ascent.terminal_q - authority.method_e_q),
        "delta_terminal_vs_phase9_seed": rational(ascent.terminal_q - authority.q),
        "iteration_count": len(ascent.iterations),
        "iterations": [_serialize_iteration(iteration) for iteration in ascent.iterations],
        "k": authority.k,
        "method_e_q": rational(authority.method_e_q),
        "move_count": ascent.move_count,
        "phase9_seed_portfolio": _portfolio_json(authority.portfolio),
        "phase9_seed_portfolio_sha256": authority.portfolio_sha256,
        "phase9_seed_q": rational(authority.q),
        "terminal_certificate": {
            "accepted_moves_strict_exact_improvements": accepted_moves_strict,
            "move_count_consistent": move_count_consistent,
            "status": "PASS",
            "terminal_best_q_lte_terminal_q": terminal_best_lte,
            "terminal_iteration_accepted_move": terminal_iteration.accepted_move,
        },
        "terminal_classification": "TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED",
        "terminal_portfolio": _portfolio_json(ascent.terminal_portfolio),
        "terminal_portfolio_sha256": portfolio_sha256(ascent.terminal_portfolio),
        "terminal_q": rational(ascent.terminal_q),
    }


def execute_phase10_ascent() -> dict[str, Any]:
    preregistration_sha256 = verify_preregistration_lock()
    seed_authorities = load_and_verify_phase9_seed_authority()
    print(f"Verified preregistration sha256: {preregistration_sha256}", flush=True)
    for k in (10, 15, 20):
        authority = seed_authorities[k]
        print(
            f"Verified Phase 9 seed k={k}: {authority.portfolio_sha256} Q={authority.q}",
            flush=True,
        )

    per_k: dict[str, Any] = {}
    runtime_seconds: dict[str, float] = {}
    for k in (10, 15, 20):
        authority = seed_authorities[k]
        print(f"Starting independent exact ascent k={k}...", flush=True)
        started = time.perf_counter()
        ascent = iterative_exact_one_exchange_ascent(
            pool_size=49,
            draw_size=6,
            minimum_matches=3,
            seed_portfolio=authority.portfolio,
        )
        runtime_seconds[str(k)] = time.perf_counter() - started
        per_k[str(k)] = _serialize_rung(authority, ascent)
        print(
            f"Completed k={k}: moves={ascent.move_count} terminal_Q={ascent.terminal_q} "
            f"seconds={runtime_seconds[str(k)]:.6f}",
            flush=True,
        )

    per_k_gate = {k: value["terminal_certificate"]["status"] for k, value in per_k.items()}
    phase10_pass = all(status == "PASS" for status in per_k_gate.values())
    if not phase10_pass:
        raise ValueError("PHASE10_EXECUTION_GATE failed")

    result_payload: dict[str, Any] = {
        "canonical_base": {
            "commit": PINNED_BASE_COMMIT,
            "tree": PINNED_BASE_TREE,
        },
        "draw_size": 6,
        "exposure_ladder": [10, 15, 20],
        "gate": {
            "global_optimum_status": "UNKNOWN",
            "per_k_terminal_certificate": per_k_gate,
            "phase10_execution_gate": "PASS",
        },
        "invariants": {
            "candidate_sampling": "NONE",
            "cross_structure_execution": "NOT_RUN",
            "db_access": False,
            "historical_draws_used": False,
            "iteration_cap": "NONE",
            "monte_carlo": "NONE",
            "p638_execution": "NOT_RUN",
            "plateau_moves_accepted": False,
            "restarts": "NONE",
            "rng": "NONE",
            "second_exchange_performed": False,
            "t539_execution": "NOT_RUN",
        },
        "lottery_type": "BIG_LOTTO",
        "owner_authorization": OWNER_AUTHORIZATION,
        "per_k": per_k,
        "phase9_authority": {
            "path": str(PHASE9_RESULT_PATH),
            "sha256": LOCKED_PHASE9_RESULT_SHA256,
            "study_id": "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1",
        },
        "pool_size": 49,
        "preregistration": {
            "path": str(PREREGISTRATION_PATH),
            "sha256": preregistration_sha256,
        },
        "primary_event": "M3_PLUS",
        "primary_event_minimum_matches": 3,
        "reference_policy": {
            "cross_structure_policy": "NEXT_IF_PHASE10_PASSES",
            "global_optimum_status": "UNKNOWN",
            "method_e_status": "HISTORICAL_CONSTRUCTOR_REFERENCE",
            "reference_promotion": "NOT_AUTHORIZED",
            "runtime_promotion": "NOT_AUTHORIZED",
        },
        "refinement_method_id": REFINEMENT_METHOD_ID,
        "reproduction_policy": {
            "canonical_json_excludes_performance_measurements": True,
            "fresh_process_byte_identity_required": True,
        },
        "rung_coupling": "NONE",
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
    }

    OUTPUT_PATH.write_bytes(canonical_json_bytes(result_payload))
    peak_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"Wrote deterministic result: {OUTPUT_PATH}", flush=True)
    print(f"RUNTIME_SECONDS_BY_K: {json.dumps(runtime_seconds, sort_keys=True)}", flush=True)
    print(f"PEAK_MEMORY_RUSAGE_RAW: {peak_memory}", flush=True)
    print("PHASE10_EXECUTION_GATE: PASS", flush=True)
    print("GLOBAL_OPTIMUM_STATUS: UNKNOWN", flush=True)
    return result_payload


def main() -> None:
    execute_phase10_ascent()


if __name__ == "__main__":
    main()
