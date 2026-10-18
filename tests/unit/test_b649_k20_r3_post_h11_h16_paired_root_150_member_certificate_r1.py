"""Independent arithmetic, full ledger preservation and adversarial root controls."""

from __future__ import annotations

import copy
import inspect
import runpy
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from itertools import product
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_post_h11_h16_paired_root_150_member_certificate_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor readoption/rebuild, region census, or heavy solver")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    from lottolab.research import b649_k20_r3_state_14696976_universal_hunter_certificate_r1 as s146

    with pytest.MonkeyPatch.context() as patch:
        for module, names in (
            (cert.prior, ("build_result", "core_proof", "pair_proof", "update_region")),
            (cert.h13, ("build_result", "h13_proof")),
            (s146, ("build_result", "core_proof", "certificate_rows", "root_pair_proof")),
            (cert.root65, ("build_result", "core_proof", "root_pair_proof")),
            (cert.root65.r12, ("build_result", "core_proof")),
            (cert.root65.ts153, ("build_result", "subset_proof")),
            (cert.hunter.r7, ("joint_residual_census", "_joint_residual_states")),
            (cert.hunter.r14, ("owner_region", "s4_child", "run_chase")),
            (cert.hunter.r6, ("iter_type_count_vectors", "candidate_type_count_vectors")),
            (cert.hunter.r8, ("support_model_status", "solver_runtime_preflight")),
        ):
            for name in names:
                if hasattr(module, name):
                    patch.setattr(module, name, forbidden)
        return cert.build_result()


def test_fixed_authority_full_closure_and_predecessor_bytes(result: dict[str, Any]) -> None:
    a = cert.verify_source_authority()
    assert a == result["SOURCE_AUTHORITY"]
    assert (a["HEAD"], a["TREE"], a["RESULT_SHA256"]) == (
        "75e30e7b87cce7384ec1ba591061ae53b2e4c8a7",
        "26479c39a0f23be7dc9e19282e68de4c013e7ced",
        "1f9ae1717c6770bb3d5fe5f1fb23cdcbecd82b31c4c6194d0fd4e3adc7697a1d",
    )
    for path, expected in {**a["upstream_sha256"], **a["implementation_sha256"]}.items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == expected
    for path in (
        cert.BASE_RESULT,
        cert.prior.SOURCE_RELATIVE,
        cert.h13.RESULT_RELATIVE,
        cert.root65.RESULT_RELATIVE,
        cert.root65.r12.RESULT_RELATIVE,
        cert.root65.ts153.RESULT_RELATIVE,
        cert.h13.BASE_RESULT,
    ):
        assert path in a["upstream_sha256"]
    base = cert.sealed(cert.BASE_RESULT)
    old = [r for region in base["REGIONS"] for r in region["member_certificates"]]
    p = result["PREDECESSOR_PRESERVATION"]
    assert len(old) == 14 and p["carried_14_certificates_sha256"] == cert.digest(old)
    assert p["carried_core_proofs_sha256"] == cert.digest(base["CORE_PROOFS"])
    assert p["H16_credit"] == 7211400 and p["readoption_count"] == p["rebuild_count"] == 0


def independent_cohorts() -> dict[str, set[cert.CountVector]]:
    def v(**counts: int) -> cert.CountVector:
        return tuple(counts.get(f"n{i}", 0) for i in range(30))

    groups: dict[str, set[cert.CountVector]] = {
        k: set() for k in ("A1", "A2", "A3", "B1", "B2", "B3")
    }
    for j, c in product(range(5), (5, 16)):
        groups["A1"].add(v(n0=12, n1=j, n4=4 - j, n20=1, **{f"n{c}": 1}))
    for name, last in (("A2", (6, 9)), ("A3", (17, 19)), ("B1", (2, 8))):
        for j, k, t in product(range(4), range(5), last):
            groups[name].add(v(n0=10, n1=j, n4=3 - j, n5=k, n16=4 - k, **{f"n{t}": 1}))
    for j, a, b in product(range(6), (6, 9), (17, 19)):
        groups["B2"].add(v(n0=11, n1=j, n4=5 - j, **{f"n{a}": 1, f"n{b}": 1}))
    for j, k, t in product(range(2), range(4), (17, 19)):
        groups["B3"].add(v(n0=13, n1=j, n4=1 - j, n5=k, n16=3 - k, **{f"n{t}": 1}))
    return groups


