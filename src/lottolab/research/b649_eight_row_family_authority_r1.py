"""Independent eight-row B649 family-authority integration.

The proof is universal over the pinned degree profile. The one frozen support
realization is checked only as an identity sanity check; it is not used as the
proof. No donor research function or solver is imported or executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, replace
from itertools import pairwise, product
from math import comb
from pathlib import Path
from typing import Any, cast

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as seven

TASK_ID = "B649_EIGHT_ROW_FAMILY_AUTHORITY_R1"
PROFILE_ID = "66655555555521000000"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_INPUT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
)
FROZEN_INPUT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
DONOR_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_SEVEN_ROW_NEXT_OWNER_BOUND_R1"
)
DONOR_HEAD = "b78b59f1525d5c701dd7f48a73b47979d2e16403"
DONOR_TREE = "5764cfa5392bf1ad775442c842ccf5aa49e1b38e"
DONOR_RESULT = "docs/research/matrix-native-results/b649-seven-row-next-owner-bound-r1-result.json"
DONOR_RESULT_SHA256 = "fd884c4c6c0d1ca97e5be10282f75c148a0f485abc6e2efbf67dc6547207ce0f"
RESULT_PATH = "docs/research/matrix-native-results/b649-eight-row-family-authority-r1-result.json"
SEVEN_ROW_COUNT = 4647
SEVEN_ROW_CERTIFICATE_COUNT = 7
SEVEN_ROW_FULL_DIGEST = "70e2c1bb28f223566cb54799fd1b325368b90d58c5fc5001cacfbba9d2996de6"
SEVEN_ROW_BOUNDS_DIGEST = "5ab591996b98daac3d14c1468970f8c0e7dd015e5b37d5445e2097bf9b59598a"
DONOR_PROOF_FIELD = "PROOF"
EIGHTH_CERTIFICATE_SCHEMA = "B649_EIGHTH_PROFILE_FULL_PROFILE_BOUND_V1"
PRIOR_INTEGRATION_RESULT_SHA256 = "48f71d9223f71d847e697e3b4a8a27d3bf85771304774e22111f40fe7e29468f"
PRIOR_INTEGRATION_HEAD = "bcaee8911daea0916ccf3cf9f9af3612c12a42a0"
PRIOR_INTEGRATION_TREE = "41f11af6eae6dc0e623849168373beb63bc3e1c0"
TICKET_COUNT = 20
TICKET_CAPACITY = 6
LABEL_COUNT = 49
TRIPLE_SUPPORTS = 22
PAIR_SUPPORTS = 27
T_MIN = 22
T_FROZEN_CAP = 264
GLOBAL_S4_FLOOR = 112
INCUMBENT = 313263888
NEXT_TIED_OWNERS = [
    "66555555555531000000",
    "66655555554441000000",
    "66655555555422000000",
]
ROOT = Path(__file__).resolve().parents[3]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_profile_ids(value: Any, message: str) -> list[str]:
    require(
        type(value) is list and all(type(profile_id) is str for profile_id in value),
        message,
    )
    profile_ids = cast(list[str], value)
    require(len(set(profile_ids)) == len(profile_ids), message)
    return profile_ids


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def live_identity(frozen_blob: bytes, donor_blob: bytes) -> dict[str, str]:
    """Collect exact pinned commit/tree identities and both result digests."""
    return {
        "frozen_head": run_git(ROOT, "rev-parse", FROZEN_HEAD),
        "frozen_tree": run_git(ROOT, "rev-parse", f"{FROZEN_HEAD}^{{tree}}"),
        "frozen_result_sha256": sha256(frozen_blob),
        "donor_head": run_git(DONOR_ROOT, "rev-parse", "HEAD"),
        "donor_tree": run_git(DONOR_ROOT, "rev-parse", "HEAD^{tree}"),
        "donor_result_sha256": sha256(donor_blob),
    }


def load_live_sources() -> tuple[bytes, bytes, dict[str, str]]:
    frozen_blob = (ROOT / FROZEN_INPUT).read_bytes()
    donor_blob = (DONOR_ROOT / DONOR_RESULT).read_bytes()
    return frozen_blob, donor_blob, live_identity(frozen_blob, donor_blob)


def validate_profile_id(profile_id: str) -> tuple[int, ...]:
    require(
        type(profile_id) is str
        and len(profile_id) == TICKET_COUNT
        and profile_id.isdecimal()
        and profile_id == PROFILE_ID,
        "unsupported profile: proof is scoped to 66655555555521000000",
    )
    return tuple(int(digit) for digit in profile_id)


def validate_source_identity(
    frozen_blob: bytes, donor_blob: bytes, identity: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = {
        "frozen_head": FROZEN_HEAD,
        "frozen_tree": FROZEN_TREE,
        "frozen_result_sha256": FROZEN_INPUT_SHA256,
        "donor_head": DONOR_HEAD,
        "donor_tree": DONOR_TREE,
        "donor_result_sha256": DONOR_RESULT_SHA256,
    }
    require(identity == expected, "frozen or donor source identity mismatch")
    require(sha256(frozen_blob) == FROZEN_INPUT_SHA256, "frozen input SHA256 mismatch")
    require(sha256(donor_blob) == DONOR_RESULT_SHA256, "donor result SHA256 mismatch")
    try:
        frozen = json.loads(frozen_blob)
        donor = json.loads(donor_blob)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("pinned authority JSON is invalid") from exc

    validate_donor_proof(donor)
    require(
        donor.get("PROFILE_ID") == PROFILE_ID
        and donor.get("PROOF_SCOPE") == "FULL_PROFILE"
        and donor.get("FROZEN_HEAD") == FROZEN_HEAD
        and donor.get("FROZEN_TREE") == FROZEN_TREE
        and donor.get("INPUT_PATH") == FROZEN_INPUT
        and donor.get("INPUT_SHA256") == FROZEN_INPUT_SHA256
        and donor.get("NEW_INEQUALITY") == "A <= 188+m+3e <= 192"
        and donor.get("T_CAP") == T_FROZEN_CAP
        and donor.get("T_TERMS_CHECKED") == T_FROZEN_CAP - T_MIN + 1
        and donor.get("UNPROVED_ASSUMPTIONS") == [],
        "donor result does not identify the pinned full-profile claim",
    )
    return frozen, donor


def validate_donor_proof(donor: Mapping[str, Any]) -> None:
    """Fail closed on donor schema, scope, and the actual top-level proof field."""
    proof = donor.get(DONOR_PROOF_FIELD)
    require(
        type(proof) is str and bool(proof.strip()),
        "donor proof field PROOF is missing or empty",
    )
    require(
        donor.get("TASK_ID") == "B649_SEVEN_ROW_NEXT_OWNER_BOUND_R1"
        and donor.get("PROFILE_ID") == PROFILE_ID
        and donor.get("PROOF_SCOPE") == "FULL_PROFILE"
        and donor.get("JUDGE_MODE") == "SELF_CHECK_ONLY"
        and donor.get("FROZEN_HEAD") == FROZEN_HEAD
        and donor.get("FROZEN_TREE") == FROZEN_TREE
        and donor.get("INPUT_PATH") == FROZEN_INPUT
        and donor.get("INPUT_SHA256") == FROZEN_INPUT_SHA256
        and donor.get("NEW_INEQUALITY") == "A <= 188+m+3e <= 192"
        and donor.get("NEW_CONTAINED_K4_CAP") == 192
        and donor.get("NEW_ADMISSIBLE_BOUND") == 313397476
        and donor.get("T_CAP") == T_FROZEN_CAP
        and donor.get("T_TERMS_CHECKED") == T_FROZEN_CAP - T_MIN + 1
        and donor.get("UNPROVED_ASSUMPTIONS") == []
        and donor.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN",
        "donor proof identity, applicability, or scope mismatch",
    )


def index_ledger_rows(records: Iterable[tuple[str, seven.Row]]) -> dict[str, seven.Row]:
    """Index the complete frozen row stream, rejecting missing, extra, or duplicate IDs."""
    items = list(records)
    require(len(items) == SEVEN_ROW_COUNT, "ledger row count mismatch")
    profile_ids = [profile_id for profile_id, _row in items]
    require(
        all(type(profile_id) is str for profile_id in profile_ids),
        "ledger profile ID is not text",
    )
    require(
        len(set(profile_ids)) == SEVEN_ROW_COUNT,
        "duplicate ledger profile ID",
    )
    require(
        all(isinstance(row, seven.Row) for _profile_id, row in items),
        "ledger row has the wrong schema",
    )
    return dict(items)


def load_seven_row_ledger(frozen: Mapping[str, Any]) -> dict[str, seven.Row]:
    """Rebuild the frozen seven-row ledger using its validated authority entrypoints."""
    require(
        frozen.get("TASK_ID") == seven.TASK_ID
        and frozen.get("LEDGER_ROWS") == SEVEN_ROW_COUNT
        and frozen.get("CERTIFICATES_COMPOSED") == SEVEN_ROW_CERTIFICATE_COUNT,
        "frozen seven-row result identity mismatch",
    )
    certificate_ids = require_profile_ids(
        frozen.get("CERTIFICATE_PROFILE_IDS"),
        "frozen seven-certificate profile IDs mismatch",
    )
    require(
        len(certificate_ids) == SEVEN_ROW_CERTIFICATE_COUNT,
        "frozen seven-certificate profile IDs mismatch",
    )

    six_result, six_ledger = seven.six_row_authority()
    before_seventh = index_ledger_rows(six_ledger.items())
    six_certificate_ids = require_profile_ids(
        six_result.get("CERTIFICATE_PROFILE_IDS"),
        "frozen six-certificate profile IDs mismatch",
    )
    require(
        certificate_ids == [*six_certificate_ids, seven.TARGET_PROFILE]
        and PROFILE_ID not in certificate_ids,
        "frozen seven-certificate lineage mismatch",
    )
    profile_bound = frozen.get("PROFILE_BOUND_AFTER")
    require(type(profile_bound) is int, "frozen profile bound is not an integer")
    seven_ledger = seven.apply_seventh(
        before_seventh,
        cast(int, profile_bound),
        seven.PROPOSED_CAP,
        f"{seven.TASK_ID}:CORE_ZERO_T256_THEOREM",
    )
    rows = index_ledger_rows(seven_ledger.items())
    full = seven.two.full_digest(rows)
    bounds = seven.two.bounds_digest(rows)
    require(
        full == SEVEN_ROW_FULL_DIGEST == frozen.get("FULL_ROWS_SHA256_AFTER")
        and bounds == SEVEN_ROW_BOUNDS_DIGEST == frozen.get("BOUNDS_SHA256_AFTER"),
        "frozen seven-row before digest mismatch",
    )
    family_bound, family_owners, next_bound = seven.three.family(rows)
    require(
        (family_bound, family_owners, next_bound)
        == (
            frozen.get("FAMILY_BOUND_AFTER"),
            frozen.get("NEXT_OWNER_IDS"),
            frozen.get("NEXT_COMPETING_BOUND"),
        ),
        "frozen seven-row family replay mismatch",
    )
    frozen_row = frozen.get("NEW_OWNER_ROWS", {}).get(PROFILE_ID)
    require(
        type(frozen_row) is dict
        and json.loads(json.dumps(asdict(rows[PROFILE_ID]))) == frozen_row,
        "frozen target row does not match the rebuilt ledger",
    )
    return rows


def verify_ledger_overlay(
    before: Mapping[str, seven.Row],
    after: Mapping[str, seven.Row],
    new_bound: int,
    source: str,
) -> dict[str, Any]:
    """Compare every row and certify that only bound/source on the target changed."""
    before_rows = index_ledger_rows(before.items())
    after_rows = index_ledger_rows(after.items())
    require(set(before_rows) == set(after_rows), "ledger profile key set changed")
    before_full = seven.two.full_digest(before_rows)
    before_bounds = seven.two.bounds_digest(before_rows)
    require(
        before_full == SEVEN_ROW_FULL_DIGEST
        and before_bounds == SEVEN_ROW_BOUNDS_DIGEST,
        "frozen seven-row before digest mismatch",
    )
    original = before_rows[PROFILE_ID]
    updated = after_rows[PROFILE_ID]
    require(
        (original.bound, original.cap, original.s4_base)
        == (313398532, T_FROZEN_CAP, GLOBAL_S4_FLOOR),
        "frozen target row baseline mismatch",
    )
    require(
        type(new_bound) is int
        and new_bound < original.bound
        and updated.bound == new_bound
        and updated.cap == original.cap
        and updated.s4_base == original.s4_base
        and updated.realization == original.realization
        and updated.source == source,
        "target row update or preserved metadata mismatch",
    )
    before_target = asdict(original)
    after_target = asdict(updated)
    changed_fields = sorted(
        field for field in before_target if before_target[field] != after_target[field]
    )
    require(changed_fields == ["bound", "source"], "target row changed a protected field")
    changed_profiles = [
        profile_id
        for profile_id in before_rows
        if before_rows[profile_id] != after_rows[profile_id]
    ]
    require(
        changed_profiles == [PROFILE_ID],
        "overlay changed a profile outside the designated owner",
    )
    unchanged_count = sum(
        before_rows[profile_id] == after_rows[profile_id]
        for profile_id in before_rows
        if profile_id != PROFILE_ID
    )
    require(unchanged_count == SEVEN_ROW_COUNT - 1, "unchanged row comparison count mismatch")
    return {
        "ROWS_BEFORE": len(before_rows),
        "ROWS_AFTER": len(after_rows),
        "PROFILE_KEY_SET_UNCHANGED": "YES",
        "FULL_DIGEST_BEFORE": before_full,
        "BOUNDS_DIGEST_BEFORE": before_bounds,
        "FULL_DIGEST_AFTER": seven.two.full_digest(after_rows),
        "BOUNDS_DIGEST_AFTER": seven.two.bounds_digest(after_rows),
        "CHANGED_ROW_COUNT": len(changed_profiles),
        "CHANGED_PROFILE_IDS": changed_profiles,
        "UNCHANGED_ROW_COMPARISONS": unchanged_count,
        "CHANGED_TARGET_FIELDS": changed_fields,
        "PRESERVED_TARGET_FIELDS": [
            field for field in before_target if field not in {"bound", "source"}
        ],
        "TARGET_ROW_BEFORE": before_target,
        "TARGET_ROW_AFTER": after_target,
        "FROZEN_BEFORE_MUTATED": "NO",
    }


def apply_eighth_overlay(
    ledger: Mapping[str, seven.Row], new_bound: int, source: str
) -> tuple[dict[str, seven.Row], dict[str, Any]]:
    """Apply the eighth certificate to a copy of the complete frozen ledger."""
    before = index_ledger_rows(ledger.items())
    original = dict(before)
    before_full = seven.two.full_digest(before)
    before_bounds = seven.two.bounds_digest(before)
    require(
        before_full == SEVEN_ROW_FULL_DIGEST
        and before_bounds == SEVEN_ROW_BOUNDS_DIGEST,
        "frozen seven-row before digest mismatch",
    )
    target = before[PROFILE_ID]
    require(
        type(new_bound) is int
        and new_bound < target.bound
        and type(source) is str
        and source == f"{RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE",
        "eighth profile update is not a fresh, scoped certificate",
    )
    after = dict(before)
    after[PROFILE_ID] = replace(target, bound=new_bound, source=source)
    summary = verify_ledger_overlay(before, after, new_bound, source)
    require(
        before == original
        and seven.two.full_digest(ledger) == before_full
        and seven.two.bounds_digest(ledger) == before_bounds,
        "frozen before ledger was mutated",
    )
    return after, summary


def build_eighth_profile_certificate(donor: Mapping[str, Any]) -> dict[str, Any]:
    """Bind the full-profile claim to the donor's real PROOF field and exact result."""
    validate_donor_proof(donor)
    proof = donor[DONOR_PROOF_FIELD]
    return {
        "SCHEMA": EIGHTH_CERTIFICATE_SCHEMA,
        "PROFILE_ID": PROFILE_ID,
        "APPLICABILITY": "FULL_PROFILE",
        "CLAIM": "A_LE_192",
        "OWNER_BOUND": donor["NEW_ADMISSIBLE_BOUND"],
        "T_CAP": donor["T_CAP"],
        "T_TERM_COUNT": donor["T_TERMS_CHECKED"],
        "PROOF_REFERENCE": {
            "HEAD": DONOR_HEAD,
            "TREE": DONOR_TREE,
            "RESULT_PATH": DONOR_RESULT,
            "RESULT_SHA256": DONOR_RESULT_SHA256,
            "RESULT_FIELD": DONOR_PROOF_FIELD,
            "FIELD_SHA256": sha256(proof.encode()),
        },
        "SOURCE_JUDGE_STATUS": "SELF_CHECK_ONLY",
        "JUDGE_UPGRADE": "NONE",
    }


