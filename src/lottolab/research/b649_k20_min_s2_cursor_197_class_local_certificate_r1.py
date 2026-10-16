"""Exact local upper-bound certificate for the frozen 197-profile W=774..785 class.

Frozen authority is the six-row cursor partition in the SHA-pinned six-row result,
cross-checked against the embedded copy in the SHA-pinned seven-row result. The
frozen class-only family maximum stays 313398532. A separately pinned 19-event
local result supplies the resolved next bound 313392516 and owner; it is used
only for the prospective max after replacing the unresolved class cursor with
the new class candidate. The source result and its ledger digests are checked
without copying or rebuilding its resolved ledger.
frontier is rebuilt from all 5,126 bounded non-increasing degree histograms and
the three existing necessary screens: triple-pair capacity, graphical residual
pair degrees, and graphical triple-shadow degrees. These are necessary conditions
for a legal 22-triple/27-pair support realization; they are not sampled witnesses
and are not claimed sufficient.

For every legal support realization, the overlap graph is simple, has 20 vertices,
93 edges, and degrees g_i=6+d_i in [6,12]. If it had no induced P3, it would be a
disjoint union of cliques. The degree interval forces every clique component to
have size 7..13; the only partitions of 20 are 7+13, 8+12, 9+11, and 10+10,
with respectively 99, 94, 91, and 90 edges, never 93. The R18 induced-P3
injection therefore gives at least delta-1=5 open wedges in every legal graph.
Since a graph triangle consumes exactly three wedges, every realization with T
triangles satisfies 22 <= T <= floor((W-5)/3). The checker enumerates every
integer T in this necessary superset, not a sample of realizations.

For each such T, let O=W-3T. Across all vertices, sum_i C(g_i,3) counts
candidate triples in neighbourhoods. Every candidate that is not a triangle
contains an open wedge, and one open wedge can be extended by at most g_max-2
third vertices. Thus 4*K4 >= sum_i C(g_i,3)-(g_max-2)*O, which gives R30's
integer ceiling for K4. The frozen R30 four-ticket calculation gives minimum
S4 weight 448 for any K4 motif (679 when no core triple is contained). Since
all S4 contributions are nonnegative and K4 motifs are distinct terms,
S4 >= max(S4_base, 448*K4). R20/R32's exact S3 identity and Bonferroni credit
then give ceil(S1-S2+S3-4*S4/7). Integer-engine and Fraction paths are checked
term-by-term over all profiles and all admissible T values.

This is a local mathematical candidate only. It does not update or accept Family
Authority, claim independent judging, or assert global K20 optimality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import ceil, comb
from pathlib import Path
from time import process_time
from typing import cast

from . import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
from . import b649_k20_min_s2_current_cursor_dynamic_family_max_r30 as r30
from . import b649_k20_min_s2_cursor_plateau_closure_r18 as r18
from . import b649_k20_min_s2_next_active_profile_exact_bound_r8 as r8
from . import b649_k20_min_s2_realizable_core_class_bound_r4 as r4
from . import b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 as r20
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_topw12_coverage_repair_r1 as partition_source

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
SIX_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
SEVEN_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
)
SIX_ROW_RESULT_SHA256 = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
SEVEN_ROW_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
NINETEEN_EVENT_WORKTREE = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_NINETEEN_EVENT_LOCAL_FAMILY_AUTHORITY_R1"
)
NINETEEN_EVENT_HEAD = "2f208ec87f7be5e536153b2b1f56f9f3ec5b7ae5"
NINETEEN_EVENT_TREE = "24256dda5764c9b3f3f88d62728384c1a70ea2ba"
NINETEEN_EVENT_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-nineteen-event-local-family-authority-r1-result.json"
)
NINETEEN_EVENT_RESULT_SHA256 = "561768b28ab5115a98637f8148d159545e79a37bff985af410be6a9cb16c391d"
PARTITION_NAME = "UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"
PARTITION_COUNT = 197
PARTITION_IDS_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
W_RANGE = (774, 785)
OLD_CLASS_BOUND = 313_394_584
EXPECTED_CLASS_BOUND = 313_258_872
FROZEN_FAMILY_BOUND = 313_398_532
NINETEEN_EVENT_FAMILY_BOUND = 313_394_584
NINETEEN_EVENT_NEXT_RESOLVED_BOUND = 313_392_516
NINETEEN_EVENT_NEXT_RESOLVED_OWNER = "65555555555541000000"
EXPECTED_PROSPECTIVE_FAMILY_BOUND = 313_392_516
INCUMBENT = 313_263_888
OPEN_WEDGE_FLOOR = 5
K4_MINIMUM_S4_WEIGHT = 448
K4_WEIGHTS_EXPECTED = {
    "SIX_EDGES_WITH_CONTAINED_TRIPLE": 448,
    "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": 679,
}
RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/"
    / "b649-k20-min-s2-cursor-197-class-local-certificate-r1-result.json"
)
FOCUSED_TEST_PATH = "tests/unit/test_b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
FOCUSED_TEST_COMMAND = (
    "PYTHONPATH=src uv run --no-project --python 3.13 --with 'numpy>=2.0' "
    "--with pytest pytest -q "
    "tests/unit/test_b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
)
REPRODUCIBLE_COMMAND = (
    "PYTHONPATH=src uv run --no-project --python 3.13 --with 'numpy>=2.0' "
    "python -m lottolab.research.b649_k20_min_s2_cursor_197_class_local_certificate_r1 "
    "--write-result --focused-test-exit-code 0 --ruff-status PASS --pyright-status PASS"
)
Profile = tuple[int, ...]
Term = tuple[int, int, int, int, int]
ROOT = Path(__file__).resolve().parents[3]


class CertificateError(ValueError):
    """A frozen input, proof premise, or computed bound failed its exact check."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CertificateError(message)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CertificateError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise CertificateError(f"{label} must be an exact integer")
    return value


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def _json_blob(path: str) -> tuple[dict[str, object], bytes]:
    blob = _git("show", f"{FROZEN_HEAD}:{path}")
    return _object(json.loads(blob), path), blob


