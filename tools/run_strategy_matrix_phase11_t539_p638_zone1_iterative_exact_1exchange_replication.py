"""Execute the Phase 11 native iterative exact 1-exchange replication.

The runner regenerates the sealed Phase-7 Method-E prefixes for DAILY_539 and
POWER_LOTTO Zone-1, verifies their frozen exact-Q and k=20 hash identities,
and invokes the canonical Phase-10 ascent implementation independently for
each requested rung. Runtime measurements are printed only; the result JSON
contains deterministic scientific evidence.
"""

from __future__ import annotations

import hashlib
import json
import resource
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.domain.lottery_rules import (
    DAILY_539_RULE_CONTRACT,
    POWER_LOTTO_RULE_CONTRACT,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor_p638_zone1 import (
    greedy_minmax_then_sum_overlap_portfolio_p638_zone1,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor_t539 import (
    greedy_minmax_then_sum_overlap_portfolio_t539,
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

STUDY_ID = (
    "STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_"
    "ITERATIVE_EXACT_1EXCHANGE_REPLICATION_V1"
)
TASK_ID = (
    "STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_"
    "ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1"
)
REFINEMENT_METHOD_ID = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
OWNER_AUTHORIZATION = (
    "AUTHORIZE_STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_"
    "ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1"
)
CANONICAL_METHOD_IMPLEMENTATION = (
    "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py"
)
PINNED_BASE_COMMIT = "1de7bf0d51160802115aa7ade416e5e717a00461"
PINNED_BASE_TREE = "895696e5c2ab87b7ebe1c294a2a32edcdefefe43"
K_SCOPE = (10, 15, 20)
MAX_K = max(K_SCOPE)

PREREGISTRATION_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-phase11-t539-p638-zone1-"
    "iterative-exact-1exchange-replication-v1-preregistration.md"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-phase11-t539-p638-zone1-"
    "iterative-exact-1exchange-replication-v1-result.json"
)
LOCKED_PREREGISTRATION_SHA256 = (
    "f44ac9547828794a861898330744fc8535a48c818fa35f609d30d3863f6fa1df"
)

TicketConstructor = Callable[[int], Portfolio]


@dataclass(frozen=True, slots=True)
class NativeStructure:
    structure_id: str
    lottery_type: str
    zone: str | None
    pool_size: int
    draw_size: int
    primary_event: str
    phase7_authority_path: Path
    phase7_authority_sha256: str
    phase7_study_id: str
    phase7_status_key: str
    phase7_status: str
    phase7_gate_key: str
    expected_method_e_sha256_k20: str
    expected_method_e_q: dict[int, Fraction]
    constructor: TicketConstructor


STRUCTURES: tuple[NativeStructure, ...] = (
    NativeStructure(
        structure_id="DAILY_539",
        lottery_type="DAILY_539",
        zone=None,
        pool_size=39,
        draw_size=5,
        primary_event="M3_PLUS",
        phase7_authority_path=Path(
            "docs/research/matrix-native-results/"
            "constructor-frontier-next-generation-t539-v1-result.json"
        ),
        phase7_authority_sha256=(
            "5e8a52d5e841b9c7e0f29711ded55e717421cc0334c272bd94ac2ee84ebe9474"
        ),
        phase7_study_id="STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1",
        phase7_status_key="t539_replication_status",
        phase7_status="T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED",
        phase7_gate_key="t539_replication_gate",
        expected_method_e_sha256_k20=(
            "81830474195db8ae460367b71ecea271a390aaa432c5af4bd78fc18c65c09b60"
        ),
        expected_method_e_q={
            10: Fraction(2734, 27417),
            15: Fraction(9475, 63973),
            20: Fraction(152, 777),
        },
        constructor=greedy_minmax_then_sum_overlap_portfolio_t539,
    ),
    NativeStructure(
        structure_id="POWER_LOTTO_ZONE1",
        lottery_type="POWER_LOTTO",
        zone="zone1",
        pool_size=38,
        draw_size=6,
        primary_event="ZONE1_M3_PLUS",
        phase7_authority_path=Path(
            "docs/research/matrix-native-results/"
            "constructor-frontier-next-generation-p638-zone1-v1-result.json"
        ),
        phase7_authority_sha256=(
            "77e6df9e8baa8202c886d6b30808b5c78993bfda13b4eab7710ae60f5ea139ed"
        ),
        phase7_study_id=(
            "STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1"
        ),
        phase7_status_key="p638_replication_status",
        phase7_status="P638_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED",
        phase7_gate_key="p638_replication_gate",
        expected_method_e_sha256_k20=(
            "59182264db6be95ab51dff64f0548f1a5f1163ca33e8b4a646fe02db383d8d85"
        ),
        expected_method_e_q={
            10: Fraction(52270, 145299),
            15: Fraction(126653, 250971),
            20: Fraction(578195, 920227),
        },
        constructor=greedy_minmax_then_sum_overlap_portfolio_p638_zone1,
    ),
)


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


def _portfolio_json(portfolio: Portfolio) -> list[list[int]]:
    return [list(ticket) for ticket in portfolio]


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
    if observed["commit"] != PINNED_BASE_COMMIT or observed["tree"] != PINNED_BASE_TREE:
        raise ValueError(
            "CANONICAL_BASE_IDENTITY_MISMATCH: "
            f"expected {PINNED_BASE_COMMIT}/{PINNED_BASE_TREE}, got "
            f"{observed['commit']}/{observed['tree']}"
        )
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PINNED_BASE_COMMIT, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise ValueError(
            "CANONICAL_BASE_ANCESTRY_MISMATCH: "
            f"{PINNED_BASE_COMMIT} is not an ancestor of HEAD"
        )
    return observed


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


def _validate_native_mapping(spec: NativeStructure) -> None:
    if spec.structure_id == "DAILY_539":
        if (
            DAILY_539_RULE_CONTRACT.main_number_max != 39
            or DAILY_539_RULE_CONTRACT.main_number_count != 5
        ):
            raise ValueError("STOP_PHASE11_T539_NATIVE_MAPPING_DRIFT")
    elif spec.structure_id == "POWER_LOTTO_ZONE1":
        if (
            POWER_LOTTO_RULE_CONTRACT.main_number_max != 38
            or POWER_LOTTO_RULE_CONTRACT.main_number_count != 6
        ):
            raise ValueError("STOP_PHASE11_P638_NATIVE_MAPPING_DRIFT")
    else:
        raise ValueError(f"unsupported structure: {spec.structure_id}")

    if spec.pool_size <= spec.draw_size:
        raise ValueError(f"invalid native dimensions for {spec.structure_id}")


def verify_phase7_authority(spec: NativeStructure) -> dict[str, Any]:
    if not spec.phase7_authority_path.exists():
        raise FileNotFoundError(f"Phase-7 authority missing: {spec.phase7_authority_path}")
    authority_bytes = spec.phase7_authority_path.read_bytes()
    authority_sha256 = hashlib.sha256(authority_bytes).hexdigest()
    if authority_sha256 != spec.phase7_authority_sha256:
        raise ValueError(
            f"PHASE7_AUTHORITY_IDENTITY_MISMATCH {spec.structure_id}: "
            f"expected {spec.phase7_authority_sha256}, got {authority_sha256}"
        )

    raw_payload: Any = json.loads(authority_bytes)
    if not isinstance(raw_payload, dict):
        raise ValueError(f"{spec.structure_id} Phase-7 authority root must be an object")
    payload = cast(dict[str, Any], raw_payload)
    if payload.get("study_id") != spec.phase7_study_id:
        raise ValueError(f"PHASE7_AUTHORITY_STUDY_ID_MISMATCH {spec.structure_id}")
    if payload.get("constructor_id") != "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1":
        raise ValueError(f"PHASE7_AUTHORITY_CONSTRUCTOR_MISMATCH {spec.structure_id}")
    if payload.get("primary_event_minimum_matches") != 3:
        raise ValueError(f"PHASE7_AUTHORITY_EVENT_MISMATCH {spec.structure_id}")
    if payload.get(spec.phase7_status_key) != spec.phase7_status:
        raise ValueError(f"PHASE7_AUTHORITY_STATUS_MISMATCH {spec.structure_id}")
    gate = payload.get(spec.phase7_gate_key)
    if not isinstance(gate, dict):
        raise ValueError(f"PHASE7_AUTHORITY_GATE_MISMATCH {spec.structure_id}")
    gate_mapping = cast(dict[str, Any], gate)
    if gate_mapping.get("passed") is not True:
        raise ValueError(f"PHASE7_AUTHORITY_GATE_MISMATCH {spec.structure_id}")
    if spec.zone is not None and payload.get("p638_zone") != spec.zone:
        raise ValueError(f"PHASE7_AUTHORITY_ZONE_MISMATCH {spec.structure_id}")
    if spec.zone is not None and payload.get("p638_zone2") != "NOT_RUN":
        raise ValueError("PHASE7_P638_ZONE2_MUST_REMAIN_NOT_RUN")

    portfolio_hashes = payload.get("portfolio_sha256")
    if not isinstance(portfolio_hashes, dict):
        raise ValueError(f"PHASE7_METHOD_E_HASH_MISSING {spec.structure_id}")
    portfolio_hash_mapping = cast(dict[str, Any], portfolio_hashes)
    if portfolio_hash_mapping.get("e") != spec.expected_method_e_sha256_k20:
        raise ValueError(f"PHASE7_METHOD_E_HASH_MISMATCH {spec.structure_id}")

    raw_per_k = payload.get("per_k")
    if not isinstance(raw_per_k, dict):
        raise ValueError(f"PHASE7_PER_K_MISSING {spec.structure_id}")
    per_k_mapping = cast(dict[str, Any], raw_per_k)
    for k, expected_q in spec.expected_method_e_q.items():
        entry = per_k_mapping.get(str(k))
        if not isinstance(entry, dict):
            raise ValueError(f"PHASE7_PER_K_MISSING {spec.structure_id} k={k}")
        entry_mapping = cast(dict[str, Any], entry)
        actual_q = _parse_rational(
            entry_mapping.get("q_e"), locator=f"{spec.structure_id}.q_e.{k}"
        )
        if actual_q != expected_q:
            raise ValueError(
                f"PHASE7_METHOD_E_Q_MISMATCH {spec.structure_id} k={k}: "
                f"expected {expected_q}, got {actual_q}"
            )

    return {
        "path": str(spec.phase7_authority_path),
        "sha256": authority_sha256,
        "study_id": spec.phase7_study_id,
        "status": spec.phase7_status,
        "method_e_portfolio_sha256_k20": spec.expected_method_e_sha256_k20,
        "method_e_q": {str(k): rational(q) for k, q in spec.expected_method_e_q.items()},
    }


def validate_portfolio(
    portfolio: Portfolio,
    *,
    pool_size: int,
    draw_size: int,
    ticket_count: int,
) -> None:
    if len(portfolio) != ticket_count:
        raise ValueError(f"expected {ticket_count} tickets, got {len(portfolio)}")
    if len(set(portfolio)) != len(portfolio):
        raise ValueError("portfolio contains duplicate tickets")
    for ticket in portfolio:
        if len(ticket) != draw_size or len(set(ticket)) != draw_size:
            raise ValueError("illegal ticket shape")
        if tuple(sorted(ticket)) != ticket:
            raise ValueError("tickets must be ascending")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError("ticket number out of range")


def regenerate_method_e(
    spec: NativeStructure,
) -> tuple[Portfolio, dict[int, Portfolio]]:
    full_portfolio = spec.constructor(MAX_K)
    validate_portfolio(
        full_portfolio,
        pool_size=spec.pool_size,
        draw_size=spec.draw_size,
        ticket_count=MAX_K,
    )
    full_hash = portfolio_sha256(full_portfolio)
    if full_hash != spec.expected_method_e_sha256_k20:
        raise ValueError(
            f"REGENERATED_METHOD_E_HASH_MISMATCH {spec.structure_id}: "
            f"expected {spec.expected_method_e_sha256_k20}, got {full_hash}"
        )

    prefixes: dict[int, Portfolio] = {}
    for k in K_SCOPE:
        raw_prefix = full_portfolio[:k]
        prefixes[k] = canonicalize_portfolio(raw_prefix)
    return full_portfolio, prefixes


def _serialize_iteration(
    spec: NativeStructure,
    iteration: ExactOneExchangeAscentIteration,
) -> dict[str, Any]:
    delta = rational(iteration.delta)
    return {
        "structure_id": spec.structure_id,
        "accepted_move": iteration.accepted_move,
        "best_neighbor_portfolio": _portfolio_json(iteration.best_neighbor_portfolio),
        "best_neighbor_portfolio_sha256": portfolio_sha256(
            iteration.best_neighbor_portfolio
        ),
        "delta": delta,
        "exact_delta": delta,
        "exact_best_neighbor_q": rational(iteration.best_neighbor_q),
        "exact_input_q": rational(iteration.input_q),
        "input_portfolio": _portfolio_json(iteration.input_portfolio),
        "input_portfolio_sha256": portfolio_sha256(iteration.input_portfolio),
        "iteration_index": iteration.iteration_index,
        "unique_legal_neighbor_count": iteration.unique_legal_neighbor_count,
    }


def serialize_rung(
    spec: NativeStructure,
    k: int,
    seed: Portfolio,
    method_e_q: Fraction,
    ascent: ExactOneExchangeAscentResult,
) -> dict[str, Any]:
    expected_seed_q = spec.expected_method_e_q[k]
    seed_sha256 = portfolio_sha256(seed)
    if ascent.seed_portfolio != seed:
        raise ValueError(f"{spec.structure_id} k={k} ascent seed portfolio changed")
    if ascent.seed_q != expected_seed_q:
        raise ValueError(
            f"{spec.structure_id} k={k} exact seed Q mismatch: "
            f"expected {expected_seed_q}, got {ascent.seed_q}"
        )
    if seed_sha256 != portfolio_sha256(ascent.seed_portfolio):
        raise ValueError(f"{spec.structure_id} k={k} seed hash changed")
    if not ascent.iterations:
        raise ValueError(f"{spec.structure_id} k={k} missing terminal iteration")

    accepted_iterations = tuple(
        iteration for iteration in ascent.iterations if iteration.accepted_move
    )
    terminal_iteration = ascent.iterations[-1]
    accepted_moves_strict = all(iteration.delta > 0 for iteration in accepted_iterations)
    terminal_best_lte = terminal_iteration.best_neighbor_q <= ascent.terminal_q
    terminal_rejected = not terminal_iteration.accepted_move
    move_count_consistent = ascent.move_count == len(accepted_iterations)
    terminal_input_consistent = (
        terminal_iteration.input_portfolio == ascent.terminal_portfolio
        and terminal_iteration.input_q == ascent.terminal_q
    )
    certificate_pass = all(
        (
            accepted_moves_strict,
            terminal_best_lte,
            terminal_rejected,
            move_count_consistent,
            terminal_input_consistent,
        )
    )
    if not certificate_pass:
        raise ValueError(f"{spec.structure_id} k={k} terminal certificate failed")

    terminal_q = rational(ascent.terminal_q)
    terminal_delta = rational(ascent.terminal_q - method_e_q)
    return {
        "structure_id": spec.structure_id,
        "k": k,
        "seed_method_e_portfolio": _portfolio_json(seed),
        "seed_method_e_portfolio_sha256": seed_sha256,
        "seed_exact_q": rational(ascent.seed_q),
        "seed_method_e_q": rational(method_e_q),
        "method_e_q": rational(method_e_q),
        "iteration_count": len(ascent.iterations),
        "iterations": [_serialize_iteration(spec, iteration) for iteration in ascent.iterations],
        "move_count": ascent.move_count,
        "terminal_portfolio": _portfolio_json(ascent.terminal_portfolio),
        "terminal_portfolio_sha256": portfolio_sha256(ascent.terminal_portfolio),
        "terminal_q": terminal_q,
        "terminal_exact_q": terminal_q,
        "exact_delta_terminal_vs_method_e": terminal_delta,
        "delta_terminal_vs_method_e": terminal_delta,
        "terminal_classification": "TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED",
        "terminal_certificate": {
            "accepted_moves_strict_exact_improvements": accepted_moves_strict,
            "move_count_consistent": move_count_consistent,
            "status": "PASS",
            "terminal_best_q_lte_terminal_q": terminal_best_lte,
            "terminal_input_consistent": terminal_input_consistent,
            "terminal_iteration_accepted_move": terminal_iteration.accepted_move,
        },
    }


def execute_phase11_replication() -> dict[str, Any]:
    preregistration_sha256 = verify_preregistration_lock()
    base_identity = verify_current_base_identity()
    print(f"Verified preregistration sha256: {preregistration_sha256}", flush=True)
    print(
        f"Verified canonical base: {base_identity['commit']} "
        f"tree={base_identity['tree']}",
        flush=True,
    )

    per_structure: dict[str, Any] = {}
    per_structure_gate: dict[str, dict[str, str]] = {}
    runtime_seconds: dict[str, dict[str, float]] = {}
    task_started = time.perf_counter()

    for spec in STRUCTURES:
        _validate_native_mapping(spec)
        authority = verify_phase7_authority(spec)
        print(
            f"Verified Phase-7 authority {spec.structure_id}: "
            f"{authority['sha256']}",
            flush=True,
        )

        generation_started = time.perf_counter()
        full_portfolio, prefixes = regenerate_method_e(spec)
        raw_prefixes = {k: full_portfolio[:k] for k in K_SCOPE}
        generation_seconds = time.perf_counter() - generation_started
        print(
            f"Regenerated Method E {spec.structure_id} k=20: "
            f"{portfolio_sha256(full_portfolio)} in {generation_seconds:.6f}s",
            flush=True,
        )

        per_k: dict[str, Any] = {}
        per_k_gate: dict[str, str] = {}
        runtime_seconds[spec.structure_id] = {
            "method_e_generation_seconds": generation_seconds
        }
        structure_payload: dict[str, Any] = {
            "structure_id": spec.structure_id,
            "lottery_type": spec.lottery_type,
            "zone": spec.zone,
            "pool_size": spec.pool_size,
            "draw_size": spec.draw_size,
            "primary_event": spec.primary_event,
            "primary_event_minimum_matches": 3,
            "k_scope": list(K_SCOPE),
            "phase7_authority": authority,
            "method_e_regeneration": {
                "constructor_id": "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1",
                "portfolio_20": _portfolio_json(full_portfolio),
                "portfolio_20_sha256": portfolio_sha256(full_portfolio),
                "canonical_portfolio_20": _portfolio_json(canonicalize_portfolio(full_portfolio)),
                "canonical_portfolio_20_sha256": portfolio_sha256(
                    canonicalize_portfolio(full_portfolio)
                ),
                "matches_sealed_phase7_k20_authority": True,
                "prefix_policy": "portfolio(k) == portfolio(20)[:k]",
                "seed_canonicalization": "canonicalize_portfolio(raw_prefix)",
                "per_k": {},
            },
            "per_k": per_k,
        }

        for k in K_SCOPE:
            seed = prefixes[k]
            method_e_q = spec.expected_method_e_q[k]
            print(
                f"Starting independent exact ascent {spec.structure_id} k={k} "
                f"seed_sha256={portfolio_sha256(seed)} Q={method_e_q}",
                flush=True,
            )
            rung_started = time.perf_counter()
            ascent = iterative_exact_one_exchange_ascent(
                pool_size=spec.pool_size,
                draw_size=spec.draw_size,
                minimum_matches=3,
                seed_portfolio=seed,
            )
            rung_seconds = time.perf_counter() - rung_started
            runtime_seconds[spec.structure_id][f"k_{k}_seconds"] = rung_seconds
            rung = serialize_rung(spec, k, seed, method_e_q, ascent)
            per_k[str(k)] = rung
            structure_payload["method_e_regeneration"]["per_k"][str(k)] = {
                "portfolio": _portfolio_json(seed),
                "portfolio_sha256": portfolio_sha256(seed),
                "source_portfolio": _portfolio_json(raw_prefixes[k]),
                "source_portfolio_sha256": portfolio_sha256(raw_prefixes[k]),
                "exact_q": rational(method_e_q),
            }
            per_k_gate[str(k)] = rung["terminal_certificate"]["status"]
            print(
                f"Completed {spec.structure_id} k={k}: "
                f"moves={ascent.move_count} terminal_Q={ascent.terminal_q} "
                f"seconds={rung_seconds:.6f}",
                flush=True,
            )

        per_structure[spec.structure_id] = structure_payload
        per_structure_gate[spec.structure_id] = per_k_gate

    all_certificates_pass = all(
        status == "PASS"
        for structure_gate in per_structure_gate.values()
        for status in structure_gate.values()
    )
    if not all_certificates_pass:
        raise ValueError("PHASE11_EXECUTION_GATE failed")

    runtime_seconds["total_elapsed_seconds"] = {
        "all_structures_seconds": time.perf_counter() - task_started
    }
    scientific_payload: dict[str, Any] = {
        "canonical_base": {
            "commit": PINNED_BASE_COMMIT,
            "tree": PINNED_BASE_TREE,
        },
        "canonical_method_implementation": CANONICAL_METHOD_IMPLEMENTATION,
        "draw_sizes": {spec.structure_id: spec.draw_size for spec in STRUCTURES},
        "exposure_ladder": list(K_SCOPE),
        "gate": {
            "global_optimum_status": "UNKNOWN",
            "per_structure_k_terminal_certificate": per_structure_gate,
            "phase11_execution_gate": "PASS",
        },
        "invariants": {
            "candidate_sampling": "NONE",
            "cross_k_coupling": "NONE",
            "cross_structure_state_sharing": "NONE",
            "db_access": False,
            "global_optimum_status": "UNKNOWN",
            "historical_draws_used": False,
            "iteration_cap": "NONE",
            "monte_carlo": "NONE",
            "p638_zone2": "NOT_RUN",
            "plateau_moves_accepted": False,
            "phase7_reseal": "NOT_RUN",
            "restarts": "NONE",
            "rng": "NONE",
            "second_exchange_performed": False,
        },
        "lottery_structures": [spec.structure_id for spec in STRUCTURES],
        "owner_authorization": OWNER_AUTHORIZATION,
        "preregistration": {
            "path": str(PREREGISTRATION_PATH),
            "sha256": preregistration_sha256,
        },
        "primary_event_minimum_matches": 3,
        "refinement_method_id": REFINEMENT_METHOD_ID,
        "reproduction_policy": {
            "canonical_json_excludes_performance_measurements": True,
            "fresh_process_byte_identity_required": True,
        },
        "rung_coupling": "NONE",
        "scope": {
            "daily_539": "RUN",
            "power_lotto_zone1": "RUN",
            "power_lotto_zone2": "NOT_RUN",
            "secondary_events": "NOT_RUN",
        },
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
        "structures": per_structure,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(canonical_json_bytes(scientific_payload))
    peak_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"Wrote deterministic result: {OUTPUT_PATH}", flush=True)
    print(f"RUNTIME_SECONDS: {json.dumps(runtime_seconds, sort_keys=True)}", flush=True)
    print(f"PEAK_MEMORY_RUSAGE_RAW: {peak_memory}", flush=True)
    print("PHASE11_EXECUTION_GATE: PASS", flush=True)
    print("GLOBAL_OPTIMUM_STATUS: UNKNOWN", flush=True)
    return scientific_payload


def main() -> None:
    execute_phase11_replication()


if __name__ == "__main__":
    main()