def validate_certificate_pointer(
    result: Mapping[str, Any], donor: Mapping[str, Any]
) -> None:
    expected_certificate = build_eighth_profile_certificate(donor)
    require(
        result.get("EIGHTH_PROFILE_CERTIFICATE") == expected_certificate,
        "donor proof pointer, identity, or applicability mismatch",
    )
    update = result.get("ROW_UPDATE")
    require(
        type(update) is dict
        and update.get("SOURCE_AFTER") == f"{RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE",
        "row source does not point to the eighth profile certificate",
    )


def validate_authority_result(
    result: Mapping[str, Any],
    donor: Mapping[str, Any],
    frozen: Mapping[str, Any],
    before: Mapping[str, seven.Row],
) -> None:
    """Recompute the emitted envelope and family summary from the full ledger."""
    require(
        result.get("PROFILE_ID") == PROFILE_ID
        and result.get("PROOF_SCOPE") == "FULL_PROFILE",
        "result profile or proof applicability mismatch",
    )
    target = before[PROFILE_ID]
    degrees = validate_profile_id(PROFILE_ID)
    local = local_intersection_weights()
    expected_terms = envelope_terms(T_FROZEN_CAP, 192, target.s4_base, local)
    old_a_cap = sum(d * (4 + d) for d in degrees) // 3
    old_terms = envelope_terms(T_FROZEN_CAP, old_a_cap, target.s4_base, local)
    old_peak = max(old_terms, key=lambda item: item["BOUND"])
    new_peak = max(expected_terms, key=lambda item: item["BOUND"])
    require(
        result.get("NEW_ENVELOPE_TERMS") == expected_terms
        and result.get("NEW_ENVELOPE_PEAK") == new_peak
        and result.get("T_CAP") == target.cap == T_FROZEN_CAP
        and result.get("OLD_A_CAP") == old_a_cap
        and result.get("NEW_A_CAP") == 192
        and result.get("OLD_OWNER_BOUND") == old_peak["BOUND"] == target.bound
        and result.get("NEW_OWNER_BOUND") == new_peak["BOUND"]
        and result.get("OWNER_DELTA") == old_peak["BOUND"] - new_peak["BOUND"]
        and len(expected_terms) == 243
        and [term["T"] for term in expected_terms] == list(range(T_MIN, T_FROZEN_CAP + 1)),
        "owner bound, cap, or integer envelope mismatch",
    )
    source = f"{RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE"
    after, overlay = apply_eighth_overlay(before, new_peak["BOUND"], source)
    require(
        result.get("LEDGER_OVERLAY") == overlay,
        "result does not report the recomputed full-ledger overlay",
    )
    before_family = seven.three.family(before)
    after_family = seven.three.family(after)
    family_delta = before_family[0] - after_family[0]
    gap = after_family[0] - INCUMBENT
    require(
        (before_family[0], before_family[1], before_family[2])
        == (
            frozen.get("FAMILY_BOUND_AFTER"),
            frozen.get("NEXT_OWNER_IDS"),
            frozen.get("NEXT_COMPETING_BOUND"),
        )
        and result.get("FAMILY_BOUND_AFTER") == after_family[0]
        and result.get("FROZEN_FAMILY_BOUND_BEFORE") == before_family[0]
        and result.get("NEXT_COMPETING_BOUND") == before_family[2]
        and result.get("FAMILY_BOUND_DELTA") == family_delta
        and result.get("NEXT_TIED_OWNERS") == after_family[1] == NEXT_TIED_OWNERS
        and (new_peak["BOUND"], after_family[0], family_delta, gap)
        == (313397476, 313398248, 284, 134360)
        and result.get("EXPECTED_REMAINING_GAP") == gap,
        "full-ledger family maximum or tied owners mismatch",
    )
    before_ids = require_profile_ids(
        frozen.get("CERTIFICATE_PROFILE_IDS"),
        "frozen seven-certificate profile IDs mismatch",
    )
    require(
        result.get("CERTIFICATE_PROFILE_IDS_BEFORE") == before_ids
        and result.get("CERTIFICATE_PROFILE_IDS_AFTER") == [*before_ids, PROFILE_ID]
        and result.get("CERTIFICATES_BEFORE") == SEVEN_ROW_CERTIFICATE_COUNT
        and result.get("CERTIFICATES_AFTER") == SEVEN_ROW_CERTIFICATE_COUNT + 1,
        "eighth certificate profile set mismatch",
    )
    require(
        len(result["CERTIFICATE_PROFILE_IDS_AFTER"]) == SEVEN_ROW_CERTIFICATE_COUNT + 1
        and len(set(result["CERTIFICATE_PROFILE_IDS_AFTER"]))
        == SEVEN_ROW_CERTIFICATE_COUNT + 1,
        "eighth certificate was duplicated",
    )
    require(
        result.get("PRESERVED_SIX_ROW_STATUS") == frozen.get("PRESERVED_SIX_ROW_STATUS")
        and result.get("INHERITED_JUDGE_STATUS") == "SELF_CHECK_ONLY"
        and result.get("NEW_CERTIFICATE_JUDGE_STATUS") == "SELF_CHECK_ONLY",
        "inherited status or caveats were upgraded",
    )
    validate_certificate_pointer(result, donor)


