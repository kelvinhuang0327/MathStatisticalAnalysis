"""Independent, bounded integer check of frozen Certificate F; no research imports.

Read the formulas as specifications, never execute a donor module. Count local
events by selecting shared labels and extracting a coefficient from private-label
polynomials. Count incidences as explicit tuples. Rebuild the full T22..264
envelope using integer minimization and numerator ceiling. This checks conditional
arithmetic, not the inherited universal cap, partition, or other certificates.
Run with Python >=3.10; this standalone tool has no application dependencies.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import resource
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from itertools import combinations
from math import comb
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
HEAD = "83ddad7ade4ae286d12890efdbf3ea7768103d5e"
TREE = "8939ae0a9150e269bbdb787a75ceb699b0cc3bca"
DONOR_HEAD = "f2ad83b4e07571a6842ac301d336360cec805a6a"
DONOR_TREE = "0b089eb90884f14283679528be40295098a5d3ef"
DIRECTORY = "docs/research/matrix-native-results/"
COMPOSITE = DIRECTORY + "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
ARCHIVE = DIRECTORY + "b649-min-s2-six-row-existing-s4-family-authority-r1-sources/"
DONOR_NAME = "b649_k20_min_s2_current_owner_motif_exact_refinement_r1"
PROFILE = "66666555554411100000"
OUTPUT = ROOT / (DIRECTORY + "b649-min-s2-certificate-f-independent-arithmetic-r1-result.json")
JsonValue = str | int | float | bool | None | Sequence["JsonValue"] | Mapping[str, "JsonValue"]
JsonObject = Mapping[str, JsonValue]
TTerm = list[int]
Edge = tuple[int, int]
Support = tuple[int, ...]
IncidenceKey = tuple[int, int]
IncidenceRow = tuple[int, int, int, int, tuple[int, ...]]


class CertificateFInput(TypedDict):
    PROFILE_ID: str
    D: list[int]
    TRIANGLE_CAP: int
    LOAD_BEARING_T: int
    S4_BASE: int
    MINIMUM_S2_PREMISES: JsonObject
    S4_RULE: str
    ALL_T_TERMS: list[TTerm]
    G: list[int]
    TERM_COLUMNS: list[str]
    DEGREE_FLOOR: JsonObject
    INCIDENCE_FLOOR: JsonObject
    OLD_ROUTE_B_S4_FLOOR: int
    NEW_S4_FLOOR: int
    OLD_INTEGER_CREDIT: int
    NEW_INTEGER_CREDIT: int
    EXACT_ADDITIONAL_CREDIT: int
    CAP_OLD_BOUND: int
    CAP_NEW_BOUND: int
    OLD_PROFILE_BOUND: int
    CERTIFIED_PROFILE_BOUND: int
    RETAINED_LOWER_T_COUNT: int
    RETAINED_LOWER_T_MAX: int
    RETAINED_TERMS_SHA256: str
    CAP_SOURCE_IDENTITY: JsonObject


class RealizationState(TypedDict):
    realization: list[list[list[int]]]


class RowUpdateInput(TypedDict):
    BEFORE: RealizationState
    AFTER: RealizationState


class CompositeInput(TypedDict):
    CERTIFICATE_F: CertificateFInput
    ROW_UPDATE: RowUpdateInput
    INCUMBENT: int
    FAMILY_BOUND_AFTER: int
    GAP_TO_INCUMBENT: int
    CERTIFICATES_COMPOSED: int


class IncidenceIdentity(TypedDict):
    TABLE: list[list[int]]
    TABLE_SHA256: str


class EquivalentIncidenceIdentity(TypedDict):
    TABLE_SHA256: str


class OwnerSupportRealization(TypedDict):
    PROFILE_ID: str
    TRIANGLES: int
    J: int
    R: int
    B: int
    MOTIFS_K_D_P_C_A_D1_P1: list[int]
    EXACT_S4_FROM_PINNED_LOCAL_TABLE: int


class DonorInput(TypedDict):
    INCIDENCE_IDENTITY: IncidenceIdentity
    EQUIVALENT_INCIDENCE_IDENTITY: EquivalentIncidenceIdentity
    OWNER_SUPPORT_REALIZATION: OwnerSupportRealization
    MODULE_PROVENANCE: Mapping[str, str]
    PROOF: str


class FloorInfo(TypedDict):
    DEGREE_FLOOR: JsonObject
    INCIDENCE_FLOOR: JsonObject


class FormulaSourceIdentity(TypedDict):
    PATH: str
    HEAD: str
    SHA256: str
    EXECUTED: bool


class Mismatch(TypedDict):
    LOCATION: str
    RECOUNTED: JsonValue
    FROZEN: JsonValue


class OwnerSupportResult(TypedDict):
    PROFILE_ID: str
    TRIANGLES: int
    J: int
    R: int
    B: int
    MOTIFS_K_D_P_C_A_D1_P1: list[int]
    EXACT_S4_FROM_PINNED_LOCAL_TABLE: int
    STATUS: str
    QUARTETS_IN_ONE_FIXED_REALIZATION: int
    UNIVERSAL_CAP_REPROVED: bool


class IncidenceCheckReport(TypedDict):
    STATUS: str
    LOCAL_CASES: int
    PRIMITIVE_TABLE_SHA256: str
    EQUIVALENT_TABLE_SHA256: str
    LOCAL_WEIGHTS_RECOUNTED: list[int]
    OWNER_REALIZATION: OwnerSupportResult


class ArithmeticReport(TypedDict):
    TASK_STATUS: str
    INDEPENDENT_ARITHMETIC_RECOUNT: str
    SCIENTIFIC_CLAIM_SUPPORTED: str


class DataReport(ArithmeticReport):
    FORMULA_OR_APPLICABILITY_INCONSISTENCY: str
    FROZEN_INPUT_REPRODUCTION: str
    T_TERMS_RECOUNTED: JsonObject
    REFERENCE_SCOPE_CAVEAT: JsonObject
    INCIDENCE_CHECK: IncidenceCheckReport
    INTEGER_ARITHMETIC_RESULT: JsonObject
    MISMATCHES: list[Mismatch]
    PRESERVED_SCIENTIFIC_BASELINE: JsonObject
    UNVERIFIED_ASSUMPTIONS: list[str]


class ExecutionReport(TypedDict, total=False):
    CPU_LIMIT_SECONDS: int
    CPU_BOUND_PROCESSES: int
    VERIFIER_CPU_NANOSECONDS: int
    PYTHON: str
    PYTHON_EXECUTABLE: str
    RESEARCH_IMPORTS: int
    SOLVER_CALLS: int
    OUTCOME_ENUMERATIONS: int
    TOTAL_TESTS_AND_VERIFICATION_CPU_NANOSECONDS: int
    COMMAND: str
    FINAL_EXIT_STATUS: int


class CertificateSourceIdentity(TypedDict):
    PROFILE_ID: str
    COMPOSITE_JSON_POINTER: str
    DONOR_JSON_POINTER: str
    DONOR_HEAD: str
    DONOR_TREE: str
    FROZEN_INPUT_SHA256: dict[str, str]
    FORMULA_SOURCES: list[FormulaSourceIdentity]


class VerificationReport(DataReport):
    TASK_ID: str
    JUDGE_MODE: str
    FROZEN_SOURCE_HEAD_AND_TREE: dict[str, str]
    CERTIFICATE_F_SOURCE_IDENTITY: CertificateSourceIdentity
    FORMULA_INDEPENDENCE: dict[str, JsonValue]
    EXECUTION: ExecutionReport
    RESULT_LOCATOR: str
    WORKSPACE: str
    CLEANUP_DISPOSITION: str
    IMPLEMENTATION_SHA256: dict[str, str]
    PRODUCTION_MUTATION: str
    RUNTIME_TRANSITION_OCCURRED: bool
    HEAVY_PROCESS_STARTED: str
    REMOTE_WRITE: str
    ORIGINAL_RESEARCH_FILES_MODIFIED: bool
    REMAINING_TASK_MODEL: dict[str, str]


class FocusedTestMetadata(TypedDict):
    STATUS: str
    TESTS_RUN: int
    FAILURES: int
    ERRORS: int
    RUNNER: str
    PATH: str


class FocusedVerificationReport(VerificationReport):
    FOCUSED_TESTS: FocusedTestMetadata


class FailureReport(ArithmeticReport):
    FROZEN_INPUT_REPRODUCTION: str
    FORMULA_OR_APPLICABILITY_INCONSISTENCY: str
    ERROR: str
    PRODUCTION_MUTATION: str
    HEAVY_PROCESS_STARTED: str


Report = VerificationReport | FocusedVerificationReport | FailureReport


PINS: dict[str, str] = {
    COMPOSITE: "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f",
    ARCHIVE + "s4-result.json":
        "e376c3c15a767bdc75fe937f8ad36adf2ae94cc705628caccfab7f655c55852c",
    ARCHIVE + "s4-source.py.txt":
        "1621262ae38fefcad112c30788c791e258be1eb5f8f2eea3dc328e3e7d6e8f09",
    ARCHIVE + "s4-tests.py.txt":
        "8e7d1dbede49bf3b47f816b40912d7f2b017ca6a1865bf87b7f16b6889028a70",
    ARCHIVE + "five-row-fresh-judge.md":
        "ebbbfe22326ea8d49ab27f77c44bb7245c44b90fdbc87afbd9dde7ae1e88407b",
}
FORMULA_SOURCES: dict[str, str] = {
    "b649_k20_min_s2_topw12_split_cap_certificate_r1.py":
        "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784",
    "b649_k20_min_s2_higher_order_closure_r2.py":
        "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45",
    "b649_k20_min_s2_resolved_above_cursor_owner_chase_r20.py":
        "b63081af598a6366ab9989f00f3e269052e8edbc41956a0771941dc03891b74e",
    "b649_k20_min_s2_owner_66655555555440000000_motif_r1.py":
        "33ba11cddd498f55019d708901e1a387316e23eecd4a9c3613dfd72268e56234",
    "b649_k20_min_s2_three_motif_complete_family_integration_r1.py":
        "7aacb00b3c9ff247c9cdb2d00faacd5ea2a84f3535b3e595b3bccfd5dbb91178",
}


def json_object(value: JsonValue, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise FrozenInputError("JSON object shape: " + label)
    return cast(JsonObject, value)


def parse_json_object(raw: bytes, label: str) -> JsonObject:
    decoded: object = json.loads(raw)
    if not isinstance(decoded, dict):
        raise FrozenInputError("JSON object shape: " + label)
    # JSON objects have string keys and json.loads restricts values to JSON data.
    return cast(JsonObject, decoded)


def required_field(value: JsonObject, key: str, label: str) -> JsonValue:
    if key not in value:
        raise FrozenInputError("missing JSON field: " + label + "." + key)
    return value[key]


def mapping_field(value: object, key: str, label: str) -> JsonValue:
    if not isinstance(value, Mapping):
        raise FrozenInputError("JSON object shape: " + label)
    mapping = cast(Mapping[str, JsonValue], value)
    if key not in mapping:
        raise FrozenInputError("missing JSON field: " + label + "." + key)
    return mapping[key]


def object_field(value: JsonObject, key: str, label: str) -> JsonObject:
    return json_object(required_field(value, key, label), label + "." + key)


def string_value(value: JsonValue, label: str) -> str:
    if not isinstance(value, str):
        raise FrozenInputError("string field shape: " + label)
    return value


def integer_value(value: JsonValue, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise FrozenInputError("integer field shape: " + label)
    return value


def integer_list(value: JsonValue, label: str) -> list[int]:
    if not isinstance(value, list):
        raise FrozenInputError("integer list shape: " + label)
    return [integer_value(item, label) for item in value]


def string_list(value: JsonValue, label: str) -> list[str]:
    if not isinstance(value, list):
        raise FrozenInputError("string list shape: " + label)
    return [string_value(item, label) for item in value]


def integer_table(value: JsonValue, label: str) -> list[TTerm]:
    if not isinstance(value, list):
        raise FrozenInputError("integer table shape: " + label)
    return [integer_list(row, label) for row in value]


def support_groups(value: JsonValue, label: str) -> list[list[int]]:
    if not isinstance(value, list):
        raise FrozenInputError("support groups shape: " + label)
    return [integer_list(support, label) for support in value]


def realization_value(value: JsonValue, label: str) -> list[list[list[int]]]:
    if not isinstance(value, list) or len(value) != 2:
        raise FrozenInputError("realization shape: " + label)
    return [support_groups(value[0], label), support_groups(value[1], label)]


def certificate_input(value: JsonValue) -> CertificateFInput:
    raw = json_object(value, "CERTIFICATE_F")
    label = "CERTIFICATE_F"
    return {
        "PROFILE_ID": string_value(required_field(raw, "PROFILE_ID", label), label),
        "D": integer_list(required_field(raw, "D", label), label + ".D"),
        "TRIANGLE_CAP": integer_value(required_field(raw, "TRIANGLE_CAP", label), label),
        "LOAD_BEARING_T": integer_value(required_field(raw, "LOAD_BEARING_T", label), label),
        "S4_BASE": integer_value(required_field(raw, "S4_BASE", label), label),
        "MINIMUM_S2_PREMISES": object_field(raw, "MINIMUM_S2_PREMISES", label),
        "S4_RULE": string_value(required_field(raw, "S4_RULE", label), label),
        "ALL_T_TERMS": integer_table(required_field(raw, "ALL_T_TERMS", label), label),
        "G": integer_list(required_field(raw, "G", label), label + ".G"),
        "TERM_COLUMNS": string_list(required_field(raw, "TERM_COLUMNS", label), label),
        "DEGREE_FLOOR": object_field(raw, "DEGREE_FLOOR", label),
        "INCIDENCE_FLOOR": object_field(raw, "INCIDENCE_FLOOR", label),
        "OLD_ROUTE_B_S4_FLOOR": integer_value(
            required_field(raw, "OLD_ROUTE_B_S4_FLOOR", label), label
        ),
        "NEW_S4_FLOOR": integer_value(required_field(raw, "NEW_S4_FLOOR", label), label),
        "OLD_INTEGER_CREDIT": integer_value(
            required_field(raw, "OLD_INTEGER_CREDIT", label), label
        ),
        "NEW_INTEGER_CREDIT": integer_value(
            required_field(raw, "NEW_INTEGER_CREDIT", label), label
        ),
        "EXACT_ADDITIONAL_CREDIT": integer_value(
            required_field(raw, "EXACT_ADDITIONAL_CREDIT", label), label
        ),
        "CAP_OLD_BOUND": integer_value(required_field(raw, "CAP_OLD_BOUND", label), label),
        "CAP_NEW_BOUND": integer_value(required_field(raw, "CAP_NEW_BOUND", label), label),
        "OLD_PROFILE_BOUND": integer_value(
            required_field(raw, "OLD_PROFILE_BOUND", label), label
        ),
        "CERTIFIED_PROFILE_BOUND": integer_value(
            required_field(raw, "CERTIFIED_PROFILE_BOUND", label), label
        ),
        "RETAINED_LOWER_T_COUNT": integer_value(
            required_field(raw, "RETAINED_LOWER_T_COUNT", label), label
        ),
        "RETAINED_LOWER_T_MAX": integer_value(
            required_field(raw, "RETAINED_LOWER_T_MAX", label), label
        ),
        "RETAINED_TERMS_SHA256": string_value(
            required_field(raw, "RETAINED_TERMS_SHA256", label), label
        ),
        "CAP_SOURCE_IDENTITY": object_field(raw, "CAP_SOURCE_IDENTITY", label),
    }


def composite_input(value: JsonValue) -> CompositeInput:
    raw = json_object(value, "composite input")
    row_update = object_field(raw, "ROW_UPDATE", "composite input")
    before = object_field(row_update, "BEFORE", "ROW_UPDATE")
    after = object_field(row_update, "AFTER", "ROW_UPDATE")
    return {
        "CERTIFICATE_F": certificate_input(
            required_field(raw, "CERTIFICATE_F", "composite input")
        ),
        "ROW_UPDATE": {
            "BEFORE": {
                "realization": realization_value(
                    required_field(before, "realization", "ROW_UPDATE.BEFORE"),
                    "ROW_UPDATE.BEFORE.realization",
                )
            },
            "AFTER": {
                "realization": realization_value(
                    required_field(after, "realization", "ROW_UPDATE.AFTER"),
                    "ROW_UPDATE.AFTER.realization",
                )
            },
        },
        "INCUMBENT": integer_value(
            required_field(raw, "INCUMBENT", "composite input"), "INCUMBENT"
        ),
        "FAMILY_BOUND_AFTER": integer_value(
            required_field(raw, "FAMILY_BOUND_AFTER", "composite input"), "FAMILY_BOUND_AFTER"
        ),
        "GAP_TO_INCUMBENT": integer_value(
            required_field(raw, "GAP_TO_INCUMBENT", "composite input"), "GAP_TO_INCUMBENT"
        ),
        "CERTIFICATES_COMPOSED": integer_value(
            required_field(raw, "CERTIFICATES_COMPOSED", "composite input"),
            "CERTIFICATES_COMPOSED",
        ),
    }


def donor_input(value: JsonValue) -> DonorInput:
    raw = json_object(value, "donor input")
    incidence = object_field(raw, "INCIDENCE_IDENTITY", "donor input")
    equivalent = object_field(raw, "EQUIVALENT_INCIDENCE_IDENTITY", "donor input")
    owner = object_field(raw, "OWNER_SUPPORT_REALIZATION", "donor input")
    provenance = object_field(raw, "MODULE_PROVENANCE", "donor input")
    return {
        "INCIDENCE_IDENTITY": {
            "TABLE": integer_table(required_field(incidence, "TABLE", "INCIDENCE_IDENTITY"),
                                    "INCIDENCE_IDENTITY.TABLE"),
            "TABLE_SHA256": string_value(
                required_field(incidence, "TABLE_SHA256", "INCIDENCE_IDENTITY"),
                "INCIDENCE_IDENTITY.TABLE_SHA256",
            ),
        },
        "EQUIVALENT_INCIDENCE_IDENTITY": {
            "TABLE_SHA256": string_value(
                required_field(equivalent, "TABLE_SHA256", "EQUIVALENT_INCIDENCE_IDENTITY"),
                "EQUIVALENT_INCIDENCE_IDENTITY.TABLE_SHA256",
            )
        },
        "OWNER_SUPPORT_REALIZATION": {
            "PROFILE_ID": string_value(
                required_field(owner, "PROFILE_ID", "OWNER_SUPPORT_REALIZATION"),
                "OWNER_SUPPORT_REALIZATION.PROFILE_ID",
            ),
            "TRIANGLES": integer_value(
                required_field(owner, "TRIANGLES", "OWNER_SUPPORT_REALIZATION"),
                "OWNER_SUPPORT_REALIZATION.TRIANGLES",
            ),
            "J": integer_value(required_field(owner, "J", "OWNER_SUPPORT_REALIZATION"),
                               "OWNER_SUPPORT_REALIZATION.J"),
            "R": integer_value(required_field(owner, "R", "OWNER_SUPPORT_REALIZATION"),
                               "OWNER_SUPPORT_REALIZATION.R"),
            "B": integer_value(required_field(owner, "B", "OWNER_SUPPORT_REALIZATION"),
                               "OWNER_SUPPORT_REALIZATION.B"),
            "MOTIFS_K_D_P_C_A_D1_P1": integer_list(
                required_field(owner, "MOTIFS_K_D_P_C_A_D1_P1", "OWNER_SUPPORT_REALIZATION"),
                "OWNER_SUPPORT_REALIZATION.MOTIFS_K_D_P_C_A_D1_P1",
            ),
            "EXACT_S4_FROM_PINNED_LOCAL_TABLE": integer_value(
                required_field(owner, "EXACT_S4_FROM_PINNED_LOCAL_TABLE",
                               "OWNER_SUPPORT_REALIZATION"),
                "OWNER_SUPPORT_REALIZATION.EXACT_S4_FROM_PINNED_LOCAL_TABLE",
            ),
        },
        "MODULE_PROVENANCE": {
            key: string_value(value, "MODULE_PROVENANCE." + key)
            for key, value in provenance.items()
        },
        "PROOF": string_value(required_field(raw, "PROOF", "donor input"), "PROOF"),
    }


class VerificationError(ValueError):
    """Frozen identity or mathematical applicability failed closed."""


class FrozenInputError(VerificationError):
    """The specified frozen inputs could not be fully reproduced."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest(value: JsonValue) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def bind(raw: bytes, expected: str, label: str) -> bytes:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise FrozenInputError("input identity: " + label)
    return raw


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)


