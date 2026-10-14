"""Independent selected-subset arithmetic, compressed coverage and semantic faults."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from functools import cache
from hashlib import sha256
from itertools import combinations, pairwise, product
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_three_state_ts_106_member_certificate_r1 as cert

EXPECTED = {
    cert.h0.joint.TARGET_STATE_ID: (1222, 1325, 33, 37, 355243049),
    cert.primary.TARGET_STATE_ID: (989, 1072, 35, 39, 355274108),
    cert.h0.s135.TARGET_STATE_ID: (1427, 1543, 38, 40, 355269698),
}


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, predecessor rebuild, solver or owner chase")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cert.h0, "build_result", forbidden)
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def test_exact_source_and_h0_preservation(result: dict[str, Any]) -> None:
    assert result["SOURCE_AUTHORITY"] == cert.verify_source_authority()
    assert result["BASE_HEAD"] == "93f7adf46a8ad08d1ec75a586f538f8814cc3cea"
    assert result["BASE_TREE"] == "026f4bf985a474223270e38c35ca8a1652edf737"
    assert sha256(cert.h0.RESULT_PATH.read_bytes()).hexdigest() == cert.BASE_RESULT_SHA256
    assert (
        cert.BASE_RESULT_SHA256
        == "993e1463a601bb6b36434c1096377e46d78ab2e00c5cc2c623a9c696e5d056ef"
    )
    h0 = cert.source_results()["H0"]
    updated = {
        r["state_id"]: {
            cert.dense(m["witness_counts"]): m["final_bound"] for m in r["complete_region_members"]
        }
        for r in result["REGIONS"]
    }
    for region in h0["REGIONS"]:
        if region["state_id"] in updated:
            for record in region["member_certificates"]:
                assert (
                    updated[region["state_id"]][cert.dense(record["witness_counts"])]
                    <= record["member_new_bound"]
                )
    assert result["H0_PRESERVATION"].startswith("PASS")


@pytest.mark.parametrize("sid", tuple(EXPECTED))
def test_complete_immutable_region_compression_and_untouched_members(
    result: dict[str, Any], sid: str
) -> None:
    region = next(r for r in result["REGIONS"] if r["state_id"] == sid)
    mc, vc, tc, tv, final = EXPECTED[sid]
    assert (
        region["region_member_count"],
        region["region_vector_count"],
        region["target_member_count"],
        region["target_vector_count"],
        region["final_state_bound"],
    ) == (mc, vc, tc, tv, final)
    originals = cert.region_rows(sid)
    targets = {m.counts for m in cert.target_members(sid)}
    records = {cert.dense(r["witness_counts"]): r for r in region["member_certificates"]}
    vectors = cert.represented_vectors(sid)
    assert set(records) == targets
    assert sum(len(vectors[v]) for v in targets) == tv
    for old, new in zip(originals, region["complete_region_members"], strict=True):
        v = cert.dense(old["witness_counts"])
        assert new["prior_bound"] == old["final_bound"]
        assert {k: new[k] for k in old if k not in ("final_bound", "prior_bound")} == {
            k: old[k] for k in old if k not in ("final_bound", "prior_bound")
        }
        assert new["final_bound"] == (
            records[v]["member_new_bound"] if v in targets else old["final_bound"]
        )
        if v in targets:
            assert new["final_bound"] < old["final_bound"]
            assert records[v]["represented_vectors"] == [cert.sparse(w) for w in vectors[v]]
    remainder = [r for r in originals if cert.dense(r["witness_counts"]) not in targets]
    assert region["preserved_member_count"] == mc - tc == len(remainder)
    assert region["preserved_vector_count"] == vc - tv
    assert region["preserved_member_bounds_sha256"] == cert.digest(
        tuple((cert.dense(r["witness_counts"]), r["final_bound"]) for r in remainder)
    )


@cache
def independent_minimum(phi: cert.Cells, q: int, n: int) -> tuple[int, tuple[int, int, int], int]:
    capacity = comb(n, 2)
    ranks = [next(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1)]
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = 0
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= q:
                    value = (
                        (n - 1) * phi[0]
                        + (phi[1] - phi[0]) * ranks[e1]
                        + (phi[2] - phi[1]) * ranks[e2]
                        + (phi[3] - phi[2]) * ranks[e3]
                    )
                    candidate = value, (e1, e2, e3)
                    best = candidate if best is None else min(best, candidate)
                    cases += 1
    assert best is not None
    return *best, cases


def test_every_pair_realization_collision_floor_and_exact_threshold_minimum(
    result: dict[str, Any],
) -> None:
    checked: set[tuple[int, int]] = set()
    for proof in result["SUBSET_PROOFS"]:
        u = cert.dense(proof["selected_subset_counts"])
        n = sum(u)
        assert proof["event_count"] == n and 2 <= n <= 18
        assert proof["proof_id"] == cert.digest(u)
        pairs = cert.six.occupied_type_pairs(u)
        rows = proof["pair_rows"]
        assert proof["occupied_type_pairs"] == [list(p) for p in sorted(pairs)]
        for pair in pairs:
            if pair in checked:
                continue
            checked.add(pair)
            left_cells, right_cells = (cert.hunter.type_cells(t) for t in pair)
            expected = {
                cells
                for cells in product(
                    *(
                        range(max(0, a + b - len(labels)), min(a, b) + 1)
                        for a, b, labels in zip(
                            left_cells, right_cells, cert.hunter.CELL_LABELS, strict=True
                        )
                    )
                )
                if sum(cells) <= 3
            }
            actual = [r for r in rows if tuple(r[:2]) == pair]
            assert {tuple(r[2:6]) for r in actual} == expected
            for row in actual:
                cells = cast(cert.Cells, tuple(row[2:6]))
                left, right = cert.hunter.realize_pair(left_cells, right_cells, cells)
                assert (
                    tuple(len(left & right & set(labels)) for labels in cert.hunter.CELL_LABELS)
                    == cells
                )
                assert (
                    cert.hunter.outcome_count(
                        (left, right), (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
                    )
                    == row[6]
                )
                assert cert.six.residual_pair_intersection(*pair, cells) == row[6] >= 0
        phi = cast(cert.Cells, tuple(min(r[6] for r in rows if sum(r[2:6]) == k) for k in range(4)))
        assert list(phi) == proof["pair_floors"]
        assert all(a <= b for a, b in pairwise(phi))
        incidences = [
            sum(c * cert.hunter.type_cells(i)[k] for i, c in enumerate(u)) for k in range(4)
        ]
        floors: list[int] = []
        for total, labels in zip(incidences, cert.hunter.CELL_LABELS, strict=True):
            a, b = divmod(total, len(labels))
            floors.append((len(labels) - b) * comb(a, 2) + b * comb(a + 1, 2))
        assert proof["cell_incidences"] == incidences
        assert proof["cell_collision_floors"] == floors
        assert proof["collision_mass_floor"] == sum(floors)
        minimum, minimizer, cases = independent_minimum(phi, sum(floors), n)
        assert proof["hunter_floor"] == minimum
        assert proof["integer_minimizer"]["edge_counts"] == list(minimizer)
        assert proof["integer_minimizer"]["rank_floors"] == [
            next(r for r in range(n) if comb(r + 1, 2) >= e) for e in minimizer
        ]
        assert (
            proof["all_admissible_threshold_cases"] == sum(proof["admissible_case_counts"]) == cases
        )
    for high in range(2, 37):
        for low in range(high - 1):
            assert (
                comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
                == high - low - 1
                > 0
            )
    for a, b in product(range(18), repeat=2):
        assert comb(a + 1, 2) + comb(b + 1, 2) <= comb(a + b + 1, 2)
    for degrees in product(range(7), repeat=3):
        q, r = divmod(sum(degrees), 3)
        assert sum(comb(d, 2) for d in degrees) >= (3 - r) * comb(q, 2) + r * comb(q + 1, 2)


def test_all_116_subsets_witnesses_full_tree_extensions_and_max_credits(
    result: dict[str, Any],
) -> None:
    proofs = {p["proof_id"]: p for p in result["SUBSET_PROOFS"]}
    total = 0
    compressed = 0
    for region in result["REGIONS"]:
        for record in region["member_certificates"]:
            vector_bounds: list[int] = []
            for row in record["vector_certificates"]:
                v, u = cert.dense(row["counts"]), cert.dense(row["selected_subset_counts"])
                assert all(0 <= a <= b and type(a) is int for a, b in zip(u, v, strict=True))
                assert 2 <= sum(u) <= 18 and sum(v) == 18
                proof = proofs[row["proof_id"]]
                assert proof["selected_subset_counts"] == row["selected_subset_counts"]
                analysis = row["witness_analysis"]
                support = cast(
                    tuple[tuple[int, ...], ...],
                    tuple(tuple(t) for t in analysis["support_witness"]),
                )
                assert cert.hunter.r8.validate_support_assignment(v, support)
                assert cert.digest(support) == analysis["support_sha256"]
                earlier = cert.sealed_vector_rows().get(v, ())
                if earlier:
                    assert analysis["support_witness"] == earlier[0]["support_witness"]
                types = tuple(i for i, c in enumerate(v) for _ in range(c))
                indices = cast(list[int], analysis["selected_event_indices"])
                assert len(indices) == len(set(indices)) == sum(u)
                assert [types[j] for j in indices] == [i for i, c in enumerate(u) for _ in range(c)]
                tickets = [set(support[j]) for j in indices]
                mass = [
                    sum(comb(sum(x in t for t in tickets), 2) for x in cell)
                    for cell in cert.hunter.CELL_LABELS
                ]
                assert mass == analysis["cell_collision_mass"]
                assert (
                    sum(mass)
                    == analysis["collision_mass"]
                    == sum(len(a & b) for a, b in combinations(tickets, 2))
                )
                assert all(
                    a >= b for a, b in zip(mass, proof["cell_collision_floors"], strict=True)
                )
                tree = cast(
                    tuple[tuple[int, int], ...], tuple(tuple(e) for e in analysis["extended_tree"])
                )
                assert len(tree) == cert.hunter.graph_rank(18, tree) == 17
                exact = 0
                for a, b in tree:
                    cells = cast(
                        cert.Cells,
                        tuple(
                            len(set(support[a]) & set(support[b]) & set(c))
                            for c in cert.hunter.CELL_LABELS
                        ),
                    )
                    cost = cert.six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
                    assert cost >= 0
                    exact += cost
                subtree = cast(tuple[tuple[int, int], ...], analysis["subset_tree"])
                phi_weight = sum(
                    proof["pair_floors"][len(tickets[a] & tickets[b])] for a, b in subtree
                )
                assert (
                    exact
                    == analysis["extended_tree_exact_weight"]
                    >= phi_weight
                    == analysis["phi_tree_weight"]
                    >= proof["hunter_floor"]
                )
                credits = row["corrections"]
                assert credits["SUBSET_HUNTER"] == proof["hunter_floor"]
                assert (
                    credits["SEALED_VALID"]
                    == row["uncorrected_anchor_bound"] - record["member_prior_bound"]
                )
                assert row["combined_correction"] == max(credits.values()) < sum(credits.values())
                assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - max(
                    credits.values()
                )
                assert (
                    row["vector_new_bound"]
                    <= row["vector_prior_bound"]
                    <= record["member_raw_bound"]
                )
                vector_bounds.append(row["vector_new_bound"])
                total += 1
            assert record["member_new_bound"] == max(vector_bounds)
            assert record["member_certified_correction"] == min(
                r["combined_correction"] for r in record["vector_certificates"]
            )
            compressed += int(len(vector_bounds) > 1)
    assert total == result["TARGET_VECTOR_COUNT"] == 116
    assert (
        sum(len(r["member_certificates"]) for r in result["REGIONS"])
        == result["TARGET_MEMBER_COUNT"]
        == 106
    )
    assert compressed > 0


def test_threshold_spanning_and_pointwise_hunter_on_synthetic_atoms() -> None:
    edges = tuple(combinations(range(3), 2))
    for weights in product(range(4), repeat=3):
        overlaps = dict(zip(edges, weights, strict=True))
        tree = cert.hunter.threshold_tree(3, overlaps)
        for k in range(1, 4):
            graph = [e for e in edges if overlaps[e] >= k]
            assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(3, graph)
        for present_mask in range(8):
            present = {i for i in range(3) if present_mask & (1 << i)}
            induced = sum(a in present and b in present for a, b in tree)
            assert int(bool(present)) <= len(present) - induced


def test_full_family_all_23_terms_owner_runner_up_and_preserved_authorities(
    result: dict[str, Any],
) -> None:
    source = cert.source_results()["H0"]
    before = {r["stable_id"]: r["bound"] for r in source["FINAL_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    for k, b in after.items():
        assert b == result["NEW_STATE_BOUNDS"].get(k, before[k])
    classified = [
        (r["stable_id"], r["bound"])
        for r in cert.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    ]
    assert (
        result["CLASSIFIED_TERMS_SHA256"]
        == source["CLASSIFIED_TERMS_SHA256"]
        == cert.digest(tuple(classified))
    )
    assert result["CLASSIFIED_TERM_COUNT"] == len(classified) == 56550
    assert result["CLASSIFIED_MAX"] == max(b for _, b in classified) == 355145504
    assert result["TAIL_BOUND"] == source["TAIL_BOUND"] == 354039277
    terms = [*after.items(), *classified, (cert.r24.TAIL_ID, result["TAIL_BOUND"])]
    maximum = max(b for _, b in terms)
    assert result["FINAL_COMPLETE_R3_UB"] == maximum == 355274920
    assert (
        result["FINAL_OWNER_IDS"]
        == sorted(k for k, b in terms if b == maximum)
        == ["state:s2-12692531-s3-681744"]
    )
    assert result["RUNNER_UP"] == max(b for _, b in terms if b < maximum) == 355274108
    assert result["START_COMPLETE_R3_UB"] == 355368426
    assert result["STRICT_GAIN"] == 355368426 - maximum == 93506
    assert result["REMAINING_GAP"] == maximum - 313263888 == 42011032


FAULTS = (
    "missing_member",
    "missing_vector",
    "subset_exceeds",
    "subset_negative",
    "subset_float",
    "subset_bool",
    "subset_too_small",
    "selected_event",
    "pair_row",
    "pair_coverage",
    "pair_floor",
    "cell_incidence",
    "cell_floor",
    "collision_floor",
    "threshold_cases",
    "threshold_minimizer",
    "threshold_rank",
    "hunter_floor",
    "extension_tree",
    "extension_weight",
    "illegal_support",
    "support_hash",
    "additive_credit",
    "lost_h0_credit",
    "compressed_max",
    "untouched_member",
    "untouched_vector",
    "missing_state",
    "preserved_state",
    "classified",
    "tail",
    "owner",
    "runner_up",
    "family_bound",
    "base_identity",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_targeted_semantic_mutations_are_rejected(result: dict[str, Any], fault: str) -> None:
    mutated = copy.deepcopy(result)
    region = mutated["REGIONS"][0]
    record = region["member_certificates"][0]
    row = record["vector_certificates"][0]
    proof = next(p for p in mutated["SUBSET_PROOFS"] if p["proof_id"] == row["proof_id"])
    analysis = row["witness_analysis"]
    if fault == "missing_member":
        region["member_certificates"].pop()
    elif fault == "missing_vector":
        record["vector_certificates"].clear()
    elif fault.startswith("subset_"):
        if fault == "subset_exceeds":
            row["selected_subset_counts"][0][1] += 1
        elif fault == "subset_negative":
            row["selected_subset_counts"][0][1] = -1
        elif fault == "subset_float":
            row["selected_subset_counts"][0][1] = float(row["selected_subset_counts"][0][1])
        elif fault == "subset_bool":
            row["selected_subset_counts"][0][1] = True
        else:
            row["selected_subset_counts"] = [[0, 1]]
    elif fault == "selected_event":
        analysis["selected_event_indices"][0] = 17
    elif fault == "pair_row":
        proof["pair_rows"][0][-1] += 1
    elif fault == "pair_coverage":
        proof["pair_rows"].pop()
    elif fault == "pair_floor":
        proof["pair_floors"][0] += 1
    elif fault == "cell_incidence":
        proof["cell_incidences"][-1] -= 1
    elif fault == "cell_floor":
        proof["cell_collision_floors"][-1] -= 1
    elif fault == "collision_floor":
        proof["collision_mass_floor"] -= 1
    elif fault == "threshold_cases":
        proof["all_admissible_threshold_cases"] -= 1
    elif fault == "threshold_minimizer":
        proof["integer_minimizer"]["edge_counts"][0] -= 1
    elif fault == "threshold_rank":
        proof["integer_minimizer"]["rank_floors"][0] -= 1
    elif fault == "hunter_floor":
        proof["hunter_floor"] += 1
    elif fault == "extension_tree":
        analysis["extended_tree"].pop()
    elif fault == "extension_weight":
        analysis["extended_tree_exact_weight"] += 1
    elif fault == "illegal_support":
        analysis["support_witness"][0] = analysis["support_witness"][1]
    elif fault == "support_hash":
        analysis["support_sha256"] = "0" * 64
    elif fault == "additive_credit":
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
        record["member_new_bound"] = row["vector_new_bound"]
    elif fault == "lost_h0_credit":
        row["corrections"]["SEALED_VALID"] = 0
    elif fault == "compressed_max":
        compressed = next(
            r for r in region["member_certificates"] if r["represented_vector_count"] > 1
        )
        compressed["member_new_bound"] -= 1
    elif fault in ("untouched_member", "untouched_vector"):
        targets = {r["member_id"] for r in region["member_certificates"]}
        remainder = next(
            r for r in region["complete_region_members"] if r["member_id"] not in targets
        )
        if fault == "untouched_member":
            remainder["final_bound"] -= 1
        else:
            remainder["represented_vectors"].pop()
    elif fault == "missing_state":
        mutated["FINAL_STATE_TERMS"].pop()
    elif fault == "preserved_state":
        next(
            r
            for r in mutated["FINAL_STATE_TERMS"]
            if r["stable_id"] == cert.h0.s141.TARGET_STATE_ID
        )["bound"] -= 1
    elif fault == "classified":
        mutated["CLASSIFIED_TERMS_SHA256"] = "0" * 64
    elif fault == "tail":
        mutated["TAIL_BOUND"] -= 1
    elif fault == "owner":
        mutated["FINAL_OWNER_IDS"] = [cert.primary.TARGET_STATE_ID]
    elif fault == "runner_up":
        mutated["RUNNER_UP"] -= 1
    elif fault == "family_bound":
        mutated["FINAL_COMPLETE_R3_UB"] -= 1
    elif fault == "base_identity":
        mutated["BASE_HEAD"] = "0" * 40
    else:
        pytest.fail("unknown mutation")
    with pytest.raises(AssertionError):
        cert.verify_result(mutated)


@pytest.mark.parametrize("field", ("BASE_TREE", "BASE_RESULT_SHA256"))
def test_immutable_identity_mutation_rejected(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    monkeypatch.setattr(cert, field, "0" * len(getattr(cert, field)))
    with pytest.raises(AssertionError, match="immutable BASE_HEAD/TREE/result SHA"):
        cert.verify_source_authority()


@pytest.mark.parametrize("kind", ("sealed_input", "predecessor_source"))
def test_warm_cache_source_tampering_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    original = Path.read_bytes
    target = cert.h0.RESULT_PATH if kind == "sealed_input" else Path(cert.h0.__file__)

    def changed(path: Path) -> bytes:
        content = original(path)
        return content + b" " if path == target else content

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(AssertionError, match="immutable executing source or sealed input changed"):
        cert.verify_result(result)


def test_live_additive_credit_mutation_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def additive(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    monkeypatch.setattr(cert.hunter, "combine_corrections", additive)
    member = cert.target_members(cert.h0.joint.TARGET_STATE_ID)[0]
    with pytest.raises(AssertionError, match="MAX single replacement"):
        cert.certify_vector(member, member.counts)


def test_exact_stored_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result)["status"] == "PASS"
    assert json.loads(cert.RESULT_PATH.read_bytes()) == result
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"


@pytest.mark.parametrize("fault", ("pair_floor", "collision_floor", "threshold_minimum"))
def test_live_mathematical_mutations_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    u = cert.dense(result["SUBSET_PROOFS"][0]["selected_subset_counts"])
    phi = cast(cert.Cells, tuple(result["SUBSET_PROOFS"][0]["pair_floors"]))
    q = int(result["SUBSET_PROOFS"][0]["collision_mass_floor"])
    cert.subset_parameters.cache_clear()
    cert.threshold_minimum.cache_clear()
    try:
        if fault == "pair_floor":
            original_pair = cert.hunter.pair_floors

            def inflated(rows: tuple[cert.PairRow, ...]) -> cert.Cells:
                values = original_pair(rows)
                return values[0] + 1, *values[1:]

            monkeypatch.setattr(cert.hunter, "pair_floors", inflated)
            with pytest.raises(AssertionError, match="exact residual pair floor"):
                cert.subset_parameters(u)
        elif fault == "collision_floor":
            original_collision = cert.hunter.cell_collision_floors

            def weakened(incidences: cert.Cells) -> cert.Cells:
                values = original_collision(incidences)
                return *values[:3], values[3] - 1

            monkeypatch.setattr(cert.hunter, "cell_collision_floors", weakened)
            with pytest.raises(AssertionError, match="balanced cell collision"):
                cert.subset_parameters(u)
        else:
            original_rank = cert.rank_minimum

            def excessive(floors: cert.Cells, mass: int, n: int) -> int:
                return original_rank(floors, mass, n) + 1

            monkeypatch.setattr(cert, "rank_minimum", excessive)
            with pytest.raises(AssertionError, match="complete exact Hunter threshold minimum"):
                cert.threshold_minimum(phi, q, sum(u))
    finally:
        cert.subset_parameters.cache_clear()
        cert.threshold_minimum.cache_clear()