def validate_realization(realization: list[Any]) -> dict[str, Any]:
    """Check the pinned witness against the stated support model; not a proof."""
    require(type(realization) is list and len(realization) == 2, "invalid realization shape")
    triples, pairs = realization
    triples = cast(list[Any], triples)
    pairs = cast(list[Any], pairs)
    require(
        type(triples) is list
        and type(pairs) is list
        and len(triples) == TRIPLE_SUPPORTS
        and len(pairs) == PAIR_SUPPORTS,
        "frozen support counts mismatch",
    )
    triple_degree = [0] * TICKET_COUNT
    label_degree = [0] * TICKET_COUNT
    used_ticket_pairs: set[tuple[int, int]] = set()
    edge_count = 0
    for supports, support_size, is_triple in (
        (triples, 3, True),
        (pairs, 2, False),
    ):
        for raw_support in supports:
            require(type(raw_support) is list, "invalid support in frozen realization")
            support = cast(list[Any], raw_support)
            require(
                len(support) == support_size
                and all(type(v) is int and 0 <= v < TICKET_COUNT for v in support)
                and len(set(support)) == support_size,
                "invalid support in frozen realization",
            )
            support_values = cast(list[int], support)
            for vertex in support_values:
                label_degree[vertex] += 1
                triple_degree[vertex] += int(is_triple)
            for i, left in enumerate(support_values):
                for right in support_values[i + 1 :]:
                    edge = (min(left, right), max(left, right))
                    require(edge not in used_ticket_pairs, "reused ticket pair in realization")
                    used_ticket_pairs.add(edge)
                    edge_count += 1
    profile = "".join(str(d) for d in sorted(triple_degree, reverse=True))
    require(profile == PROFILE_ID, "frozen realization has the wrong profile")
    require(label_degree == [TICKET_CAPACITY] * TICKET_COUNT, "ticket capacity mismatch")
    require(edge_count == 93, "overlap graph edge count mismatch")
    return {
        "CHECK_SCOPE": "ONE_PINNED_REALIZATION_ONLY",
        "TRIPLE_SUPPORTS": len(triples),
        "PAIR_SUPPORTS": len(pairs),
        "TICKET_LABEL_COUNTS": sorted(set(label_degree)),
        "TRIPLE_DEGREE_DISTRIBUTION": {
            str(d): triple_degree.count(d) for d in sorted(set(triple_degree), reverse=True)
        },
        "SIMPLE_OVERLAP_GRAPH_EDGES": edge_count,
    }