def load_inputs(
    root: Path = ROOT,
) -> tuple[CompositeInput, DonorInput, list[FormulaSourceIdentity]]:
    require(git(root, "rev-parse", "HEAD").decode().strip() == HEAD, "frozen HEAD")
    for ref, tree in ((HEAD, TREE), (DONOR_HEAD, DONOR_TREE)):
        require(git(root, "rev-parse", ref + "^{tree}").decode().strip() == tree,
                "frozen tree: " + ref)
    blobs: dict[str, bytes] = {}
    for path, pin in PINS.items():
        raw = bind(git(root, "show", HEAD + ":" + path), pin, path)
        require((root / path).read_bytes() == raw, "working input differs: " + path)
        blobs[path] = raw
    composite_json = parse_json_object(blobs[COMPOSITE], COMPOSITE)
    donor_json = parse_json_object(blobs[ARCHIVE + "s4-result.json"], ARCHIVE + "s4-result.json")
    require(composite_json["CERTIFICATE_F"] == donor_json["OWNER_CERTIFICATE"],
            "F/donor equality")
    require(composite_json["DONOR_RESULT_SHA256"] == PINS[ARCHIVE + "s4-result.json"],
            "donor digest metadata")
    for name, path in (
        ("s4-result.json", DIRECTORY + DONOR_NAME.replace("_", "-") + "-result.json"),
        ("s4-source.py.txt", "src/lottolab/research/" + DONOR_NAME + ".py"),
        ("s4-tests.py.txt", "tests/unit/test_" + DONOR_NAME + ".py"),
    ):
        require(git(root, "show", DONOR_HEAD + ":" + path) == blobs[ARCHIVE + name],
                "archive/donor Git identity: " + name)
    proof = ast.get_docstring(ast.parse(blobs[ARCHIVE + "s4-source.py.txt"]), clean=False)
    require(proof == donor_json["PROOF"], "frozen formula prose")
    identities: list[FormulaSourceIdentity] = []
    provenance = object_field(donor_json, "MODULE_PROVENANCE", "donor input")
    for name, pin in FORMULA_SOURCES.items():
        path = "src/lottolab/research/" + name
        require(provenance[path] == pin, "formula provenance: " + path)
        raw = bind(git(root, "show", DONOR_HEAD + ":" + path), pin, path)
        shared = name not in (
            "b649_k20_min_s2_owner_66655555555440000000_motif_r1.py",
            "b649_k20_min_s2_three_motif_complete_family_integration_r1.py",
        )
        if shared:
            require(git(root, "show", HEAD + ":" + path) == raw, "shared formula: " + path)
            require((root / path).read_bytes() == raw, "working formula: " + path)
        identities.append({"PATH": path, "HEAD": HEAD if shared else DONOR_HEAD,
                           "SHA256": pin, "EXECUTED": False})
    judge = blobs[ARCHIVE + "five-row-fresh-judge.md"].decode()
    require("T22..238 covers217 entries" in judge, "217-term reference attribution")
    return composite_input(composite_json), donor_input(donor_json), identities


