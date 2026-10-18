"""Independent arithmetic, complete ledger coverage, and falsifiable proof guards."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations, pairwise, product
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_state_13548976_fifty_three_subset_hunter_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor rebuild, census, solver, or chase")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module in (cert.h11, cert.prior, cert.prior.h0):
            patch.setattr(module, "build_result", forbidden)
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def test_exact_base_and_sealed_predecessors(result: dict[str, Any]) -> None:
    assert result["BASE_HEAD"] == "f8bb2f27e0c02af819588c0f923a5f883b0f9a0d"
    assert result["BASE_TREE"] == "810dffc9f83b5bbc4bf0fbe023c504e75bc152c8"
    assert sha256(cert.h11.RESULT_PATH.read_bytes()).hexdigest() == cert.BASE_RESULT_SHA256
    assert (
        cert.BASE_RESULT_SHA256
        == "31f1b558447ed4b630f55bc49e7955bb395f4eff3a19d41da5041acfad045816"
    )
    assert result["SOURCE_AUTHORITY"] == cert.verify_source_authority()
    assert (
        result["REGION_SHA256"]
        == "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
    )
    for path, expected in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == expected
    assert all(
        module.RESULT_RELATIVE in result["ALL_CARRIED_CERTIFICATES_SHA256"]
        for module in (cert.h11, cert.prior, cert.prior.h0)
    )


def test_all_1427_members_1543_vectors_and_signatures(result: dict[str, Any]) -> None:
    members, recovered = cert.region_members(), cert.represented_vectors()
    assert len(members) == len(recovered) == result["REGION_MEMBER_COVERAGE"] == 1427
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(flat) == len(set(flat)) == result["REGION_VECTOR_COVERAGE"] == 1543
    for member, row in zip(members, cert.region_rows(), strict=True):
        signature = cert.hunter.eleven.compression_signature(cert.catalog.rebuild_member(member))
        vectors = recovered[member.counts]
        assert len(vectors) == member.represented_vector_count
        assert vectors == tuple(sorted(vectors)) and min(vectors) == member.counts
        assert row["member_id"] == cert.member_id(member.counts)
        assert row["compression_signature"] == cert.catalog.normalized(signature)
        assert row["represented_vectors"] == [cert.sparse(v) for v in vectors]
        for v in vectors:
            state = cert.catalog.rebuild_member(
                replace(member, counts=v, represented_vector_count=1)
            )
            assert len(v) == 30 and sum(v) == 18 and min(v) >= 0
            assert cert.hunter.eleven.compression_signature(state) == signature
            assert cert.hunter.r14.raw_bound(state) == member.raw_bound


def test_targets_automatically_recovered_including_all_top_twelve(result: dict[str, Any]) -> None:
    members = cert.region_members()
    targets = cert.target_members(members)
    selected = {m.counts for m in targets}
    assert selected == {m.counts for m in members if m.final_bound > 355145504}
    assert len(targets) == result["TARGET_MEMBER_COUNT"] == result["TARGET_VECTOR_COUNT"] == 53
    assert all(m.represented_vector_count == 1 for m in targets)
    top12 = sorted(members, key=lambda m: (-m.final_bound, m.counts))[:12]
    assert {m.counts for m in top12} <= selected
    assert result["TOP_TWELVE_MEMBER_IDS"] == [cert.member_id(m.counts) for m in top12]
    assert len(selected - {m.counts for m in top12}) == 41
    assert [r["member_id"] for r in result["MEMBER_CERTIFICATES"]] == [
        cert.member_id(m.counts) for m in targets
    ]
    for bad in (
        tuple(m for m in members if m != targets[0]),
        tuple(replace(m, represented_vector_count=2) if m == targets[0] else m for m in members),
    ):
        with pytest.raises(AssertionError, match="53-member"):
            cert.target_members(bad)


@cache
def independent_minimum(phi: cert.Cells, q: int, n: int) -> tuple[int, tuple[int, int, int], int]:
    capacity = comb(n, 2)
    ranks = [next(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1)]
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = 0
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < q:
                    continue
                value = (n - 1) * phi[0] + sum(
                    (phi[k + 1] - phi[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                )
                candidate = value, (e1, e2, e3)
                best = candidate if best is None else min(best, candidate)
                cases += 1
    assert best is not None
    return *best, cases


def test_complete_pair_rows_four_cell_collision_and_threshold_minima(
    result: dict[str, Any],
) -> None:
    checked: set[tuple[int, int]] = set()
    for proof in result["SUBSET_PROOFS"]:
        u = cert.dense(proof["selected_subset_counts"])
        assert sum(u) == proof["event_count"] and sum(u) in (17, 18)
        assert proof["proof_id"] == cert.digest(u)
        pairs = cert.six.occupied_type_pairs(u)
        rows = proof["pair_rows"]
        assert proof["occupied_type_pairs"] == [list(p) for p in sorted(pairs)]
        for pair in pairs:
            if pair in checked:
                continue
            checked.add(pair)
            left, right = (cert.hunter.type_cells(t) for t in pair)
            expected = {
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
            assert len(actual) == len(expected) and {tuple(r[2:6]) for r in actual} == expected
            for row in actual:
                cells = cast(cert.Cells, tuple(row[2:6]))
                tickets = cert.hunter.realize_pair(left, right, cells)
                assert (
                    tuple(
                        len(tickets[0] & tickets[1] & set(labels))
                        for labels in cert.hunter.CELL_LABELS
                    )
                    == cells
                )
                assert (
                    cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B))
                    == row[6]
                )
                assert cert.six.residual_pair_intersection(*pair, cells) == row[6] >= 0
        phi = cast(cert.Cells, tuple(min(r[6] for r in rows if sum(r[2:6]) == k) for k in range(4)))
        assert list(phi) == proof["pair_floors"]
        assert all(a <= b for a, b in pairwise(phi))
        inc = [sum(c * cert.hunter.type_cells(i)[k] for i, c in enumerate(u)) for k in range(4)]
        floors = [
            (len(labels) - r) * comb(q, 2) + r * comb(q + 1, 2)
            for total, labels in zip(inc, cert.hunter.CELL_LABELS, strict=True)
            for q, r in [divmod(total, len(labels))]
        ]
        assert proof["cell_incidences"] == inc
        assert proof["cell_collision_floors"] == floors
        assert proof["collision_mass_floor"] == sum(floors)
        minimum, minimizer, cases = independent_minimum(phi, sum(floors), sum(u))
        assert proof["hunter_floor"] == minimum
        assert proof["integer_minimizer"]["edge_counts"] == list(minimizer)
        assert proof["integer_minimizer"]["rank_floors"] == [
            next(r for r in range(sum(u)) if comb(r + 1, 2) >= e) for e in minimizer
        ]
        assert (
            proof["all_admissible_threshold_cases"] == sum(proof["admissible_case_counts"]) == cases
        )


def test_universal_balancing_rank_kruskal_and_pointwise_hunter() -> None:
    for high in range(2, 19):
        for low in range(high - 1):
            assert (
                comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
                == high - low - 1
                > 0
            )
    for a, b in product(range(18), repeat=2):
        assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    for degrees in product(range(7), repeat=3):
        q, r = divmod(sum(degrees), 3)
        assert sum(comb(d, 2) for d in degrees) >= (3 - r) * comb(q, 2) + r * comb(q + 1, 2)
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_all_53_subsets_credits_witnesses_and_nonnegative_extensions(
    result: dict[str, Any],
) -> None:
    proofs = {p["proof_id"]: p for p in result["SUBSET_PROOFS"]}
    subset_sizes: set[int] = set()
    for record in result["MEMBER_CERTIFICATES"]:
        vector_bounds: list[int] = []
        for row in record["vector_certificates"]:
            v, u = cert.dense(row["counts"]), cert.dense(row["selected_subset_counts"])
            cert.validate_subset(v, u)
            subset_sizes.add(sum(u))
            candidates = cert.subset_candidates(v)
            assert len(candidates) == 1 + sum(c > 0 for c in v)
            assert [r["counts"] for r in row["candidate_subsets"]] == [
                cert.sparse(c) for c in candidates
            ]
            assert u in candidates
            proof = proofs[row["proof_id"]]
            assert proof["hunter_floor"] == max(
                r["rank_relaxation_floor"] for r in row["candidate_subsets"]
            )
            credits = row["corrections"]
            existing = max(c for name, c in credits.items() if name != "SUBSET_HUNTER")
            assert (
                existing
                == row["prior_applied_correction"]
                == row["uncorrected_anchor_bound"] - row["vector_prior_bound"]
            )
            assert (
                row["existing_applied_credit"]
                == row["uncorrected_anchor_bound"] - record["member_prior_bound"]
            )
            assert credits["SUBSET_HUNTER"] == proof["hunter_floor"]
            assert row["combined_correction"] == max(credits.values()) != sum(credits.values())
            bound = min(
                row["vector_prior_bound"],
                row["uncorrected_anchor_bound"] - row["combined_correction"],
            )
            assert bound == row["vector_new_bound"] < record["member_prior_bound"]
            assert (
                row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
            )
            state = cert.catalog.rebuild_member(
                cert.LedgerMember(v, 1, record["member_raw_bound"], record["member_prior_bound"])
            )
            assert row["compression_signature"] == cert.catalog.normalized(
                cert.hunter.eleven.compression_signature(state)
            )
            earlier = cert.sealed_vector_bounds().get(v, ())
            assert all(bound <= b for b in earlier)
            witness = row["witness_analysis"]
            support = tuple(tuple(int(x) for x in t) for t in witness["support_witness"])
            assert cert.hunter.r8.validate_support_assignment(v, support)
            assert cert.digest(support) == witness["support_sha256"]
            types = tuple(i for i, c in enumerate(v) for _ in range(c))
            indices = cast(list[int], witness["selected_event_indices"])
            assert len(indices) == len(set(indices)) == sum(u)
            assert (
                [types[j] for j in indices]
                == witness["selected_event_types"]
                == [i for i, c in enumerate(u) for _ in range(c)]
            )
            selected = tuple(frozenset(support[j]) for j in indices)
            mass = [
                sum(comb(sum(x in t for t in selected), 2) for x in cell)
                for cell in cert.hunter.CELL_LABELS
            ]
            assert mass == witness["cell_collision_mass"]
            assert (
                sum(mass)
                == witness["collision_mass"]
                == sum(len(a & b) for a, b in combinations(selected, 2))
            )
            assert all(a >= b for a, b in zip(mass, proof["cell_collision_floors"], strict=True))
            subtree = cast(list[tuple[int, int]], witness["subset_tree"])
            tree = cast(list[tuple[int, int]], witness["extended_tree"])
            assert len(subtree) == cert.hunter.graph_rank(sum(u), subtree) == sum(u) - 1
            assert len(tree) == cert.hunter.graph_rank(18, tree) == 17
            weight = 0
            for a, b in tree:
                cells = cast(
                    cert.Cells,
                    tuple(
                        len(set(support[a]) & set(support[b]) & set(cell))
                        for cell in cert.hunter.CELL_LABELS
                    ),
                )
                cost = cert.six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
                assert cost >= 0
                weight += cost
            assert (
                weight
                == witness["extended_tree_exact_weight"]
                >= witness["phi_tree_weight"]
                >= proof["hunter_floor"]
            )
            for predecessor in cert.prior.sealed_vector_rows().get(v, ()):
                tickets = tuple(tuple(int(x) for x in t) for t in predecessor["support_witness"])
                assert cert.hunter.r8.validate_support_assignment(v, tickets)
            vector_bounds.append(bound)
        assert record["member_new_bound"] == max(vector_bounds)
        assert record["member_certified_correction"] == min(
            r["combined_correction"] for r in record["vector_certificates"]
        )
    assert subset_sizes == {17, 18}


def test_all_untouched_members_and_complete_standalone_family(result: dict[str, Any]) -> None:
    targets = {r["member_id"] for r in result["MEMBER_CERTIFICATES"]}
    remainder: list[dict[str, Any]] = []
    for old, new in zip(cert.region_rows(), result["COMPLETE_REGION_MEMBERS"], strict=True):
        assert new["prior_bound"] == old["final_bound"]
        assert {k: new[k] for k in old if k not in ("prior_bound", "final_bound")} == {
            k: old[k] for k in old if k not in ("prior_bound", "final_bound")
        }
        if old["member_id"] not in targets:
            assert old["final_bound"] == new["final_bound"]
            remainder.append(new)
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 1374
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1490
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355116818
    )
    assert result["PRESERVED_REMAINDER_SHA256"] == cert.digest(
        tuple((cert.dense(r["witness_counts"]), r["final_bound"]) for r in remainder)
    )
    assert (
        result["NEW_TARGET_COHORT_MAX"]
        == max(r["member_new_bound"] for r in result["MEMBER_CERTIFICATES"])
        == 353607184
    )
    source = cert.source_results()["H11"]
    before = {r["stable_id"]: r["bound"] for r in source["FINAL_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == 23
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_STATE_BOUND"] == 355269698
    assert after[cert.TARGET_STATE_ID] == result["FINAL_TARGET_STATE_UB"] == 355116818
    for k in ("CLASSIFIED_MAX", "CLASSIFIED_TERM_COUNT", "CLASSIFIED_TERMS_SHA256", "TAIL_BOUND"):
        assert result[k] == source[k]
    assert result["CLASSIFIED_MAX"] == 355145504 and result["TAIL_BOUND"] == 354039277
    assert (
        result["START_COMPLETE_R3_UB"]
        == result["FINAL_STANDALONE_COMPLETE_R3_UB"]
        == max(*after.values(), result["CLASSIFIED_MAX"], result["TAIL_BOUND"])
        == 355274472
    )
    assert result["FINAL_OWNER"] == ["state:s2-12692531-s3-681744"]
    assert result["REMAINING_GAP"] == 355274472 - 313263888 == 42010584


MUTATIONS = (
    "base",
    "pair",
    "missing_pair",
    "pair_floor",
    "collision",
    "threshold",
    "minimizer",
    "case_count",
    "oversized_subset",
    "short_subset",
    "subset_id",
    "signature",
    "missing_member",
    "duplicate_member",
    "missing_vector",
    "missing_vector_row",
    "sum_credit",
    "double_subtraction",
    "witness",
    "extension",
    "prior_credit",
    "remainder",
    "remainder_digest",
    "region_vector",
    "state",
    "owner",
    "tail",
    "classified",
    "numeric_type",
    "candidate",
)


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_semantic_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["SUBSET_PROOFS"][0]
    record = bad["MEMBER_CERTIFICATES"][0]
    row = record["vector_certificates"][0]
    if mutation == "base":
        bad["BASE_TREE"] = "0" * 40
    elif mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "missing_pair":
        proof["pair_rows"].pop()
    elif mutation == "pair_floor":
        proof["pair_floors"][0] += 1
    elif mutation == "collision":
        proof["cell_collision_floors"][3] += 1
    elif mutation == "threshold":
        proof["hunter_floor"] += 1
    elif mutation == "minimizer":
        proof["integer_minimizer"]["rank_floors"][0] -= 1
    elif mutation == "case_count":
        proof["all_admissible_threshold_cases"] -= 1
    elif mutation == "oversized_subset":
        row["selected_subset_counts"] = [[0, 19]]
    elif mutation == "short_subset":
        row["selected_subset_counts"] = [[0, 16]]
    elif mutation == "subset_id":
        row["proof_id"] = "0" * 64
    elif mutation == "signature":
        row["compression_signature"][0] += 1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(record))
    elif mutation == "missing_vector":
        record["represented_vectors"].pop()
    elif mutation == "missing_vector_row":
        record["vector_certificates"].pop()
    elif mutation == "sum_credit":
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "double_subtraction":
        row["vector_new_bound"] -= row["prior_applied_correction"]
    elif mutation == "witness":
        row["witness_analysis"]["support_witness"][0][0] = 99
    elif mutation == "extension":
        row["witness_analysis"]["extended_tree"].pop()
    elif mutation == "prior_credit":
        row["existing_applied_credit"] += 1
    elif mutation == "remainder":
        next(
            r
            for r in bad["COMPLETE_REGION_MEMBERS"]
            if r["member_id"] not in {m["member_id"] for m in bad["MEMBER_CERTIFICATES"]}
        )["final_bound"] -= 1
    elif mutation == "remainder_digest":
        bad["PRESERVED_REMAINDER_SHA256"] = "0" * 64
    elif mutation == "region_vector":
        bad["COMPLETE_REGION_MEMBERS"][-1]["represented_vectors"].pop()
    elif mutation == "state":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER"] = [cert.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "classified":
        bad["CLASSIFIED_MAX"] -= 1
    elif mutation == "numeric_type":
        bad["NEW_TARGET_COHORT_MAX"] = float(bad["NEW_TARGET_COHORT_MAX"])
    else:
        row["candidate_subsets"].pop()
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "relative",
    (
        cert.h11.RESULT_RELATIVE,
        cert.prior.RESULT_RELATIVE,
        cert.prior.h0.RESULT_RELATIVE,
        "src/lottolab/research/b649_k20_r3_three_state_ts_106_member_certificate_r1.py",
        "src/lottolab/research/b649_k20_r3_preserved_eleven_hunter_certificate_r1.py",
    ),
)
def test_source_tamper_rejected_with_warm_caches(
    relative: str, monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    read = Path.read_bytes

    def tamper(path: Path) -> bytes:
        data = read(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="immutable executing source or sealed input"):
        cert.build_result()
    assert result["TASK_STATUS"] == "SUCCESS"


def test_live_additive_credit_mutation_rejected(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    def additive(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "combine_corrections", additive)
        with pytest.raises(AssertionError, match="MAX-only"):
            cert.build_result()
    assert cert.build_result() == result


def test_live_illegal_subset_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    member = cert.target_members(cert.region_members())[0]

    def invalid(_v: cert.CountVector) -> cert.CountVector:
        return (19, *(0 for _ in range(29)))

    with monkeypatch.context() as patch:
        patch.setattr(cert.prior, "select_subset", invalid)
        with pytest.raises(AssertionError, match="0<=u<=v"):
            cert.certify_vector(member, member.counts)
    assert cert.certify_vector(member, member.counts)["vector_new_bound"] < member.final_bound


def test_live_missing_vector_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    recover = cert.catalog.r17.represented_vectors

    def omit(members: Any) -> dict[cert.CountVector, tuple[cert.CountVector, ...]]:
        found = dict(recover(members))
        found.pop(next(iter(found)))
        return found

    cert.represented_vectors.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(cert.catalog.r17, "represented_vectors", omit)
            with pytest.raises(AssertionError, match="represented-vector"):
                cert.represented_vectors()
    finally:
        cert.represented_vectors.cache_clear()
    assert sum(map(len, cert.represented_vectors().values())) == 1543


def test_live_wrong_pair_floor_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    v = cert.target_members(cert.region_members())[0].counts
    u = cert.select_subset(v)
    original = cert.prior.pair_rows

    def corrupt(selected: cert.CountVector) -> tuple[cert.prior.PairRow, ...]:
        rows = list(original(selected))
        rows[0] = (*rows[0][:6], rows[0][6] + 1)
        return tuple(rows)

    cert.subset_proof.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(cert.prior, "pair_rows", corrupt)
            with pytest.raises(AssertionError, match="exact residual type-pair"):
                cert.subset_proof(u)
    finally:
        cert.subset_proof.cache_clear()
    assert cert.subset_proof(u)["hunter_floor"] > 0


def test_live_negative_tree_extension_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    v = cert.target_members(cert.region_members())[0].counts
    u = cert.select_subset(v)
    proof = cert.subset_proof(u)

    def negative(*_args: object) -> int:
        return -1

    with monkeypatch.context() as patch:
        patch.setattr(cert.six, "residual_pair_intersection", negative)
        with pytest.raises(AssertionError, match="negative residual intersection"):
            cert.prior.witness_analysis(v, u, proof)
    assert (
        cert.prior.witness_analysis(v, u, proof)["extended_tree_exact_weight"]
        >= proof["hunter_floor"]
    )


@pytest.mark.parametrize(
    "u",
    (
        (-1, *(0 for _ in range(29))),
        (16, *(0 for _ in range(29))),
        (19, *(0 for _ in range(29))),
        (True, *(0 for _ in range(29))),
        (18,),
    ),
)
def test_invalid_subset_shapes_rejected(u: cert.CountVector) -> None:
    with pytest.raises(AssertionError, match="17/18"):
        cert.validate_subset((18, *(0 for _ in range(29))), u)


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 53,
        "vectors": 53,
        "region_members": 1427,
        "region_vectors": 1543,
        "state_terms": 23,
    }
    assert json.loads(cert.RESULT_PATH.read_bytes()) == result
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
