"""Independent six-member proof, three-component preservation and fault rejection."""

from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace
from hashlib import sha256
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_three_component_joint_certificate_r1 as cert

PHI = (107800, 574000, 1691620, 3451651)


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, search or outcome enumeration")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    # Protect the complete cold replay, including both imported components.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def test_three_immutable_identities_and_byte_exact_components(result: dict[str, Any]) -> None:
    identity = cert.verify_source_authority()
    assert identity == result["SOURCE_AUTHORITY"]
    assert set(identity["identities"]) == {
        "5cfacd03b1026274577f6647083684b53b00bcae",
        "f3a90b9367e40942022c05c6cf918ad758bd1bc9",
        "28751d6cbb3088907a0595ff093f04e4cf4f9c29",
    }
    assert len(identity["component_files"]) == 6
    for path, (head, blob, expected_sha) in cert.SOURCE_FILES.items():
        immutable = subprocess.check_output(
            ["git", "-C", str(cert.REPO_ROOT), "show", f"{head}:{path}"]
        )
        assert (cert.REPO_ROOT / path).read_bytes() == immutable
        assert sha256(immutable).hexdigest() == expected_sha
        assert identity["component_files"][path]["BLOB"] == blob
    p, d, _ = cert.source_components()
    assert cert.primary.RESULT_PATH.read_bytes() == cert.primary.encode(p).encode()
    assert cert.donor.RESULT_PATH.read_bytes() == cert.donor.encode(d).encode()
    assert p["TARGET_MEMBER_COUNT"] == p["TARGET_VECTOR_COUNT"] == 47
    assert p["FINAL_TARGET_STATE_UB"] == result["FORTY_SEVEN_MEMBER_STATE_UB"] == 355368426
    assert p["TEN_EVENT_FLOOR"] == 3767400 and p["TWELVE_EVENT_FLOOR"] == 4915400
    assert result["FORTY_SEVEN_MEMBER_BOUNDS_SHA256"] == p["COMPLETE_UPDATED_BOUNDS_SHA256"]
    assert result["FORTY_SEVEN_MEMBER_CERTIFICATES_SHA256"] == cert.primary.json_digest(
        p["MEMBER_CERTIFICATES"]
    )
    assert result["CLASSIFIED_LEVEL_CERTIFICATES"] == d["LEVEL_CERTIFICATES"]
    assert result["COMPLETE_CLASSIFIED_AGGREGATE_LEVELS"] == d["COMPLETE_AGGREGATE_LEVELS"]
    assert [r["level_new_bound"] for r in d["LEVEL_CERTIFICATES"]] == [
        355145504,
        355145056,
        355144608,
        355144160,
        355143712,
    ]
    assert d["AGGREGATE_LEVEL_COUNT"] == 29 and d["AGGREGATE_VECTOR_COUNT"] == 183
    assert d["TARGET_VECTOR_COUNT"] == 15
    assert result["PRESERVED_CLASSIFIED_AGGREGATE_LEVEL_COUNT"] == 24
    assert result["PRESERVED_CLASSIFIED_AGGREGATE_VECTOR_COUNT"] == 168


def test_six_exact_members_and_complete_untouched_region(result: dict[str, Any]) -> None:
    members, vectors = cert.region_members(), cert.represented_vectors()
    targets = cert.target_members(members)
    expected: set[tuple[int, ...]] = set()
    for j in range(6):
        v = [0] * 30
        v[0], v[1], v[4], v[20] = 12, j, 5 - j, 1
        expected.add(tuple(v))
    assert {m.counts for m in targets} == expected
    assert len(members) == len(vectors) == len(result["COMPLETE_REGION_MEMBERS"]) == 1222
    flat = [v for group in vectors.values() for v in group]
    assert len(flat) == len(set(flat)) == result["REGION_VECTOR_COUNT"] == 1325
    assert result["PRESERVED_MEMBER_COUNT"] == 1216 and result["PRESERVED_VECTOR_COUNT"] == 1319
    previous = {
        cert.dense(r["witness_counts"]): r
        for r in cert.source_components()[2]["COMPLETE_REGION_MEMBERS"]
    }
    for m, row in zip(members, result["COMPLETE_REGION_MEMBERS"], strict=True):
        assert cert.dense(row["witness_counts"]) == m.counts
        assert tuple(cert.dense(v) for v in row["represented_vectors"]) == vectors[m.counts]
        assert row["raw_bound"] == previous[m.counts]["raw_bound"]
        if m.counts not in expected:
            assert row["final_bound"] == m.final_bound == previous[m.counts]["final_bound"]
    for m in targets:
        assert vectors[m.counts] == (m.counts,) and m.represented_vector_count == 1
        with pytest.raises(AssertionError, match="six-member coverage"):
            cert.target_members(tuple(row for row in members if row != m))
    with pytest.raises(AssertionError, match="six-member coverage"):
        cert.target_members((*members, targets[0]))


