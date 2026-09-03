"""Outcome-free intake and comparison of existing Strategy Matrix methods.

The research ledger owns method metadata; this module only dispatches already
implemented algorithms and normalizes their evidence. It does not register a
production strategy, fit anything, rank strategies, or define a composite score.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    DAILY_539_RULE_CONTRACT,
    POWER_LOTTO_RULE_CONTRACT,
    LotteryRuleContract,
)
from lottolab.research.biglotto_multi_ticket_constructors_r1 import CONSTRUCTORS
from lottolab.research.bounded_coverage_optimizer import exact_portfolio_coverage
from lottolab.research.bounded_coverage_optimizer_fast import restart_greedy_swap_search_fast
from lottolab.research.cyclic_sidon_shift import sidon_shift_portfolio as sidon_b649
from lottolab.research.cyclic_sidon_shift_p638_zone1 import sidon_shift_portfolio as sidon_p638
from lottolab.research.cyclic_sidon_shift_t539 import sidon_shift_portfolio as sidon_t539
from lottolab.research.exact_coverage_baseline import exact_random_portfolio_coverage
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    fast_exact_portfolio_coverage,
)
from lottolab.research.global_exact_coverage_solver import PAIRWISE_MAX_INTERSECTION
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_sum_then_reuse_dispersion_constructor import (
    greedy_minmax_sum_then_reuse_dispersion_portfolio,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)
from lottolab.research.hard_div_pairwise_bounded_candidate_adapter import (
    METHOD_ID as HARD_DIV,
)
from lottolab.research.hard_div_pairwise_bounded_candidate_adapter import (
    AdapterStatus,
    HardDivPairwiseBoundedCandidateResult,
    HardDivPairwiseSearchEvidence,
    big_lotto_dispatch,
    run_hard_div_pairwise_bounded_candidate_adapter,
)
from lottolab.research.low_overlap_portfolio_constructor import (
    build_low_overlap_portfolio,
    compute_portfolio_geometry_metrics,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    evaluate_one_exchange_neighborhood,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    iterative_exact_one_exchange_ascent,
)

K_SCOPE = (2, 3, 5, 10, 20)
LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
RESULT_PATH = Path(
    "docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json"
)
NATIVE_MEASUREMENT_KEY = "native_coverage_r1"
NATIVE_MEASUREMENT_PATH = Path(
    "docs/research/matrix-native-results/strategy-matrix-native-evidence-coverage-r1-result.json"
)
NATIVE_MEASUREMENT_SCHEMA_VERSION = "1.0.0"
NATIVE_CANDIDATE_POOL_KIND = "clustered_plus_sidon"
NATIVE_MEASUREMENT_MINIMUM_MATCHES = 3
NATIVE_MAX_SAMPLE_ATTEMPTS = 200
SIDON = "CYCLIC_SIDON_SHIFT_V1"
ARM_B = "GREEDY_MIN_OVERLAP_V1"
ARM_E = "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
ARM_F = "GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1"
CANDIDATE = "CANDIDATE_LOW_OVERLAP_V1"
BOUNDED = "RESTART_GREEDY_SWAP_COVERAGE_SEARCH_V1"
ONE_EXCHANGE = "REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1"
ITERATIVE = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
HARD_DIV_R2 = "HARD_DIV_PAIRWISE_OVERLAP_R2"
HARD_DIV_RADIUS2_RECONCILIATION_PATH = Path(
    "docs/research/matrix-native-results/hard-div-exact-radius2-reconciliation-r1-result.json"
)
HARD_DIV_RADIUS2_RECONCILIATION_SHA256 = (
    "2d37c6dceb69664b489a458f46d201d9e13b544a08c3924ece8b848f44d25b82"
)
METHOD_IDS = (
    SIDON,
    ARM_B,
    ARM_E,
    ARM_F,
    CANDIDATE,
    BOUNDED,
    ONE_EXCHANGE,
    ITERATIVE,
    HARD_DIV,
    HARD_DIV_R2,
    *CONSTRUCTORS,
)
# Methods whose supported cells are executed inline by their own canonical adapter.
# They are therefore never "open" cells awaiting the native-coverage checkpoint.
NATIVE_DIRECT_DISPATCH = frozenset({HARD_DIV, HARD_DIV_R2})
# A portfolio hash is only comparable alongside the byte convention that produced it.
# The Matrix's own portfolio_sha256 uses canonical_json_bytes; a native method may
# carry a differently-canonicalized identity of the same portfolio, which is expected.
NATIVE_PORTFOLIO_HASH_CANONICALIZATION = "COMPACT_JSON_NO_TRAILING_NEWLINE"
RULES = {
    "BIG_LOTTO": BIG_LOTTO_RULE_CONTRACT,
    "DAILY_539": DAILY_539_RULE_CONTRACT,
    "POWER_LOTTO_ZONE1": POWER_LOTTO_RULE_CONTRACT,
}
SIDON_CONSTRUCTORS = {
    "BIG_LOTTO": sidon_b649,
    "DAILY_539": sidon_t539,
    "POWER_LOTTO_ZONE1": sidon_p638,
}
GREEDY_CONSTRUCTORS: Mapping[str, Callable[[int, int, int], Portfolio]] = {
    ARM_B: greedy_min_overlap_portfolio,
    ARM_E: greedy_minmax_then_sum_overlap_portfolio,
    ARM_F: greedy_minmax_sum_then_reuse_dispersion_portfolio,
}
TOY_RULES = replace(DAILY_539_RULE_CONTRACT, main_number_max=14, main_number_count=4)
TOY_SEARCH_BUDGET = {
    "seed": 20260815,
    "restart_count": 2,
    "candidate_sample_size": 10,
    "max_swap_passes": 2,
}
type JsonObject = dict[str, Any]


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def rational(value: Fraction) -> JsonObject:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
    }


def parse_rational(value: JsonObject) -> Fraction:
    """Accept the two existing exact encodings, but reject conflicting authorities."""
    result = Fraction(value["exact"])
    if "numerator" in value and result != Fraction(value["numerator"], value["denominator"]):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: rational fields disagree")
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned_file(root: Path, entry: JsonObject) -> Path:
    relative = Path(entry["path"])
    path = root / relative
    if relative.is_absolute() or ".." in relative.parts or path.is_symlink():
        raise ValueError("intake source must be a repository file")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("intake source escapes repository")
    if _sha256(path) != entry["sha256"]:
        raise ValueError(f"intake evidence changed: {relative}")
    return path


def load_matrix(root: Path) -> JsonObject:
    """Fail closed before dispatch if intake, source or evidence identity drifts."""
    ledger = json.loads((root / LEDGER_PATH).read_text())
    matrix = cast(JsonObject, ledger["imported_optimizer_matrix"])
    if matrix["schema_version"] != "1.0.0" or matrix["supported_k"] != list(K_SCOPE):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: matrix schema/k")
    if matrix["canonical_result_path"] != RESULT_PATH.as_posix():
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: canonical result path")
    methods: list[JsonObject] = matrix["methods"]
    ids = [method["strategy_id"] for method in methods]
    if len(ids) != len(set(ids)) or set(ids) != set(METHOD_IDS):
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: duplicate or unknown method")
    if len(methods) != 13 or len({method["strategy_family"] for method in methods}) != 8:
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: method/family intake count")
    required = {
        "strategy_family",
        "strategy_id",
        "method_type",
        "portfolio_or_ticket_level",
        "supported_lottery",
        "supported_k",
        "objective",
        "search_type",
        "neighborhood_radius",
        "exact_or_heuristic",
        "diversification_constraint",
        "deterministic",
        "source_status",
        "core_correctness_test",
        "source_files",
        "correctness_evidence",
        "supports_synthetic_shape",
        "evidence_source",
        "proof_status",
    }
    for method in methods:
        if not required <= method.keys():
            raise ValueError("incomplete imported method metadata")
        if method["source_status"] != "IMPLEMENTED" or method["core_correctness_test"] != "PASS":
            raise ValueError("IMPORTED_METHOD_CORE_CORRECTNESS_UNKNOWN")
        if method["deterministic"] is not True:
            raise ValueError("imported method is not deterministic under its fixed inputs")
        supported = method["supported_k"]
        if (
            not supported
            or any(type(k) is not int or k not in K_SCOPE for k in supported)
            or len(set(supported)) != len(supported)
        ):
            raise ValueError("invalid imported k scope")
        if method["strategy_id"] in CONSTRUCTORS and supported != [5, 10, 20]:
            raise ValueError("frozen native constructor budget contract changed")
        if not method["source_files"] or not method["correctness_evidence"]:
            raise ValueError("IMPORTED_METHOD_CORE_CORRECTNESS_UNKNOWN")
        for entry in [*method["source_files"], *method["correctness_evidence"]]:
            _pinned_file(root, entry)
    for entry in matrix["native_evidence"].values():
        _pinned_file(root, entry)
    return matrix


def _row(
    method: JsonObject,
    case_id: str,
    lottery: str,
    k: int,
    *,
    scope: str,
    status: str = "MEASURED",
    reason: str | None = None,
    variant: str = "default",
    minimum_matches: int | None = None,
) -> JsonObject:
    dimensions = {
        field: method[field]
        for field in (
            "strategy_family",
            "strategy_id",
            "method_type",
            "portfolio_or_ticket_level",
            "objective",
            "search_type",
            "neighborhood_radius",
            "exact_or_heuristic",
            "diversification_constraint",
            "deterministic",
            "source_status",
            "evidence_source",
            "proof_status",
        )
    }
    return {
        **dimensions,
        "row_id": f"{case_id}|{method['strategy_id']}|{variant}|k{k}|m{minimum_matches}",
        "case_id": case_id,
        "lottery": lottery,
        "k": k,
        "variant": variant,
        "zone": "zone1" if lottery == "POWER_LOTTO_ZONE1" else None,
        "evidence_scope": scope,
        "status": status,
        "status_reason": reason,
        "minimum_matches": minimum_matches,
        "evaluation_objective": "UNIFORM_MAIN_DRAW_COVERAGE" if minimum_matches else "GEOMETRY",
        "exact_q": None,
        "q_random_expected": None,
        "delta_vs_reference": None,
        "reference": None,
        "geometry": None,
        "portfolio": None,
        "search_evidence": None,
        "source_evidence": None,
        "local_optimum_status": "NOT_CERTIFIED",
        "global_optimum_status": "UNKNOWN",
    }


def _attach_q(
    row: JsonObject,
    rules: LotteryRuleContract,
    q: Fraction,
    reference_q: Fraction,
    reference_id: str,
) -> None:
    if not 0 <= q <= 1 or not 0 <= reference_q <= 1:
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: coverage outside [0,1]")
    row["pool_size"] = rules.main_number_max
    row["draw_size"] = rules.main_number_count
    row["exact_q"] = rational(q)
    row["reference"] = {"strategy_id": reference_id, "exact_q": rational(reference_q)}
    row["delta_vs_reference"] = rational(q - reference_q)
    row["q_random_expected"] = rational(
        exact_random_portfolio_coverage(
            rules.main_number_max,
            rules.main_number_count,
            row["minimum_matches"],
            row["k"],
        )
    )
    if q == 1:
        # A mathematical upper bound, NOT a claim of exhaustive portfolio search.
        row["global_optimum_status"] = "CERTIFIED_BY_UNIT_UPPER_BOUND"
        row["global_optimum_proof"] = "Exact Q=1 attains the universal probability upper bound."
        row["proof_status"] = "GLOBAL_OPTIMUM_CERTIFIED_BY_UNIT_UPPER_BOUND"


def _attach_portfolio(row: JsonObject, rules: LotteryRuleContract, portfolio: Portfolio) -> None:
    if len(portfolio) != row["k"] or len(set(portfolio)) != row["k"]:
        raise ValueError("imported portfolio violated exact-k/distinct-ticket contract")
    for ticket in portfolio:
        if (
            len(ticket) != rules.main_number_count
            or tuple(sorted(set(ticket))) != ticket
            or any(type(n) is not int or not 1 <= n <= rules.main_number_max for n in ticket)
        ):
            raise ValueError("imported portfolio contains an illegal ticket")
    row["pool_size"] = rules.main_number_max
    row["draw_size"] = rules.main_number_count
    row["portfolio"] = portfolio
    row["portfolio_sha256"] = hashlib.sha256(canonical_json_bytes(portfolio)).hexdigest()
    row["geometry"] = asdict(compute_portfolio_geometry_metrics(portfolio, rules))
    row["geometry"]["mean_pairwise_overlap_exact"] = rational(
        Fraction(
            sum(size * count for size, count in row["geometry"]["overlap_profile"].items()),
            math.comb(row["k"], 2),
        )
    )


def _attach_native_portfolio_hash(row: JsonObject, native_sha256: str) -> None:
    """Carry a native method's own portfolio identity without recomputing it.

    This never replaces ``portfolio_sha256``: that field stays the Matrix-owned
    identity derived from the stored portfolio by ``_attach_portfolio``, so it
    cannot be spoofed by an upstream producer. A native method's hash answers a
    different question - "is this the same portfolio the adapter sealed?" - and
    is recorded alongside the byte convention that produced it, because a hash
    without its canonicalization is not a comparable identity.
    """

    if len(native_sha256) != 64 or not all(c in "0123456789abcdef" for c in native_sha256):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native portfolio hash")
    row["native_portfolio_sha256"] = native_sha256
    row["native_portfolio_sha256_canonicalization"] = NATIVE_PORTFOLIO_HASH_CANONICALIZATION


def _exact(rules: LotteryRuleContract, minimum: int, portfolio: Portfolio) -> Fraction:
    return exact_portfolio_coverage(
        rules.main_number_max,
        rules.main_number_count,
        minimum,
        portfolio,
    )


def compare_neighborhood(
    method: JsonObject,
    rules: LotteryRuleContract,
    seed: Portfolio,
    minimum_matches: int,
    *,
    case_id: str,
    reference_id: str,
) -> JsonObject:
    """Keep a non-improving one-step neighbor separate from the retained portfolio."""
    row = _row(
        method,
        case_id,
        "SYNTHETIC",
        len(seed),
        scope="SYNTHETIC_UNIFORM_WINNING_SPACE",
        minimum_matches=minimum_matches,
    )
    if method["strategy_id"] == ITERATIVE and minimum_matches != 3:
        row.update(status="NOT_APPLICABLE", status_reason="ITERATIVE_EVALUATOR_REQUIRES_M3_PLUS")
        return row
    n, d = rules.main_number_max, rules.main_number_count
    if method["strategy_id"] == ONE_EXCHANGE:
        evaluated = evaluate_one_exchange_neighborhood(n, d, minimum_matches, seed)
        accepted = evaluated["delta_vs_reference"] > 0
        portfolio = evaluated["best_neighbor"] if accepted else seed
        q = evaluated["q_best_neighbor"] if accepted else evaluated["q_reference"]
        reference_q = evaluated["q_reference"]
        row["search_evidence"] = {
            "all_neighbors_evaluated": evaluated["all_neighbors_evaluated"],
            "unique_legal_neighbor_count": evaluated["unique_neighbor_count"],
            "best_neighbor_q": rational(evaluated["q_best_neighbor"]),
            "best_neighbor_delta": rational(evaluated["delta_vs_reference"]),
            "accepted_move": accepted,
            "neighborhood_unit": "REMOVE_ONE_ADD_ONE_NUMBER_IN_ONE_TICKET",
        }
        if not accepted:
            row["local_optimum_status"] = "CERTIFIED_ONE_NUMBER_EXCHANGE"
            row["proof_status"] = "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_NO_GLOBAL_PROOF"
    else:
        result = iterative_exact_one_exchange_ascent(n, d, minimum_matches, seed)
        portfolio, q, reference_q = result.terminal_portfolio, result.terminal_q, result.seed_q
        row["search_evidence"] = {
            "move_count": result.move_count,
            "neighborhood_unit": "REMOVE_ONE_ADD_ONE_NUMBER_IN_ONE_TICKET",
            "iterations": [
                {
                    "input_q": rational(item.input_q),
                    "best_neighbor_q": rational(item.best_neighbor_q),
                    "delta": rational(item.delta),
                    "accepted_move": item.accepted_move,
                    "unique_legal_neighbor_count": item.unique_legal_neighbor_count,
                    "input_portfolio": item.input_portfolio,
                    "best_neighbor_portfolio": item.best_neighbor_portfolio,
                }
                for item in result.iterations
            ],
        }
        row["local_optimum_status"] = "CERTIFIED_ONE_NUMBER_EXCHANGE"
        row["proof_status"] = "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_NO_GLOBAL_PROOF"
    _attach_portfolio(row, rules, portfolio)
    _attach_q(row, rules, q, reference_q, reference_id)
    return row


def _toy_rows(methods: Mapping[str, JsonObject]) -> list[JsonObject]:
    rows: list[JsonObject] = []
    prefixes = {key: fn(14, 4, 20) for key, fn in GREEDY_CONSTRUCTORS.items()}
    for minimum in (2, 3):
        for k in K_SCOPE:
            baseline = prefixes[ARM_E][:k]
            baseline_q = _exact(TOY_RULES, minimum, baseline)
            for method_id, prefix in prefixes.items():
                row = _row(
                    methods[method_id],
                    "TOY_14_4",
                    "SYNTHETIC",
                    k,
                    scope="SYNTHETIC_UNIFORM_WINNING_SPACE",
                    minimum_matches=minimum,
                )
                portfolio = prefix[:k]
                reference_id = ARM_B if method_id == ARM_E else ARM_E
                _attach_portfolio(row, TOY_RULES, portfolio)
                _attach_q(
                    row,
                    TOY_RULES,
                    _exact(TOY_RULES, minimum, portfolio),
                    _exact(TOY_RULES, minimum, prefixes[reference_id][:k]),
                    reference_id,
                )
                rows.append(row)
            result = restart_greedy_swap_search_fast(14, 4, minimum, k, **TOY_SEARCH_BUDGET)
            # Restart 0 and the multi-restart selection come from ONE unchanged
            # invocation, not two tuned algorithms or two method families.
            for variant, portfolio, q in (
                (
                    "first_restart",
                    result.restart_outcomes[0].portfolio,
                    result.restart_outcomes[0].coverage,
                ),
                ("best_restart", result.portfolio, result.coverage),
            ):
                row = _row(
                    methods[BOUNDED],
                    "TOY_14_4",
                    "SYNTHETIC",
                    k,
                    scope="SYNTHETIC_UNIFORM_WINNING_SPACE",
                    variant=variant,
                    minimum_matches=minimum,
                )
                row["search_type"] = (
                    "SINGLE_RESTART_HEURISTIC"
                    if variant == "first_restart"
                    else "BEST_OF_RESTARTS_HEURISTIC"
                )
                row["search_evidence"] = {
                    "budget": TOY_SEARCH_BUDGET,
                    "evaluations_used_entire_invocation": result.evaluations_used,
                    "best_restart_index": result.best_restart_index,
                    "restart_coverages": [
                        rational(item.coverage) for item in result.restart_outcomes
                    ],
                    "sampled_converged_by_restart": [
                        item.converged for item in result.restart_outcomes
                    ],
                    "neighborhood_unit": "SAMPLED_WHOLE_TICKET_REPLACEMENT",
                }
                row["local_optimum_status"] = "NOT_CERTIFIED_SAMPLED_NEIGHBORHOOD"
                _attach_portfolio(row, TOY_RULES, portfolio)
                _attach_q(row, TOY_RULES, q, baseline_q, ARM_E)
                rows.append(row)
            for method_id in (ONE_EXCHANGE, ITERATIVE):
                rows.append(
                    compare_neighborhood(
                        methods[method_id],
                        TOY_RULES,
                        baseline,
                        minimum,
                        case_id="TOY_14_4",
                        reference_id=ARM_E,
                    )
                )
    # This pre-existing correctness fixture discriminates one-step from iterative
    # ascent even where the greedy reference already happens to be locally optimal.
    rules = replace(TOY_RULES, main_number_max=8)
    seed = ((1, 2, 3, 4), (1, 2, 3, 5))
    for method_id in (ONE_EXCHANGE, ITERATIVE):
        rows.append(
            compare_neighborhood(
                methods[method_id],
                rules,
                seed,
                3,
                case_id="EXISTING_TWO_MOVE_FIXTURE_8_4",
                reference_id="EXISTING_CORE_TEST_SEED",
            )
        )
    return rows


def candidate_pool(lottery: str, kind: str) -> Portfolio:
    """Declared synthetic inputs, independent of every historical/future draw."""
    rules = RULES[lottery]
    n, d = rules.main_number_max, rules.main_number_count
    if kind == "clustered_plus_sidon":
        clustered = tuple(itertools.islice(itertools.combinations(range(1, n + 1), d), 20))
        return tuple(dict.fromkeys((*clustered, *SIDON_CONSTRUCTORS[lottery](20))))
    if kind != "uniform_seeded":
        raise ValueError("unknown synthetic candidate case")
    rng = random.Random(20260815)
    tickets: dict[tuple[int, ...], None] = {}
    while len(tickets) < 40:
        tickets[tuple(sorted(rng.sample(range(1, n + 1), d)))] = None
    return tuple(tickets)


def _candidate_rows(methods: Mapping[str, JsonObject]) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for lottery, rules in RULES.items():
        for kind in ("clustered_plus_sidon", "uniform_seeded"):
            candidates = candidate_pool(lottery, kind)
            variants = [(CANDIDATE, "geometry_only"), (CANDIDATE, "score_priority")]
            if lottery == "BIG_LOTTO":
                variants.extend((method_id, "default") for method_id in CONSTRUCTORS)
            for k in K_SCOPE:
                for method_id, variant in variants:
                    method = methods[method_id]
                    row = _row(
                        method,
                        f"CANDIDATES_{lottery}_{kind}",
                        lottery,
                        k,
                        scope="NATIVE_RULE_SYNTHETIC_CANDIDATE_GEOMETRY",
                        variant=variant,
                    )
                    row["candidate_pool_sha256"] = hashlib.sha256(
                        canonical_json_bytes(candidates)
                    ).hexdigest()
                    row["candidate_count"] = len(candidates)
                    if k not in method["supported_k"]:
                        row.update(status="NOT_APPLICABLE", status_reason="UNSUPPORTED_NATIVE_K")
                        rows.append(row)
                        continue
                    if method_id == CANDIDATE:
                        scores = (
                            [float(len(candidates) - i) for i in range(len(candidates))]
                            if variant == "score_priority"
                            else None
                        )
                        portfolio = build_low_overlap_portfolio(candidates, k, rules, scores)
                    else:
                        portfolio = CONSTRUCTORS[method_id](candidates, k)
                    _attach_portfolio(row, rules, portfolio)
                    row["reference"] = {
                        "strategy_id": "INPUT_ORDER_PREFIX",
                        "geometry": asdict(
                            compute_portfolio_geometry_metrics(candidates[:k], rules)
                        ),
                    }
                    row["coverage_status"] = "NOT_RUN"
                    row["coverage_status_reason"] = (
                        "Geometry comparison only; no native winning-space run."
                    )
                    rows.append(row)
    return rows


def _pointer(payload: Any, pointer: str) -> Any:
    current: object = payload
    for part in pointer.strip("/").split("/"):
        if isinstance(current, list):
            current = cast(list[object], current)[int(part)]
        elif isinstance(current, dict):
            current = cast(dict[str, object], current)[part]
        else:
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: invalid evidence pointer")
    return current


def _native_locator(method_id: str, lottery: str, k: int) -> tuple[str, str] | None:
    structure_key = {
        "BIG_LOTTO": "next_b649",
        "DAILY_539": "next_t539",
        "POWER_LOTTO_ZONE1": "next_p638",
    }[lottery]
    if method_id in (SIDON, ARM_B, ARM_E) and k in (3, 5, 10, 20):
        arm = {SIDON: "a", ARM_B: "b", ARM_E: "e"}[method_id]
        return structure_key, f"/per_k/{k}/q_{arm}"
    if method_id == BOUNDED and lottery == "BIG_LOTTO" and k in (3, 5, 10, 20):
        return "frontier_b649", f"/q/c/3/{k}"
    if method_id == ARM_F and lottery == "BIG_LOTTO" and k in (10, 20):
        return "method_f", f"/per_k/{k}/q_f"
    if method_id == ONE_EXCHANGE and lottery == "BIG_LOTTO" and k in (10, 20):
        return "one_exchange", f"/per_k/{k}/q_best_neighbor"
    if method_id == ITERATIVE and k in (10, 20):
        if lottery == "BIG_LOTTO":
            return "ascent_b649", f"/per_k/{k}/terminal_q"
        return "ascent_cross", f"/structures/{lottery}/per_k/{k}/terminal_q"
    return None


def _native_supported_specs(
    methods: Mapping[str, JsonObject],
) -> list[tuple[str, LotteryRuleContract, str, JsonObject, int]]:
    """Derive supported native cells from the canonical method/lottery matrix."""

    return [
        (lottery, rules, method_id, method, k)
        for lottery, rules in RULES.items()
        for method_id, method in methods.items()
        for k in K_SCOPE
        if lottery in method["supported_lottery"] and k in method["supported_k"]
    ]


def _native_row_id(lottery: str, method_id: str, k: int) -> str:
    return f"NATIVE_{lottery}|{method_id}|default|k{k}|m{NATIVE_MEASUREMENT_MINIMUM_MATCHES}"


def _is_checkpoint_managed(method_id: str, lottery: str, k: int) -> bool:
    """True for supported cells with neither pinned evidence nor a direct executor.

    Only these cells are carried by the native-coverage checkpoint. A method in
    ``NATIVE_DIRECT_DISPATCH`` runs its own canonical adapter inline, so it is
    never an open cell and must not widen the checkpoint's expected identity set.
    """

    if method_id in NATIVE_DIRECT_DISPATCH:
        return False
    return _native_locator(method_id, lottery, k) is None


def _native_supported_not_run_row_ids(methods: Mapping[str, JsonObject]) -> list[str]:
    """Return the open native identities without maintaining a second cell list."""

    return sorted(
        _native_row_id(lottery, method_id, k)
        for lottery, _rules, method_id, _method, k in _native_supported_specs(methods)
        if _is_checkpoint_managed(method_id, lottery, k)
    )


def _load_native_documents(root: Path, matrix: JsonObject) -> dict[str, JsonObject]:
    entries = cast(dict[str, JsonObject], matrix["native_evidence"])
    return {
        key: cast(JsonObject, json.loads((root / entry["path"]).read_text()))
        for key, entry in entries.items()
        if key != NATIVE_MEASUREMENT_KEY
    }


def _native_search_budget(documents: Mapping[str, JsonObject]) -> dict[str, int]:
    """Reuse the already-sealed native bounded-search budget."""

    optimizer = cast(JsonObject, documents["frontier_b649"]["optimizer"])
    keys = ("seed", "restart_count", "candidate_sample_size", "max_swap_passes")
    budget = {key: optimizer[key] for key in keys}
    if any(type(budget[key]) is not int or budget[key] <= 0 for key in keys):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: invalid native search budget")
    budget["max_sample_attempts"] = NATIVE_MAX_SAMPLE_ATTEMPTS
    return cast(dict[str, int], budget)


def _portfolio_from_json(value: Any) -> Portfolio:
    if not isinstance(value, list):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: measured portfolio is not a list")
    tickets = cast(list[list[int]], value)
    return tuple(tuple(ticket) for ticket in tickets)


def _measure_native_row(
    method: JsonObject,
    lottery: str,
    rules: LotteryRuleContract,
    k: int,
    search_budget: Mapping[str, int],
    documents: Mapping[str, JsonObject],
) -> JsonObject:
    """Execute one supported native cell through an existing deterministic method."""

    method_id = cast(str, method["strategy_id"])
    minimum_matches = NATIVE_MEASUREMENT_MINIMUM_MATCHES
    row = _row(
        method,
        f"NATIVE_{lottery}",
        lottery,
        k,
        scope="NATIVE_UNIFORM_WINNING_SPACE",
        minimum_matches=minimum_matches,
    )
    number_max = rules.main_number_max
    draw_size = rules.main_number_count
    measurement_evidence: JsonObject = {
        "execution_classification": "EXECUTED_EXISTING_NATIVE_METHOD",
        "method_invocation": method_id,
        "minimum_matches": minimum_matches,
    }

    reference_portfolio: Portfolio | None = None
    reference_q: Fraction
    portfolio: Portfolio
    q: Fraction
    reference_locator = _native_locator(ARM_E, lottery, k)
    if reference_locator is not None:
        reference_source, reference_pointer = reference_locator
        reference_q = parse_rational(_pointer(documents[reference_source], reference_pointer))
        measurement_evidence["reference_q_reused_from_native_evidence"] = True
        measurement_evidence["reference_q_locator"] = {
            "source_key": reference_source,
            "json_pointer": reference_pointer,
        }
        if method_id in (ONE_EXCHANGE, ITERATIVE):
            reference_portfolio = GREEDY_CONSTRUCTORS[ARM_E](number_max, draw_size, k)
    else:
        reference_portfolio = GREEDY_CONSTRUCTORS[ARM_E](number_max, draw_size, k)
        reference_q = fast_exact_portfolio_coverage(
            number_max, draw_size, minimum_matches, reference_portfolio
        )

    if method_id == CANDIDATE:
        candidates = candidate_pool(lottery, NATIVE_CANDIDATE_POOL_KIND)
        portfolio = build_low_overlap_portfolio(candidates, k, rules)
        row["candidate_pool_kind"] = NATIVE_CANDIDATE_POOL_KIND
        row["candidate_pool_sha256"] = hashlib.sha256(
            canonical_json_bytes(candidates)
        ).hexdigest()
        row["candidate_count"] = len(candidates)
        measurement_evidence.update(
            {
                "candidate_pool_kind": NATIVE_CANDIDATE_POOL_KIND,
                "candidate_pool_scope": "NATIVE_RULE_SYNTHETIC_CANDIDATE_POOL",
                "candidate_selection_mode": "GEOMETRY_ONLY",
            }
        )
        clear_cache()
        q = fast_exact_portfolio_coverage(number_max, draw_size, minimum_matches, portfolio)
    elif method_id in CONSTRUCTORS:
        candidates = candidate_pool("BIG_LOTTO", NATIVE_CANDIDATE_POOL_KIND)
        portfolio = CONSTRUCTORS[method_id](candidates, k)
        row["candidate_pool_kind"] = NATIVE_CANDIDATE_POOL_KIND
        row["candidate_pool_sha256"] = hashlib.sha256(
            canonical_json_bytes(candidates)
        ).hexdigest()
        row["candidate_count"] = len(candidates)
        measurement_evidence.update(
            {
                "candidate_pool_kind": NATIVE_CANDIDATE_POOL_KIND,
                "candidate_pool_scope": "NATIVE_RULE_SYNTHETIC_CANDIDATE_POOL",
                "candidate_selection_mode": "FROZEN_B649_CONSTRUCTOR",
            }
        )
        clear_cache()
        q = fast_exact_portfolio_coverage(number_max, draw_size, minimum_matches, portfolio)
    elif method_id == SIDON:
        portfolio = SIDON_CONSTRUCTORS[lottery](k)
        clear_cache()
        q = fast_exact_portfolio_coverage(number_max, draw_size, minimum_matches, portfolio)
    elif method_id in GREEDY_CONSTRUCTORS:
        portfolio = GREEDY_CONSTRUCTORS[method_id](number_max, draw_size, k)
        clear_cache()
        q = fast_exact_portfolio_coverage(number_max, draw_size, minimum_matches, portfolio)
    elif method_id == BOUNDED:
        result = restart_greedy_swap_search_fast(
            number_max,
            draw_size,
            minimum_matches,
            k,
            seed=search_budget["seed"],
            restart_count=search_budget["restart_count"],
            candidate_sample_size=search_budget["candidate_sample_size"],
            max_swap_passes=search_budget["max_swap_passes"],
            max_sample_attempts=search_budget["max_sample_attempts"],
        )
        portfolio, q = result.portfolio, result.coverage
        row["local_optimum_status"] = "NOT_CERTIFIED_SAMPLED_NEIGHBORHOOD"
        row["search_evidence"] = {
            "budget": dict(search_budget),
            "evaluations_used_entire_invocation": result.evaluations_used,
            "best_restart_index": result.best_restart_index,
            "restart_coverages": [
                rational(item.coverage) for item in result.restart_outcomes
            ],
            "sampled_converged_by_restart": [
                item.converged for item in result.restart_outcomes
            ],
            "neighborhood_unit": "SAMPLED_WHOLE_TICKET_REPLACEMENT",
        }
        measurement_evidence["search_budget"] = dict(search_budget)
    elif method_id == ONE_EXCHANGE:
        assert reference_portfolio is not None
        evaluated = evaluate_one_exchange_neighborhood(
            number_max, draw_size, minimum_matches, reference_portfolio
        )
        accepted = evaluated["delta_vs_reference"] > 0
        portfolio = evaluated["best_neighbor"] if accepted else reference_portfolio
        q = evaluated["q_best_neighbor"] if accepted else evaluated["q_reference"]
        reference_q = evaluated["q_reference"]
        row["search_evidence"] = {
            "all_neighbors_evaluated": evaluated["all_neighbors_evaluated"],
            "unique_legal_neighbor_count": evaluated["unique_neighbor_count"],
            "best_neighbor_q": rational(evaluated["q_best_neighbor"]),
            "best_neighbor_delta": rational(evaluated["delta_vs_reference"]),
            "accepted_move": accepted,
            "neighborhood_unit": "REMOVE_ONE_ADD_ONE_NUMBER_IN_ONE_TICKET",
        }
        if not accepted:
            row["local_optimum_status"] = "CERTIFIED_ONE_NUMBER_EXCHANGE"
            row["proof_status"] = "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_NO_GLOBAL_PROOF"
        measurement_evidence["seed_policy"] = ARM_E
    elif method_id == ITERATIVE:
        assert reference_portfolio is not None
        result = iterative_exact_one_exchange_ascent(
            number_max, draw_size, minimum_matches, reference_portfolio
        )
        portfolio, q, reference_q = result.terminal_portfolio, result.terminal_q, result.seed_q
        row["search_evidence"] = {
            "move_count": result.move_count,
            "neighborhood_unit": "REMOVE_ONE_ADD_ONE_NUMBER_IN_ONE_TICKET",
            "iterations": [
                {
                    "input_q": rational(item.input_q),
                    "best_neighbor_q": rational(item.best_neighbor_q),
                    "delta": rational(item.delta),
                    "accepted_move": item.accepted_move,
                    "unique_legal_neighbor_count": item.unique_legal_neighbor_count,
                    "input_portfolio": item.input_portfolio,
                    "best_neighbor_portfolio": item.best_neighbor_portfolio,
                }
                for item in result.iterations
            ],
        }
        row["local_optimum_status"] = "CERTIFIED_ONE_NUMBER_EXCHANGE"
        row["proof_status"] = "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_NO_GLOBAL_PROOF"
        measurement_evidence["seed_policy"] = ARM_E
    else:
        raise ValueError(f"NATIVE_MEASUREMENT_UNSUPPORTED_METHOD:{method_id}")

    _attach_portfolio(row, rules, portfolio)
    _attach_q(row, rules, q, reference_q, ARM_E)
    row["measurement_evidence"] = measurement_evidence
    return row


def _native_measurement_failure(
    method: JsonObject,
    lottery: str,
    k: int,
    error: Exception,
) -> JsonObject:
    reason = f"EXISTING_NATIVE_EXECUTION_FAILED:{type(error).__name__}:{error}"
    row = _row(
        method,
        f"NATIVE_{lottery}",
        lottery,
        k,
        scope="NATIVE_UNIFORM_WINNING_SPACE",
        status="NOT_RUN",
        reason=reason,
        minimum_matches=NATIVE_MEASUREMENT_MINIMUM_MATCHES,
    )
    row["measurement_evidence"] = {
        "execution_classification": "ATTEMPTED_EXISTING_NATIVE_METHOD",
        "failure_type": type(error).__name__,
        "failure_reason": str(error),
    }
    return row


def measure_native_coverage(root: Path) -> JsonObject:
    """Execute every currently open supported native cell once."""

    matrix = load_matrix(root)
    methods = {method["strategy_id"]: method for method in matrix["methods"]}
    documents = _load_native_documents(root, matrix)
    search_budget = _native_search_budget(documents)
    expected_open = _native_supported_not_run_row_ids(methods)
    rows: list[JsonObject] = []

    for lottery, rules, method_id, method, k in _native_supported_specs(methods):
        if not _is_checkpoint_managed(method_id, lottery, k):
            continue
        clear_cache()
        try:
            row = _measure_native_row(method, lottery, rules, k, search_budget, documents)
        except Exception as error:
            row = _native_measurement_failure(method, lottery, k, error)
        finally:
            clear_cache()
        rows.append(row)

    rows.sort(key=lambda row: row["row_id"])
    actual_ids = [row["row_id"] for row in rows]
    if actual_ids != expected_open:
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: native measurement identity drift")
    measured_count = sum(row["status"] == "MEASURED" for row in rows)
    return {
        "artifact_id": "STRATEGY_MATRIX_NATIVE_EVIDENCE_COVERAGE_R1",
        "schema_version": NATIVE_MEASUREMENT_SCHEMA_VERSION,
        "source_type": "STRATEGY_MATRIX_NATIVE",
        "execution_policy": "OUTCOME_FREE_DETERMINISTIC_EXISTING_IMPLEMENTATION",
        "matrix_authority_base_head": matrix["base_head"],
        "matrix_authority_base_tree": matrix["base_tree"],
        "minimum_matches": NATIVE_MEASUREMENT_MINIMUM_MATCHES,
        "candidate_pool": {
            "kind": NATIVE_CANDIDATE_POOL_KIND,
            "scope": "NATIVE_RULE_SYNTHETIC_CANDIDATE_POOL",
            "selection_mode": "EXISTING_DECLARED_CANDIDATE_POOL",
        },
        "seed_policy": ARM_E,
        "search_budget": search_budget,
        "supported_native_not_run_row_ids": expected_open,
        "starting_supported_native_not_run_count": len(expected_open),
        "rows": rows,
        "new_native_measured_count": measured_count,
        "remaining_native_not_run_count": len(rows) - measured_count,
    }


def repair_native_coverage(root: Path) -> JsonObject:
    """Complete a previously interrupted native measurement artifact."""

    matrix = load_matrix(root)
    methods = {method["strategy_id"]: method for method in matrix["methods"]}
    documents = _load_native_documents(root, matrix)
    search_budget = _native_search_budget(documents)
    expected_open = _native_supported_not_run_row_ids(methods)
    path = root / NATIVE_MEASUREMENT_PATH
    if not path.is_file():
        raise ValueError("NATIVE_MEASUREMENT_CHECKPOINT_MISSING")
    checkpoint = cast(JsonObject, json.loads(path.read_text()))
    if (
        checkpoint.get("artifact_id") != "STRATEGY_MATRIX_NATIVE_EVIDENCE_COVERAGE_R1"
        or checkpoint.get("schema_version") != NATIVE_MEASUREMENT_SCHEMA_VERSION
        or checkpoint.get("matrix_authority_base_head") != matrix["base_head"]
        or checkpoint.get("matrix_authority_base_tree") != matrix["base_tree"]
        or checkpoint.get("supported_native_not_run_row_ids") != expected_open
    ):
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: native checkpoint drift")
    raw_rows = checkpoint.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native checkpoint rows")
    raw_rows = cast(list[object], raw_rows)
    checkpoint_rows: dict[str, JsonObject] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native checkpoint row")
        row = cast(JsonObject, raw_row)
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or row_id in checkpoint_rows:
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native checkpoint row id")
        if row_id not in expected_open or row.get("evidence_scope") != (
            "NATIVE_UNIFORM_WINNING_SPACE"
        ):
            raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: native checkpoint row scope")
        if row.get("status") not in {"MEASURED", "NOT_RUN"}:
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native checkpoint status")
        if row["status"] == "MEASURED":
            if row.get("exact_q") is None or row.get("portfolio") is None:
                raise ValueError(
                    "CANONICAL_METRIC_CONTRACT_CONFLICT: native checkpoint measured row"
                )
            parse_rational(cast(JsonObject, row["exact_q"]))
        checkpoint_rows[row_id] = row
    if set(checkpoint_rows) != set(expected_open):
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: incomplete native checkpoint rows")

    rows: list[JsonObject] = []
    for lottery, rules, method_id, method, k in _native_supported_specs(methods):
        if not _is_checkpoint_managed(method_id, lottery, k):
            continue
        row_id = _native_row_id(lottery, method_id, k)
        checkpoint_row = checkpoint_rows[row_id]
        if checkpoint_row["status"] == "MEASURED":
            rows.append(checkpoint_row)
            continue
        clear_cache()
        try:
            row = _measure_native_row(method, lottery, rules, k, search_budget, documents)
        except Exception as error:
            row = _native_measurement_failure(method, lottery, k, error)
        finally:
            clear_cache()
        rows.append(row)

    rows.sort(key=lambda row: row["row_id"])
    if [row["row_id"] for row in rows] != expected_open:
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: native repair identity drift")
    measured_count = sum(row["status"] == "MEASURED" for row in rows)
    repaired = dict(checkpoint)
    repaired["rows"] = rows
    repaired["starting_supported_native_not_run_count"] = len(expected_open)
    repaired["new_native_measured_count"] = measured_count
    repaired["remaining_native_not_run_count"] = len(rows) - measured_count
    return repaired


def _load_native_measurement_rows(
    root: Path, matrix: JsonObject, methods: Mapping[str, JsonObject]
) -> dict[str, tuple[int, JsonObject]]:
    entries = cast(dict[str, JsonObject], matrix["native_evidence"])
    entry = entries.get(NATIVE_MEASUREMENT_KEY)
    if entry is None:
        return {}
    path = _pinned_file(root, entry)
    artifact = cast(JsonObject, json.loads(path.read_text()))
    if artifact.get("schema_version") != NATIVE_MEASUREMENT_SCHEMA_VERSION:
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native measurement schema")
    expected_open = _native_supported_not_run_row_ids(methods)
    if artifact.get("supported_native_not_run_row_ids") != expected_open:
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: native measurement open cells drifted")
    raw_rows = artifact.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native measurement rows")
    raw_rows = cast(list[object], raw_rows)
    records: dict[str, tuple[int, JsonObject]] = {}
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, dict):
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native measurement row")
        record = cast(JsonObject, raw_row)
        row_id = record.get("row_id")
        if not isinstance(row_id, str) or row_id in records:
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native measurement row id")
        if row_id not in expected_open:
            raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: unexpected native measurement row")
        if record.get("status") not in {"MEASURED", "NOT_RUN"}:
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native measurement status")
        if record.get("evidence_scope") != "NATIVE_UNIFORM_WINNING_SPACE":
            raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native measurement scope")
        if record["status"] == "MEASURED":
            if record.get("exact_q") is None or record.get("portfolio") is None:
                raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: incomplete measured row")
            if (
                cast(JsonObject, record.get("measurement_evidence", {})).get(
                    "execution_classification"
                )
                != "EXECUTED_EXISTING_NATIVE_METHOD"
            ):
                raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: measured execution proof")
            parse_rational(cast(JsonObject, record["exact_q"]))
        records[row_id] = (index, record)
    if set(records) != set(expected_open):
        raise ValueError("MATRIX_AUTHORITY_UNRESOLVED: incomplete native measurement rows")
    return records


def _apply_native_measurement(
    row: JsonObject,
    record: JsonObject,
    entry: JsonObject,
    index: int,
    rules: LotteryRuleContract,
) -> None:
    if record["status"] == "NOT_RUN":
        row["status"] = "NOT_RUN"
        row["status_reason"] = record.get("status_reason") or (
            "EXISTING_NATIVE_EXECUTION_DID_NOT_COMPLETE"
        )
        row["measurement_evidence"] = record.get("measurement_evidence")
        return

    q = parse_rational(cast(JsonObject, record["exact_q"]))
    reference = cast(JsonObject, record["reference"])
    if reference.get("strategy_id") != ARM_E:
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: native reference strategy")
    reference_q = parse_rational(cast(JsonObject, reference["exact_q"]))
    portfolio = _portfolio_from_json(record["portfolio"])
    _attach_portfolio(row, rules, portfolio)
    _attach_q(row, rules, q, reference_q, ARM_E)
    for field in (
        "candidate_pool_kind",
        "candidate_pool_sha256",
        "candidate_count",
        "search_evidence",
        "local_optimum_status",
        "proof_status",
        "measurement_evidence",
    ):
        if field in record:
            row[field] = record[field]
    row["status"] = "MEASURED"
    row["status_reason"] = None
    row["source_evidence"] = {
        **entry,
        "json_pointer": f"/rows/{index}",
    }


def _hard_div_search_evidence(result: HardDivPairwiseBoundedCandidateResult) -> JsonObject:
    """Summarize the adapter's certificate without copying every iteration trace."""

    evidence = cast(HardDivPairwiseSearchEvidence, result.search_evidence)
    return {
        "neighborhood_unit": evidence.neighborhood_unit,
        "neighborhood_radius": 1,
        "hard_pairwise_intersection_cap": PAIRWISE_MAX_INTERSECTION,
        "iteration_count": evidence.iteration_count,
        "move_count": evidence.move_count,
        "complete_neighbor_count_total": evidence.complete_neighbor_count_total,
        "hard_feasible_neighbor_count_total": evidence.hard_feasible_neighbor_count_total,
        "exact_evaluated_neighbor_count_total": evidence.exact_evaluated_neighbor_count_total,
        "terminal_no_strict_improvement": evidence.terminal_no_strict_improvement,
        "complete_neighborhood_certified": evidence.complete_neighborhood_certified,
        "hard_feasible_filter_before_exact_evaluation": (
            evidence.hard_feasible_filter_before_exact_evaluation
        ),
        "seed_policy": SIDON,
        # Hashes inside this native-evidence block are the adapter's own, so they
        # carry the adapter's byte convention rather than the Matrix's.
        "portfolio_hash_canonicalization": NATIVE_PORTFOLIO_HASH_CANONICALIZATION,
        "seed_portfolio_sha256": result.seed_portfolio_sha256,
        "seed_exact_q": rational(cast(Fraction, result.seed_exact_q)),
        "seed_covered_draw_count": result.seed_covered_draw_count,
        "covered_draw_count": result.covered_draw_count,
        "total_draw_count": result.total_draw_count,
    }