def profile_degree_distribution(degrees: tuple[int, ...]) -> dict[str, int]:
    return {str(d): degrees.count(d) for d in sorted(set(degrees), reverse=True)}


def prove_a_cap(profile_id: str = PROFILE_ID) -> dict[str, Any]:
    """Full-profile incidence proof for A <= 188 + m + 3e <= 192."""
    degrees = validate_profile_id(profile_id)
    distribution = profile_degree_distribution(degrees)
    require(
        distribution == {"6": 3, "5": 9, "2": 1, "1": 1, "0": 6},
        "profile distribution does not match the frozen support model",
    )
    require(sum(degrees) == 3 * TRIPLE_SUPPORTS, "triple incidence total mismatch")
    old_numerator = sum(d * (4 + d) for d in degrees)
    old_cap = old_numerator // 3
    require(old_numerator == 602 and old_cap == 200, "old A relaxation mismatch")

    # In any legal support, d=0 vertices cannot occur. A support with three
    # d=6 vertices is unique if it exists; the unique d=1 and d=2 vertices
    # can share at most one support. Thus m,e are independently binary.
    caps = {
        (m, e): 22 * 9 - 3 * 2 - 4 + 3 * e + m
        for m, e in product((0, 1), repeat=2)
    }
    require(caps == {(0, 0): 188, (0, 1): 191, (1, 0): 189, (1, 1): 192},
            "incidence case table mismatch")
    return {
        "A_DEFINITION": (
            "A counts K4 quartets containing a triple support; each has at most "
            "one such support by pair-linearity, so A=sum_S |intersection N(v)|."
        ),
        "M_DEFINITION": (
            "m is the number of triple supports on all three degree-6 tickets; "
            "there is at most one such 3-set."
        ),
        "E_DEFINITION": (
            "e is the number of triple supports containing both the unique "
            "degree-2 and unique degree-1 tickets; there is at most one."
        ),
        "PROFILE_DEGREE_DISTRIBUTION": distribution,
        "OLD_AVERAGE_NUMERATOR": old_numerator,
        "OLD_AVERAGE_CAP": old_cap,
        "NEW_INCIDENCE_CASES": [
            {"m": m, "e": e, "A_CAP": caps[(m, e)]}
            for m in (0, 1)
            for e in (0, 1)
        ],
        "PROOF": (
            "For each triple support S, a fourth common neighbour is outside S. "
            "For each v in S it is among at most g_v-2=4+d_v choices, so "
            "c(S)<=4+min_{v in S} d_v. Relative to 9 per support, a support "
            "through the unique d=2 ticket loses 3 (two supports total), a "
            "support through the unique d=1 ticket loses 4 (one total), their "
            "shared support restores 3, and the all-d=6 support adds 1. "
            "Therefore sum_S c(S)<=22*9-3*2-4+3e+m=188+3e+m. "
            "Since m,e are binary for every legal realization, m+3e<=4 "
            "and A<=192. This depends only on the full degree profile and "
            "frozen pair-linearity, not on a sampled realization."
        ),
        "A_LE_188_PLUS_M_PLUS_3E": True,
        "M_PLUS_3E_LE_4": True,
        "A_LE_192": True,
        "PROOF_SCOPE": "FULL_PROFILE",
    }