def test_complete_threshold_minimization_independent_of_component_proofs(
    result: dict[str, Any],
) -> None:
    proof = result["TWELVE_EVENT_PROOF"]
    assert proof == cert.twelve_event_proof()
    assert proof["pair_rows"] == [[0, 0, 0, 0, 0, k, value] for k, value in enumerate(PHI)]
    outside = set(range(49)) - (cert.hunter.ANCHOR_A | cert.hunter.ANCHOR_B)
    assert set(proof["outside_labels"]) == outside and len(outside) == 40
    assert proof["outside_incidences"] == 72
    assert proof["balanced_frequencies"] == [[1, 8], [2, 32]]
    assert proof["collision_mass_floor"] == 32
    for high in range(2, 13):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    ranks = [min(r for r in range(12) if comb(r + 1, 2) >= edges) for edges in range(67)]
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = [0, 0, 0]
    for e1 in range(67):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 32:
                    continue
                value = 11 * PHI[0] + sum(
                    (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                )
                assert value >= 4915400
                candidate = value, (e1, e2, e3)
                best = candidate if best is None else min(best, candidate)
                cases[2 if e3 else int(e2 > 0)] += 1
    assert best == (4915400, (32, 0, 0))
    assert sum(cases) == proof["all_admissible_threshold_cases"] == 51257
    assert cases == proof["admissible_case_counts"]
    assert proof["integer_minimizer"]["rank_floors"] == [8, 0, 0]
    for k, cost in enumerate(PHI):
        cells = (0, 0, 0, k)
        tickets = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert cert.six.residual_pair_intersection(0, 0, cells) == cost
        assert (
            cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)) == cost
        )


def test_universal_nested_threshold_tree_and_hunter_atom_inequality() -> None:
    # All 4^6 weighted K4 graphs test the universal Kruskal/rank argument.
    edges = tuple(combinations(range(4), 2))
    for values in product(range(4), repeat=len(edges)):
        overlaps = dict(zip(edges, values, strict=True))
        tree = cert.hunter.threshold_tree(4, overlaps)
        assert len(tree) == cert.hunter.graph_rank(4, tree) == 3
        for k in range(1, 4):
            graph = [e for e in edges if overlaps[e] >= k]
            rank = cert.hunter.graph_rank(4, graph)
            assert len(graph) <= comb(rank + 1, 2)
            assert sum(overlaps[e] >= k for e in tree) == rank
        for atom in range(16):
            active = {v for v in range(4) if atom & (1 << v)}
            induced = sum(a in active and b in active for a, b in tree)
            assert int(bool(active)) <= len(active) - induced
    # Convex component-rank bound used for arbitrary n, not just K4.
    for a in range(12):
        for b in range(12 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) <= comb(a + b + 1, 2)