def _hard_div_native_row(
    method: JsonObject,
    lottery: str,
    rules: LotteryRuleContract,
    k: int,
) -> JsonObject:
    """Measure one HARD_DIV cell through its canonical adapter.

    The Matrix owns registration, dispatch, normalization and the artifact only.
    The Sidon seed, the radius-1 neighborhood, hard-feasibility filtering and the
    exact coverage evaluation all stay inside the adapter's public API.
    """

    minimum_matches = NATIVE_MEASUREMENT_MINIMUM_MATCHES
    row = _row(
        method,
        f"NATIVE_{lottery}",
        lottery,
        k,
        scope="NATIVE_UNIFORM_WINNING_SPACE",
        minimum_matches=minimum_matches,
    )
    try:
        result = run_hard_div_pairwise_bounded_candidate_adapter(big_lotto_dispatch(k))
    except Exception as error:
        # Fail closed: an execution failure is NOT_RUN, never a fabricated row.
        row.update(
            status="NOT_RUN",
            status_reason=f"HARD_DIV_ADAPTER_EXECUTION_FAILED:{type(error).__name__}",
        )
        return row
    if result.status is not AdapterStatus.MEASURED:
        row.update(
            status=result.status.value,
            status_reason=result.status_reason or "HARD_DIV_ADAPTER_DID_NOT_MEASURE",
        )
        return row
    if (
        result.method_id != HARD_DIV
        or result.reference_strategy_id != SIDON
        or result.lottery != lottery
        or result.k != k
        or result.minimum_matches != minimum_matches
        or result.pool_size != rules.main_number_max
        or result.draw_size != rules.main_number_count
    ):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: hard-div dispatch identity")
    portfolio = result.portfolio
    seed_q = result.seed_exact_q
    q = result.exact_q
    native_sha256 = result.portfolio_sha256
    if (
        portfolio is None
        or seed_q is None
        or q is None
        or native_sha256 is None
        or result.search_evidence is None
        or result.geometry_max_pairwise_overlap is None
    ):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: incomplete hard-div measurement")

    _attach_portfolio(row, rules, portfolio)
    _attach_q(row, rules, q, seed_q, SIDON)
    _attach_native_portfolio_hash(row, native_sha256)

    if (
        row["geometry"]["max_pairwise_overlap"] != result.geometry_max_pairwise_overlap
        or result.geometry_max_pairwise_overlap > PAIRWISE_MAX_INTERSECTION
    ):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: hard-div pairwise overlap cap")
    if result.delta_vs_reference != q - seed_q:
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: hard-div delta vs reference")
    if (
        result.local_optimum_status != "CERTIFIED_ONE_NUMBER_EXCHANGE"
        or result.proof_status != method["proof_status"]
        or result.global_optimum_status != "UNKNOWN"
    ):
        # A radius-1 certificate is never a global optimum claim.
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: hard-div proof boundary")
    row["local_optimum_status"] = result.local_optimum_status
    row["proof_status"] = result.proof_status
    row["search_evidence"] = _hard_div_search_evidence(result)
    row["measurement_evidence"] = {
        "execution_classification": "EXECUTED_EXISTING_NATIVE_METHOD",
        "method_invocation": HARD_DIV,
        "minimum_matches": minimum_matches,
        "dispatch": "CANONICAL_HARD_DIV_PAIRWISE_BOUNDED_CANDIDATE_ADAPTER",
    }
    row["source_evidence"] = {
        **cast(JsonObject, method["source_files"][0]),
        "dispatch": "CANONICAL_ADAPTER_PUBLIC_API",
    }
    return row