def ceil_ratio(numerator: int, denominator: int) -> int:
    require(type(numerator) is int and type(denominator) is int and denominator > 0,
            "integer ceiling domain")
    quotient, remainder = divmod(numerator, denominator)
    return quotient + int(remainder != 0)


def local_outcomes(
    n: int,
    shared: Sequence[Sequence[int]],
    pool: int = 49,
    ticket_size: int = 6,
    selected: int = 7,
    threshold: int = 3,
) -> int:
    """Coefficient counting, independent of the donor's capped-state event DP.

    Each shared support is ONE label. Remaining labels are private to one ticket
    or outside all tickets. For each shared-label subset, multiply private-label
    selection polynomials subject to each ticket's hit threshold; extract degree
    selected and multiply by selected choices of special label.
    """
    require(all(len(set(s)) == len(s) and all(0 <= v < n for v in s) for s in shared),
            "shared support domain")
    private = [ticket_size - sum(v in s for s in shared) for v in range(n)]
    outside = pool - len(shared) - sum(private)
    require(min(private) >= 0 and outside >= 0, "local label capacity")
    total = 0
    for mask in range(1 << len(shared)):
        chosen = [s for i, s in enumerate(shared) if mask & (1 << i)]
        used = len(chosen)
        needed = [max(0, threshold - sum(v in s for s in chosen)) for v in range(n)]
        if used + sum(needed) > selected:
            continue
        polynomial = {used: 1}
        for capacity, minimum in zip(private, needed, strict=True):
            next_polynomial: dict[int, int] = {}
            for degree, coefficient in polynomial.items():
                for count in range(minimum, min(capacity, selected - degree) + 1):
                    power = degree + count
                    next_polynomial[power] = (
                        next_polynomial.get(power, 0) + coefficient * comb(capacity, count)
                    )
            polynomial = next_polynomial
        for degree, coefficient in polynomial.items():
            if 0 <= selected - degree <= outside:
                total += coefficient * comb(outside, selected - degree)
    return selected * total


