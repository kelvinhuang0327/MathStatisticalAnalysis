"""Exact two-layer coverage, nine-event proof, compression and complete R3 replay."""

from __future__ import annotations

import copy
from dataclasses import replace
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_next_two_layers_shared_hunter_certificate_r1 as cert

prior = cert.prior
PHI = (107_800, 574_000, 1_691_620, 3_451_651)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def vectors_of(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for member in result["MEMBER_CERTIFICATES"] for row in member["vector_certificates"]
    ]


def test_exact_two_layer_coverage(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    members = prior.six.region_members()
    bounds = cert.current_member_bounds(members)
    layers = cert.target_layers(members, bounds)
    assert len(members) == result["REGION_COMPRESSED_MEMBER_COUNT"] == 1_427
    assert sum(m.represented_vector_count for m in members) == 1_543
    assert result["REGION_SHA256"] == prior.REGION_SHA256
    assert result["FIRST_LAYER_COVERAGE"] == result["SECOND_LAYER_COVERAGE"] == [11, 12]
    assert [row["prior_max"] for row in result["LAYERS"]] == [355_629_750, 355_629_302]
    for index, layer in enumerate(layers):
        assert {bounds[m.counts] for m in layer} == {result["LAYERS"][index]["prior_max"]}
        assert result["LAYERS"][index]["member_ids"] == [prior.member_id(m.counts) for m in layer]
    rows = vectors_of(result)
    assert len(result["MEMBER_CERTIFICATES"]) == 22
    assert len(rows) == len({row["vector_id"] for row in rows}) == 24
    # Independent description of the actual two layer vector families.
    expected = {
        prior.member_id(prior.dense([[i, n] for i, n in counts if n]))
        for second in (False, True)
        for a in range(6)
        for last in (17, 19)
        for counts in [
            [(0, 9), (1, a), (4, 5 - a), (5, int(second)), (16, 3 - int(second)), (last, 1)]
        ]
    }
    assert {row["vector_id"] for row in rows} == expected
    recovered = prior.catalog.r17.represented_vectors(
        tuple(prior.catalog.rebuild_member(m) for layer in layers for m in layer)
    )
    for row in result["MEMBER_CERTIFICATES"]:
        assert (
            tuple(prior.dense(v) for v in row["represented_vectors"])
            == recovered[prior.dense(row["witness_counts"])]
        )


def test_nine_event_identity_and_exact_pair_rows(result: dict[str, Any]) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert prior.type_cells(0) == (0, 0, 0, 6)
    rows = prior.exact_pair_rows(((0, 0),))
    assert len(rows) == 4 and proof["pair_rows"] == [list(row) for row in rows]
    assert tuple(proof["pair_floors"]) == PHI
    for overlap, value in enumerate(PHI):
        assert (
            prior.outcome_count(
                prior.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), (0, 0, 0, overlap)),
                (prior.ANCHOR_A, prior.ANCHOR_B),
            )
            == value
        )
        assert prior.six.residual_pair_intersection(0, 0, (0, 0, 0, overlap)) == value
    for row in vectors_of(result):
        vector = prior.dense(row["counts"])
        assert vector[0] == proof["event_count"] == 9
        assert sum(vector) == 18
        assert row["nine_event_indices"] == list(range(9))
        assert row["nine_event_types"] == [0] * 9
        assert row["outside_incidences"] == 9 * 6 == 54
        assert row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
        assert row["residual_event_sum"] == sum(
            n * prior.residual_event_size(i) for i, n in enumerate(vector) if n
        )
    assert proof["residual_event_size"] == prior.residual_event_size(0)


