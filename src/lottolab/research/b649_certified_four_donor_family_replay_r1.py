"""Replay four formally judged exact-profile certificates into a local Family candidate.

The replay starts from the immutable A/B Family result at ``BASE_HEAD`` and
changes exactly four resolved profile bounds. It preserves the complete cursor
projection and inherited dispositions. This is a local candidate only; it does
not establish legal attainment, a global optimum, or formal Family adoption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

TASK_ID = "B649_CERTIFIED_FOUR_DONOR_FAMILY_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
BASE_HEAD = "9acea1331e021a9623fa593997d90cfc89a69136"
BASE_TREE = "de577e8d6f3ccbe52e663c96ee1528c95a0ee7ec"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-ab-t249-t260k4-composition-r1-result.json"
)
BASE_RESULT_SHA256 = "9fbe17d020573835cd69f16296fee224ff4f83aef8b3e7a644f2ffaabdfe92c9"
RESULT_PATH = "docs/research/matrix-native-results/b649-certified-four-donor-family-r1-result.json"
EVIDENCE_PATH = Path(
    "docs/research/matrix-native-results/b649-certified-four-donor-family-r1-evidence"
)


@dataclass(frozen=True)
class DonorPin:
    key: str
    profile: str
    old_bound: int
    bound: int
    head: str
    tree: str
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    judge_tree: str
    judge_report_sha256: str
    judge_evidence_file: str | None
    reviewed_head: str | None = None
    reviewed_input_tree: str | None = None


DONORS: tuple[DonorPin, ...] = (
    DonorPin(
        key="T257",
        profile="66665555555321100000",
        old_bound=313391636,
        bound=313329096,
        head="bbfee5c20258fe69dbe48f070f86c6afa0020416",
        tree="6925613dda4a93bca22b91d74f5084e21d27f031",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-min-s2-666655555553211-t257-formal-r2-result.json"
        ),
        result_sha256="f2a2a48ff023dbb6a259911fb8b01b9a318b0982b5681f479549d35fdb1c3b42",
        source_path="src/lottolab/research/b649_min_s2_666655555553211_t257_formal_r2.py",
        source_sha256="3d87309630afe1e2d145356ca44faf965000e141ede48a5482ba4dfd22db0448",
        test_path="tests/unit/test_b649_min_s2_666655555553211_t257_formal_r2.py",
        test_sha256="1d2dd3c3365f4a81acf2512b6fe22fdb83afdb0768a81a58466871fa6f904340",
        judge_tree="6925613dda4a93bca22b91d74f5084e21d27f031",
        judge_report_sha256="dd8cdc8ded41ecf93a8846aea1ae226979eb18d6c8a54f51c51b0e33066403e2",
        judge_evidence_file="t257-certified-commit-message.txt",
    ),
    DonorPin(
        key="T237",
        profile="65555555555432100000",
        old_bound=313391560,
        bound=313122700,
        head="f30863f708e7f4d026d5c99e9b79529e38f9be92",
        tree="a9977cc6451693ad8badd18d0bd7e5e9bb9c709e",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-min-s2-t257-t237-joint-exact-authority-r1-result.json"
        ),
        result_sha256="4aa6f817220db51a3648df3dcbe10efbd0d0ad614afa4223404e7dcd62ab01ac",
        source_path="src/lottolab/research/b649_min_s2_t257_t237_joint_exact_authority_r1.py",
        source_sha256="d8d286d021cacba5dc55803c5db5ba8cbe00a502a9916191be540755d00af131",
        test_path="tests/unit/test_b649_min_s2_t257_t237_joint_exact_authority_r1.py",
        test_sha256="cd1f2fa08bfd9215bfa46a8dd189a1baefa177aa74f9b420ec8ae759b907bdf7",
        judge_tree="a9977cc6451693ad8badd18d0bd7e5e9bb9c709e",
        judge_report_sha256="bbed01db2176856535aacc5915a2989727bd8889bb3276e01a3c5c08cafae595",
        judge_evidence_file="t237-judge-report.json",
    ),
    DonorPin(
        key="W821_R2",
        profile="65555555555511111000",
        old_bound=313391172,
        bound=313364480,
        head="4b7a20446743f8e060c85c9002cd1c137f90b398",
        tree="89e6e1175b7d7b0526a25c89136cb88a2e878e80",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-next-unique-max-owner-w821-z3-resume-r2-result.json"
        ),
        result_sha256="2c8dee1b784aa674b80b52d76f600e5d50fbfc98ed15a0a3cb87ea57828ab96e",
        source_path="src/lottolab/research/b649_next_unique_max_owner_w821_z3_resume_r2.py",
        source_sha256="0bb936a694b433cb88e91667e6e7885f3579a4c17beced97393a317dbe42ec9e",
        test_path="tests/unit/test_b649_next_unique_max_owner_w821_z3_resume_r2.py",
        test_sha256="3b51007a8ea130b743c99b8fc55c4df83abb22233f7bbddbac366a689f067c22",
        judge_tree="89e6e1175b7d7b0526a25c89136cb88a2e878e80",
        judge_report_sha256="cadf94ef1a021ca6b453edfe3da45c31b0b87c5f8cd4e2894ddf7c78950de16a",
        judge_evidence_file="w821-fresh-judge-report.md",
        reviewed_head="1f8c3334bd27ca5fb37a5dd7958437d15d901e73",
        reviewed_input_tree="dc3cc48f934c627ff4ec041f1b21cbb48458ba52",
    ),
    DonorPin(
        key="T208",
        profile="55555555555443000000",
        old_bound=313390396,
        bound=312835000,
        head="6a7178354c302daa0ea98b638a687a043cade4d1",
        tree="6745a903fb1dabbea3939212fad0613020429d26",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-s3-t208-exact-profile-certificate-r2-result.json"
        ),
        result_sha256="7f76e162696850f80c68e25cc4dfcf288aa164003bf513c2d85e94f90955ae3b",
        source_path="src/lottolab/research/b649_s3_t208_exact_profile_certificate_r2.py",
        source_sha256="33da4fad8af7d794c42de10f4f4da76b3428dfacada4851da2527eea2184079c",
        test_path="tests/unit/test_b649_s3_t208_exact_profile_certificate_r2.py",
        test_sha256="5de05d84e71ad88a69228665bf864f20436567b1f9f64a74181d8ca6c610a7bf",
        judge_tree="6745a903fb1dabbea3939212fad0613020429d26",
        judge_report_sha256="12b0dace8690fbae019a8a0d262f96d695251abf115ddd457206b55dbb8a4e20",
        judge_evidence_file="t208-judge-report.json",
    ),
)

INCUMBENT = 313263888
PROFILE_PATTERN = re.compile(r"[0-9]{20}\Z")


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def document(value: object, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label}: expected object")
    return cast(dict[str, Any], value)


def integer(value: object, label: str) -> int:
    require(type(value) is int, f"{label}: expected integer")
    return cast(int, value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}: invalid JSON: {error}") from error
    return document(parsed, label)


def git_bytes(*args: str) -> bytes:
    env = {
        **os.environ,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    return subprocess.check_output(["git", "-C", str(ROOT), *args], env=env)


def git_text(*args: str) -> str:
    return git_bytes(*args).decode().strip()


def frozen_blob(head: str, path: str, expected_sha256: str | None = None) -> bytes:
    entries = git_bytes("ls-tree", head, "--", path).decode().splitlines()
    require(len(entries) == 1, f"{head}:{path}: expected one tree entry")
    metadata, separator, found_path = entries[0].partition("\t")
    require(separator == "\t" and found_path == path, f"{head}:{path}: path mismatch")
    require(metadata.startswith("100644 blob "), f"{head}:{path}: unsafe blob mode")
    raw = git_bytes("cat-file", "blob", f"{head}:{path}")
    if expected_sha256 is not None:
        require(sha256(raw) == expected_sha256, f"{head}:{path}: SHA256 mismatch")
    return raw


def safe_working_file(path: str) -> bytes:
    target = ROOT / path
    require(target.is_file() and not target.is_symlink(), f"unsafe working file: {path}")
    return target.read_bytes()


def safe_evidence_file(name: str) -> bytes:
    require(Path(name).name == name, "evidence filename must be a single component")
    target = ROOT / EVIDENCE_PATH / name
    require(target.is_file() and not target.is_symlink(), f"missing/unsafe evidence: {name}")
    return target.read_bytes()


def git_commit_exists(head: str) -> bool:
    env = {
        **os.environ,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    result = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-e", f"{head}^{{commit}}"],
        capture_output=True,
        env=env,
    )
    return result.returncode == 0


def load_donor_blob(pin: DonorPin, path: str, expected_sha256: str) -> bytes:
    filename = Path(path).name
    raw = safe_evidence_file(filename)
    require(sha256(raw) == expected_sha256, f"{pin.key}:{filename}: SHA256 mismatch")
    if git_commit_exists(pin.head):
        git_raw = frozen_blob(pin.head, path, expected_sha256)
        require(git_raw == raw, f"{pin.key}:{path}: evidence file differs from git blob")
    return raw


def _profile_bounds(value: object, label: str) -> dict[str, int]:
    raw = document(value, label)
    result: dict[str, int] = {}
    for profile, bound in raw.items():
        require(
            PROFILE_PATTERN.fullmatch(profile) is not None, f"{label}: invalid profile {profile}"
        )
        result[profile] = integer(bound, f"{label}[{profile}]")
    return result


def family_summary(
    rows: Mapping[str, int], cursor: Mapping[str, int], incumbent: int
) -> dict[str, Any]:
    require(not (set(rows) & set(cursor)), "resolved/cursor profile overlap")
    entries = {**rows, **cursor}
    require(bool(entries), "empty Family projection")
    maximum = max(entries.values())
    owners = sorted(profile for profile, bound in entries.items() if bound == maximum)
    next_bound = max((bound for bound in entries.values() if bound < maximum), default=None)
    next_owners = (
        sorted(profile for profile, bound in entries.items() if bound == next_bound)
        if next_bound is not None
        else []
    )
    return {
        "FAMILY_UB": maximum,
        "ALL_OWNER_IDS": owners,
        "NEXT_DISTINCT_BOUND": next_bound,
        "NEXT_DISTINCT_OWNER_IDS": next_owners,
        "STILL_OPEN_PROFILES": sum(bound > incumbent for bound in entries.values()),
        "TOTAL_PROFILES": len(entries),
        "RESOLVED_ROWS": len(rows),
        "CURSOR_PROFILES": len(cursor),
    }


def independent_family_summary(
    rows: Mapping[str, int], cursor: Mapping[str, int], incumbent: int
) -> dict[str, Any]:
    require(not (set(rows) & set(cursor)), "independent replay: resolved/cursor overlap")
    ordered = sorted([*rows.items(), *cursor.items()], key=lambda item: (-item[1], item[0]))
    require(bool(ordered), "independent replay: empty Family projection")
    maximum = ordered[0][1]
    owners = sorted(profile for profile, bound in ordered if bound == maximum)
    next_bound = next((bound for _, bound in ordered if bound < maximum), None)
    next_owners = sorted(profile for profile, bound in ordered if bound == next_bound)
    return {
        "FAMILY_UB": maximum,
        "ALL_OWNER_IDS": owners,
        "NEXT_DISTINCT_BOUND": next_bound,
        "NEXT_DISTINCT_OWNER_IDS": next_owners,
        "STILL_OPEN_PROFILES": sum(bound > incumbent for _, bound in ordered),
        "TOTAL_PROFILES": len(ordered),
        "RESOLVED_ROWS": len(rows),
        "CURSOR_PROFILES": len(cursor),
    }


def _load_base() -> tuple[dict[str, Any], dict[str, int], dict[str, int]]:
    require(git_text("rev-parse", "--show-toplevel") == str(ROOT), "wrong repository root")
    require(git_text("rev-parse", f"{BASE_HEAD}^{{tree}}") == BASE_TREE, "Base tree mismatch")
    raw = frozen_blob(BASE_HEAD, BASE_RESULT_PATH, BASE_RESULT_SHA256)
    require(
        safe_working_file(BASE_RESULT_PATH) == raw, "working Base result differs from pinned bytes"
    )
    base = parse_json(raw, "Base result")
    rows = _profile_bounds(base.get("RESOLVED_ROW_BOUNDS"), "Base resolved rows")
    require(len(rows) == 4647, "Base resolved row count")
    cursor = document(base.get("CURSOR"), "Base cursor")
    cursor_ids = cursor.get("PROFILE_IDS")
    require(isinstance(cursor_ids, list), "Base cursor PROFILE_IDS")
    ids = cast(list[object], cursor_ids)
    require(len(ids) == 197, "Base cursor profile count")
    require(all(isinstance(profile, str) for profile in ids), "Base cursor profile identity")
    profile_ids = cast(list[str], ids)
    require(len(profile_ids) == len(set(profile_ids)), "duplicate Base cursor profile")
    require(
        all(PROFILE_PATTERN.fullmatch(profile) is not None for profile in profile_ids),
        "invalid cursor ID",
    )
    projection = _profile_bounds(cursor.get("COARSE_BOUND_PROJECTION"), "Base cursor projection")
    require(set(projection) == set(profile_ids), "Base cursor identity/projection mismatch")
    require(not (set(rows) & set(projection)), "Base resolved/cursor profile overlap")
    require(
        integer(cursor.get("PROFILE_COUNT"), "Base cursor PROFILE_COUNT") == 197,
        "cursor count mismatch",
    )
    require(
        integer(base.get("INCUMBENT"), "Base incumbent") == INCUMBENT, "Base incumbent mismatch"
    )
    summary = family_summary(rows, projection, INCUMBENT)
    require(summary["FAMILY_UB"] == 313391636, "Base Family UB mismatch")
    require(summary["TOTAL_PROFILES"] == 4844, "Base complete Family coverage")
    return base, rows, projection


def _evidence_json(filename: str, expected_sha256: str) -> dict[str, Any]:
    raw = safe_evidence_file(filename)
    require(sha256(raw) == expected_sha256, f"Judge evidence SHA256 mismatch: {filename}")
    return parse_json(raw, filename)


def _judge_summary(pin: DonorPin, doc: dict[str, Any]) -> dict[str, Any]:
    if pin.key == "T257":
        message = safe_evidence_file(cast(str, pin.judge_evidence_file))
        if git_commit_exists(pin.head):
            require(
                message == git_bytes("show", "-s", "--format=%B", pin.head),
                "T257 commit-message receipt drift",
            )
        text = message.decode()
        require(
            "Fresh-context scientific Judge: VERIFIED_WITH_CAVEATS; G01-G17 PASS." in text,
            "T257 Judge verdict",
        )
        require(f"Exact judged tree: {pin.judge_tree}" in text, "T257 reviewed tree")
        require(pin.judge_report_sha256 in text, "T257 sealed Judge report digest")
        return {
            "VERDICT": "VERIFIED_WITH_CAVEATS",
            "JUDGE_MODE": "FRESH_CONTEXT",
            "REVIEWED_TREE": pin.judge_tree,
            "REPORT_SHA256": pin.judge_report_sha256,
            "EVIDENCE": "immutable donor commit message",
            "LIMITATION": (
                "Final G18/committed-tree/R15 disposition is external in task-evidence; "
                "report body was not separately re-read for this integration."
            ),
        }

    if pin.key == "T237":
        judge = _evidence_json(cast(str, pin.judge_evidence_file), pin.judge_report_sha256)
        require(judge.get("VERDICT") == "VERIFIED_WITH_CAVEATS", "T237 Judge verdict")
        require(judge.get("JUDGE_MODE") == "FRESH_CONTEXT", "T237 Judge mode")
        require(judge.get("JUDGED_HEAD") == pin.head, "T237 judged commit")
        require(judge.get("JUDGED_TREE") == pin.judge_tree == pin.tree, "T237 judged tree")
        require(judge.get("FINAL_COMMITTED_TREE") == pin.tree, "T237 committed tree")
        require(judge.get("RESULT_SHA256") == pin.result_sha256, "T237 Judge result SHA256")
        require(judge.get("COMMIT_TREE_MATCH") == "YES", "T237 Judge commit/tree equality")
        return {
            "VERDICT": judge["VERDICT"],
            "JUDGE_MODE": judge["JUDGE_MODE"],
            "REVIEWED_HEAD": judge["JUDGED_HEAD"],
            "REVIEWED_TREE": judge["JUDGED_TREE"],
            "RESULT_SHA256": judge["RESULT_SHA256"],
            "REPORT_SHA256": pin.judge_report_sha256,
            "CAVEATS": judge.get("CAVEATS", []),
        }

    if pin.key == "W821_R2":
        report = safe_evidence_file(cast(str, pin.judge_evidence_file))
        require(sha256(report) == pin.judge_report_sha256, "W821 Judge report SHA256")
        text = report.decode()
        require(text.startswith("VERIFIED_WITH_CAVEATS"), "W821 Judge verdict")
        require("JUDGE_MODE: FRESH_CONTEXT" in text, "W821 Judge mode")
        require(f"HEAD: {pin.reviewed_head}" in text, "W821 reviewed precommit HEAD")
        require(f"Input tree: {pin.reviewed_input_tree}" in text, "W821 pre-review input tree")
        require(
            f"Reviewed immutable candidate TREE: {pin.judge_tree}" in text,
            "W821 reviewed candidate tree",
        )
        if git_commit_exists(pin.head):
            require(
                git_text("rev-parse", f"{pin.head}^") == pin.reviewed_head,
                "W821 final commit parent",
            )
            require(
                git_text("rev-parse", f"{pin.reviewed_head}^{{tree}}") == pin.reviewed_input_tree,
                "W821 pre-review input identity",
            )

        limitations_start = text.find("Limitations:")
        require(limitations_start >= 0, "W821 Judge limitations missing")
        limitations_end = text.find("\n\n", limitations_start)
        limitations = text[limitations_start : limitations_end if limitations_end >= 0 else None]
        require(
            "Conditional historical exclusions and Base authority are inherited" in limitations,
            "W821 caveat binding",
        )
        require("No realizability or optimality claim" in limitations, "W821 limitation binding")
        return {
            "VERDICT": "VERIFIED_WITH_CAVEATS",
            "JUDGE_MODE": "FRESH_CONTEXT",
            "REVIEWED_HEAD": pin.reviewed_head,
            "REVIEWED_TREE": pin.judge_tree,
            "FINAL_CERTIFIED_HEAD": pin.head,
            "FINAL_CERTIFIED_TREE": pin.tree,
            "REPORT_SHA256": pin.judge_report_sha256,
            "LIMITATIONS": limitations,
        }

    if pin.key == "T208":
        judge = _evidence_json(cast(str, pin.judge_evidence_file), pin.judge_report_sha256)
        clarification = _evidence_json(
            "t208-source-clarification.json",
            "7b2f52c99430985fa74de5fa95bd062542944104467f4d33fbad415d6663184d",
        )
        clarification_identity = document(
            clarification.get("SOURCE_IDENTITY"), "T208 clarification identity"
        )
        owner_clarification = document(
            clarification.get("OWNER_CLARIFICATION"), "T208 Owner clarification"
        )
        require(judge.get("VERDICT") == "VERIFIED_WITH_CAVEATS", "T208 Judge verdict")
        require(judge.get("JUDGE_MODE") == "FRESH_CONTEXT", "T208 Judge mode")
        require(judge.get("RESULT_SHA256") == pin.result_sha256, "T208 Judge result SHA256")
        require(judge.get("JUDGED_HEAD") == pin.head, "T208 Judge reviewed HEAD")
        require(judge.get("JUDGED_TREE") == pin.tree, "T208 Judge reviewed tree")
        require(judge.get("FINAL_LOCAL_COMMIT") == pin.head, "T208 final committed HEAD")
        require(judge.get("FINAL_COMMITTED_TREE") == pin.tree, "T208 final committed tree")
        require(judge.get("COMMIT_TREE_MATCH") == "YES", "T208 Judge commit/tree equality")
        require(clarification_identity.get("HEAD") == pin.head, "T208 clarification HEAD")
        require(clarification_identity.get("TREE") == pin.tree, "T208 clarification tree")
        require(
            clarification_identity.get("RESULT_SHA256") == pin.result_sha256,
            "T208 clarification result SHA256",
        )
        require(
            owner_clarification.get("CERTIFICATE_SOURCE_MODE") == "INDEPENDENT_REDERIVATION",
            "T208 source mode",
        )
        require(
            owner_clarification.get("ORIGINAL_RESEARCH_CONVERSATION_ID") == "UNKNOWN_NOT_VERIFIED",
            "T208 history caveat",
        )
        require(clarification_identity.get("HEAD") == pin.head, "T208 clarification candidate")
        return {
            "VERDICT": judge["VERDICT"],
            "JUDGE_MODE": judge["JUDGE_MODE"],
            "REVIEWED_HEAD": judge["JUDGED_HEAD"],
            "REVIEWED_TREE": judge["JUDGED_TREE"],
            "RESULT_SHA256": judge["RESULT_SHA256"],
            "REPORT_SHA256": pin.judge_report_sha256,
            "SOURCE_CLARIFICATION_SHA256": (
                "7b2f52c99430985fa74de5fa95bd062542944104467f4d33fbad415d6663184d"
            ),
            "CERTIFICATE_SOURCE_MODE": owner_clarification["CERTIFICATE_SOURCE_MODE"],
            "ORIGINAL_RESEARCH_CONVERSATION_ID": owner_clarification[
                "ORIGINAL_RESEARCH_CONVERSATION_ID"
            ],
            "CAVEATS": judge.get("CAVEATS", []),
        }

    raise ValueError(f"unknown donor key: {pin.key}")


def _donor_record(pin: DonorPin) -> dict[str, Any]:
    if git_commit_exists(pin.head):
        require(
            git_text("rev-parse", f"{pin.head}^{{tree}}") == pin.tree,
            f"{pin.key} commit/tree mismatch",
        )
    result_raw = load_donor_blob(pin, pin.result_path, pin.result_sha256)
    donor = parse_json(result_raw, f"{pin.key} result")
    load_donor_blob(pin, pin.source_path, pin.source_sha256)
    load_donor_blob(pin, pin.test_path, pin.test_sha256)
    require(donor.get("SOURCE_SHA256") == pin.source_sha256, f"{pin.key} source/result binding")
    require(donor.get("TEST_SHA256") == pin.test_sha256, f"{pin.key} test/result binding")

    if pin.key in {"T257", "T237"}:
        require(donor.get("BASE_HEAD") == BASE_HEAD, f"{pin.key} Base HEAD binding")
        require(donor.get("BASE_TREE") == BASE_TREE, f"{pin.key} Base tree binding")
        require(
            donor.get("BASE_RESULT_SHA256") == BASE_RESULT_SHA256, f"{pin.key} Base result binding"
        )
    elif pin.key == "T208":
        base_identity = document(donor.get("BASE"), "T208 Base identity")
        require(base_identity.get("HEAD") == BASE_HEAD, "T208 Base HEAD binding")
        require(base_identity.get("TREE") == BASE_TREE, "T208 Base tree binding")
        require(
            base_identity.get("RESULT_SHA256") == BASE_RESULT_SHA256, "T208 Base result binding"
        )

    if pin.key == "T257":
        profile = donor.get("TARGET_PROFILE")
        bound = donor.get("FULL_PROFILE_BOUND")
        caveats = donor.get("INHERITED_CAVEATS_AND_STATUS_VERBATIM")
        certificate_base: object = {
            "HEAD": donor.get("BASE_HEAD"),
            "TREE": donor.get("BASE_TREE"),
            "RESULT_SHA256": donor.get("BASE_RESULT_SHA256"),
        }
        require(
            donor.get("TASK_STATUS") == "PROFILE_CERTIFICATE; FRESH_JUDGE_AND_LIFECYCLE_EXTERNAL",
            "T257 pre-Judge disposition",
        )
    elif pin.key == "T237":
        profile = donor.get("T237_PROFILE")
        bound = donor.get("NEW_FULL_PROFILE_BOUND")
        caveats = donor.get("INHERITED_CAVEATS_AND_STATUS_VERBATIM")
        certificate_base = {
            "HEAD": donor.get("BASE_HEAD"),
            "TREE": donor.get("BASE_TREE"),
            "RESULT_SHA256": donor.get("BASE_RESULT_SHA256"),
        }
        require(
            donor.get("TASK_STATUS")
            == "DETERMINISTIC_CERTIFICATE_PENDING_FOCUSED_CHECKS_FRESH_JUDGE_AND_LIFECYCLE",
            "T237 pre-Judge disposition",
        )
    elif pin.key == "W821_R2":
        profile = donor.get("PROFILE_ID")
        bound = donor.get("NEW_BOUND")
        caveats = {
            "INHERITED_CAVEATS_AND_STATUS_VERBATIM": donor.get(
                "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
            ),
            "INHERITED_CAVEATS_REFERENCE": donor.get("INHERITED_CAVEATS_REFERENCE"),
            "INHERITED_EXCLUSION": donor.get("INHERITED_EXCLUSION"),
        }
        certificate_base = donor.get("MATHEMATICAL_BASE")
        require(donor.get("TASK_STATUS") == "PROVEN_FAMILY_GAIN", "W821 certificate status")
        exclusion = document(donor.get("INHERITED_EXCLUSION"), "W821 inherited exclusion")
        require(exclusion.get("RECERTIFIED_THIS_ROUND") is False, "W821 exclusion caveat")
        require(
            exclusion.get("SCOPE") == "CONDITIONAL_ON_THE_ORIGINAL_NECESSARY_CONDITION_SCREEN",
            "W821 exclusion scope",
        )
    else:
        facts = document(donor.get("FACTS"), "T208 certificate facts")
        profile = facts.get("PROFILE")
        bound = donor.get("FULL_PROFILE_BOUND")
        caveats = {
            "JUDGE_CAVEATS": _evidence_json("t208-judge-report.json", pin.judge_report_sha256).get(
                "CAVEATS", []
            ),
            "SOURCE_CLARIFICATION": _evidence_json(
                "t208-source-clarification.json",
                "7b2f52c99430985fa74de5fa95bd062542944104467f4d33fbad415d6663184d",
            ).get("OWNER_CLARIFICATION"),
        }
        certificate_base = donor.get("BASE")

    require(profile == pin.profile, f"{pin.key} exact profile identity")
    require(integer(bound, f"{pin.key} bound") == pin.bound, f"{pin.key} certified bound")
    judge = _judge_summary(pin, donor)
    return {
        "DONOR": pin.key,
        "PROFILE": pin.profile,
        "OLD_BASE_BOUND": pin.old_bound,
        "CERTIFIED_BOUND": pin.bound,
        "PROFILE_GAIN": pin.old_bound - pin.bound,
        "CERTIFIED_HEAD": pin.head,
        "CERTIFIED_TREE": pin.tree,
        "RESULT_PATH": pin.result_path,
        "RESULT_SHA256": pin.result_sha256,
        "SOURCE_PATH": pin.source_path,
        "SOURCE_SHA256": pin.source_sha256,
        "TEST_PATH": pin.test_path,
        "TEST_SHA256": pin.test_sha256,
        "CERTIFICATE_INPUT_BASE": certificate_base,
        "JUDGE": judge,
        "INHERITED_CAVEATS_AND_DISPOSITIONS": caveats,
    }


def compute_result() -> dict[str, Any]:
    base, original_rows, cursor = _load_base()
    donor_records = [_donor_record(pin) for pin in DONORS]
    require(
        len({pin.profile for pin in DONORS}) == len(DONORS), "duplicate donor profile assignment"
    )
    updated_rows = dict(original_rows)
    updates: dict[str, int] = {}
    for pin in DONORS:
        require(
            original_rows.get(pin.profile) == pin.old_bound, f"{pin.key} old Base bound mismatch"
        )
        updated_rows[pin.profile] = pin.bound
        updates[pin.profile] = pin.bound

    changed_profiles = sorted(
        profile for profile in original_rows if updated_rows[profile] != original_rows[profile]
    )
    require(
        changed_profiles == sorted(updates),
        "authorized donor changes differ from resolved ledger changes",
    )
    unchanged_rows = {
        profile: bound
        for profile, bound in sorted(original_rows.items())
        if profile not in set(changed_profiles)
    }
    require(len(unchanged_rows) == 4643, "unchanged resolved row count")

    before = family_summary(original_rows, cursor, INCUMBENT)
    after = family_summary(updated_rows, cursor, INCUMBENT)
    independent = independent_family_summary(updated_rows, cursor, INCUMBENT)
    require(after == independent, "independent Family replay mismatch")

    base_caveats = base.get("INHERITED_CAVEATS_AND_STATUS_VERBATIM")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "CERTIFIED_LOCAL_FAMILY_CANDIDATE_PENDING_FRESH_JUDGE; NOT_FORMAL_FAMILY_AUTHORITY"
        ),
        "BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": BASE_RESULT_SHA256,
            "FAMILY_UB": before["FAMILY_UB"],
            "INCUMBENT": INCUMBENT,
            "RESOLVED_ROWS": len(original_rows),
            "CURSOR_PROFILES": len(cursor),
        },
        "DONORS": donor_records,
        "PROFILE_LEVEL_GAINS": [
            {
                "PROFILE": pin.profile,
                "OLD_BOUND": pin.old_bound,
                "NEW_BOUND": pin.bound,
                "GAIN": pin.old_bound - pin.bound,
            }
            for pin in DONORS
        ],
        "RESOLVED_LEDGER": {
            "ROW_BOUNDS": updated_rows,
            "UPDATED_PROFILE_BOUNDS": updates,
            "UPDATED_ROWS": len(changed_profiles),
            "UNCHANGED_ROWS": len(unchanged_rows),
            "UNCHANGED_ROWS_SHA256": sha256(render(unchanged_rows)),
        },
        "CURSOR": {
            "PROFILE_COUNT": len(cursor),
            "PROFILE_BOUNDS": cursor,
            "SOURCE_CURSOR": base["CURSOR"],
            "SOURCE_CURSOR_SHA256": sha256(render(base["CURSOR"])),
            "UNCHANGED": True,
        },
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_GAIN_FROM_BASE": before["FAMILY_UB"] - after["FAMILY_UB"],
        "INDEPENDENT_REPLAY": {
            "METHOD_1": "direct max, complete owner scan, and second distinct bound scan",
            "METHOD_2": "descending sort of all resolved and cursor profile pairs",
            "MATCH": after == independent,
            "FAMILY_SUMMARY": independent,
        },
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": {
            "BASE": base_caveats,
            "DONORS": {
                record["DONOR"]: record["INHERITED_CAVEATS_AND_DISPOSITIONS"]
                for record in donor_records
            },
            "NO_UPGRADE_POLICY": (
                "Original dispositions and caveats retain their stated scope; this composition "
                "makes no mathematical re-certification of inherited exclusions."
            ),
        },
        "LIMITS": {
            "LEGAL_ATTAINMENT": "UNKNOWN",
            "GLOBAL_K20_OPTIMUM": "UNKNOWN",
            "HEAVY_SOLVER_STARTED_FOR_INTEGRATION": "NO",
            "FORMAL_MAIN_FAMILY_ADOPTION": "NOT_DONE",
            "T217_INTEGRATED": "NO",
            "W832_INTEGRATED": "NO",
            "CURSOR30_INTEGRATED": "NO",
            "REMOTE_WRITE": "NO",
            "PUSH_PR_MERGE": "NOT_AUTHORIZED_NOT_RUN",
        },
    }


def _verify_against(candidate: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    require(
        dict(candidate) == dict(expected),
        "candidate result differs from deterministic four-donor replay",
    )


def verify_result(candidate: Mapping[str, Any]) -> None:
    _verify_against(candidate, compute_result())


def verify_result_file() -> dict[str, Any]:
    raw = safe_working_file(RESULT_PATH)
    candidate = parse_json(raw, "candidate result")
    verify_result(candidate)
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-result", action="store_true")
    mode.add_argument("--verify-result", action="store_true")
    args = parser.parse_args()

    result = compute_result()
    payload = render(result)
    target = ROOT / RESULT_PATH
    if args.write_result:
        require(
            not target.exists() and not target.is_symlink(),
            "result exists; read before replacement",
        )
        target.write_bytes(payload)
    else:
        candidate = parse_json(safe_working_file(RESULT_PATH), "candidate result")
        _verify_against(candidate, result)
        require(
            safe_working_file(RESULT_PATH) == payload, "candidate result bytes are not canonical"
        )
    print(
        json.dumps(
            {
                "RESULT_SHA256": sha256(payload),
                "BASE_FAMILY_UB": result["BASE"]["FAMILY_UB"],
                "FAMILY_AFTER": result["FAMILY_AFTER"],
                "FAMILY_GAIN_FROM_BASE": result["FAMILY_GAIN_FROM_BASE"],
                "DONOR_COUNT": len(result["DONORS"]),
                "UPDATED_ROWS": result["RESOLVED_LEDGER"]["UPDATED_ROWS"],
                "UNCHANGED_ROWS": result["RESOLVED_LEDGER"]["UNCHANGED_ROWS"],
                "CURSOR_PROFILES": result["CURSOR"]["PROFILE_COUNT"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
