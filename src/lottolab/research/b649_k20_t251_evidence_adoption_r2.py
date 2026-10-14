"""Validate the isolated T-cap evidence adoption for profile 66555555555531000000.

This module reads only the pinned family result, its pinned primary per-T
certificate, and the method that defines the source JSON digest and columns.
It does not replay the Family ledger, invoke a solver, or certify a family
closure.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_ID = "B649_K20_T251_ISOLATED_EVIDENCE_ADOPTION_R2"
PROFILE = "66555555555531000000"
FROZEN_HEAD = "e6fee5ebbfb972a1432bbc10ab5a337feac38478"
FROZEN_TREE = "0f32a6e5c813953bb902cce395b5b6fea0a77c59"

FAMILY_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-neighbor-deficit-sts13-family-closure-r1-result.json"
)
FAMILY_RESULT_SHA256 = "fef709c5168afa6da26ce18e0be78c40a12c6a711dec364e42659e1bb309d7b6"
PER_T_SOURCE_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-shared-neighbor-deficit-certificate-r1-result.json"
)
PER_T_SOURCE_SHA256 = "4e7b8163846f6b87c561fc7a96f12a18c46636ee66c9d0dfdd0b24eb1ec08dfa"
SOURCE_METHOD_ID = "b649_k20_min_s2_shared_neighbor_deficit_certificate_r1"
SOURCE_METHOD_PATH = f"src/lottolab/research/{SOURCE_METHOD_ID}.py"
SOURCE_METHOD_SHA256 = "ff1fe5bc00ec0fb50ad82af740f4747f7b8d0894830f7f151596d4ff4912ba53"
SOURCE_COLUMN = "BOUND"
SOURCE_COLUMN_INDEX = 12
SOURCE_TERM_COLUMNS = [
    "T",
    "OLD_BOUND",
    "OLD_K4_FLOOR",
    "OLD_CONTAINED_K4_CAP",
    "OLD_S4",
    "S3",
    "L_HAT",
    "K4_FLOOR",
    "SHARED_S4_FLOOR",
    "S4_USED",
    "FOURTH_ORDER_BOUND",
    "FIFTH_ORDER_BOUND",
    "BOUND",
]

OLD_CAP = 265
T_CAP = 251
EXPECTED_OLD_ROW_BOUND = 313261354
EXPECTED_NEW_ROW_BOUND = 313142921
EXPECTED_ROW_DELTA = 118433
EXPECTED_OLD_TERM_COUNT = 244
EXPECTED_TERM_COUNT = 230
EXPECTED_ARGMAX_NEW_T = 251
EXPECTED_TERM_DIGEST = "bee307b6d1bb35e59fae704f8b1c523048f641e798aa2ea534d487c10b17a6c1"

RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/"
    "b649-k20-t251-evidence-adoption-r2-result.json"
)


class EvidenceValidationError(ValueError):
    """Raised when evidence or its pinned provenance fails closed."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _source_digest(value: object) -> str:
    """Mirror the pinned source method's digest serializer exactly."""
    return _sha256(json.dumps(value, sort_keys=True).encode())


def _pinned_json(root: Path, relative_path: str, expected_sha256: str) -> dict[str, Any]:
    path = root / relative_path
    if path.is_symlink() or not path.is_file():
        raise EvidenceValidationError(f"pinned input is not a regular file: {relative_path}")
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise EvidenceValidationError(f"cannot read pinned input: {relative_path}") from exc
    observed_sha256 = _sha256(blob)
    if observed_sha256 != expected_sha256:
        raise EvidenceValidationError(f"pinned input digest mismatch: {relative_path}")
    try:
        value = json.loads(blob)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError(f"pinned input is not valid JSON: {relative_path}") from exc
    if type(value) is not dict:
        raise EvidenceValidationError(f"pinned input must be a JSON object: {relative_path}")
    return value


def _verify_frozen_git_identity(root: Path) -> None:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{FROZEN_HEAD}^{{commit}}"],
            cwd=root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
        tree = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{FROZEN_HEAD}^{{tree}}"],
            cwd=root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceValidationError("frozen Git identity is unavailable") from exc
    if commit != FROZEN_HEAD or tree != FROZEN_TREE:
        raise EvidenceValidationError("frozen Git identity mismatch")


def _exact_int(value: object) -> bool:
    return type(value) is int