def test_full_regions_six_families_and_independent_twenty_aliases(result: dict[str, Any]) -> None:
    groups = independent_cohorts()
    assert {k: set(vs) for k, vs in cert.cohorts().items()} == groups
    seen: dict[str, int] = {}
    for region, expected in zip(
        result["REGIONS"], ((1427, 1543, 80, 90), (1222, 1325, 70, 80)), strict=True
    ):
        state = region["state_id"]
        rows, targets = region["complete_region_members"], region["member_certificates"]
        vr = [v for r in rows for v in r["represented_vector_bounds"]]
        target_vectors = [
            cert.dense(v["counts"]) for r in targets for v in r["vector_certificates"]
        ]
        assert (len(rows), len(vr), len(targets), len(target_vectors)) == expected
        assert len({r["member_id"] for r in rows}) == expected[0]
        assert len({cert.dense(v["counts"]) for v in vr}) == expected[1]
        expected_vs = {v for k, vs in groups.items() if k[0] == targets[0]["cohort"][0] for v in vs}
        assert set(target_vectors) == expected_vs
        assert (
            cert.catalog.digest(
                tuple((cert.dense(r["witness_counts"]), r["raw_bound"]) for r in rows)
            )
            == cert.REGION_HASHES[state]
        )
        for record in targets:
            name = record["cohort"]
            seen[name] = seen.get(name, 0) + 1
            vs = tuple(cert.dense(v) for v in record["represented_vectors"])
            canonical = cert.dense(record["counts"])
            assert canonical == min(vs) and cert.member_id(canonical) == record["member_id"]
            assert set(vs).issubset(groups[name]) and vs == cert.region_vectors(state)[canonical]
            assert vs == tuple(cert.dense(v["counts"]) for v in record["vector_certificates"])
    assert seen == {"A1": 10, "A2": 35, "A3": 35, "B1": 40, "B2": 18, "B3": 12}
    # Derive equal-signature classes independently, without the alias helper.
    counts: dict[str, int] = {}
    for name, vs in groups.items():
        state = cert.STATE_A if name[0] == "A" else cert.STATE_B
        lookup = {v: k for k, vectors in cert.region_vectors(state).items() for v in vectors}
        pairs = {tuple(sorted(w for w in vs if lookup[w] == lookup[v])) for v in vs}
        duplicates = [pair for pair in pairs if len(pair) > 1]
        counts[name] = len(duplicates)
        for a, b in duplicates:
            if name in ("A2", "A3"):
                assert a[5] == b[5] and sorted((a[1], b[1])) == [1, 2]
                assert {
                    next(i for i in ((6, 9) if name == "A2" else (17, 19)) if v[i]) for v in (a, b)
                } == ({6, 9} if name == "A2" else {17, 19})
            elif name == "B2":
                assert a[1] == b[1] and {(v[6], v[9], v[17], v[19]) for v in (a, b)} == {
                    (0, 1, 1, 0),
                    (1, 0, 0, 1),
                }
            else:
                assert name == "B3" and a[5] == b[5]
                assert {(v[1], v[17], v[19]) for v in (a, b)} == {(0, 1, 0), (1, 0, 1)}
        reported = result["COMPRESSED_ALIASES"].get(name, [])
        assert {tuple(sorted(cert.dense(v) for v in p["vectors"])) for p in reported} == set(
            duplicates
        )
    assert counts == {"A1": 0, "A2": 5, "A3": 5, "B1": 0, "B2": 6, "B3": 4}
    assert sum(counts.values()) == result["COMPRESSED_ALIAS_COVERAGE"] == 20


