"""Focused gates for the R3 Hunter class-split ladder certificates and state term."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_r3_hunter_class_split_ladder_r1 as ladder
from lottolab.research import b649_k20_r3_hunter_next_sibling_certificate_r1 as sibling
from lottolab.research import b649_k20_r3_hunter_tree_member_certificate_r1 as hunter
from lottolab.research.b649_k20_r3_frontier_realizability_bound_r8 import (
    _pair_event_correction_table,  # pyright: ignore[reportPrivateUsage]
)

FIRST, CARRIED, THIRD, FOURTH, FIFTH, SIXTH = ladder.LADDER
OUTSIDE_FLOORS = (107_800, 568_610, 1_667_932, 3_406_165)
OUTSIDE_FLOORS_NO_TYPE5 = (107_800, 568_680, 1_669_066, 3_408_685)
CORE_FLOORS_TYPE5_PAIR = (102_536, 535_542, 1_588_965, 3_260_138)
CORE_FLOORS_ONE_TYPE5 = (102_760, 537_082, 1_592_605, 3_266_116)
CORE_FLOORS_TYPE16_ONLY = (102_900, 539_196, 1_599_493, 3_270_148)
# member: (rows, Q, class mass floors, homogeneous, class split, certified bound)
EXPECTED = {
    FIRST: (20, 80, (38, 4), 7_372_190, 7_790_062, 353_098_606),
    THIRD: (35, 80, (38, 0), 7_372_190, 7_790_062, 353_097_710),
    FOURTH: (35, 82, (38, 0), 7_372_190, 7_790_062, 353_097_262),
    FIFTH: (23, 85, (38, 1), 7_393_106, 7_791_602, 353_095_274),
    SIXTH: (15, 88, (38, 2), 7_421_148, 7_794_556, 353_091_872),
}
CLASS_FLOORS = {
    FIRST: (OUTSIDE_FLOORS, CORE_FLOORS_TYPE5_PAIR),
    THIRD: (OUTSIDE_FLOORS, CORE_FLOORS_TYPE5_PAIR),
    FOURTH: (OUTSIDE_FLOORS, CORE_FLOORS_TYPE5_PAIR),
    FIFTH: (OUTSIDE_FLOORS, CORE_FLOORS_ONE_TYPE5),
    SIXTH: (OUTSIDE_FLOORS_NO_TYPE5, CORE_FLOORS_TYPE16_ONLY),
}
FIRST_COMMITTED_BOUND = 353_516_478
CARRIED_BOUND = 353_098_158
START_STATE_BOUND = 355_722_668
REFINED_STATE_BOUND = 355_274_920
R3_DURABLE_BOUND = 355_734_631
NEXT_OWNERS = {
    "[0,11][1,1][2,1][4,1][5,4]": 1,
    "[0,11][1,1][4,1][5,4][8,1]": 1,
    "[0,11][1,2][2,1][5,4]": 1,
    "[0,11][2,1][4,2][5,4]": 2,
    "[0,11][4,2][5,4][8,1]": 1,
}


CACHED = (
    ladder.region_maximum,
    ladder.witness_analysis,
    ladder.first_member_class_split,
    ladder.build_result,
    ladder.verify_ladder_identity,
)


@pytest.fixture
def fresh_caches() -> Iterator[None]:
    for function in CACHED:
        function.cache_clear()
    yield
    for function in CACHED:
        function.cache_clear()


def _r24_record() -> dict[str, Any]:
    text = (ladder.REPO_ROOT / hunter.R24_RESULT_RELATIVE).read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(text))


def test_ladder_identity_and_member_source_scope() -> None:
    cells = ladder.verify_ladder_identity()

    assert cells == {0: (0, 0, 0, 6), 5: (0, 1, 1, 4), 16: (1, 0, 0, 5)}
    assert [ladder.member_id(sparse) for sparse in ladder.LADDER] == [
        "[0,13][5,5]",
        "[0,13][5,4][16,1]",
        "[0,13][5,3][16,2]",
        "[0,13][5,2][16,3]",
        "[0,13][5,1][16,4]",
        "[0,13][16,5]",
    ]
    assert FIRST == hunter.MEMBER_SPARSE and CARRIED == sibling.MEMBER_SPARSE
    for sparse, expected in EXPECTED.items():
        counts = hunter.dense_counts(sparse)
        assert ladder.certified_member_bound(ladder.STATE_ID, counts) == expected[5]
        with pytest.raises(hunter.CertificateScopeError):
            ladder.certified_member_bound("state:other", counts)
    with pytest.raises(hunter.CertificateScopeError):
        ladder.certified_member_bound(ladder.STATE_ID, hunter.dense_counts(CARRIED))
    with pytest.raises(hunter.CertificateScopeError):
        ladder.certified_member_bound(
            ladder.STATE_ID, hunter.dense_counts(((0, 11), (4, 2), (5, 4), (8, 1)))
        )
    with pytest.raises(hunter.CertificateScopeError):
        ladder.build_member_certificate(CARRIED)


def test_type_specific_pair_tables_replay_r8_within_the_overlap_limits() -> None:
    for sparse, expected in EXPECTED.items():
        rows = ladder.member_rows(sparse)
        pairs = sibling.occurring_type_pairs(sparse)
        observed = sorted(
            (row.left_type, row.right_type, *row.overlap, row.residual_intersection) for row in rows
        )
        replay = sorted(
            (left, right, shared, a_only, b_only, outside, value)
            for left, right in pairs
            for shared, a_only, b_only, outside, value, _quadruple in (
                _pair_event_correction_table(left, right)
            )
        )
        counts = dict(sparse)

        assert len(rows) == expected[0] == len(replay)
        assert observed == replay
        assert ((16, 16) in pairs) == (counts.get(16, 0) >= 2)
        assert ((5, 5) in pairs) == (counts.get(5, 0) >= 2)
        assert {row.total_overlap for row in rows} <= {0, 1, 2, 3}
        assert sibling.class_edge_counts(sparse) == (143, 10)
        assert sibling.class_pair_floors(rows) == CLASS_FLOORS[sparse]
        assert sibling.global_pair_floors(rows) == min(CLASS_FLOORS[sparse])
    assert hunter.family_pair_overlap_ceiling() == 3
    with pytest.raises(ValueError, match="outside the R3 range"):
        hunter.threshold_edge_counts((4,))


def test_forced_collision_floors_and_class_specific_masses() -> None:
    for sparse, expected in EXPECTED.items():
        certificate = ladder.build_member_certificate(sparse)
        masses = ladder.class_masses(certificate.class_minimizer_counts)
        k = ladder.type16_count(sparse)

        assert certificate.cell_incidences == (k, 5 - k, 5 - k, 98 + k)
        assert certificate.collision_floor == expected[1]
        assert certificate.class_mass_floors == ladder.class_mass_floors(sparse) == expected[2]
        assert sum(masses) == certificate.collision_floor
        assert all(mass >= floor for mass, floor in zip(masses, expected[2], strict=True))
    with pytest.raises(AssertionError, match="exceed the total"):
        ladder.require_class_masses(((40, 0, 0), (40, 0, 0)), (60, 30), 80)
    with pytest.raises(AssertionError, match="class-specific forced mass"):
        ladder.require_class_masses(((80, 0, 0), (0, 0, 0)), (38, 2), 80)


def test_spanning_tree_rank_lower_bound_regressions_for_every_floor_pair() -> None:
    for floors in {CLASS_FLOORS[sparse] for sparse in EXPECTED}:
        regressions = sibling.tree_rank_regressions(floors)

        assert regressions["CLASS_THRESHOLD_TREE_EXHAUSTIVE_K4_LABELLINGS"] == 5 * 4**6
        assert regressions["EXACT_MASS_REDUCTION_K4_FLOORS_CHECKED"] > 0
        assert regressions["RANK_FLOOR_EXHAUSTIVE_GRAPHS_ON_6_VERTICES"] == 2**15
    assert [hunter.rank_floor(edges) for edges in (78, 79, 91, 92, 153)] == [12, 13, 13, 14, 17]


def test_finite_minimisation_reproduces_each_member_census() -> None:
    for sparse, expected in EXPECTED.items():
        certificate = ladder.build_member_certificate(sparse)
        classes = sibling.member_edge_classes(
            certificate.class_edge_counts, certificate.class_pair_floors
        )
        split = sibling.minimum_class_tree_correction(classes, certificate.collision_floor)
        single = sibling.minimum_class_tree_correction(
            (sibling.EdgeClass("ALL_PAIRS", 153, certificate.global_pair_floors),),
            certificate.collision_floor,
        )

        assert certificate.homogeneous_hunter_correction == expected[3]
        assert split.correction == certificate.class_hunter_correction == expected[4]
        assert single.correction == expected[3]
        assert split.edge_counts == ((certificate.collision_floor - 10, 0, 0), (10, 0, 0))
        assert (
            sibling.minimum_class_tree_correction(
                classes, certificate.collision_floor - 1
            ).correction
            <= split.correction
        )


def test_max_combination_and_single_subtraction() -> None:
    for sparse, expected in EXPECTED.items():
        certificate = ladder.build_member_certificate(sparse)
        summed = (
            certificate.pair_sum_correction
            + certificate.forest_correction
            + certificate.rational_correction
            + certificate.homogeneous_hunter_correction
            + certificate.class_hunter_correction
        )

        assert certificate.certified_correction == expected[4]
        assert certificate.certified_member_bound == certificate.raw_union_bound - expected[4]
        with pytest.raises(AssertionError, match="max"):
            ladder.verify_member_certificate(replace(certificate, certified_correction=summed))
        with pytest.raises(AssertionError, match="once"):
            ladder.verify_member_certificate(
                replace(
                    certificate,
                    certified_member_bound=certificate.certified_member_bound
                    - certificate.forest_correction,
                )
            )


def test_first_member_class_split_strictly_improves_the_committed_bound() -> None:
    first = ladder.first_member_class_split()

    assert first["STATUS"] == "VALID_STRICT_IMPROVEMENT"
    assert first["COMMITTED_BOUND"] == FIRST_COMMITTED_BOUND
    assert first["COMMITTED_HOMOGENEOUS_CORRECTION"] == 7_372_190
    assert first["HOMOGENEOUS_REPLAY_EQUALS_COMMITTED"] is True
    assert first["CLASS_SPLIT_BOUND"] == EXPECTED[FIRST][5]
    assert first["IMPROVEMENT"] == FIRST_COMMITTED_BOUND - EXPECTED[FIRST][5] == 417_872


def test_carried_member_is_read_by_source_identity_not_recomputed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    carried = ladder.carried_member_record()

    assert carried["CERTIFIED_MEMBER_BOUND"] == CARRIED_BOUND
    assert carried["CERTIFIED_CORRECTION"] == carried["HUNTER_CLASS_SPLIT"] == 7_790_062
    assert carried["RECOMPUTED"] is False
    assert ladder.ladder_bounds()[CARRIED] == CARRIED_BOUND
    monkeypatch.setitem(ladder.UPSTREAM_SHA256, sibling.RESULT_RELATIVE, "0" * 64)
    ladder.verify_upstream_fingerprints.cache_clear()
    try:
        with pytest.raises(AssertionError, match="fingerprint"):
            ladder.verify_upstream_fingerprints()
    finally:
        monkeypatch.undo()
        ladder.verify_upstream_fingerprints.cache_clear()
    assert ladder.verify_upstream_fingerprints() == ladder.UPSTREAM_SHA256


def test_region_maximum_covers_every_member_and_vector() -> None:
    maximum = ladder.region_maximum()
    region = ladder.r24_region()
    ladder_set = set(ladder.LADDER)
    carried = [
        (member, bound)
        for member, bound in maximum.member_bounds
        if member.sparse not in ladder_set
    ]

    assert maximum.start_state_bound == START_STATE_BOUND == region.state_term
    assert maximum.refined_state_bound == REFINED_STATE_BOUND
    assert maximum.covered_member_count == len(region.members) == 582
    assert maximum.covered_vector_count == 633
    assert all(bound == member.final_bound for member, bound in carried)
    assert len(carried) == 576
    assert maximum.refined_state_bound == max(bound for _, bound in carried)
    assert all(
        bound < REFINED_STATE_BOUND
        for member, bound in maximum.member_bounds
        if member.sparse in ladder_set
    )
    assert {
        ladder.member_id(member.sparse): member.represented_vector_count
        for member in maximum.owners
    } == NEXT_OWNERS
    result = ladder.build_result()
    assert result["R3_WITH_REFINED_STATE_TERM"] == result["R3_DURABLE_BOUND"] == R3_DURABLE_BOUND
    assert result["R3_GLOBAL_BOUND_UNCHANGED"] is True
    assert result["R3_BOUND_CLAIM"] == "NONE"


@pytest.mark.usefixtures("fresh_caches")
def test_compressed_members_are_carried_and_never_certified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maximum = ladder.region_maximum()
    region = ladder.r24_region()
    compressed = [member for member in region.members if member.represented_vector_count > 1]

    assert maximum.compressed_member_count == len(compressed) == 49
    assert maximum.compressed_vector_count == 100
    assert maximum.max_compressed_bound == REFINED_STATE_BOUND
    for member in compressed:
        with pytest.raises(hunter.CertificateScopeError):
            ladder.certified_member_bound(ladder.STATE_ID, hunter.dense_counts(member.sparse))
    tampered = tuple(
        replace(member, represented_vector_count=2) if member.sparse == SIXTH else member
        for member in region.members
    )
    monkeypatch.setattr(ladder, "r24_region", lambda: replace(region, members=tampered))
    ladder.region_maximum.cache_clear()
    with pytest.raises(AssertionError, match="compressed"):
        ladder.region_maximum()


@pytest.mark.usefixtures("fresh_caches")
def test_region_rejects_a_certificate_above_its_carried_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raised = {**ladder.ladder_bounds(), THIRD: START_STATE_BOUND}
    monkeypatch.setattr(ladder, "ladder_bounds", lambda: raised)
    with pytest.raises(AssertionError, match="only lower"):
        ladder.region_maximum()


@pytest.mark.usefixtures("fresh_caches")
def test_region_rejects_a_missing_ladder_member(monkeypatch: pytest.MonkeyPatch) -> None:
    region = ladder.r24_region()
    trimmed = tuple(member for member in region.members if member.sparse != FIFTH)
    monkeypatch.setattr(ladder, "r24_region", lambda: replace(region, members=trimmed))
    with pytest.raises(AssertionError, match="ladder differs"):
        ladder.region_maximum()


def test_carried_member_certificate_is_refused_as_a_source() -> None:
    certificate = ladder.build_member_certificate(FIRST)
    carried_raw = hunter.event_decomposition(CARRIED).raw_union_bound
    relabelled = replace(certificate, member_sparse=CARRIED, raw_union_bound=carried_raw)
    with pytest.raises(AssertionError, match="pinned ladder member"):
        ladder.verify_member_certificate(relabelled)


@pytest.mark.usefixtures("fresh_caches")
def test_region_rejects_a_dropped_non_ladder_member(monkeypatch: pytest.MonkeyPatch) -> None:
    region = ladder.r24_region()
    dropped = next(member for member in region.members if member.represented_vector_count > 1)
    trimmed = tuple(member for member in region.members if member != dropped)
    monkeypatch.setattr(ladder, "r24_region", lambda: replace(region, members=trimmed))
    with pytest.raises(AssertionError, match="cover every member"):
        ladder.region_maximum()


@pytest.mark.parametrize(
    "tamper",
    [
        "member_above_term",
        "final_above_raw",
        "repeated_member",
        "region_sha",
        "non_canonical",
        "zero_vectors",
        "missing_term",
    ],
)
def test_region_ledger_rejects_tampering(tamper: str) -> None:
    stored = _r24_record()
    assert ladder.region_ledger_from(stored) == ladder.r24_region()
    region = next(
        item
        for item in cast(list[dict[str, Any]], stored["STATE_REGION_CERTIFICATES"])
        if item["owner_id"] == ladder.STATE_ID
    )
    members = cast(list[dict[str, Any]], region["complete_region_members"])
    plain = next(member for member in members if len(member["witness_counts"]) > 2)
    if tamper == "member_above_term":
        plain["raw_bound"] = plain["final_bound"] = START_STATE_BOUND + 1
    elif tamper == "final_above_raw":
        plain["final_bound"] = plain["raw_bound"] + 1
    elif tamper == "repeated_member":
        members.append(dict(plain))
    elif tamper == "region_sha":
        region["region_sha256"] = "0" * 64
    elif tamper == "non_canonical":
        plain["witness_counts"] = list(reversed(plain["witness_counts"]))
    elif tamper == "zero_vectors":
        plain["represented_vector_count"] = 0
    elif tamper == "missing_term":
        stored["CURRENT_STATE_TERMS"] = [
            term for term in stored["CURRENT_STATE_TERMS"] if term["stable_id"] != ladder.STATE_ID
        ]
    else:
        raise AssertionError(tamper)
    with pytest.raises(AssertionError):
        ladder.region_ledger_from(stored)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("MEMBER_ID", "[0,13][5,5]"),
        ("MEMBER_COUNTS", [[0, 13], [5, 5]]),
        ("STATE_ID", "state:other"),
        ("REGION_SHA256", "0" * 64),
        ("BASE_HEAD", "0" * 40),
        ("CERTIFIED_MEMBER_BOUND", CARRIED_BOUND - 1),
        ("R3_BOUND_CLAIM", str(R3_DURABLE_BOUND - 1)),
        ("COMBINATION", "SUM"),
    ],
)
def test_carried_record_rejects_tampering(field: str, value: object) -> None:
    stored = cast(dict[str, Any], json.loads(sibling.RESULT_PATH.read_text(encoding="utf-8")))
    assert ladder.carried_record_from(stored)["CERTIFIED_MEMBER_BOUND"] == CARRIED_BOUND
    if field == "COMBINATION":
        stored["CORRECTIONS"] = {**stored["CORRECTIONS"], field: value}
    else:
        stored[field] = value
    with pytest.raises(AssertionError):
        ladder.carried_record_from(stored)


@pytest.mark.usefixtures("fresh_caches")
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("HUNTER_CORRECTION", 7_372_191, "homogeneous replay"),
        ("CERTIFIED_MEMBER_BOUND", FIRST_COMMITTED_BOUND - 1, "homogeneous replay"),
        ("MEMBER_ID", "[0,13][5,4][16,1]", "different member"),
    ],
)
def test_first_member_rejects_a_mismatched_committed_record(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    record = {**sibling.prior_member_record(), field: value}
    monkeypatch.setattr(sibling, "prior_member_record", lambda: record)
    with pytest.raises(AssertionError, match=message):
        ladder.first_member_class_split()


@pytest.mark.usefixtures("fresh_caches")
def test_build_result_rejects_packet_drift_and_an_r3_move(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ladder.PACKET_REFERENCE, "NEXT_RAW_REGION_LEVEL", REFINED_STATE_BOUND - 1)
    with pytest.raises(AssertionError, match="packet"):
        ladder.build_result()
    monkeypatch.undo()
    ladder.build_result.cache_clear()
    region = ladder.r24_region()
    monkeypatch.setattr(ladder, "r24_region", lambda: replace(region, unclassified_tail_bound=0))
    with pytest.raises(AssertionError, match="move the R3 bound"):
        ladder.build_result()


@pytest.mark.usefixtures("fresh_caches")
@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("LADDER", (*ladder.LADDER[:5], ((0, 13), (5, 1), (16, 4))), "ladder member 5"),
        ("LADDER", (((0, 12), (5, 6)), *ladder.LADDER[1:]), "ladder member 0"),
        ("FIRST_MEMBER", CARRIED, "two committed members"),
    ],
)
def test_ladder_identity_rejects_a_wrong_member(
    monkeypatch: pytest.MonkeyPatch, name: str, value: object, message: str
) -> None:
    monkeypatch.setattr(ladder, name, value)
    with pytest.raises(AssertionError, match=message):
        ladder.verify_ladder_identity()


@pytest.mark.usefixtures("fresh_caches")
def test_witness_of_another_member_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    first_tickets = ladder.witness_residual_tickets(FIRST)

    def wrong_tickets(sparse: ladder.Sparse) -> tuple[tuple[int, ...], ...]:
        del sparse
        return first_tickets

    monkeypatch.setattr(ladder, "witness_residual_tickets", wrong_tickets)
    with pytest.raises(AssertionError, match="not the member"):
        ladder.witness_analysis(SIXTH)


@pytest.mark.usefixtures("fresh_caches")
@pytest.mark.parametrize("tamper", ["correction", "collision_floor", "class_mass"])
def test_witness_rejects_an_over_claiming_certificate(
    monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    certificate = ladder.build_member_certificate(SIXTH)
    witness = ladder.witness_analysis(SIXTH)
    masses = ladder.class_masses(witness.class_nested_counts)
    if tamper == "correction":
        inflated = replace(certificate, class_hunter_correction=witness.census_objective + 1)
        message = "contradicts"
    elif tamper == "collision_floor":
        inflated = replace(certificate, collision_floor=witness.collision_mass + 1)
        message = "collision floor"
    else:
        inflated = replace(certificate, class_mass_floors=(masses[0] + 1, 0))
        message = "class-specific"

    def over_claiming(sparse: ladder.Sparse) -> ladder.LadderMemberCertificate:
        del sparse
        return inflated

    monkeypatch.setattr(ladder, "build_member_certificate", over_claiming)
    with pytest.raises(AssertionError, match=message):
        ladder.require_witness_consistency(SIXTH)


def test_legal_witnesses_are_consistent_and_cap17_stays_refuted() -> None:
    assert ladder.witness_residual_tickets(FIRST) == hunter.CAP17_WITNESS_RESIDUAL_TICKETS
    assert ladder.witness_residual_tickets(CARRIED) == sibling.witness_residual_tickets()
    for sparse in EXPECTED:
        witness = ladder.require_witness_consistency(sparse)
        certificate = ladder.build_member_certificate(sparse)

        assert witness.member_sparse == sparse
        assert witness.maximum_pair_overlap == witness.anchor_overlap == 3
        assert witness.residual_multiplicity == 18
        assert witness.exact_rows_match_table is True
        assert witness.collision_mass == witness.label_collision_mass
        assert witness.collision_mass >= certificate.collision_floor
        assert (
            witness.exact_tree_weight
            >= witness.floor_tree_weight
            >= witness.census_objective
            >= certificate.class_hunter_correction
        )
    with pytest.raises(hunter.MultiplicityCapRefuted):
        hunter.require_multiplicity_cap(17)
    assert hunter.cap17_witness_analysis().residual_multiplicity == 18


def test_result_reports_the_ladder_and_refined_state_term_only() -> None:
    first = ladder.build_result()
    second = json.loads(hunter.encode(ladder.build_result()))

    assert first == second
    assert first["LADDER_MEMBER_COUNT"] == 6
    assert first["NEW_MEMBER_CERTIFICATES"] == [
        ladder.member_id(sparse) for sparse in ladder.NEW_MEMBERS
    ]
    assert [item["RECOMPUTED"] for item in first["MEMBERS_ALREADY_CERTIFIED"]] == [False, False]
    assert {name: value["BOUND"] for name, value in first["CERTIFIED_MEMBER_BOUNDS"].items()} == {
        ladder.member_id(sparse): (CARRIED_BOUND if sparse == CARRIED else EXPECTED[sparse][5])
        for sparse in ladder.LADDER
    }
    assert first["START_STATE_BOUND"] == START_STATE_BOUND
    assert first["REFINED_STATE_BOUND"] == REFINED_STATE_BOUND
    assert first["STATE_TERM_DROP"] == START_STATE_BOUND - REFINED_STATE_BOUND
    assert first["NU_LE_17"] == "\u03bd <= 17 REFUTED"


def test_result_artifact_replays_the_shipped_entry_point() -> None:
    text = ladder.RESULT_PATH.read_text(encoding="utf-8")
    assert json.loads(text) == ladder.build_result()
    assert text == hunter.encode(ladder.build_result())


TAMPERED_FIELDS = [
    "residual_event_count",
    "raw_union_bound",
    "pair_rows_sha256",
    "global_pair_floors",
    "class_edge_counts",
    "outside_floor_raised",
    "core_floor_lowered",
    "cell_incidences",
    "collision_floor",
    "class_mass_floors",
    "class_minimizer_counts",
    "homogeneous_hunter_correction",
    "class_hunter_correction",
    "rational_correction",
    "state_id",
    "region_sha256",
    "member_sparse_carried",
    "member_sparse_swapped",
    "certified_member_bound",
]


@pytest.mark.parametrize("sparse", [FIRST, SIXTH], ids=["first", "sixth"])
@pytest.mark.parametrize("mutated", TAMPERED_FIELDS)
def test_each_tampered_certificate_fails_closed(sparse: ladder.Sparse, mutated: str) -> None:
    certificate = ladder.build_member_certificate(sparse)
    outside, core = certificate.class_pair_floors
    other = THIRD if sparse == FIRST else FIFTH
    if mutated == "residual_event_count":
        changed = replace(certificate, residual_event_count=17)
    elif mutated == "raw_union_bound":
        changed = replace(certificate, raw_union_bound=certificate.raw_union_bound + 1)
    elif mutated == "pair_rows_sha256":
        changed = replace(certificate, pair_rows_sha256="0" * 64)
    elif mutated == "global_pair_floors":
        changed = replace(certificate, global_pair_floors=outside)
    elif mutated == "class_edge_counts":
        changed = replace(certificate, class_edge_counts=(153, 0))
    elif mutated == "outside_floor_raised":
        changed = replace(
            certificate,
            class_pair_floors=((outside[0] + 1, outside[1], outside[2], outside[3]), core),
        )
    elif mutated == "core_floor_lowered":
        changed = replace(
            certificate,
            class_pair_floors=(outside, (core[0], core[1] - 1, core[2], core[3])),
        )
    elif mutated == "cell_incidences":
        # Same balanced per-cell floors, so only the incidence identity can reject it.
        changed = replace(
            certificate, cell_incidences=(5, 1, 0, 103) if sparse == SIXTH else (1, 5, 5, 98)
        )
    elif mutated == "collision_floor":
        changed = replace(certificate, collision_floor=certificate.collision_floor + 1)
    elif mutated == "class_mass_floors":
        # Weaker than the derived floors, so the census minimizer still satisfies it.
        changed = replace(
            certificate,
            class_mass_floors=(certificate.class_mass_floors[0] - 1, 0),
        )
    elif mutated == "class_minimizer_counts":
        changed = replace(
            certificate, class_minimizer_counts=((certificate.collision_floor, 0, 0), (0, 0, 0))
        )
    elif mutated == "homogeneous_hunter_correction":
        changed = replace(
            certificate,
            homogeneous_hunter_correction=certificate.homogeneous_hunter_correction + 1,
        )
    elif mutated == "class_hunter_correction":
        changed = replace(
            certificate, class_hunter_correction=certificate.class_hunter_correction + 1
        )
    elif mutated == "rational_correction":
        changed = replace(certificate, rational_correction=certificate.rational_correction + 1)
    elif mutated == "state_id":
        changed = replace(certificate, state_id="state:other")
    elif mutated == "region_sha256":
        changed = replace(certificate, region_sha256="0" * 64)
    elif mutated == "member_sparse_carried":
        changed = replace(certificate, member_sparse=CARRIED)
    elif mutated == "member_sparse_swapped":
        changed = replace(certificate, member_sparse=other)
    elif mutated == "certified_member_bound":
        changed = replace(
            certificate, certified_member_bound=certificate.certified_member_bound - 1
        )
    else:
        raise AssertionError(mutated)

    ladder.verify_member_certificate(certificate)
    with pytest.raises(AssertionError):
        ladder.verify_member_certificate(changed)