_frozen_canonical_rows_cache: dict[str, JsonObject] | None = None


def _get_frozen_canonical_row(root: Path, row_id: str) -> JsonObject | None:
    global _frozen_canonical_rows_cache
    if _frozen_canonical_rows_cache is None:
        result_path = root / RESULT_PATH
        if not result_path.exists():
            return None
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            _frozen_canonical_rows_cache = {
                entry["row_id"]: entry for entry in data.get("rows", []) if "row_id" in entry
            }
        except Exception:
            _frozen_canonical_rows_cache = {}
    return _frozen_canonical_rows_cache.get(row_id)


def _hard_div_radius2_search_evidence(
    k_res: JsonObject,
    artifact: JsonObject,
) -> JsonObject:
    neighborhood = cast(JsonObject, k_res["neighborhood"])
    return {
        "neighborhood_unit": artifact["neighborhood_unit"],
        "neighborhood_radius": 2,
        "hard_pairwise_intersection_cap": artifact["hard_pairwise_max_intersection"],
        "complete_endpoint_count": neighborhood["complete_endpoint_count"],
        "hard_feasible_endpoint_count": neighborhood["hard_feasible_endpoint_count"],
        "exact_evaluated_endpoint_count": neighborhood["exact_evaluated_endpoint_count"],
        "accepted_move": neighborhood["accepted_move"],
        "classification": k_res["classification"],
        "terminal_certificate": k_res["radius2_terminal_certificate"],
        "baseline_method_id": artifact["baseline_method_id"],
        "baseline_portfolio_sha256": k_res["radius1_portfolio_sha256"],
        "baseline_exact_q": k_res["radius1_q"],
        "portfolio_hash_canonicalization": NATIVE_PORTFOLIO_HASH_CANONICALIZATION,
        "total_draw_count": artifact["total_draw_count"],
    }