@pytest.mark.parametrize(
    "n,q,rank,h",
    [(10, 20, 6, 3767400), (11, 26, 7, 4341400), (12, 32, 8, 4915400), (13, 38, 9, 5489400)],
)
def test_independent_complete_integer_core_minimum(
    result: dict[str, Any], n: int, q: int, rank: int, h: int
) -> None:
    proof = result["CORE_PROOFS"][f"H{n}"]
    low, remainder = divmod(6 * n, 40)
    assert (
        (40 - remainder) * comb(low, 2) + remainder * comb(low + 1, 2)
        == q
        == proof["collision_floor"]
    )
    capacity = comb(n, 2)
    rho = [next(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1)]
    best, cases = 10**20, 0
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= q:
                    cases += 1
                    value = (
                        (n - 1) * 107800 + 466200 * rho[e1] + 1117620 * rho[e2] + 1760031 * rho[e3]
                    )
                    best = min(best, value)
    assert best == h == proof["hunter_floor"]
    assert proof["threshold_cases"] == cases
    assert proof["minimizer"] == [q, 0, 0] and proof["ranks"] == [rank, 0, 0]
    assert proof["rank_floor_table"] == rho
    assert cert.hunter.verify_rank_floor_algebra(n) == capacity + 1


def test_all_48_true_residual_rows_and_type20_floor(result: dict[str, Any]) -> None:
    proof = result["ROOT_PAIR_PROOF"]
    rows = tuple(tuple(r) for r in proof["rows"])
    types = (0, 1, 2, 4, 5, 6, 8, 9, 16, 17, 19, 20)
    assert len(rows) == 48 and tuple(r[:6] for r in rows) == tuple(
        (0, t, 0, 0, 0, z) for t in types for z in range(4)
    )
    assert tuple(r[6] for r in rows[:4]) == (107800, 574000, 1691620, 3451651)
    floors = {
        0: 107800,
        1: 107800,
        2: 105560,
        4: 107800,
        5: 107800,
        6: 105560,
        8: 105560,
        9: 105560,
        16: 107800,
        17: 105560,
        19: 105560,
        20: 103600,
    }
    for row, recount in zip(rows, proof["recount"], strict=True):
        assert (
            row[6]
            == recount["raw_E"] - recount["triple_A"] - recount["triple_B"] + recount["quadruple"]
            == recount["residual_R"]
        )
        assert row[6] >= floors[row[1]]
        tickets = cert.hunter.realize_pair(
            cert.hunter.type_cells(0),
            cert.hunter.type_cells(row[1]),
            cast(cert.hunter.Cells, row[2:6]),
        )
        # Independent residual API and exact cell coverage, no lottery outcome enumeration.
        assert (
            cert.hunter.six.residual_pair_intersection(0, row[1], cast(cert.hunter.Cells, row[2:6]))
            == row[6]
        )
        assert len(tickets[0] & tickets[1]) == row[5]
    assert min(r[6] for r in rows if r[1] == 20) == 103600
    mixed = next(r for r in proof["recount"] if r["types"] == [0, 6] and r["cells"] == [0, 0, 0, 0])
    assert (mixed["raw_E"], mixed["residual_R"]) == (107800, 105560)
    pair20 = next(
        r for r in proof["recount"] if r["types"] == [0, 20] and r["cells"] == [0, 0, 0, 0]
    )
    assert pair20["residual_R"] == 103600 < pair20["raw_E"]
    typed = cast(tuple[cert.hunter.PairRow, ...], rows)
    for bad in ({**floors, 20: 105560}, {**floors, 6: 107800}, {**floors, 1: 574000}):
        with pytest.raises(AssertionError, match="residual"):
            cert.validate_root_rows(typed, bad)
    with pytest.raises(AssertionError):
        cert.validate_root_rows(typed[:-1], floors)
    raw = cast(
        tuple[cert.hunter.PairRow, ...],
        tuple((*r[:6], c["raw_E"]) for r, c in zip(rows, proof["recount"], strict=True)),
    )
    with pytest.raises(AssertionError):
        cert.validate_root_rows(raw, floors)


def test_universal_collision_nested_threshold_and_pointwise_hunter() -> None:
    for a in range(2, 79):
        for b in range(a - 1):
            assert comb(a, 2) + comb(b, 2) - comb(a - 1, 2) - comb(b + 1, 2) == a - b - 1 > 0
    assert cert.hunter.verify_threshold_tree_lemma() == 4096
    for n in (10, 11, 12, 13):
        indices = tuple(reversed(range(18 - n, 18)))
        core = tuple((indices[0], j) for j in indices[1:])
        attachments = tuple((indices[0], j) for j in range(18 - n))
        tree = cert.validate_tree_extension(indices, core, attachments)
        masks = tuple((1 << a) | (1 << b) for a, b in tree)
        # Enumerate abstract event-presence masks, never official lottery outcomes.
        for mask in range(1 << 18):
            assert int(mask > 0) <= mask.bit_count() - sum(mask & e == e for e in masks)
        for bad in (
            attachments[:-1],
            (core[0], *attachments[1:]),
            (attachments[0], *attachments[:-1]),
        ):
            with pytest.raises(AssertionError, match="tree"):
                cert.validate_tree_extension(indices, core, bad)
        with pytest.raises(AssertionError):
            cert.validate_tree_extension(indices, (*core[:-1], core[0]), attachments)


