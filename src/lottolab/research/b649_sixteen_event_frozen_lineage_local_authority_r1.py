"""Replay a five-proof overlay on the frozen seven-row B649 family ledger."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_eleven_event_family_authority_r1 as eleven
from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_nine_event_eight_profile_local_authority_r1 as nine

TASK_ID = "B649_SIXTEEN_EVENT_FROZEN_LINEAGE_LOCAL_AUTHORITY_R1"
ROOT = Path(__file__).resolve().parents[3]

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

ELEVEN_HEAD = "a94b3075e971b41a546110c72f3553141e279307"
ELEVEN_TREE = "80ad4ef5c2c3f0d9d557095cdc0004544854a767"
ELEVEN_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-eleven-event-family-authority-r1-result.json"
)
ELEVEN_RESULT_SHA256 = "8989853af223b8056ec1dd9980d0e142da2507897c04ca414a1d7e454f2347af"
ELEVEN_SOURCE_PATH = "src/lottolab/research/b649_eleven_event_family_authority_r1.py"
ELEVEN_SOURCE_SHA256 = "9e67989cc2fae451809aa8c6c4da0cb8d7852150f151136c4bd18dd9df3df7f6"
ELEVEN_TEST_PATH = "tests/unit/test_b649_eleven_event_family_authority_r1.py"
ELEVEN_TEST_SHA256 = "d664be7b71ed1bee893a6a49dd3095e7368440676252d1e9021b2367eca36114"
FOUR_ENGINE_PATH = "src/lottolab/research/b649_existing_four_owner_local_authority_r1.py"
FOUR_ENGINE_SHA256 = "2f1cdffeb703d080069e6ab7ac0fb83e5e15ca42c465db05f2458d4466289759"

T257_HEAD = "c2e7cd504cd4e800cad136306224c1f4ae50a0f1"
T257_TREE = "d5e170d3cc081afb2b4174892470e88d19d54de4"
T257_RESULT_PATH = "docs/research/matrix-native-results/b649-new-family-max-owner-a-r1-result.json"
T257_RESULT_SHA256 = "5e92e6726f11ef678755cb08b1e8f5e854fda8a013ebefe0dcdb91420b42bfe2"
T257_SOURCE_PATH = "src/lottolab/research/b649_new_family_max_owner_a_r1.py"
T257_SOURCE_SHA256 = "80571655847b63a695d6b9842ad1d8484611a43b6596d9f3017f365402c89880"
T257_TEST_PATH = "tests/unit/test_b649_new_family_max_owner_a_r1.py"
T257_TEST_SHA256 = "a3df51910fc490398eb6ef554d3a4c388aad0f3412a17f43d4694ddfae9c878e"
T257_PROOF_SHA256 = "af3b084d09d7a085571e801d80ba941627713b82fa6722180d681984ab69629c"

T243_HEAD = "97dcfa9a2cfec1ef30097d808ecb6f87e9c6241f"
T243_TREE = "83fbdfece095ec5f88ac411a9d2db7a9aaf833f3"
T243_BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
T243_BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
T243_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-b-exact-bound-r1-result-"
    "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b.json"
)
T243_RESULT_SHA256 = "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b"
T243_SOURCE_PATH = "src/lottolab/research/b649_min_s2_owner_b_exact_bound_r1.py"
T243_SOURCE_SHA256 = "2a176205ceb6b96b929e459c44270d9e4f4fc04389d9507efe75806a5c885290"
T243_TEST_PATH = "tests/unit/test_b649_min_s2_owner_b_exact_bound_r1.py"
T243_TEST_SHA256 = "404639ae889f9509e4e9930597b4d1df86373fe5f6842f27b863057e11a2c5c8"
T243_PROOF_SHA256 = "891c4f7423034d89a806788630585df784ff9f605c3efaa2095e1d25a47473fc"

PR378_HEAD = "693e750e8fdf62382b5be056cffe3b688608ab6d"
PR378_TREE = "484b4df1b44fc2fb0405c6b470aff58579f0617e"
PR378_BASE_HEAD = T243_BASE_HEAD
PR378_BASE_TREE = T243_BASE_TREE
PR378_IMPLEMENTATION_HEAD = "61bad6d9ed4bdb6977d076d6b7fa28ac7b05f82a"
PR378_IMPLEMENTATION_TREE = "78f4a11e774c3c6fe3a13d0f1ab10f7e7d8c7ed0"
PR378_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-three-max-profiles-shared-certificate-r2-result.json"
)
PR378_RESULT_SHA256 = "dc28b0f4e3bfb14be8a39a3d3148f1d27aadf3e060c89a8e6e695dfea55babcc"
PR378_SOURCE_PATH = "src/lottolab/research/b649_three_max_profiles_shared_certificate_r2.py"
PR378_SOURCE_SHA256 = "ac4890aba8f8524fb705fead03d4e36608c3ab299cd02f870db06f1a3848ba9d"
PR378_TEST_PATH = "tests/unit/test_b649_three_max_profiles_shared_certificate_r2.py"
PR378_TEST_SHA256 = "d5d0d23543721fe918fd551d6756921d19e6c6cb89d4cec363edb7acd1973fac"
PR378_PROOF_SHA256 = "7aece59b75a95f001984c3f7887a41537d2a3d5ea67fbc54fc5e0fec073c6fc1"

EXPECTED_ROW_COUNT = 4_647
EXPECTED_NEW_FAMILY_BOUND = 313_395_060
EXPECTED_MAX_OWNERS = ["66655555555332000000", "66655555555421100000"]
EXPECTED_NEXT_BOUND = 313_394_776
EXPECTED_NEXT_OWNER = ["66555555555431100000"]
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
INCUMBENT = 313_263_888
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-sixteen-event-frozen-lineage-local-authority-r1-result.json"
)

FROZEN_ROUTE_B_SOURCE_PINS = {
    "src/lottolab/research/b649_min_s2_next_owner_core_zero_t256_cert_r1.py":
        "49a7364b7fbcb2ed03fdd6c3eda43067f38fdcbbda6caee7a6eedf71fa02fa04",
    "src/lottolab/research/b649_min_s2_core_zero_t257_three_row_cert_r1.py":
        "0e3d4746ef59eece7de5291cf3fe40c364f5dc70380d00666095c0362f95d806",
    "src/lottolab/research/b649_min_s2_two_certified_row_combined_authority_r1.py":
        "d4e66d1515d9d9c1d1206d7d5cee8769d9fb12bc2f39d11b471f5689ae2ffa5f",
    "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py":
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d",
    "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py":
        "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784",
}


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    task_id: str
    head: str
    tree: str
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    proof_path: str
    proof_fragment: str
    proof_sha256: str


@dataclass(frozen=True)
class EventSpec:
    event_id: str
    artifact_key: str
    profile_id: str
    cap: int
    expected_bound: int
    proof_scope_detail: str
    applicability: str


ARTIFACTS: dict[str, ArtifactSpec] = {
    "T257": ArtifactSpec(
        key="T257",
        task_id="B649_NEW_FAMILY_MAX_OWNER_A_R1",
        head=T257_HEAD,
        tree=T257_TREE,
        result_path=T257_RESULT_PATH,
        result_sha256=T257_RESULT_SHA256,
        source_path=T257_SOURCE_PATH,
        source_sha256=T257_SOURCE_SHA256,
        test_path=T257_TEST_PATH,
        test_sha256=T257_TEST_SHA256,
        proof_path=T257_SOURCE_PATH,
        proof_fragment="MODULE_DOCSTRING",
        proof_sha256=T257_PROOF_SHA256,
    ),
    "T243": ArtifactSpec(
        key="T243",
        task_id="B649_MIN_S2_OWNER_B_666655555544310_EXACT_BOUND_R1",
        head=T243_HEAD,
        tree=T243_TREE,
        result_path=T243_RESULT_PATH,
        result_sha256=T243_RESULT_SHA256,
        source_path=T243_SOURCE_PATH,
        source_sha256=T243_SOURCE_SHA256,
        test_path=T243_TEST_PATH,
        test_sha256=T243_TEST_SHA256,
        proof_path=T243_RESULT_PATH,
        proof_fragment="PROOF",
        proof_sha256=T243_PROOF_SHA256,
    ),
    "PR378": ArtifactSpec(
        key="PR378",
        task_id="B649_THREE_MAX_PROFILES_SHARED_CERTIFICATE_R2",
        head=PR378_HEAD,
        tree=PR378_TREE,
        result_path=PR378_RESULT_PATH,
        result_sha256=PR378_RESULT_SHA256,
        source_path=PR378_SOURCE_PATH,
        source_sha256=PR378_SOURCE_SHA256,
        test_path=PR378_TEST_PATH,
        test_sha256=PR378_TEST_SHA256,
        proof_path=PR378_RESULT_PATH,
        proof_fragment="PROOF",
        proof_sha256=PR378_PROOF_SHA256,
    ),
}

EVENT_SPECS: tuple[EventSpec, ...] = (
    EventSpec(
        "T257",
        "T257",
        "66655555555511100000",
        257,
        313_332_416,
        "FULL_PROFILE",
        "VERIFIED",
    ),
    EventSpec(
        "T243",
        "T243",
        "66665555554431000000",
        243,
        313_206_948,
        "EXACT_PROFILE_FULL_BOUND",
        "VERIFIED",
    ),
    EventSpec(
        "PR378_65555555555532000000",
        "PR378",
        "65555555555532000000",
        230,
        313_072_532,
        "ANALYTIC_UNIVERSAL_BOUND_FOR_EXACT_PROFILE",
        "VERIFIED_WITH_SCOPE",
    ),
    EventSpec(
        "PR378_66555555554442000000",
        "PR378",
        "66555555554442000000",
        227,
        313_045_840,
        "ANALYTIC_UNIVERSAL_BOUND_FOR_EXACT_PROFILE",
        "VERIFIED_WITH_SCOPE",
    ),
    EventSpec(
        "PR378_66555555555333000000",
        "PR378",
        "66555555555333000000",
        228,
        313_054_608,
        "ANALYTIC_UNIVERSAL_BOUND_FOR_EXACT_PROFILE",
        "VERIFIED_WITH_SCOPE",
    ),
)

EXPECTED_BEFORE = {
    "66655555555511100000": (313_395_344, 264),
    "66665555554431000000": (313_395_344, 264),
    "65555555555532000000": (313_395_164, 266),
    "66555555554442000000": (313_395_164, 266),
    "66555555555333000000": (313_395_164, 266),
}

EXPECTED_FAMILY_AFTER = {
    "FAMILY_BOUND": EXPECTED_NEW_FAMILY_BOUND,
    "TIED_OWNERS": EXPECTED_MAX_OWNERS,
    "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
    "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNER,
    "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
}

Row = four.Row


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    return nine.json_object(raw, message)


def module_docstring(raw: bytes, path: str) -> str:
    try:
        parsed = ast.parse(raw.decode(), filename=path)
        proof = ast.get_docstring(parsed, clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError(f"proof source cannot be parsed: {path}") from exc
    require(type(proof) is str and bool(proof.strip()), f"proof source is missing: {path}")
    return cast(str, proof)


def verify_artifact(
    root: Path, spec: ArtifactSpec
) -> tuple[dict[str, Any], str, dict[str, bytes]]:
    four.verify_commit(root, spec.head, spec.tree)
    blobs = {
        "RESULT": four.committed_blob(root, spec.head, spec.result_path),
        "SOURCE": four.committed_blob(root, spec.head, spec.source_path),
        "TEST": four.committed_blob(root, spec.head, spec.test_path),
    }
    require(
        sha256(blobs["RESULT"]) == spec.result_sha256,
        f"donor result SHA256 mismatch: {spec.key}",
    )
    require(
        sha256(blobs["SOURCE"]) == spec.source_sha256,
        f"donor source SHA256 mismatch: {spec.key}",
    )
    require(
        sha256(blobs["TEST"]) == spec.test_sha256,
        f"donor test SHA256 mismatch: {spec.key}",
    )
    record = json_object(blobs["RESULT"], f"donor result is invalid JSON: {spec.key}")
    require(record.get("TASK_ID") == spec.task_id, f"donor task ID mismatch: {spec.key}")
    if spec.key == "T257":
        require(
            record.get("FROZEN_HEAD") == FROZEN_HEAD
            and record.get("FROZEN_TREE") == FROZEN_TREE
            and record.get("FROZEN_RESULT_SHA256") == FROZEN_RESULT_SHA256
            and record.get("FROZEN_HEAD_TREE") == "MATCH"
            and record.get("FROZEN_RESULT_SHA256_STATUS") == "MATCH",
            "T257 Frozen authority identity mismatch",
        )
    elif spec.key == "T243":
        require(
            record.get("BASE_HEAD") == T243_BASE_HEAD
            and record.get("BASE_TREE") == T243_BASE_TREE,
            "T243 mathematical Base identity mismatch",
        )
        parents = four.run_git(root, "show", "-s", "--format=%P", spec.head).split()
        require(parents == [T243_BASE_HEAD], "T243 donor parent mismatch")
    if spec.proof_fragment == "MODULE_DOCSTRING":
        proof = module_docstring(blobs["SOURCE"], spec.source_path)
    else:
        raw_proof = record.get(spec.proof_fragment)
        require(type(raw_proof) is str, f"donor proof is missing: {spec.key}")
        proof = cast(str, raw_proof)
        require(
            proof == module_docstring(blobs["SOURCE"], spec.source_path),
            f"donor result proof differs from source: {spec.key}",
        )
    require(
        sha256(proof.encode()) == spec.proof_sha256,
        f"donor proof SHA256 mismatch: {spec.key}",
    )
    return record, proof, blobs


def verify_frozen_route_b_sources(root: Path) -> dict[str, str]:
    four.verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    four.verify_commit(root, ELEVEN_HEAD, ELEVEN_TREE)
    for path, expected in FROZEN_ROUTE_B_SOURCE_PINS.items():
        frozen_blob = four.committed_blob(root, FROZEN_HEAD, path)
        eleven_blob = four.committed_blob(root, ELEVEN_HEAD, path)
        require(sha256(frozen_blob) == expected, f"Frozen Route-B source pin mismatch: {path}")
        require(eleven_blob == frozen_blob, f"Route-B source changed after Frozen tree: {path}")
        require((root / path).read_bytes() == frozen_blob, f"local Route-B source changed: {path}")
    wrapper = four.committed_blob(root, ELEVEN_HEAD, FOUR_ENGINE_PATH)
    require(sha256(wrapper) == FOUR_ENGINE_SHA256, "Route-B loader wrapper source mismatch")
    require(
        (root / FOUR_ENGINE_PATH).read_bytes() == wrapper,
        "local Route-B loader wrapper changed",
    )
    return dict(FROZEN_ROUTE_B_SOURCE_PINS)


def verify_eleven_candidate(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Row], dict[str, Row], dict[str, str]]:
    four.verify_commit(root, ELEVEN_HEAD, ELEVEN_TREE)
    result_blob = four.committed_blob(root, ELEVEN_HEAD, ELEVEN_RESULT_PATH)
    source_blob = four.committed_blob(root, ELEVEN_HEAD, ELEVEN_SOURCE_PATH)
    test_blob = four.committed_blob(root, ELEVEN_HEAD, ELEVEN_TEST_PATH)
    require(sha256(result_blob) == ELEVEN_RESULT_SHA256, "11-event result SHA256 mismatch")
    require(sha256(source_blob) == ELEVEN_SOURCE_SHA256, "11-event source SHA256 mismatch")
    require(sha256(test_blob) == ELEVEN_TEST_SHA256, "11-event test SHA256 mismatch")
    require(
        (root / ELEVEN_SOURCE_PATH).read_bytes() == source_blob
        and (root / ELEVEN_TEST_PATH).read_bytes() == test_blob,
        "11-event source or test differs from pinned tree",
    )
    stored = json_object(result_blob, "11-event result is invalid JSON")
    rebuilt, frozen, after = eleven.build_candidate()
    require(
        stored == rebuilt and result_blob == eleven.serialize_result(rebuilt),
        "11-event result differs from exact replay",
    )
    require(
        rebuilt.get("UPDATE_EVENTS") == 11
        and rebuilt.get("DISTINCT_CHANGED_PROFILES") == 10
        and rebuilt.get("FAMILY_AFTER", {}).get("FAMILY_BOUND") == 313_395_344,
        "11-event source identity or family frontier mismatch",
    )
    identity = {
        "HEAD": ELEVEN_HEAD,
        "TREE": ELEVEN_TREE,
        "RESULT_PATH": ELEVEN_RESULT_PATH,
        "RESULT_SHA256": sha256(result_blob),
        "SOURCE_PATH": ELEVEN_SOURCE_PATH,
        "SOURCE_SHA256": sha256(source_blob),
        "TEST_PATH": ELEVEN_TEST_PATH,
        "TEST_SHA256": sha256(test_blob),
        "UPDATE_EVENTS": rebuilt["UPDATE_EVENTS"],
        "DISTINCT_CHANGED_PROFILES": rebuilt["DISTINCT_CHANGED_PROFILES"],
        "NEW_FULL_DIGEST": rebuilt["NEW_FULL_DIGEST"],
        "NEW_BOUNDS_DIGEST": rebuilt["NEW_BOUNDS_DIGEST"],
        "SOURCE_REPLAY_MATCH": "YES",
    }
    return rebuilt, frozen, after, identity


def verify_pr378_evaluator_closure(
    root: Path, result: Mapping[str, Any]
) -> dict[str, str]:
    four.verify_commit(root, PR378_HEAD, PR378_TREE)
    four.verify_commit(root, PR378_BASE_HEAD, PR378_BASE_TREE)
    pins = result.get("SOURCE_PINS")
    require(type(pins) is dict and len(pins) == 22, "PR #378 evaluator source pin count mismatch")
    checked: dict[str, str] = {}
    for path_value, digest_value in cast(dict[Any, Any], pins).items():
        require(type(path_value) is str and type(digest_value) is str, "invalid PR source pin")
        path = cast(str, path_value)
        digest = cast(str, digest_value)
        require(len(digest) == 64, f"invalid PR source SHA256: {path}")
        base_blob = four.committed_blob(root, PR378_BASE_HEAD, path)
        pr_blob = four.committed_blob(root, PR378_HEAD, path)
        frozen_blob = four.committed_blob(root, FROZEN_HEAD, path)
        require(sha256(base_blob) == digest, f"PR math-base evaluator pin mismatch: {path}")
        require(sha256(pr_blob) == digest, f"PR tree evaluator pin mismatch: {path}")
        require(sha256(frozen_blob) == digest, f"Frozen evaluator pin mismatch: {path}")
        require(
            (root / path).read_bytes() == frozen_blob,
            f"local evaluator source changed: {path}",
        )
        checked[path] = digest
    return dict(sorted(checked.items()))


def verify_pr378_authority(
    root: Path,
    result: Mapping[str, Any],
    source_blob: bytes,
) -> tuple[dict[str, str], dict[str, Mapping[str, Any]]]:
    require(result.get("TASK_ID") == ARTIFACTS["PR378"].task_id, "PR #378 task identity mismatch")
    mathematical_base = result.get("MATHEMATICAL_BASE")
    require(isinstance(mathematical_base, Mapping), "PR #378 mathematical Base is missing")
    mathematical_base_map = cast(Mapping[str, Any], mathematical_base)
    require(
        mathematical_base_map.get("HEAD") == PR378_BASE_HEAD
        and mathematical_base_map.get("TREE") == PR378_BASE_TREE,
        "PR #378 mathematical Base identity mismatch",
    )
    implementation_base = result.get("IMPLEMENTATION_BASE")
    require(isinstance(implementation_base, Mapping), "PR #378 implementation Base is missing")
    implementation_base_map = cast(Mapping[str, Any], implementation_base)
    require(
        implementation_base_map.get("HEAD") == PR378_IMPLEMENTATION_HEAD
        and implementation_base_map.get("TREE") == PR378_IMPLEMENTATION_TREE,
        "PR #378 implementation Base identity mismatch",
    )
    four.verify_commit(root, PR378_IMPLEMENTATION_HEAD, PR378_IMPLEMENTATION_TREE)
    pins = verify_pr378_evaluator_closure(root, result)
    proof = result.get("PROOF")
    require(type(proof) is str, "PR #378 shared proof is missing")
    require(
        cast(str, proof) == module_docstring(source_blob, PR378_SOURCE_PATH)
        and sha256(cast(str, proof).encode()) == PR378_PROOF_SHA256,
        "PR #378 proof bytes do not match source",
    )
    raw_certificates = result.get("CERTIFICATES")
    require(
        type(raw_certificates) is list and len(raw_certificates) == 3,
        "PR certificates missing",
    )
    certificates: dict[str, Mapping[str, Any]] = {}
    for value in cast(list[Any], raw_certificates):
        require(isinstance(value, Mapping), "invalid PR certificate")
        certificate = cast(Mapping[str, Any], value)
        profile_id = certificate.get("PROFILE_ID")
        require(type(profile_id) is str and profile_id not in certificates, "duplicate PR profile")
        theorem = certificate.get("THEOREM")
        require(isinstance(theorem, Mapping), "PR theorem scope missing")
        theorem_map = cast(Mapping[str, Any], theorem)
        require(
            theorem_map.get("PROFILE_ID") == profile_id
            and theorem_map.get("COMPLETENESS")
            == "NOT_APPLICABLE — ANALYTIC_UNIVERSAL_BOUND"
            and theorem_map.get("ATTAINABILITY") == "NOT_ASSERTED",
            f"PR theorem scope mismatch: {profile_id}",
        )
        certificates[cast(str, profile_id)] = certificate
    expected_profiles = {event.profile_id for event in EVENT_SPECS if event.artifact_key == "PR378"}
    require(set(certificates) == expected_profiles, "PR profile set mismatch")
    return pins, certificates


def verify_event_proof_scope(
    event: EventSpec,
    record: Mapping[str, Any],
    proof: str,
    row: Row,
    pr_certificates: Mapping[str, Mapping[str, Any]],
) -> None:
    require(
        (row.bound, row.cap) == EXPECTED_BEFORE[event.profile_id],
        f"Frozen row before-state mismatch: {event.profile_id}",
    )
    require(row.s4_base == four.GLOBAL_S4_FLOOR, f"Frozen row S4 base mismatch: {event.profile_id}")
    if event.artifact_key == "T257":
        source_row = record.get("SOURCE_ROW")
        require(isinstance(source_row, Mapping), "T257 source row missing")
        source = cast(Mapping[str, Any], source_row)
        require(
            record.get("PROOF_SCOPE") == "FULL_PROFILE"
            and record.get("PROFILE_ID") == event.profile_id
            and record.get("NEW_PROVED_T_CAP") == event.cap
            and source.get("bound") == row.bound
            and source.get("cap") == row.cap
            and source.get("s4_base") == row.s4_base
            and source.get("source") == row.source,
            "T257 scope or Frozen row binding mismatch",
        )
    elif event.artifact_key == "T243":
        require(
            record.get("TARGET_PROFILE") == event.profile_id
            and record.get("CURRENT_PROFILE_BOUND") == row.bound
            and record.get("CURRENT_T_CAP") == row.cap
            and record.get("CURRENT_S4_FLOOR") == row.s4_base
            and record.get("BOUND_SOURCE") == row.source
            and record.get("NEW_PROVEN_T_CAP") == event.cap
            and proof.startswith(
                f"Exact-profile split certificate for {event.profile_id}: T <= {event.cap}."
            ),
            "T243 scope or Frozen row binding mismatch",
        )
    else:
        certificate = pr_certificates.get(event.profile_id)
        require(certificate is not None, f"PR certificate missing: {event.profile_id}")
        cert = cast(Mapping[str, Any], certificate)
        theorem = cast(Mapping[str, Any], cert["THEOREM"])
        s4_authority = cert.get("S4_AUTHORITY")
        require(isinstance(s4_authority, Mapping), "PR S4 authority is missing")
        require(
            cert.get("OLD_BOUND") == row.bound
            and cert.get("OLD_T_CAP") == row.cap
            and cert.get("NEW_T_CAP") == event.cap
            and cast(Mapping[str, Any], s4_authority).get("INHERITED_FLOOR") == row.s4_base
            and theorem.get("PROFILE_ID") == event.profile_id
            and theorem.get("ANALYTIC_CAP") == event.cap
            and "Universal analytic certificate" in proof,
            f"PR certificate scope or Frozen row binding mismatch: {event.profile_id}",
        )


def source_locator(artifact: ArtifactSpec) -> str:
    return (
        f"git:{artifact.head}@{artifact.tree}:{artifact.proof_path}"
        f"#{artifact.proof_fragment}:sha256={artifact.proof_sha256}"
    )


def verify_unique_events(events: Sequence[Mapping[str, Any]]) -> None:
    ids = [event.get("EVENT_ID") for event in events]
    require(len(ids) == len(set(ids)), "duplicate update event")


def verify_ledger_partition(
    before: Mapping[str, Row],
    after: Mapping[str, Row],
    expected_changed: set[str],
) -> set[str]:
    require(set(before) == set(after), "ledger profile set changed")
    require(
        len(before) == EXPECTED_ROW_COUNT and len(after) == EXPECTED_ROW_COUNT,
        "row count mismatch",
    )
    changed = {profile_id for profile_id in before if before[profile_id] != after[profile_id]}
    require(changed == expected_changed, "unrelated row mutation or missing event")
    return changed


def verify_family_frontier(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    four.verify_family_summary(actual, expected)


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except ValueError:
        return "PASS"
    raise ValueError(message)


def verify_negative_cases(
    root: Path,
    pins: Sequence[nine.DonorPin],
    identities: Mapping[str, Mapping[str, Any]],
    frozen: Mapping[str, Row],
    after_eleven: Mapping[str, Row],
    after: Mapping[str, Row],
    changed_from_frozen: set[str],
    family_after: Mapping[str, Any],
) -> dict[str, str]:
    first = pins[0]
    identity = identities[first.event_id]
    certificate = {
        "PROFILE_ID": first.profile_id,
        "T_CAP": first.cap,
        "OWNER_BOUND": first.bound,
        "PROOF_SCOPE": "FULL_PROFILE",
        "ROW_SOURCE": identity["ROW_SOURCE"],
        "PROOF_SHA256": first.proof_sha256,
    }
    unrelated = next(profile_id for profile_id in after if profile_id not in changed_from_frozen)
    changed_copy = dict(after)
    changed_copy[unrelated] = replace(changed_copy[unrelated], source="unrelated-mutation")
    wrong_family = dict(family_after)
    wrong_family["FAMILY_BOUND"] = cast(int, wrong_family["FAMILY_BOUND"]) + 1
    wrong_source = replace(ARTIFACTS["T257"], source_sha256="0" * 64)
    return {
        "WRONG_SOURCE_SHA_REJECTED": expect_rejected(
            lambda: verify_artifact(root, wrong_source),
            "wrong source SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: nine.verify_certificate(
                certificate,
                profile_id="0" * 20,
                cap=first.cap,
                bound=first.bound,
                source=cast(str, identity["ROW_SOURCE"]),
            ),
            "wrong profile was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: nine.verify_certificate(
                certificate,
                profile_id=first.profile_id,
                cap=first.cap - 1,
                bound=first.bound,
                source=cast(str, identity["ROW_SOURCE"]),
            ),
            "wrong cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: nine.verify_certificate(
                certificate,
                profile_id=first.profile_id,
                cap=first.cap,
                bound=first.bound + 1,
                source=cast(str, identity["ROW_SOURCE"]),
            ),
            "wrong bound was accepted",
        ),
        "MISSING_PROOF_REJECTED": expect_rejected(
            lambda: nine.proof_sha256(None),
            "missing proof was accepted",
        ),
        "DUPLICATE_EVENT_HANDLED": expect_rejected(
            lambda: nine.apply_donor_events(
                after_eleven,
                [first, first],
                identities,
            ),
            "duplicate event was accepted",
        ),
        "UNRELATED_ROW_MUTATION_REJECTED": expect_rejected(
            lambda: verify_ledger_partition(frozen, changed_copy, changed_from_frozen),
            "unrelated row mutation was accepted",
        ),
        "INCORRECT_FAMILY_MAX_REJECTED": expect_rejected(
            lambda: verify_family_frontier(wrong_family, family_after),
            "incorrect family maximum was accepted",
        ),
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    frozen_route_pins = verify_frozen_route_b_sources(ROOT)
    previous, frozen, after_eleven, eleven_identity = verify_eleven_candidate(ROOT)
    require(len(frozen) == EXPECTED_ROW_COUNT, "Frozen ledger row count mismatch")

    t257_record, t257_proof, t257_blobs = verify_artifact(ROOT, ARTIFACTS["T257"])
    t243_record, t243_proof, t243_blobs = verify_artifact(ROOT, ARTIFACTS["T243"])
    pr378_record, pr378_proof, pr378_blobs = verify_artifact(ROOT, ARTIFACTS["PR378"])
    pr378_pins, pr378_certificates = verify_pr378_authority(
        ROOT, pr378_record, pr378_blobs["SOURCE"]
    )
    artifact_records = {
        "T257": (t257_record, t257_proof, t257_blobs),
        "T243": (t243_record, t243_proof, t243_blobs),
        "PR378": (pr378_record, pr378_proof, pr378_blobs),
    }

    pins: list[nine.DonorPin] = []
    identities: dict[str, dict[str, Any]] = {}
    new_route_results: dict[str, dict[str, Any]] = {}
    for event in EVENT_SPECS:
        artifact = ARTIFACTS[event.artifact_key]
        record, proof, blobs = artifact_records[event.artifact_key]
        row = after_eleven[event.profile_id]
        verify_event_proof_scope(event, record, proof, row, pr378_certificates)
        route = four.route_b_envelope(event.profile_id, event.cap)
        require(
            route["S4_BASE"] == row.s4_base and route["BOUND"] == event.expected_bound,
            f"Frozen Route-B bound mismatch: {event.profile_id}",
        )
        locator = source_locator(artifact)
        pin = nine.DonorPin(
            event_id=event.event_id,
            task_id=artifact.task_id,
            profile_id=event.profile_id,
            previous_bound=row.bound,
            previous_cap=row.cap,
            bound=cast(int, route["BOUND"]),
            cap=event.cap,
            s4_base=row.s4_base,
            head=artifact.head,
            tree=artifact.tree,
            result_path=artifact.result_path,
            result_sha256=artifact.result_sha256,
            source_path=artifact.source_path,
            source_sha256=artifact.source_sha256,
            test_path=artifact.test_path,
            test_sha256=artifact.test_sha256,
            proof_sha256=artifact.proof_sha256,
        )
        identity = {
            "EVENT_ID": event.event_id,
            "TASK_ID": artifact.task_id,
            "HEAD": artifact.head,
            "TREE": artifact.tree,
            "RESULT_PATH": artifact.result_path,
            "RESULT_SHA256": sha256(blobs["RESULT"]),
            "SOURCE_PATH": artifact.source_path,
            "SOURCE_SHA256": sha256(blobs["SOURCE"]),
            "TEST_PATH": artifact.test_path,
            "TEST_SHA256": sha256(blobs["TEST"]),
            "PROOF_FIELD": artifact.proof_fragment,
            "PROOF_SHA256": artifact.proof_sha256,
            "PROFILE_ID": event.profile_id,
            "PROOF_SCOPE": "FULL_PROFILE",
            "PROOF_SCOPE_DETAIL": event.proof_scope_detail,
            "PROOF_APPLICABILITY": event.applicability,
            "CAP_BEFORE": row.cap,
            "CAP_AFTER": event.cap,
            "BOUND_BEFORE": row.bound,
            "BOUND_AFTER": route["BOUND"],
            "S4_BASE": row.s4_base,
            "ROW_SOURCE_BEFORE": row.source,
            "ROW_SOURCE": locator,
            "ROUTE_B_RECOMPUTATION": {
                "ENGINE": "Frozen Route-B R32 plus split cross-check",
                "S4_BASE": route["S4_BASE"],
                "TERM_COUNT": route["TERM_COUNT"],
                "ARGMAX_TERM": route["ARGMAX_TERM"],
                "BOUND": route["BOUND"],
            },
        }
        pins.append(pin)
        identities[event.event_id] = identity
        new_route_results[event.event_id] = cast(
            dict[str, Any], identity["ROUTE_B_RECOMPUTATION"]
        )

    after, new_events = nine.apply_donor_events(after_eleven, pins, identities)
    verify_unique_events(new_events)
    previous_events = cast(list[dict[str, Any]], previous["EVENT_HISTORY"])
    events = previous_events + new_events
    verify_unique_events(events)
    require(
        len(previous_events) == 11 and len(new_events) == 5 and len(events) == 16,
        "event count mismatch",
    )

    old_changed = set(previous["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"])
    new_profiles = {event.profile_id for event in EVENT_SPECS}
    require(
        not (old_changed & new_profiles),
        "new proof profile duplicates an earlier changed profile",
    )
    expected_changed = old_changed | new_profiles
    changed = verify_ledger_partition(frozen, after, expected_changed)
    changed_from_eleven = verify_ledger_partition(after_eleven, after, new_profiles)
    require(len(changed) == 15 and len(changed_from_eleven) == 5, "changed profile count mismatch")
    require(len(frozen) - len(changed) == 4_632, "Frozen unchanged row count mismatch")
    require(
        len(after_eleven) - len(changed_from_eleven) == 4_642,
        "11-event unchanged row count mismatch",
    )
    for event in new_events:
        require(
            after[event["PROFILE_ID"]].source == event["SOURCE_AFTER"],
            f"row source binding mismatch: {event['PROFILE_ID']}",
        )

    before_full = four.seven.two.full_digest(frozen)
    before_bounds = four.seven.two.bounds_digest(frozen)
    after_full = four.seven.two.full_digest(after)
    after_bounds = four.seven.two.bounds_digest(after)
    bounds_projection = {
        profile_id: replace(row, source=frozen[profile_id].source)
        for profile_id, row in after.items()
    }
    projected_bounds = four.seven.two.bounds_digest(bounds_projection)
    require(before_full == four.SEVEN_ROW_FULL_DIGEST, "Frozen full digest mismatch")
    require(before_bounds == four.SEVEN_ROW_BOUNDS_DIGEST, "Frozen bounds digest mismatch")
    require(projected_bounds == after_bounds, "bounds-only projection digest mismatch")
    require(
        four.seven.two.full_digest(frozen) == four.SEVEN_ROW_FULL_DIGEST,
        "Frozen ledger changed during replay",
    )

    family_before = four.family_frontier(frozen)
    family_after_eleven = four.family_frontier(after_eleven)
    family_after = four.family_frontier(after)
    verify_family_frontier(family_after, EXPECTED_FAMILY_AFTER)
    require(
        family_before["FAMILY_BOUND"] == 313_398_532
        and family_after_eleven["FAMILY_BOUND"] == 313_395_344,
        "prior family frontier mismatch",
    )
    require(
        family_after_eleven == previous["FAMILY_AFTER"],
        "11-event family frontier differs from its source result",
    )
    resolved_above_incumbent = sum(row.bound > INCUMBENT for row in after.values())
    require(resolved_above_incumbent == 1_369, "resolved rows above incumbent mismatch")
    require(
        all(
            after[event.profile_id].source == identities[event.event_id]["ROW_SOURCE"]
            for event in EVENT_SPECS
        ),
        "new source metadata binding mismatch",
    )

    overlay = {
        "ROWS_BEFORE": len(frozen),
        "ROWS_AFTER": len(after),
        "PREVIOUS_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "UPDATE_EVENTS": len(events),
        "DISTINCT_CHANGED_PROFILE_COUNT": len(changed),
        "DISTINCT_CHANGED_PROFILES": sorted(changed),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed),
        "UNCHANGED_ROWS_FROM_ELEVEN_EVENT": len(after_eleven) - len(changed_from_eleven),
        "FULL_DIGEST_BEFORE": before_full,
        "BOUNDS_DIGEST_BEFORE": before_bounds,
        "FULL_DIGEST_AFTER": after_full,
        "BOUNDS_DIGEST_AFTER": after_bounds,
        "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": projected_bounds,
        "FULL_DIGEST_IS_ROW_SOURCE_AWARE": "YES",
        "FROZEN_LEDGER_UNCHANGED": "YES",
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "UNRELATED_ROW_MUTATION": "NONE",
    }

    caveats = dict(previous["CAVEATS"])
    caveats.update(
        {
            "T243": "VERIFIED_WITH_CAVEATS",
            "PR378": "CROSS_LINEAGE_PARTIAL",
            "PR378_CI": "FAIL",
        }
    )
    negative_validations = verify_negative_cases(
        ROOT,
        pins,
        identities,
        frozen,
        after_eleven,
        after,
        changed,
        family_after,
    )
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_16_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "ELEVEN_EVENT_HEAD_TREE": "MATCH",
            "ELEVEN_EVENT_RESULT_SHA256": "MATCH",
            "T257_DONOR_SHA": "MATCH",
            "T243_DONOR_SHA": "MATCH",
            "PR378_SOURCE_BYTES": "MATCH",
            "T243_PROOF_APPLICABILITY": "VERIFIED",
            "PR378_PROOF_APPLICABILITY": "VERIFIED_WITH_SCOPE",
            "PR378_EVALUATOR_CLOSURE": "VERIFIED_ALL_LOAD_BEARING_SOURCES",
            "FROZEN_THREE_ROW_CAP_SOURCE": "VERIFIED",
            "ALL_NEW_SOURCE_LOCATORS": "REAL_AND_RESOLVABLE",
        },
        "FROZEN_AUTHORITY": previous["FROZEN_AUTHORITY"],
        "ELEVEN_EVENT_AUTHORITY": eleven_identity,
        "FROZEN_ROUTE_B_AUTHORITY": {
            "FROZEN_HEAD": FROZEN_HEAD,
            "FROZEN_TREE": FROZEN_TREE,
            "ENGINE_WRAPPER_PATH": FOUR_ENGINE_PATH,
            "ENGINE_WRAPPER_SHA256": FOUR_ENGINE_SHA256,
            "SOURCE_PINS": frozen_route_pins,
        },
        "T257_DONOR": {
            "HEAD": T257_HEAD,
            "TREE": T257_TREE,
            "RESULT_PATH": T257_RESULT_PATH,
            "RESULT_SHA256": T257_RESULT_SHA256,
            "PROOF_SOURCE": T257_SOURCE_PATH,
            "PROOF_SHA256": T257_PROOF_SHA256,
            "PROOF_SCOPE": "FULL_PROFILE",
            "PROOF_APPLICABILITY": "VERIFIED",
        },
        "T243_DONOR": {
            "HEAD": T243_HEAD,
            "TREE": T243_TREE,
            "MATHEMATICAL_BASE_HEAD": T243_BASE_HEAD,
            "MATHEMATICAL_BASE_TREE": T243_BASE_TREE,
            "RESULT_PATH": T243_RESULT_PATH,
            "RESULT_SHA256": T243_RESULT_SHA256,
            "PROOF_FIELD": "PROOF",
            "PROOF_SHA256": T243_PROOF_SHA256,
            "PROOF_SCOPE": "EXACT_PROFILE_FULL_BOUND",
            "PROOF_APPLICABILITY": "VERIFIED",
            "ORIGINAL_FRESH_CONTEXT_VERDICT": "VERIFIED_WITH_CAVEATS",
            "ORIGINAL_JUDGE_REPORT": "NOT_RECONSTRUCTED",
            "IMPORT_POLICY": "DONOR_MODULE_NOT_IMPORTED; FROZEN_ROUTE_B_RECOMPUTED",
        },
        "PR378_AUTHORITY": {
            "HEAD": PR378_HEAD,
            "TREE": PR378_TREE,
            "RESULT_PATH": PR378_RESULT_PATH,
            "RESULT_SHA256": PR378_RESULT_SHA256,
            "SOURCE_PATH": PR378_SOURCE_PATH,
            "SOURCE_SHA256": PR378_SOURCE_SHA256,
            "TEST_PATH": PR378_TEST_PATH,
            "TEST_SHA256": PR378_TEST_SHA256,
            "PROOF_SHA256": PR378_PROOF_SHA256,
            "PROOF_APPLICABILITY": "VERIFIED_WITH_SCOPE",
            "CROSS_LINEAGE_VERDICT": "PARTIAL",
            "ORIGINAL_CI": "FAIL",
            "EVALUATOR_CLOSURE": {
                "LOAD_BEARING_SOURCE_COUNT": len(pr378_pins),
                "CHECKED_AGAINST": {
                    "PR_HEAD": PR378_HEAD,
                    "MATHEMATICAL_BASE_HEAD": PR378_BASE_HEAD,
                    "FROZEN_HEAD": FROZEN_HEAD,
                },
                "ALL_SOURCE_PINS_MATCH": "YES",
                "SOURCE_PINS": pr378_pins,
            },
        },
        "DONOR_IDENTITIES": identities,
        "ROUTE_B_RECOMPUTATIONS": new_route_results,
        "UPDATE_EVENTS": len(events),
        "PREVIOUS_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "DISTINCT_CHANGED_PROFILES": len(changed),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed),
        "UNCHANGED_ROWS_FROM_ELEVEN_EVENT": len(after_eleven) - len(changed_from_eleven),
        "EVENT_HISTORY": events,
        "LEDGER_OVERLAY": overlay,
        "ROW_SOURCE_METADATA_VERIFIED": "YES",
        "OLD_LEDGER_UNCHANGED": "YES",
        "FROZEN_LEDGER_MUTATED": "NO",
        "DONOR_WORKTREES_MUTATED": "NO",
        "CURSOR_PRESERVED": "YES",
        "NEW_FULL_DIGEST": after_full,
        "NEW_BOUNDS_DIGEST": after_bounds,
        "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": projected_bounds,
        "FAMILY_BEFORE": family_before,
        "FAMILY_AFTER_ELEVEN_EVENT": family_after_eleven,
        "FAMILY_AFTER": family_after,
        "FAMILY_DELTA_FROM_FROZEN": family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"],
        "FAMILY_DELTA_FROM_ELEVEN_EVENT": (
            family_after_eleven["FAMILY_BOUND"] - family_after["FAMILY_BOUND"]
        ),
        "RESOLVED_ROWS_ABOVE_INCUMBENT": resolved_above_incumbent,
        "UNRESOLVED_CURSOR": previous["UNRESOLVED_CURSOR"],
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CAVEATS": caveats,
        "HISTORICAL_AUTHORITY_CAVEATS": previous["HISTORICAL_AUTHORITY_CAVEATS"],
        "NEGATIVE_VALIDATIONS": negative_validations,
        "FOCUSED_TEST_PATH": (
            "tests/unit/test_b649_sixteen_event_frozen_lineage_local_authority_r1.py"
        ),
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER": "NOT_RUN",
        "PR378_CI": "FAIL",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    return result, frozen, after


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        previous = json_object(path.read_bytes(), "existing result artifact is invalid JSON")
        require(previous.get("TASK_ID") == TASK_ID, "refusing to overwrite another result artifact")
    path.write_bytes(raw)
    require(path.read_bytes() == raw, "result read-after-write mismatch")
    return sha256(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result, _frozen, _after = build_candidate()
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
                "UPDATE_EVENTS": result["UPDATE_EVENTS"],
                "DISTINCT_CHANGED_PROFILES": result["DISTINCT_CHANGED_PROFILES"],
                "NEW_FULL_DIGEST": result["NEW_FULL_DIGEST"],
                "NEW_BOUNDS_DIGEST": result["NEW_BOUNDS_DIGEST"],
                "FAMILY_AFTER": result["FAMILY_AFTER"],
                "AUTHORITY_GATES": result["AUTHORITY_GATES"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