def _hard_div_radius2_native_row(
    root: Path,
    method: JsonObject,
    lottery: str,
    rules: LotteryRuleContract,
    k: int,
) -> JsonObject:
    """Measure one HARD_DIV radius-2 cell through canonical reconciliation evidence."""

    minimum_matches = NATIVE_MEASUREMENT_MINIMUM_MATCHES
    row = _row(
        method,
        f"NATIVE_{lottery}",
        lottery,
        k,
        scope="NATIVE_UNIFORM_WINNING_SPACE",
        minimum_matches=minimum_matches,
    )
    if lottery != "BIG_LOTTO" or k not in K_SCOPE:
        row.update(status="NOT_APPLICABLE", status_reason="UNSUPPORTED_LOTTERY_OR_K")
        return row

    artifact_path = root / HARD_DIV_RADIUS2_RECONCILIATION_PATH
    if not artifact_path.exists():
        row.update(
            status="NOT_RUN",
            status_reason="CANONICAL_RADIUS2_RECONCILIATION_ARTIFACT_MISSING",
        )
        return row

    artifact_bytes = artifact_path.read_bytes()
    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
    if artifact_sha != HARD_DIV_RADIUS2_RECONCILIATION_SHA256:
        raise ValueError("RADIUS2_EVIDENCE_IDENTITY_MISMATCH: artifact sha256 mismatch")

    artifact = json.loads(artifact_bytes.decode("utf-8"))
    k_res = next((res for res in artifact["k_results"] if res["k"] == k), None)
    if k_res is None:
        raise ValueError(f"CANONICAL_METRIC_CONTRACT_CONFLICT: missing k={k} in radius2 artifact")

    portfolio = tuple(tuple(int(num) for num in ticket) for ticket in k_res["radius2_portfolio"])
    radius2_q = Fraction(k_res["radius2_q"]["numerator"], k_res["radius2_q"]["denominator"])
    radius1_q = Fraction(k_res["radius1_q"]["numerator"], k_res["radius1_q"]["denominator"])
    native_sha256 = k_res["radius2_portfolio_sha256"]

    _attach_portfolio(row, rules, portfolio)
    _attach_q(row, rules, radius2_q, radius1_q, HARD_DIV)
    _attach_native_portfolio_hash(row, native_sha256)

    if (
        row["geometry"]["max_pairwise_overlap"] != k_res["max_pairwise_intersection"]
        or k_res["max_pairwise_intersection"] > PAIRWISE_MAX_INTERSECTION
    ):
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: radius-2 pairwise overlap cap")

    expected_delta = radius2_q - radius1_q
    artifact_delta = Fraction(k_res["delta"]["numerator"], k_res["delta"]["denominator"])
    if expected_delta != artifact_delta:
        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: radius-2 delta arithmetic")

    row["local_optimum_status"] = k_res["radius2_terminal_certificate"]
    row["proof_status"] = method["proof_status"]
    row["global_optimum_status"] = "UNKNOWN"
    row["search_evidence"] = _hard_div_radius2_search_evidence(k_res, artifact)
    row["measurement_evidence"] = {
        "execution_classification": "EXECUTED_EXISTING_NATIVE_METHOD",
        "method_invocation": HARD_DIV_R2,
        "minimum_matches": minimum_matches,
        "dispatch": "CANONICAL_HARD_DIV_EXACT_RADIUS2_RECONCILIATION_ARTIFACT",
        "reconciliation_task_id": artifact["task_id"],
    }
    row["source_evidence"] = {
        "dispatch": "CANONICAL_RADIUS2_RECONCILIATION_RESULT",
        "evidence_class": "EXISTING_NATIVE_EXACT_EVIDENCE",
        "path": HARD_DIV_RADIUS2_RECONCILIATION_PATH.as_posix(),
        "sha256": HARD_DIV_RADIUS2_RECONCILIATION_SHA256,
    }
    return row