def test_all_six_current_credits_max_once_and_legal_tree_extensions(result: dict[str, Any]) -> None:
    assert result["SIX_MEMBER_BOUNDS"] == [355173959] * 6
    assert result["SIX_MEMBER_CURRENT_FOREST_CORRECTIONS"] == [4592000] * 6
    for record in result["MEMBER_CERTIFICATES"]:
        row = record["vector_certificates"][0]
        vector = cert.dense(row["counts"])
        assert row["uncorrected_anchor_bound"] == 360089359
        assert row["prior_applied_correction"] == 4592000
        assert record["member_prior_bound"] == record["member_raw_bound"] == 355497359
        assert row["selected_event_types"] == [0] * 12
        assert row["selected_event_indices"] == list(range(12))
        corrections = row["corrections"]
        assert corrections["EXISTING_HUNTER"] == 0
        assert corrections["EXISTING_R14"] == 0
        assert row["existing_credit_coverage"] == {
            "sealed_r14_matches": 0,
            "sealed_hunter_matches": 0,
            "carried_catalog_size": 335,
            "prior_equals_raw": True,
        }
        assert corrections["FOREST"] == corrections["CARRIED_VALID"] == 4592000
        assert row["combined_correction"] == max(corrections.values()) == 4915400
        assert row["combined_correction"] != sum(corrections.values())
        assert row["vector_new_bound"] == 360089359 - max(corrections.values())
        support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(vector, support)
        assert cert.digest(support) == row["support_sha256"]
        tickets = tuple(frozenset(t) for t in support)
        selected = tickets[:12]
        overlaps = {(a, b): len(selected[a] & selected[b]) for a, b in combinations(range(12), 2)}
        witness = row["witness_analysis"]
        mass = sum(comb(sum(x in t for t in selected), 2) for x in cert.hunter.CELL_LABELS[3])
        assert mass == sum(overlaps.values()) == witness["collision_mass"] >= 32
        tree = tuple((int(e[0]), int(e[1])) for e in witness["subset_tree"])
        assert len(tree) == cert.hunter.graph_rank(12, tree) == 11
        for k in range(1, 4):
            graph = [e for e, v in overlaps.items() if v >= k]
            assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(12, graph)
        assert sum(PHI[overlaps[e]] for e in tree) == witness["phi_tree_weight"] >= 4915400
        full = tuple((int(e[0]), int(e[1])) for e in witness["extended_tree"])
        assert len(full) == cert.hunter.graph_rank(18, full) == 17
        types = tuple(i for i, count in enumerate(vector) for _ in range(count))
        weight = 0
        for a, b in full:
            cells = tuple(len(tickets[a] & tickets[b] & set(c)) for c in cert.hunter.CELL_LABELS)
            assert len(cells) == 4
            cost = cert.six.residual_pair_intersection(
                types[a], types[b], (cells[0], cells[1], cells[2], cells[3])
            )
            assert cost >= 0
            weight += cost
        assert weight == witness["extended_tree_exact_weight"] >= witness["phi_tree_weight"]