def _expected_payload(root: Path) -> dict[str, Any]:
    _verify_frozen_git_identity(root)

    family = _pinned_json(root, FAMILY_RESULT_PATH, FAMILY_RESULT_SHA256)
    per_t_source = _pinned_json(root, PER_T_SOURCE_PATH, PER_T_SOURCE_SHA256)
    method_path = root / SOURCE_METHOD_PATH
    if method_path.is_symlink() or not method_path.is_file():
        raise EvidenceValidationError("pinned source method is not a regular file")
    try:
        method_blob = method_path.read_bytes()
    except OSError as exc:
        raise EvidenceValidationError("cannot read pinned source method") from exc
    if _sha256(method_blob) != SOURCE_METHOD_SHA256:
        raise EvidenceValidationError("pinned source method digest mismatch")

    family_links = family.get("SIBLING_FILE_SHA256")
    if (
        type(family_links) is not dict
        or family.get("PRIMARY_RESULT_SHA256") != PER_T_SOURCE_SHA256
        or family_links.get(PER_T_SOURCE_PATH) != PER_T_SOURCE_SHA256
        or family_links.get(SOURCE_METHOD_PATH) != SOURCE_METHOD_SHA256
    ):
        raise EvidenceValidationError("fixed Family does not bind the pinned per-T source")
    if (
        per_t_source.get("TASK_ID") != "B649_K20_MIN_S2_SHARED_NEIGHBOR_DEFICIT_CERTIFICATE_R1"
        or per_t_source.get("SOURCE_SHA256") != SOURCE_METHOD_SHA256
        or per_t_source.get("TERM_COLUMNS") != SOURCE_TERM_COLUMNS
    ):
        raise EvidenceValidationError("pinned method or BOUND column identity mismatch")

    active = per_t_source.get("ACTIVE_CERTIFICATES")
    if type(active) is not dict or PROFILE not in active or type(active[PROFILE]) is not dict:
        raise EvidenceValidationError("target profile is absent from the pinned active certificate")
    certificate = active[PROFILE]
    if certificate.get("PROFILE_ID") != PROFILE:
        raise EvidenceValidationError("per-T certificate profile identity mismatch")
    source_terms = certificate.get("ALL_T_TERMS")
    if type(source_terms) is not list:
        raise EvidenceValidationError("per-T source rows are missing")
    if len(source_terms) != EXPECTED_OLD_TERM_COUNT:
        raise EvidenceValidationError("per-T source row count mismatch")

    term_values: list[tuple[int, int]] = []
    for row in source_terms:
        if type(row) is not list or len(row) != len(SOURCE_TERM_COLUMNS):
            raise EvidenceValidationError("per-T source row shape mismatch")
        t_value = row[0]
        bound_value = row[SOURCE_COLUMN_INDEX]
        if not _exact_int(t_value) or not _exact_int(bound_value):
            raise EvidenceValidationError("per-T source T and BOUND values must be integers")
        term_values.append((t_value, bound_value))
    if [t_value for t_value, _ in term_values] != list(range(22, OLD_CAP + 1)):
        raise EvidenceValidationError("per-T source range is not the original 22..265 range")

    old_bound = max(bound for _, bound in term_values)
    old_argmax = [t_value for t_value, bound in term_values if bound == old_bound]
    new_terms = [row for row in source_terms if row[0] <= T_CAP]
    new_bound = max(row[SOURCE_COLUMN_INDEX] for row in new_terms)
    new_argmax = [row[0] for row in new_terms if row[SOURCE_COLUMN_INDEX] == new_bound]
    term_digest = _source_digest(new_terms)

    if (
        old_bound != EXPECTED_OLD_ROW_BOUND
        or old_argmax != [OLD_CAP]
        or len(new_terms) != EXPECTED_TERM_COUNT
        or new_bound != EXPECTED_NEW_ROW_BOUND
        or new_argmax != [EXPECTED_ARGMAX_NEW_T]
        or old_bound - new_bound != EXPECTED_ROW_DELTA
        or term_digest != EXPECTED_TERM_DIGEST
    ):
        raise EvidenceValidationError("recomputed source bounds do not match accepted evidence")

    family_bounds = family.get("COMPLETE_PROFILE_BOUNDS")
    if type(family_bounds) is not list:
        raise EvidenceValidationError("fixed Family profile bound summary is missing")
    target_bounds = [
        row[1]
        for row in family_bounds
        if type(row) is list and len(row) == 2 and row[0] == PROFILE
    ]
    if target_bounds != [old_bound]:
        raise EvidenceValidationError("fixed Family target bound differs from per-T maximum")

    proof = {
        "CORE_CAPACITIES": "(0^2,1^10,3,5)",
        "Y_RANGE": [0, 6],
        "CORE_ZERO_EDGES": "18-2*y",
        "ZERO_ZERO_EDGES": "9+y",
        "CORE_COMPLEMENT_EDGES": "25-y",
        "INDEPENDENT_CCZ_BOUND": (
            "I_CCZ >= 6*(25-y)-sum_c a_c*(1+r_c+a_c)"
        ),
        "CORRECTION_TERM_BOUND": (
            "sum_c a_c*(1+r_c+a_c) <= 3*(18-2*y)+52"
        ),
        "SIMPLIFIED_FLOOR": "6*(25-y)-[3*(18-2*y)+52]=44",
        "COUNT_IDENTITY": "T+I=295",
        "CAP_DERIVATION": "T<=295-44=251",
        "NO_DOUBLE_COUNTING_REASON": (
            "T terms and independent CCZ witnesses are disjoint event classes; "
            "the independent CCZ count excludes witnesses already represented by T, "
            "so adding T and I_CCZ counts each witness once."
        ),
    }
    provenance = {
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_RESULT_PATH": FAMILY_RESULT_PATH,
        "FROZEN_RESULT_SHA256": FAMILY_RESULT_SHA256,
        "SOURCE_INPUT_PATH": PER_T_SOURCE_PATH,
        "SOURCE_INPUT_SHA256": PER_T_SOURCE_SHA256,
        "SOURCE_METHOD": SOURCE_METHOD_ID,
        "SOURCE_METHOD_PATH": SOURCE_METHOD_PATH,
        "SOURCE_METHOD_SHA256": SOURCE_METHOD_SHA256,
        "SOURCE_COLUMN": SOURCE_COLUMN,
        "SOURCE_COLUMN_INDEX": SOURCE_COLUMN_INDEX,
        "LINEAGE": "E6FEE5EB_FIXED_FAMILY_ORIGINAL_S4_S5_PER_T_BOUND",
    }
    historical_status = {
        "MATHEMATICS": "ACCEPTED",
        "MATH_JUDGE_DEPTH": "FULL",
        "HISTORICAL_MATH_RESOURCE": "FAIL",
        "NEW_IMPLEMENTATION": "SELF_CHECK_ONLY",
        "NEW_ARTIFACT_JUDGE": "NOT_RUN",
        "FULL_FAMILY_CLOSURE": "NOT_CLAIMED",
        "GLOBAL_OPTIMUM": "NOT_CLAIMED",
    }
    resource = {
        "VERDICT": "PASS",
        "NICE_PRIORITY": 15,
        "WORKERS": 1,
        "SOLVER": "NOT_USED",
        "FULL_FAMILY_LEDGER_REPLAY": "NOT_RUN",
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_SELF_CHECK",
        "PROFILE": PROFILE,
        "PROFILE_UPDATES": [[PROFILE, old_bound, new_bound]],
        "PROVENANCE": provenance,
        "I_FLOOR": 44,
        "W": 829,
        "T_CAP": T_CAP,
        "OLD_CAP": max(t_value for t_value, _ in term_values),
        "OLD_ROW_BOUND": old_bound,
        "NEW_ROW_BOUND": new_bound,
        "ROW_DELTA": old_bound - new_bound,
        "OLD_TERM_COUNT": len(source_terms),
        "TERM_COUNT": len(new_terms),
        "ARGMAX_NEW_T": new_argmax[0],
        "TERM_DIGEST": term_digest,
        "PROOF": proof,
        "HISTORICAL_STATUS": historical_status,
        "NEW_RESOURCE_VERDICT": "PASS",
        "RESOURCE": resource,
    }


