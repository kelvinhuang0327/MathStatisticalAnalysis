"""Adapt the sealed four-donor Family result to the existing successor schema.

This module only validates pinned source bytes, projects the verified result
into the established row/cursor contract, and audits the two fixed ledgers.
It does not implement or alter the Family mathematics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from . import b649_certified_four_donor_family_replay_r1 as family_replay
from . import b649_min_s2_owner_ab_t249_t260k4_composition_r1 as successor_consumer

type Document = dict[str, object]

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_FOUR_DONOR_FAMILY_SCHEMA_SUCCESSOR_R1"
TASK_STATUS = "LOCAL_AUTHORITY_SUCCESSOR_CANDIDATE"
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-four-donor-family-successor-r1-result.json"
)
SOURCE_PATH = "src/lottolab/research/b649_four_donor_family_successor_r1.py"
TEST_PATH = "tests/unit/test_b649_four_donor_family_successor_r1.py"

STAGING_HEAD = "37eaf54bc2d0bfc85bde3667731cc470dfb18f54"
STAGING_TREE = "852033548b9fd0c40392fcbd5a634656c973526a"
PINNED_MAIN_HEAD = "e2429e7a4a184016af755be1c75a4c84c9d5b526"
PINNED_MAIN_TREE = "0c4180e831ebb9a1bf8b22007e39fce8a313a41c"
SCIENCE_BASE_HEAD = "9acea1331e021a9623fa593997d90cfc89a69136"
SCIENCE_BASE_TREE = "de577e8d6f3ccbe52e663c96ee1528c95a0ee7ec"
PORTABLE_CANDIDATE_HEAD = "26c504a1747c61f461d7fbcc9a760ca53d427f58"
PORTABLE_CANDIDATE_TREE = "3a715f6025b02ee939f8751c12e482fb12b0871c"

MAIN_LEDGER_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
T245_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-t245-cursor41-joint-formal-authority-r1-result.json"
)
T245_SOURCE_PATH = "src/lottolab/research/b649_min_s2_t245_cursor41_joint_formal_authority_r1.py"
T245_TEST_PATH = "tests/unit/test_b649_min_s2_t245_cursor41_joint_formal_authority_r1.py"
T245_PRIOR_ART_SOURCE_PATH = "src/lottolab/research/b649_next_two_max_profiles_exact_bound_r1.py"
T245_PROFILE_ID = "66555555555431100000"
PREVIOUS_REPORTED_DIFF_COUNT = 32
EVIDENCE_MANIFEST_PATH = (
    "docs/research/matrix-native-results/"
    "b649-certified-four-donor-family-r1-evidence/evidence-manifest.json"
)
EVIDENCE_DIRECTORY = (
    "docs/research/matrix-native-results/"
    "b649-certified-four-donor-family-r1-evidence"
)
PROFILE_PATTERN = re.compile(r"[0-9]{20}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes, label: str) -> Document:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}: invalid JSON: {error}") from error
    return _document(value, label)


def _document(value: object, label: str) -> Document:
    require(type(value) is dict, f"{label}: expected object")
    return cast(Document, value)


def _string(value: object, label: str) -> str:
    require(type(value) is str, f"{label}: expected string")
    return cast(str, value)


def _integer(value: object, label: str) -> int:
    require(type(value) is int, f"{label}: expected integer")
    return cast(int, value)


def _strings(value: object, label: str) -> list[str]:
    require(type(value) is list, f"{label}: expected list")
    items = cast(list[object], value)
    require(all(type(item) is str for item in items), f"{label}: expected string IDs")
    return cast(list[str], items)


def _profile_bounds(value: object, label: str) -> dict[str, int]:
    rows = _document(value, label)
    result: dict[str, int] = {}
    for profile, bound in rows.items():
        require(type(profile) is str and PROFILE_PATTERN.fullmatch(profile) is not None, label)
        result[profile] = _integer(bound, f"{label}[{profile}]")
    return result


def _git(*args: str) -> bytes:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "-c", "core.fsmonitor=false", *args], env=env
    )


def _assert_tree(head: str, tree: str) -> None:
    actual = _git("rev-parse", f"{head}^{{tree}}").decode().strip()
    require(actual == tree, f"pinned tree mismatch for {head}")


def _frozen_blob(head: str, path: str, expected_sha256: str | None = None) -> bytes:
    entries = _git("ls-tree", head, "--", path).decode().splitlines()
    require(len(entries) == 1, f"{head}:{path}: expected one tree entry")
    metadata, separator, found_path = entries[0].partition("\t")
    require(separator == "\t" and found_path == path, f"{head}:{path}: path mismatch")
    require(metadata.startswith("100644 blob "), f"{head}:{path}: unsafe blob mode")
    raw = _git("cat-file", "blob", f"{head}:{path}")
    if expected_sha256 is not None:
        require(_sha(raw) == expected_sha256, f"{head}:{path}: SHA256 mismatch")
    return raw


def _working_file(path: str) -> bytes:
    relative = Path(path)
    require(not relative.is_absolute() and ".." not in relative.parts, "unsafe working path")
    target = ROOT / relative
    require(target.is_file() and not target.is_symlink(), f"missing/unsafe working file: {path}")
    return target.read_bytes()


def _fixed_json(head: str, path: str, expected_sha256: str | None = None) -> tuple[Document, bytes]:
    raw = _frozen_blob(head, path, expected_sha256)
    return parse_json(raw, f"{head}:{path}"), raw


def _load_manifest() -> tuple[Document, str]:
    manifest, raw = _fixed_json(STAGING_HEAD, EVIDENCE_MANIFEST_PATH)
    require(_working_file(EVIDENCE_MANIFEST_PATH) == raw, "working evidence manifest differs")
    entries = _document(manifest.get("ENTRIES"), "evidence manifest ENTRIES")
    require(len(entries) == 17, "expected all 17 portable donor evidence entries")
    for filename, value in entries.items():
        require(type(filename) is str and Path(filename).name == filename, "unsafe evidence name")
        entry = _document(value, f"evidence manifest {filename}")
        expected_size = _integer(entry.get("bytes"), f"{filename} bytes")
        expected_sha = _string(entry.get("sha256"), f"{filename} sha256")
        require(SHA256_PATTERN.fullmatch(expected_sha) is not None, f"{filename} sha256 format")
        path = f"{EVIDENCE_DIRECTORY}/{filename}"
        working = _working_file(path)
        pinned = _frozen_blob(STAGING_HEAD, path, expected_sha)
        require(working == pinned, f"{filename}: working bytes differ from Staging blob")
        require(len(working) == expected_size, f"{filename}: evidence size mismatch")
    return manifest, _sha(raw)


def _load_family_result() -> tuple[Document, str]:
    raw = _frozen_blob(STAGING_HEAD, family_replay.RESULT_PATH)
    require(_working_file(family_replay.RESULT_PATH) == raw, "working Family result differs")
    result = parse_json(raw, "Staging four-donor Family result")
    recomputed = family_replay.compute_result()
    require(result == recomputed, "Staging Family result differs from sealed donor replay")
    return result, _sha(raw)


def _load_t245_certificate(science_rows: Mapping[str, int]) -> Document:
    result, raw = _fixed_json(SCIENCE_BASE_HEAD, T245_RESULT_PATH)
    source_raw = _frozen_blob(SCIENCE_BASE_HEAD, T245_SOURCE_PATH)
    test_raw = _frozen_blob(SCIENCE_BASE_HEAD, T245_TEST_PATH)
    source_sha = _sha(source_raw)
    test_sha = _sha(test_raw)
    require(result.get("SOURCE_SHA256") == source_sha, "T245 source/result binding")
    require(result.get("TEST_SHA256") == test_sha, "T245 test/result binding")
    row_bounds = _profile_bounds(result.get("RESOLVED_ROW_BOUNDS"), "T245 resolved rows")
    envelope = _document(result.get("T245_ENVELOPE"), "T245 envelope")
    t245_bound = _integer(envelope.get("NEW_BOUND"), "T245 NEW_BOUND")
    require(row_bounds.get(T245_PROFILE_ID) == t245_bound, "T245 target row/certificate mismatch")
    require(science_rows.get(T245_PROFILE_ID) == t245_bound, "Science row differs from T245 result")

    provenance = _document(result.get("PROVENANCE"), "T245 provenance")
    prior_head = _string(provenance.get("T245_PRIOR_ART_HEAD"), "T245 prior-art head")
    prior_sha = _string(provenance.get("T245_SOURCE_SHA256"), "T245 prior-art source SHA256")
    prior_raw = _frozen_blob(prior_head, T245_PRIOR_ART_SOURCE_PATH, prior_sha)
    require(_sha(prior_raw) == prior_sha, "T245 prior-art source identity")
    return {
        "PROFILE_ID": T245_PROFILE_ID,
        "BOUND": t245_bound,
        "RESULT_PATH": T245_RESULT_PATH,
        "RESULT_SHA256": _sha(raw),
        "SOURCE_PATH": T245_SOURCE_PATH,
        "SOURCE_SHA256": source_sha,
        "TEST_PATH": T245_TEST_PATH,
        "TEST_SHA256": test_sha,
        "PRIOR_ART_HEAD": prior_head,
        "PRIOR_ART_SOURCE_PATH": T245_PRIOR_ART_SOURCE_PATH,
        "PRIOR_ART_SOURCE_SHA256": prior_sha,
    }


def _load_main_science_diff() -> Document:
    main, main_raw = _fixed_json(PINNED_MAIN_HEAD, MAIN_LEDGER_PATH)
    science, science_raw = _fixed_json(
        SCIENCE_BASE_HEAD,
        family_replay.BASE_RESULT_PATH,
        family_replay.BASE_RESULT_SHA256,
    )
    main_rows = _profile_bounds(main.get("RESOLVED_ROW_BOUNDS"), "pinned Main rows")
    science_rows = _profile_bounds(science.get("RESOLVED_ROW_BOUNDS"), "Science Base rows")
    require(len(main_rows) == 4647 and len(science_rows) == 4647, "ledger row count")
    require(set(main_rows) == set(science_rows), "Main/Science profile identity mismatch")
    t245 = _load_t245_certificate(science_rows)
    changed = [
        {
            "PROFILE_ID": profile,
            "MAIN_BOUND": main_rows[profile],
            "SCIENCE_BASE_BOUND": science_rows[profile],
        }
        for profile in sorted(main_rows)
        if main_rows[profile] != science_rows[profile]
    ]
    changed_by_id = {row["PROFILE_ID"]: row for row in changed}
    t245_row = changed_by_id.get(T245_PROFILE_ID)
    if t245_row is None:
        raise ValueError("T245 profile missing from full ledger difference")
    require(t245_row["SCIENCE_BASE_BOUND"] == t245["BOUND"], "T245 difference/source mismatch")
    count_delta = len(changed) - PREVIOUS_REPORTED_DIFF_COUNT
    require(count_delta == 1, "32/33 discrepancy is not explained by the identified T245 row")
    return {
        "PINNED_MAIN_HEAD": PINNED_MAIN_HEAD,
        "PINNED_MAIN_TREE": PINNED_MAIN_TREE,
        "MAIN_LEDGER_PATH": MAIN_LEDGER_PATH,
        "MAIN_LEDGER_SHA256": _sha(main_raw),
        "SCIENCE_BASE_HEAD": SCIENCE_BASE_HEAD,
        "SCIENCE_BASE_TREE": SCIENCE_BASE_TREE,
        "SCIENCE_BASE_RESULT_PATH": family_replay.BASE_RESULT_PATH,
        "SCIENCE_BASE_RESULT_SHA256": _sha(science_raw),
        "PREVIOUS_REPORTED_DIFF_COUNT": PREVIOUS_REPORTED_DIFF_COUNT,
        "RECOMPUTED_DIFF_COUNT": len(changed),
        "COUNT_DELTA": count_delta,
        "DIFF_ROWS": changed,
        "T245_EXTRA_ROW": {**cast(Document, t245_row), **t245},
        "EXPLANATION": (
            "The full 4,647-row comparison includes the T245-certified profile "
            f"{T245_PROFILE_ID}; excluding that changed row yields the earlier count. "
            "The prior report did not provide its own machine-readable ID set."
        ),
    }


def _assert_ref_identities() -> None:
    _assert_tree(STAGING_HEAD, STAGING_TREE)
    _assert_tree(PINNED_MAIN_HEAD, PINNED_MAIN_TREE)
    _assert_tree(SCIENCE_BASE_HEAD, SCIENCE_BASE_TREE)
    _assert_tree(PORTABLE_CANDIDATE_HEAD, PORTABLE_CANDIDATE_TREE)


def build_candidate() -> Document:
    _assert_ref_identities()
    manifest, manifest_sha = _load_manifest()
    family_result, family_result_sha = _load_family_result()

    ledger_audit = _document(family_result.get("RESOLVED_LEDGER"), "Family resolved ledger")
    rows = _profile_bounds(ledger_audit.get("ROW_BOUNDS"), "Family candidate rows")
    cursor_audit = _document(family_result.get("CURSOR"), "Family source cursor")
    source_cursor = _document(cursor_audit.get("SOURCE_CURSOR"), "full source cursor")
    cursor_ids = _strings(source_cursor.get("PROFILE_IDS"), "cursor PROFILE_IDS")
    projection = _profile_bounds(cursor_audit.get("PROFILE_BOUNDS"), "cursor profile bounds")
    source_projection = _profile_bounds(
        source_cursor.get("COARSE_BOUND_PROJECTION"), "source cursor projection"
    )
    require(cursor_ids == source_cursor.get("PROFILE_IDS"), "cursor identity preservation")
    require(len(cursor_ids) == len(set(cursor_ids)) == 197, "cursor profile identity count")
    require(set(cursor_ids) == set(projection) == set(source_projection), "cursor projection IDs")
    require(projection == source_projection, "cursor projection values changed")
    require(len(rows) == 4647 and not set(rows) & set(projection), "Family coverage")

    base = _document(family_result.get("BASE"), "Family base")
    incumbent = _integer(base.get("INCUMBENT"), "INCUMBENT")
    summary = family_replay.family_summary(rows, projection, incumbent)
    independent = family_replay.independent_family_summary(rows, projection, incumbent)
    require(summary == independent, "independent Family replay mismatch")
    require(summary == family_result.get("FAMILY_AFTER"), "sealed Family summary mismatch")
    consumer_summary = successor_consumer.family(rows, projection)
    cursor_summary_bound = _integer(source_cursor.get("BOUND"), "cursor summary bound")
    effective_cursor_max = max(projection.values())
    main_science_diff = _load_main_science_diff()

    candidate = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": TASK_STATUS,
        "CANONICAL_MAIN_ADOPTION": "NOT_DONE",
        "REMOTE_WRITE": "NO",
        "SOURCE_IDENTITY": {
            "STAGING_HEAD": STAGING_HEAD,
            "STAGING_TREE": STAGING_TREE,
            "SCIENCE_BASE_HEAD": SCIENCE_BASE_HEAD,
            "SCIENCE_BASE_TREE": SCIENCE_BASE_TREE,
            "SCIENCE_BASE_RESULT_SHA256": family_replay.BASE_RESULT_SHA256,
            "PORTABLE_CANDIDATE_HEAD": PORTABLE_CANDIDATE_HEAD,
            "PORTABLE_CANDIDATE_TREE": PORTABLE_CANDIDATE_TREE,
            "FAMILY_RESULT_PATH": family_replay.RESULT_PATH,
            "FAMILY_RESULT_SHA256": family_result_sha,
            "EVIDENCE_MANIFEST_PATH": EVIDENCE_MANIFEST_PATH,
            "EVIDENCE_MANIFEST_SHA256": manifest_sha,
        },
        "BASE_HEAD": SCIENCE_BASE_HEAD,
        "BASE_TREE": SCIENCE_BASE_TREE,
        "BASE_RESULT_SHA256": family_replay.BASE_RESULT_SHA256,
        "MODEL": dict(successor_consumer.MODEL),
        "SCHEMA_CONSUMER": {
            "SOURCE_PATH": (
                "src/lottolab/research/"
                "b649_min_s2_owner_ab_t249_t260k4_composition_r1.py"
            ),
            "RESOLVED_ROW_BOUNDS": "object[str, int] at top level",
            "CURSOR": {
                "PROFILE_COUNT": "int",
                "PROFILE_IDS": "array[str]",
                "COARSE_BOUND_PROJECTION": "object[str, int]",
            },
            "INCUMBENT": "int at top level",
        },
        "IMPLEMENTATION_SOURCE_SHA256": _sha(_working_file(SOURCE_PATH)),
        "FOCUSED_TEST_SHA256": _sha(_working_file(TEST_PATH)),
        "INCUMBENT": incumbent,
        "RESOLVED_ROWS": len(rows),
        "ROWS_UPDATED": ledger_audit["UPDATED_ROWS"],
        "OTHER_ROWS_UNCHANGED": ledger_audit["UNCHANGED_ROWS"],
        "RESOLVED_ROW_BOUNDS": dict(sorted(rows.items())),
        "CURSOR_PROFILES": len(cursor_ids),
        "CURSOR_PRESERVED": cursor_audit.get("UNCHANGED"),
        "CURSOR_SUMMARY_BOUND": cursor_summary_bound,
        "EFFECTIVE_CURSOR_MAX": effective_cursor_max,
        "CURSOR": {
            "PROFILE_COUNT": len(cursor_ids),
            "PROFILE_IDS": cursor_ids,
            "COARSE_BOUND_PROJECTION": dict(sorted(projection.items())),
            "CURSOR_SUMMARY_PROFILE_ID": source_cursor.get("ID"),
            "CURSOR_SUMMARY_BOUND": cursor_summary_bound,
            "EFFECTIVE_CURSOR_MAX": effective_cursor_max,
            "SOURCE_CURSOR_SHA256": cursor_audit.get("SOURCE_CURSOR_SHA256"),
            "SOURCE_CURSOR": source_cursor,
        },
        "FAMILY_UB": summary["FAMILY_UB"],
        "ALL_OWNER_IDS": summary["ALL_OWNER_IDS"],
        "NEXT_DISTINCT_BOUND": summary["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNER_IDS": summary["NEXT_DISTINCT_OWNER_IDS"],
        "OPEN_PROFILES": summary["STILL_OPEN_PROFILES"],
        "TOTAL_PROFILES": summary["TOTAL_PROFILES"],
        "FAMILY_BOUND": consumer_summary["FAMILY_BOUND"],
        "OWNER_IDS": consumer_summary["OWNER_IDS"],
        "GAP_TO_INCUMBENT": consumer_summary["GAP_TO_INCUMBENT"],
        "STILL_OPEN_PROFILE_COUNT": consumer_summary["STILL_OPEN_PROFILE_COUNT"],
        "RESOLVED_MAXIMUM": consumer_summary["RESOLVED_MAXIMUM"],
        "CURSOR_MAXIMUM": consumer_summary["CURSOR_MAXIMUM"],
        "FAMILY_BEFORE": family_result["FAMILY_BEFORE"],
        "FAMILY_AFTER": consumer_summary,
        "FOUR_DONOR_FAMILY_AFTER": summary,
        "FAMILY_GAIN_FROM_BASE": family_result["FAMILY_GAIN_FROM_BASE"],
        "INDEPENDENT_REPLAY": {
            "METHOD_1": "direct maximum, full owner scan, and next-distinct scan",
            "METHOD_2": "descending sort of every resolved and cursor profile pair",
            "MATCH": summary == independent,
            "FAMILY_SUMMARY": independent,
        },
        "RESOLVED_LEDGER_AUDIT": {
            "UPDATED_PROFILE_BOUNDS": ledger_audit["UPDATED_PROFILE_BOUNDS"],
            "UPDATED_ROWS": ledger_audit["UPDATED_ROWS"],
            "UNCHANGED_ROWS": ledger_audit["UNCHANGED_ROWS"],
            "UNCHANGED_ROWS_SHA256": ledger_audit["UNCHANGED_ROWS_SHA256"],
        },
        "DONORS": family_result["DONORS"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": family_result[
            "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
        ],
        "LIMITS": family_result["LIMITS"],
        "SEALED_EVIDENCE": {
            "MANIFEST_PATH": EVIDENCE_MANIFEST_PATH,
            "MANIFEST_SHA256": manifest_sha,
            "ENTRY_COUNT": len(_document(manifest["ENTRIES"], "manifest entries")),
            "MANIFEST": manifest,
        },
        "MAIN_VS_SCIENCE_BASE": main_science_diff,
        "T245_CERTIFICATE": main_science_diff["T245_EXTRA_ROW"],
    }
    validate_consumer_schema(candidate)
    return candidate


def validate_consumer_schema(candidate: object) -> tuple[dict[str, int], dict[str, int]]:
    doc = _document(candidate, "candidate")
    rows_value = doc.get("RESOLVED_ROW_BOUNDS")
    require(type(rows_value) is dict, "RESOLVED_ROW_BOUNDS must be an object")
    rows = successor_consumer.ledger(rows_value)
    cursor = successor_consumer.obj(doc.get("CURSOR"))
    profile_count = successor_consumer.integer(cursor.get("PROFILE_COUNT"))
    profile_ids = _strings(cursor.get("PROFILE_IDS"), "CURSOR.PROFILE_IDS")
    projection_value = cursor.get("COARSE_BOUND_PROJECTION")
    require(type(projection_value) is dict, "CURSOR.COARSE_BOUND_PROJECTION must be an object")
    projection = successor_consumer.ledger(projection_value)
    incumbent = successor_consumer.integer(doc.get("INCUMBENT"))
    require(incumbent == family_replay.INCUMBENT, "INCUMBENT contract")
    require(
        len(rows) == 4647 and len(profile_ids) == 197 and profile_count == 197,
        "consumer counts",
    )
    require(len(profile_ids) == len(set(profile_ids)), "duplicate cursor profile ID")
    require(set(profile_ids) == set(projection), "cursor ID/projection contract")
    require(not set(rows) & set(projection), "resolved/cursor overlap")
    consumer_summary = successor_consumer.family(rows, projection)
    _require_same_types_and_values(
        doc.get("FAMILY_AFTER"), consumer_summary, "FAMILY_AFTER"
    )
    require(
        _integer(doc.get("FAMILY_BOUND"), "FAMILY_BOUND")
        == consumer_summary["FAMILY_BOUND"],
        "successor Family bound contract",
    )
    require(
        doc.get("OWNER_IDS") == consumer_summary["OWNER_IDS"],
        "successor Family owner contract",
    )
    require(
        _integer(doc.get("STILL_OPEN_PROFILE_COUNT"), "STILL_OPEN_PROFILE_COUNT")
        == consumer_summary["STILL_OPEN_PROFILE_COUNT"],
        "successor open-profile contract",
    )
    return rows, projection


def _require_same_types_and_values(actual: object, expected: object, label: str) -> None:
    require(type(actual) is type(expected), f"{label}: schema type mismatch")
    if type(expected) is dict:
        actual_doc = cast(dict[object, object], actual)
        expected_doc = cast(dict[object, object], expected)
        require(actual_doc.keys() == expected_doc.keys(), f"{label}: object fields mismatch")
        for key in expected_doc:
            _require_same_types_and_values(actual_doc[key], expected_doc[key], f"{label}.{key}")
    elif type(expected) is list:
        actual_list = cast(list[object], actual)
        expected_list = cast(list[object], expected)
        require(len(actual_list) == len(expected_list), f"{label}: list length mismatch")
        pairs = zip(actual_list, expected_list, strict=True)
        for index, (actual_item, expected_item) in enumerate(pairs):
            _require_same_types_and_values(actual_item, expected_item, f"{label}[{index}]")
    else:
        require(actual == expected, f"{label}: value mismatch")


def validate_family_summary(
    actual: object,
    rows: Mapping[str, int],
    projection: Mapping[str, int],
    incumbent: int,
) -> Document:
    summary = family_replay.family_summary(rows, projection, incumbent)
    independent_summary = family_replay.independent_family_summary(
        rows, projection, incumbent
    )
    require(summary == independent_summary, "independent Family summary mismatch")
    _require_same_types_and_values(actual, summary, "FAMILY_AFTER")
    return summary


def validate_candidate(candidate: object, expected: Document | None = None) -> None:
    doc = _document(candidate, "candidate")
    rows, projection = validate_consumer_schema(doc)
    require(doc.get("TASK_STATUS") == TASK_STATUS, "candidate status must remain local")
    require(
        doc.get("CANONICAL_MAIN_ADOPTION") == "NOT_DONE",
        "candidate cannot claim Main adoption",
    )
    require(doc.get("REMOTE_WRITE") == "NO", "candidate cannot claim a remote write")

    family_summary = validate_family_summary(
        doc.get("FOUR_DONOR_FAMILY_AFTER"), rows, projection, family_replay.INCUMBENT
    )
    require(
        doc.get("FAMILY_UB") == family_summary["FAMILY_UB"],
        "candidate Family maximum mismatch",
    )
    require(
        doc.get("ALL_OWNER_IDS") == family_summary["ALL_OWNER_IDS"],
        "candidate owner list mismatch",
    )
    require(
        doc.get("NEXT_DISTINCT_BOUND") == family_summary["NEXT_DISTINCT_BOUND"],
        "candidate next distinct bound mismatch",
    )

    comparison = _document(doc.get("MAIN_VS_SCIENCE_BASE"), "Main/Science comparison")
    diff_rows = comparison.get("DIFF_ROWS")
    require(type(diff_rows) is list, "Main/Science DIFF_ROWS must be a list")
    recomputed_count = _integer(comparison.get("RECOMPUTED_DIFF_COUNT"), "recomputed diff count")
    require(recomputed_count == len(cast(list[object], diff_rows)), "unexplained row diff count")
    require(
        _integer(comparison.get("COUNT_DELTA"), "row diff count delta")
        == recomputed_count
        - _integer(comparison.get("PREVIOUS_REPORTED_DIFF_COUNT"), "prior diff count"),
        "row diff count reconciliation mismatch",
    )

    expected_doc = expected if expected is not None else build_candidate()
    _require_same_types_and_values(doc, expected_doc, "candidate")


def verify_candidate(candidate: object) -> None:
    validate_candidate(candidate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    target = ROOT / RESULT_PATH
    if args.write_result:
        require(not target.exists(), "result exists; read before replacement")
        result = build_candidate()
        payload = render(result)
        target.write_bytes(payload)
        reread = _working_file(RESULT_PATH)
        require(reread == payload, "result read-after-write mismatch")
        validate_candidate(parse_json(reread, "candidate result"), result)
    else:
        raw = _working_file(RESULT_PATH)
        result = parse_json(raw, "candidate result")
        verify_candidate(result)
        payload = raw
    print(
        json.dumps(
            {
                "RESULT_SHA256": _sha(payload),
                "TASK_STATUS": result["TASK_STATUS"],
                "RESOLVED_ROWS": result["RESOLVED_ROWS"],
                "CURSOR_PROFILES": result["CURSOR_PROFILES"],
                "FAMILY_UB": result["FAMILY_UB"],
                "ALL_OWNER_IDS": result["ALL_OWNER_IDS"],
                "NEXT_DISTINCT_BOUND": result["NEXT_DISTINCT_BOUND"],
                "OPEN_PROFILES": result["OPEN_PROFILES"],
                "MAIN_VS_SCIENCE_DIFF_COUNT": _document(
                    result["MAIN_VS_SCIENCE_BASE"], "comparison"
                )["RECOMPUTED_DIFF_COUNT"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