def test_full_family_independently_recomputed(result: dict[str, Any]) -> None:
    states = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    classified = {r["stable_id"]: r["bound"] for r in result["FINAL_CLASSIFIED_TERMS"]}
    assert len(states) == result["STATE_TERM_COUNT"] == 23
    assert len(classified) == result["CLASSIFIED_TERM_COUNT"] == 56550
    assert states[cert.TARGET_STATE_ID] == result["SIX_MEMBER_STATE_UB"] == 355406030
    assert states[cert.primary.TARGET_STATE_ID] == 355368426
    assert states["state:s2-14122976-s3-1005536"] == 355379038
    assert states["state:s2-13548976-s3-951748"] == 355374810
    assert max(classified.values()) == result["FINAL_CLASSIFIED_MAX"] == 355145504
    assert result["TAIL_BOUND"] == cert.six.sealed_tail_bound() == 354039277
    explicit = tuple((k, b) for k, b in cert.six.classified_terms() if k != cert.r24.AGGREGATE_ID)
    assert len(explicit) == result["PRESERVED_CLASSIFIED_EXPLICIT_TERM_COUNT"] == 56549
    assert all(classified[k] == b for k, b in explicit)
    terms = {**states, **classified, cert.r24.TAIL_ID: result["TAIL_BOUND"]}
    ub = max(terms.values())
    assert ub == result["FINAL_COMPLETE_R3_UB"] == 355406030
    assert (
        sorted(k for k, b in terms.items() if b == ub)
        == result["FINAL_OWNER_IDS"]
        == [cert.TARGET_STATE_ID]
    )
    assert result["START_COMPLETE_R3_UB"] == 355497359
    assert result["CANONICAL_INCUMBENT"] == 313263888
    assert result["REMAINING_GAP"] == ub - 313263888 == 42142142
    assert result["STRICT_GAIN"] == 355497359 - ub == 91329
    assert result["DUPLICATE_CORRECTIONS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"


@pytest.mark.parametrize(
    "mutation",
    [
        "six_missing",
        "six_duplicate",
        "vector_missing",
        "wrong_forest",
        "additive_credit",
        "wrong_floor",
        "threshold_case_missing",
        "wrong_pair",
        "wrong_collision",
        "wrong_state",
        "state_missing",
        "classified_missing",
        "primary_bound",
        "donor_bound",
        "tail",
        "owner",
        "witness",
        "gap",
        "gain",
        "authority",
    ],
)
def test_tampered_joint_certificate_rejected(result: dict[str, Any], mutation: str) -> None:
    changed = copy.deepcopy(result)
    row = changed["MEMBER_CERTIFICATES"][0]["vector_certificates"][0]
    if mutation == "six_missing":
        changed["MEMBER_CERTIFICATES"].pop()
    elif mutation == "six_duplicate":
        changed["MEMBER_CERTIFICATES"].append(changed["MEMBER_CERTIFICATES"][0])
    elif mutation == "vector_missing":
        changed["MEMBER_CERTIFICATES"][0]["vector_certificates"].clear()
    elif mutation == "wrong_forest":
        row["corrections"]["FOREST"] = 5166000
    elif mutation == "additive_credit":
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "wrong_floor":
        changed["TWELVE_EVENT_PROOF"]["hunter_floor"] += 1
    elif mutation == "threshold_case_missing":
        changed["TWELVE_EVENT_PROOF"]["all_admissible_threshold_cases"] -= 1
    elif mutation == "wrong_pair":
        changed["TWELVE_EVENT_PROOF"]["pair_floors"][0] += 1
    elif mutation == "wrong_collision":
        changed["TWELVE_EVENT_PROOF"]["collision_mass_floor"] -= 1
    elif mutation == "wrong_state":
        changed["FINAL_STATE_TERMS"][0]["bound"] -= 1
    elif mutation == "state_missing":
        changed["FINAL_STATE_TERMS"].pop()
    elif mutation == "classified_missing":
        changed["FINAL_CLASSIFIED_TERMS"].pop()
    elif mutation == "primary_bound":
        changed["FORTY_SEVEN_MEMBER_STATE_UB"] -= 1
    elif mutation == "donor_bound":
        changed["CLASSIFIED_LEVEL_CERTIFICATES"][0]["level_new_bound"] -= 1
    elif mutation == "tail":
        changed["TAIL_BOUND"] -= 1
    elif mutation == "owner":
        changed["FINAL_OWNER_IDS"] = []
    elif mutation == "witness":
        row["support_witness"][0][0] = 100
    elif mutation == "gap":
        changed["REMAINING_GAP"] -= 1
    elif mutation == "gain":
        changed["STRICT_GAIN"] += 1
    else:
        changed["SOURCE_AUTHORITY"]["identities"][cert.DONOR_HEAD]["TREE"] = "0" * 40
    with pytest.raises(AssertionError):
        cert.verify_result(changed)


@pytest.mark.parametrize(
    "path", [p for p, v in cert.SOURCE_FILES.items() if v[0] == cert.DONOR_HEAD]
)
def test_donor_byte_tampering_rejected_with_warm_caches(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    original = Path.read_bytes

    def tampered(target: Path) -> bytes:
        data = original(target)
        return data + b" " if target == cert.REPO_ROOT / path else data

    monkeypatch.setattr(Path, "read_bytes", tampered)
    with pytest.raises(AssertionError, match="byte identity"):
        cert.build_result()
    monkeypatch.undo()
    assert cert.verify_result(result)["status"] == "PASS"


def test_invalid_immutable_authority_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    tree, path, result_sha = cert.SOURCE_IDENTITIES[cert.DONOR_HEAD]
    monkeypatch.setitem(
        cert.SOURCE_IDENTITIES, cert.DONOR_HEAD, ("0" * len(tree), path, result_sha)
    )
    with pytest.raises(AssertionError, match="authority"):
        cert.build_result()
    monkeypatch.undo()
    assert cert.verify_result(result)["status"] == "PASS"


@pytest.mark.parametrize(
    "mutation",
    [
        "additive",
        "forest",
        "pair",
        "mass",
        "rank",
        "event",
        "threshold_count",
        "inflated_floor",
        "missing_vector",
        "missing_state",
        "missing_classified",
        "family",
    ],
)
def test_semantic_implementation_mutations_killed(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    member = cert.target_members(cert.region_members())[0]
    proof = copy.deepcopy(result["TWELVE_EVENT_PROOF"])
    if mutation == "additive":

        def add(values: dict[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", add)
    elif mutation == "forest":
        rebuild = cert.catalog.rebuild_member

        def wrong_forest(m: cert.LedgerMember) -> Any:
            state = rebuild(m)
            return replace(state, complementary_forest_floor=5166000)

        monkeypatch.setattr(cert.catalog, "rebuild_member", wrong_forest)
    elif mutation == "pair":
        pair = cert.six.residual_pair_intersection

        def wrong_pair(a: int, b: int, cells: tuple[int, int, int, int]) -> int:
            return pair(a, b, cells) + 1

        monkeypatch.setattr(cert.six, "residual_pair_intersection", wrong_pair)
    elif mutation == "mass":
        mass = cert.hunter.balanced_collision_mass

        def wrong_mass(incidences: int, labels: int) -> int:
            return mass(incidences, labels) - 1

        monkeypatch.setattr(cert.hunter, "balanced_collision_mass", wrong_mass)
    elif mutation == "rank":
        rank = cert.hunter.rank_floor

        def wrong_rank(edges: int) -> int:
            return max(0, rank(edges) - 1)

        monkeypatch.setattr(cert.hunter, "rank_floor", wrong_rank)
    elif mutation == "event":
        monkeypatch.setattr(cert.hunter, "RESIDUAL_EVENT_DEFINITION", "E_i")
    elif mutation in ("threshold_count", "inflated_floor"):
        minimum = cert.hunter.minimum_tree_correction

        def wrong_minimum(floors: Any, mass: int, n: int) -> Any:
            row = minimum(floors, mass, n)
            return (
                replace(row, census_size=row.census_size - 1)
                if mutation == "threshold_count"
                else replace(row, correction=row.correction + 1)
            )

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", wrong_minimum)
    elif mutation == "missing_vector":
        represented = cert.catalog.r17.represented_vectors

        def missing_vector(states: Any) -> Any:
            recovered = dict(represented(states))
            recovered[member.counts] = ()
            return recovered

        monkeypatch.setattr(cert.catalog.r17, "represented_vectors", missing_vector)
    elif mutation == "missing_state":
        components = copy.deepcopy(cert.source_components())
        components[0]["FINAL_STATE_TERMS"].pop()
        monkeypatch.setattr(cert, "source_components", lambda: components)
    elif mutation == "missing_classified":
        terms = cert.six.classified_terms()
        monkeypatch.setattr(cert.six, "classified_terms", lambda: terms[:-1])
    else:
        maximum = cert.six.tail.family_maximum

        def wrong_family(tail: int, states: Any, classified: Any) -> dict[str, Any]:
            family = maximum(tail, states, classified)
            return (
                {**family, "R3_BOUND": 1}
                if dict(states)[cert.TARGET_STATE_ID] == 355406030
                else family
            )

        monkeypatch.setattr(cert.six.tail, "family_maximum", wrong_family)
    cert.twelve_event_proof.cache_clear()
    try:
        with pytest.raises(AssertionError):
            if mutation == "missing_vector":
                cert.represented_vectors.cache_clear()
                cert.represented_vectors()
            elif mutation in ("missing_state", "missing_classified", "family"):
                cert.recompute_family(355406030)
            else:
                cert.certify_member(member, (member.counts,), proof)
    finally:
        monkeypatch.undo()
        cert.twelve_event_proof.cache_clear()
        cert.represented_vectors.cache_clear()
    assert cert.verify_result(result)["status"] == "PASS"


def test_missing_and_invalid_member_vectors_rejected(result: dict[str, Any]) -> None:
    member = cert.target_members(cert.region_members())[0]
    for vectors in [(), (member.counts, member.counts), (tuple([0] * 30),)]:
        with pytest.raises(AssertionError, match="applicability"):
            cert.certify_member(member, vectors, result["TWELVE_EVENT_PROOF"])
    bad = copy.deepcopy(result["TWELVE_EVENT_PROOF"])
    bad["event_count"] = 11
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_member(member, (member.counts,), bad)


def test_exact_result_verifier_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result)["status"] == "PASS"
    stored = cert.RESULT_PATH.read_bytes()
    assert json.loads(stored) == result
    assert stored == cert.encode(cert.build_result()).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