def test_all_170_credits_bounds_legal_supports_and_same_tree_weights(
    result: dict[str, Any],
) -> None:
    total = 0
    expected_credit = {
        "A1": 5558000,
        "A2": 4627560,
        "A3": 4627560,
        "B1": 4627560,
        "B2": 5091520,
        "B3": 6026160,
    }
    for region in result["REGIONS"]:
        for member in region["member_certificates"]:
            bounds: list[int] = []
            for r in member["vector_certificates"]:
                v, name = cert.dense(r["counts"]), r["cohort"]
                expected = {
                    "A1": 354141809 + 448 * int(v[5] > 0),
                    "A2": 353891944 + 448 * v[5],
                    "A3": 353925082 + 448 * v[5],
                    "B1": 354220678 + 448 * v[5],
                    "B2": 354034408,
                    "B3": 354244702 + 448 * v[5],
                }[name]
                n = v[0]
                leaf = sum(
                    c * (103600 if i == 20 else 105560 if i in (2, 6, 8, 9, 17, 19) else 107800)
                    for i, c in enumerate(v)
                    if i
                )
                assert (
                    result["CORE_PROOFS"][f"H{n}"]["hunter_floor"] + leaf
                    == expected_credit[name]
                    == r["root_credit"]
                )
                assert sum(v) == 18 and all(type(c) is int and c >= 0 for c in v)
                assert r["new_credit"] == max(r["corrections"].values()) == expected_credit[name]
                assert r["existing_applied_credit"] == max(
                    c for k, c in r["corrections"].items() if k != "PAIRED_ROOT"
                )
                assert (
                    r["vector_prior_bound"]
                    == cert.vector_rows(region["state_id"])[v]["final_bound"]
                )
                assert (
                    r["vector_new_bound"]
                    == min(r["vector_prior_bound"], r["uncorrected_bound"] - r["new_credit"])
                    == expected
                )
                assert r["uncorrected_bound"] == r["anchor_union"] + r["residual_event_sum"]
                w = r["witness_analysis"]
                support = tuple(tuple(t) for t in w["support_witness"])
                assert cert.hunter.r8.validate_support_assignment(v, support)
                assert not cert.hunter.r8.validate_support_assignment(v, (support[1], *support[1:]))
                tree = cert.validate_tree_extension(
                    tuple(w["core_indices"]),
                    tuple(tuple(e) for e in w["core_tree"]),
                    tuple(tuple(e) for e in w["attachment_edges"]),
                )
                assert len(tree) == len(w["edge_costs"]) == 17
                assert (
                    sum(w["edge_costs"][: n - 1]) >= result["CORE_PROOFS"][f"H{n}"]["hunter_floor"]
                )
                assert sum(w["edge_costs"]) == w["extended_exact_weight"] >= expected_credit[name]
                bounds.append(expected)
                total += 1
            assert member["member_new_bound"] == max(bounds)
    assert total == 170
    assert cert.apply_credit(100, 60, {"old": 50, "root": 30}) == (50, 50)
    assert cert.apply_credit(100, 40, {"old": 20, "root": 30}) == (30, 40)
    assert cert.member_bound((40, 60)) == 60
    for counts, n in (
        ((), 10),
        ((10.0, *([0] * 29)), 10),
        ((10, -1, 9, *([0] * 27)), 10),
        ((18, *([0] * 29)), 18),
    ):
        with pytest.raises(AssertionError):
            cert.validate_counts(cast(cert.CountVector, counts), n)