def _native_rows(
    root: Path,
    matrix: JsonObject,
    methods: Mapping[str, JsonObject],
    *,
    recompute_direct_dispatch: bool = False,
) -> list[JsonObject]:
    entries = cast(dict[str, JsonObject], matrix["native_evidence"])
    documents = _load_native_documents(root, matrix)
    measured_rows = _load_native_measurement_rows(root, matrix, methods)
    rows: list[JsonObject] = []
    for lottery, rules in RULES.items():
        for method_id, method in methods.items():
            for k in K_SCOPE:
                row = _row(
                    method,
                    f"NATIVE_{lottery}",
                    lottery,
                    k,
                    scope="NATIVE_UNIFORM_WINNING_SPACE",
                    minimum_matches=3,
                )
                if lottery not in method["supported_lottery"] or k not in method["supported_k"]:
                    row.update(status="NOT_APPLICABLE", status_reason="UNSUPPORTED_LOTTERY_OR_K")
                    rows.append(row)
                    continue
                if method_id == HARD_DIV:
                    if not recompute_direct_dispatch and (root / RESULT_PATH).exists():
                        frozen_row = _get_frozen_canonical_row(root, row["row_id"])
                        if frozen_row is not None:
                            rows.append(frozen_row)
                            continue
                    clear_cache()
                    try:
                        rows.append(_hard_div_native_row(method, lottery, rules, k))
                    finally:
                        clear_cache()
                    continue
                if method_id == HARD_DIV_R2:
                    rows.append(_hard_div_radius2_native_row(root, method, lottery, rules, k))
                    continue
                locator = _native_locator(method_id, lottery, k)
                if locator is None:
                    measured = measured_rows.get(row["row_id"])
                    if measured is None:
                        row.update(
                            status="NOT_RUN", status_reason="NO_EXISTING_NATIVE_EXACT_EVIDENCE"
                        )
                    else:
                        index, record = measured
                        _apply_native_measurement(
                            row, record, entries[NATIVE_MEASUREMENT_KEY], index, rules
                        )
                    rows.append(row)
                    continue
                source_key, pointer = locator
                document = documents[source_key]
                q = parse_rational(_pointer(document, pointer))
                reference_id = ARM_B if method_id == ARM_E else ARM_E
                reference_locator = _native_locator(reference_id, lottery, k)
                if reference_locator is None:
                    raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: missing reference")
                reference_source, reference_pointer = reference_locator
                reference_q = parse_rational(
                    _pointer(documents[reference_source], reference_pointer)
                )
                _attach_q(row, rules, q, reference_q, reference_id)
                row["status"] = "REUSED_VERIFIED"
                row["source_evidence"] = {**entries[source_key], "json_pointer": pointer}
                row["reference"]["source_evidence"] = {
                    **entries[reference_source],
                    "json_pointer": reference_pointer,
                }
                if method_id == ITERATIVE:
                    rung: JsonObject = _pointer(document, pointer.rsplit("/", 1)[0])
                    terminal = rung["iterations"][-1]
                    terminal_input = parse_rational(terminal["exact_input_q"])
                    best_neighbor = parse_rational(terminal["exact_best_neighbor_q"])
                    if (
                        rung["terminal_certificate"]["status"] != "PASS"
                        or terminal["accepted_move"]
                        or terminal_input != q
                        or best_neighbor > q
                    ):
                        raise ValueError("CANONICAL_METRIC_CONTRACT_CONFLICT: terminal certificate")
                    _attach_portfolio(
                        row, rules, tuple(tuple(ticket) for ticket in rung["terminal_portfolio"])
                    )
                    row["local_optimum_status"] = "CERTIFIED_ONE_NUMBER_EXCHANGE"
                    row["proof_status"] = "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_NO_GLOBAL_PROOF"
                    row["search_evidence"] = {
                        "move_count": rung["move_count"],
                        "terminal_neighbor_count": terminal["unique_legal_neighbor_count"],
                        "terminal_best_neighbor_q": rational(best_neighbor),
                        "terminal_input_q": rational(terminal_input),
                        "trace_source_pointer": pointer.rsplit("/", 1)[0] + "/iterations",
                        "seed_policy": "PHASE9_BEST_NEIGHBOR"
                        if lottery == "BIG_LOTTO"
                        else "METHOD_E",
                    }
                elif method_id == ONE_EXCHANGE:
                    rung = document["per_k"][str(k)]
                    _attach_portfolio(
                        row,
                        rules,
                        tuple(tuple(ticket) for ticket in rung["best_neighbor_portfolio"]),
                    )
                    row["search_evidence"] = {
                        "unique_legal_neighbor_count": rung["unique_neighbor_count"],
                        "best_neighbor_delta": rung["delta_vs_reference_e"],
                        "seed_policy": "METHOD_E",
                    }
                    if parse_rational(rung["delta_vs_reference_e"]) <= 0:
                        row["local_optimum_status"] = "CERTIFIED_ONE_NUMBER_EXCHANGE"
                        row["proof_status"] = (
                            "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_NO_GLOBAL_PROOF"
                        )
                elif method_id == BOUNDED:
                    row["local_optimum_status"] = "NOT_CERTIFIED_SAMPLED_NEIGHBORHOOD"
                    optimizer = document["optimizer"]
                    row["search_evidence"] = {
                        "budget": {key: optimizer[key] for key in TOY_SEARCH_BUDGET},
                        **optimizer["search_by_k"][str(k)],
                    }
                rows.append(row)
    return rows