LOCAL_PATTERNS: dict[str, tuple[int, tuple[int, ...]]] = {
    "SINGLE": (1, ()),
    "OVERLAP_PAIR": (2, (0b11,)),
    "DISJOINT_PAIR": (2, ()),
    "THREE_ONE_EDGE": (3, (0b011,)),
    "THREE_WEDGE": (3, (0b011, 0b101)),
    "THREE_PAIR_TRIANGLE": (3, (0b011, 0b101, 0b110)),
    "THREE_SUPPORT_TRIANGLE": (3, (0b111,)),
    "FOUR_FIVE_EDGES": (4, (0b0011, 0b0101, 0b1001, 0b0110, 0b1010)),
    "K4_PAIR_ONLY": (4, (0b0011, 0b0101, 0b1001, 0b0110, 0b1010, 0b1100)),
    "K4_CONTAINED_TRIPLE": (4, (0b0111, 0b1001, 0b1010, 0b1100)),
}
EXPECTED_LOCAL_WEIGHTS = {
    "SINGLE": 18611432,
    "OVERLAP_PAIR": 574000,
    "DISJOINT_PAIR": 107800,
    "THREE_ONE_EDGE": 0,
    "THREE_WEDGE": 2800,
    "THREE_PAIR_TRIANGLE": 20272,
    "THREE_SUPPORT_TRIANGLE": 7000,
    "FOUR_FIVE_EDGES": 112,
    "K4_PAIR_ONLY": 679,
    "K4_CONTAINED_TRIPLE": 448,
}