def test_every_untouched_member_vector_and_56574_ordered_terms(result: dict[str, Any]) -> None:
    for region, expected in zip(
        result["REGIONS"], ((1347, 1453, 355051410), (1152, 1245, 355060310)), strict=True
    ):
        state = region["state_id"]
        ids = {r["member_id"] for r in region["member_certificates"]}
        remainder = [r for r in region["complete_region_members"] if r["member_id"] not in ids]
        vectors = [v for r in remainder for v in r["represented_vector_bounds"]]
        assert (len(remainder), len(vectors), max(r["final_bound"] for r in remainder)) == expected
        assert all(r["final_bound"] == r["prior_bound"] for r in (*remainder, *vectors))
        old = {r["member_id"]: r for r in cert.region_rows(state)}
        for r in region["complete_region_members"]:
            for key in (
                "member_id",
                "witness_counts",
                "represented_vector_count",
                "represented_vectors",
                "raw_bound",
                "compression_signature",
            ):
                assert r[key] == old[r["member_id"]][key]
            assert r["final_bound"] == max(v["final_bound"] for v in r["represented_vector_bounds"])
        for r in remainder:
            assert r["final_bound"] == old[r["member_id"]]["final_bound"]
            for v in r["represented_vector_bounds"]:
                assert (
                    v["final_bound"]
                    == cert.vector_rows(state)[cert.dense(v["counts"])]["final_bound"]
                )
    before = cert.family_terms()
    bounds = {r["state_id"]: r["new_state_bound"] for r in result["REGIONS"]}
    after = tuple((k, bounds.get(k, b)) for k, b in before)
    assert len(before) == len(after) == len(dict(after)) == 56574
    assert sum(a != b for a, b in zip(before, after, strict=True)) == 2
    assert after[23:] == before[23:] and len(after[23:-1]) == 56550
    assert max(b for _, b in after[23:-1]) == 354800665 and after[-1] == (
        "unclassified-tail",
        354039277,
    )
    d = dict(after)
    assert d[cert.prior.STATE_A] == 355016928 and d["state:s2-14696976-s3-1059324"] == 354603232
    ordered = sorted(after, key=lambda r: (-r[1], r[0]))
    assert ordered[:2] == [("state:s2-12692531-s3-681744", 355073068), (cert.STATE_B, 355060310)]
    assert result["FINAL_OWNER"] == ordered[0][0] and result["RUNNER_UP"] == {
        "stable_id": ordered[1][0],
        "bound": ordered[1][1],
    }
    assert max(b for _, b in before) == result["START_COMPLETE_R3_UB"] == 355110434
    assert max(b for _, b in after) == result["FINAL_COMPLETE_R3_UB"] == 355073068
    assert result["STRICT_GAIN"] == 37366 and result["REMAINING_GAP"] == 41809180
    assert (
        sha256(repr(after).encode("ascii")).hexdigest()
        == result["FAMILY_RECOMPUTATION"]["new_sha256"]
        == "37f97730c6f223ca1a9458a6f01822788ba0e81f57da6f71e4989b621857f1e7"
    )
    for bad in (before[:-2] + before[-1:], tuple(reversed(before))):
        with pytest.raises(AssertionError):
            cert.recompute_family(bad, bounds)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_A",
        "missing_B",
        "missing_alias",
        "canonical",
        "type20",
        "raw_E",
        "mixed_collision",
        "Q10",
        "Q11",
        "Q12",
        "Q13",
        "H10",
        "H11",
        "H12",
        "H13",
        "duplicate_attachment",
        "SUM",
        "double_subtract",
        "member_MIN",
        "untouched_member",
        "untouched_vector",
        "missing_term",
        "owner",
        "runner_up",
        "state131",
        "state146",
        "classified",
        "tail",
        "witness",
        "source_hash",
        "H16",
    ],
)
def test_semantic_result_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    a, b = bad["REGIONS"]
    member = next(r for r in a["member_certificates"] if r["represented_vector_count"] > 1)
    record = member["vector_certificates"][0]
    if mutation in ("missing_A", "missing_B"):
        (a if mutation == "missing_A" else b)["member_certificates"].pop()
    elif mutation == "missing_alias":
        member["represented_vectors"].pop()
        member["vector_certificates"].pop()
    elif mutation == "canonical":
        member["counts"] = member["represented_vectors"][-1]
    elif mutation == "type20":
        bad["ROOT_PAIR_PROOF"]["root_floors"]["20"] = 105560
    elif mutation == "raw_E":
        for row, recount in zip(
            bad["ROOT_PAIR_PROOF"]["rows"], bad["ROOT_PAIR_PROOF"]["recount"], strict=True
        ):
            row[6] = recount["raw_E"]
    elif mutation == "mixed_collision":
        next(r for r in bad["ROOT_PAIR_PROOF"]["rows"] if r[1] == 1 and r[5] == 1)[6] = 574000
    elif mutation.startswith(("Q", "H")) and mutation != "H16":
        bad["CORE_PROOFS"]["H" + mutation[1:]][
            "collision_floor" if mutation[0] == "Q" else "hunter_floor"
        ] += 1
    elif mutation == "duplicate_attachment":
        w = record["witness_analysis"]
        w["attachment_edges"][0] = w["core_tree"][0]
    elif mutation == "SUM":
        record["new_credit"] = sum(record["corrections"].values())
    elif mutation == "double_subtract":
        record["vector_new_bound"] = record["uncorrected_bound"] - 2 * record["new_credit"]
    elif mutation == "member_MIN":
        row = next(
            r
            for r in b["complete_region_members"]
            if len({v["final_bound"] for v in r["represented_vector_bounds"]}) > 1
        )
        row["final_bound"] = min(v["final_bound"] for v in row["represented_vector_bounds"])
    elif mutation in ("untouched_member", "untouched_vector"):
        ids = {r["member_id"] for r in a["member_certificates"]}
        row = next(r for r in a["complete_region_members"] if r["member_id"] not in ids)
        (row if mutation == "untouched_member" else row["represented_vector_bounds"][0])[
            "final_bound"
        ] -= 1
    elif mutation == "missing_term":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER"] = cert.STATE_A
    elif mutation == "runner_up":
        bad["RUNNER_UP"]["stable_id"] = cert.STATE_A
    elif mutation in ("state131", "state146"):
        state = cert.prior.STATE_A if mutation == "state131" else "state:s2-14696976-s3-1059324"
        next(r for r in bad["FINAL_STATE_TERMS"] if r["stable_id"] == state)["bound"] -= 1
    elif mutation in ("classified", "tail"):
        bad["FAMILY_RECOMPUTATION"]["classified_max" if mutation == "classified" else "tail"] -= 1
    elif mutation == "witness":
        w = record["witness_analysis"]["support_witness"]
        w[0] = w[1]
    elif mutation == "H16":
        bad["PREDECESSOR_PRESERVATION"]["H16_credit"] += 1
    else:
        bad["SOURCE_AUTHORITY"]["implementation_sha256"][cert.SOURCE_RELATIVE] = "0" * 64
    with pytest.raises(AssertionError, match=r"replay|identity"):
        cert.verify_result(bad)


