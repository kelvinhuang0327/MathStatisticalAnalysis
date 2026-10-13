"""Independent complete-region, Hunter threshold and semantic mutation checks."""

from __future__ import annotations

import copy
import itertools
import json
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_state_13548976_three_level_shared_hunter_r1 as cert

PHI = (107_800, 574_000, 1_691_620, 3_451_651)
FINAL_OWNER = "state:s2-13169800-s3-789320"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_immutable_authority(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "33e715faaad4ed0e13873705e5a01590ee4b70ec",
        "TREE": "3eafa630733297de427f3290433cc9024ea4b7f5",
        "RESULT_SHA256": "2c62c25a8ebc324cea35cac6e5e7ac85a016b67b2c6bf136b8e81be6c06820fa",
    }
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert result["REGION_IDENTITY"] == result["REGION_SHA256"] == cert.REGION_SHA256
    assert sha256(cert.prior.RESULT_PATH.read_bytes()).hexdigest() == cert.BASE_RESULT_SHA256
    assert result["PREDECESSOR_STATE_ID"] == cert.prior.TARGET_STATE_ID
    assert cert.source_authority()["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]


def test_complete_1427_members_1543_vectors_and_compression(result: dict[str, Any]) -> None:
    members, recovered = cert.region_members(), cert.represented_vectors()
    assert len(members) == len(recovered) == len(result["COMPLETE_REGION_MEMBERS"]) == 1427
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 1543
    assert tuple(sum(m.represented_vector_count == n for m in members) for n in (1, 2, 4)) == (
        1313,
        113,
        1,
    )
    assert cert.catalog.region_fingerprint(members) == cert.REGION_SHA256
    assert recovered == cert.region.represented_vectors()
    assert result["ALL_REPRESENTED_VECTORS_SHA256"] == cert.digest(
        tuple((m.counts, recovered[m.counts]) for m in members)
    )
    for m, row in zip(members, result["COMPLETE_REGION_MEMBERS"], strict=True):
        signature = cert.hunter.eleven.compression_signature(cert.catalog.rebuild_member(m))
        vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
        assert vectors == recovered[m.counts]
        assert len(vectors) == row["represented_vector_count"] == m.represented_vector_count
        assert tuple(sorted(vectors)) == vectors and min(vectors) == m.counts
        assert cert.catalog.normalized(signature) == row["compression_signature"]
        for v in vectors:
            state = cert.catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
            assert cert.hunter.eleven.compression_signature(state) == signature
            assert cert.hunter.r14.raw_bound(state) == m.raw_bound == row["raw_bound"]
            assert sum(v) == 18 and len(v) == 30 and min(v) >= 0


def test_exact_three_cohorts_recovered_from_region(result: dict[str, Any]) -> None:
    levels = cert.target_levels(cert.region_members())
    expected_ids: list[str] = []
    for level, (bound, members) in enumerate(levels):
        assert bound == (355_505_920, 355_501_587, 355_501_139)[level]
        expected: set[tuple[int, ...]] = set()
        for j in range(5 if level == 0 else 8):
            v = [0] * 30
            v[0], v[1], v[4] = (13, j, 4 - j) if level == 0 else (9, j, 7 - j)
            if level == 0:
                v[25] = 1
            else:
                v[5 if level == 1 else 16], v[20] = 1, 1
            expected.add(tuple(v))
            expected_ids.append(cert.member_id(tuple(v)))
        assert {v for m in members for v in cert.represented_vectors()[m.counts]} == expected
        assert len(members) == (5, 8, 8)[level]
        assert all(
            m.represented_vector_count == 1 and m.final_bound == m.raw_bound for m in members
        )
    assert result["THREE_LEVEL_MEMBER_COUNT"] == result["THREE_LEVEL_VECTOR_COUNT"] == 21
    assert result["THREE_LEVEL_VECTOR_COUNTS"] == [5, 8, 8]
    assert result["THREE_LEVEL_MEMBER_IDS"] == expected_ids
    assert [r["member_id"] for r in result["MEMBER_CERTIFICATES"]] == expected_ids
    with pytest.raises(AssertionError, match="three-level"):
        cert.target_levels(tuple(m for m in cert.region_members() if m != levels[0][1][0]))


@pytest.mark.parametrize(
    "n,mass,cases,floor", [(9, 14, 9016, 3_193_400), (13, 38, 83479, 5_489_400)]
)
def test_full_exact_threshold_minimum_and_independent_pair_costs(
    result: dict[str, Any], n: int, mass: int, cases: int, floor: int
) -> None:
    proof = result["HUNTER_PROOFS"][str(n)]
    assert proof == cert.hunter_proof(n)
    assert proof["event_count"] == n and proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    assert proof["residual_event_definition"] == "R_i = E_i \\ (E_A \u222a E_B)"
    outside = set(range(49)) - (cert.hunter.ANCHOR_A | cert.hunter.ANCHOR_B)
    assert set(proof["outside_labels"]) == outside == set(cert.hunter.CELL_LABELS[3])
    assert len(outside) == proof["outside_label_count"] == 40
    assert proof["outside_incidences"] == n * 6
    assert proof["collision_mass_floor"] == mass == n * 6 - 40
    assert proof["balanced_frequencies"] == [[1, 80 - n * 6], [2, n * 6 - 40]]
    assert proof["pair_overlap_ceiling"] == 3
    for overlap, cost in enumerate(PHI):
        cells = (0, 0, 0, overlap)
        tickets = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert cert.six.residual_pair_intersection(0, 0, cells) == cost
        assert (
            cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)) == cost
        )
        assert proof["pair_rows"][overlap] == [0, 0, *cells, cost]
    for high in range(2, n + 1):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    ranks = [min(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(comb(n, 2) + 1)]
    candidates: list[tuple[int, tuple[int, int, int]]] = []
    counts = [0, 0, 0]
    for e1 in range(comb(n, 2) + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= mass:
                    value = (n - 1) * PHI[0] + sum(
                        (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                    )
                    assert value >= floor
                    candidates.append((value, (e1, e2, e3)))
                    counts[2 if e3 else int(e2 > 0)] += 1
    assert len(candidates) == proof["all_admissible_threshold_cases"] == cases
    assert counts == proof["admissible_case_counts"]
    assert min(candidates) == (floor, (mass, 0, 0))
    assert proof["integer_minimizer"] == {
        "edge_counts": [mass, 0, 0],
        "rank_floors": [ranks[mass], 0, 0],
        "feasible_threshold_triples": cases,
    }
    assert proof["hunter_floor"] == result[f"HUNTER_N{n}_FLOOR"] == floor
    assert proof["floor_method"] == "FULL_EXACT_INTEGER_MINIMIZATION"
    assert proof["rank_algebra_rows"] == comb(n, 2) + 1
    if n == 13:
        shortcut = min(
            (n - 1) * PHI[0]
            + ranks[-(-mass // k)] * (PHI[1] - PHI[0])
            + int(k >= 2) * (PHI[2] - PHI[1])
            + int(k >= 3) * (PHI[3] - PHI[2])
            for k in range(1, 4)
        )
        assert shortcut == 5_208_420 < floor
    with pytest.raises(ValueError):
        cert.hunter_proof(10)


def test_max_corrections_event_gates_and_all_new_bounds(result: dict[str, Any]) -> None:
    assert result["NEW_LEVEL_BOUNDS"] == [355_182_520, 355_178_187, 355_177_739]
    for level, band in enumerate(result["THREE_LEVELS"]):
        records = [r for r in result["MEMBER_CERTIFICATES"] if r["member_id"] in band["member_ids"]]
        n = 13 if level == 0 else 9
        floor = 5_489_400 if level == 0 else 3_193_400
        prior = 5_166_000 if level == 0 else 2_870_000
        assert len(records) == (5, 8, 8)[level]
        for member in records:
            assert member["member_raw_bound"] == member["member_prior_bound"] == band["prior_bound"]
            assert member["member_certified_correction"] == floor
            assert member["member_new_bound"] == band["new_bound"]
            row = member["vector_certificates"][0]
            vector = cert.dense(row["counts"])
            assert vector[0] == row["type0_count"] == row["event_count"] == n
            assert row["selected_event_indices"] == list(range(n))
            assert row["selected_event_types"] == [0] * n
            assert row["outside_incidences"] == n * 6
            assert row["collision_mass_floor"] == (38 if n == 13 else 14)
            assert row["residual_event_definition"] == cert.RESIDUAL_EVENT_DEFINITION
            corrections = row["corrections"]
            assert corrections["FOREST"] == row["prior_applied_correction"] == prior
            assert corrections["EXISTING_R14"] == 0
            assert corrections["EXISTING_HUNTER"] == (4_341_400 if n == 13 else 3_193_400)
            assert corrections["NEW_HUNTER"] == row["combined_correction"] == floor
            assert (
                row["combined_correction"] == max(corrections.values()) != sum(corrections.values())
            )
            assert (
                row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
            )
            assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - floor
            assert member["member_prior_bound"] - member["member_new_bound"] == 323_400
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_all_21_legal_supports_nested_forests_and_exact_tree_extensions(
    result: dict[str, Any],
) -> None:
    rows = [row for r in result["MEMBER_CERTIFICATES"] for row in r["vector_certificates"]]
    for row in rows:
        vector = cert.dense(row["counts"])
        support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(vector, support)
        assert (
            support == cert.support_witness(vector)
            and cert.digest(support) == row["support_sha256"]
        )
        tickets = tuple(frozenset(t) for t in support)
        anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
        assert len(set((*anchors, *tickets))) == 20
        assert all(len(t) == 6 and t <= set(range(49)) for t in (*anchors, *tickets))
        assert max(len(a & b) for a, b in combinations((*anchors, *tickets), 2)) == 3
        n = row["event_count"]
        subset = tickets[:n]
        witness = row["witness_analysis"]
        assert all(t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
        mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
        overlaps = {(i, j): len(subset[i] & subset[j]) for i, j in combinations(range(n), 2)}
        assert (
            mass
            == sum(overlaps.values())
            == witness["collision_mass"]
            >= row["collision_mass_floor"]
        )
        tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
        assert len(tree) == cert.hunter.graph_rank(n, tree) == n - 1
        for k in range(1, 4):
            graph = [edge for edge, v in overlaps.items() if v >= k]
            assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(n, graph)
        weight = sum(PHI[overlaps[e]] for e in tree)
        assert weight == witness["phi_tree_weight"] >= row["combined_correction"]
        full = cast(list[tuple[int, int]], witness["extended_tree"])
        assert len(full) == cert.hunter.graph_rank(18, full) == 17
        types = tuple(i for i, c in enumerate(vector) for _ in range(c))
        exact = 0
        for a, b in full:
            cells = tuple(len(tickets[a] & tickets[b] & set(c)) for c in cert.hunter.CELL_LABELS)
            cost = cert.six.residual_pair_intersection(
                types[a], types[b], cast(tuple[int, int, int, int], cells)
            )
            assert cost >= 0
            exact += cost
        assert exact == witness["extended_tree_exact_weight"] >= weight
    assert (
        cert.digest(tuple((r["counts"], r["support_witness"]) for r in rows))
        == result["RECORDED_WITNESSES_SHA256"]
    )


def test_1406_untouched_members_1522_vectors_and_14_predecessor_certificates(
    result: dict[str, Any],
) -> None:
    members = cert.region_members()
    targets = set(result["THREE_LEVEL_MEMBER_IDS"])
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert {r["member_id"] for r in rows if r["final_bound"] != r["prior_bound"]} == targets
    for m, row in zip(members, rows, strict=True):
        assert row["raw_bound"] == m.raw_bound and row["prior_bound"] == m.final_bound
        if row["member_id"] not in targets:
            assert row["final_bound"] == m.final_bound
    remainder = [r for r in rows if r["member_id"] not in targets]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 1406
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1522
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_374_810
    )
    predecessor = cert.source_authority()
    original = predecessor["MEMBER_CERTIFICATES"]
    assert len(original) == result["PREDECESSOR_MEMBER_COUNT"] == 14
    assert result["PREDECESSOR_MEMBER_CERTIFICATES"] == original
    assert cert.json_digest(original) == result["PREDECESSOR_CERTIFICATES_SHA256"]
    assert (
        result["PREDECESSOR_REGION_BOUNDS_SHA256"] == predecessor["COMPLETE_UPDATED_BOUNDS_SHA256"]
    )
    assert result["PREDECESSOR_STATE_BOUND"] == predecessor["FINAL_TARGET_STATE_UB"] == 355_379_038
    for r in original:
        for v in r["vector_certificates"]:
            assert cert.hunter.r8.validate_support_assignment(
                cert.dense(v["counts"]), tuple(tuple(t) for t in v["support_witness"])
            )
    assert (
        cert.digest(
            tuple(
                (m.counts, m.represented_vector_count, m.raw_bound, m.final_bound)
                for m in members
                if cert.member_id(m.counts) not in targets
            )
        )
        == result["PRESERVED_MEMBER_BOUNDS_SHA256"]
    )
    for path, h in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == h


def test_independent_complete_family_and_next_owner(result: dict[str, Any]) -> None:
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert result["START_STATE_TERMS"] == cert.source_authority()["FINAL_STATE_TERMS"]
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_COMPLETE_R3_UB"] == 355_505_920
    state = max(r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"])
    assert after[cert.TARGET_STATE_ID] == state == result["FINAL_TARGET_STATE_UB"] == 355_374_810
    assert after[cert.prior.TARGET_STATE_ID] == 355_379_038
    classified = cert.six.classified_terms()
    assert len(classified) == result["CLASSIFIED_TERM_COUNT"] == 56550
    terms = [*after.items(), (cert.r24.TAIL_ID, result["TAIL_BOUND"]), *classified]
    maximum = max(b for _, b in terms)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355_499_536
    assert [k for k, b in terms if b == maximum] == result["FINAL_OWNER_IDS"] == [FINAL_OWNER]
    assert result["REMAINING_GAP"] == maximum - 313_263_888 == 42_235_648
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == cert.source_authority()[key]
    assert result["CLASSIFIED_MAX"] == max(b for _, b in classified)
    assert result["TAIL_BOUND"] == 354_039_277


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 21,
        "vectors": 21,
        "region_members": 1427,
        "region_vectors": 1543,
    }
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"


def test_nested_forests_and_hunter_lemma_on_small_families() -> None:
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


@pytest.mark.parametrize("relative", sorted(cert.UPSTREAM_SHA256))
def test_all_source_tampering_rejected_with_warm_caches(
    relative: str, monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    read = Path.read_bytes

    def tamper(path: Path) -> bytes:
        data = read(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.build_result()
    assert result["TASK_STATUS"] == "SUCCESS"


def test_parsed_source_identity_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    read = Path.read_text

    def tamper(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.prior.RESULT_RELATIVE:
            payload = json.loads(text)
            payload["TASK_ID"] = "FOREIGN_CERTIFICATE"
            return json.dumps(payload)
        return text

    cert.source_authority.cache_clear()
    monkeypatch.setattr(Path, "read_text", tamper)
    try:
        with pytest.raises(AssertionError, match="predecessor identity"):
            cert.source_authority()
    finally:
        cert.source_authority.cache_clear()


@pytest.mark.parametrize("target_only", [False, True])
def test_missing_recovered_vector_mutation_rejected(
    monkeypatch: pytest.MonkeyPatch, target_only: bool
) -> None:
    original = cert.catalog.r17.represented_vectors

    def missing(members: Any) -> dict[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        recovered = original(members)
        member = (
            cert.target_levels(cert.region_members())[0][1][0]
            if target_only
            else next(m for m in cert.region_members() if m.represented_vector_count == 2)
        )
        recovered[member.counts] = recovered[member.counts][:-1]
        return recovered

    cert.represented_vectors.cache_clear()
    monkeypatch.setattr(cert.catalog.r17, "represented_vectors", missing)
    try:
        with pytest.raises(AssertionError, match="represented-vector coverage"):
            cert.represented_vectors()
    finally:
        cert.represented_vectors.cache_clear()


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, heavy refinement or full outcome enumeration")


def test_no_new_census_solver_or_heavy_route(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    monkeypatch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(cert.hunter.r14, "owner_region", forbidden)
    monkeypatch.setattr(cert.hunter.r14, "s4_child", forbidden)
    monkeypatch.setattr(cert.hunter.r8, "support_model_status", forbidden)
    monkeypatch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
    monkeypatch.setattr(cert.r24, "run_chase", forbidden)
    cert.region_members.cache_clear()
    cert.represented_vectors.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0 and result["OUTCOME_ENUMERATION_USED"] is False
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"


@pytest.mark.parametrize("level", range(3))
def test_invalid_applicability_and_incomplete_target_vector_rejected(level: int) -> None:
    member = cert.target_levels(cert.region_members())[level][1][0]
    vectors, proof = cert.represented_vectors()[member.counts], cert.hunter_proof(member.counts[0])
    for invalid in ((), (vectors[0], vectors[0])):
        with pytest.raises(AssertionError, match="represented-vector"):
            cert.certify_member(member, invalid, proof)
    wrong = list(vectors[0])
    wrong[0] -= 1
    wrong[1] += 1
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, tuple(wrong), proof)
    bad = copy.deepcopy(proof)
    bad["residual_event_definition"] = "E_i"
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, member.counts, bad)


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "pair",
        "floor",
        "rank",
        "mass",
        "case_count",
        "event",
        "signature",
        "missing_member",
        "duplicate_member",
        "missing_vector",
        "missing_vector_row",
        "max_sum",
        "witness",
        "digest",
        "remainder",
        "region_vector",
        "sealed",
        "family",
        "owner",
        "tail",
        "aggregate",
        "classified_count",
        "predecessor_region",
        "witness_ledger",
    ],
)
def test_tampered_certificate_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["HUNTER_PROOFS"]["13"]
    member = bad["MEMBER_CERTIFICATES"][0]
    row = member["vector_certificates"][0]
    if mutation == "source":
        bad["BASE_TREE"] = "0" * 40
    elif mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "rank":
        proof["integer_minimizer"]["rank_floors"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "case_count":
        proof["all_admissible_threshold_cases"] -= 1
    elif mutation == "event":
        row["selected_event_types"][0] = 1
    elif mutation == "signature":
        row["compression_signature"][0] = -1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "missing_vector":
        member["represented_vectors"].pop()
    elif mutation == "missing_vector_row":
        member["vector_certificates"].pop()
    elif mutation == "max_sum":
        row["combined_correction"] = sum(row["corrections"].values())
    elif mutation == "witness":
        row["support_witness"][0][0] = 99
    elif mutation == "digest":
        row["support_sha256"] = "0" * 64
    elif mutation == "remainder":
        next(
            r
            for r in bad["COMPLETE_REGION_MEMBERS"]
            if r["member_id"] not in bad["THREE_LEVEL_MEMBER_IDS"]
        )["final_bound"] -= 1
    elif mutation == "region_vector":
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["represented_vector_count"] == 2)[
            "represented_vectors"
        ].pop()
    elif mutation == "sealed":
        bad["PREDECESSOR_CERTIFICATES_SHA256"] = "0" * 64
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "aggregate":
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    elif mutation == "classified_count":
        bad["CLASSIFIED_TERM_COUNT"] -= 1
    elif mutation == "predecessor_region":
        bad["PREDECESSOR_REGION_BOUNDS_SHA256"] = "0" * 64
    else:
        bad["RECORDED_WITNESSES_SHA256"] = "0" * 64
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "mutation",
    [
        "max_sum",
        "pair",
        "mass",
        "rank",
        "event",
        "signature",
        "threshold_tree",
        "threshold_census",
        "weaker_thirteen_shortcut",
        "outside_universe",
        "family",
    ],
)
def test_semantic_algorithm_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    member = cert.target_levels(cert.region_members())[0][1][0]
    vector, proof = member.counts, cert.hunter_proof(member.counts[0])
    if mutation == "max_sum":

        def add(values: Mapping[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", add)
    elif mutation == "pair":
        original_pair = cert.hunter.exact_pair_rows

        def wrong_pairs(pairs: tuple[tuple[int, int], ...]) -> tuple[tuple[int, ...], ...]:
            return tuple((*r[:6], r[6] + 1) for r in original_pair(pairs))

        monkeypatch.setattr(cert.hunter, "exact_pair_rows", wrong_pairs)
    elif mutation == "mass":
        original_mass = cert.hunter.balanced_collision_mass

        def undercount(incidences: int, labels: int) -> int:
            return original_mass(incidences, labels) - 1

        monkeypatch.setattr(cert.hunter, "balanced_collision_mass", undercount)
    elif mutation == "rank":
        original_rank = cert.hunter.rank_floor

        def lower_rank(edges: int) -> int:
            return max(0, original_rank(edges) - 1)

        monkeypatch.setattr(cert.hunter, "rank_floor", lower_rank)
    elif mutation == "event":
        monkeypatch.setattr(cert.hunter, "RESIDUAL_EVENT_DEFINITION", "E_i")
    elif mutation == "signature":
        serial = itertools.count()

        def drifting_signature(_state: object) -> tuple[int]:
            return (next(serial),)

        monkeypatch.setattr(cert.hunter.eleven, "compression_signature", drifting_signature)
    elif mutation == "threshold_tree":

        def empty_tree(
            _n: int, _weights: Mapping[tuple[int, int], int]
        ) -> tuple[tuple[int, int], ...]:
            return ()

        monkeypatch.setattr(cert.hunter, "threshold_tree", empty_tree)
    elif mutation == "threshold_census":
        original_minimum = cert.hunter.minimum_tree_correction

        def missing_case(floors: Any, mass: int, vertices: int) -> Any:
            row = original_minimum(floors, mass, vertices)
            return replace(row, census_size=row.census_size - 1)

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", missing_case)
    elif mutation == "weaker_thirteen_shortcut":
        original_minimum = cert.hunter.minimum_tree_correction

        def weaker(floors: Any, mass: int, vertices: int) -> Any:
            row = original_minimum(floors, mass, vertices)
            return replace(row, correction=5_208_420) if vertices == 13 else row

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", weaker)
    elif mutation == "outside_universe":
        labels = cert.hunter.CELL_LABELS
        monkeypatch.setattr(cert.hunter, "CELL_LABELS", (*labels[:3], labels[3][:-1]))
    else:
        original_family = cert.six.tail.family_maximum

        def wrong_family(tail: int, states: Any, classified: Any) -> dict[str, Any]:
            family = original_family(tail, states, classified)
            return (
                {**family, "R3_BOUND": 1}
                if dict(states)[cert.TARGET_STATE_ID] == 355_374_810
                else family
            )

        monkeypatch.setattr(cert.six.tail, "family_maximum", wrong_family)
    if mutation == "family":
        with pytest.raises(AssertionError, match="independent full Family"):
            cert.recompute_family(355_374_810)
    else:
        with pytest.raises(AssertionError):
            cert.certify_vector(member, vector, proof)