def _nineteen_event_git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(NINETEEN_EVENT_WORKTREE), *args], cwd=ROOT
    )


def _nineteen_event_source(
    *,
    expected_head: str = NINETEEN_EVENT_HEAD,
    expected_tree: str = NINETEEN_EVENT_TREE,
    expected_result_sha256: str = NINETEEN_EVENT_RESULT_SHA256,
) -> tuple[dict[str, object], str]:
    """Read the pinned 19-event result without copying its resolved ledger."""

    _require(expected_head == NINETEEN_EVENT_HEAD, "19-event HEAD identity mismatch")
    _require(expected_tree == NINETEEN_EVENT_TREE, "19-event tree identity mismatch")
    _require(
        expected_result_sha256 == NINETEEN_EVENT_RESULT_SHA256,
        "expected 19-event result digest mismatch",
    )
    head = _nineteen_event_git("rev-parse", "HEAD").decode().strip()
    tree = _nineteen_event_git("rev-parse", "HEAD^{tree}").decode().strip()
    _require(head == NINETEEN_EVENT_HEAD, "19-event worktree HEAD mismatch")
    _require(tree == NINETEEN_EVENT_TREE, "19-event worktree tree mismatch")
    committed_blob = _nineteen_event_git(
        "show", f"{NINETEEN_EVENT_HEAD}:{NINETEEN_EVENT_RESULT_PATH}"
    )
    worktree_result = NINETEEN_EVENT_WORKTREE / NINETEEN_EVENT_RESULT_PATH
    _require(
        worktree_result.read_bytes() == committed_blob,
        "19-event result differs from its pinned committed blob",
    )
    digest = hashlib.sha256(committed_blob).hexdigest()
    _require(digest == NINETEEN_EVENT_RESULT_SHA256, "19-event result digest mismatch")
    result = _object(json.loads(committed_blob), NINETEEN_EVENT_RESULT_PATH)
    _require(
        result.get("TASK_ID") == "B649_NINETEEN_EVENT_LOCAL_FAMILY_AUTHORITY_R1",
        "19-event task identity mismatch",
    )
    frozen = _object(result.get("FROZEN_AUTHORITY"), "19-event frozen authority")
    _require(frozen.get("HEAD") == FROZEN_HEAD, "19-event frozen HEAD mismatch")
    _require(frozen.get("TREE") == FROZEN_TREE, "19-event frozen tree mismatch")
    _require(
        frozen.get("RESULT_SHA256") == SEVEN_ROW_RESULT_SHA256,
        "19-event frozen family source mismatch",
    )
    family = _object(result.get("FAMILY_AFTER"), "19-event family after")
    cursor = _object(family.get("CURSOR"), "19-event family cursor")
    _require(
        _integer(family.get("FAMILY_BOUND"), "19-event family bound")
        == NINETEEN_EVENT_FAMILY_BOUND,
        "19-event family bound mismatch",
    )
    _require(
        _integer(cursor.get("BOUND"), "19-event cursor bound") == OLD_CLASS_BOUND,
        "19-event cursor class bound mismatch",
    )
    _require(
        _integer(family.get("NEXT_COMPETING_BOUND"), "19-event next resolved bound")
        == NINETEEN_EVENT_NEXT_RESOLVED_BOUND,
        "19-event next resolved bound mismatch",
    )
    owners = family.get("NEXT_COMPETING_OWNERS")
    _require(
        owners == [NINETEEN_EVENT_NEXT_RESOLVED_OWNER],
        "19-event next resolved owner mismatch",
    )
    _require(
        _integer(result.get("NEXT_DISTINCT_BOUND"), "19-event next distinct bound")
        == NINETEEN_EVENT_NEXT_RESOLVED_BOUND,
        "19-event ledger next bound mismatch",
    )
    _require(
        result.get("NEXT_RESOLVED_OWNER") == [NINETEEN_EVENT_NEXT_RESOLVED_OWNER],
        "19-event ledger next owner mismatch",
    )
    overlay = _object(result.get("LEDGER_OVERLAY"), "19-event ledger overlay")
    _require(
        _integer(overlay.get("ROWS_AFTER"), "19-event ledger row count") == 4_647,
        "19-event resolved ledger row count mismatch",
    )
    _require(
        overlay.get("BOUNDS_DIGEST_AFTER") == result.get("NEW_BOUNDS_DIGEST"),
        "19-event bounds digest mismatch",
    )
    _require(
        overlay.get("FULL_DIGEST_AFTER") == result.get("NEW_FULL_DIGEST"),
        "19-event full ledger digest mismatch",
    )
    _require(
        overlay.get("SOURCE_METADATA_BINDINGS") == "VERIFIED"
        and result.get("ROW_SOURCE_METADATA_VERIFIED") == "YES",
        "19-event ledger source metadata is not verified",
    )
    return result, digest