def test_collision_and_three_threshold_cases(result: dict[str, Any]) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert proof["outside_label_count"] == 40
    assert proof["balanced_frequencies"] == [[1, 26], [2, 14]]
    frequencies = [1] * 26 + [2] * 14
    assert sum(frequencies) == 54
    assert sum(comb(d, 2) for d in frequencies) == proof["collision_mass_floor"] == 14
    # d(d-1)/2 >= d-1: sum C(d,2) >= 54-40, attained by the balanced allocation.
    assert all(comb(d, 2) >= d - 1 for d in range(10))
    cases = cert.threshold_cases(PHI, 14, 9)
    assert cases == proof["threshold_cases"]
    assert [row["e1_lower_bound"] for row in cases] == [14, 7, 5]
    assert [row["rank_lower_bounds"] for row in cases] == [[5, 0, 0], [4, 1, 0], [3, 1, 1]]
    assert [row["hunter_floor"] for row in cases] == [3_193_400, 3_844_820, 5_138_651]
    for e1 in range(37):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 14:
                    continue
                case = cases[2 if e3 else 1 if e2 else 0]
                ranks = tuple(prior.rank_floor(e) for e in (e1, e2, e3))
                assert all(
                    r >= floor for r, floor in zip(ranks, case["rank_lower_bounds"], strict=True)
                )
                assert prior.tree_weight_floor(PHI, ranks, 9) >= case["hunter_floor"]
    with pytest.raises(ValueError):
        cert.threshold_cases(PHI, 0, 9)


def test_exact_integer_hunter_floor(result: dict[str, Any]) -> None:
    # Independent dual relaxation over ranks, rather than the source edge triples.
    feasible = [
        8 * PHI[0] + sum((PHI[k] - PHI[k - 1]) * ranks[k - 1] for k in range(1, 4))
        for r1 in range(9)
        for r2 in range(r1 + 1)
        for r3 in range(r2 + 1)
        for ranks in [(r1, r2, r3)]
        if sum(comb(r + 1, 2) for r in ranks) >= 14
    ]
    assert min(feasible) == result["HUNTER_FLOOR"] == 3_193_400
    tree = prior.minimum_tree_correction(PHI, 14, 9)
    assert tree.correction == 8 * PHI[0] + 5 * (PHI[1] - PHI[0])
    assert tree.edge_counts == (14, 0, 0) and tree.rank_floors == (5, 0, 0)
    assert (
        tree.census_size
        == result["NINE_EVENT_PROOF"]["integer_minimizer"]["feasible_threshold_triples"]
        == 9_016
    )