def _assert_same_typed_value(actual: object, expected: object, path: str = "result") -> None:
    if type(actual) is not type(expected):
        raise EvidenceValidationError(f"wrong type at {path}")
    if type(expected) is dict:
        actual_map = actual
        expected_map = expected
        if set(actual_map) != set(expected_map):
            missing = set(expected_map) - set(actual_map)
            extra = set(actual_map) - set(expected_map)
            raise EvidenceValidationError(
                f"schema mismatch at {path}: missing={sorted(missing)!r}, extra={sorted(extra)!r}"
            )
        for key in expected_map:
            _assert_same_typed_value(actual_map[key], expected_map[key], f"{path}.{key}")
        return
    if type(expected) is list:
        actual_list = actual
        expected_list = expected
        if len(actual_list) != len(expected_list):
            raise EvidenceValidationError(f"list length mismatch at {path}")
        for index, (actual_item, expected_item) in enumerate(zip(actual_list, expected_list)):
            _assert_same_typed_value(actual_item, expected_item, f"{path}[{index}]")
        return
    if actual != expected:
        raise EvidenceValidationError(f"value mismatch at {path}")


def _reject_resource_fail_to_pass(payload: object) -> None:
    if type(payload) is not dict:
        return
    resource = payload.get("RESOURCE")
    if type(resource) is not dict:
        return
    if resource.get("VERDICT") == "PASS":
        nice_priority = resource.get("NICE_PRIORITY")
        workers = resource.get("WORKERS")
        if (
            not _exact_int(nice_priority)
            or nice_priority < 15
            or not _exact_int(workers)
            or workers != 1
            or resource.get("SOLVER") != "NOT_USED"
            or resource.get("FULL_FAMILY_LEDGER_REPLAY") != "NOT_RUN"
        ):
            raise EvidenceValidationError("resource failure cannot be reported as PASS")


def validate_evidence_adoption(payload: object | None = None) -> None:
    """Validate the saved artifact or a candidate payload against pinned inputs."""
    root = _repo_root()
    expected = _expected_payload(root)
    if payload is None:
        try:
            payload = json.loads(RESULT_PATH.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceValidationError("cannot read the evidence adoption result") from exc
    _reject_resource_fail_to_pass(payload)
    _assert_same_typed_value(payload, expected)


def main() -> int:
    try:
        validate_evidence_adoption()
    except EvidenceValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {PROFILE} evidence adoption matches pinned inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