def verify_frozen_source_identity(
    *,
    frozen_head: str = FROZEN_HEAD,
    frozen_tree: str = FROZEN_TREE,
    six_result_sha256: str = SIX_ROW_RESULT_SHA256,
    seven_result_sha256: str = SEVEN_ROW_RESULT_SHA256,
    nineteen_event_head: str = NINETEEN_EVENT_HEAD,
    nineteen_event_tree: str = NINETEEN_EVENT_TREE,
    nineteen_event_result_sha256: str = NINETEEN_EVENT_RESULT_SHA256,
) -> dict[str, object]:
    """Bind frozen partition sources and the separate pinned 19-event ledger."""

    _require(frozen_head == FROZEN_HEAD, "frozen HEAD identity mismatch")
    _require(frozen_tree == FROZEN_TREE, "frozen tree identity mismatch")
    _require(
        _git("rev-parse", f"{FROZEN_HEAD}^{{tree}}").decode().strip() == FROZEN_TREE,
        "frozen HEAD tree mismatch",
    )
    six, six_blob = _json_blob(SIX_RESULT_PATH)
    seven, seven_blob = _json_blob(SEVEN_RESULT_PATH)
    six_digest = hashlib.sha256(six_blob).hexdigest()
    seven_digest = hashlib.sha256(seven_blob).hexdigest()
    _require(six_result_sha256 == SIX_ROW_RESULT_SHA256, "expected six-row digest mismatch")
    _require(seven_result_sha256 == SEVEN_ROW_RESULT_SHA256, "expected seven-row digest mismatch")
    _require(six_digest == SIX_ROW_RESULT_SHA256, "frozen six-row result digest mismatch")
    _require(seven_digest == SEVEN_ROW_RESULT_SHA256, "frozen seven-row result digest mismatch")

    partition = _object(six.get("CURSOR_PARTITION_AUTHORITY"), "six-row partition authority")
    frontier = _object(partition.get(PARTITION_NAME), "six-row unresolved frontier")
    cursor = _object(six.get("CURSOR"), "six-row cursor")
    _require(
        _integer(frontier.get("COUNT"), "partition count") == PARTITION_COUNT,
        "partition count mismatch",
    )
    _require(frontier.get("IDS_SHA256") == PARTITION_IDS_SHA256, "partition digest mismatch")
    _require(frontier.get("W_RANGE") == list(W_RANGE), "partition W range mismatch")
    _require(
        _integer(cursor.get("BOUND"), "cursor bound") == OLD_CLASS_BOUND,
        "old class bound mismatch",
    )
    _require(
        seven.get("SIX_ROW_RESULT_SHA256") == SIX_ROW_RESULT_SHA256,
        "seven-row six-result link mismatch",
    )
    preserved = _object(seven.get("PRESERVED_SIX_ROW_STATUS"), "preserved six-row status")
    _require(
        preserved.get("CURSOR_PARTITION_AUTHORITY") == partition,
        "six/seven-row partition authorities differ",
    )
    nineteen, nineteen_digest = _nineteen_event_source(
        expected_head=nineteen_event_head,
        expected_tree=nineteen_event_tree,
        expected_result_sha256=nineteen_event_result_sha256,
    )
    return {
        "SIX_RESULT": six,
        "SEVEN_RESULT": seven,
        "NINETEEN_EVENT_RESULT": nineteen,
        "PARTITION_AUTHORITY": frontier,
        "SIX_ROW_RESULT_SHA256": six_digest,
        "SEVEN_ROW_RESULT_SHA256": seven_digest,
        "NINETEEN_EVENT_RESULT_SHA256": nineteen_digest,
    }


def _module_provenance() -> dict[str, str]:
    """Require the profile and math helpers to equal their frozen Git blobs."""

    modules = (*partition_source.PROVENANCE_MODULES, r18, r20)
    provenance: dict[str, str] = {}
    for module in modules:
        module_path = module.__file__
        if module_path is None:
            raise CertificateError("frozen helper has no source path")
        source = Path(module_path).resolve()
        _require(source.is_relative_to(ROOT), f"helper outside candidate worktree: {source}")
        relative = source.relative_to(ROOT).as_posix()
        committed = _git("show", f"{FROZEN_HEAD}:{relative}")
        _require(source.read_bytes() == committed, f"frozen helper changed: {relative}")
        provenance[relative] = hashlib.sha256(committed).hexdigest()
    return dict(sorted(provenance.items()))


def _profile_ids(profiles: Sequence[Profile]) -> list[str]:
    return [r20.profile_id(profile) for profile in sorted(profiles, reverse=True)]


def _ids_digest(ids: Sequence[str]) -> str:
    return hashlib.sha256(json.dumps(list(ids)).encode()).hexdigest()