def local_case(
    edges: set[Edge], support: Support | None
) -> tuple[int, int, int, int, int, tuple[int, ...]]:
    """Explicit incidence tuple sets on four vertices; no donor motif classes."""
    adjacent = [{b if a == v else a for a, b in edges if v in (a, b)} for v in range(4)]
    stars = {(v, leaves) for v in range(4)
             for leaves in combinations(sorted(adjacent[v]), 3)}
    open_pairs = [(v, (a, b)) for v in range(4)
                  for a, b in combinations(sorted(adjacent[v]), 2) if (a, b) not in edges]
    wedge_extensions = {(v, pair, x) for v, pair in open_pairs
                        for x in adjacent[v] - set(pair)}
    support_vertices: Support = support if support is not None else ()
    support_extensions = {(v, x) for v in support_vertices for x in adjacent[v]
                          if x not in support_vertices}
    degrees = sorted(map(len, adjacent))
    k, diamond = int(degrees == [3, 3, 3, 3]), int(degrees == [2, 2, 3, 3])
    paw, claw = int(degrees == [1, 2, 2, 3]), int(degrees == [1, 1, 1, 3])
    contained = int(support is not None)
    a, d1, p1 = contained * k, contained * diamond, contained * paw
    shadow: set[Edge] = set(combinations(support, 2)) if support else set()
    labels = ([support] if support else []) + sorted(edges - shadow)
    s4 = local_outcomes(4, labels)
    u, ell, b = len(stars), len(wedge_extensions), len(support_extensions)
    require(u == 4 * k + 2 * diamond + paw + claw, "local star identity")
    require(ell == 2 * diamond + 2 * paw + 3 * claw, "local open-wedge identity")
    require(b == 3 * a + 2 * d1 + p1, "local support identity")
    require(s4 == 679 * k - 231 * a + 112 * (diamond - d1), "local event weight")
    dropped = 56 * claw + 42 * d1 + 77 * p1
    slack = 56 * (p1 + claw)
    require(s4 == 231 * k + 112 * u - 56 * ell - 77 * b + dropped,
            "primitive incidence identity")
    require(s4 == 231 * k - 63 * a + 56 * (2 * u - ell - b) + slack,
            "equivalent incidence identity")
    require(4 * k >= u - ell and b >= 3 * a and min(dropped, slack) >= 0,
            "incidence inequality direction")
    return u, ell, b, s4, slack, (k, diamond, paw, claw, a, d1, p1)


