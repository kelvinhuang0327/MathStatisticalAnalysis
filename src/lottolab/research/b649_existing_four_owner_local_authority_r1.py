"""Prospective four-owner overlay on the frozen seven-row B649 authority."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, replace
from itertools import pairwise, product
from math import comb
from pathlib import Path
from typing import Any, cast

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as seven

TASK_ID = "B649_EXISTING_FOUR_OWNER_LOCAL_AUTHORITY_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
)
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
SEVEN_ROW_FULL_DIGEST = "70e2c1bb28f223566cb54799fd1b325368b90d58c5fc5001cacfbba9d2996de6"
SEVEN_ROW_BOUNDS_DIGEST = "5ab591996b98daac3d14c1468970f8c0e7dd015e5b37d5445e2097bf9b59598a"
SEVEN_ROW_COUNT = 4_647
SEVEN_CERTIFICATE_COUNT = 7
INCUMBENT = 313_263_888
GLOBAL_S4_FLOOR = 112

EIGHT_HEAD = "c00cdb14cdfb7d0e0d57a4019c0306a0f5b29b7d"
EIGHT_TREE = "5ee9ef8c5ccd418bc9b1dcae97f169bf996a0b66"
EIGHT_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-eight-row-family-authority-r1-result.json"
)
EIGHT_RESULT_SHA256 = "404600c87162bbb1db4d82eefe1c07a925ba88ad204662d2e2a00a44f8ffc3f0"
EIGHT_SOURCE_PATH = "src/lottolab/research/b649_eight_row_family_authority_r1.py"
EIGHT_SOURCE_SHA256 = "80ae74274cfd216811318e346a66c437afd58053bf0fa4b9729ae26690768be8"
EIGHT_TEST_PATH = "tests/unit/test_b649_eight_row_family_authority_r1.py"
EIGHT_TEST_SHA256 = "dc0385dafa58123ead4d62abc9d96d6991beb23275125d356dd0c4238419f4df"
EIGHT_WORKTREE = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_EIGHT_ROW_FAMILY_AUTHORITY_R1"
)
EIGHT_BRANCH = "codex/b649-eight-row-family-authority-r1"
EIGHT_PROFILE = "66655555555521000000"
EIGHT_BOUND = 313_397_476
EIGHT_CAP = 264

T241_HEAD = "8c6e7bdd355cfee990e2d832be5f1e979640633d"
T241_TREE = "731337c55455fbc6bee24ab858dd2db2eb189b8f"
T241_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-tied-owner-core-zero-t241-bound-r1-result.json"
)
T241_RESULT_SHA256 = "6b1d346d9a5eac07a19a67201ec9fc5e4447c5c24cea1c913ab1aaf3882b5849"
T241_SOURCE_PATH = "src/lottolab/research/b649_min_s2_tied_owner_core_zero_t241_bound_r1.py"
T241_SOURCE_SHA256 = "72895234c6c011555cf4ef431f995f2f4a235c62ddee4697f96b51c23cb6d66f"
T241_TEST_PATH = "tests/unit/test_b649_min_s2_tied_owner_core_zero_t241_bound_r1.py"
T241_TEST_SHA256 = "83313e7442644f0d04aaaebe309d101994f6f2bab66c0a86afe90d21d6eddc9d"
T241_PROOF_SHA256 = "1e68078094edb9e69ac354235634043330a4ca484aa4cae3359a0ae55da5b151"

T240_HEAD = "2434d065eea9aa9c133f1c5d47e2fb99ae638e12"
T240_TREE = "18b7fde5c7dcc39d4d5f0354c2bb9aaaa6d700bc"
T240_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-tied-owner-zero-graph-t240-bound-r1-result.json"
)
T240_RESULT_SHA256 = "db28881ca4f642db38695235e0ce9e1d679179e27888d5dcc81264c55518c0b3"
T240_SOURCE_PATH = "src/lottolab/research/b649_min_s2_tied_owner_zero_graph_t240_bound_r1.py"
T240_SOURCE_SHA256 = "347a302649a4e2671b7c039fbb8a525a443bb49c41a0fb5ac86d52b50a01722b"
T240_TEST_PATH = "tests/unit/test_b649_min_s2_tied_owner_zero_graph_t240_bound_r1.py"
T240_TEST_SHA256 = "4d354a82de1cc08489c2c5f55958c3bb6bd49c9ab1712340d84de4ac3251634c"
T240_PROOF_SHA256 = "0bf1c99420d449f9a30bba040eeb628f9a43fc1cef1fad88bb39a6e5e39e9c76"

C235_PROFILE = "66655555555422000000"
C235_CAP = 235
C235_BOUND = 313_129_388
C235_PROOF_PATH = "docs/research/matrix-native-results/b649-min-s2-c235-full-profile-proof-r1.md"
C235_PROOF_SHA256 = "84df00423cb60e2dbbb4f89e2d5703bb15a5826816eed876de8d8b532d5eb56a"
C235_REPORT_THREAD = "01a132f3-6c00-7042-89ff-0f60a1b6fa52"
C235_REPORT_TURN = "01a132f3-9a57-74c0-8c95-7e2212c5ddd8"
C235_REPORT_ITEM = "msg_0178b51303703352016acd91cca0808191ba728af34c7cadf0"

RESULT_PATH = (
    "docs/research/matrix-native-results/b649-existing-four-owner-local-authority-r1-result.json"
)
ROOT = Path(__file__).resolve().parents[3]
Row = seven.Row

TARGET_SPECS: tuple[dict[str, Any], ...] = (
    {
        "profile_id": EIGHT_PROFILE,
        "before_bound": 313_398_532,
        "before_cap": 264,
        "after_bound": EIGHT_BOUND,
        "after_cap": EIGHT_CAP,
        "source_kind": "EIGHT_ROW_CANDIDATE",
    },
    {
        "profile_id": "66555555555531000000",
        "before_bound": 313_398_248,
        "before_cap": 265,
        "after_bound": 313_183_160,
        "after_cap": 241,
        "source_kind": "T241_DONOR",
    },
    {
        "profile_id": "66655555554441000000",
        "before_bound": 313_398_248,
        "before_cap": 265,
        "after_bound": 313_174_392,
        "after_cap": 240,
        "source_kind": "T240_DONOR",
    },
    {
        "profile_id": C235_PROFILE,
        "before_bound": 313_398_248,
        "before_cap": 265,
        "after_bound": C235_BOUND,
        "after_cap": C235_CAP,
        "source_kind": "C235_LOCAL_PROOF",
    },
)
TARGET_PROFILE_IDS = tuple(spec["profile_id"] for spec in TARGET_SPECS)
EXPECTED_AFTER_FAMILY = 313_398_144
EXPECTED_AFTER_OWNERS = ["66665555555331000000", "66665555555411100000"]
EXPECTED_NEXT_BOUND = 313_397_860
EXPECTED_NEXT_OWNERS = ["66665555554421100000"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_git(root: Path, *args: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    )
    return completed.stdout if binary else completed.stdout.decode().strip()


def committed_blob(root: Path, head: str, path: str) -> bytes:
    raw = run_git(root, "show", f"{head}:{path}", binary=True)
    require(type(raw) is bytes, f"Git blob was not bytes: {path}")
    return cast(bytes, raw)


def verify_identity(actual: Mapping[str, str], expected: Mapping[str, str]) -> None:
    require(dict(actual) == dict(expected), "source identity mismatch")


def verify_commit(root: Path, head: str, tree: str) -> None:
    require(run_git(root, "rev-parse", head) == head, "pinned HEAD mismatch")
    require(run_git(root, "rev-parse", f"{head}^{{tree}}") == tree, "pinned tree mismatch")


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(message) from exc
    require(type(value) is dict, message)
    return cast(dict[str, Any], value)


def require_hash(raw: bytes, expected: str, label: str) -> None:
    require(sha256(raw) == expected, f"{label} SHA256 mismatch")


def verify_frozen_source(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    raw = committed_blob(root, FROZEN_HEAD, FROZEN_RESULT_PATH)
    require_hash(raw, FROZEN_RESULT_SHA256, "frozen seven-row result")
    require((root / FROZEN_RESULT_PATH).read_bytes() == raw, "working frozen result differs")
    frozen = json_object(raw, "frozen seven-row result is invalid JSON")
    expected = {
        "HEAD": FROZEN_HEAD,
        "TREE": FROZEN_TREE,
        "RESULT_PATH": FROZEN_RESULT_PATH,
        "RESULT_SHA256": FROZEN_RESULT_SHA256,
    }
    return frozen, expected


def verify_eight_row_candidate(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_commit(root, EIGHT_HEAD, EIGHT_TREE)
    require(EIGHT_WORKTREE.is_dir(), "eight-row candidate worktree is absent")
    require(
        run_git(EIGHT_WORKTREE, "rev-parse", "HEAD") == EIGHT_HEAD
        and run_git(EIGHT_WORKTREE, "rev-parse", "HEAD^{tree}") == EIGHT_TREE,
        "eight-row candidate worktree identity mismatch",
    )
    require(
        run_git(EIGHT_WORKTREE, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "eight-row candidate worktree is not clean",
    )
    require(
        run_git(EIGHT_WORKTREE, "branch", "--show-current") == EIGHT_BRANCH,
        "eight-row candidate branch mismatch",
    )
    paths = (
        (EIGHT_RESULT_PATH, EIGHT_RESULT_SHA256),
        (EIGHT_SOURCE_PATH, EIGHT_SOURCE_SHA256),
        (EIGHT_TEST_PATH, EIGHT_TEST_SHA256),
    )
    inputs: dict[str, bytes] = {}
    for path, expected_sha in paths:
        raw = committed_blob(root, EIGHT_HEAD, path)
        require_hash(raw, expected_sha, f"eight-row {path}")
        require(
            (EIGHT_WORKTREE / path).read_bytes() == raw, f"eight-row working bytes differ: {path}"
        )
        inputs[path] = raw
    result = json_object(inputs[EIGHT_RESULT_PATH], "eight-row result is invalid JSON")
    require(
        result.get("TASK_ID") == "B649_EIGHT_ROW_FAMILY_AUTHORITY_R1"
        and result.get("PROFILE_ID") == EIGHT_PROFILE
        and result.get("PROOF_SCOPE") == "FULL_PROFILE"
        and result.get("NEW_OWNER_BOUND") == EIGHT_BOUND
        and result.get("T_CAP") == EIGHT_CAP
        and result.get("ROW_UPDATE", {}).get("BEFORE_BOUND") == 313_398_532
        and result.get("ROW_UPDATE", {}).get("AFTER_BOUND") == EIGHT_BOUND
        and result.get("ROW_UPDATE", {}).get("CAP_AFTER") == EIGHT_CAP
        and result.get("INHERITED_JUDGE_STATUS") == "SELF_CHECK_ONLY"
        and result.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN",
        "eight-row result claim, scope, or status mismatch",
    )
    proof = result.get("A_PROOF")
    require(
        type(proof) is dict
        and proof.get("PROOF_SCOPE") == "FULL_PROFILE"
        and proof.get("A_LE_188_PLUS_M_PLUS_3E") is True
        and proof.get("M_PLUS_3E_LE_4") is True
        and proof.get("A_LE_192") is True,
        "eight-row full-profile proof is missing",
    )
    certificate = result.get("EIGHTH_PROFILE_CERTIFICATE")
    require(
        type(certificate) is dict
        and certificate.get("PROFILE_ID") == EIGHT_PROFILE
        and certificate.get("APPLICABILITY") == "FULL_PROFILE"
        and certificate.get("OWNER_BOUND") == EIGHT_BOUND
        and certificate.get("T_CAP") == EIGHT_CAP
        and certificate.get("SOURCE_JUDGE_STATUS") == "SELF_CHECK_ONLY"
        and certificate.get("JUDGE_UPGRADE") == "NONE",
        "eight-row certificate pointer is invalid",
    )
    preserved = result.get("PRESERVED_SIX_ROW_STATUS")
    require(
        type(preserved) is dict
        and preserved.get("CURSOR_STATUS") == "UNRESOLVED_AUTHORITY_UNCHANGED"
        and preserved.get("CURSOR_PROFILE_COUNT") == 197
        and preserved.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN"
        and preserved.get("PRIOR_JUDGE_CAVEATS") == "PRESERVED",
        "eight-row unresolved cursor or Judge caveat changed",
    )
    input_identity = {
        "HEAD": EIGHT_HEAD,
        "TREE": EIGHT_TREE,
        "WORKTREE_PATH": str(EIGHT_WORKTREE),
        "WORKTREE_BRANCH": EIGHT_BRANCH,
        "WORKTREE_CLEAN": "YES",
        "RESULT_PATH": EIGHT_RESULT_PATH,
        "RESULT_SHA256": EIGHT_RESULT_SHA256,
        "SOURCE_PATH": EIGHT_SOURCE_PATH,
        "SOURCE_SHA256": EIGHT_SOURCE_SHA256,
        "TEST_PATH": EIGHT_TEST_PATH,
        "TEST_SHA256": EIGHT_TEST_SHA256,
    }
    return result, input_identity


def verify_tied_owner_donor(
    root: Path,
    *,
    profile_id: str,
    head: str,
    tree: str,
    result_path: str,
    result_sha256: str,
    source_path: str,
    source_sha256: str,
    test_path: str,
    test_sha256: str,
    proof_sha256: str,
    task_id: str,
    cap: int,
    bound: int,
    s4_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_commit(root, head, tree)
    raws: dict[str, bytes] = {}
    for path, expected_sha in (
        (result_path, result_sha256),
        (source_path, source_sha256),
        (test_path, test_sha256),
    ):
        raw = committed_blob(root, head, path)
        require_hash(raw, expected_sha, f"donor {path}")
        raws[path] = raw
    result = json_object(raws[result_path], "donor result is invalid JSON")
    proof = result.get("PROOF")
    require(type(proof) is str and bool(proof.strip()), "donor proof field is absent")
    proof_text = cast(str, proof)
    require_hash(proof_text.encode(), proof_sha256, "donor proof field")
    try:
        source_doc = ast.get_docstring(ast.parse(raws[source_path].decode()), clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("donor source cannot be parsed") from exc
    require(source_doc == proof_text, "donor result proof differs from committed source")
    require(
        result.get("TASK_ID") == task_id
        and result.get("TARGET_PROFILE") == profile_id
        and result.get("PROOF_SCOPE") == "FULL_PROFILE"
        and result.get("NEW_T_CAP") == cap
        and result.get("NEW_ADMISSIBLE_BOUND") == bound
        and result.get(s4_key) == GLOBAL_S4_FLOOR
        and result.get("OLD_BOUND") == 313_398_248
        and result.get("FROZEN_HEAD") == FROZEN_HEAD
        and result.get("FROZEN_TREE") == FROZEN_TREE
        and result.get("FROZEN_RESULT_SHA256") == FROZEN_RESULT_SHA256
        and f"T<={cap}" in proof_text
        and str(bound) in proof_text,
        "donor profile, full-profile scope, cap, or frozen authority mismatch",
    )
    identity = {
        "HEAD": head,
        "TREE": tree,
        "RESULT_PATH": result_path,
        "RESULT_SHA256": result_sha256,
        "SOURCE_PATH": source_path,
        "SOURCE_SHA256": source_sha256,
        "TEST_PATH": test_path,
        "TEST_SHA256": test_sha256,
        "PROOF_FIELD": "PROOF",
        "PROOF_FIELD_SHA256": proof_sha256,
        "PROFILE_ID": profile_id,
        "PROOF_SCOPE": "FULL_PROFILE",
        "CAP": cap,
        "BOUND": bound,
    }
    return result, identity


def verify_donors(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    t241, id241 = verify_tied_owner_donor(
        root,
        profile_id="66555555555531000000",
        head=T241_HEAD,
        tree=T241_TREE,
        result_path=T241_RESULT_PATH,
        result_sha256=T241_RESULT_SHA256,
        source_path=T241_SOURCE_PATH,
        source_sha256=T241_SOURCE_SHA256,
        test_path=T241_TEST_PATH,
        test_sha256=T241_TEST_SHA256,
        proof_sha256=T241_PROOF_SHA256,
        task_id="B649_NEXT_TIED_OWNER_BOUNDED_BOUND_RESEARCH_R1",
        cap=241,
        bound=313_183_160,
        s4_key="S4_BASE",
    )
    t240, id240 = verify_tied_owner_donor(
        root,
        profile_id="66655555554441000000",
        head=T240_HEAD,
        tree=T240_TREE,
        result_path=T240_RESULT_PATH,
        result_sha256=T240_RESULT_SHA256,
        source_path=T240_SOURCE_PATH,
        source_sha256=T240_SOURCE_SHA256,
        test_path=T240_TEST_PATH,
        test_sha256=T240_TEST_SHA256,
        proof_sha256=T240_PROOF_SHA256,
        task_id="B649_NEXT_TIED_OWNER_EXACT_BOUND_R1",
        cap=240,
        bound=313_174_392,
        s4_key="SOURCE_S4_BASE",
    )
    return {"T241": t241, "T240": t240}, {"T241": id241, "T240": id240}


def verify_c235_proof_file(root: Path) -> tuple[bytes, str]:
    path = root / C235_PROOF_PATH
    require(path.is_file(), "C235 proof artifact is missing")
    raw = path.read_bytes()
    require_hash(raw, C235_PROOF_SHA256, "C235 proof artifact")
    return raw, sha256(raw)


def index_rows(records: Iterable[tuple[str, Row]]) -> dict[str, Row]:
    items = list(records)
    require(len(items) == SEVEN_ROW_COUNT, "ledger row count mismatch")
    profile_ids = [profile_id for profile_id, _row in items]
    require(
        all(type(profile_id) is str for profile_id in profile_ids)
        and len(set(profile_ids)) == SEVEN_ROW_COUNT,
        "ledger contains invalid or duplicate profile IDs",
    )
    require(all(isinstance(row, Row) for _pid, row in items), "ledger row schema mismatch")
    return dict(items)


def load_frozen_seven_row_ledger(
    frozen: Mapping[str, Any],
) -> dict[str, Row]:
    require(
        frozen.get("TASK_ID") == seven.TASK_ID
        and frozen.get("LEDGER_ROWS") == SEVEN_ROW_COUNT
        and frozen.get("CERTIFICATES_COMPOSED") == SEVEN_CERTIFICATE_COUNT,
        "frozen seven-row result identity mismatch",
    )
    certificate_ids = frozen.get("CERTIFICATE_PROFILE_IDS")
    typed_certificate_ids = cast(list[str], certificate_ids)
    require(
        type(certificate_ids) is list
        and len(certificate_ids) == SEVEN_CERTIFICATE_COUNT
        and len(set(typed_certificate_ids)) == SEVEN_CERTIFICATE_COUNT,
        "frozen seven-row certificate IDs mismatch",
    )
    six_result, six_ledger = seven.six_row_authority()
    six_ids = six_result.get("CERTIFICATE_PROFILE_IDS")
    require(
        type(six_ids) is list
        and typed_certificate_ids == [*cast(list[str], six_ids), seven.TARGET_PROFILE],
        "frozen seven-row certificate lineage mismatch",
    )
    profile_bound = frozen.get("PROFILE_BOUND_AFTER")
    require(type(profile_bound) is int, "frozen seventh bound is not an integer")
    ledger = seven.apply_seventh(
        six_ledger,
        cast(int, profile_bound),
        seven.PROPOSED_CAP,
        f"{seven.TASK_ID}:CORE_ZERO_T256_THEOREM",
    )
    rows = index_rows(ledger.items())
    require(
        seven.two.full_digest(rows) == SEVEN_ROW_FULL_DIGEST
        and seven.two.bounds_digest(rows) == SEVEN_ROW_BOUNDS_DIGEST,
        "frozen seven-row full or bounds digest mismatch",
    )
    family = seven.three.family(rows)
    require(
        family
        == (
            frozen.get("FAMILY_BOUND_AFTER"),
            frozen.get("NEXT_OWNER_IDS"),
            frozen.get("NEXT_COMPETING_BOUND"),
        ),
        "frozen seven-row family replay mismatch",
    )
    frozen_row = frozen.get("NEW_OWNER_ROWS", {}).get(EIGHT_PROFILE)
    require(
        type(frozen_row) is dict
        and json.loads(json.dumps(asdict(rows[EIGHT_PROFILE]))) == frozen_row,
        "frozen eight-row candidate baseline does not match reconstructed ledger",
    )
    return rows


def c235_case_table() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for e in range(7):
        r = 6 + 2 * e
        candidates = [
            (a, q, b, c)
            for a, q, b, c in product(range(9), range(3), range(5), range(5))
            if a + q + b + c == r
        ]
        require(bool(candidates), f"C235 relaxation has no case for e={e}")

        def q_value(values: tuple[int, int, int, int]) -> int:
            return -2 * values[0] + values[1] * (values[1] - 2) + values[2] ** 2 + values[3] ** 2

        max_q = max(q_value(values) for values in candidates)
        maximizers = [values for values in candidates if q_value(values) == max_q]
        zero_degree_square_bound = e * (e + 1)
        before_p = 211 + max_q + zero_degree_square_bound - 8 * e
        non_top_q = max(
            (q_value(values) for values in candidates if values not in maximizers),
            default=None,
        )
        forced_remainder = 2 if e == 1 and maximizers == [(0, 0, 4, 4)] else 0
        non_top_bound = (
            None if non_top_q is None else 211 + non_top_q + zero_degree_square_bound - 8 * e
        )
        final_bound = max(before_p - forced_remainder, non_top_bound or 0)
        cases.append(
            {
                "E": e,
                "R": r,
                "INTEGER_RELAXATION_CASES": len(candidates),
                "Q_MAX": max_q,
                "Q_MAXIMIZERS": [list(values) for values in maximizers],
                "NON_TOP_Q_MAX": non_top_q,
                "SUM_ELL_SQUARED_BOUND": zero_degree_square_bound,
                "T_BOUND_BEFORE_P": before_p,
                "FORCED_P_MIN_FOR_TOP_CASE": forced_remainder,
                "NON_TOP_T_BOUND": non_top_bound,
                "T_BOUND_AFTER_P": final_bound,
            }
        )
    require(
        [(row["Q_MAX"], row["T_BOUND_BEFORE_P"], row["T_BOUND_AFTER_P"]) for row in cases]
        == [
            (20, 231, 231),
            (32, 237, 235),
            (32, 233, 233),
            (28, 227, 227),
            (24, 223, 223),
            (20, 221, 221),
            (16, 221, 221),
        ],
        "C235 seven-case relaxation table mismatch",
    )
    require(
        cases[1]["Q_MAXIMIZERS"] == [[0, 0, 4, 4]] and cases[1]["NON_TOP_T_BOUND"] <= 233,
        "C235 forced-remainder case is not unique",
    )
    return {
        "CASE_COUNT": len(cases),
        "CASES": cases,
        "MAX_T": max(row["T_BOUND_AFTER_P"] for row in cases),
    }


def c235_profile_proof(root: Path, proof_raw: bytes) -> dict[str, Any]:
    profile = seven.three.split.profile_values(C235_PROFILE)
    distribution = {str(d): profile.count(d) for d in sorted(set(profile), reverse=True)}
    require(
        distribution == {"6": 3, "5": 8, "4": 1, "2": 2, "0": 6}
        and len(profile) == 20
        and sum(profile) == 66,
        "C235 profile degree distribution mismatch",
    )
    degrees = [6 + d for d in profile]
    graph_edges = sum(degrees) // 2
    complement_edges = comb(20, 2) - graph_edges
    phi = comb(20, 3) - 18 * complement_edges + sum(comb(13 - d, 2) for d in profile)
    goodman = comb(20, 3) - sum(g * (19 - g) for g in degrees) // 2
    require(
        (graph_edges, complement_edges, phi, goodman) == (93, 97, 295, 295),
        "C235 Goodman identity mismatch",
    )
    sigma_capacity = sum(6 - d for d in profile if d > 0)
    require(sigma_capacity == 18, "C235 core-zero incidence capacity mismatch")
    table = c235_case_table()
    require(table["MAX_T"] == C235_CAP, "C235 analytic cap mismatch")
    proof_text = proof_raw.decode()
    require(
        "T = 211 + Q + Σ_u ℓ_u² - 8e - P" in proof_text  # noqa: RUF001
        and "P≥2" in proof_text
        and "T≤235" in proof_text,
        "C235 proof artifact omits its identity or forced remainder",
    )
    route = route_b_envelope(C235_PROFILE, C235_CAP)
    require(route["BOUND"] == C235_BOUND, "C235 Route-B owner bound mismatch")
    return {
        "PROFILE_ID": C235_PROFILE,
        "DEGREE_DISTRIBUTION": distribution,
        "PROOF_SCOPE": "FULL_PROFILE",
        "UPSTREAM_REPORT": {
            "TASK_ID": "B649_FINAL_TIED_OWNER_C_FULL_PROFILE_R1",
            "THREAD_ID": C235_REPORT_THREAD,
            "TURN_ID": C235_REPORT_TURN,
            "FINAL_ITEM_ID": C235_REPORT_ITEM,
            "REPORT_CONTENT_SHA256": "NOT_AVAILABLE_FROM_THREAD_API",
        },
        "PROOF_PATH": C235_PROOF_PATH,
        "PROOF_CONTENT_SHA256": sha256(proof_raw),
        "GOODMAN_IDENTITY": {
            "G_EDGES": graph_edges,
            "H_EDGES": complement_edges,
            "TRIANGLE_CONSTANT": phi,
            "FORMULA": "T=295-t(H)",
        },
        "SIGMA_CAPACITY": sigma_capacity,
        "SEVEN_E_CASES": table,
        "T_CAP": C235_CAP,
        "ROUTE_B": route,
        "OWNER_BOUND": C235_BOUND,
        "CAP_ATTAINMENT": "UNKNOWN",
        "LEGAL_WITNESS": "NOT_ESTABLISHED",
    }


def route_b_envelope(profile_id: str, cap: int) -> dict[str, Any]:
    profile = seven.three.split.profile_values(profile_id)
    terms_r32 = seven.three.r32.route_b_envelope(profile, cap, GLOBAL_S4_FLOOR)
    terms_split = seven.three.split.route_b_terms(profile, cap, GLOBAL_S4_FLOOR)
    require(terms_r32 == terms_split, "Route-B implementations disagree")
    degrees = [6 + d for d in profile]
    w = sum(comb(g, 2) for g in degrees)
    u = sum(comb(g, 3) for g in degrees)
    maximum_degree = max(degrees)
    a_numerator = sum(d * (g - 2) for d, g in zip(profile, degrees, strict=True))
    a_floor = a_numerator // 3
    exact_terms: list[list[int]] = []
    for t, bound, k4, contained, s4, s3 in terms_r32:
        k4_numerator = u - (maximum_degree - 2) * (w - 3 * t)
        k4_exact = max(0, -((-k4_numerator) // 4))
        contained_exact = min(k4_exact, a_floor)
        s4_exact = max(
            GLOBAL_S4_FLOOR,
            448 * contained_exact + 679 * (k4_exact - contained_exact),
        )
        s3_exact = 2_800 * w + 11_872 * (t - 22) - 30_800
        bound_exact = 308_390_040 + s3_exact - (4 * s4_exact) // 7
        require(
            (k4, contained, s4, s3, bound)
            == (k4_exact, contained_exact, s4_exact, s3_exact, bound_exact),
            f"Route-B exact integer/rational arithmetic mismatch at T={t}",
        )
        exact_terms.append([t, bound_exact, k4_exact, contained_exact, s4_exact, s3_exact])
    require(
        [row[0] for row in exact_terms] == list(range(22, cap + 1))
        and all(left[1] < right[1] for left, right in pairwise(exact_terms)),
        "Route-B term domain or monotonicity mismatch",
    )
    peak = max(exact_terms, key=lambda row: row[1])
    return {
        "PROFILE_ID": profile_id,
        "S4_BASE": GLOBAL_S4_FLOOR,
        "TERM_COUNT": len(exact_terms),
        "TERMS": exact_terms,
        "ARGMAX_TERM": peak,
        "BOUND": peak[1],
        "INCREASING": True,
        "R32_AND_FROZEN_IMPLEMENTATIONS_MATCH": True,
        "EXACT_INTEGER_ROUNDING_MATCH": True,
    }


def source_reference(
    source_kind: str,
    identities: Mapping[str, Any],
    proof_sha: str | None = None,
) -> str:
    if source_kind == "EIGHT_ROW_CANDIDATE":
        return (
            f"git:{EIGHT_HEAD}@{EIGHT_TREE}:{EIGHT_RESULT_PATH}"
            f"#EIGHTH_PROFILE_CERTIFICATE:sha256={EIGHT_RESULT_SHA256}"
        )
    if source_kind == "T241_DONOR":
        return f"git:{T241_HEAD}@{T241_TREE}:{T241_RESULT_PATH}#PROOF:sha256={T241_PROOF_SHA256}"
    if source_kind == "T240_DONOR":
        return f"git:{T240_HEAD}@{T240_TREE}:{T240_RESULT_PATH}#PROOF:sha256={T240_PROOF_SHA256}"
    require(
        source_kind == "C235_LOCAL_PROOF" and proof_sha == C235_PROOF_SHA256,
        "C235 source is not bound to the verified proof artifact",
    )
    return f"file:{C235_PROOF_PATH}:sha256={C235_PROOF_SHA256}"


def verify_certificate(
    certificate: Mapping[str, Any],
    *,
    profile_id: str,
    cap: int,
    bound: int,
    source: str,
) -> None:
    require(
        certificate.get("PROFILE_ID") == profile_id,
        "certificate profile mismatch",
    )
    require(
        type(certificate.get("T_CAP")) is int and certificate.get("T_CAP") == cap,
        "certificate T cap mismatch",
    )
    require(
        type(certificate.get("OWNER_BOUND")) is int and certificate.get("OWNER_BOUND") == bound,
        "certificate owner bound mismatch",
    )
    require(
        certificate.get("PROOF_SCOPE") == "FULL_PROFILE"
        and certificate.get("APPLICABILITY") == "FULL_PROFILE"
        and certificate.get("ROW_SOURCE") == source,
        "certificate scope or source identity mismatch",
    )


def build_owner_certificates(
    identities: Mapping[str, Any], c235: Mapping[str, Any]
) -> list[dict[str, Any]]:
    certificates: list[dict[str, Any]] = []
    for spec in TARGET_SPECS:
        proof_sha = C235_PROOF_SHA256 if spec["source_kind"] == "C235_LOCAL_PROOF" else None
        source = source_reference(spec["source_kind"], identities, proof_sha)
        certificate = {
            "SCHEMA": "B649_PROSPECTIVE_OWNER_FULL_PROFILE_BOUND_V1",
            "PROFILE_ID": spec["profile_id"],
            "APPLICABILITY": "FULL_PROFILE",
            "PROOF_SCOPE": "FULL_PROFILE",
            "OWNER_BOUND": spec["after_bound"],
            "T_CAP": spec["after_cap"],
            "S4_BASE": GLOBAL_S4_FLOOR,
            "ROW_SOURCE": source,
            "SOURCE_KIND": spec["source_kind"],
            "SOURCE_JUDGE_STATUS": "SELF_CHECK_ONLY",
            "JUDGE_UPGRADE": "NONE",
        }
        if spec["profile_id"] == C235_PROFILE:
            certificate["PROOF_CONTENT_SHA256"] = c235["PROOF_CONTENT_SHA256"]
            certificate["UPSTREAM_REPORT"] = c235["UPSTREAM_REPORT"]
        verify_certificate(
            certificate,
            profile_id=spec["profile_id"],
            cap=spec["after_cap"],
            bound=spec["after_bound"],
            source=source,
        )
        certificates.append(certificate)
    return certificates


def apply_four_updates(
    before: Mapping[str, Row], certificates: Sequence[Mapping[str, Any]]
) -> dict[str, Row]:
    before_rows = index_rows(before.items())
    profile_ids = [certificate.get("PROFILE_ID") for certificate in certificates]
    require(
        len(profile_ids) == len(set(profile_ids)),
        "duplicate owner update rejected",
    )
    require(
        tuple(profile_ids) == TARGET_PROFILE_IDS,
        "owner update set or order mismatch",
    )
    require(
        seven.two.full_digest(before_rows) == SEVEN_ROW_FULL_DIGEST
        and seven.two.bounds_digest(before_rows) == SEVEN_ROW_BOUNDS_DIGEST,
        "frozen ledger digest changed before update",
    )
    after = dict(before_rows)
    for spec, certificate in zip(TARGET_SPECS, certificates, strict=True):
        profile_id = cast(str, spec["profile_id"])
        source = cast(str, certificate.get("ROW_SOURCE"))
        verify_certificate(
            certificate,
            profile_id=profile_id,
            cap=cast(int, spec["after_cap"]),
            bound=cast(int, spec["after_bound"]),
            source=source,
        )
        old = before_rows[profile_id]
        require(
            (old.bound, old.cap, old.s4_base)
            == (spec["before_bound"], spec["before_cap"], GLOBAL_S4_FLOOR),
            f"owner row baseline mismatch: {profile_id}",
        )
        require(
            spec["after_bound"] < old.bound
            and 22 <= spec["after_cap"] <= old.cap
            and (spec["after_cap"] < old.cap or profile_id == EIGHT_PROFILE),
            f"owner row is not tightened: {profile_id}",
        )
        after[profile_id] = replace(
            old,
            bound=cast(int, spec["after_bound"]),
            cap=cast(int, spec["after_cap"]),
            source=source,
        )
    verify_ledger_overlay(before_rows, after, certificates)
    require(
        seven.two.full_digest(before_rows) == SEVEN_ROW_FULL_DIGEST
        and seven.two.bounds_digest(before_rows) == SEVEN_ROW_BOUNDS_DIGEST,
        "frozen ledger was mutated by candidate updates",
    )
    return after


def verify_ledger_overlay(
    before: Mapping[str, Row],
    after: Mapping[str, Row],
    certificates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before_rows = index_rows(before.items())
    after_rows = index_rows(after.items())
    require(set(before_rows) == set(after_rows), "ledger profile set changed")
    require(
        seven.two.full_digest(before_rows) == SEVEN_ROW_FULL_DIGEST
        and seven.two.bounds_digest(before_rows) == SEVEN_ROW_BOUNDS_DIGEST,
        "ledger before digest mismatch",
    )
    changed = [
        profile_id
        for profile_id in before_rows
        if before_rows[profile_id] != after_rows[profile_id]
    ]
    require(
        set(changed) == set(TARGET_PROFILE_IDS) and len(changed) == 4,
        "ledger overlay changed a non-target row or missed a target",
    )
    for spec, certificate in zip(TARGET_SPECS, certificates, strict=True):
        profile_id = cast(str, spec["profile_id"])
        old = asdict(before_rows[profile_id])
        new = asdict(after_rows[profile_id])
        changed_fields = sorted(field for field in old if old[field] != new[field])
        expected_fields = (
            ["bound", "source"]
            if spec["after_cap"] == spec["before_cap"]
            else ["bound", "cap", "source"]
        )
        require(
            changed_fields == expected_fields,
            f"protected row fields changed: {profile_id}",
        )
        require(
            (new["bound"], new["cap"], new["s4_base"], new["source"])
            == (
                spec["after_bound"],
                spec["after_cap"],
                GLOBAL_S4_FLOOR,
                certificate.get("ROW_SOURCE"),
            ),
            f"target row update mismatch: {profile_id}",
        )
    unchanged = [
        profile_id
        for profile_id in before_rows
        if profile_id not in TARGET_PROFILE_IDS
        and before_rows[profile_id] == after_rows[profile_id]
    ]
    require(len(unchanged) == SEVEN_ROW_COUNT - 4, "unchanged row count mismatch")
    return {
        "ROWS_BEFORE": len(before_rows),
        "ROWS_AFTER": len(after_rows),
        "CHANGED_PROFILE_COUNT": len(changed),
        "CHANGED_PROFILES": list(TARGET_PROFILE_IDS),
        "UNCHANGED_ROWS": len(unchanged),
        "FULL_DIGEST_BEFORE": seven.two.full_digest(before_rows),
        "BOUNDS_DIGEST_BEFORE": seven.two.bounds_digest(before_rows),
        "FULL_DIGEST_AFTER": seven.two.full_digest(after_rows),
        "BOUNDS_DIGEST_AFTER": seven.two.bounds_digest(after_rows),
        "FROZEN_LEDGER_UNCHANGED": "YES",
    }


def family_frontier(ledger: Mapping[str, Row]) -> dict[str, Any]:
    maximum, owners, next_bound = seven.three.family(ledger)
    cursor_id = seven.three.two.chase.prior.CURSOR_ID
    cursor_bound = seven.three.two.chase.prior.CURSOR_BOUND
    levels = [(row.bound, profile_id) for profile_id, row in ledger.items()]
    levels.append((cursor_bound, cursor_id))
    next_owners = sorted(profile_id for bound, profile_id in levels if bound == next_bound)
    require(
        maximum == max(bound for bound, _profile_id in levels)
        and owners == sorted(profile_id for bound, profile_id in levels if bound == maximum)
        and next_bound == max(bound for bound, _profile_id in levels if bound < maximum),
        "family frontier disagrees with full row recount",
    )
    return {
        "FAMILY_BOUND": maximum,
        "TIED_OWNERS": owners,
        "NEXT_COMPETING_BOUND": next_bound,
        "NEXT_COMPETING_OWNERS": next_owners,
        "CURSOR": {"ID": cursor_id, "BOUND": cursor_bound},
    }


def verify_family_summary(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    require(dict(actual) == dict(expected), "family maximum or owner summary mismatch")


def build_candidate() -> tuple[
    dict[str, Any], dict[str, Row], dict[str, Row], list[dict[str, Any]]
]:
    require(
        Path(cast(str, run_git(ROOT, "rev-parse", "--show-toplevel"))) == ROOT,
        "wrong repository root",
    )
    frozen, frozen_identity = verify_frozen_source(ROOT)
    eight, eight_identity = verify_eight_row_candidate(ROOT)
    _donors, donor_identities = verify_donors(ROOT)
    proof_raw, proof_sha = verify_c235_proof_file(ROOT)
    require(proof_sha == C235_PROOF_SHA256, "C235 proof SHA256 mismatch")
    c235 = c235_profile_proof(ROOT, proof_raw)

    before = load_frozen_seven_row_ledger(frozen)
    before_family = family_frontier(before)
    require(
        before_family["FAMILY_BOUND"] == 313_398_532
        and before_family["TIED_OWNERS"] == [EIGHT_PROFILE]
        and before_family["NEXT_COMPETING_BOUND"] == 313_398_248,
        "frozen seven-row family frontier mismatch",
    )
    cursor_authority = frozen.get("PRESERVED_SIX_ROW_STATUS")
    require(
        type(cursor_authority) is dict
        and cursor_authority.get("CURSOR_STATUS") == "UNRESOLVED_AUTHORITY_UNCHANGED"
        and cursor_authority.get("CURSOR_PROFILE_COUNT") == 197
        and cursor_authority.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN"
        and cursor_authority == eight.get("PRESERVED_SIX_ROW_STATUS"),
        "unresolved cursor or prior Judge state was not preserved",
    )
    cursor_authority = cast(dict[str, Any], cursor_authority)
    identities: dict[str, Any] = {
        "FROZEN_SEVEN_ROW": frozen_identity,
        "EIGHT_ROW_CANDIDATE": eight_identity,
        "DONORS": donor_identities,
        "C235_PROOF": {
            "PATH": C235_PROOF_PATH,
            "SHA256": proof_sha,
            "UPSTREAM_THREAD_ID": C235_REPORT_THREAD,
            "UPSTREAM_TURN_ID": C235_REPORT_TURN,
            "UPSTREAM_FINAL_ITEM_ID": C235_REPORT_ITEM,
        },
    }
    certificates = build_owner_certificates(identities, c235)
    after = apply_four_updates(before, certificates)
    overlay = verify_ledger_overlay(before, after, certificates)
    after_family = family_frontier(after)
    verify_family_summary(
        after_family,
        {
            "FAMILY_BOUND": EXPECTED_AFTER_FAMILY,
            "TIED_OWNERS": EXPECTED_AFTER_OWNERS,
            "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
            "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
            "CURSOR": {
                "ID": seven.three.two.chase.prior.CURSOR_ID,
                "BOUND": seven.three.two.chase.prior.CURSOR_BOUND,
            },
        },
    )
    above_incumbent = sum(row.bound > INCUMBENT for row in after.values())
    require(above_incumbent == 1_375, "remaining above-incumbent profile count mismatch")
    certificate_ids_before = cast(list[str], frozen["CERTIFICATE_PROFILE_IDS"])
    certificate_ids_after = [*certificate_ids_before, *TARGET_PROFILE_IDS]
    require(
        len(certificate_ids_after) == 11 and len(set(certificate_ids_after)) == 11,
        "prospective eleven-certificate profile set mismatch",
    )
    row_updates: list[dict[str, Any]] = []
    for spec in TARGET_SPECS:
        profile_id = cast(str, spec["profile_id"])
        row_updates.append(
            {
                "PROFILE_ID": profile_id,
                "BEFORE_BOUND": before[profile_id].bound,
                "AFTER_BOUND": after[profile_id].bound,
                "CAP_BEFORE": before[profile_id].cap,
                "CAP_AFTER": after[profile_id].cap,
                "S4_BASE": after[profile_id].s4_base,
                "SOURCE_AFTER": after[profile_id].source,
            }
        )
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROSPECTIVE_LOCAL_INTEGRATION_COMPLETE",
        "FORMAL_JUDGE_STATUS": "NOT_UPGRADED",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "SOURCE_PUBLICATION": "NOT_RUN",
        "FROZEN_AUTHORITY": {
            **frozen_identity,
            "LEDGER_ROWS": SEVEN_ROW_COUNT,
            "CERTIFICATES": SEVEN_CERTIFICATE_COUNT,
            "FULL_DIGEST": SEVEN_ROW_FULL_DIGEST,
            "BOUNDS_DIGEST": SEVEN_ROW_BOUNDS_DIGEST,
        },
        "INPUT_IDENTITIES": identities,
        "C235_PROOF": c235,
        "CERTIFICATES_BEFORE": SEVEN_CERTIFICATE_COUNT,
        "CERTIFICATES_PROSPECTIVE_AFTER": len(certificate_ids_after),
        "CERTIFICATE_PROFILE_IDS_BEFORE": certificate_ids_before,
        "CERTIFICATE_PROFILE_IDS_AFTER": certificate_ids_after,
        "OWNER_CERTIFICATES": certificates,
        "ROW_UPDATES": row_updates,
        "LEDGER_OVERLAY": overlay,
        "LEDGER_ROWS_BEFORE": len(before),
        "LEDGER_ROWS_AFTER": len(after),
        "ALL_ROW_RECOUNT": len(after),
        "OWNER_BOUNDS_AFTER": {spec["profile_id"]: spec["after_bound"] for spec in TARGET_SPECS},
        "FAMILY_BEFORE": before_family,
        "FAMILY_AFTER": after_family,
        "FAMILY_BOUND_DELTA": before_family["FAMILY_BOUND"] - after_family["FAMILY_BOUND"],
        "UNRESOLVED_CURSOR_PRESERVED": "YES",
        "UNRESOLVED_CURSOR_PROFILE_COUNT": cursor_authority["CURSOR_PROFILE_COUNT"],
        "ABOVE_INCUMBENT_PROFILE_COUNT_REMAINS": above_incumbent,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "INHERITED_JUDGE_CAVEATS": {
            "EIGHT_ROW_CANDIDATE": "BLOCKED_UNVERIFIABLE",
            "SIX_ROW_AUTHORITY": "VERIFIED_WITH_CAVEATS",
            "CURSOR_STATUS": "UNRESOLVED_AUTHORITY_UNCHANGED",
        },
        "HEAVY_SOLVER_STARTED": "NO",
        "RESTRICTED_REMOTE_OBJECT_FETCH": "NOT_RUN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    return result, before, after, certificates


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        require(path.read_bytes() == raw, "refusing to overwrite a different result artifact")
    else:
        path.write_bytes(raw)
    return sha256(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result, _before, _after, _certificates = build_candidate()
    raw = serialize_result(result)
    digest = sha256(raw)
    if args.write_result:
        digest = write_result(result)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "RESULT_PATH": RESULT_PATH if args.write_result else "NOT_WRITTEN",
                "RESULT_SHA256": digest,
                "LEDGER_ROWS": result["ALL_ROW_RECOUNT"],
                "FAMILY_AFTER": result["FAMILY_AFTER"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