def validate_partition_profiles(
    profiles: Sequence[Profile],
    *,
    expected_count: int = PARTITION_COUNT,
    expected_digest: str = PARTITION_IDS_SHA256,
    expected_w_range: tuple[int, int] = W_RANGE,
) -> list[str]:
    """Check exact sorted membership cardinality, uniqueness, digest, and W range."""

    _require(len(profiles) == expected_count, "partition profile count mismatch")
    _require(len(set(profiles)) == len(profiles), "partition contains duplicate profiles")
    _require(
        all(
            len(profile) == r4.K20_TICKET_COUNT
            and profile == tuple(sorted(profile, reverse=True))
            and all(type(d) is int and 0 <= d <= r4.K20_TICKET_CAPACITY for d in profile)
            and sum(profile) == r4.K20_TRIPLE_INCIDENCE_COUNT
            for profile in profiles
        ),
        "partition contains an invalid degree profile",
    )
    ids = _profile_ids(profiles)
    _require(ids == sorted(ids, reverse=True), "partition ids are not sorted")
    _require(_ids_digest(ids) == expected_digest, "partition membership digest mismatch")
    actual_w = (
        min(r4.overlap_wedge_count(profile) for profile in profiles),
        max(r4.overlap_wedge_count(profile) for profile in profiles),
    )
    _require(actual_w == expected_w_range, "partition W range mismatch")
    return ids


def rebuild_frontier() -> tuple[tuple[Profile, ...], dict[str, object]]:
    """Rebuild the W=774..785 frontier as the exact frozen partition component."""

    authority = verify_frozen_source_identity()
    frontier_authority = _object(authority["PARTITION_AUTHORITY"], "frontier authority")
    six = _object(authority["SIX_RESULT"], "six-row result")
    cursor = _object(six.get("CURSOR"), "six-row cursor")
    cursor_id = cursor.get("ID")
    _require(isinstance(cursor_id, str), "cursor id missing")
    cursor_profile = r20.decode_profile(cursor_id)
    cursor_w = r4.overlap_wedge_count(cursor_profile)
    cursor_bound = _integer(cursor.get("BOUND"), "cursor bound")
    _require(cursor_w == 785 and cursor_bound == OLD_CLASS_BOUND, "frozen cursor identity mismatch")

    universe = partition_source.build_universe()
    band = universe.band(*W_RANGE)
    dominated = {
        profile
        for profile in universe.admissible
        if r4.overlap_wedge_count(profile) <= cursor_w
        and r8.coarse_profile_envelope(profile).family_upper_bound <= cursor_bound
    }
    _require(dominated == band, "frozen frontier rule differs from the complete W band")
    profiles = tuple(sorted(band, reverse=True))
    authority_count = _integer(frontier_authority.get("COUNT"), "partition authority count")
    authority_digest = frontier_authority.get("IDS_SHA256")
    if not isinstance(authority_digest, str):
        raise CertificateError("partition digest missing")
    authority_range_raw = frontier_authority.get("W_RANGE")
    if not isinstance(authority_range_raw, list):
        raise CertificateError("partition authority W range malformed")
    authority_range_values = cast(list[object], authority_range_raw)
    if len(authority_range_values) != 2:
        raise CertificateError("partition authority W range malformed")
    authority_range: tuple[int, int] = (
        _integer(authority_range_values[0], "partition minimum W"),
        _integer(authority_range_values[1], "partition maximum W"),
    )
    ids = validate_partition_profiles(
        profiles,
        expected_count=authority_count,
        expected_digest=authority_digest,
        expected_w_range=authority_range,
    )
    _require(authority_count == PARTITION_COUNT, "frozen partition count changed")
    _require(authority_digest == PARTITION_IDS_SHA256, "frozen partition digest changed")
    _require(authority_range == W_RANGE, "frozen partition W range changed")
    frontier: dict[str, object] = {
        "PROFILE_IDS": ids,
        "PROFILE_COUNT": len(profiles),
        "MISSING_PROFILES": 0,
        "DUPLICATE_PROFILES": 0,
        "PROFILE_IDS_SHA256": _ids_digest(ids),
        "W_RANGE": list(authority_range),
        "FROZEN_PARTITION_NAME": PARTITION_NAME,
        "REBUILD_RULE": "ADMISSIBLE_UNIVERSE_INTERSECT_W_774_785_DOMINATED_BY_W785_CURSOR",
    }
    return profiles, {**authority, "REBUILT_FRONTIER": frontier}


def max_triangles_from_open_wedge_floor(
    profile: Profile, *, open_wedge_floor: int = OPEN_WEDGE_FLOOR
) -> int:
    """Return the full integer T domain ceiling, rejecting a changed wedge premise."""

    engine_floor = r18.generic_open_wedge_floor(
        r4.K20_TICKET_COUNT,
        3 * r4.K20_TRIPLE_SUPPORT_COUNT + r4.K20_DOUBLE_SUPPORT_COUNT,
        r4.K20_TICKET_CAPACITY,
        2 * r4.K20_TICKET_CAPACITY,
    )
    _require(engine_floor == OPEN_WEDGE_FLOOR, "frozen R18 open-wedge floor changed")
    _require(open_wedge_floor == engine_floor, "open-wedge lower bound mismatch")
    wedges = r4.overlap_wedge_count(profile)
    cap = (wedges - open_wedge_floor) // 3
    _require(cap >= r4.K20_TRIPLE_SUPPORT_COUNT, "open-wedge cap excludes the 22 core triangles")
    _require(wedges - 3 * cap >= open_wedge_floor, "open-wedge cap is not admissible")
    _require(wedges - 3 * (cap + 1) < open_wedge_floor, "open-wedge cap is not maximal")
    return cap


