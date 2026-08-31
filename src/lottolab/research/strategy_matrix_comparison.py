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
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_sum_then_reuse_dispersion_constructor import (
    greedy_minmax_sum_then_reuse_dispersion_portfolio,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
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
SIDON = "CYCLIC_SIDON_SHIFT_V1"
ARM_B = "GREEDY_MIN_OVERLAP_V1"
ARM_E = "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
ARM_F = "GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1"
CANDIDATE = "CANDIDATE_LOW_OVERLAP_V1"
BOUNDED = "RESTART_GREEDY_SWAP_COVERAGE_SEARCH_V1"
ONE_EXCHANGE = "REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1"
ITERATIVE = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
METHOD_IDS = (
    SIDON,
    ARM_B,
    ARM_E,
    ARM_F,
    CANDIDATE,
    BOUNDED,
    ONE_EXCHANGE,
    ITERATIVE,
    *CONSTRUCTORS,
)
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
    if len(methods) != 11 or len({method["strategy_family"] for method in methods}) != 6:
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


def _native_rows(
    root: Path, matrix: JsonObject, methods: Mapping[str, JsonObject]
) -> list[JsonObject]:
    entries: JsonObject = matrix["native_evidence"]
    documents = {
        key: json.loads((root / entry["path"]).read_text()) for key, entry in entries.items()
    }
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
                locator = _native_locator(method_id, lottery, k)
                if locator is None:
                    row.update(status="NOT_RUN", status_reason="NO_EXISTING_NATIVE_EXACT_EVIDENCE")
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
            "Complete radius-1 number-exchange scans and ascent.",
            "2-exchange and explicitly defined radius-N neighborhoods.",
            "Iterating radius 1 cannot certify or escape every radius-2 plateau; "
            "whole-ticket sampled swaps use a different unit.",
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


def build_comparison(root: Path) -> JsonObject:
    matrix = load_matrix(root)
    methods = {method["strategy_id"]: method for method in matrix["methods"]}
    rows = [*_toy_rows(methods), *_candidate_rows(methods), *_native_rows(root, matrix, methods)]
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
