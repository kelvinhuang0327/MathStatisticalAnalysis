"""Focused independent coverage, arithmetic and non-equivalent mutation guards."""

from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Callable, Mapping
from hashlib import sha256
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_ts153_four_state_wall_adoption_r2 as cert

type Rows = list[list[int]]


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor rebuild, census, heavy solver or chase")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module in (cert.ts61, cert.joint, cert.ts53, cert.h11, cert.prior, cert.prior.h0):
            patch.setattr(module, "build_result", forbidden)
            patch.setattr(module, "verify_stored_result", forbidden)
        patch.setattr(cert.joint, "universal_proof", forbidden)
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def vector(values: dict[int, int]) -> cert.CountVector:
    return tuple(values.get(i, 0) for i in range(30))


def vector_rows(result: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    return [
        (region["state_id"], record, row)
        for region in result["REGIONS"]
        for record in region["member_certificates"]
        for row in record["vector_certificates"]
    ]


def proofs(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["proof_id"]: p for p in result["SUBSET_PROOFS"]}


def rank(e: int) -> int:
    r = 0
    while comb(r + 1, 2) < e:
        r += 1
    return r


def test_immutable_authority_complete_regions_and_target_digests(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert authority["HEAD"] == "116f6a84d18b540931fb733c522ba5a72e6d7eb9"
    assert authority["TREE"] == "d4d190632737c86ea62335da0f5dde2d790d6590"
    assert authority["RESULT_SHA256"] == (
        "4fbcb5733c7a0a3035dbcc8eff30d8d93d6fd6d2124dc86734aff6f0fa174816"
    )
    assert result["SOURCE_AUTHORITY"] == authority
    assert set(authority["donor_sha256"]) == set(cert.source_paths())
    identities: list[tuple[str, cert.CountVector, tuple[cert.CountVector, ...]]] = []
    new_bounds: list[tuple[str, cert.CountVector, int]] = []
    coverage = [0, 0, 0, 0, 0]
    for region in result["REGIONS"]:
        sid = region["state_id"]
        members, recovered = cert.region_members(sid), cert.represented_vectors(sid)
        spec = cert.REGION_SPECS[sid]
        assert cert.catalog.region_fingerprint(members) == spec[0]
        assert (len(members), sum(len(v) for v in recovered.values())) == spec[1:3]
        assert max(m.final_bound for m in members) == dict(cert.state_terms())[sid]
        target_members = [m for m in members if m.final_bound > 355145504]
        assert [cert.member_id(m.counts) for m in target_members] == [
            r["member_id"] for r in region["member_certificates"]
        ]
        assert (
            len(target_members),
            sum(m.represented_vector_count for m in target_members),
            sum(m.represented_vector_count > 1 for m in target_members),
        ) == spec[3:]
        for member, row in zip(members, cert.region_rows(sid), strict=True):
            vectors = recovered[member.counts]
            assert len(vectors) == member.represented_vector_count
            assert min(vectors) == member.counts
            assert row["represented_vectors"] == [cert.sparse(v) for v in vectors]
            signature = cert.hunter.eleven.compression_signature(
                cert.catalog.rebuild_member(member)
            )
            if sid != cert.STATE_12692531:
                assert row["compression_signature"] == cert.catalog.normalized(signature)
            for v in vectors:
                state = cert.catalog.rebuild_member(cert.replace(member, counts=v))
                assert state.joint_s2 >= int(sid.split("-s3-")[0].split("s2-")[1])
                assert state.joint_s3 <= int(sid.split("-s3-")[1])
                assert cert.hunter.eleven.compression_signature(state) == signature
                assert cert.hunter.r14.raw_bound(state) == member.raw_bound
        for m in target_members:
            identities.append((sid, m.counts, tuple(sorted(recovered[m.counts]))))
        for m in region["member_certificates"]:
            new_bounds.append((sid, cert.dense(m["witness_counts"]), m["member_new_bound"]))
        coverage = [a + b for a, b in zip(coverage, (*spec[1:3], *spec[3:]), strict=True)]
    assert coverage == [3007, 3251, 153, 159, 6]
    assert (
        sha256(repr(tuple(sorted(identities))).encode("ascii")).hexdigest()
        == (result["TARGET_IDENTITY_DIGEST"])
        == cert.EXPECTED_TARGET_IDENTITY_DIGEST
    )
    assert (
        sha256(repr(tuple(sorted(new_bounds))).encode("ascii")).hexdigest()
        == (result["NEW_MEMBER_BOUND_DIGEST"])
        == cert.EXPECTED_MEMBER_NEW_BOUND_DIGEST
    )


def test_deterministic_full_or_delete_one_ranking(result: dict[str, Any]) -> None:
    sizes: list[int] = []
    for _sid, _member, row in vector_rows(result):
        v, u = cert.dense(row["counts"]), cert.dense(row["selected_subset_counts"])
        candidates = [
            v,
            *(
                tuple(c - int(i == j) for i, c in enumerate(v))
                for j, count in enumerate(v)
                if count
            ),
        ]

        def ranking(c: cert.CountVector) -> tuple[int, int, cert.CountVector]:
            _rows, phi, _inc, collision = cert.prior.subset_parameters(c)
            n = sum(c)
            floor = min(
                (n - 1) * phi[0]
                + (phi[1] - phi[0]) * a
                + (phi[2] - phi[1]) * b
                + (phi[3] - phi[2]) * d
                for a in range(n)
                for b in range(a + 1)
                for d in range(b + 1)
                if comb(a + 1, 2) + comb(b + 1, 2) + comb(d + 1, 2) >= sum(collision)
            )
            return -floor, n, c

        assert u == min(candidates, key=ranking)
        for c in candidates:
            assert all(0 <= a <= b for a, b in zip(c, v, strict=True))
            assert sum(c) in (17, 18)
        sizes.append(sum(u))
    assert (sizes.count(18), sizes.count(17)) == (70, 89)
    assert len(proofs(result)) == 140


def test_selected_subsets_complete_pair_rows_and_type_applicability(
    result: dict[str, Any],
) -> None:
    by_id = proofs(result)
    used: set[str] = set()
    for _sid, _record, row in vector_rows(result):
        v, u = cert.dense(row["counts"]), cert.dense(row["selected_subset_counts"])
        assert all(0 <= a <= b for a, b in zip(u, v, strict=True))
        assert 2 <= sum(u) <= 18 and sum(u) in (17, 18)
        assert row["deleted_event_types"] == [i for i in range(30) for _ in range(v[i] - u[i])]
        assert row["proof_id"] == cert.digest(u)
        used.add(row["proof_id"])
    assert used == set(by_id) and len(by_id) == 140
    checked: set[tuple[int, ...]] = set()
    for proof in by_id.values():
        u = cert.dense(proof["selected_subset_counts"])
        events = [i for i, c in enumerate(u) for _ in range(c)]
        pairs = sorted({(min(a, b), max(a, b)) for a, b in combinations(events, 2)})
        assert [tuple(p) for p in proof["occupied_type_pairs"]] == pairs
        rows = cast(Rows, proof["pair_rows"])
        for pair in pairs:
            left, right = (cert.hunter.type_cells(i) for i in pair)
            legal = {
                c
                for c in product(
                    *(
                        range(max(0, a + b - len(labels)), min(a, b) + 1)
                        for a, b, labels in zip(left, right, cert.hunter.CELL_LABELS, strict=True)
                    )
                )
                if sum(c) <= 3
            }
            actual = [r for r in rows if tuple(r[:2]) == pair]
            assert len(actual) == len(legal) and {tuple(r[2:6]) for r in actual} == legal
            for r in actual:
                key = tuple(r)
                if key in checked:
                    continue
                checked.add(key)
                cells = cast(tuple[int, int, int, int], tuple(r[2:6]))
                e, f = cert.hunter.realize_pair(left, right, cells)
                anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
                assert r[6] == (
                    cert.hunter.outcome_count((e, f))
                    - cert.hunter.outcome_count((e, f, anchors[0]))
                    - cert.hunter.outcome_count((e, f, anchors[1]))
                    + cert.hunter.outcome_count((e, f, *anchors))
                )
        phi = [min(r[6] for r in rows if sum(r[2:6]) == k) for k in range(4)]
        assert proof["pair_floors"] == phi and phi == sorted(phi) and phi[0] >= 0
    assert len(checked) == 261
    assert len({r[:2] for r in checked}) == 45
    # A floor read from the pure type-0 pair is illegal on mixed pairs.
    rejected = 0
    for proof in by_id.values():
        rows = [
            cast(tuple[int, int, int, int, int, int, int], tuple(r)) for r in proof["pair_rows"]
        ]
        pure = [r for r in rows if r[:2] == (0, 0)]
        if not pure:
            continue
        wrong = tuple(min(r[6] for r in pure if sum(r[2:6]) == k) for k in range(4))
        if any(w > f for w, f in zip(wrong, proof["pair_floors"], strict=True)):
            rejected += 1
            with pytest.raises(AssertionError, match="exceeds an exact row"):
                cert.hunter.require_safe_pair_floors(wrong, rows)
    assert rejected > 0


def test_full_target_pair_catalog_exact_all_56_pairs_330_rows(result: dict[str, Any]) -> None:
    pairs: set[tuple[int, int]] = set()
    for _, _, row in vector_rows(result):
        v = cert.dense(row["counts"])
        events = [i for i, count in enumerate(v) for _ in range(count)]
        pairs.update((min(a, b), max(a, b)) for a, b in combinations(events, 2))
    assert sorted(pairs) == [tuple(p) for p in result["FULL_TARGET_TYPE_PAIRS"]]
    assert len(pairs) == result["TYPE_PAIR_COUNT"] == 56
    rows = result["FULL_TARGET_PAIR_ROWS"]
    assert len(rows) == len({tuple(row) for row in rows}) == result["LEGAL_PAIR_ROW_COUNT"] == 330
    for pair in pairs:
        left, right = (cert.hunter.type_cells(i) for i in pair)
        legal = {
            cells
            for cells in product(
                *(
                    range(max(0, a + b - len(labels)), min(a, b) + 1)
                    for a, b, labels in zip(left, right, cert.hunter.CELL_LABELS, strict=True)
                )
            )
            if sum(cells) <= 3
        }
        actual = [r for r in rows if tuple(r[:2]) == pair]
        assert len(actual) == len(legal) and {tuple(r[2:6]) for r in actual} == legal
        for row in actual:
            cells = cast(tuple[int, int, int, int], tuple(row[2:6]))
            e, f = cert.hunter.realize_pair(left, right, cells)
            a, b = cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B
            assert (
                row[6]
                == (
                    cert.hunter.outcome_count((e, f))
                    - cert.hunter.outcome_count((e, f, a))
                    - cert.hunter.outcome_count((e, f, b))
                    + cert.hunter.outcome_count((e, f, a, b))
                )
                >= 0
            )
    assert {tuple(r) for p in result["SUBSET_PROOFS"] for r in p["pair_rows"]} <= {
        tuple(r) for r in rows
    }


def test_balanced_collision_floor_exact_universal_and_tight(result: dict[str, Any]) -> None:
    for proof in proofs(result).values():
        u = cert.dense(proof["selected_subset_counts"])
        incidences = [
            sum(c * cert.hunter.type_cells(i)[k] for i, c in enumerate(u)) for k in range(4)
        ]
        assert proof["cell_incidences"] == incidences
        floors: list[int] = []
        for total, labels in zip(incidences, cert.hunter.CELL_LABELS, strict=True):
            size = len(labels)
            balanced = [total // size + int(i < total % size) for i in range(size)]
            floor = sum(comb(d, 2) for d in balanced)
            # Smoothing: any transfer away from balance never lowers the mass.
            for i, j in product(range(size), repeat=2):
                if i != j and balanced[i] > 0:
                    moved = list(balanced)
                    moved[i] -= 1
                    moved[j] += 1
                    assert sum(comb(d, 2) for d in moved) >= floor
            floors.append(floor)
        assert proof["cell_collision_floors"] == floors
        # The balanced support attains Q, so Q + 1 would be an over-tight claim.
        assert proof["collision_mass_floor"] == sum(floors)
    for _sid, _record, row in vector_rows(result):
        proof = proofs(result)[row["proof_id"]]
        observed = row["witness_analysis"]["cell_collision_mass"]
        assert all(o >= f for o, f in zip(observed, proof["cell_collision_floors"], strict=True))


def test_all_40_threshold_groups_independent_complete_integer_minima(
    result: dict[str, Any],
) -> None:
    groups = {
        (tuple(p["pair_floors"]), p["collision_mass_floor"], p["event_count"]): p
        for p in result["SUBSET_PROOFS"]
    }
    assert len(groups) == 40
    total_cases = 0
    for (phi, q, n), proof in groups.items():
        ranks = [rank(e) for e in range(comb(n, 2) + 1)]
        best: tuple[int, tuple[int, int, int]] | None = None
        cases = 0
        for e1 in range(comb(n, 2) + 1):
            for e2 in range(e1 + 1):
                for e3 in range(e2 + 1):
                    if e1 + e2 + e3 < q:
                        continue
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
        assert best[0] == proof["hunter_floor"]
        assert list(best[1]) == proof["integer_minimizer"]["edge_counts"]
        assert [ranks[e] for e in best[1]] == proof["integer_minimizer"]["rank_floors"]
        assert cases == proof["all_admissible_threshold_cases"]
        assert cases == sum(proof["admissible_case_counts"])
        total_cases += cases
    assert total_cases == result["ADMISSIBLE_THRESHOLD_CASES"] == 19933125


def test_universal_smoothing_graph_rank_kruskal_and_pointwise_hunter() -> None:
    for high in range(2, 19):
        for low in range(high - 1):
            assert (
                comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
                == high - low - 1
                > 0
            )
    for a, b in product(range(18), repeat=2):
        assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_universal_tree_extension_and_witnessed_spanning_tree(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    for _sid, _record, row in vector_rows(result):
        v, u = cert.dense(row["counts"]), cert.dense(row["selected_subset_counts"])
        extension = row["tree_extension"]
        root = next(i for i, c in enumerate(u) if c)
        attachments = extension["attachment_edges"]
        assert [a["omitted_type"] for a in attachments] == row["deleted_event_types"]
        for attachment in attachments:
            assert attachment["attach_type"] == root
            pair = tuple(sorted((root, attachment["omitted_type"])))
            left, right = (cert.hunter.type_cells(i) for i in pair)
            values = [
                cert.six.residual_pair_intersection(*pair, c)
                for c in product(
                    *(
                        range(max(0, a + b - len(labels)), min(a, b) + 1)
                        for a, b, labels in zip(left, right, cert.hunter.CELL_LABELS, strict=True)
                    )
                )
                if sum(c) <= 3
            ]
            assert len(values) == attachment["legal_row_count"]
            assert min(values) == attachment["minimum_intersection"] >= 0
        assert (
            extension["subset_tree_edges"] + len(attachments) == 17 == sum(u) - 1 + sum(v) - sum(u)
        )
        witness = row["witness_analysis"]
        tree = [tuple(e) for e in witness["extended_tree"]]
        parent = list(range(18))

        def find(x: int, parent: list[int] = parent) -> int:
            while parent[x] != x:
                x = parent[x]
            return x

        for a, b in tree:
            ra, rb = find(a), find(b)
            assert ra != rb
            parent[ra] = rb
        assert len(tree) == 17 and len({find(x) for x in range(18)}) == 1
        floor = proofs(result)[row["proof_id"]]["hunter_floor"]
        assert witness["extended_tree_exact_weight"] >= witness["phi_tree_weight"] >= floor
    v = next(
        cert.dense(r["counts"])
        for _, _, r in vector_rows(result)
        if sum(cert.dense(r["selected_subset_counts"])) == 17
    )
    u = cert.ts53.select_subset(v)
    original = cert.prior.verified_pair_rows

    def negative(pair: tuple[int, int]) -> tuple[tuple[int, ...], ...]:
        rows = original(pair)
        return (*rows, (*rows[0][:6], -1))

    monkeypatch.setattr(cert.prior, "verified_pair_rows", negative)
    with pytest.raises(AssertionError, match="negative intersection"):
        cert.tree_extension_proof(v, u)


def test_max_once_credits_preserved_and_compressed_max(result: dict[str, Any]) -> None:
    for _sid, record, row in vector_rows(result):
        credits = row["corrections"]
        unc = row["uncorrected_anchor_bound"]
        assert set(credits) == {
            "R6_PAIR",
            "FOREST",
            "SEALED_MEMBER",
            "SEALED_VECTOR",
            "SUBSET_HUNTER",
        }
        assert row["combined_correction"] == max(credits.values())
        assert row["prior_applied_correction"] == max(
            v for k, v in credits.items() if k != "SUBSET_HUNTER"
        )
        assert credits["SEALED_MEMBER"] == unc - record["member_prior_bound"]
        sealed = [b for _, b in row["sealed_vector_bounds"]]
        assert row["vector_prior_bound"] == min([record["member_prior_bound"], *sealed])
        assert credits["SEALED_VECTOR"] == unc - row["vector_prior_bound"]
        assert row["vector_new_bound"] == min(
            row["vector_prior_bound"], unc - row["combined_correction"]
        )
        # SUM would subtract more than the single valid MAX correction.
        assert unc - sum(credits.values()) < row["vector_new_bound"]
        assert row["vector_new_bound"] < record["member_prior_bound"]
    compressed = 0
    for region in result["REGIONS"]:
        for record in region["member_certificates"]:
            bounds = [r["vector_new_bound"] for r in record["vector_certificates"]]
            assert record["member_new_bound"] == max(bounds)
            compressed += len(bounds) > 1
    assert compressed == 6


def test_compressed_max_non_equivalent_source_mutation(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # All actual aliases tie. Loosen one valid upper bound by one: it remains
    # safe and makes MAX->MIN non-equivalent without inventing an alias domain.
    sid = cert.STATE_12695020
    member = next(m for m in cert.target_members(sid) if m.represented_vector_count == 2)
    vectors = cert.represented_vectors(sid)[member.counts]
    record = next(
        m
        for r in result["REGIONS"]
        if r["state_id"] == sid
        for m in r["member_certificates"]
        if m["member_id"] == cert.member_id(member.counts)
    )
    rows = copy.deepcopy(record["vector_certificates"])
    assert rows[0]["vector_new_bound"] == rows[1]["vector_new_bound"]
    rows[1]["vector_new_bound"] += 1
    expected = max(int(r["vector_new_bound"]) for r in rows)
    assert expected < member.final_bound

    def safe_bound(_sid: str, _member: cert.LedgerMember, v: cert.CountVector) -> dict[str, Any]:
        return cast(dict[str, Any], rows[vectors.index(v)])

    monkeypatch.setattr(cert, "certify_vector", safe_bound)
    original = cert.certify_member
    source = inspect.getsource(original)
    operator = 'max(int(r["vector_new_bound"]) for r in rows)'
    assert source.count(operator) == 1
    namespace = dict(vars(cert))
    exec(
        compile(
            source.replace(operator, operator.replace("max(", "min(")),
            "<controlled-compressed-max-mutation>",
            "exec",
        ),
        namespace,
    )
    mutant = cast(Callable[[str, cert.LedgerMember], dict[str, Any]], namespace["certify_member"])

    def require_correct_bound(function: Callable[[str, cert.LedgerMember], dict[str, Any]]) -> None:
        assert function(sid, member)["member_new_bound"] == expected, "compressed MAX required"

    require_correct_bound(original)
    with pytest.raises(AssertionError, match="compressed MAX required"):
        require_correct_bound(mutant)
    require_correct_bound(original)


def test_untouched_remainder_family_and_witness_soundness(result: dict[str, Any]) -> None:
    preserved_members = preserved_vectors = 0
    for region in result["REGIONS"]:
        sid = region["state_id"]
        original = cert.region_members(sid)
        records = {cert.dense(r["witness_counts"]): r for r in region["member_certificates"]}
        rows = region["complete_region_members"]
        assert len(rows) == len(original)
        for member, row in zip(original, rows, strict=True):
            assert cert.dense(row["witness_counts"]) == member.counts
            assert row["prior_bound"] == member.final_bound
            if member.counts in records:
                assert row["final_bound"] == records[member.counts]["member_new_bound"]
            else:
                assert row["final_bound"] == member.final_bound
                preserved_members += 1
                preserved_vectors += member.represented_vector_count
        assert max(r["final_bound"] for r in rows) == cert.EXPECTED_STATE_BOUNDS[sid]
    assert (preserved_members, preserved_vectors) == (2854, 3092)
    states = [(r["stable_id"], r["bound"]) for r in result["FINAL_STATE_TERMS"]]
    start = dict(cert.state_terms())
    assert len(dict(states)) == len(states) == 23
    assert {k for k, b in states if b != start[k]} == set(cert.REGION_SPECS)
    classified = cert.classified_terms()
    assert len(dict(classified)) == len(classified) == 56550
    assert (
        cert.digest(classified)
        == result["CLASSIFIED_TERMS_SHA256"]
        == ("8974cda817f7f03f24bb6bd03ed6c59f1bb95ede70aa1a678fc05d99adf533d3")
    )
    assert cert.six.sealed_tail_bound() == result["TAIL_BOUND"] == 354039277
    terms = (*states, *classified, (cert.r24.TAIL_ID, result["TAIL_BOUND"]))
    assert len(terms) == result["FAMILY_TERM_COUNT"] == 56574
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355145504
    assert (
        result["FINAL_OWNER_IDS"]
        == [k for k, b in terms if b == maximum]
        == ["carried-r12-other-levels"]
    )
    assert result["RUNNER_UP"] == {"bound": runner, "owner_ids": [cert.STATE_13169800]}
    assert runner == 355142998
    assert result["START_COMPLETE_R3_UB"] - maximum == result["STRICT_GAIN"] == 89635
    assert maximum - cert.r24.INCUMBENT == result["REMAINING_GAP"] == 41881616
    carried = cert.joint.carried_supports()
    for _, _, row in vector_rows(result):
        v = cert.dense(row["counts"])
        witness = row["witness_analysis"]
        support = tuple(tuple(t) for t in witness["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(v, support)
        assert cert.digest(support) == witness["support_sha256"]
        for other in carried.get(v, ()):
            assert cert.hunter.r8.validate_support_assignment(v, other)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_alias",
        "invalid_subset",
        "wrong_pair_floor",
        "over_tight_Q",
        "sum_credit",
        "missing_State",
        "compressed_underbound",
        "untouched_bound",
    ],
)
def test_non_equivalent_semantic_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    region = bad["REGIONS"][1]
    if mutation == "missing_alias":
        member = next(m for m in region["member_certificates"] if m["represented_vector_count"] > 1)
        member["represented_vectors"].pop()
        member["vector_certificates"].pop()
        member["represented_vector_count"] -= 1
    elif mutation == "invalid_subset":
        row = region["member_certificates"][0]["vector_certificates"][0]
        row["selected_subset_counts"] = cert.sparse(
            tuple(c + int(i == 29) for i, c in enumerate(cert.dense(row["counts"])))
        )
    elif mutation == "wrong_pair_floor":
        bad["SUBSET_PROOFS"][0]["pair_floors"][0] += 1
    elif mutation == "over_tight_Q":
        bad["SUBSET_PROOFS"][0]["collision_mass_floor"] += 1
    elif mutation == "sum_credit":
        row = region["member_certificates"][0]["vector_certificates"][0]
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "missing_State":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "compressed_underbound":
        member = next(
            m for m in region["member_certificates"] if m["represented_vector_count"] == 2
        )
        member["member_new_bound"] -= 1
    else:
        row = next(
            r for r in region["complete_region_members"] if r["final_bound"] == r["prior_bound"]
        )
        row["final_bound"] -= 1
    assert cert.encode(bad) != cert.encode(result)
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


def test_live_missing_alias_sum_credit_illegal_subset_and_missing_state(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = cert.STATE_12695020
    recovered = dict(cert.represented_vectors(sid))
    member = next(m for m in cert.target_members(sid) if m.represented_vector_count == 2)
    recovered[member.counts] = recovered[member.counts][:1]
    original = cert.represented_vectors

    def incomplete(s: str) -> dict[cert.CountVector, tuple[cert.CountVector, ...]]:
        return recovered if s == sid else original(s)

    with monkeypatch.context() as patch:
        patch.setattr(cert, "represented_vectors", incomplete)
        with pytest.raises(AssertionError, match="alias coverage"):
            cert.target_members(sid)

    def sum_credits(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "combine_corrections", sum_credits)
        with pytest.raises(AssertionError, match="MAX-only"):
            cert.certify_vector(sid, member, original(sid)[member.counts][0])
    v = member.counts
    for u in (
        tuple(c + int(i == 29) for i, c in enumerate(v)),
        tuple(c - int(i == 0) * 2 for i, c in enumerate(v)),
    ):
        with pytest.raises(AssertionError, match="selected subset"):
            cert.ts53.validate_subset(v, u)
    terms = cert.state_terms()[:-1]
    with monkeypatch.context() as patch:
        patch.setattr(cert, "state_terms", lambda: terms)
        with pytest.raises(AssertionError, match="23-State"):
            cert.recompute_family(result["REGIONS"])


def test_executing_source_tampering_rejected_after_warm_caches(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert result["SOURCE_AUTHORITY_STATUS"].startswith("PASS")
    original = Path.read_bytes
    target = Path(cert.joint.__file__).resolve()

    def tampered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n# tampered\n" if path.resolve() == target else data

    monkeypatch.setattr(Path, "read_bytes", tampered)
    with pytest.raises(AssertionError, match="immutable donor source"):
        cert.verify_source_authority()


def test_stored_byte_exact_fresh_equivalent_replay(result: dict[str, Any]) -> None:
    stored = cert.RESULT_PATH.read_bytes()
    assert stored == cert.encode(result).encode()
    status = cert.verify_stored_result()
    assert status == {
        "status": "PASS",
        "members": 153,
        "vectors": 159,
        "state_terms": 23,
        "classified_terms": 56550,
        "complete_r3": 355145504,
    }
    assert cert.verify_result(cast(dict[str, Any], json.loads(stored)))["vectors"] == 159