def check_incidence() -> tuple[list[list[int]], list[list[int]], dict[IncidenceKey, IncidenceRow]]:
    primitive: list[list[int]] = []
    equivalent: list[list[int]] = []
    lookup: dict[IncidenceKey, IncidenceRow] = {}
    pairs = list(combinations(range(4), 2))
    for edge_mask in range(64):
        edges = {p for bit, p in enumerate(pairs) if edge_mask & (1 << bit)}
        supports = [None] + [s for s in combinations(range(4), 3)
                             if set(combinations(s, 2)) <= edges]
        for support in supports:
            mark = sum(1 << v for v in support) if support else 0
            u, ell, b, s4, slack, motifs = local_case(edges, support)
            primitive.append([edge_mask, mark, u, ell, b, s4])
            equivalent.append([edge_mask, mark, u, ell, b, s4, slack])
            lookup[edge_mask, mark] = (u, ell, b, s4, motifs)
    require(len(lookup) == len(primitive) == 96, "local legal-case completeness")
    return primitive, equivalent, lookup


def profile_statistics(degrees: Sequence[int]) -> tuple[list[int], int, int, int]:
    require(len(degrees) == 20 and all(type(d) is int and 0 <= d <= 6 for d in degrees)
            and sum(degrees) == 66, "minimum-S2 profile domain")
    g = [d + 6 for d in degrees]
    w = sum(comb(v, 2) for v in g)
    u = sum(comb(v, 3) for v in g)
    b = sum(d * (v - 2) for d, v in zip(degrees, g, strict=True))
    return g, w, u, b


