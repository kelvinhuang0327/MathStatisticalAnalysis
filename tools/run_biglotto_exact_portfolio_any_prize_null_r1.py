"""Validate and seal exact Big Lotto portfolio ANY_PRIZE null support evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from dataclasses import dataclass
from itertools import combinations
from math import comb
from pathlib import Path
from time import perf_counter
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import LOTTERY_PRIZE_EVALUATOR
from lottolab.research.biglotto_exact_portfolio_any_prize_null_r1 import (
    TOTAL_OUTCOME_COUNT,
    TOTAL_SEVEN_SET_COUNT,
    ExactPortfolioAnyPrizeProbability,
    exact_portfolio_any_prize_probability,
    exact_seven_set_ticket_triple_union_count,
)

TASK_ID = "BIGLOTTO_EXACT_PORTFOLIO_ANY_PRIZE_NULL_EXECUTION_SUPPORT_R1"
BASE_HEAD = "e8e8bd9caa5157b6190c912fa878d79f467dc98d"
BASE_TREE = "27820999434871d852bf22af8dbeb7c66de71f88"
EXPECTED_CANDIDATE_IDS = (
    "BMSGV1_BCU_4e7d61f26f300458",
    "BMSGV1_BCU_6d1c587273d742e3",
    "BMSGV1_BCU_7f162cc77d7e46e5",
    "BMSGV1_BCU_5d32cca92cf6c7ea",
    "BMSGV1_BCU_052424120e14ec66",
    "BMSGV1_BCU_d45edd29a192b37d",
    "BMSGV1_BCU_636542e0273b2706",
    "BMSGV1_BCU_e57e85d0095f138e",
    "BMSGV1_BCU_44934fb9b3c30499",
)
JSON_OUTPUT_NAMES = (
    "support_authority.json",
    "algorithm_contract.json",
    "canonical_evaluator_equivalence.json",
    "exactness_oracle_validation.json",
    "performance_manifest.json",
    "source_contract.json",
    "next_stage_handoff.json",
    "run_manifest.json",
)
ALL_OUTPUT_NAMES = (
    *JSON_OUTPUT_NAMES,
    "r2_candidate_compatibility.csv",
    "SHA256SUMS",
)


@dataclass(frozen=True, slots=True)
class CandidatePortfolio:
    candidate_id: str
    constructor: str
    matched_k: int
    tickets: tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class TimedCandidateResult:
    candidate: CandidatePortfolio
    result: ExactPortfolioAnyPrizeProbability
    runtime_seconds: float


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: Path) -> dict[str, object]:
    parsed = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain a JSON object with string keys")
    object_mapping = cast(dict[object, object], parsed)
    if any(type(key) is not str for key in object_mapping):
        raise ValueError(f"{path} must contain a JSON object with string keys")
    return {cast(str, key): value for key, value in object_mapping.items()}


def _object_map(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    object_mapping = cast(dict[object, object], value)
    if any(type(key) is not str for key in object_mapping):
        raise ValueError(f"{label} must have string keys")
    return {cast(str, key): item for key, item in object_mapping.items()}


def _required_text(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if type(value) is not str or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} must be an exact integer")
    return value


def _verify_sha256sums(root: Path) -> dict[str, str]:
    manifest = root / "SHA256SUMS"
    if not manifest.is_file():
        raise ValueError(f"missing checksum manifest: {manifest}")
    verified: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, filename = line.partition("  ")
        if separator != "  " or len(digest) != 64 or not filename:
            raise ValueError(f"invalid SHA256SUMS line under {root}: {line!r}")
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe checksum path under {root}: {filename}")
        actual = _sha256(root / relative)
        if actual != digest:
            raise ValueError(f"checksum mismatch under {root}: {filename}")
        verified[filename] = digest
    if not verified:
        raise ValueError(f"empty checksum manifest: {manifest}")
    return verified


def _load_candidates(candidate_root: Path) -> tuple[CandidatePortfolio, ...]:
    batch = _load_json_object(candidate_root / "candidate_batch.json")
    raw_candidates = batch.get("CANDIDATES")
    if not isinstance(raw_candidates, list):
        raise ValueError("candidate_batch.CANDIDATES must be a list")

    candidates: list[CandidatePortfolio] = []
    for index, raw_candidate in enumerate(cast(list[object], raw_candidates)):
        candidate = _object_map(raw_candidate, f"CANDIDATES[{index}]")
        raw_tickets = candidate.get("FINAL_TICKETS")
        if not isinstance(raw_tickets, list):
            raise ValueError(f"CANDIDATES[{index}].FINAL_TICKETS must be a list")
        tickets: list[tuple[int, ...]] = []
        for ticket_index, raw_ticket in enumerate(cast(list[object], raw_tickets)):
            if not isinstance(raw_ticket, list):
                raise ValueError(
                    f"CANDIDATES[{index}].FINAL_TICKETS[{ticket_index}] is invalid"
                )
            ticket_values = cast(list[object], raw_ticket)
            if any(type(number) is not int for number in ticket_values):
                raise ValueError(
                    f"CANDIDATES[{index}].FINAL_TICKETS[{ticket_index}] is invalid"
                )
            tickets.append(tuple(cast(int, number) for number in ticket_values))
        parsed = CandidatePortfolio(
            candidate_id=_required_text(candidate, "CANDIDATE_ID"),
            constructor=_required_text(candidate, "CONSTRUCTOR"),
            matched_k=_required_int(candidate, "MATCHED_K"),
            tickets=tuple(tickets),
        )
        declared_cardinality = _required_int(candidate, "FINAL_CARDINALITY")
        if declared_cardinality != len(parsed.tickets):
            raise ValueError(f"candidate cardinality mismatch: {parsed.candidate_id}")
        candidates.append(parsed)

    actual_ids = tuple(candidate.candidate_id for candidate in candidates)
    if actual_ids != EXPECTED_CANDIDATE_IDS:
        raise ValueError("candidate identities/order do not match the frozen authority")
    if tuple(len(candidate.tickets) for candidate in candidates) != (
        10,
        20,
        40,
        10,
        20,
        40,
        10,
        20,
        40,
    ):
        raise ValueError("candidate portfolio shapes do not match the frozen authority")
    return tuple(candidates)


def _git(repository_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), *arguments),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _canonical_signature_equivalence() -> list[dict[str, object]]:
    ticket = (1, 2, 3, 4, 5, 6)
    outside = tuple(range(7, 50))
    rows: list[dict[str, object]] = []
    for main_hits in range(7):
        for special_hit in (False, True):
            if main_hits + int(special_hit) > 6:
                continue
            winning_main = tuple(sorted((*ticket[:main_hits], *outside[: 6 - main_hits])))
            winning_special = ticket[main_hits] if special_hit else outside[6 - main_hits]
            evaluated = LOTTERY_PRIZE_EVALUATOR.evaluate(
                lottery_type=LotteryType.BIG_LOTTO,
                predicted_main_numbers=ticket,
                predicted_special_number=None,
                winning_main_numbers=winning_main,
                winning_special_number=winning_special,
            )
            threshold_winner = main_hits + int(special_hit) >= 3
            if evaluated.is_winner is not threshold_winner:
                raise ArithmeticError("canonical evaluator is not seven-set threshold equivalent")
            rows.append(
                {
                    "CANONICAL_IS_WINNER": evaluated.is_winner,
                    "MAIN_HITS": main_hits,
                    "PRIZE_TIER": evaluated.prize_tier,
                    "SEVEN_SET_INTERSECTION": main_hits + int(special_hit),
                    "SPECIAL_HIT": special_hit,
                    "THRESHOLD_IS_WINNER": threshold_winner,
                }
            )
    if len(rows) != 13:
        raise ArithmeticError("expected all 13 admissible hit signatures")
    return rows


def _single_ticket_original_outcome_oracle() -> int:
    favorable = 0
    for main_hits in range(7):
        main_count = comb(6, main_hits) * comb(43, 6 - main_hits)
        for special_hit in (False, True):
            if not 3 <= main_hits + int(special_hit) <= 6:
                continue
            special_count = (6 - main_hits) if special_hit else (37 + main_hits)
            favorable += main_count * special_count
    return favorable


def _pair_portfolio(overlap: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    first = (1, 2, 3, 4, 5, 6)
    second = tuple((*first[:overlap], *range(7, 13 - overlap)))
    return first, second


def _pair_seven_set_oracle(overlap: int) -> int:
    ticket_only = 6 - overlap
    outside_both = 37 + overlap
    single = sum(comb(6, hits) * comb(43, 7 - hits) for hits in range(3, 7))
    both = 0
    for common in range(overlap + 1):
        for first_only in range(ticket_only + 1):
            for second_only in range(ticket_only + 1):
                outside = 7 - common - first_only - second_only
                if not 0 <= outside <= outside_both:
                    continue
                if common + first_only < 3 or common + second_only < 3:
                    continue
                both += (
                    comb(overlap, common)
                    * comb(ticket_only, first_only)
                    * comb(ticket_only, second_only)
                    * comb(outside_both, outside)
                )
    return 2 * single - both


def _reduced_domain_validation() -> list[dict[str, object]]:
    cases = (
        (12, ((1, 2, 3, 4, 5, 6),)),
        (13, ((1, 2, 3, 4, 5, 6), (1, 2, 7, 8, 9, 10))),
        (
            14,
            (
                (1, 2, 3, 4, 5, 6),
                (1, 2, 3, 7, 8, 9),
                (1, 2, 3, 10, 11, 12),
            ),
        ),
    )
    rows: list[dict[str, object]] = []
    for pool_size, portfolio in cases:
        exhaustive = sum(
            any(len(set(seven_set) & set(ticket)) >= 3 for ticket in portfolio)
            for seven_set in combinations(range(1, pool_size + 1), 7)
        )
        production = exact_seven_set_ticket_triple_union_count(pool_size, portfolio)
        if production != exhaustive:
            raise ArithmeticError("reduced-domain exhaustive oracle mismatch")
        rows.append(
            {
                "EXHAUSTIVE_FAVORABLE_SEVEN_SET_COUNT": exhaustive,
                "POOL_SIZE": pool_size,
                "PRODUCTION_FAVORABLE_SEVEN_SET_COUNT": production,
                "STATUS": "PASS",
                "TICKET_COUNT": len(portfolio),
                "TOTAL_SEVEN_SET_COUNT": comb(pool_size, 7),
            }
        )
    return rows


def _timed_candidate(
    candidate: CandidatePortfolio,
    *,
    reverse_order: bool,
) -> TimedCandidateResult:
    portfolio = tuple(reversed(candidate.tickets)) if reverse_order else candidate.tickets
    started = perf_counter()
    result = exact_portfolio_any_prize_probability(portfolio)
    elapsed = perf_counter() - started
    if result.unique_ticket_count != len(candidate.tickets):
        raise ValueError(f"unexpected duplicate candidate tickets: {candidate.candidate_id}")
    return TimedCandidateResult(candidate, result, elapsed)


def _result_record(result: ExactPortfolioAnyPrizeProbability) -> dict[str, object]:
    return {
        "EXACT_PROBABILITY": (
            f"{result.exact_probability.numerator}/{result.exact_probability.denominator}"
        ),
        "FAVORABLE_OUTCOME_COUNT": result.favorable_outcome_count,
        "FAVORABLE_SEVEN_SET_COUNT": result.favorable_seven_set_count,
        "REDUCED_DENOMINATOR": result.exact_probability.denominator,
        "REDUCED_NUMERATOR": result.exact_probability.numerator,
        "TOTAL_OUTCOME_COUNT": result.total_outcome_count,
    }


def _json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_outputs(
    output_root: Path,
    payloads: dict[str, dict[str, object]],
    csv_text: str,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for name in JSON_OUTPUT_NAMES:
        (output_root / name).write_text(_json_text(payloads[name]), encoding="utf-8")
    (output_root / "r2_candidate_compatibility.csv").write_text(csv_text, encoding="utf-8")
    checksum_names = sorted((*JSON_OUTPUT_NAMES, "r2_candidate_compatibility.csv"))
    checksum_text = "".join(
        f"{_sha256(output_root / name)}  {name}\n" for name in checksum_names
    )
    (output_root / "SHA256SUMS").write_text(checksum_text, encoding="utf-8")
    if set(path.name for path in output_root.iterdir() if path.is_file()) != set(
        ALL_OUTPUT_NAMES
    ):
        raise ValueError("output root contains an unexpected file set")
    _verify_sha256sums(output_root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--forward-protocol-root", type=Path, required=True)
    parser.add_argument("--candidate-authority-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--external-verification-status",
        choices=("PENDING", "PASS"),
        default="PENDING",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    repository_root = cast(Path, args.repository_root).resolve()
    forward_root = cast(Path, args.forward_protocol_root).resolve()
    candidate_root = cast(Path, args.candidate_authority_root).resolve()
    output_root = cast(Path, args.output_root).resolve()
    external_verification = cast(str, args.external_verification_status)
    started = perf_counter()

    forward_checksums = _verify_sha256sums(forward_root)
    candidate_checksums = _verify_sha256sums(candidate_root)
    exact_contract = _load_json_object(forward_root / "exact_portfolio_null_contract.json")
    outcome_space = _object_map(
        exact_contract.get("official_outcome_space"),
        "official_outcome_space",
    )
    if _required_int(outcome_space, "outcome_count") != TOTAL_OUTCOME_COUNT:
        raise ValueError("frozen outcome space does not match the engine")
    evaluator_binding = _object_map(
        exact_contract.get("canonical_evaluator_binding"),
        "canonical_evaluator_binding",
    )

    source_path = (
        repository_root
        / "src/lottolab/research/biglotto_exact_portfolio_any_prize_null_r1.py"
    )
    test_path = (
        repository_root / "tests/unit/test_biglotto_exact_portfolio_any_prize_null_r1.py"
    )
    tool_path = repository_root / "tools/run_biglotto_exact_portfolio_any_prize_null_r1.py"
    rules_path = repository_root / "src/lottolab/domain/lottery_rules.py"
    evaluator_path = repository_root / "src/lottolab/domain/prize_evaluation.py"
    if _sha256(rules_path) != _required_text(evaluator_binding, "lottery_rule_sha256"):
        raise ValueError("canonical lottery-rule source hash drift")
    if _sha256(evaluator_path) != _required_text(
        evaluator_binding, "prize_evaluator_sha256"
    ):
        raise ValueError("canonical prize-evaluator source hash drift")

    signature_rows = _canonical_signature_equivalence()
    single_oracle = _single_ticket_original_outcome_oracle()
    single_actual = exact_portfolio_any_prize_probability(((1, 2, 3, 4, 5, 6),))
    if single_actual.favorable_outcome_count != single_oracle:
        raise ArithmeticError("single-ticket original-outcome oracle mismatch")

    pair_rows: list[dict[str, object]] = []
    pair_results: dict[int, ExactPortfolioAnyPrizeProbability] = {}
    for overlap in (0, 2, 5):
        pair_result = exact_portfolio_any_prize_probability(_pair_portfolio(overlap))
        pair_oracle = _pair_seven_set_oracle(overlap)
        if pair_result.favorable_seven_set_count != pair_oracle:
            raise ArithmeticError(f"pair overlap-{overlap} oracle mismatch")
        pair_results[overlap] = pair_result
        pair_rows.append(
            {
                "OVERLAP": overlap,
                "ORACLE_FAVORABLE_SEVEN_SET_COUNT": pair_oracle,
                "PRODUCTION": _result_record(pair_result),
                "STATUS": "PASS",
            }
        )

    duplicate = exact_portfolio_any_prize_probability(
        ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6))
    )
    reversed_pair = exact_portfolio_any_prize_probability(
        tuple(reversed(_pair_portfolio(2)))
    )
    duplicate_pass = duplicate.exact_probability == single_actual.exact_probability
    order_pass = reversed_pair.exact_probability == pair_results[2].exact_probability
    if not duplicate_pass or not order_pass:
        raise ArithmeticError("portfolio canonicalization invariant failed")
    reduced_rows = _reduced_domain_validation()

    candidates = _load_candidates(candidate_root)
    first_pass = tuple(
        _timed_candidate(candidate, reverse_order=False) for candidate in candidates
    )
    second_pass = tuple(
        _timed_candidate(candidate, reverse_order=True) for candidate in candidates
    )
    for first, second in zip(first_pass, second_pass, strict=True):
        if first.result != second.result:
            raise ArithmeticError(
                f"candidate determinism/order failure: {first.candidate.candidate_id}"
            )

    csv_buffer = io.StringIO()
    fieldnames: list[str] = [
        "CANDIDATE_ID",
        "CONSTRUCTOR",
        "MATCHED_K",
        "INPUT_TICKET_COUNT",
        "UNIQUE_TICKET_COUNT",
        "FAVORABLE_OUTCOME_COUNT",
        "TOTAL_OUTCOME_COUNT",
        "REDUCED_NUMERATOR",
        "REDUCED_DENOMINATOR",
        "PASS1_RUNTIME_SECONDS",
        "PASS2_REVERSED_RUNTIME_SECONDS",
        "DETERMINISTIC",
        "STATUS",
    ]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    compatibility_rows: list[dict[str, object]] = []
    for first, second in zip(first_pass, second_pass, strict=True):
        result = first.result
        row: dict[str, object] = {
            "CANDIDATE_ID": first.candidate.candidate_id,
            "CONSTRUCTOR": first.candidate.constructor,
            "MATCHED_K": first.candidate.matched_k,
            "INPUT_TICKET_COUNT": result.input_ticket_count,
            "UNIQUE_TICKET_COUNT": result.unique_ticket_count,
            "FAVORABLE_OUTCOME_COUNT": result.favorable_outcome_count,
            "TOTAL_OUTCOME_COUNT": result.total_outcome_count,
            "REDUCED_NUMERATOR": result.exact_probability.numerator,
            "REDUCED_DENOMINATOR": result.exact_probability.denominator,
            "PASS1_RUNTIME_SECONDS": f"{first.runtime_seconds:.9f}",
            "PASS2_REVERSED_RUNTIME_SECONDS": f"{second.runtime_seconds:.9f}",
            "DETERMINISTIC": "YES",
            "STATUS": "PASS",
        }
        writer.writerow(row)
        compatibility_rows.append(row)

    head = _git(repository_root, "rev-parse", "HEAD")
    tree = _git(repository_root, "show", "-s", "--format=%T", "HEAD")
    branch = _git(repository_root, "branch", "--show-current")
    status = _git(repository_root, "status", "--short")
    source_state = "CLEAN_COMMITTED" if not status else "EXPECTED_PRECOMMIT_DIRTY"

    representative: list[dict[str, object]] = []
    for ticket_count in (10, 20, 40):
        matching = [
            run.runtime_seconds
            for run in first_pass
            if len(run.candidate.tickets) == ticket_count
        ]
        representative.append(
            {
                "CALCULATION_COUNT": len(matching),
                "MAX_RUNTIME_SECONDS": max(matching),
                "MEAN_RUNTIME_SECONDS": sum(matching) / len(matching),
                "MIN_RUNTIME_SECONDS": min(matching),
                "TICKET_COUNT": ticket_count,
            }
        )
    first_total = sum(run.runtime_seconds for run in first_pass)
    second_total = sum(run.runtime_seconds for run in second_pass)

    support_authority: dict[str, object] = {
        "ALLOWED_WRITES": [str(repository_root), str(output_root)],
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BRANCH": branch,
        "CANDIDATE_AUTHORITY_ROOT": str(candidate_root),
        "CANDIDATE_SHA256_VERIFICATION": f"PASS_{len(candidate_checksums)}_FILES",
        "FORBIDDEN_MUTATIONS": ["R2_CANDIDATE_SEMANTICS", "R2_FORWARD_PROTOCOL", "DB", "GOAL_C"],
        "FORWARD_PROTOCOL_ROOT": str(forward_root),
        "FORWARD_SHA256_VERIFICATION": f"PASS_{len(forward_checksums)}_FILES",
        "OWNER_AUTHORIZATION_STATUS": "PRESENT",
        "SCHEMA_VERSION": "BIGLOTTO_EXACT_PORTFOLIO_NULL_SUPPORT_AUTHORITY_V1",
        "TASK_CLASS": "STATE_CHANGING_IMPLEMENTATION",
        "TASK_ID": TASK_ID,
        "WORKER_ROUTE": "STANDARD_JUDGED",
        "WORKTREE": str(repository_root),
    }
    algorithm_contract: dict[str, object] = {
        "CANONICAL_EVENT_EQUIVALENCE": (
            "ticket wins iff its intersection with the unordered seven-number "
            "main-plus-special set has cardinality at least 3"
        ),
        "COUNTING_METHOD": (
            "count seven-sets containing no ticket triple via pair-completion masks "
            "and exact five-prefix/final-pair enumeration; subtract from C(49,7); "
            "multiply by seven special designations"
        ),
        "CURRENT_DATE_DEPENDENCY": "NONE",
        "EMPIRICAL_FREQUENCY_APPROXIMATION": "NONE",
        "EXACT": "YES",
        "EXACT_DUPLICATE_IDEMPOTENCE": "YES",
        "INDEPENDENT_TICKET_APPROXIMATION": "NONE",
        "MONTE_CARLO": "NONE",
        "OFFICIAL_OUTCOME_SPACE": TOTAL_OUTCOME_COUNT,
        "PORTFOLIO_ORDER_INVARIANCE": "YES",
        "RNG": "NONE",
        "SCHEMA_VERSION": "BIGLOTTO_EXACT_PORTFOLIO_NULL_ALGORITHM_CONTRACT_V1",
        "SPECIAL_DESIGNATIONS_PER_SEVEN_SET": 7,
        "TARGET_OUTCOME_DEPENDENCY": "NONE",
        "TOTAL_SEVEN_SET_COUNT": TOTAL_SEVEN_SET_COUNT,
    }
    canonical_equivalence: dict[str, object] = {
        "ENTRYPOINT": "lottolab.domain.prize_evaluation.LOTTERY_PRIZE_EVALUATOR.evaluate",
        "EVALUATED_SIGNATURE_COUNT": len(signature_rows),
        "LOTTERY_RULE_SHA256": _sha256(rules_path),
        "PRIZE_EVALUATOR_SHA256": _sha256(evaluator_path),
        "SCHEMA_VERSION": "BIGLOTTO_CANONICAL_EVALUATOR_EQUIVALENCE_V1",
        "SIGNATURES": signature_rows,
        "STATUS": "PASS",
    }
    oracle_validation: dict[str, object] = {
        "DUPLICATE_IDEMPOTENCE": "PASS" if duplicate_pass else "FAIL",
        "INDEPENDENT_REDUCED_DOMAIN_EXHAUSTIVE_ORACLE": reduced_rows,
        "PAIR_OVERLAP_ORACLE": pair_rows,
        "PORTFOLIO_ORDER_INVARIANCE": "PASS" if order_pass else "FAIL",
        "SCHEMA_VERSION": "BIGLOTTO_EXACTNESS_ORACLE_VALIDATION_V1",
        "SINGLE_TICKET_ORACLE": {
            "ORACLE_CONSTRUCTION": "direct original (6-main-set, designated-special) category sum",
            "ORACLE_FAVORABLE_OUTCOME_COUNT": single_oracle,
            "PRODUCTION": _result_record(single_actual),
            "STATUS": "PASS",
        },
        "STATUS": "PASS",
    }
    performance_manifest: dict[str, object] = {
        "ALL_NINE_FIRST_PASS_RUNTIME_SECONDS": first_total,
        "ALL_NINE_REVERSED_PASS_RUNTIME_SECONDS": second_total,
        "ASSESSMENT_BASIS": (
            "all nine frozen 10/20/40-ticket portfolios completed exactly twice "
            "in a bounded local run; no arbitrary threshold was imposed"
        ),
        "CANDIDATE_CALCULATIONS": compatibility_rows,
        "MONTE_CARLO": "NONE",
        "OPERATIONAL_PRE_DRAW_EXECUTION": "PASS",
        "REPRESENTATIVE_PORTFOLIO_SIZES": representative,
        "SCHEMA_VERSION": "BIGLOTTO_EXACT_PORTFOLIO_NULL_PERFORMANCE_V1",
    }
    source_contract: dict[str, object] = {
        "API": "exact_portfolio_any_prize_probability(portfolio)",
        "DISCOVERY_RESULT": {
            "RESULT": "NO_EXISTING_IMPLEMENTATION_SATISFIES_EXACT_FROZEN_CONTRACT",
            "REVIEWED_ADJACENT_SUPPORT": [
                "src/lottolab/research/bounded_coverage_optimizer.py",
                "src/lottolab/research/exact_coverage_fast_evaluator.py",
                "src/lottolab/application/historical_success_random_baseline.py",
            ],
            "SEARCH_ROOTS": ["src/lottolab/research", "src/lottolab/domain", "tools", "tests"],
        },
        "IMPLEMENTATION_PATH": str(source_path.relative_to(repository_root)),
        "IMPLEMENTATION_SHA256": _sha256(source_path),
        "RETURN_AUTHORITY": ["favorable outcome count", "total outcome count", "exact Fraction"],
        "SCHEMA_VERSION": "BIGLOTTO_EXACT_PORTFOLIO_NULL_SOURCE_CONTRACT_V1",
        "TEST_PATH": str(test_path.relative_to(repository_root)),
        "TEST_SHA256": _sha256(test_path),
        "TOOL_PATH": str(tool_path.relative_to(repository_root)),
        "TOOL_SHA256": _sha256(tool_path),
    }
    next_stage_handoff: dict[str, object] = {
        "EXACT": "YES",
        "INDEPENDENCE_APPROXIMATION": "NO",
        "MONTE_CARLO": "NO",
        "NEXT_STAGE_R2": "FORWARD_REGISTRATION_READINESS",
        "OUTCOME_SPACE": TOTAL_OUTCOME_COUNT,
        "R2_FORWARD_PROTOCOL_COMPATIBLE": "YES",
        "REUSABLE_BY_OTHER_FROZEN_BIGLOTTO_PORTFOLIO_STRATEGIES": "YES",
        "SCHEMA_VERSION": "BIGLOTTO_EXACT_PORTFOLIO_NULL_NEXT_STAGE_HANDOFF_V1",
        "SOURCE_HEAD": head,
        "SOURCE_STATE": source_state,
        "SOURCE_TREE": tree,
        "SUPPORT_KIND": "BIGLOTTO_EXACT_PORTFOLIO_ANY_PRIZE_NULL",
    }
    total_runtime = perf_counter() - started
    run_manifest: dict[str, object] = {
        "BRANCH": branch,
        "CANDIDATE_COUNT": len(candidates),
        "COMMAND": " ".join(sys.argv),
        "EXTERNAL_VERIFICATION_STATUS": external_verification,
        "FINAL_HEAD": head,
        "FINAL_TREE": tree,
        "INTERNAL_VALIDATION": {
            "CANONICAL_EVALUATOR_EQUIVALENCE": "PASS",
            "DETERMINISM": "PASS_9_OF_9",
            "DUPLICATE_IDEMPOTENCE": "PASS",
            "INDEPENDENT_EXACT_ORACLE": "PASS",
            "PAIR_OVERLAP_EXACTNESS": "PASS_3_CLASSES",
            "PORTFOLIO_ORDER_INVARIANCE": "PASS",
            "R2_CANDIDATE_COMPATIBILITY": "PASS_9_OF_9",
            "SINGLE_TICKET_EXACTNESS": "PASS",
        },
        "OUTPUT_FILES": list(ALL_OUTPUT_NAMES),
        "REPOSITORY_STATUS": status or "CLEAN",
        "SCHEMA_VERSION": "BIGLOTTO_EXACT_PORTFOLIO_NULL_RUN_MANIFEST_V1",
        "TASK_ID": TASK_ID,
        "TOTAL_RUNTIME_SECONDS": total_runtime,
    }
    payloads = {
        "support_authority.json": support_authority,
        "algorithm_contract.json": algorithm_contract,
        "canonical_evaluator_equivalence.json": canonical_equivalence,
        "exactness_oracle_validation.json": oracle_validation,
        "performance_manifest.json": performance_manifest,
        "source_contract.json": source_contract,
        "next_stage_handoff.json": next_stage_handoff,
        "run_manifest.json": run_manifest,
    }
    _write_outputs(output_root, payloads, csv_buffer.getvalue())
    print(
        json.dumps(
            {
                "CANDIDATE_COMPATIBILITY": "PASS_9_OF_9",
                "EXACTNESS": "PASS",
                "OUTPUT_ROOT": str(output_root),
                "SHA256SUMS": "PASS",
                "TOTAL_RUNTIME_SECONDS": total_runtime,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