def _gap(
    category: str,
    gap_id: str,
    existing: str,
    missing: str,
    why: str,
    branch: int | None,
    evidence: list[str],
) -> JsonObject:
    return {
        "category": category,
        "gap_id": gap_id,
        "existing_capability": existing,
        "missing_capability": missing,
        "why_not_duplicate": why,
        "handoff_branch": branch,
        "evidence_row_ids": evidence,
    }


def detect_gaps(rows: list[JsonObject], methods: Mapping[str, JsonObject]) -> list[JsonObject]:
    local = [
        row["row_id"]
        for row in rows
        if row["local_optimum_status"] == "CERTIFIED_ONE_NUMBER_EXCHANGE"
    ]
    unavailable = [row["row_id"] for row in rows if row["status"] == "NOT_RUN"]
    low_k = [key for key, method in methods.items() if not {2, 3} <= set(method["supported_k"])]
    return [
        _gap(
            "METHOD_GAPS",
            "GLOBAL_EXACT_SOLVER",
            "Exact evaluation and bounded best-of-restarts search.",
            "A portfolio-wide exact solver/certificate below Q=1.",
            "Exact objective values and local certificates do not enumerate all portfolios.",
            3,
            local,
        ),
        _gap(
            "FEATURE_GAPS",
            "K_GAP_NATIVE_CANDIDATE_CONSTRUCTORS",
            "Frozen candidate-set constructors support 5/10/20: " + ", ".join(low_k),
            "Native 2/3 allocation with its own correctness evidence.",
            "Current guards reject low k; truncating a 5-ticket result changes the contract.",
            3,
            [row["row_id"] for row in rows if row["strategy_id"] in low_k and row["k"] in (2, 3)],
        ),
        _gap(
            "FEATURE_GAPS",
            "NATIVE_EXACT_EVIDENCE_COVERAGE",
            "All requested k have fresh synthetic comparisons; selected native rungs "
            "have sealed exact Q.",
            "Native Q for supported but unmeasured method/k cells and candidate-pool "
            "geometry cases.",
            "A synthetic rule/candidate measurement is not native uniform winning-space evidence.",
            None,
            unavailable,
        ),
        _gap(
            "SEARCH_GAPS",
            "TWO_EXCHANGE_AND_RADIUS_N",
            (
                "Complete radius-1 scans and exact radius-2 two-exchange local escape "
                "for B649 (k=2, 3, 5, 10, 20)."
            ),
            "Arbitrary radius-N neighborhoods beyond radius 2 and cross-structure expansion.",
            (
                "Exact radius-2 escape is implemented for B649, but radius-N beyond 2 "
                "remains an open search gap."
            ),
            3,
            local,
        ),
        _gap(
            "OBJECTIVE_GAPS",
            "COVERAGE_WITH_HARD_DIVERSIFICATION",
            "Sidon enforces pairwise overlap <=1; coverage optimizers only require "
            "distinct tickets.",
            "Coverage optimization subject to an explicit hard overlap/exposure constraint.",
            "Greedy overlap preferences and descriptive geometry do not constrain "
            "the coverage search feasible set.",
            3,
            [
                row["row_id"]
                for row in rows
                if row["strategy_id"] == BOUNDED and row["status"] == "MEASURED"
            ],
        ),
        _gap(
            "OBJECTIVE_GAPS",
            "EXPECTED_HIT_UTILITY_CONTRACT",
            "Uniform at-least-one-ticket coverage and frozen lexicographic geometry objectives.",
            "A formally defined expected-hit utility objective and verified optimizer for it.",
            "Coverage is a union probability; it is not a utility or payout expectation. "
            "Define the contract before implementation.",
            None,
            [],
        ),
    ]