def exact_term(profile: Profile, triangles: int, *, base_s4: int) -> Term:
    """Cross-check one R30/R32 integer term against a separate Fraction derivation."""

    cap = max_triangles_from_open_wedge_floor(profile)
    _require(
        r4.K20_TRIPLE_SUPPORT_COUNT <= triangles <= cap,
        "triangle count outside the complete open-wedge domain",
    )
    weights = r30.k4_quartet_weights()
    _require(weights == K4_WEIGHTS_EXPECTED, "frozen R30 K4/S4 motif weights changed")
    wedges = r4.overlap_wedge_count(profile)
    graph_degrees = tuple(r4.K20_TICKET_CAPACITY + d for d in profile)
    open_wedges = wedges - 3 * triangles

    engine_k4, engine_s4_motif = r30.motif_s4_floor(profile, triangles)
    s4 = max(base_s4, engine_s4_motif)
    s3_engine, bound_engine = r32.bound_from_cap(profile, triangles, s4)

    excess = sum(comb(degree, 3) for degree in graph_degrees) - (
        max(graph_degrees) - 2
    ) * open_wedges
    k4_exact = max(0, -(-excess // 4))
    s4_exact = max(base_s4, K4_MINIMUM_S4_WEIGHT * k4_exact)
    noncore_triangles = triangles - r4.K20_TRIPLE_SUPPORT_COUNT
    s3_exact = (
        2_800 * (wedges - 3 * triangles)
        + 20_272 * noncore_triangles
        + 7_000 * r4.K20_TRIPLE_SUPPORT_COUNT
    )
    exact_bound = Fraction(r4.K20_S1 - r4.K20_S2 + s3_exact, 1) - Fraction(4 * s4_exact, 7)
    bound_exact = ceil(exact_bound)

    _require(engine_k4 == k4_exact, "R30 K4 ceiling disagrees with exact integer derivation")
    _require(engine_s4_motif == K4_MINIMUM_S4_WEIGHT * k4_exact, "R30 S4 credit mismatch")
    _require(s4 == s4_exact, "S4 base/credit differs from exact derivation")
    _require(s3_engine == s3_exact, "R32 S3 term disagrees with exact source formula")
    _require(bound_engine == bound_exact, "integer and exact-rational bounds differ")
    _require(0 <= Fraction(bound_engine, 1) - exact_bound < 1, "exact bound rounding is invalid")
    return triangles, bound_engine, engine_k4, s4, s3_engine


def profile_terms(profile: Profile) -> tuple[Term, ...]:
    """Evaluate every integer triangle count admitted by the necessary wedge floor."""

    base_s4 = r28.profile_s4_floor(profile)
    cap = max_triangles_from_open_wedge_floor(profile)
    return tuple(
        exact_term(profile, triangles, base_s4=base_s4)
        for triangles in range(r4.K20_TRIPLE_SUPPORT_COUNT, cap + 1)
    )


def verify_profile_maximum(terms: Sequence[Sequence[int]], claimed_maximum: int) -> None:
    """Reject a profile certificate whose claimed bound is not the maximum of all T terms."""

    _require(bool(terms), "profile has no triangle terms")
    _require(all(len(term) == 5 and type(term[1]) is int for term in terms), "malformed term table")
    maximum = max(term[1] for term in terms)
    _require(maximum == claimed_maximum, "profile maximum does not match its complete term table")


def verify_class_maximum(
    profile_rows: Sequence[Mapping[str, object]], claimed_maximum: int
) -> None:
    """Reject a class maximum that is not the maximum across all profile rows."""

    _require(len(profile_rows) == PARTITION_COUNT, "class maximum lacks complete profile coverage")
    values = [
        _integer(row.get("CLASS_BOUND_AFTER"), "per-profile class bound")
        for row in profile_rows
    ]
    _require(max(values) == claimed_maximum, "class maximum does not match the 197 profile bounds")


def _profile_record(profile: Profile) -> dict[str, object]:
    terms = profile_terms(profile)
    term_rows = [list(term) for term in terms]
    maximum = max(term[1] for term in terms)
    verify_profile_maximum(term_rows, maximum)
    cap = max_triangles_from_open_wedge_floor(profile)
    argmax = max(term[0] for term in terms if term[1] == maximum)
    return {
        "PROFILE_ID": r20.profile_id(profile),
        "WEDGE_COUNT": r4.overlap_wedge_count(profile),
        "TRIANGLE_MIN": r4.K20_TRIPLE_SUPPORT_COUNT,
        "TRIANGLE_MAX": cap,
        "BASE_S4_FLOOR": r28.profile_s4_floor(profile),
        "TERM_COUNT": len(terms),
        "CLASS_BOUND_AFTER": maximum,
        "MAXIMIZING_TRIANGLE_COUNT": argmax,
        "TERMS_COLUMNS": ["T", "BOUND", "K4_FLOOR", "S4_FLOOR", "S3"],
        "TERMS": term_rows,
    }


def calculate_prospective_family_bound(
    six: Mapping[str, object],
    seven: Mapping[str, object],
    nineteen_event: Mapping[str, object],
    class_bound: int,
) -> dict[str, object]:
    """Keep frozen, 19-event, class-only, and prospective maxima separate."""

    raw_bounds = _object(six.get("RESOLVED_ROW_BOUNDS"), "six-row resolved bounds")
    bounds: dict[str, int] = {
        profile: _integer(value, f"six-row bound for {profile}")
        for profile, value in raw_bounds.items()
    }
    update = _object(seven.get("ROW_UPDATE"), "seven-row update")
    profile_id = update.get("PROFILE_ID")
    if not isinstance(profile_id, str) or profile_id not in bounds:
        raise CertificateError("seven-row profile is not in six-row ledger")
    before = _integer(seven.get("PROFILE_BOUND_BEFORE"), "seven-row prior profile bound")
    after = _integer(seven.get("PROFILE_BOUND_AFTER"), "seven-row updated profile bound")
    _require(bounds[profile_id] == before, "seven-row update does not match six-row ledger")
    bounds[profile_id] = after
    resolved_max = max(bounds.values())
    _require(
        resolved_max == _integer(seven.get("FAMILY_BOUND_AFTER"), "seven-row family bound"),
        "seven-row family maximum does not match the updated resolved ledger",
    )
    _require(
        resolved_max == FROZEN_FAMILY_BOUND,
        "frozen six/seven-row family maximum differs from its pinned value",
    )
    family_after = _object(nineteen_event.get("FAMILY_AFTER"), "19-event family after")
    _require(
        _integer(family_after.get("FAMILY_BOUND"), "19-event family bound")
        == NINETEEN_EVENT_FAMILY_BOUND,
        "19-event family bound does not match its pinned result",
    )
    next_resolved_bound = _integer(
        family_after.get("NEXT_COMPETING_BOUND"), "19-event next resolved bound"
    )
    _require(
        next_resolved_bound == NINETEEN_EVENT_NEXT_RESOLVED_BOUND,
        "19-event next resolved bound mismatch",
    )
    owners = family_after.get("NEXT_COMPETING_OWNERS")
    _require(
        owners == [NINETEEN_EVENT_NEXT_RESOLVED_OWNER],
        "19-event next resolved owner differs from its pinned result",
    )
    prospective = max(next_resolved_bound, class_bound)
    _require(
        prospective == EXPECTED_PROSPECTIVE_FAMILY_BOUND,
        "19-event next resolved bound and class candidate do not yield expected projection",
    )
    return {
        "FROZEN_FAMILY_BOUND": resolved_max,
        "FROZEN_CLASS_ONLY_FAMILY_BOUND": resolved_max,
        "NINETEEN_EVENT_RESOLVED_LEDGER_ROW_COUNT": _integer(
            _object(nineteen_event.get("LEDGER_OVERLAY"), "19-event ledger overlay").get(
                "ROWS_AFTER"
            ),
            "19-event ledger row count",
        ),
        "NINETEEN_EVENT_BOUNDS_DIGEST": _object(
            nineteen_event.get("LEDGER_OVERLAY"), "19-event ledger overlay"
        ).get("BOUNDS_DIGEST_AFTER"),
        "NINETEEN_EVENT_FULL_LEDGER_DIGEST": _object(
            nineteen_event.get("LEDGER_OVERLAY"), "19-event ledger overlay"
        ).get("FULL_DIGEST_AFTER"),
        "NINETEEN_EVENT_FAMILY_BOUND": NINETEEN_EVENT_FAMILY_BOUND,
        "NINETEEN_EVENT_NEXT_RESOLVED_BOUND": next_resolved_bound,
        "NINETEEN_EVENT_NEXT_RESOLVED_OWNER": NINETEEN_EVENT_NEXT_RESOLVED_OWNER,
        "NEW_CLASS_BOUND_CANDIDATE": class_bound,
        "PROSPECTIVE_FAMILY_BOUND": prospective,
        "SEVEN_ROW_UPDATED_PROFILE": profile_id,
        "EXPECTED_PROSPECTIVE_FAMILY_BOUND": EXPECTED_PROSPECTIVE_FAMILY_BOUND,
        "EXPECTED_PROSPECTIVE_BOUND_MATCH": True,
    }


def _verification_record(
    focused_test_exit_code: int | None,
    ruff_status: str,
    pyright_status: str,
) -> dict[str, object]:
    passed = focused_test_exit_code == 0
    negative_status = "PASS" if passed else "NOT_RUN"
    return {
        "FOCUSED_TEST_COMMAND": FOCUSED_TEST_COMMAND,
        "FOCUSED_TEST_EXIT_CODE": focused_test_exit_code,
        "NEGATIVE_CASE_RESULTS": {
            "FROZEN_SOURCE_IDENTITY": negative_status,
            "PARTITION_OMISSION_AND_DUPLICATE": negative_status,
            "W_RANGE": negative_status,
            "OPEN_WEDGE_LOWER_BOUND": negative_status,
            "K4_CEILING": negative_status,
            "S4_CREDIT": negative_status,
            "PARTITION_MAXIMUM": negative_status,
        },
        "RUFF": ruff_status,
        "PYRIGHT": pyright_status,
        "CPU_PROCESS_COUNT": 1,
        "HEAVY_SOLVER_STARTED": "NO",
    }


def build_result(
    *,
    focused_test_exit_code: int | None = None,
    ruff_status: str = "NOT_RUN",
    pyright_status: str = "NOT_RUN",
) -> dict[str, object]:
    """Rebuild the full candidate table, all term checks, and prospective ledger maximum."""

    provenance = _module_provenance()
    profiles, authority = rebuild_frontier()
    identity = verify_frozen_source_identity()
    records = [_profile_record(profile) for profile in profiles]
    term_count = sum(_integer(row["TERM_COUNT"], "profile term count") for row in records)
    class_after = max(_integer(row["CLASS_BOUND_AFTER"], "profile class bound") for row in records)
    verify_class_maximum(records, class_after)
    class_before = max(
        r8.coarse_profile_envelope(profile).family_upper_bound for profile in profiles
    )
    _require(class_before == OLD_CLASS_BOUND, "old class maximum differs from frozen cursor bound")
    _require(
        class_after == EXPECTED_CLASS_BOUND,
        "computed class maximum differs from the expected candidate bound",
    )
    _require(len(records) == PARTITION_COUNT, "complete class profile coverage failed")
    _require(
        _ids_digest([cast(str, row["PROFILE_ID"]) for row in records]) == PARTITION_IDS_SHA256,
        "computed profile rows do not match the frozen membership digest",
    )

    weights = r30.k4_quartet_weights()
    _require(weights == K4_WEIGHTS_EXPECTED, "R30 quartet weights fail the frozen proof")
    clique_partitions = r18.clique_partition_edge_totals(
        r4.K20_TICKET_COUNT,
        r4.K20_TICKET_CAPACITY,
        2 * r4.K20_TICKET_CAPACITY,
    )
    forbidden_partitions = [
        {"COMPONENT_SIZES": list(sizes), "EDGE_COUNT": edges}
        for sizes, edges in clique_partitions
        if edges == 3 * r4.K20_TRIPLE_SUPPORT_COUNT + r4.K20_DOUBLE_SUPPORT_COUNT
    ]
    _require(not forbidden_partitions, "93-edge clique partition invalidates the induced-P3 floor")
    class_authority = _object(authority["SIX_RESULT"], "six-row result")
    seven = _object(authority["SEVEN_RESULT"], "seven-row result")
    nineteen_event = _object(authority["NINETEEN_EVENT_RESULT"], "19-event result")
    prospective = calculate_prospective_family_bound(
        class_authority, seven, nineteen_event, class_after
    )
    prospective_family_bound = _integer(
        prospective["PROSPECTIVE_FAMILY_BOUND"], "prospective family bound"
    )
    artifact_hashes = {
        "SOURCE_SHA256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
        "TEST_SHA256": hashlib.sha256((ROOT / FOCUSED_TEST_PATH).read_bytes()).hexdigest(),
    }
    ledger_overlay = _object(nineteen_event.get("LEDGER_OVERLAY"), "19-event ledger overlay")
    return {
        "TASK_ID": "B649_CURSOR_197_CLASS_LOCAL_CERTIFICATE_R1",
        "STATUS": "LOCAL_MATHEMATICAL_CANDIDATE",
        "BASE_HEAD": FROZEN_HEAD,
        "BASE_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE_MATCH": True,
        "SIX_ROW_RESULT_PATH": SIX_RESULT_PATH,
        "SIX_ROW_RESULT_SHA256": identity["SIX_ROW_RESULT_SHA256"],
        "SEVEN_ROW_RESULT_PATH": SEVEN_RESULT_PATH,
        "SEVEN_ROW_RESULT_SHA256": identity["SEVEN_ROW_RESULT_SHA256"],
        "NINETEEN_EVENT_RESULT_PATH": NINETEEN_EVENT_RESULT_PATH,
        "NINETEEN_EVENT_WORKTREE": str(NINETEEN_EVENT_WORKTREE),
        "NINETEEN_EVENT_HEAD": NINETEEN_EVENT_HEAD,
        "NINETEEN_EVENT_TREE": NINETEEN_EVENT_TREE,
        "NINETEEN_EVENT_RESULT_SHA256": identity["NINETEEN_EVENT_RESULT_SHA256"],
        "NINETEEN_EVENT_LEDGER_PROVENANCE": {
            "ROWS_AFTER": ledger_overlay["ROWS_AFTER"],
            "BOUNDS_DIGEST_AFTER": ledger_overlay["BOUNDS_DIGEST_AFTER"],
            "FULL_DIGEST_AFTER": ledger_overlay["FULL_DIGEST_AFTER"],
            "SOURCE_METADATA_BINDINGS": ledger_overlay["SOURCE_METADATA_BINDINGS"],
        },
        "PARTITION_NAME": PARTITION_NAME,
        "PARTITION_COUNT": PARTITION_COUNT,
        "COVERED_PROFILES": len(records),
        "MISSING_PROFILES": 0,
        "DUPLICATE_PROFILES": 0,
        "PARTITION_IDS_SHA256": PARTITION_IDS_SHA256,
        "W_RANGE": list(W_RANGE),
        "PROFILE_IDS": _object(authority["REBUILT_FRONTIER"], "rebuilt frontier")["PROFILE_IDS"],
        "PROFILE_BOUND_ROWS": records,
        "CLASS_BOUND_BEFORE": class_before,
        "CLASS_BOUND_AFTER": class_after,
        "CLASS_DELTA": class_before - class_after,
        "COMPLETE_CLASS_COVERAGE": True,
        "EXPECTED_CLASS_BOUND": EXPECTED_CLASS_BOUND,
        "EXPECTED_CLASS_BOUND_MATCH": class_after == EXPECTED_CLASS_BOUND,
        "NEW_BOUND_BELOW_INCUMBENT": class_after < INCUMBENT,
        "CLASS_BOUND_BELOW_INCUMBENT_BY": INCUMBENT - class_after,
        "FROZEN_FAMILY_BOUND": prospective["FROZEN_FAMILY_BOUND"],
        "FROZEN_CLASS_ONLY_FAMILY_BOUND": prospective[
            "FROZEN_CLASS_ONLY_FAMILY_BOUND"
        ],
        "NINETEEN_EVENT_FAMILY_BOUND": prospective["NINETEEN_EVENT_FAMILY_BOUND"],
        "NINETEEN_EVENT_NEXT_RESOLVED_BOUND": prospective[
            "NINETEEN_EVENT_NEXT_RESOLVED_BOUND"
        ],
        "NINETEEN_EVENT_NEXT_RESOLVED_OWNER": prospective[
            "NINETEEN_EVENT_NEXT_RESOLVED_OWNER"
        ],
        "NEW_CLASS_BOUND_CANDIDATE": prospective["NEW_CLASS_BOUND_CANDIDATE"],
        "PROSPECTIVE_FAMILY_BOUND": prospective_family_bound,
        "EXPECTED_PROSPECTIVE_FAMILY_BOUND": EXPECTED_PROSPECTIVE_FAMILY_BOUND,
        "EXPECTED_PROSPECTIVE_BOUND_MATCH": prospective["EXPECTED_PROSPECTIVE_BOUND_MATCH"],
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "FORMAL_AUTHORITY_STATUS": "NOT_ACCEPTED",
        "PROOF": {
            "SCOPE": "FULL_197_PROFILE_CLASS",
            "OPEN_WEDGES_GE_5_PROOF": {
                "STATUS": "PASS",
                "GRAPH_VERTICES": r4.K20_TICKET_COUNT,
                "GRAPH_EDGES": 3 * r4.K20_TRIPLE_SUPPORT_COUNT + r4.K20_DOUBLE_SUPPORT_COUNT,
                "GRAPH_DEGREE_RANGE": [r4.K20_TICKET_CAPACITY, 2 * r4.K20_TICKET_CAPACITY],
                "CLIQUE_PARTITION_EDGE_TOTALS": [
                    {"COMPONENT_SIZES": list(sizes), "EDGE_COUNT": edges}
                    for sizes, edges in clique_partitions
                ],
                "93_EDGE_CLIQUE_PARTITIONS": forbidden_partitions,
                "INDUCED_P3_INJECTION_FLOOR": OPEN_WEDGE_FLOOR,
                "TRIANGLE_DOMAIN": "22..floor((W-5)/3), inclusive",
                "DOMAIN_KIND": "COMPLETE_NECESSARY_SUPERSET_OF_REALIZABLE_TRIANGLE_COUNTS",
            },
            "K4_S4_PROOF": {
                "STATUS": "PASS",
                "K4_FLOOR": "max(0,ceil((sum(C(g_i,3))-(g_max-2)*(W-3*T))/4))",
                "K4_QUARTET_WEIGHTS": weights,
                "S4_FLOOR": "max(profile S4 base,448*K4)",
                "S4_CREDIT": "ceil(S1-S2+S3-4*S4/7), exact rational ceiling",
                "NECESSITY_SCOPE": "EVERY_LEGAL_SUPPORT_REALIZATION",
            },
            "EXACT_TERM_COUNT": term_count,
            "EXPECTED_EXACT_TERM_COUNT": 46_839,
            "EXACT_TERM_COUNT_MATCH": term_count == 46_839,
            "INTEGER_RATIONAL_CROSSCHECK": {
                "STATUS": "PASS",
                "TERMS_CHECKED": term_count,
                "INTEGER_ENGINE": "R30.motif_s4_floor + R32.bound_from_cap",
                "EXACT_RATIONAL_ENGINE": (
                    "independent integer K4 ceiling and fractions.Fraction S4 credit"
                ),
            },
        },
        "SOURCE_MODULE_SHA256": provenance,
        **artifact_hashes,
        "PROOF_LOCATOR": (
            "src/lottolab/research/b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
            "#build_result, exact_term, rebuild_frontier; module docstring"
        ),
        "REPRODUCIBLE_COMMAND": REPRODUCIBLE_COMMAND,
        "VERIFICATION": _verification_record(
            focused_test_exit_code, ruff_status, pyright_status
        ),
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "INDEPENDENT_JUDGE_CLAIMED": "NO",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }


def _write_result(result: Mapping[str, object]) -> str:
    payload = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--focused-test-exit-code", type=int)
    parser.add_argument("--ruff-status", choices=("PASS", "FAIL", "NOT_RUN"), default="NOT_RUN")
    parser.add_argument(
        "--pyright-status", choices=("PASS", "FAIL", "NOT_RUN"), default="NOT_RUN"
    )
    args = parser.parse_args()
    started = process_time()
    result = build_result(
        focused_test_exit_code=args.focused_test_exit_code,
        ruff_status=args.ruff_status,
        pyright_status=args.pyright_status,
    )
    result["CPU_SECONDS"] = round(process_time() - started, 6)
    digest = "NOT_WRITTEN"
    if args.write_result:
        digest = _write_result(result)
    print(
        json.dumps(
            {
                "CLASS_BOUND_BEFORE": result["CLASS_BOUND_BEFORE"],
                "CLASS_BOUND_AFTER": result["CLASS_BOUND_AFTER"],
                "COVERED_PROFILES": result["COVERED_PROFILES"],
                "EXACT_TERM_COUNT": _object(result["PROOF"], "proof")["EXACT_TERM_COUNT"],
                "PROSPECTIVE_FAMILY_BOUND": result["PROSPECTIVE_FAMILY_BOUND"],
                "EXPECTED_PROSPECTIVE_FAMILY_BOUND": EXPECTED_PROSPECTIVE_FAMILY_BOUND,
                "RESULT_SHA256": digest,
                "CPU_SECONDS": result["CPU_SECONDS"],
                "HEAVY_SOLVER_STARTED": "NO",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