def local_intersection_weight(ticket_count: int, shared_masks: tuple[int, ...]) -> int:
    """Exact category-generating-function count of ordered 6+special draws.

    A draw is a 7-label set with one of its seven labels designated special.
    DP categories are shared-label masks, each ticket's private labels, and
    labels outside the tickets. This is independent of the donor implementation.
    """
    require(1 <= ticket_count <= 4, "local motif count supports one to four tickets")
    require(
        all(
            type(mask) is int
            and 0 < mask < (1 << ticket_count)
            and bin(mask).count("1") >= 2
            for mask in shared_masks
        ),
        "invalid shared-label mask",
    )
    private = [
        TICKET_CAPACITY
        - sum(bool(mask & (1 << ticket)) for mask in shared_masks)
        for ticket in range(ticket_count)
    ]
    require(min(private) >= 0, "ticket capacity exceeded by shared labels")
    outside = LABEL_COUNT - len(shared_masks) - sum(private)
    require(outside >= 0, "more than 49 labels in local motif")
    categories: Counter[int] = Counter(shared_masks)
    categories.update({1 << ticket: size for ticket, size in enumerate(private)})
    categories[0] += outside
    require(sum(categories.values()) == LABEL_COUNT, "local label partition mismatch")

    # State=(number selected, per-ticket hit counts); choosing k labels from
    # one category has multiplicity C(category_size,k).
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, (0,) * ticket_count): 1}
    for mask, size in sorted(categories.items()):
        next_states: defaultdict[tuple[int, tuple[int, ...]], int] = defaultdict(int)
        for (selected, hits), ways in states.items():
            for take in range(min(size, 7 - selected) + 1):
                new_hits = tuple(
                    hits[ticket] + (take if mask & (1 << ticket) else 0)
                    for ticket in range(ticket_count)
                )
                next_states[(selected + take, new_hits)] += ways * comb(size, take)
        states = dict(next_states)
    seven_sets = sum(
        ways
        for (selected, hits), ways in states.items()
        if selected == 7 and all(hits[ticket] >= 3 for ticket in range(ticket_count))
    )
    return 7 * seven_sets


def local_intersection_weights() -> dict[str, int]:
    weights = {
        name: local_intersection_weight(ticket_count, masks)
        for name, (ticket_count, masks) in LOCAL_PATTERNS.items()
    }
    require(weights == EXPECTED_LOCAL_WEIGHTS, "frozen local intersection weights mismatch")
    return weights


def verify_bonferroni_multiplicity(max_winners: int = 7) -> list[dict[str, int]]:
    """Check the integer numerator inequality used by S1-S2+S3-4*S4/7."""
    require(max_winners == 7, "winner multiplicity is outside the frozen proof")
    table: list[dict[str, int]] = []
    for winners in range(1, max_winners + 1):
        numerator = (
            7 * (winners - comb(winners, 2) + comb(winners, 3))
            - 4 * comb(winners, 4)
        )
        require(numerator >= 7, "Bonferroni multiplicity inequality failed")
        table.append({"WINNERS": winners, "NUMERATOR_OVER_7": numerator})
    return table