def build_comparison(root: Path, *, recompute_direct_dispatch: bool = False) -> JsonObject:
    matrix = load_matrix(root)
    methods = {method["strategy_id"]: method for method in matrix["methods"]}
    rows = [
        *_toy_rows(methods),
        *_candidate_rows(methods),
        *_native_rows(root, matrix, methods, recompute_direct_dispatch=recompute_direct_dispatch),
    ]
    rows.sort(key=lambda row: row["row_id"])
    if len({row["row_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate canonical comparison row")
    improvements = [
        {
            "row_id": row["row_id"],
            "reference": row["reference"]["strategy_id"],
            "delta": row["delta_vs_reference"],
            "evidence_scope": row["evidence_scope"],
        }
        for row in rows
        if row["delta_vs_reference"] is not None and parse_rational(row["delta_vs_reference"]) > 0
    ]
    gaps = detect_gaps(rows, methods)
    method_families = sorted({method["strategy_family"] for method in methods.values()})
    return {
        "task_id": "STRATEGY_MATRIX_IMPORTED_OPTIMIZER_INTEGRATION_AND_GAP_R1",
        "schema_version": matrix["schema_version"],
        "base_head": matrix["base_head"],
        "base_tree": matrix["base_tree"],
        "matrix_intake_sha256": hashlib.sha256(canonical_json_bytes(matrix)).hexdigest(),
        "imported_method_count": len(methods),
        "distinct_family_count": len(method_families),
        "method_families": method_families,
        "supported_k": K_SCOPE,
        "methods": list(methods.values()),
        "rows": rows,
        "status_counts": {
            status: sum(row["status"] == status for row in rows)
            for status in ("MEASURED", "REUSED_VERIFIED", "NOT_APPLICABLE", "NOT_RUN")
        },
        "strict_improvements": improvements,
        "new_deterministic_comparison_row_ids": [
            row["row_id"] for row in rows if row["status"] == "MEASURED"
        ],
        "reused_native_evidence_row_ids": [
            row["row_id"] for row in rows if row["status"] == "REUSED_VERIFIED"
        ],
        "exact_optimum_row_ids": [
            row["row_id"]
            for row in rows
            if row["global_optimum_status"] == "CERTIFIED_BY_UNIT_UPPER_BOUND"
        ],
        "gaps": gaps,
        "gap_counts": {
            category: sum(gap["category"] == category for gap in gaps)
            for category in ("METHOD_GAPS", "FEATURE_GAPS", "SEARCH_GAPS", "OBJECTIVE_GAPS")
        },
        "family_expansion_candidates": [
            {
                "strategy_family": family,
                "basis": "CONTROLLED_ALGORITHM_COMPARISON_ONLY",
                "evidence_row_ids": [
                    row["row_id"]
                    for row in rows
                    if row["strategy_family"] == family
                    and row["delta_vs_reference"] is not None
                    and parse_rational(row["delta_vs_reference"]) > 0
                ],
            }
            for family in ("EXACT_ONE_NUMBER_EXCHANGE", "BOUNDED_COVERAGE_SEARCH")
        ],
        "handoffs": {
            "branch_2": [],
            "branch_3": [gap["gap_id"] for gap in gaps if gap["handoff_branch"] == 3],
            "branch_4": [],
            "branch_5": [],
            "branch_6": {
                "canonical_metrics": RESULT_PATH.as_posix(),
                "recompute_authority": False,
                "comparison_keys": [
                    "case_id",
                    "lottery",
                    "zone",
                    "k",
                    "minimum_matches",
                    "evidence_scope",
                    "candidate_pool_sha256",
                ],
                "restriction": "Consume these metrics; no synthetic/native or geometry/Q pooling.",
            },
            "branch_7": {
                "schema": "docs/research/cross-lottery-research-ledger-r1-schema.md",
                "status_semantics": matrix["status_semantics"],
                "ui_implemented": False,
            },
        },
        "claim_boundary": {
            "predictive_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
            "db_access": "NO",
            "db_write": "NO",
            "future_outcome_access": "NO",
            "production_runtime_mutation": "NONE",
            "leaderboard": "NOT_PRODUCED",
            "global_optimum_without_proof": "NEVER_CLAIMED",
        },
    }
