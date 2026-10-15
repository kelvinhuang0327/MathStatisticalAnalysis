"""Independent integer proofs, sealed coverage, preservation and semantic mutants."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from math import comb
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import (
    b649_k20_r3_classified_r12_five_level_ten_event_certificate_r1 as cert,
)

PHI = (107800, 571200, 1679692, 3428908)
BOUNDS = [354588304, 354587856, 354587408, 354586960, 354586512]


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor rebuild, classification, census or solver")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module in (
            cert.nine,
            cert.ts153,
            cert.ts153.ts61,
            cert.ts153.joint,
            cert.ts153.ts53,
            cert.ts153.prior,
            cert.ts153.h11,
        ):
            patch.setattr(module, "build_result", forbidden)
            patch.setattr(module, "verify_stored_result", forbidden)
        patch.setattr(cert.nine, "aggregate_levels", forbidden)
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.r6, "iter_type_count_vectors", forbidden)
        patch.setattr(cert.r12, "tail_level_census", forbidden)
        patch.setattr(cert.r12, "classify_vector", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        minimum = cert.hunter.minimum_tree_correction

        def bounded(phi: cert.Cells, q: int, n: int = 18) -> Any:
            assert n == 10, "TS153 large threshold enumeration must never run"
            return minimum(phi, q, n)

        patch.setattr(cert.hunter, "minimum_tree_correction", bounded)
        return cert.build_result()


def test_immutable_authority_and_complete_sealed_coverage(result: dict[str, Any]) -> None:
    identity = cert.verify_source_authority()
    assert identity["HEAD"] == "b25f5b17440b8eb3e344f6c2567473081995646c"
    assert identity["TREE"] == "7ef64b1c6071c53e6612872009f07134aff4af9a"
    assert identity["RESULT_SHA256"] == (
        "800641b391ee23961ddbe12a1806670322063a6ee759465720d7cabe36a4f159"
    )
    assert identity == result["SOURCE_AUTHORITY"]
    for relative, expected in identity["donor_sha256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == expected
    levels = cert.aggregate_levels()
    assert [r.ordinal for r in levels] == [i for i in range(1, 33) if i not in (1, 2, 24)]
    flat = [v for r in levels for v in r.vectors]
    assert len(levels) == result["AGGREGATE_LEVEL_COVERAGE"] == 29
    assert len(flat) == len(set(flat)) == result["AGGREGATE_VECTOR_COVERAGE"] == 183
    assert (
        sha256(repr(tuple((r.ordinal, r.vectors) for r in levels)).encode("ascii")).hexdigest()
        == (result["AGGREGATE_VECTORS_SHA256"])
        == "4cb42408f0b805ea9d7cfab99df2bf44b733ea43d5fc01612d0e246c962f1801"
    )
    targets = cert.target_levels(levels)
    actual: list[tuple[int, cert.CountVector, tuple[object, ...]]] = []
    for k, level in enumerate(targets):
        assert level.ordinal == (25, 26, 27, 30, 32)[k]
        expected = {
            tuple({0: 9, 1: a, 4: 2 - a, 5: 7 - k, 16: k}.get(i, 0) for i in range(30))
            for a in range(3)
        }
        assert set(level.vectors) == expected
        for v in level.vectors:
            raw = level.source_row["level_prior_bound"]
            state = cert.catalog.rebuild_member(cert.catalog.LedgerMember(v, 1, raw, raw))
            signature = cert.hunter.eleven.compression_signature(state)
            assert signature == cert.vector_signature(v)
            actual.append((level.ordinal, v, signature))
            u = cert.select_subset(v)
            assert sum(u) == 10 and u[0] == 9
            assert u[1] == int(v[1] > 0) and u[4] == int(v[1] == 0)
            assert all(a <= b for a, b in zip(u, v, strict=True))
    assert len(actual) == result["TARGET_VECTOR_COVERAGE"] == 15
    assert (
        sha256(repr(tuple(actual)).encode("ascii")).hexdigest()
        == (result["TARGET_SIGNATURE_DIGEST"])
        == "8a342aa566133a49891871a7e8b8cc75e1f52297e221aeaf6cdc0d4a92a10e32"
    )


def test_exact_pair_rows_mixed_floors_and_complete_integer_relaxation(
    result: dict[str, Any],
) -> None:
    proof = result["TEN_EVENT_PROOF"]
    assert proof["residual_event_definition"] == "R_i = E_i \\ (E_A \u222a E_B)"
    expected = {
        (0, 0): (107800, 574000, 1691620, 3451651),
        (0, 1): PHI,
        (0, 4): PHI,
    }
    rows: list[list[int]] = []
    for (a, b), costs in expected.items():
        for overlap, value in enumerate(costs):
            cells = (0, 0, 0, overlap)
            tickets = cert.hunter.realize_pair(
                cert.hunter.type_cells(a), cert.hunter.type_cells(b), cells
            )
            assert cert.six.residual_pair_intersection(a, b, cells) == value
            assert (
                cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B))
                == value
            )
            rows.append([a, b, *cells, value])
    assert proof["pair_rows"] == rows and len(rows) == 12
    assert proof["pair_floors"] == list(PHI)
    with pytest.raises(AssertionError, match="floor exceeds"):
        cert.hunter.require_safe_pair_floors(
            (107800, 574000, 1691620, 3451651),
            cert.hunter.exact_pair_rows(((0, 0), (0, 1), (0, 4))),
        )
    assert proof["outside_incidences"] == 9 * 6 + 5 == 59
    assert len(proof["outside_labels"]) == 40
    assert proof["balanced_frequencies"] == [[1, 21], [2, 19]]
    assert proof["collision_mass_floor"] == 21 * comb(1, 2) + 19 * comb(2, 2) == 19
    # Smoothing one unit between frequencies differing by >=2 reduces the objective.
    for hi in range(2, 11):
        for lo in range(hi - 1):
            assert comb(hi, 2) + comb(lo, 2) - comb(hi - 1, 2) - comb(lo + 1, 2) == hi - lo - 1 > 0
    rho = [next(r for r in range(10) if comb(r + 1, 2) >= e) for e in range(46)]
    assert proof["rank_floor_table"] == rho
    candidates = [
        (
            9 * PHI[0] + sum((PHI[j + 1] - PHI[j]) * rho[e] for j, e in enumerate((e1, e2, e3))),
            (e1, e2, e3),
        )
        for e1 in range(46)
        for e2 in range(e1 + 1)
        for e3 in range(e2 + 1)
        if e1 + e2 + e3 >= 19
    ]
    assert len(candidates) == proof["all_admissible_threshold_cases"] == 17022
    assert min(candidates) == (3750600, (19, 0, 0))
    assert proof["integer_minimizer"] == {"edge_counts": [19, 0, 0], "rank_floors": [6, 0, 0]}
    assert proof["hunter_floor"] == 9 * 107800 + 6 * (571200 - 107800) == 3750600


def test_universal_graph_rank_kruskal_and_pointwise_hunter() -> None:
    for a in range(10):
        for b in range(10 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_all_fifteen_witnesses_and_universal_tree_extensions(result: dict[str, Any]) -> None:
    seen: set[cert.CountVector] = set()
    for level in result["LEVEL_CERTIFICATES"]:
        for row in level["vector_certificates"]:
            v = cert.dense(row["counts"])
            seen.add(v)
            u = cert.select_subset(v)
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            tickets = tuple(frozenset(t) for t in support)
            anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
            assert cert.hunter.r8.validate_support_assignment(v, support)
            assert len(set((*anchors, *tickets))) == 20
            assert all(len(a & b) <= 3 for a, b in combinations((*anchors, *tickets), 2))
            assert cert.digest(support) == row["support_sha256"]
            types = tuple(i for i, n in enumerate(v) for _ in range(n))
            witness = row["witness_analysis"]
            indices = cast(list[int], witness["selected_event_indices"])
            assert [types[j] for j in indices] == [0] * 9 + [1 if v[1] else 4]
            selected = tuple(tickets[j] for j in indices)
            overlaps = {
                (a, b): len(selected[a] & selected[b]) for a, b in combinations(range(10), 2)
            }
            mass = sum(comb(sum(x in t for t in selected), 2) for x in cert.hunter.CELL_LABELS[3])
            assert mass == sum(overlaps.values()) == witness["collision_mass"] >= 19
            tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
            assert len(tree) == cert.hunter.graph_rank(10, tree) == 9
            for j in range(1, 4):
                graph = [e for e, value in overlaps.items() if value >= j]
                assert sum(overlaps[e] >= j for e in tree) == cert.hunter.graph_rank(10, graph)
            weight = sum(PHI[overlaps[e]] for e in tree)
            assert weight == witness["phi_tree_weight"] >= 3750600
            full = [(int(a), int(b)) for a, b in witness["extended_tree"]]
            assert len(full) == cert.hunter.graph_rank(18, full) == 17
            total = 0
            for a, b in full:
                cells = cast(
                    cert.Cells,
                    tuple(len(tickets[a] & tickets[b] & set(c)) for c in cert.hunter.CELL_LABELS),
                )
                cost = cert.six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
                assert cost >= 0
                total += cost
            assert total == witness["extended_tree_exact_weight"] >= weight
            extension = cert.tree_extension_proof(v, u)
            assert extension == row["tree_extension"]
            assert extension["subset_tree_edges"] == 9
            assert extension["extended_tree_edges"] == 17
            assert len(extension["attachment_edges"]) == 8
            assert all(a["minimum_intersection"] >= 0 for a in extension["attachment_edges"])
    assert len(seen) == 15


def test_max_only_credit_preservation_and_all_five_level_bounds(result: dict[str, Any]) -> None:
    _, ledger = cert.source_results()
    old = {
        cert.dense(v["counts"]): v
        for r in ledger["LEVEL_CERTIFICATES"]
        for v in r["vector_certificates"]
    }
    assert result["NEW_FIVE_LEVEL_BOUNDS"] == BOUNDS
    for k, level in enumerate(result["LEVEL_CERTIFICATES"]):
        assert len(level["vector_certificates"]) == level["represented_vector_count"] == 3
        bounds: list[int] = []
        for row in level["vector_certificates"]:
            v = cert.dense(row["counts"])
            for name, credit in old[v]["corrections"].items():
                assert row["corrections"][name] == credit
            assert row["corrections"]["NINE_EVENT_HUNTER"] == 3193400
            assert row["corrections"]["TEN_EVENT_HUNTER"] == 3750600
            assert row["prior_applied_correction"] == 3193400
            assert row["combined_correction"] == max(row["corrections"].values()) == 3750600
            assert row["combined_correction"] != sum(row["corrections"].values())
            assert row["uncorrected_anchor_bound"] == 358338904 - 448 * k
            assert row["vector_new_bound"] == min(
                row["vector_prior_bound"], row["uncorrected_anchor_bound"] - 3750600
            )
            bounds.append(row["vector_new_bound"])
        assert max(bounds) == level["level_new_bound"] == BOUNDS[k]


def test_untouched_bounds_and_all_56574_family_terms_remaximized(result: dict[str, Any]) -> None:
    source, ledger = cert.source_results()
    before = {r["ordinal"]: r for r in ledger["COMPLETE_AGGREGATE_LEVELS"]}
    remainder: list[dict[str, Any]] = []
    for row in result["COMPLETE_AGGREGATE_LEVELS"]:
        if row["ordinal"] not in cert.TARGET_ORDINALS:
            assert row == {
                **before[row["ordinal"]],
                "adopted_prior_bound": before[row["ordinal"]]["level_final_bound"],
            }
            remainder.append(row)
    assert len(remainder) == 24 and sum(r["represented_vector_count"] for r in remainder) == 168
    assert max(r["level_final_bound"] for r in remainder) == 354333735
    states, classified, tail = cert.family_inputs()
    updated = tuple((r["stable_id"], r["bound"]) for r in result["FINAL_CLASSIFIED_TERMS"])
    assert len(updated) == len(classified) == 56550
    assert [(k, b) for k, b in classified if k != cert.r24.AGGREGATE_ID] == [
        (k, b) for k, b in updated if k != cert.r24.AGGREGATE_ID
    ]
    assert sum(b != new for (_, b), (_, new) in zip(classified, updated, strict=True)) == 1
    assert result["PRESERVED_EXPLICIT_CLASSIFIED"]["count"] == 56549
    assert result["PRESERVED_EXPLICIT_CLASSIFIED"]["maximum"] == 354800665
    assert (
        cert.digest(updated)
        == result["NEW_CLASSIFIED_DIGEST"]
        == ("c5e05f33c98da7ec83bd5cef319a23929600be16df7cbaad36d7a032126acbeb")
    )
    assert max(b for _, b in updated) == result["NEW_CLASSIFIED_MAX"] == 354800665
    assert result["FINAL_STATE_TERMS"] == source["FINAL_STATE_TERMS"]
    assert len(states) == 23 and tail == result["TAIL_BOUND"] == 354039277
    assert {sid: dict(states)[sid] for sid in cert.ts153.EXPECTED_STATE_BOUNDS} == (
        cert.ts153.EXPECTED_STATE_BOUNDS
    )
    terms = (*states, *updated, (cert.r24.TAIL_ID, tail))
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    assert (
        len(terms) == len(dict(terms)) == result["FULL_FAMILY_RECOMPUTATION"]["term_count"] == 56574
    )
    assert cert.digest(terms) == result["FULL_FAMILY_RECOMPUTATION"]["terms_sha256"]
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355142998
    assert (
        [k for k, b in terms if b == maximum]
        == [result["FINAL_OWNER"]]
        == ["state:s2-13169800-s3-789320"]
    )
    assert runner == result["RUNNER_UP"]["bound"] == 355141066
    assert (
        [k for k, b in terms if b == runner]
        == result["RUNNER_UP"]["owner_ids"]
        == ["state:s2-12695020-s3-735532"]
    )
    assert result["START_COMPLETE_R3_UB"] - maximum == result["STRICT_GAIN"] == 2506
    assert maximum - 313263888 == result["REMAINING_GAP"] == 41879110


@pytest.mark.parametrize("mutation", ("wrong_mixed_floor", "wrong_q", "rank", "threshold_case"))
def test_non_equivalent_proof_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    if mutation == "wrong_mixed_floor":

        def wrong_floors(_rows: object) -> cert.Cells:
            return (107800, 574000, 1691620, 3451651)

        monkeypatch.setattr(cert.hunter, "pair_floors", wrong_floors)
    elif mutation == "wrong_q":
        original = cert.hunter.balanced_collision_mass

        def wrong_mass(i: int, n: int) -> int:
            return original(i, n) - 1

        monkeypatch.setattr(cert.hunter, "balanced_collision_mass", wrong_mass)
    elif mutation == "rank":
        original_rank = cert.hunter.rank_floor

        def wrong_rank(e: int) -> int:
            return original_rank(e) - int(e > 0)

        monkeypatch.setattr(cert.hunter, "rank_floor", wrong_rank)
    else:
        original_minimum = cert.hunter.minimum_tree_correction

        def incomplete(phi: cert.Cells, q: int, n: int = 18) -> Any:
            value = original_minimum(phi, q, n)
            return replace(value, census_size=value.census_size - 1)

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", incomplete)
    with pytest.raises(AssertionError):
        cert.ten_event_proof()
    monkeypatch.undo()
    assert cert.ten_event_proof()["hunter_floor"] == 3750600


def test_sum_credit_missing_vector_missing_family_and_signature_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    levels = cert.aggregate_levels()
    level = cert.target_levels(levels)[0]
    proof = cert.ten_event_proof()
    with pytest.MonkeyPatch.context() as patch:

        def additive(values: Mapping[str, int]) -> int:
            return sum(values.values())

        patch.setattr(cert.hunter, "combine_corrections", additive)
        with pytest.raises(AssertionError, match="MAX single"):
            cert.certify_vector(level, level.vectors[0], proof)
    for invalid in (level.vectors[:2], (level.vectors[0],) * 3, tuple(reversed(level.vectors))):
        with pytest.raises(AssertionError, match="represented-vector"):
            cert.certify_level(level, invalid, proof)
    original_sealed = cert.sealed
    corrupted = copy.deepcopy(original_sealed(cert.nine.RESULT_RELATIVE))
    target = next(r for r in corrupted["COMPLETE_AGGREGATE_LEVELS"] if r["ordinal"] == 25)
    target["represented_vectors"].pop()

    def missing_vector(p: str) -> dict[str, Any]:
        return corrupted if p == cert.nine.RESULT_RELATIVE else original_sealed(p)

    monkeypatch.setattr(cert, "sealed", missing_vector)
    with pytest.raises(AssertionError, match="coverage"):
        cert.aggregate_levels()
    monkeypatch.undo()
    states, classified, tail = cert.family_inputs()
    monkeypatch.setattr(cert, "family_inputs", lambda: (states, classified[:-1], tail))
    with pytest.raises(AssertionError, match="Family term coverage"):
        cert.recompute_family(354588304)
    monkeypatch.undo()
    original_signature = cert.vector_signature
    alias = level.vectors[-1]

    def wrong_signature(v: cert.CountVector) -> tuple[object, ...]:
        return ("wrong",) if v == alias else original_signature(v)

    monkeypatch.setattr(cert, "vector_signature", wrong_signature)
    with pytest.raises(AssertionError, match="fifteen actual target signatures"):
        cert.target_levels(levels)
    monkeypatch.undo()
    assert cert.certify_vector(level, level.vectors[0], proof)["vector_new_bound"] == BOUNDS[0]


def test_illegal_witness_subset_and_negative_extension_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    level = cert.target_levels(cert.aggregate_levels())[0]
    v = level.vectors[0]
    u = cert.select_subset(v)
    row = cert.certify_vector(level, v, cert.ten_event_proof())
    support = tuple(tuple(t) for t in row["support_witness"])
    with pytest.raises(AssertionError, match="illegal"):
        cert.witness_analysis(v, u, (support[0],) * 18, cert.ten_event_proof())
    with pytest.raises(AssertionError, match="applicability"):
        cert.select_subset(tuple(c - int(i == 0) for i, c in enumerate(v)))
    original_rows = cert.ts153.prior.verified_pair_rows

    def negative(pair: tuple[int, int]) -> Any:
        rows = original_rows(pair)
        return (*rows[:-1], (*rows[-1][:6], -1))

    monkeypatch.setattr(cert.ts153.prior, "verified_pair_rows", negative)
    with pytest.raises(AssertionError, match="nonnegative"):
        cert.tree_extension_proof(v, u)
    monkeypatch.undo()
    assert cert.tree_extension_proof(v, u)["extended_tree_edges"] == 17


def test_warm_cache_authority_tamper_and_exact_byte_replay(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cert, "BASE_TREE", "0" * 40)
    with pytest.raises(AssertionError, match="BASE HEAD/TREE"):
        cert.build_result()
    monkeypatch.undo()
    original_read = cert.Path.read_bytes
    target = cert.REPO_ROOT / cert.nine.RESULT_RELATIVE

    def changed(path: cert.Path) -> bytes:
        value = original_read(path)
        return value + b" " if path == target else value

    monkeypatch.setattr(cert.Path, "read_bytes", changed)
    with pytest.raises(AssertionError, match="immutable donor bytes"):
        cert.build_result()
    monkeypatch.undo()
    assert cert.verify_result(result)["status"] == "PASS"
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert json.loads(cert.RESULT_PATH.read_bytes()) == result
    assert cert.verify_stored_result()["status"] == "PASS"