def test_max_single_replacement(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            parts = row["corrections"]
            assert row["combined_correction"] == max(parts.values()) == 3_193_400
            assert row["combined_correction"] != sum(parts.values())
            assert (
                row["prior_applied_correction"]
                == max(parts["R6_PAIR"], parts["FOREST"])
                == 2_870_000
            )
            assert parts["EXISTING_R14"] == parts["EXISTING_HUNTER"] == 0
            assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - max(parts.values())
            assert (
                member["member_prior_bound"]
                == row["uncorrected_anchor_bound"] - row["prior_applied_correction"]
            )
        assert member["member_certified_correction"] == min(
            row["combined_correction"] for row in member["vector_certificates"]
        )
        assert member["member_new_bound"] == max(
            row["vector_new_bound"] for row in member["vector_certificates"]
        )
    assert result["NEW_FIRST_LAYER_MAX"] == 355_306_350
    assert result["NEW_SECOND_LAYER_MAX"] == 355_305_902
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_compression_and_weakest_vector(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    members = {m.counts: m for m in prior.six.region_members()}
    for row in result["MEMBER_CERTIFICATES"]:
        member = members[prior.dense(row["witness_counts"])]
        signature = prior.eleven.compression_signature(prior.catalog.rebuild_member(member))
        for vector in row["represented_vectors"]:
            rebuilt = prior.catalog.rebuild_member(
                replace(member, counts=prior.dense(vector), represented_vector_count=1)
            )
            assert prior.eleven.compression_signature(rebuilt) == signature
    double = next(
        row for row in result["MEMBER_CERTIFICATES"] if row["represented_vector_count"] == 2
    )
    member = members[prior.dense(double["witness_counts"])]
    vectors = tuple(prior.dense(v) for v in double["represented_vectors"])
    with pytest.raises(AssertionError, match="represented vectors"):
        cert.certify_member(member, vectors[:1], member.raw_bound, cert.nine_event_proof())

    def heterogeneous(
        _member: cert.LedgerMember, vector: cert.CountVector, _bound: int, _proof: dict[str, Any]
    ) -> dict[str, Any]:
        correction = 3 if vector == vectors[0] else 7
        return {
            "combined_correction": correction,
            "uncorrected_anchor_bound": 100,
            "vector_new_bound": 100 - correction,
        }

    monkeypatch.setattr(cert, "certify_vector", heterogeneous)
    row = cert.certify_member(member, vectors, member.raw_bound, cert.nine_event_proof())
    assert row["member_certified_correction"] == 3 and row["member_new_bound"] == 97


def test_witness_soundness_and_subset_extension(result: dict[str, Any]) -> None:
    for row in vectors_of(result):
        vector = prior.dense(row["counts"])
        support = tuple(tuple(ticket) for ticket in row["support_witness"])
        assert prior.r8.validate_support_assignment(vector, support)
        assert prior.digest(support) == row["support_sha256"]
        subset = tuple(frozenset(ticket) for ticket in support[:9])
        mass = sum(
            comb(sum(label in ticket for ticket in subset), 2) for label in prior.CELL_LABELS[3]
        )
        pair_mass = sum(len(a & b) for a, b in combinations(subset, 2))
        witness = row["witness_analysis"]
        assert mass == pair_mass == witness["collision_mass"] >= 14
        assert witness["exact_tree_weight"] >= witness["phi_tree_weight"] >= result["HUNTER_FLOOR"]
        assert len(witness["subset_tree"]) == 8
        assert len(witness["extended_tree"]) == prior.graph_rank(18, witness["extended_tree"]) == 17
        full_weight = 0
        types = tuple(i for i, n in enumerate(vector) for _ in range(n))
        for a, b in witness["extended_tree"]:
            left, right = int(a), int(b)
            cells = tuple(
                len(set(support[left]) & set(support[right]) & set(labels))
                for labels in prior.CELL_LABELS
            )
            value = prior.six.residual_pair_intersection(
                types[left], types[right], (cells[0], cells[1], cells[2], cells[3])
            )
            assert value >= 0
            full_weight += value
        assert full_weight >= witness["phi_tree_weight"]


def test_preserved_remainder_and_state_maximum(result: dict[str, Any]) -> None:
    source = cert.source_authority()
    assert result["EARLIER_HUNTER_CERTIFICATES"] == source["MEMBER_CERTIFICATES"]
    earlier = prior.eleven_authority()
    assert result["EARLIER_R14_CERTIFICATES"] == earlier["MEMBER_CERTIFICATES"]
    assert result["EARLIER_SIX_R14_CERTIFICATES"] == earlier["ORIGINAL_SIX_CERTIFICATES"]
    assert [
        len(result[key])
        for key in (
            "EARLIER_HUNTER_CERTIFICATES",
            "EARLIER_R14_CERTIFICATES",
            "EARLIER_SIX_R14_CERTIFICATES",
        )
    ] == [11, 11, 6]
    old = {row["member_id"]: row for row in source["COMPLETE_REGION_MEMBERS"]}
    rows = result["COMPLETE_REGION_MEMBERS"]
    targets = {row["member_id"] for row in result["MEMBER_CERTIFICATES"]}
    assert len(rows) == len({row["member_id"] for row in rows}) == 1_427
    for row in rows:
        assert row["prior_bound"] == old[row["member_id"]]["final_bound"]
        assert row["raw_bound"] == old[row["member_id"]]["raw_bound"]
        if row["member_id"] not in targets:
            assert row["final_bound"] == row["prior_bound"]
    assert result["PRESERVED_MEMBER_COUNT"] == 1_405
    assert (
        max(row["final_bound"] for row in rows if row["member_id"] not in targets)
        == result["PRESERVED_REMAINDER_MAX"]
        == 355_595_786
    )
    assert max(row["final_bound"] for row in rows) == result["FINAL_STATE_BOUND"] == 355_595_786


def test_family_owner_transition(result: dict[str, Any]) -> None:
    before = {row["stable_id"]: row["bound"] for row in result["START_STATE_TERMS"]}
    after = {row["stable_id"]: row["bound"] for row in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert {key for key in before if before[key] != after[key]} == {prior.TARGET_STATE_ID}
    assert result["START_COMPLETE_R3_UB"] == max(before.values()) == 355_629_750
    assert (
        result["FINAL_COMPLETE_R3_UB"]
        == max(max(after.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"])
        == 355_628_469
    )
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13169800-s3-789320"]
    assert result["START_FAMILY_MAX_RECOMPUTATION"]["OWNER_IDS"] == [prior.TARGET_STATE_ID]
    assert (
        result["REMAINING_GAP"]
        == result["FINAL_COMPLETE_R3_UB"] - result["CURRENT_INCUMBENT"]
        == 42_364_581
    )
    source = cert.source_authority()
    for field in (
        "TAIL_BOUND",
        "CLASSIFIED_MAX",
        "CLASSIFIED_AGGREGATE",
        "CLASSIFIED_TERMS_SHA256",
    ):
        assert result[field] == source[field]
    family = cert.recompute_family(result["FINAL_STATE_BOUND"])
    assert family["start"] == result["START_FAMILY_MAX_RECOMPUTATION"]
    assert family["final"] == result["FINAL_FAMILY_MAX_RECOMPUTATION"]


def test_stored_result_and_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_text() == prior.encode(result)
    assert cert.verify_result(result) == {"status": "PASS", "certificates": 22, "vectors": 24}


@pytest.mark.parametrize(
    "mutation",
    [
        "pair_cost",
        "floor",
        "case",
        "mass",
        "event",
        "member",
        "duplicate",
        "vector",
        "weakest",
        "correction",
        "witness",
        "digest",
        "remainder",
        "earlier_hunter",
        "earlier_r14",
        "family",
        "owner",
        "tail",
        "aggregate",
    ],
)
def test_tampered_certificate_rejection(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    member = bad["MEMBER_CERTIFICATES"][0]
    vector = member["vector_certificates"][0]
    proof = bad["NINE_EVENT_PROOF"]
    if mutation == "pair_cost":
        proof["pair_rows"][0][6] += 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "case":
        proof["threshold_cases"][0]["rank_lower_bounds"][0] += 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "event":
        vector["nine_event_types"][0] = 1
    elif mutation == "member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "vector":
        double = next(
            row for row in bad["MEMBER_CERTIFICATES"] if row["represented_vector_count"] == 2
        )
        double["represented_vectors"].pop()
        double["vector_certificates"].pop()
    elif mutation == "weakest":
        member["member_certified_correction"] += 1
    elif mutation == "correction":
        vector["combined_correction"] = sum(vector["corrections"].values())
    elif mutation == "witness":
        vector["support_witness"][0][0] = 99
    elif mutation == "digest":
        vector["support_sha256"] = "0" * 64
    elif mutation == "remainder":
        targets = {row["member_id"] for row in bad["MEMBER_CERTIFICATES"]}
        next(row for row in bad["COMPLETE_REGION_MEMBERS"] if row["member_id"] not in targets)[
            "final_bound"
        ] -= 1
    elif mutation == "earlier_hunter":
        bad["EARLIER_HUNTER_CERTIFICATES"][0]["member_new_bound"] -= 1
    elif mutation == "earlier_r14":
        bad["EARLIER_R14_CERTIFICATES"][0]["member_new_bound"] -= 1
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [prior.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    else:
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    with pytest.raises(AssertionError, match=r"witness|replay"):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "relative",
    [
        prior.RESULT_RELATIVE,
        "src/lottolab/research/b649_k20_r3_preserved_eleven_hunter_certificate_r1.py",
    ],
)
def test_upstream_tamper_rejection(relative: str, monkeypatch: pytest.MonkeyPatch) -> None:
    read = Path.read_bytes

    def tamper(path: Path) -> bytes:
        data = read(path)
        return data + b"\n" if path.as_posix().endswith(relative) else data

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.verify_upstream_fingerprints()


def test_incomplete_layer_rejection() -> None:
    members = prior.six.region_members()
    bounds = cert.current_member_bounds(members)
    layers = cert.target_layers(members, bounds)
    bounds[layers[1][-1].counts] -= 1
    with pytest.raises(AssertionError, match="coverage"):
        cert.target_layers(members, bounds)


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver or full official outcome enumeration")


def test_no_solver_or_census_and_bound_inputs(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prior.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(prior.r14, "owner_region", forbidden)
    monkeypatch.setattr(prior.r14, "s4_child", forbidden)
    monkeypatch.setattr(prior.r8, "support_model_status", forbidden)
    monkeypatch.setattr(prior.r8, "solver_runtime_preflight", forbidden)
    cert.nine_event_proof.cache_clear()
    assert cert.build_result() == result
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