def recount_terms(
    degrees: Sequence[int], cap: int = 264, base: int = 112
) -> tuple[list[TTerm], TTerm | None, FloorInfo | None]:
    """Find minimum permitted K and minimize event weight over contained K4s.

    T denotes total graph triangles, not the noncore count. Only the last term
    adopts the new incidence floor, exactly as specified by Certificate F.
    """
    g, w, u, b = profile_statistics(degrees)
    require(type(cap) is int and 22 <= cap <= w // 3, "triangle domain")
    require(type(base) is int and base >= 0, "S4 floor domain")
    a_cap = b // 3
    rebuilt: list[TTerm] = []
    old_cap: TTerm | None = None
    cap_info: FloorInfo | None = None
    for t in range(22, cap + 1):
        ow = w - 3 * t
        ell_cap = (max(g) - 2) * ow
        excess = u - ell_cap
        k = next(k for k in range(u // 4 + 2) if 4 * k >= excess)
        require(k == max(0, ceil_ratio(excess, 4)), "minimum K ceiling")
        a = min(k, a_cap)
        route_weight = min(448 * inside + 679 * (k - inside) for inside in range(a + 1))
        s4 = max(base, route_weight)
        # Constants are independently recounted in verify_data before comparison.
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        union_base = 372228640 - 63838600 + s3
        if t == cap:
            old_cap = [t, ceil_ratio(7 * union_base - 4 * s4, 7), k, a, s4, s3]
            constant = 112 * u - 56 * ell_cap - 77 * b
            degree_floor = max(0, 231 * k + constant)
            incidence_floor = max(0, 231 * k - 63 * a_cap + 56 * (2 * u - ell_cap - b))
            require(incidence_floor == degree_floor + 21 * (b % 3), "floor equivalence")
            s4 = max(s4, degree_floor, incidence_floor)
            a = a_cap
            cap_info = {
                "DEGREE_FLOOR": {"W": w, "J": u, "B": b, "OW": ow, "R_MAX": ell_cap,
                                 "K4_BOUND": k, "S4_CONSTANT": constant,
                                 "S4_CERTIFIED_FLOOR": degree_floor},
                "INCIDENCE_FLOOR": {"W": w, "U": u, "R": b, "OW": ow, "L_MAX": ell_cap,
                                    "K4_FLOOR": k, "A_MAX": a_cap,
                                    "S4_FLOOR": incidence_floor},
            }
        numerator = 7 * union_base - 4 * s4
        bound = ceil_ratio(numerator, 7)
        require(bound == union_base - (4 * s4) // 7 and 0 <= 7 * bound - numerator < 7,
                "credit rounding direction")
        rebuilt.append([t, bound, k, a, s4, s3])
    return rebuilt, old_cap, cap_info


def compare(
    actual: JsonValue, expected: JsonValue, label: str, mismatches: list[Mismatch]
) -> None:
    if actual != expected:
        mismatches.append({"LOCATION": label, "RECOUNTED": actual, "FROZEN": expected})


def check_realization(
    composite: CompositeInput,
    donor: DonorInput,
    lookup: dict[IncidenceKey, IncidenceRow],
    mismatches: list[Mismatch],
) -> OwnerSupportResult:
    """One supplied owner realization, not a family/partition replay."""
    before, after = composite["ROW_UPDATE"]["BEFORE"], composite["ROW_UPDATE"]["AFTER"]
    require(before["realization"] == after["realization"], "owner realization identity")
    triples, pairs = after["realization"]
    require(len(triples) == 22 and len(pairs) == 27, "22/27 label premise")
    edges: set[Edge] = set()
    support_sets: list[set[int]] = []
    d, capacity = [0] * 20, [0] * 20
    for support in triples + pairs:
        require(len(set(support)) == len(support) and all(type(v) is int and 0 <= v < 20
                                                        for v in support), "label support")
        require(len(support) in (2, 3), "support multiplicity")
        shadow = set(combinations(sorted(support), 2))
        require(not (edges & shadow), "pair linearity")
        edges.update(shadow)
        for v in support:
            capacity[v] += 1
            d[v] += int(len(support) == 3)
        if len(support) == 3:
            support_sets.append(set(support))
    require(capacity == [6] * 20 and ''.join(map(str, d)) == PROFILE, "owner capacity/profile")
    g, w, u, b = profile_statistics(d)
    adjacency = [{other for e in edges if v in e for other in e if other != v}
                 for v in range(20)]
    require(list(map(len, adjacency)) == g and len(edges) == 93, "shadow degree premise")
    triangles = sum(all(e in edges for e in combinations(vertices, 2))
                    for vertices in combinations(range(20), 3))
    ell = sum(len(adj - {a, c}) for adj in adjacency
              for a, c in combinations(sorted(adj), 2) if (a, c) not in edges)
    b_direct = sum(len(adjacency[v] - s) for s in support_sets for v in s)
    totals: list[int] = [0] * 4
    motifs: list[int] = [0] * 7
    for quartet in combinations(range(20), 4):
        edge_mask = sum(1 << bit for bit, (a, c) in enumerate(combinations(quartet, 2))
                        if (a, c) in edges)
        contained = [s for s in support_sets if s <= set(quartet)]
        require(len(contained) <= 1, "quartet has at most one triple support")
        mark = sum(1 << i for i, v in enumerate(quartet) if contained and v in contained[0])
        row = lookup[edge_mask, mark]
        totals = [a + c for a, c in zip(totals, row[:4], strict=True)]
        motifs = [a + c for a, c in zip(motifs, row[4], strict=True)]
    require(totals[:3] == [u, ell, b_direct] and b_direct == b, "global incidence additivity")
    require(0 <= triangles <= 264 and ell <= (max(g) - 2) * (w - 3 * triangles),
            "realized incidence bound direction")
    observed: dict[str, JsonValue] = {
        "PROFILE_ID": PROFILE,
        "TRIANGLES": triangles,
        "J": u,
        "R": ell,
        "B": b,
        "MOTIFS_K_D_P_C_A_D1_P1": motifs,
        "EXACT_S4_FROM_PINNED_LOCAL_TABLE": totals[3],
    }
    for key, value in observed.items():
        compare(value, mapping_field(donor["OWNER_SUPPORT_REALIZATION"], key,
                                    "OWNER_SUPPORT_REALIZATION"),
                "OWNER_REALIZATION." + key, mismatches)
    status = "FAIL" if any(m["LOCATION"].startswith("OWNER_REALIZATION.")
                           for m in mismatches) else "PASS"
    return {
        "PROFILE_ID": PROFILE,
        "TRIANGLES": triangles,
        "J": u,
        "R": ell,
        "B": b,
        "MOTIFS_K_D_P_C_A_D1_P1": motifs,
        "EXACT_S4_FROM_PINNED_LOCAL_TABLE": totals[3],
        "STATUS": status,
        "QUARTETS_IN_ONE_FIXED_REALIZATION": comb(20, 4),
        "UNIVERSAL_CAP_REPROVED": False,
    }


def verify_data(composite: CompositeInput, donor: DonorInput) -> DataReport:
    cert = composite["CERTIFICATE_F"]
    mismatches: list[Mismatch] = []
    require(cert["PROFILE_ID"] == PROFILE and cert["D"] == list(map(int, PROFILE)),
            "Certificate F profile")
    require(cert["TRIANGLE_CAP"] == cert["LOAD_BEARING_T"] == 264 and cert["S4_BASE"] == 112,
            "Certificate F applicability")
    require(cert["MINIMUM_S2_PREMISES"] == {
        "TRIPLE_LABELS": 22, "PAIR_LABELS": 27, "TICKET_CAPACITY": 6,
        "PAIR_LINEARITY": True,
        "AUTHORITY": "PINNED_COMPLETE_LEDGER_AND_VALIDATED_OWNER_SUPPORT_REALIZATION",
    }, "Certificate F minimum-S2 premises")
    require(cert["S4_RULE"] == "MAX(EXISTING, DEGREE, INCIDENCE); NEVER ADD OVERLAPPING FLOORS",
            "S4 adoption scope")
    primitive, equivalent, lookup = check_incidence()
    compare(primitive, donor["INCIDENCE_IDENTITY"]["TABLE"], "LOCAL_PRIMITIVE_TABLE", mismatches)
    compare(digest(primitive), donor["INCIDENCE_IDENTITY"]["TABLE_SHA256"],
            "LOCAL_PRIMITIVE_HASH", mismatches)
    compare(digest(equivalent), donor["EQUIVALENT_INCIDENCE_IDENTITY"]["TABLE_SHA256"],
            "LOCAL_EQUIVALENT_HASH", mismatches)
    # Recount the S1/S2/S3 constants from the same independent label counter.
    counts = {
        "SINGLE": local_outcomes(1, []), "DISJOINT_PAIR": local_outcomes(2, []),
        "OVERLAP_PAIR": local_outcomes(2, [(0, 1)]),
        "WEDGE": local_outcomes(3, [(0, 1), (0, 2)]),
        "PAIR_TRIANGLE": local_outcomes(3, [(0, 1), (0, 2), (1, 2)]),
        "CORE_TRIANGLE": local_outcomes(3, [(0, 1, 2)]),
    }
    expected = {"SINGLE": 18611432, "DISJOINT_PAIR": 107800, "OVERLAP_PAIR": 574000,
                "WEDGE": 2800, "PAIR_TRIANGLE": 20272, "CORE_TRIANGLE": 7000}
    compare(counts, expected, "INDEPENDENT_EVENT_CONSTANTS", mismatches)
    compare(20 * counts["SINGLE"], 372228640, "S1", mismatches)
    compare(93 * counts["OVERLAP_PAIR"] + 97 * counts["DISJOINT_PAIR"], 63838600,
            "S2", mismatches)
    compare(counts["PAIR_TRIANGLE"] - 3 * counts["WEDGE"], 11872, "S3_TRIANGLE", mismatches)
    compare(22 * (3 * counts["WEDGE"] - counts["CORE_TRIANGLE"]), 30800,
            "S3_CORE_CORRECTION", mismatches)
    # Pair linearity makes the chosen hit triples pair-disjoint on seven labels:
    # r*C(3,2) <= C(7,2), hence r<=7. Check the correction numerically for every r.
    for r in range(8):
        excess = r - comb(r, 2) + comb(r, 3) - int(r > 0)
        require(7 * excess >= 4 * comb(r, 4), "4/7 Bonferroni direction")
    rebuilt, old_cap, floor_info = recount_terms(cert["D"])
    if old_cap is None or floor_info is None:
        raise VerificationError("missing cap-term recount metadata")
    stored = cert["ALL_T_TERMS"]
    require(len(stored) == 243 and all(len(row) == 6 for row in stored),
            "integer T-term table schema")
    require([row[0] for row in stored] == list(range(22, 265)), "complete T-term domain")
    compare(cert["G"], [6 + d for d in cert["D"]], "GRAPH_DEGREES", mismatches)
    compare(cert["TERM_COLUMNS"], ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
            "TERM_COLUMNS", mismatches)
    for actual, frozen in zip(rebuilt, stored, strict=True):
        compare(actual, frozen, "T=" + str(actual[0]), mismatches)
    lower = rebuilt[:-1]
    aggregates: JsonObject = {
        "DEGREE_FLOOR": floor_info["DEGREE_FLOOR"],
        "INCIDENCE_FLOOR": floor_info["INCIDENCE_FLOOR"],
        "OLD_ROUTE_B_S4_FLOOR": old_cap[4], "NEW_S4_FLOOR": rebuilt[-1][4],
        "OLD_INTEGER_CREDIT": (4 * old_cap[4]) // 7,
        "NEW_INTEGER_CREDIT": (4 * rebuilt[-1][4]) // 7,
        "EXACT_ADDITIONAL_CREDIT": (4 * rebuilt[-1][4]) // 7 - (4 * old_cap[4]) // 7,
        "CAP_OLD_BOUND": old_cap[1], "CAP_NEW_BOUND": rebuilt[-1][1],
        "OLD_PROFILE_BOUND": max([old_cap[1]] + [row[1] for row in lower]),
        "CERTIFIED_PROFILE_BOUND": max(row[1] for row in rebuilt),
        "RETAINED_LOWER_T_COUNT": len(lower), "RETAINED_LOWER_T_MAX": max(row[1] for row in lower),
        "RETAINED_TERMS_SHA256": digest(lower),
    }
    for key, value in aggregates.items():
        compare(value, mapping_field(cert, key, "CERTIFICATE_F"),
                "CERTIFICATE_F." + key, mismatches)
    proof = cert["CAP_SOURCE_IDENTITY"]
    for key, value in {"ATTEMPT_INDEX": 2779, "PROFILE_IDS": [PROFILE], "WEDGE_COUNT": 833,
                       "TARGET_TRIANGLE_CAP": 264, "REFUTED_GRAPH_TRIANGLE_COUNT": 265,
                       "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 264,
                       "OPEN_WEDGE_CEILING_REFUTED": 833 - 3 * 265,
                       "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": 833 - 3 * 265 + 1}.items():
        compare(value, mapping_field(proof, key, "CAP_SOURCE_IDENTITY"),
                "CAP_SOURCE_ARITHMETIC." + key, mismatches)
    realization = check_realization(composite, donor, lookup, mismatches)
    return {
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY_WITH_REFERENCE_CAVEAT" if not mismatches
                       else "FAIL_FORMULA_OR_ARITHMETIC_MISMATCH",
        "INDEPENDENT_ARITHMETIC_RECOUNT": "PASS" if not mismatches else "FAIL",
        "FORMULA_OR_APPLICABILITY_INCONSISTENCY": "NONE" if not mismatches else "SEE_MISMATCHES",
        "FROZEN_INPUT_REPRODUCTION": "PASS",
        "T_TERMS_RECOUNTED": {
            "COUNT": len(rebuilt), "RANGE": [22, 264],
            "SIX_INTEGER_COLUMNS_PER_TERM": 6,
            "ALL_TERMS_SHA256": digest(rebuilt),
            "RETAINED_TERMS_SHA256": digest(lower),
            "SAMPLES": [row for row in rebuilt if row[0] in (22, 238, 263, 264)],
        },
        "REFERENCE_SCOPE_CAVEAT": {
            "STATUS": "217_TERM_ATTRIBUTION_MISMATCH",
            "217_TERMS_BELONG_TO": "Prior five-row Cap238 certificate, T22..238, Certificate E",
            "CERTIFICATE_F_ACTUAL_COUNT": 243,
            "F_T22_THROUGH_T238_PREFIX_RECOUNTED": 217,
            "CERTIFICATE_E_VERIFIED_BY_THIS_TASK": False,
            "SOURCE": ARCHIVE + "five-row-fresh-judge.md:19,31,45",
        },
        "INCIDENCE_CHECK": {"STATUS": "FAIL" if any(
                                m["LOCATION"].startswith(("LOCAL_", "OWNER_REALIZATION."))
                                for m in mismatches) else "PASS", "LOCAL_CASES": len(primitive),
                            "PRIMITIVE_TABLE_SHA256": digest(primitive),
                            "EQUIVALENT_TABLE_SHA256": digest(equivalent),
                            "LOCAL_WEIGHTS_RECOUNTED": sorted({r[-1] for r in primitive}),
                            "OWNER_REALIZATION": realization},
        "INTEGER_ARITHMETIC_RESULT": {**aggregates, "EVENT_CONSTANTS_RECOUNTED": counts,
            "MAXIMIZING_T": [
                row[0] for row in rebuilt
                if row[1] == aggregates["CERTIFIED_PROFILE_BOUND"]
            ],
            "ROUNDING": "ceil((7*(S1-S2+S3)-4*S4)/7); integer only",
            "DIRECTION_CHECKS": "K lower; A,L upper; S4 max; union upper",
        },
        "MISMATCHES": mismatches,
        "SCIENTIFIC_CLAIM_SUPPORTED": "NONE" if mismatches else
                                      "Certificate F's conditional T22..264 arithmetic and local "
                                      "incidence identities match the frozen certificate. "
                                      "No six-certificate VERIFIED verdict or strict winning "
                                      "outcome.",
        "PRESERVED_SCIENTIFIC_BASELINE": {"INCUMBENT": composite["INCUMBENT"],
            "SIX_ROW_FAMILY_UPPER_BOUND": composite["FAMILY_BOUND_AFTER"],
            "REMAINING_GAP": composite["GAP_TO_INCUMBENT"], "CERTIFICATES_COMPOSED": 6,
            "DONOR_JUDGE_STATUS": "SELF_CHECK_ONLY", "GLOBAL_K20_OPTIMUM": "UNKNOWN",
            "WHOLE_FAMILY_REPLAYED": False},
        "UNVERIFIED_ASSUMPTIONS": [
            "Universal triangle cap264 relies on inherited CP-SAT infeasibility; "
            "solver proof not rerun.",
            "Inherited S4>=112 existence theorem is accepted, not independently reproved here.",
            "Complete MIN-S2 partition/ledger and all other certificates, including Cap238's "
            "217 terms, are not revalidated; one fixed realization does not "
            "prove universal coverage.",
            "Global K20 optimality remains UNKNOWN; T256 theorem is outside this PR/task.",
        ],
    }


def cpu_limit() -> None:
    soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    new_soft = 120 if soft == resource.RLIM_INFINITY else min(soft, 120)
    new_hard = 120 if hard == resource.RLIM_INFINITY else min(hard, 120)
    resource.setrlimit(resource.RLIMIT_CPU, (min(new_soft, new_hard), new_hard))


def verify_frozen(root: Path = ROOT) -> VerificationReport:
    started = time.process_time_ns()
    try:
        composite, donor, sources = load_inputs(root)
    except VerificationError as exc:
        raise FrozenInputError(str(exc)) from exc
    report = verify_data(composite, donor)
    require(composite["INCUMBENT"] == 313263888 and composite["FAMILY_BOUND_AFTER"] == 313398920
            and composite["GAP_TO_INCUMBENT"] == 135032 and composite["CERTIFICATES_COMPOSED"] == 6,
            "scientific baseline identity")
    return {
        **report,
        "TASK_ID": "B649_MIN_S2_CERTIFICATE_F_INDEPENDENT_ARITHMETIC_R1",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FROZEN_SOURCE_HEAD_AND_TREE": {"HEAD": HEAD, "TREE": TREE},
        "CERTIFICATE_F_SOURCE_IDENTITY": {
            "PROFILE_ID": PROFILE,
            "COMPOSITE_JSON_POINTER": "/CERTIFICATE_F",
            "DONOR_JSON_POINTER": "/OWNER_CERTIFICATE",
            "DONOR_HEAD": DONOR_HEAD,
            "DONOR_TREE": DONOR_TREE,
            "FROZEN_INPUT_SHA256": PINS,
            "FORMULA_SOURCES": sources,
        },
        "FORMULA_INDEPENDENCE": {
            "DONOR_CODE_IMPORTED_OR_EXECUTED": False,
            "INTEGER_ONLY": True,
            "METHOD": "Shared-label subset and private-label polynomial "
                      "coefficient counts; explicit incidence tuple sets; integer finite "
                      "minimization for Route-B S4; independent numerator ceiling; frozen "
                      "results used only for comparison.",
        },
        "EXECUTION": {"CPU_LIMIT_SECONDS": 120, "CPU_BOUND_PROCESSES": 1,
            "VERIFIER_CPU_NANOSECONDS": time.process_time_ns() - started,
            "PYTHON": sys.version, "PYTHON_EXECUTABLE": sys.executable,
            "RESEARCH_IMPORTS": 0, "SOLVER_CALLS": 0, "OUTCOME_ENUMERATIONS": 0},
        "RESULT_LOCATOR": str(OUTPUT), "WORKSPACE": str(root), "CLEANUP_DISPOSITION": "RETAIN",
        "IMPLEMENTATION_SHA256": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in (
                "tools/verify_b649_min_s2_certificate_f_independent_arithmetic_r1.py",
                "tests/unit/test_b649_min_s2_certificate_f_independent_arithmetic_r1.py",
            )
        },
        "PRODUCTION_MUTATION": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": False,
        "HEAVY_PROCESS_STARTED": "NO",
        "REMOTE_WRITE": "NONE",
        "ORIGINAL_RESEARCH_FILES_MODIFIED": False,
        "REMAINING_TASK_MODEL": {
            "最強模型": "後續單一 family owner 的 exact improvement/證書改進研究。",
            "強模型": "已驗證數學結果的工程正確性整合。",
            "中弱模型": "固定證據的機械性記錄及發布。",
        },
    }


def failure_report(exc: Exception) -> FailureReport:
    missing = isinstance(exc, (FrozenInputError, OSError, subprocess.CalledProcessError,
                              KeyError, TypeError, json.JSONDecodeError))
    return {
        "TASK_STATUS": "UNABLE_TO_REPRODUCE_FROZEN_INPUT" if missing
                       else "FAIL_FORMULA_OR_APPLICABILITY_INCONSISTENCY",
        "INDEPENDENT_ARITHMETIC_RECOUNT": "NOT_COMPLETED" if missing else "FAIL",
        "FROZEN_INPUT_REPRODUCTION": "FAIL" if missing else "PASS",
        "FORMULA_OR_APPLICABILITY_INCONSISTENCY": "NOT_EVALUATED" if missing else str(exc),
        "SCIENTIFIC_CLAIM_SUPPORTED": "NONE", "ERROR": str(exc),
        "PRODUCTION_MUTATION": "NONE", "HEAVY_PROCESS_STARTED": "NO",
    }


def save_report(report: Report, path: Path = OUTPUT) -> None:
    # All input identities are checked again by load_inputs on each invocation.
    # Only this task's designated result path may be written.
    require(path.resolve() == OUTPUT.resolve(), "result write boundary")
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    cpu_limit()
    try:
        report = verify_frozen()
    except (VerificationError, OSError, subprocess.CalledProcessError, KeyError,
            TypeError, json.JSONDecodeError) as exc:
        report = failure_report(exc)
    if args.write_result:
        save_report(report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["INDEPENDENT_ARITHMETIC_RECOUNT"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
