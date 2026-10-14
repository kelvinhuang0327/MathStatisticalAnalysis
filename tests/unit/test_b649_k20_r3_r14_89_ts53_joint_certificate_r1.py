"""Focused independent coverage, arithmetic and non-equivalent mutation guards."""

from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Callable, Mapping
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_r14_89_ts53_joint_certificate_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor rebuild, census, heavy solver or chase")


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


def vector(values: dict[int, int]) -> cert.CountVector:
    return tuple(values.get(i, 0) for i in range(30))


def test_exact_authorities_and_three_donor_blobs(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert result["SOURCE_AUTHORITY"] == authority
    assert authority["objects"]["PRIMARY"] == {
        "HEAD": "f8bb2f27e0c02af819588c0f923a5f883b0f9a0d",
        "TREE": "810dffc9f83b5bbc4bf0fbe023c504e75bc152c8",
        "RESULT_SHA256": "31f1b558447ed4b630f55bc49e7955bb395f4eff3a19d41da5041acfad045816",
    }
    assert authority["objects"]["TS53_DONOR"]["TREE"] == "ac60557c255a88e933502c8ed2ded6d84062752e"
    assert (
        authority["objects"]["R14_RESEARCH"]["TREE"] == "25174405e76eb4350eb045a0c02c4f04901b776e"
    )
    for relative, blob_id in authority["donor_blob_ids"].items():
        local = (cert.REPO_ROOT / relative).read_bytes()
        assert local == cert.git_bytes("show", f"{cert.DONOR_HEAD}:{relative}")
        assert sha256(local).hexdigest() == sha256(cert.git_bytes("show", blob_id)).hexdigest()
    assert len(authority["donor_blob_ids"]) == 3
    assert cert.source_results()["TS53"]["FINAL_STANDALONE_COMPLETE_R3_UB"] == 355274472
    assert result["TS53_CERTIFICATE_SHA256"] == cert.DONOR_RESULT_SHA256


def test_parameter_identity_and_all_ten_aliases(result: dict[str, Any]) -> None:
    a: set[cert.CountVector] = set()
    for k in range(5):
        for pattern in (
            {4: 2, 8: 1},
            {2: 1, 4: 2},
            {1: 1, 4: 1, 8: 1},
            {1: 1, 2: 1, 4: 1},
            {1: 2, 2: 1},
            {1: 2, 8: 1},
        ):
            a.add(vector({0: 11, 5: 4 - k, 16: k, **pattern}))
    b = {
        vector({0: 9, 1: j, 4: 5 - j, 5: 3 - k, 16: k, e: 1})
        for k, j, e in product(range(4), range(6), (6, 9))
    }
    c = {vector({0: 10, 1: j, 4: 6 - j, 17: n, 19: 2 - n}) for j, n in product(range(7), range(3))}
    assert len(a) == 30 and len(b) == 48 and len(c) == 21
    assert set(cert.target_parameters(cert.STATE_A)) == a
    assert set(cert.target_parameters(cert.STATE_B)) == b | c
    assert not a.intersection(b | c)
    alias_count = 0
    for sid, expected in ((cert.STATE_A, a), (cert.STATE_B, b | c)):
        targets, recovered = cert.target_members(sid), cert.represented_vectors(sid)
        assert {v for m in targets for v in recovered[m.counts]} == expected
        grouped: dict[str, list[cert.CountVector]] = {}
        for v in sorted(expected):
            member = next(m for m in targets if v in recovered[m.counts])
            state = cert.catalog.rebuild_member(
                cert.replace(member, counts=v, represented_vector_count=1)
            )
            key = repr(cert.hunter.eleven.compression_signature(state))
            grouped.setdefault(key, []).append(v)
        assert len(grouped) == cert.REGION_SPECS[sid][2]
        aliases = tuple(sorted(tuple(vs) for vs in grouped.values() if len(vs) > 1))
        assert aliases == cert.expected_aliases(sid)
        alias_count += len(aliases)
    assert alias_count == 10
    assert result["R14_89_MEMBER_COVERAGE"] == 89
    assert result["R14_99_VECTOR_COVERAGE"] == 99
    adopted = {
        cert.dense(r["witness_counts"]) for r in cert.source_results()["H11"]["MEMBER_CERTIFICATES"]
    }
    assert len(adopted) == 5
    targets_a = cert.target_members(cert.STATE_A)
    assert adopted <= {m.counts for m in targets_a}
    # The forbidden cutoff would lose precisely these five canonical targets.
    assert {m.counts for m in targets_a if m.final_bound <= 355269698} == adopted


def test_complete_regions_and_preserved_bounds(result: dict[str, Any]) -> None:
    for region in result["REGIONS"]:
        sid = region["state_id"]
        members, vectors = cert.region_members(sid), cert.represented_vectors(sid)
        mc, vc, tc, tv = cert.REGION_SPECS[sid]
        assert len(members) == len(vectors) == mc
        assert len({v for vs in vectors.values() for v in vs}) == vc
        assert len(region["member_certificates"]) == tc
        assert region["target_vector_count"] == tv
        selected = {cert.dense(r["witness_counts"]) for r in region["member_certificates"]}
        preserved = tuple(m for m in members if m.counts not in selected)
        assert len(preserved) == region["preserved_member_count"] == mc - tc
        assert sum(len(vectors[m.counts]) for m in preserved) == vc - tv
        rows = {cert.dense(r["witness_counts"]): r for r in region["complete_region_members"]}
        assert set(rows) == {m.counts for m in members}
        assert all(rows[m.counts]["final_bound"] == m.final_bound for m in preserved)
        assert (
            cert.digest(tuple((m.counts, m.final_bound) for m in preserved))
            == region["preserved_bounds_sha256"]
        )
        assert max(r["final_bound"] for r in rows.values()) == region["new_state_bound"]
    ts = cert.source_results()["TS53"]
    assert ts["REGION_MEMBER_COVERAGE"] == 1427 and ts["REGION_VECTOR_COVERAGE"] == 1543
    assert ts["NEW_TARGET_COHORT_MAX"] == 353607184
    assert ts["PRESERVED_MEMBER_COUNT"] == 1374 and ts["PRESERVED_VECTOR_COUNT"] == 1490
    assert result["TS53_TARGET_MEMBER_IDS"] == [r["member_id"] for r in ts["MEMBER_CERTIFICATES"]]
    assert result["TS53_UPDATED_REGION_SHA256"] == ts["COMPLETE_UPDATED_BOUNDS_SHA256"]


def test_all_264_legal_pair_rows_and_mixed_floors(result: dict[str, Any]) -> None:
    proof = result["R14_PROOF"]
    rows = cert.exact_pair_rows()
    expected_pairs: set[cert.Pair] = set()
    for sid in cert.REGION_SPECS:
        for v in cert.target_parameters(sid):
            types = [i for i, count in enumerate(v) for _ in range(count)]
            expected_pairs.update((min(a, b), max(a, b)) for a, b in combinations(types, 2))
    assert len(expected_pairs) == len(proof["occupied_type_pairs"]) == 44
    assert {tuple(p) for p in proof["occupied_type_pairs"]} == expected_pairs
    assert len(rows) == len(proof["pair_rows"]) == 264
    for pair in sorted(expected_pairs):
        cells_l, cells_r = (cert.hunter.type_cells(i) for i in pair)
        legal = {
            overlap
            for overlap in product(
                *(
                    range(max(0, a + b - len(labels)), min(a, b) + 1)
                    for a, b, labels in zip(cells_l, cells_r, cert.hunter.CELL_LABELS, strict=True)
                )
            )
            if sum(overlap) <= 3
        }
        actual = [r for r in rows if r[:2] == pair]
        assert len(actual) == len(legal) and {r[2:6] for r in actual} == legal
        for row in actual:
            cells = row[2:6]
            assert row[6] == cert.six.residual_pair_intersection(*pair, cells)
            left, right = cert.hunter.realize_pair(cells_l, cells_r, cells)
            # Direct E_left E_right minus anchors checks every exact residual row.
            assert row[6] == (
                cert.hunter.outcome_count((left, right))
                - cert.hunter.outcome_count((left, right, cert.hunter.ANCHOR_A))
                - cert.hunter.outcome_count((left, right, cert.hunter.ANCHOR_B))
                + cert.hunter.outcome_count(
                    (left, right, cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
                )
            )
        floor, slope = cert.pair_floors()[pair]
        assert floor == min(r[6] for r in actual)
        assert slope == min(Fraction(r[6] - floor, r[5]) for r in actual if r[5])
        assert all(Fraction(r[6]) >= floor + slope * r[5] for r in actual)
    type0_floor, type0_slope = cert.pair_floors()[0, 0]
    unsafe = [
        p
        for p in expected_pairs
        if any(r[6] < type0_floor + type0_slope * r[5] for r in rows if r[:2] == p)
    ]
    assert unsafe
    for pair in unsafe:
        with pytest.raises(AssertionError, match="unsafe type-specific"):
            cert.require_safe_pair_floor(pair, type0_floor, type0_slope, rows)


def test_independent_99_vector_moments_exact_ceiling_and_cap18(result: dict[str, Any]) -> None:
    proof = result["R14_PROOF"]
    floors: list[int] = []
    for record in proof["vector_moments"]:
        v = cert.dense(record["counts"])
        n = [i for i, c in enumerate(v) for _ in range(c)]
        pairs = [(min(a, b), max(a, b)) for a, b in combinations(n, 2)]
        minimum = sum(cert.pair_floors()[p][0] for p in pairs)
        slope = min(cert.pair_floors()[p][1] for p in pairs)
        total = sum(cert.hunter.type_cells(i)[3] for i in n)
        degrees = [total // 40 + int(i < total % 40) for i in range(40)]
        mass = sum(comb(d, 2) for d in degrees)
        exact = minimum + (slope.numerator * mass + slope.denominator - 1) // slope.denominator
        assert exact == record["residual_s2_floor"]
        assert record["outside_collision_floor"] == mass
        floors.append(exact)
    assert len(floors) == 99 and min(floors) == 44130478
    assert proof["correction_floor"] == (min(floors) + 8) // 9 == 4903387
    for m in range(19):
        assert comb(m, 2) <= 9 * max(m - 1, 0)
    assert Fraction(2, 17) * comb(18, 2) > 17
    with pytest.raises(AssertionError, match="cap17"):
        cert.multiplicity_proof(17)
    for n in (0, 1, 8, 9, 10, 44130478, 10**100 + 1):
        assert cert.ceiling(n, 9) == (n + 8) // 9
    for n, d in ((-1, 9), (1, 0), (1, -9)):
        with pytest.raises(ValueError):
            cert.ceiling(n, d)


def test_each_vector_credit_and_compressed_max_and_witnesses(result: dict[str, Any]) -> None:
    for region in result["REGIONS"]:
        for member in region["member_certificates"]:
            rows = member["vector_certificates"]
            assert len(rows) == member["represented_vector_count"]
            for row in rows:
                credits = row["corrections"]
                v = cert.dense(row["counts"])
                assert row["new_credit"] == max(credits.values())
                assert row["new_credit"] == max(row["current_credit"], 4903387)
                assert row["current_credit"] == row["uncorrected_bound"] - row["vector_prior_bound"]
                assert row["vector_new_bound"] == min(
                    row["vector_prior_bound"], row["uncorrected_bound"] - row["new_credit"]
                )
                support = tuple(tuple(t) for t in row["support_witness"])
                assert cert.hunter.r8.validate_support_assignment(v, support)
                assert cert.digest(support) == row["support_sha256"]
                for carried in cert.carried_supports().get(v, ()):
                    assert cert.hunter.r8.validate_support_assignment(v, carried)
            assert member["member_new_bound"] == max(r["vector_new_bound"] for r in rows)
            assert member["member_new_bound"] <= member["member_prior_bound"]


def test_stronger_vector_credit_retained_and_non_equivalent_compressed_max(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert result["R14_99_VECTOR_COVERAGE"] == 99
    sid = cert.STATE_A
    member = next(m for m in cert.target_members(sid) if m.represented_vector_count == 2)
    vectors = cert.represented_vectors(sid)[member.counts]
    sealed = dict(cert.ts53.sealed_vector_bounds())
    # Controlled seam models a future stronger certificate on just one alias.
    stronger = member.final_bound - 10000000
    sealed[vectors[0]] = (*sealed.get(vectors[0], ()), stronger)
    monkeypatch.setattr(cert.ts53, "sealed_vector_bounds", lambda: sealed)
    rows = [cert.certify_vector(member, v) for v in vectors]
    assert rows[0]["vector_new_bound"] == stronger
    assert rows[0]["new_credit"] == rows[0]["current_credit"] > 4903387
    assert rows[1]["vector_new_bound"] > stronger
    assert (
        cert.certify_member(sid, member, vectors)["member_new_bound"] == rows[1]["vector_new_bound"]
    )

    def fixture_vector(_member: cert.LedgerMember, v: cert.CountVector) -> dict[str, Any]:
        return rows[vectors.index(v)]

    monkeypatch.setattr(cert, "certify_vector", fixture_vector)
    # Mutate only this aggregation call in an isolated in-memory function;
    # target identity and all other MAX operations keep their real semantics.
    source = inspect.getsource(cert.certify_member)
    operator = 'max(r["vector_new_bound"] for r in rows)'
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
    mutant = cast(
        Callable[[str, cert.LedgerMember, tuple[cert.CountVector, ...]], dict[str, Any]],
        namespace["certify_member"],
    )
    with pytest.raises(AssertionError):
        assert mutant(sid, member, vectors)["member_new_bound"] == rows[1]["vector_new_bound"]
    assert (
        cert.certify_member(sid, member, vectors)["member_new_bound"] == rows[1]["vector_new_bound"]
    )


def test_full_family_all_23_states_classified_and_tail(result: dict[str, Any]) -> None:
    states = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    start = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    assert len(states) == len(start) == 23
    assert {k for k in states if states[k] != start[k]} == set(cert.REGION_SPECS)
    assert states[cert.STATE_A] == 355235139 and states[cert.STATE_B] == 355243700
    assert states[cert.ts53.TARGET_STATE_ID] == 355116818
    assert states["state:s2-12695020-s3-735532"] == 355243049
    classified = [
        (r["stable_id"], r["bound"])
        for r in cert.prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    ]
    assert len(classified) == len(dict(classified)) == result["CLASSIFIED_TERM_COUNT"] == 56550
    assert cert.digest(tuple(classified)) == result["CLASSIFIED_TERMS_SHA256"]
    assert max(b for _, b in classified) == result["CLASSIFIED_MAX"] == 355145504
    tail = cert.six.sealed_tail_bound()
    assert tail == result["TAIL_BOUND"] == 354039277
    terms = [*states.items(), *classified, (cert.r24.TAIL_ID, tail)]
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355243700
    assert result["FINAL_OWNER_IDS"] == [k for k, b in terms if b == maximum] == [cert.STATE_B]
    assert result["RUNNER_UP"] == {
        "bound": runner,
        "owner_ids": [k for k, b in terms if b == runner],
    }
    assert runner == 355243049
    assert result["START_COMPLETE_R3_UB"] - maximum == result["STRICT_GAIN"] == 30772
    assert maximum - cert.r24.INCUMBENT == result["REMAINING_GAP"] == 41979812


@pytest.mark.parametrize(
    "mutation",
    ["missing_alias", "wrong_pair_floor", "cap17", "sum_credit", "missing_state", "member_bound"],
)
def test_non_equivalent_stored_mathematical_mutations_rejected(
    result: dict[str, Any], mutation: str
) -> None:
    bad = copy.deepcopy(result)
    if mutation == "missing_alias":
        region = bad["REGIONS"][0]
        m = next(r for r in region["member_certificates"] if r["represented_vector_count"] == 2)
        m["represented_vectors"].pop()
        m["vector_certificates"].pop()
        m["represented_vector_count"] = 1
    elif mutation == "wrong_pair_floor":
        p = next(p for p in bad["R14_PROOF"]["pair_floors"] if p["types"] != [0, 0])
        p["minimum"] = cert.pair_floors()[0, 0][0]
        p["outside_slope"] = [574000, 1]
    elif mutation == "cap17":
        bad["R14_PROOF"]["multiplicity"]["cap"] = 17
    elif mutation == "sum_credit":
        row = bad["REGIONS"][0]["member_certificates"][0]["vector_certificates"][0]
        row["new_credit"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_bound"] - row["new_credit"]
    elif mutation == "missing_state":
        bad["FINAL_STATE_TERMS"].pop()
    else:
        row = bad["REGIONS"][0]["member_certificates"][0]
        row["member_new_bound"] -= 1
    assert cert.encode(bad) != cert.encode(result)
    with pytest.raises(AssertionError, match="complete exact joint"):
        cert.verify_result(bad)


def test_donor_tampering_rejected_after_warm_caches(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes
    donor_test = cert.REPO_ROOT / cert.DONOR_PATHS[1]

    def tampered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n# tampered\n" if path == donor_test else data

    monkeypatch.setattr(Path, "read_bytes", tampered)
    with pytest.raises(AssertionError, match="donor tampering"):
        cert.verify_result(result)


def test_live_sum_credit_mutation_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert result["R14_CORRECTION_FLOOR"] == 4903387

    def sum_credits(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    monkeypatch.setattr(cert.hunter, "combine_corrections", sum_credits)
    member = cert.target_members(cert.STATE_A)[0]
    with pytest.raises(AssertionError, match="MAX-only"):
        cert.certify_vector(member, cert.represented_vectors(cert.STATE_A)[member.counts][0])


def test_live_missing_alias_and_state_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = cert.STATE_A
    recovered = dict(cert.represented_vectors(sid))
    owner = next(
        k
        for k, vs in recovered.items()
        if len(vs) == 2 and k in {m.counts for m in cert.target_members(sid)}
    )
    recovered[owner] = recovered[owner][:1]
    original_vectors = cert.represented_vectors

    def incomplete_vectors(state_id: str) -> dict[cert.CountVector, tuple[cert.CountVector, ...]]:
        return recovered if state_id == sid else original_vectors(state_id)

    with monkeypatch.context() as patch:
        patch.setattr(cert, "represented_vectors", incomplete_vectors)
        with pytest.raises(AssertionError, match="target/alias"):
            cert.target_members(sid)
    sources = copy.deepcopy(cert.source_results())
    sources["TS53"]["FINAL_STATE_TERMS"].pop()
    monkeypatch.setattr(cert, "source_results", lambda: sources)
    with pytest.raises(AssertionError, match="23-State"):
        cert.recompute_family(result["REGIONS"])


def test_stored_byte_exact_fresh_equivalent_replay(result: dict[str, Any]) -> None:
    stored = cert.RESULT_PATH.read_bytes()
    assert stored == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
    assert cert.verify_result(cast(dict[str, Any], json.loads(stored)))["members"] == 89