@pytest.mark.parametrize("n", [10, 11, 12, 13])
def test_live_wrong_collision_and_overstrong_hunter_minima(
    monkeypatch: pytest.MonkeyPatch, n: int
) -> None:
    original = cert.hunter.minimum_tree_correction
    cert.core_proof.cache_clear()

    def overstrong(phi: cert.hunter.Cells, mass: int, k: int = 18) -> cert.hunter.TreeMinimum:
        return replace(original(phi, mass, k), correction=original(phi, mass, k).correction + 1)

    def wrong_collision(_incidences: int, _labels: int) -> int:
        return 0

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "minimum_tree_correction", overstrong)
        with pytest.raises(AssertionError, match="minimum"):
            cert.core_proof(n)
    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "balanced_collision_mass", wrong_collision)
        with pytest.raises(AssertionError, match="collision"):
            cert.core_proof(n)
    cert.core_proof.cache_clear()
    assert cert.core_proof(n)["hunter_floor"] == cert.CORE_SPECS[n][2]


@pytest.mark.parametrize(
    "function,old,new,args,expected",
    [
        (
            "apply_credit",
            "credit = max(credits.values())",
            "credit = sum(credits.values())",
            (100, 80, {"old": 20, "root": 30}),
            (30, 70),
        ),
        (
            "apply_credit",
            "uncorrected - credit",
            "uncorrected - 2 * credit",
            (100, 80, {"old": 20, "root": 30}),
            (30, 70),
        ),
        ("member_bound", "return max(bounds)", "return min(bounds)", ((40, 60),), 60),
    ],
)
def test_actual_source_mutants_killed(
    function: str, old: str, new: str, args: tuple[Any, ...], expected: object
) -> None:
    original = cast(Callable[..., object], getattr(cert, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace = dict(vars(cert))
    exec(compile(source.replace(old, new), "<semantic-source-mutant>", "exec"), namespace)
    mutant = cast(Callable[..., object], namespace[function])
    assert original(*args) == expected
    with pytest.raises(AssertionError):
        assert mutant(*args) == expected
    assert original(*args) == expected


@pytest.mark.parametrize(
    "relative",
    [
        cert.BASE_RESULT,
        cert.h13.RESULT_RELATIVE,
        cert.root65.RESULT_RELATIVE,
        cert.root65.ts153.RESULT_RELATIVE,
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        cert.SOURCE_RELATIVE,
        cert.TEST_RELATIVE,
    ],
)
def test_live_source_result_tampering_after_warm_caches(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    original = Path.read_bytes

    def tampered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", tampered)
        with pytest.raises(AssertionError, match=r"identity|source binding"):
            cert.verify_result(result)


def test_stored_replay_and_no_forbidden_work(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
    assert (
        result["OWNER_REGION_CALLS"]
        == result["R7_CENSUS_CALLS"]
        == result["PREDECESSOR_REBUILD_CALLS"]
        == 0
    )
    assert (
        result["NEW_HEAVY_SOLVER_STARTED"] is result["OFFICIAL_OUTCOME_ENUMERATION_USED"] is False
    )
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"


@pytest.mark.parametrize(
    "name",
    [
        "test_fixed_authority_and_transitive_source_bytes",
        "test_all_target_bounds_max_only_and_sound_witnesses",
        "test_every_untouched_bound_and_complete_family_recomputation",
    ],
)
def test_relevant_h11_h16_predecessor_without_rebuild(name: str) -> None:
    namespace = runpy.run_path(str(cert.REPO_ROOT / cert.prior.TEST_RELATIVE))
    check = cast(Callable[[dict[str, Any]], None], namespace[name])
    check(cert.sealed(cert.BASE_RESULT))


@pytest.mark.parametrize(
    "module,relative,name",
    [
        (
            cert.h13.SOURCE_RELATIVE,
            cert.h13.RESULT_RELATIVE,
            "test_exact_base_donor_and_executing_import_closure",
        ),
        (
            cert.h13.SOURCE_RELATIVE,
            cert.h13.RESULT_RELATIVE,
            "test_max_only_credits_eight_bounds_and_sound_witnesses",
        ),
        (
            cert.h13.SOURCE_RELATIVE,
            cert.h13.RESULT_RELATIVE,
            "test_preserve_every_untouched_member_and_vector_and_recompute_all_terms",
        ),
        (
            cert.root65.SOURCE_RELATIVE,
            cert.root65.RESULT_RELATIVE,
            "test_all_members_vectors_aliases_and_65_actual_identities",
        ),
        (
            cert.root65.SOURCE_RELATIVE,
            cert.root65.RESULT_RELATIVE,
            "test_max_only_credits_and_strongest_untouched_vector_bounds",
        ),
        (
            "src/lottolab/research/b649_k20_r3_state_14696976_universal_hunter_certificate_r1.py",
            cert.h13.BASE_RESULT,
            "test_complete_family_only_one_state_changes_and_max_only",
        ),
        (
            "src/lottolab/research/b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
            cert.root65.ts153.RESULT_RELATIVE,
            "test_immutable_authority_complete_regions_and_target_digests",
        ),
        (
            "src/lottolab/research/b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
            cert.root65.ts153.RESULT_RELATIVE,
            "test_max_once_credits_preserved_and_compressed_max",
        ),
        (
            "src/lottolab/research/b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
            cert.root65.ts153.RESULT_RELATIVE,
            "test_untouched_remainder_family_and_witness_soundness",
        ),
    ],
)
def test_relevant_earlier_predecessors_without_rebuild(
    module: str, relative: str, name: str
) -> None:
    path = "tests/unit/test_" + Path(module).name
    assert (cert.REPO_ROOT / path).read_bytes() == cert.frozen_blob(path)
    namespace = runpy.run_path(str(cert.REPO_ROOT / path))
    check = cast(Callable[[dict[str, Any]], None], namespace[name])
    check(cert.sealed(relative))