def envelope_terms(
    triangle_cap: int,
    a_cap: int,
    s4_base: int,
    local: dict[str, int],
) -> list[dict[str, int]]:
    require(type(triangle_cap) is int and T_MIN <= triangle_cap <= T_FROZEN_CAP,
            "T outside frozen proof range")
    require(type(a_cap) is int and 0 <= a_cap <= 200, "invalid A cap")
    require(type(s4_base) is int and s4_base >= 0, "invalid frozen S4 base")

    degrees = validate_profile_id(PROFILE_ID)
    graph_degrees = [TICKET_CAPACITY + d for d in degrees]
    wedge_count = sum(comb(g, 2) for g in graph_degrees)
    neighbour_triples = sum(comb(g, 3) for g in graph_degrees)
    maximum_graph_degree = max(graph_degrees)
    s1 = TICKET_COUNT * local["SINGLE"]
    s2 = 93 * local["OVERLAP_PAIR"] + 97 * local["DISJOINT_PAIR"]
    terms: list[dict[str, int]] = []
    for triangles in range(T_MIN, triangle_cap + 1):
        open_wedges = wedge_count - 3 * triangles
        require(open_wedges >= 0, "triangle count exceeds wedge identity")
        excess = neighbour_triples - (maximum_graph_degree - 2) * open_wedges
        k4_floor = max(0, (excess + 3) // 4)
        require(4 * k4_floor >= excess, "K4 ceiling rounded down")
        require(
            k4_floor == 0 or 4 * (k4_floor - 1) < excess,
            "K4 ceiling is not least integer",
        )
        contained = min(k4_floor, a_cap)
        s4_floor = max(
            s4_base,
            local["K4_CONTAINED_TRIPLE"] * contained
            + local["K4_PAIR_ONLY"] * (k4_floor - contained),
        )
        s3 = (
            local["THREE_WEDGE"] * open_wedges
            + local["THREE_PAIR_TRIANGLE"] * (triangles - TRIPLE_SUPPORTS)
            + local["THREE_SUPPORT_TRIANGLE"] * TRIPLE_SUPPORTS
        )
        four_s4_quotient, remainder = divmod(4 * s4_floor, 7)
        bound = s1 - s2 + s3 - four_s4_quotient
        # This records the conservative integer ceiling of N - 4*S4/7.
        exact_numerator = 7 * (s1 - s2 + s3) - 4 * s4_floor
        require(7 * bound - exact_numerator == remainder, "S4 integer rounding mismatch")
        terms.append(
            {
                "T": triangles,
                "OPEN_WEDGES": open_wedges,
                "K4_LOWER_BOUND": k4_floor,
                "A_CAP": a_cap,
                "S4_FLOOR": s4_floor,
                "S3": s3,
                "BOUND": bound,
                "ROUNDING_REMAINDER": remainder,
            }
        )
    return terms


def build_authority(
    frozen_blob: bytes,
    donor_blob: bytes,
    identity: dict[str, str],
    profile_id: str = PROFILE_ID,
) -> dict[str, Any]:
    validate_profile_id(profile_id)
    frozen, donor = validate_source_identity(frozen_blob, donor_blob, identity)
    ledger_before = load_seven_row_ledger(frozen)
    row = frozen["NEW_OWNER_ROWS"][PROFILE_ID]

    old_ids = require_profile_ids(
        frozen.get("CERTIFICATE_PROFILE_IDS"),
        "frozen seven-certificate identities mismatch",
    )
    require(
        len(old_ids) == 7
        and PROFILE_ID not in old_ids
        and frozen.get("CERTIFICATES_COMPOSED") == 7,
        "frozen seven-certificate identities mismatch",
    )
    require(
        frozen.get("LEDGER_ROWS") == 4647
        and row.get("bound") == 313398532
        and row.get("cap") == T_FROZEN_CAP
        and row.get("s4_base") == GLOBAL_S4_FLOOR
        and frozen.get("FAMILY_BOUND_AFTER") == 313398532
        and frozen.get("NEXT_COMPETING_BOUND") == 313398248
        and frozen.get("NEXT_COMPETING_OWNER_IDS") == NEXT_TIED_OWNERS
        and frozen.get("NEXT_OWNER_IDS") == [PROFILE_ID]
        and frozen.get("INCUMBENT") == INCUMBENT
        and frozen.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN",
        "frozen family facts mismatch",
    )
    inherited = frozen.get("PRESERVED_SIX_ROW_STATUS")
    require(
        type(inherited) is dict
        and inherited.get("AUTHORITY_JUDGE_STATUS") == "VERIFIED_WITH_CAVEATS"
        and inherited.get("PRIOR_JUDGE_CAVEATS") == "PRESERVED"
        and inherited.get("DONOR_JUDGE_STATUS") == "SELF_CHECK_ONLY",
        "inherited caveats or review status changed",
    )
    realization_check = validate_realization(row["realization"])
    degrees = validate_profile_id(PROFILE_ID)
    a_proof = prove_a_cap()
    local = local_intersection_weights()
    old_a_cap = sum(d * (4 + d) for d in degrees) // 3
    old_terms = envelope_terms(T_FROZEN_CAP, old_a_cap, row["s4_base"], local)
    new_terms = envelope_terms(T_FROZEN_CAP, 192, row["s4_base"], local)
    old_peak = max(old_terms, key=lambda item: item["BOUND"])
    new_peak = max(new_terms, key=lambda item: item["BOUND"])
    require(
        len(old_terms) == len(new_terms) == T_FROZEN_CAP - T_MIN + 1 == 243
        and old_peak["BOUND"] == row["bound"] == 313398532
        and old_peak["T"] == T_FROZEN_CAP
        and (new_peak["BOUND"], new_peak["T"]) == (313397476, T_FROZEN_CAP)
        and all(a["BOUND"] < b["BOUND"] for a, b in pairwise(new_terms)),
        "full frozen T envelope mismatch",
    )
    owner_delta = old_peak["BOUND"] - new_peak["BOUND"]
    source_after = f"{RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE"
    ledger_after, ledger_overlay = apply_eighth_overlay(
        ledger_before, new_peak["BOUND"], source_after
    )
    family_before = seven.three.family(ledger_before)
    family_after_recomputed = seven.three.family(ledger_after)
    family_after = family_after_recomputed[0]
    family_delta = family_before[0] - family_after
    gap = family_after - INCUMBENT
    require(
        (owner_delta, family_after, family_delta, gap)
        == (1056, 313398248, 284, 134360),
        "family maximum or remaining gap mismatch",
    )

    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "EIGHT_ROW_CANDIDATE_CORRECTED_PENDING_DELTA_JUDGE",
        "REVIEW_ROUTE": "FRESH_CONTEXT_DELTA_JUDGE",
        "PRIOR_INTEGRATION_HISTORY": {
            "VERDICT": "REFUTED",
            "HEAD": PRIOR_INTEGRATION_HEAD,
            "TREE": PRIOR_INTEGRATION_TREE,
            "RESULT_SHA256": PRIOR_INTEGRATION_RESULT_SHA256,
            "PARENT_HISTORY_PRESERVED": "YES",
        },
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROFILE_ID": PROFILE_ID,
        "PROFILE_DEGREE_DISTRIBUTION": profile_degree_distribution(degrees),
        "SUPPORT_MODEL": {
            "TICKETS": TICKET_COUNT,
            "TICKET_CAPACITY": TICKET_CAPACITY,
            "LABELS": LABEL_COUNT,
            "TRIPLE_SUPPORTS": TRIPLE_SUPPORTS,
            "PAIR_SUPPORTS": PAIR_SUPPORTS,
            "PAIR_LINEARITY": "NO_TICKET_PAIR_REUSED",
            "OVERLAP_GRAPH": "SIMPLE",
        },
        "FROZEN_AUTHORITY": {
            "HEAD": FROZEN_HEAD,
            "TREE": FROZEN_TREE,
            "INPUT_PATH": FROZEN_INPUT,
            "INPUT_SHA256": FROZEN_INPUT_SHA256,
            "FROZEN_RESULT_IDENTITY_VERIFIED": "YES",
        },
        "DONOR_AUTHORITY": {
            "HEAD": DONOR_HEAD,
            "TREE": DONOR_TREE,
            "RESULT_PATH": str(DONOR_ROOT / DONOR_RESULT),
            "RESULT_SHA256": DONOR_RESULT_SHA256,
            "PROOF_FIELD": DONOR_PROOF_FIELD,
            "PROOF_FIELD_SCHEMA": "TOP_LEVEL_NONEMPTY_UTF8_TEXT",
            "PROOF_FIELD_SHA256": sha256(donor[DONOR_PROOF_FIELD].encode()),
            "DONOR_WORKTREE_MUTATION": "NONE",
            "DONOR_FUNCTIONS_EXECUTED": "NO",
        },
        "FROZEN_REALIZATION_CHECK": realization_check,
        "A_PROOF": a_proof,
        "T_CAP": T_FROZEN_CAP,
        "T_CAP_STATUS": "UNCHANGED_FROZEN_ACCEPTED_PREMISE",
        "WEDGE_COUNT": 832,
        "NEIGHBOUR_TRIPLE_SUM": 2356,
        "MAX_OVERLAP_DEGREE": 12,
        "LOCAL_INTERSECTION_RECOUNT": local,
        "S1": 372228640,
        "S2": 63838600,
        "BONFERRONI_MULTIPLICITY_CHECK": verify_bonferroni_multiplicity(),
        "OLD_OWNER_BOUND": old_peak["BOUND"],
        "NEW_OWNER_BOUND": new_peak["BOUND"],
        "OWNER_DELTA": owner_delta,
        "OLD_A_CAP": old_a_cap,
        "NEW_A_CAP": 192,
        "OLD_ENVELOPE": {
            "TERM_COUNT": len(old_terms),
            "T_RANGE": [T_MIN, T_FROZEN_CAP],
            "MAX_T": old_peak["T"],
            "MAX_BOUND": old_peak["BOUND"],
        },
        "NEW_ENVELOPE_PEAK": new_peak,
        "NEW_ENVELOPE_TERMS": new_terms,
        "INTEGER_RECOUNT": {
            "T_TERMS_CHECKED": len(new_terms),
            "S4_CEILING_DIRECTION": "ceil(N - 4*S4/7) = N - floor(4*S4/7)",
            "K4_DIRECTION": "ceil(max(0, C - 10*O)/4)",
            "ROUNDING_CHECKED_FOR_EVERY_T": "YES",
            "NO_T_CAP_STRENGTHENING": "YES",
        },
        "CERTIFICATES_BEFORE": 7,
        "CERTIFICATES_AFTER": 8,
        "CERTIFICATE_PROFILE_IDS_BEFORE": old_ids,
        "CERTIFICATE_PROFILE_IDS_AFTER": [*old_ids, PROFILE_ID],
        "LEDGER_ROWS": 4647,
        "LEDGER_ROW_COUNT_PRESERVED": "YES",
        "LEDGER_OVERLAY": ledger_overlay,
        "CHANGED_PROFILE_COUNT": 1,
        "CHANGED_PROFILE_ID": PROFILE_ID,
        "EXACTLY_ONE_OWNER_UPDATED": "YES",
        "ROW_UPDATE": {
            "BEFORE_BOUND": row["bound"],
            "AFTER_BOUND": new_peak["BOUND"],
            "CAP_BEFORE": row["cap"],
            "CAP_AFTER": T_FROZEN_CAP,
            "S4_BASE_BEFORE": row["s4_base"],
            "S4_BASE_AFTER": row["s4_base"],
            "SOURCE_BEFORE": row["source"],
            "SOURCE_AFTER": source_after,
        },
        "OTHER_PROFILES_UNCHANGED": "YES",
        "EXISTING_CERTIFICATE_IDENTITIES_UNCHANGED": "YES",
        "FROZEN_FAMILY_BOUND_BEFORE": family_before[0],
        "NEXT_COMPETING_BOUND": family_before[2],
        "FAMILY_BOUND_AFTER": family_after,
        "FAMILY_BOUND_DELTA": family_delta,
        "NEXT_TIED_OWNERS": family_after_recomputed[1],
        "INCUMBENT": INCUMBENT,
        "EXPECTED_REMAINING_GAP": gap,
        "NEW_STRICT_WINNING_OUTCOMES": 0,
        "OUTCOME_SEARCH": "NOT_RUN; NO WINNING OUTCOME CLAIMED",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PRESERVED_SIX_ROW_STATUS": inherited,
        "INHERITED_JUDGE_STATUS": "SELF_CHECK_ONLY",
        "EIGHTH_PROFILE_CERTIFICATE": build_eighth_profile_certificate(donor),
        "NEW_CERTIFICATE_JUDGE_STATUS": "SELF_CHECK_ONLY",
        "FORMAL_LEDGER_MUTATED": "NO",
        "CERTIFICATE_F_MUTATED": "NO",
        "PR365_MUTATED": "NO",
        "PUSH": "NOT_RUN",
        "PR_MUTATION": "NONE",
        "PRODUCTION_MUTATION": "NONE",
        "NEGATIVE_TESTS": [
            "wrong profile",
            "tampered baseline owner bound",
            "invalid frozen or donor source identity",
            "T outside the frozen proof range",
        ],
    }
    validate_authority_result(result, donor, frozen, ledger_before)
    return result


