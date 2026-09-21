"""Build the canonical B649 OFFICIAL_ANY_PRIZE reference designation.

This module is a fail-closed designation gate.  It consumes the pinned
Phase-9/Phase-10 result bytes and the canonicalized postcheck evidence; it
does not invoke either optimizer, regenerate Method E, or recount outcomes.
The sealed postcheck verifier is evidence only and is stored as
``verifier-source.txt`` so repository Ruff cannot treat it as active Python.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path("docs/research/matrix-native-results")
EVIDENCE_DIR = RESULTS_DIR / ("b649-reference-e-improved-portfolio-official-any-prize-postcheck-r1")

OUTPUT_PATH = RESULTS_DIR / ("b649-official-any-prize-constructor-reference-designation-v1.json")
REPORT_PATH = RESULTS_DIR / (
    "b649-official-any-prize-constructor-reference-designation-v1-report.md"
)

REFERENCE_METHOD_ID = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
REFERENCE_METHOD_VERSION = "V1"
SEED_POLICY = "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
REFERENCE_PRIMARY_DECISION_METRIC = "OFFICIAL_ANY_PRIZE"
OPTIMIZATION_OBJECTIVE = "M3_PLUS_EXACT_COVERAGE"
POSTCHECK_OBJECTIVE = "OFFICIAL_ANY_PRIZE_EXACT"
SCOPE = "BIG_LOTTO K10/K15/K20 only"
STOP_TOKEN = "STOP_REFERENCE_DESIGNATION_AUTHORITY_UNRESOLVED"

K_SCOPE = (10, 15, 20)
K_NOT_SUPERSEDED = (1, 2, 3, 5)
BASE_HEAD = "947baf9da42a5656a6e6e9577b33cc5e33213347"
BASE_TREE = "109f6ca34db4363f11b378f2ad3cbeb730e6ce99"

PHASE9_RESULT_PATH = RESULTS_DIR / "reference-e-exact-one-exchange-b649-v1-result.json"
PHASE10_RESULT_PATH = RESULTS_DIR / (
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-result.json"
)
EXPECTED_MAX_RESULT_PATH = RESULTS_DIR / "expected-max-exact-1exchange-ascent-k20-r1-result.json"

PHASE9_RESULT_SHA256 = "5c45204d227cc3750b9efe68ec9afeb3d83d6bd72104acbe319897fc94013e00"
PHASE10_RESULT_SHA256 = "099ca254ff9143c00953bde62329b2b8ae298a1f8e2bcfb757ca1c263119aa2c"
EXPECTED_MAX_RESULT_SHA256 = "413c4af57cc38b282b4f03ae6c12961f4c91984d7f94c54c74fabfd2da8e2a89"

RESEARCH_SOURCE_HASHES: dict[Path, str] = {
    Path("src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py"): (
        "01e634924797355d4f19487a7abfaeed8910bc3b0c5ee8a6d95ebe617a368577"
    ),
    Path("src/lottolab/research/reference_e_exact_one_exchange_refinement.py"): (
        "83a69b45e622aedaf5e3e98552fa10b1cda75e21d5ee40aac4938b893b82e63e"
    ),
    Path("src/lottolab/research/greedy_minmax_then_sum_overlap_constructor.py"): (
        "26780ad1db8e9814a518a4d0d534d0925859a70f3ace580b8a4ebbc86b1d1c62"
    ),
    EXPECTED_MAX_RESULT_PATH: EXPECTED_MAX_RESULT_SHA256,
    PHASE9_RESULT_PATH: PHASE9_RESULT_SHA256,
    PHASE10_RESULT_PATH: PHASE10_RESULT_SHA256,
}

SEALED_VERIFIER_LOGICAL_NAME = "verifier.py"
SEALED_VERIFIER_STORED_PATH = EVIDENCE_DIR / "verifier-source.txt"
EVIDENCE_MANIFEST_PATH = EVIDENCE_DIR / "SHA256SUMS"
EVIDENCE_INPUTS_PATH = EVIDENCE_DIR / "inputs.json"
EVIDENCE_POSTCHECK_PATH = EVIDENCE_DIR / "official_any_prize_postcheck.json"

EVIDENCE_FILE_HASHES: dict[Path, str] = {
    EVIDENCE_POSTCHECK_PATH: "f49405c245020a0328e79c0a7194e840075a156539143a717757a864f787ed1f",
    EVIDENCE_INPUTS_PATH: "a62ea73a422b7f9a3169ca039e00acb421fc0d9a4af1aafda8007b8891ea20c8",
    EVIDENCE_MANIFEST_PATH: "b0a9a6cbe08b9d14d987fc04ca8605d5c4743a01d51fbcd7dd2658219a74ad70",
    SEALED_VERIFIER_STORED_PATH: "4e8cafdcb855be68797342b5a1154b84a327482e889d71db379f94f3e3a7796e",
}

MANIFEST_ENTRIES = {
    "inputs.json": EVIDENCE_FILE_HASHES[EVIDENCE_INPUTS_PATH],
    "official_any_prize_postcheck.json": EVIDENCE_FILE_HASHES[EVIDENCE_POSTCHECK_PATH],
    SEALED_VERIFIER_LOGICAL_NAME: EVIDENCE_FILE_HASHES[SEALED_VERIFIER_STORED_PATH],
}

REFERENCE_E_SEED_HASHES: dict[int, str] = {
    10: "8e7e2dd0417a3eab3b9c9155257cf8be443de4dc34132e50024851ea9b31a810",
    15: "a4400d0f1d50f096b74bfb72f8eb10f42bb31bfc6d3d180d6781a867ad1b1d62",
    20: "ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff",
}

PHASE9_SEED_HASHES: dict[int, str] = {
    10: "4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5",
    15: "ba6f516af65c31246550827ddcdcff2fcbf3f588be336e6de959a59dc898d1c8",
    20: "a107d9cb5c7e0def7b19ccf2a6d02306b25bc0efe3443ea9899f3a4755429a4a",
}

TERMINAL_PORTFOLIO_HASHES: dict[int, str] = {
    10: "4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5",
    15: "8057138edd980413fa52607144d66a90372e68d251654998e3a1767fd3d9ce83",
    20: "bf561d28d26961043f112ba8ed762ba9535666022c7df6bcefe49b8a21412710",
}

REFERENCE_M3_Q = {
    10: "212295/1165318",
    15: "927161/3495954",
    20: "17379/50666",
}
PHASE9_SEED_Q = {
    10: "90995/499422",
    15: "464027/1747977",
    20: "171323/499422",
}

PHASE10_MOVE_COUNTS = {10: 0, 15: 21, 20: 27}
COMBINED_ACCEPTED_MOVES = {10: 1, 15: 22, 20: 28}

# The Phase-9 first-step maximum-tie counts are part of the task authority.
# They are intentionally recorded separately from Phase-9's canonical result,
# whose scientific JSON stores the selected lexicographic winner but not the
# cardinality of the tied maximum set.
FIRST_STEP_MAX_TIES = {10: 1, 15: 40, 20: 1}

EXPECTED_OFFICIAL_ROWS: dict[int, dict[str, Any]] = {
    10: {
        "reference_official_any_prize_count": 176219120,
        "terminal_official_any_prize_count": 176291360,
        "reference_official_any_prize_q": "286070/976143",
        "terminal_official_any_prize_q": "66980/228459",
        "official_outcome_count_delta": 72240,
        "official_absolute_delta": "10/83237",
        "official_relative_lift": "129/314677",
        "reference_portfolio_sha256": REFERENCE_E_SEED_HASHES[10],
        "terminal_portfolio_sha256": TERMINAL_PORTFOLIO_HASHES[10],
    },
    15: {
        "reference_official_any_prize_count": 248523240,
        "terminal_official_any_prize_count": 250028100,
        "reference_official_any_prize_q": "1479305/3579191",
        "terminal_official_any_prize_q": "2976525/7158382",
        "official_outcome_count_delta": 1504860,
        "official_absolute_delta": "17915/7158382",
        "official_relative_lift": "3583/591722",
        "reference_portfolio_sha256": REFERENCE_E_SEED_HASHES[15],
        "terminal_portfolio_sha256": TERMINAL_PORTFOLIO_HASHES[15],
    },
    20: {
        "reference_official_any_prize_count": 311373272,
        "terminal_official_any_prize_count": 312463830,
        "reference_official_any_prize_q": "5560237/10737573",
        "terminal_official_any_prize_q": "7439615/14316764",
        "official_outcome_count_delta": 1090558,
        "official_absolute_delta": "77897/42950292",
        "official_relative_lift": "77897/22240948",
        "reference_portfolio_sha256": REFERENCE_E_SEED_HASHES[20],
        "terminal_portfolio_sha256": TERMINAL_PORTFOLIO_HASHES[20],
    },
}


def _require(condition: bool, what: str) -> None:
    if not condition:
        raise ValueError(f"{STOP_TOKEN}: {what}")


def _repo_path(path: Path) -> Path:
    return REPO_ROOT / path


def _read_bytes(path: Path) -> bytes:
    absolute = _repo_path(path)
    _require(absolute.is_file(), f"missing pinned artifact {path.as_posix()}")
    return absolute.read_bytes()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verify_hash(path: Path, expected: str) -> str:
    actual = _sha256(_read_bytes(path))
    _require(
        actual == expected,
        f"sha256 mismatch for {path.as_posix()}: expected {expected}, got {actual}",
    )
    return actual


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read_bytes(path))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{STOP_TOKEN}: invalid JSON at {path.as_posix()}") from exc
    _require(isinstance(payload, dict), f"JSON root is not an object: {path.as_posix()}")
    return cast(dict[str, Any], payload)


def _portfolio_sha256(portfolio: Any) -> str:
    return _sha256(json.dumps(portfolio, separators=(",", ":")).encode("utf-8"))


def _portfolio_rows(payload: Any, *, locator: str) -> list[list[int]]:
    _require(isinstance(payload, list), f"{locator} must be an array")
    rows: list[list[int]] = []
    for ticket_index, ticket_payload in enumerate(cast(list[Any], payload)):
        _require(
            isinstance(ticket_payload, list),
            f"{locator}[{ticket_index}] must be an array",
        )
        ticket = cast(list[Any], ticket_payload)
        _require(
            all(isinstance(number, int) for number in ticket),
            f"{locator}[{ticket_index}] must contain only integers",
        )
        rows.append([cast(int, number) for number in ticket])
    return rows


def _verify_sorted_portfolio(payload: Any, *, locator: str, ticket_count: int) -> list[list[int]]:
    rows = _portfolio_rows(payload, locator=locator)
    _require(len(rows) == ticket_count, f"{locator} ticket count mismatch")
    tickets = [tuple(row) for row in rows]
    _require(
        all(ticket == tuple(sorted(ticket)) for ticket in tickets),
        f"{locator} ticket order is not canonical",
    )
    _require(tickets == sorted(tickets), f"{locator} portfolio order is not canonical")
    _require(
        all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in tickets),
        f"{locator} ticket legality mismatch",
    )
    _require(
        all(1 <= number <= 49 for ticket in tickets for number in ticket),
        f"{locator} number range mismatch",
    )
    return rows


def _exact_fraction(payload: Any, *, locator: str) -> Fraction:
    _require(isinstance(payload, dict), f"{locator} must be an object")
    mapping = cast(dict[str, Any], payload)
    numerator = mapping.get("numerator")
    denominator = mapping.get("denominator")
    exact = mapping.get("exact")
    _require(
        isinstance(numerator, int) and isinstance(denominator, int),
        f"{locator} numerator/denominator mismatch",
    )
    numerator_int = cast(int, numerator)
    denominator_int = cast(int, denominator)
    try:
        value = Fraction(numerator_int, denominator_int)
    except ZeroDivisionError as exc:
        raise ValueError(f"{STOP_TOKEN}: zero denominator at {locator}") from exc
    _require(exact == f"{value.numerator}/{value.denominator}", f"{locator} exact string mismatch")
    return value


def _verify_repository_artifacts() -> dict[str, str]:
    verified: dict[str, str] = {}
    for path, expected in RESEARCH_SOURCE_HASHES.items():
        verified[path.as_posix()] = _verify_hash(path, expected)
    return verified


def _parse_manifest(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"{STOP_TOKEN}: SHA256SUMS is not UTF-8") from exc
    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        parts = line.split()
        _require(len(parts) == 2, f"SHA256SUMS malformed at line {line_number}")
        digest, logical_name = parts
        _require(
            len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
            f"SHA256SUMS digest malformed at line {line_number}",
        )
        _require(logical_name not in entries, f"SHA256SUMS duplicate logical name {logical_name}")
        entries[logical_name] = digest
    return entries


def _verify_evidence_bundle() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, str], dict[str, str]
]:
    for path, expected in EVIDENCE_FILE_HASHES.items():
        _verify_hash(path, expected)

    manifest = _parse_manifest(_read_bytes(EVIDENCE_MANIFEST_PATH))
    _require(
        manifest == MANIFEST_ENTRIES, "sealed SHA256SUMS entries do not match the pinned manifest"
    )

    stored_by_logical = {
        "inputs.json": EVIDENCE_INPUTS_PATH,
        "official_any_prize_postcheck.json": EVIDENCE_POSTCHECK_PATH,
        SEALED_VERIFIER_LOGICAL_NAME: SEALED_VERIFIER_STORED_PATH,
    }
    stored_hashes: dict[str, str] = {}
    for logical_name, stored_path in stored_by_logical.items():
        stored_hashes[logical_name] = _sha256(_read_bytes(stored_path))
        _require(
            stored_hashes[logical_name] == manifest[logical_name],
            f"logical sealed evidence hash mismatch for {logical_name}: "
            f"stored as {stored_path.as_posix()}",
        )

    inputs = _read_json(EVIDENCE_INPUTS_PATH)
    postcheck = _read_json(EVIDENCE_POSTCHECK_PATH)
    return inputs, postcheck, manifest, stored_hashes


def _verify_seed_source() -> tuple[dict[str, Any], dict[int, str]]:
    source = _read_json(EXPECTED_MAX_RESULT_PATH)
    seed_authority = source.get("seed_authority")
    _require(isinstance(seed_authority, dict), "Reference E seed authority missing")
    seed = cast(dict[str, Any], seed_authority)
    _require(seed.get("constructor_id") == SEED_POLICY, "Reference E seed constructor mismatch")
    constructor_order = _portfolio_rows(
        seed.get("constructor_order_portfolio"),
        locator="seed_authority.constructor_order_portfolio",
    )
    _require(
        len(constructor_order) == 20, "Reference E constructor-order seed must contain 20 tickets"
    )
    _require(
        _portfolio_sha256(constructor_order) == seed.get("constructor_order_portfolio_sha256"),
        "Reference E constructor-order portfolio hash mismatch",
    )
    hashes: dict[int, str] = {}
    for k in K_SCOPE:
        hashes[k] = _portfolio_sha256(constructor_order[:k])
        _require(
            hashes[k] == REFERENCE_E_SEED_HASHES[k], f"Reference E seed identity mismatch at k={k}"
        )
    return source, hashes


def _verify_evidence_authority(inputs: dict[str, Any]) -> None:
    authority = inputs.get("authority")
    _require(isinstance(authority, dict), "postcheck input authority missing")
    auth = cast(dict[str, Any], authority)
    _require(auth.get("base_head") == BASE_HEAD, "postcheck base HEAD mismatch")
    _require(auth.get("base_tree") == BASE_TREE, "postcheck base tree mismatch")
    phase9_auth = auth.get("reference_e_authority")
    phase10_auth = auth.get("phase10_authority")
    _require(isinstance(phase9_auth, dict), "Reference E authority missing from postcheck inputs")
    _require(isinstance(phase10_auth, dict), "Phase 10 authority missing from postcheck inputs")
    phase9_mapping = cast(dict[str, Any], phase9_auth)
    phase10_mapping = cast(dict[str, Any], phase10_auth)
    _require(
        phase9_mapping.get("file_sha256") == PHASE9_RESULT_SHA256, "postcheck Phase 9 hash mismatch"
    )
    _require(
        phase10_mapping.get("file_sha256") == PHASE10_RESULT_SHA256,
        "postcheck Phase 10 hash mismatch",
    )
    _require(
        phase10_mapping.get("primary_event") == "M3_PLUS", "postcheck Phase 10 objective mismatch"
    )
    _require(
        phase10_mapping.get("global_optimum_status") == "UNKNOWN",
        "postcheck global optimum status mismatch",
    )
    _require(
        phase10_mapping.get("phase10_execution_gate") == "PASS", "postcheck Phase 10 gate mismatch"
    )

    per_k = inputs.get("per_k")
    _require(isinstance(per_k, dict), "postcheck per_k inputs missing")
    per_k_mapping = cast(dict[str, Any], per_k)
    for k in K_SCOPE:
        row = per_k_mapping.get(str(k))
        _require(isinstance(row, dict), f"postcheck inputs missing k={k}")
        mapping = cast(dict[str, Any], row)
        reference = mapping.get("reference")
        terminal = mapping.get("terminal")
        _require(
            isinstance(reference, dict) and isinstance(terminal, dict),
            f"postcheck portfolios missing k={k}",
        )
        reference_mapping = cast(dict[str, Any], reference)
        terminal_mapping = cast(dict[str, Any], terminal)
        _require(
            reference_mapping.get("expected_sha256") == REFERENCE_E_SEED_HASHES[k],
            f"Reference E input hash mismatch at k={k}",
        )
        _require(
            terminal_mapping.get("expected_sha256") == TERMINAL_PORTFOLIO_HASHES[k],
            f"terminal input hash mismatch at k={k}",
        )
        reference_portfolio = _portfolio_rows(
            reference_mapping.get("portfolio"), locator=f"inputs.per_k.{k}.reference.portfolio"
        )
        terminal_portfolio = _verify_sorted_portfolio(
            terminal_mapping.get("portfolio"),
            locator=f"inputs.per_k.{k}.terminal.portfolio",
            ticket_count=k,
        )
        _require(
            _portfolio_sha256(reference_portfolio) == REFERENCE_E_SEED_HASHES[k],
            f"Reference E input bytes mismatch at k={k}",
        )
        _require(
            _portfolio_sha256(terminal_portfolio) == TERMINAL_PORTFOLIO_HASHES[k],
            f"terminal input bytes mismatch at k={k}",
        )
        _require(
            reference_mapping.get("sealed_m3_q") == REFERENCE_M3_Q[k],
            f"Reference E M3 Q mismatch at k={k}",
        )


def _verify_phase9(
    phase9: dict[str, Any], seed_hashes: dict[int, str]
) -> dict[int, dict[str, Any]]:
    _require(
        phase9.get("study_id") == "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1",
        "Phase 9 study identity mismatch",
    )
    _require(
        phase9.get("task_id") == "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1",
        "Phase 9 task identity mismatch",
    )
    _require(phase9.get("primary_event") == "M3_PLUS", "Phase 9 primary event mismatch")
    _require(
        phase9.get("primary_event_minimum_matches") == 3, "Phase 9 minimum-match objective mismatch"
    )
    _require(phase9.get("reference_constructor_id") == SEED_POLICY, "Phase 9 constructor mismatch")
    _require(phase9.get("exposure_ladder") == list(K_SCOPE), "Phase 9 scope mismatch")
    gate = phase9.get("gate")
    regeneration = phase9.get("reference_e_regeneration")
    _require(
        isinstance(gate, dict) and isinstance(regeneration, dict),
        "Phase 9 gate or regeneration record missing",
    )
    gate_mapping = cast(dict[str, Any], gate)
    regeneration_mapping = cast(dict[str, Any], regeneration)
    _require(
        gate_mapping.get("phase9_advance_gate") == "PASS",
        "Phase 9 advance gate mismatch",
    )
    _require(
        gate_mapping.get("global_optimum_status") == "UNKNOWN",
        "Phase 9 global optimum status mismatch",
    )
    _require(
        regeneration_mapping.get("matches_sealed_phase7_authority") is True,
        "Phase 9 sealed Reference E parity mismatch",
    )
    _require(
        regeneration_mapping.get("portfolio_20_sha256") == REFERENCE_E_SEED_HASHES[20],
        "Phase 9 k20 Reference E hash mismatch",
    )

    raw_per_k = phase9.get("per_k")
    _require(isinstance(raw_per_k, dict), "Phase 9 per_k result missing")
    per_k = cast(dict[str, Any], raw_per_k)
    verified: dict[int, dict[str, Any]] = {}
    for k in K_SCOPE:
        row = per_k.get(str(k))
        _require(isinstance(row, dict), f"Phase 9 k={k} result missing")
        mapping = cast(dict[str, Any], row)
        _require(
            mapping.get("reference_portfolio_sha256") == REFERENCE_E_SEED_HASHES[k],
            f"Phase 9 reference seed hash mismatch at k={k}",
        )
        best_portfolio = _verify_sorted_portfolio(
            mapping.get("best_neighbor_portfolio"),
            locator=f"phase9.per_k.{k}.best_neighbor_portfolio",
            ticket_count=k,
        )
        _require(
            _portfolio_sha256(best_portfolio) == PHASE9_SEED_HASHES[k],
            f"Phase 9 selected seed identity mismatch at k={k}",
        )
        _require(
            mapping.get("best_neighbor_portfolio_sha256") == PHASE9_SEED_HASHES[k],
            f"Phase 9 selected seed artifact hash mismatch at k={k}",
        )
        _require(
            mapping.get("classification") == "ONE_EXCHANGE_IMPROVEMENT_FOUND",
            f"Phase 9 improvement classification mismatch at k={k}",
        )
        _require(
            _exact_fraction(mapping.get("q_reference_e"), locator=f"phase9.per_k.{k}.q_reference_e")
            == Fraction(REFERENCE_M3_Q[k]),
            f"Phase 9 Reference E Q mismatch at k={k}",
        )
        _require(
            _exact_fraction(
                mapping.get("q_best_neighbor"), locator=f"phase9.per_k.{k}.q_best_neighbor"
            )
            == Fraction(PHASE9_SEED_Q[k]),
            f"Phase 9 seed Q mismatch at k={k}",
        )
        delta = _exact_fraction(
            mapping.get("delta_vs_reference_e"), locator=f"phase9.per_k.{k}.delta_vs_reference_e"
        )
        _require(delta > 0, f"Phase 9 improvement is not strict at k={k}")
        verified[k] = {
            "reference_portfolio_sha256": REFERENCE_E_SEED_HASHES[k],
            "phase9_seed_portfolio_sha256": PHASE9_SEED_HASHES[k],
            "reference_m3_q": REFERENCE_M3_Q[k],
            "phase9_seed_q": PHASE9_SEED_Q[k],
            "phase9_delta_vs_reference_e": str(delta),
            "unique_neighbor_count": mapping.get("unique_neighbor_count"),
        }
    return verified


def _verify_phase10(
    phase10: dict[str, Any],
    phase9_verified: dict[int, dict[str, Any]],
    inputs: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    _require(
        phase10.get("study_id")
        == "STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1",
        "Phase 10 study identity mismatch",
    )
    _require(
        phase10.get("task_id")
        == "STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1",
        "Phase 10 task identity mismatch",
    )
    _require(
        phase10.get("refinement_method_id") == REFERENCE_METHOD_ID,
        "Phase 10 method identity mismatch",
    )
    _require(phase10.get("primary_event") == "M3_PLUS", "Phase 10 primary event mismatch")
    _require(
        phase10.get("primary_event_minimum_matches") == 3,
        "Phase 10 minimum-match objective mismatch",
    )
    _require(phase10.get("exposure_ladder") == list(K_SCOPE), "Phase 10 scope mismatch")
    _require(phase10.get("rung_coupling") == "NONE", "Phase 10 rung coupling mismatch")
    gate = phase10.get("gate")
    policy = phase10.get("reference_policy")
    _require(
        isinstance(gate, dict) and isinstance(policy, dict),
        "Phase 10 gate or policy record missing",
    )
    gate_mapping = cast(dict[str, Any], gate)
    policy_mapping = cast(dict[str, Any], policy)
    _require(
        gate_mapping.get("phase10_execution_gate") == "PASS",
        "Phase 10 execution gate mismatch",
    )
    _require(
        gate_mapping.get("global_optimum_status") == "UNKNOWN",
        "Phase 10 global optimum status mismatch",
    )
    _require(
        policy_mapping.get("global_optimum_status") == "UNKNOWN",
        "Phase 10 policy global optimum status mismatch",
    )
    _require(
        policy_mapping.get("runtime_promotion") == "NOT_AUTHORIZED",
        "Phase 10 runtime promotion mismatch",
    )

    raw_per_k = phase10.get("per_k")
    input_per_k = inputs["per_k"]
    _require(
        isinstance(raw_per_k, dict) and isinstance(input_per_k, dict),
        "Phase 10 per_k result missing",
    )
    per_k = cast(dict[str, Any], raw_per_k)
    input_per_k_mapping = cast(dict[str, Any], input_per_k)
    verified: dict[int, dict[str, Any]] = {}
    for k in K_SCOPE:
        row = per_k.get(str(k))
        _require(isinstance(row, dict), f"Phase 10 k={k} result missing")
        mapping = cast(dict[str, Any], row)
        _require(
            mapping.get("phase9_seed_portfolio_sha256") == PHASE9_SEED_HASHES[k],
            f"Phase 10 Phase 9 seed hash mismatch at k={k}",
        )
        phase9_seed_portfolio = _verify_sorted_portfolio(
            mapping.get("phase9_seed_portfolio"),
            locator=f"phase10.per_k.{k}.phase9_seed_portfolio",
            ticket_count=k,
        )
        _require(
            _portfolio_sha256(phase9_seed_portfolio) == PHASE9_SEED_HASHES[k],
            f"Phase 10 Phase 9 seed bytes mismatch at k={k}",
        )
        terminal_portfolio = _verify_sorted_portfolio(
            mapping.get("terminal_portfolio"),
            locator=f"phase10.per_k.{k}.terminal_portfolio",
            ticket_count=k,
        )
        _require(
            _portfolio_sha256(terminal_portfolio) == TERMINAL_PORTFOLIO_HASHES[k],
            f"Phase 10 terminal identity mismatch at k={k}",
        )
        _require(
            mapping.get("terminal_portfolio_sha256") == TERMINAL_PORTFOLIO_HASHES[k],
            f"Phase 10 terminal artifact hash mismatch at k={k}",
        )
        input_row = input_per_k_mapping.get(str(k))
        _require(
            isinstance(input_row, dict),
            f"postcheck input k={k} missing for Phase 10 reconciliation",
        )
        input_row_mapping = cast(dict[str, Any], input_row)
        raw_input_terminal = input_row_mapping.get("terminal")
        _require(
            isinstance(raw_input_terminal, dict),
            f"postcheck input terminal missing at k={k}",
        )
        input_terminal = cast(dict[str, Any], raw_input_terminal)
        _require(
            terminal_portfolio
            == _portfolio_rows(
                input_terminal.get("portfolio"), locator=f"inputs.per_k.{k}.terminal.portfolio"
            ),
            f"Phase 10 terminal portfolio differs from postcheck input at k={k}",
        )
        _require(
            mapping.get("move_count") == PHASE10_MOVE_COUNTS[k],
            f"Phase 10 move count mismatch at k={k}",
        )
        _require(
            mapping.get("iteration_count") == PHASE10_MOVE_COUNTS[k] + 1,
            f"Phase 10 iteration count mismatch at k={k}",
        )
        _require(
            mapping.get("terminal_classification") == "TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED",
            f"Phase 10 terminal classification mismatch at k={k}",
        )
        certificate = mapping.get("terminal_certificate")
        _require(
            certificate
            == {
                "accepted_moves_strict_exact_improvements": True,
                "move_count_consistent": True,
                "status": "PASS",
                "terminal_best_q_lte_terminal_q": True,
                "terminal_iteration_accepted_move": False,
            },
            f"Phase 10 terminal certificate mismatch at k={k}",
        )
        iterations = mapping.get("iterations")
        _require(isinstance(iterations, list), f"Phase 10 iteration trace is not a list at k={k}")
        iterations_list = cast(list[Any], iterations)
        _require(
            len(iterations_list) == PHASE10_MOVE_COUNTS[k] + 1,
            f"Phase 10 iteration trace mismatch at k={k}",
        )
        accepted = 0
        for index, iteration_payload in enumerate(iterations_list):
            _require(
                isinstance(iteration_payload, dict), f"Phase 10 iteration {index} missing at k={k}"
            )
            iteration = cast(dict[str, Any], iteration_payload)
            _require(
                iteration.get("iteration_index") == index,
                f"Phase 10 iteration index mismatch at k={k}, iteration={index}",
            )
            delta = _exact_fraction(
                iteration.get("delta"), locator=f"phase10.per_k.{k}.iterations[{index}].delta"
            )
            if iteration.get("accepted_move") is True:
                accepted += 1
                _require(
                    delta > 0, f"Phase 10 accepted non-strict move at k={k}, iteration={index}"
                )
            else:
                _require(
                    iteration.get("accepted_move") is False,
                    f"Phase 10 accepted_move is not boolean at k={k}, iteration={index}",
                )
        _require(
            accepted == PHASE10_MOVE_COUNTS[k], f"Phase 10 accepted move total mismatch at k={k}"
        )
        _require(
            cast(dict[str, Any], iterations_list[-1]).get("accepted_move") is False,
            f"Phase 10 terminal iteration was accepted at k={k}",
        )
        verified[k] = {
            "phase9_seed_portfolio_sha256": PHASE9_SEED_HASHES[k],
            "terminal_portfolio_sha256": TERMINAL_PORTFOLIO_HASHES[k],
            "phase10_move_count": PHASE10_MOVE_COUNTS[k],
            "phase10_iteration_count": PHASE10_MOVE_COUNTS[k] + 1,
            "terminal_classification": mapping["terminal_classification"],
            "terminal_certificate": cast(dict[str, Any], certificate),
            "phase10_delta_vs_phase9_seed": mapping["delta_terminal_vs_phase9_seed"]["exact"],
            "phase10_delta_vs_method_e": mapping["delta_terminal_vs_method_e"]["exact"],
        }
    return verified


def _verify_postcheck(
    inputs: dict[str, Any],
    postcheck: dict[str, Any],
    phase10_verified: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    _verify_evidence_authority(inputs)
    _require(
        postcheck.get("task_id")
        == "B649_REFERENCE_E_IMPROVED_PORTFOLIO_OFFICIAL_ANY_PRIZE_POSTCHECK_R1",
        "postcheck task identity mismatch",
    )
    _require(postcheck.get("task_status") == "COMPLETE", "postcheck task is not COMPLETE")
    _require(postcheck.get("lottery_type") == "BIG_LOTTO", "postcheck lottery mismatch")
    _require(
        postcheck.get("overall_classification") == "OFFICIAL_ANY_PRIZE_LIFT_REPLICATED_K10_K15_K20",
        "postcheck classification mismatch",
    )
    _require(
        postcheck.get("total_main_draw_count") == 13983816, "postcheck main draw count mismatch"
    )
    _require(
        postcheck.get("total_outcome_count") == 601304088, "postcheck total outcome count mismatch"
    )
    _require(
        postcheck.get("authority") == inputs["authority"],
        "postcheck authority does not equal canonical inputs",
    )
    contract = postcheck.get("official_any_prize_contract")
    _require(isinstance(contract, dict), "official any-prize contract missing")
    contract_mapping = cast(dict[str, Any], contract)
    _require(
        contract_mapping.get("portfolio_event")
        == "at least one selected ticket receives any official prize",
        "official any-prize portfolio event mismatch",
    )
    _require(
        contract_mapping.get("rule")
        == (
            "main_matches >= 3 OR (main_matches == 2 AND official special number "
            "is one of the ticket's remaining selected numbers)"
        ),
        "official any-prize rule mismatch",
    )
    _require(
        contract_mapping.get("canonical_source")
        == "src/lottolab/domain/lottery_rules.py BIG_LOTTO_RULE_CONTRACT.prize_rule",
        "official any-prize rule source mismatch",
    )
    verification = postcheck.get("verification")
    _require(isinstance(verification, dict), "postcheck verification is not an object")
    verification_mapping = cast(dict[str, Any], verification)
    _require(
        set(verification_mapping.values()) == {"PASS"},
        "postcheck verification is not all PASS",
    )
    invariants = postcheck.get("invariants")
    _require(isinstance(invariants, dict), "postcheck invariants missing")
    invariant_mapping = cast(dict[str, Any], invariants)
    _require(
        invariant_mapping.get("historical_outcome_data_used") is False,
        "postcheck historical outcome invariant mismatch",
    )
    _require(
        invariant_mapping.get("monte_carlo") is False,
        "postcheck Monte Carlo invariant mismatch",
    )
    _require(invariant_mapping.get("db_access") is False, "postcheck DB invariant mismatch")
    _require(
        invariant_mapping.get("production_mutation") == "NONE",
        "postcheck production mutation invariant mismatch",
    )
    _require(
        invariant_mapping.get("candidate_generation") == "NONE",
        "postcheck candidate generation invariant mismatch",
    )
    _require(
        invariant_mapping.get("portfolio_mutation") == "NONE",
        "postcheck portfolio mutation invariant mismatch",
    )
    _require(
        invariant_mapping.get("exact_arithmetic") == "FRACTION",
        "postcheck exact arithmetic invariant mismatch",
    )
    _require(
        invariant_mapping.get("predictive_signal_claim") is False,
        "postcheck predictive-signal invariant mismatch",
    )
    _require(
        invariant_mapping.get("global_optimum_status") == "UNKNOWN",
        "postcheck global optimum invariant mismatch",
    )

    per_k = postcheck.get("per_k")
    _require(isinstance(per_k, dict), "postcheck per_k result missing")
    per_k_mapping = cast(dict[str, Any], per_k)
    verified: dict[int, dict[str, Any]] = {}
    for k in K_SCOPE:
        row = per_k_mapping.get(str(k))
        _require(isinstance(row, dict), f"postcheck k={k} result missing")
        mapping = cast(dict[str, Any], row)
        expected = EXPECTED_OFFICIAL_ROWS[k]
        for field, value in expected.items():
            _require(mapping.get(field) == value, f"postcheck {field} mismatch at k={k}")
        _require(mapping.get("k") == k, f"postcheck k field mismatch at k={k}")
        _require(
            mapping.get("classification") == "M3_IMPROVEMENT_CONFIRMED_OFFICIAL_ANY_PRIZE_POSITIVE",
            f"postcheck per-k classification mismatch at k={k}",
        )
        _require(
            phase10_verified[k]["terminal_portfolio_sha256"]
            == mapping["terminal_portfolio_sha256"],
            f"postcheck terminal hash does not reconcile at k={k}",
        )
        verified[k] = {field: mapping[field] for field in expected}
        verified[k]["classification"] = mapping["classification"]
        verified[k]["reference_m3_q"] = mapping["reference_m3_q"]
        verified[k]["terminal_m3_q"] = mapping["terminal_m3_q"]
    return verified


def build_designation() -> dict[str, Any]:
    """Verify all pinned identities and return deterministic designation data."""

    repository_hashes = _verify_repository_artifacts()
    inputs, postcheck, manifest, stored_evidence_hashes = _verify_evidence_bundle()
    seed_source, seed_hashes = _verify_seed_source()
    phase9 = _read_json(PHASE9_RESULT_PATH)
    phase10 = _read_json(PHASE10_RESULT_PATH)
    phase9_verified = _verify_phase9(phase9, seed_hashes)
    phase10_verified = _verify_phase10(phase10, phase9_verified, inputs)
    official_verified = _verify_postcheck(inputs, postcheck, phase10_verified)

    per_k: dict[str, dict[str, Any]] = {}
    for k in K_SCOPE:
        combined_moves = 1 + phase10_verified[k]["phase10_move_count"]
        _require(
            combined_moves == COMBINED_ACCEPTED_MOVES[k],
            f"combined accepted-move count mismatch at k={k}",
        )
        per_k[str(k)] = {
            "k": k,
            "reference_e_seed_sha256": seed_hashes[k],
            "reference_e_seed_hash_convention": "constructor-order compact JSON",
            "phase9_seed_sha256": PHASE9_SEED_HASHES[k],
            "phase9_seed_hash_convention": "sorted compact JSON",
            "terminal_portfolio_sha256": TERMINAL_PORTFOLIO_HASHES[k],
            "terminal_portfolio_hash_convention": "sorted compact JSON",
            "phase9_first_exchange_count": 1,
            "phase10_accepted_moves": phase10_verified[k]["phase10_move_count"],
            "combined_accepted_moves_from_reference_e": combined_moves,
            "first_step_max_ties": FIRST_STEP_MAX_TIES[k],
            "phase10_terminal_certificate": phase10_verified[k]["terminal_certificate"],
            "official_any_prize": official_verified[k],
        }

    evidence_map = {
        "canonical_directory": EVIDENCE_DIR.as_posix(),
        "manifest_path": EVIDENCE_MANIFEST_PATH.as_posix(),
        "manifest_sha256": EVIDENCE_FILE_HASHES[EVIDENCE_MANIFEST_PATH],
        "manifest_entries": manifest,
        "logical_to_stored": {
            "inputs.json": EVIDENCE_INPUTS_PATH.as_posix(),
            "official_any_prize_postcheck.json": EVIDENCE_POSTCHECK_PATH.as_posix(),
            SEALED_VERIFIER_LOGICAL_NAME: SEALED_VERIFIER_STORED_PATH.as_posix(),
        },
        "stored_sha256": stored_evidence_hashes,
        "verifier_bytes": "PRESERVED_EXACTLY",
    }

    return {
        "designation_id": "B649_OFFICIAL_ANY_PRIZE_CONSTRUCTOR_REFERENCE_DESIGNATION_R1",
        "source_type": "BIG_LOTTO_REFERENCE_DESIGNATION",
        "reference_update": "REFERENCE_UPDATE_RECOMMENDED",
        "reference_method_id": REFERENCE_METHOD_ID,
        "reference_method_version": REFERENCE_METHOD_VERSION,
        "seed_policy": SEED_POLICY,
        "scope": SCOPE,
        "scope_detail": {
            "lottery": "BIG_LOTTO",
            "superseded_k": list(K_SCOPE),
            "not_superseded_k": list(K_NOT_SUPERSEDED),
            "other_lotteries_not_superseded": ["T539", "P638"],
            "supersession_rule": "Reference E is superseded only for BIG_LOTTO K10/K15/K20.",
        },
        "reference_primary_decision_metric": REFERENCE_PRIMARY_DECISION_METRIC,
        "optimization_objective": OPTIMIZATION_OBJECTIVE,
        "postcheck_objective": POSTCHECK_OBJECTIVE,
        "objective_split": {
            "optimization_metric": "M3_PLUS",
            "optimization_objective": OPTIMIZATION_OBJECTIVE,
            "decision_metric": REFERENCE_PRIMARY_DECISION_METRIC,
            "postcheck_objective": POSTCHECK_OBJECTIVE,
            "optimization_did_not_optimize_official_any_prize_directly": True,
            "official_any_prize_postcheck_reconciled": True,
        },
        "reference_comparator": "YES",
        "global_optimum_status": "UNKNOWN",
        "known_frontier": "NO",
        "runtime_promotion": "NOT_AUTHORIZED",
        "production_promotion": "NOT_AUTHORIZED",
        "predictive_signal_claim": "NO",
        "historical_oos_claim": "NO",
        "expected_payout_claim": "NO",
        "strategy_id_created": "NO",
        "hash_conventions": {
            "reference_e_seed": "constructor-order compact JSON",
            "phase9_seed": "sorted compact JSON",
            "terminal_portfolio": "sorted compact JSON",
            "sealed_manifest": (
                "SHA-256 of exact bytes; logical verifier.py is mapped to the stored "
                "non-Python evidence filename"
            ),
        },
        "authority": {
            "base_head": BASE_HEAD,
            "base_tree": BASE_TREE,
            "repository_artifacts": repository_hashes,
            "seed_source": {
                "path": EXPECTED_MAX_RESULT_PATH.as_posix(),
                "constructor_id": seed_source["seed_authority"]["constructor_id"],
                "constructor_order_portfolio_sha256": seed_source["seed_authority"][
                    "constructor_order_portfolio_sha256"
                ],
            },
            "phase9_result": {
                "path": PHASE9_RESULT_PATH.as_posix(),
                "sha256": PHASE9_RESULT_SHA256,
            },
            "phase10_result": {
                "path": PHASE10_RESULT_PATH.as_posix(),
                "sha256": PHASE10_RESULT_SHA256,
            },
        },
        "evidence": evidence_map,
        "per_k": per_k,
        "caveats": [
            "This is a reference comparator, not a known frontier or global optimum.",
            "Radius-1 local optimality does not establish global optimality.",
            (
                "The designation is fixed-budget portfolio geometry only; it makes no "
                "predictive, OOS, bias, or payout claim."
            ),
            (
                "K10/K15/K20 supersession does not regrade K1/K2/K3/K5, T539, P638, "
                "or prior Matrix result cells."
            ),
        ],
    }


def render_report(designation: dict[str, Any]) -> str:
    rows = designation["per_k"]
    lines = [
        "# B649 OFFICIAL_ANY_PRIZE constructor reference designation R1",
        "",
        (
            "Status: CANONICALIZED — research reference designation only; no runtime "
            "or production promotion."
        ),
        "",
        f"REFERENCE_UPDATE: {designation['reference_update']}",
        f"REFERENCE_METHOD_ID: {designation['reference_method_id']}",
        f"SEED_POLICY: {designation['seed_policy']}",
        f"REFERENCE_METHOD_VERSION: {designation['reference_method_version']}",
        f"SCOPE: {designation['scope']}",
        f"REFERENCE_PRIMARY_DECISION_METRIC: {designation['reference_primary_decision_metric']}",
        f"OPTIMIZATION_OBJECTIVE: {designation['optimization_objective']}",
        f"POSTCHECK_OBJECTIVE: {designation['postcheck_objective']}",
        "",
        "## Decision boundary",
        "",
        "The iterative exact one-number-exchange refinement is designated as the",
        "reference comparator only for BIG_LOTTO K10/K15/K20. The refinement",
        "optimizes M3_PLUS exact coverage; OFFICIAL_ANY_PRIZE is the primary",
        "decision metric checked by the separate exact postcheck.",
        "",
        (
            "| K | Reference E seed hash | Terminal hash | Phase 10 moves | Combined "
            "moves | First-step max ties | Official outcomes gained |"
        ),
        "|---:|:---|:---|---:|---:|---:|---:|",
    ]
    for k in K_SCOPE:
        row = rows[str(k)]
        lines.append(
            f"| {k} | `{row['reference_e_seed_sha256']}` | `{row['terminal_portfolio_sha256']}` | "
            f"{row['phase10_accepted_moves']} | "
            f"{row['combined_accepted_moves_from_reference_e']} | "
            f"{row['first_step_max_ties']} | "
            f"{row['official_any_prize']['official_outcome_count_delta']} |"
        )
    lines.extend(
        [
            "",
            "The K15 first-step maximum tie count (40) is load-bearing: exact-Q",
            "ties use the lexicographically smallest canonical portfolio. No plateau",
            "move is accepted.",
            "",
            "## Required status fields",
            "",
            "```text",
            "GLOBAL_OPTIMUM_STATUS: UNKNOWN",
            "KNOWN_FRONTIER: NO",
            "REFERENCE_COMPARATOR: YES",
            "RUNTIME_PROMOTION: NOT_AUTHORIZED",
            "PRODUCTION_PROMOTION: NOT_AUTHORIZED",
            "PREDICTIVE_SIGNAL_CLAIM: NO",
            "HISTORICAL_OOS_CLAIM: NO",
            "EXPECTED_PAYOUT_CLAIM: NO",
            "STRATEGY_ID_CREATED: NO",
            "```",
            "",
            "K1/K2/K3/K5 are not superseded. T539 and P638 are not superseded.",
            "No Phase-7, Phase-9, Phase-10, Matrix, runtime, DB, API, or frontend",
            "artifact was modified by this designation.",
            "",
            "## Canonicalized postcheck evidence",
            "",
            f"Evidence directory: `{designation['evidence']['canonical_directory']}`",
            "",
            "The original `SHA256SUMS` bytes are preserved. Its logical sealed",
            "filename `verifier.py` maps to the stored non-Python evidence file",
            "`verifier-source.txt`; its bytes match the manifest digest exactly.",
            "The manifest is reconciled logically because the physical filename",
            "differs; direct `shasum -c SHA256SUMS` is not claimed for the relocated",
            "directory.",
            "",
            "Do not call this designation best known or globally optimal; do not",
            "start the next task, push, or open a PR in this task.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    designation = build_designation()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(designation, indent=2, sort_keys=True).rstrip("\n") + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(render_report(designation), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"wrote {REPORT_PATH}")
    print(f"reference_method_id: {REFERENCE_METHOD_ID}")
    print(f"scope: {SCOPE}")


if __name__ == "__main__":
    main()