def compute_result() -> dict[str, Any]:
    """Load pinned sources and compute the result through the complete ledger path."""
    frozen_blob, donor_blob, identity = load_live_sources()
    return build_authority(frozen_blob, donor_blob, identity)


def serialize_result(result: dict[str, Any]) -> bytes:
    return (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: dict[str, Any]) -> tuple[str, str]:
    """Replace only the exact REFUTED predecessor at the authorized result path."""
    destination = ROOT / RESULT_PATH
    encoded = serialize_result(result)
    if destination.exists():
        existing = destination.read_bytes()
        if existing == encoded:
            action = "ALREADY_MATCHED"
        else:
            require(
                sha256(existing) == PRIOR_INTEGRATION_RESULT_SHA256,
                "refusing to replace a result other than the pinned REFUTED predecessor",
            )
            destination.write_bytes(encoded)
            require(destination.read_bytes() == encoded, "result write did not round-trip")
            action = "REPLACED_PINNED_REFUTED_PREDECESSOR"
    else:
        with destination.open("xb") as stream:
            stream.write(encoded)
        action = "CREATED"
    return action, sha256(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    if args.write_result:
        action, digest = write_result(result)
    else:
        action, digest = "NOT_WRITTEN", sha256(serialize_result(result))
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "PROFILE_ID": PROFILE_ID,
                "NEW_OWNER_BOUND": result["NEW_OWNER_BOUND"],
                "FAMILY_BOUND_AFTER": result["FAMILY_BOUND_AFTER"],
                "T_TERMS_CHECKED": result["INTEGER_RECOUNT"]["T_TERMS_CHECKED"],
                "RESULT_ACTION": action,
                "RESULT_SHA256": digest,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
