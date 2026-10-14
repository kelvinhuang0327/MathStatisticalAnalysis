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

from lottolab.research import b649_k20_r3_post_r14_ts_61_member_two_state_certificate_r1 as cert

A, B = cert.STATE_13169800, cert.STATE_12695020
type Rows = list[list[int]]


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor rebuild, census, heavy solver or chase")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module in (cert.joint, cert.ts53, cert.h11, cert.prior, cert.prior.h0):
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


def test_exact_base_authority_and_donor_bytes(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert result["SOURCE_AUTHORITY"] == authority
    assert (authority["HEAD"], authority["TREE"]) == (
        "935a582edfefa8b4405c34499e7f30daa9d24e22",
        "dd9e1e52ef7da0eab21157af5df587efb04a644e",
    )
    base = cert.git_bytes("show", f"{cert.BASE_HEAD}:{cert.joint.RESULT_RELATIVE}")
    assert sha256(base).hexdigest() == authority["RESULT_SHA256"]
    assert authority["RESULT_SHA256"] == (
        "300044f832661c5fd43d06c5c458c2450984351b643498eb4e0d3e79058d8a0c"
    )
    assert (cert.REPO_ROOT / cert.joint.RESULT_RELATIVE).read_bytes() == base
    paths = set(authority["donor_sha256"])
    assert paths == set(cert.source_paths())
    for module in (cert.joint, cert.ts53, cert.h11, cert.prior, cert.prior.h0):
        assert module.RESULT_RELATIVE in paths
        source = Path(inspect.getfile(module)).resolve()
        assert str(source.relative_to(cert.REPO_ROOT)) in paths
    for relative, digest in authority["donor_sha256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == digest
    assert result["LEDGER_AUTHORITY"] == {
        A: cert.joint.RESULT_RELATIVE,
        B: cert.prior.RESULT_RELATIVE,
    }
    sealed = json.loads((cert.REPO_ROOT / cert.joint.RESULT_RELATIVE).read_bytes())
    assert sealed["FINAL_COMPLETE_R3_UB"] == result["START_COMPLETE_R3_UB"] == 355243700


def test_derived_cutoff_complete_regions_targets_and_eight_aliases(
    result: dict[str, Any],
) -> None:
    sealed = json.loads((cert.REPO_ROOT / cert.joint.RESULT_RELATIVE).read_bytes())
    others = [r["bound"] for r in sealed["FINAL_STATE_TERMS"] if r["stable_id"] not in (A, B)]
    classified = cert.prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    cutoff = max(*others, *(r["bound"] for r in classified), sealed["TAIL_BOUND"])
    assert len(others) == 21 and cutoff == result["TARGET_CUTOFF"] == 355235139
    expected = {A: (989, 1072, 3, 3, 0, 986, 1069), B: (1222, 1325, 58, 66, 8, 1164, 1259)}
    for region in result["REGIONS"]:
        sid = region["state_id"]
        members, recovered = cert.region_members(sid), cert.represented_vectors(sid)
        mc, vc, tc, tv, compressed, pc, pv = expected[sid]
        assert region["region_sha256"] == cert.REGION_SPECS[sid][0]
        assert (region["region_member_count"], region["region_vector_count"]) == (mc, vc)
        assert len({v for vs in recovered.values() for v in vs}) == vc
        targets = [m for m in members if m.final_bound > cutoff]
        assert [r["member_id"] for r in region["member_certificates"]] == [
            cert.member_id(m.counts) for m in targets
        ]
        assert (len(targets), sum(len(recovered[m.counts]) for m in targets)) == (tc, tv)
        assert sum(len(recovered[m.counts]) > 1 for m in targets) == compressed
        assert (region["preserved_member_count"], region["preserved_vector_count"]) == (pc, pv)
    a_ids = [r["witness_counts"] for r in result["REGIONS"][0]["member_certificates"]]
    assert a_ids == [
        [[0, 15], [4, 2], [25, 1]],
        [[0, 15], [1, 1], [4, 1], [25, 1]],
        [[0, 15], [1, 2], [25, 1]],
    ]
    # Independent signature grouping of all 66 target vectors of State12695020.
    grouped: dict[str, list[cert.CountVector]] = {}
    targets_b = cert.target_members(B)
    for member in targets_b:
        for v in cert.represented_vectors(B)[member.counts]:
            state = cert.catalog.rebuild_member(
                cert.replace(member, counts=v, represented_vector_count=1)
            )
            assert cert.hunter.r14.raw_bound(state) == member.raw_bound
            grouped.setdefault(repr(cert.hunter.eleven.compression_signature(state)), []).append(v)
    assert len(grouped) == 58 and sum(len(vs) for vs in grouped.values()) == 66
    aliases = sorted(tuple(sorted(vs)) for vs in grouped.values() if len(vs) > 1)

    def p(j: int, a: int, b: int) -> cert.CountVector:
        return vector({0: 10, 1: j, 4: 6 - j, a: 1, b: 1})

    independent = sorted(
        tuple(sorted(pair))
        for pair in (*((p(j, 9, 17), p(j, 6, 19)) for j in range(7)), (p(2, 6, 17), p(4, 9, 19)))
    )
    assert aliases == independent == [tuple(a) for a in cert.expected_aliases(B)]
    assert result["COMPRESSED_TARGET_COUNT"] == 8
    stored = result["REGIONS"][1]["compression_aliases"]
    assert [[cert.dense(v) for v in pair] for pair in stored] == [list(a) for a in independent]
    assert (result["TARGET_MEMBER_COUNT"], result["TARGET_VECTOR_COUNT"]) == (61, 69)


def test_selected_subsets_complete_pair_rows_and_type_applicability(
    result: dict[str, Any],
) -> None:
    by_id = proofs(result)
    used: set[str] = set()
    for sid, _record, row in vector_rows(result):
        v, u = cert.dense(row["counts"]), cert.dense(row["selected_subset_counts"])
        assert all(0 <= a <= b for a, b in zip(u, v, strict=True))
        assert 2 <= sum(u) <= 18 and sum(u) in (17, 18)
        assert row["deleted_event_types"] == [i for i in range(30) for _ in range(v[i] - u[i])]
        if sid == A:
            assert row["deleted_event_types"] == [25] and v[25] == 1
        assert row["proof_id"] == cert.digest(u)
        used.add(row["proof_id"])
    assert used == set(by_id) and len(by_id) == 57
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


def test_hunter_threshold_minimum_independent(result: dict[str, Any]) -> None:
    seen: dict[tuple[tuple[int, ...], int, int], int] = {}
    for proof in proofs(result).values():
        phi, q, n = tuple(proof["pair_floors"]), proof["collision_mass_floor"], proof["event_count"]
        key = (phi, q, n)
        if key not in seen:
            seen[key] = min(
                (n - 1) * phi[0]
                + (phi[1] - phi[0]) * a
                + (phi[2] - phi[1]) * b
                + (phi[3] - phi[2]) * c
                for a in range(n)
                for b in range(a + 1)
                for c in range(b + 1)
                if comb(a + 1, 2) + comb(b + 1, 2) + comb(c + 1, 2) >= q
            )
        assert proof["hunter_floor"] == seen[key]
        e = proof["integer_minimizer"]["edge_counts"]
        assert e[0] >= e[1] >= e[2] >= 0 and sum(e) >= q and e[0] <= comb(n, 2)
        assert proof["integer_minimizer"]["rank_floors"] == [rank(x) for x in e]
    # Complete edge-triple enumeration for every bound that determines a cohort maximum.
    decisive = {
        cert.digest(cert.dense(row["selected_subset_counts"]))
        for _sid, record, row in vector_rows(result)
        if row["vector_new_bound"] == record["member_new_bound"]
        and record["member_new_bound"] in (354044236, 352913883)
    }
    # Two State13169800 subsets plus six full State12695020 vectors.
    assert len(decisive) == 8
    for proof_id in decisive:
        proof = proofs(result)[proof_id]
        phi, q, n = proof["pair_floors"], proof["collision_mass_floor"], proof["event_count"]
        ranks = [rank(x) for x in range(comb(n, 2) + 1)]
        best = min(
            (n - 1) * phi[0]
            + (phi[1] - phi[0]) * ranks[e1]
            + (phi[2] - phi[1]) * ranks[e2]
            + (phi[3] - phi[2]) * ranks[e3]
            for e1 in range(comb(n, 2) + 1)
            for e2 in range(e1 + 1)
            for e3 in range(max(0, q - e1 - e2), e2 + 1)
        )
        assert best == proof["hunter_floor"]
    a_floors = sorted(
        proofs(result)[row["proof_id"]]["hunter_floor"]
        for sid, _record, row in vector_rows(result)
        if sid == A
    )
    assert a_floors == [7513464, 7513464, 7716968]


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
    v = cert.dense(vector_rows(result)[0][2]["counts"])
    u = cert.ts53.select_subset(v)
    original = cert.prior.verified_pair_rows

    def negative(pair: tuple[int, int]) -> tuple[tuple[int, ...], ...]:
        rows = original(pair)
        return (*rows, (*rows[0][:6], -1))

    monkeypatch.setattr(cert.prior, "verified_pair_rows", negative)
    with pytest.raises(AssertionError, match="negative intersection"):
        cert.tree_extension_proof(v, u)


def test_max_once_credits_preserved_and_compressed_max(result: dict[str, Any]) -> None:
    for sid, record, row in vector_rows(result):
        credits = row["corrections"]
        unc = row["uncorrected_anchor_bound"]
        assert set(credits) == {
            "R6_PAIR",
            "FOREST",
            "SEALED_MEMBER",
            "SEALED_VECTOR",
            "SUBSET_HUNTER",
        }
        assert row["combined_correction"] == max(credits.values()) == credits["SUBSET_HUNTER"]
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
        if sid == A:
            assert credits["FOREST"] == 6314000 and unc == 361557700
            assert any("type0-ge9" in source for source, _ in row["sealed_vector_bounds"])
        assert row["vector_new_bound"] < record["member_prior_bound"]
    distinct = 0
    for region in result["REGIONS"]:
        for record in region["member_certificates"]:
            bounds = [r["vector_new_bound"] for r in record["vector_certificates"]]
            assert record["member_new_bound"] == max(bounds)
            distinct += len(set(bounds)) > 1
    assert distinct > 0
    assert [r["member_new_bound"] for r in result["REGIONS"][0]["member_certificates"]] == [
        354044236,
        353840732,
        354044236,
    ]


def test_live_sum_credit_and_compressed_min_mutations_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    member = next(m for m in cert.target_members(B) if m.represented_vector_count == 2)
    vectors = cert.represented_vectors(B)[member.counts]
    rows = [cert.certify_vector(B, member, v) for v in vectors]
    assert rows[0]["vector_new_bound"] != rows[1]["vector_new_bound"]

    def fixture_vector(_sid: str, _member: cert.LedgerMember, v: cert.CountVector) -> Any:
        return rows[vectors.index(v)]

    with monkeypatch.context() as patch:
        patch.setattr(cert, "certify_vector", fixture_vector)
        source = inspect.getsource(cert.certify_member)
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
        mutant = cast(
            Callable[[str, cert.LedgerMember], dict[str, Any]], namespace["certify_member"]
        )
        honest = cert.certify_member(B, member)["member_new_bound"]
        assert honest == max(r["vector_new_bound"] for r in rows)
        assert mutant(B, member)["member_new_bound"] < honest

    def sum_credits(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    monkeypatch.setattr(cert.hunter, "combine_corrections", sum_credits)
    with pytest.raises(AssertionError, match="MAX-only"):
        cert.certify_vector(B, member, vectors[0])
    assert result["CORRECTION_COMBINATION"].startswith("MAX(")


def test_untouched_bounds_new_state_bounds_and_witnesses(result: dict[str, Any]) -> None:
    expected = {
        A: (354044236, 355176136, 355176136),
        B: (352913883, 355213740, 355213740),
    }
    for region in result["REGIONS"]:
        sid = region["state_id"]
        members = cert.region_members(sid)
        changed = {cert.dense(r["witness_counts"]) for r in region["member_certificates"]}
        rows = region["complete_region_members"]
        assert [cert.dense(r["witness_counts"]) for r in rows] == [m.counts for m in members]
        for m, row in zip(members, rows, strict=True):
            assert row["prior_bound"] == m.final_bound
            if m.counts in changed:
                assert row["final_bound"] < m.final_bound
            else:
                assert row["final_bound"] == m.final_bound
        preserved = tuple(m for m in members if m.counts not in changed)
        assert (
            cert.digest(tuple((m.counts, m.final_bound) for m in preserved))
            == region["preserved_bounds_sha256"]
        )
        cohort, remainder, state = expected[sid]
        assert region["target_cohort_max"] == cohort
        assert (
            region["preserved_remainder_max"] == max(m.final_bound for m in preserved) == remainder
        )
        assert region["new_state_bound"] == max(r["final_bound"] for r in rows) == state
    assert result["NEW_STATE_13169800_UB"] == 355176136
    assert result["NEW_STATE_12695020_UB"] == 355213740
    assert len(result["REGIONS"][0]["new_state_member_ids"]) == 10
    carried = cert.joint.carried_supports()
    for _sid, _record, row in vector_rows(result):
        v = cert.dense(row["counts"])
        support = tuple(tuple(t) for t in row["witness_analysis"]["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(v, support)
        assert cert.digest(support) == row["witness_analysis"]["support_sha256"]
        for other in carried.get(v, ()):
            assert cert.hunter.r8.validate_support_assignment(v, other)
    r14 = {v for sid in cert.joint.REGION_SPECS for v in cert.joint.target_parameters(sid)}
    assert len(r14) == 99 and result["R14_TARGET_OVERLAP"] == 0
    assert not r14 & {cert.dense(row["counts"]) for _, _, row in vector_rows(result)}


def test_full_family_all_23_states_classified_and_tail(result: dict[str, Any]) -> None:
    states = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    start = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    sealed = json.loads((cert.REPO_ROOT / cert.joint.RESULT_RELATIVE).read_bytes())
    assert start == {r["stable_id"]: r["bound"] for r in sealed["FINAL_STATE_TERMS"]}
    assert len(states) == len(start) == 23
    assert {k for k in states if states[k] != start[k]} == {A, B}
    assert states[A] == 355176136 and states[B] == 355213740
    assert states[cert.OWNER_STATE] == 355235139
    assert states[cert.ts53.TARGET_STATE_ID] == 355116818
    classified = [
        (r["stable_id"], r["bound"])
        for r in cert.prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    ]
    assert len(classified) == len(dict(classified)) == result["CLASSIFIED_TERM_COUNT"] == 56550
    assert cert.digest(tuple(classified)) == result["CLASSIFIED_TERMS_SHA256"]
    assert result["CLASSIFIED_TERMS_SHA256"] == sealed["CLASSIFIED_TERMS_SHA256"]
    assert max(b for _, b in classified) == result["CLASSIFIED_MAX"] == 355145504
    tail = cert.six.sealed_tail_bound()
    assert tail == result["TAIL_BOUND"] == sealed["TAIL_BOUND"] == 354039277
    terms = [*states.items(), *classified, (cert.r24.TAIL_ID, tail)]
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355235139
    assert result["FINAL_OWNER_IDS"] == [k for k, b in terms if b == maximum] == [cert.OWNER_STATE]
    assert result["RUNNER_UP"] == {
        "bound": runner,
        "owner_ids": [k for k, b in terms if b == runner],
    }
    assert runner == 355213740 and result["RUNNER_UP"]["owner_ids"] == [B]
    assert result["START_COMPLETE_R3_UB"] - maximum == result["STRICT_GAIN"] == 8561
    assert maximum - cert.r24.INCUMBENT == result["REMAINING_GAP"] == 41971251


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_vector",
        "wrong_subset",
        "wrong_pair_floor",
        "over_tight_collision",
        "sum_credit",
        "missing_family_term",
        "member_bound",
    ],
)
def test_non_equivalent_stored_mathematical_mutations_rejected(
    result: dict[str, Any], mutation: str
) -> None:
    bad = copy.deepcopy(result)
    region = bad["REGIONS"][1]
    if mutation == "missing_vector":
        m = next(r for r in region["member_certificates"] if r["represented_vector_count"] == 2)
        m["represented_vectors"].pop()
        m["vector_certificates"].pop()
        m["represented_vector_count"] = 1
    elif mutation == "wrong_subset":
        row = region["member_certificates"][0]["vector_certificates"][0]
        row["selected_subset_counts"] = row["counts"]
    elif mutation == "wrong_pair_floor":
        proof = next(p for p in bad["SUBSET_PROOFS"] if p["pair_floors"][0] < p["pair_floors"][1])
        proof["pair_floors"][0] = proof["pair_floors"][1]
    elif mutation == "over_tight_collision":
        bad["SUBSET_PROOFS"][0]["collision_mass_floor"] += 1
    elif mutation == "sum_credit":
        row = region["member_certificates"][0]["vector_certificates"][0]
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "missing_family_term":
        bad["FINAL_STATE_TERMS"].pop()
    else:
        bad["REGIONS"][0]["member_certificates"][0]["member_new_bound"] -= 1
    assert cert.encode(bad) != cert.encode(result)
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


def test_live_missing_vector_illegal_subset_and_family_term_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    recovered = dict(cert.represented_vectors(B))
    owner = next(m.counts for m in cert.target_members(B) if m.represented_vector_count == 2)
    recovered[owner] = recovered[owner][:1]
    original = cert.represented_vectors

    def incomplete(state_id: str) -> dict[cert.CountVector, tuple[cert.CountVector, ...]]:
        return recovered if state_id == B else original(state_id)

    with monkeypatch.context() as patch:
        patch.setattr(cert, "represented_vectors", incomplete)
        with pytest.raises(AssertionError, match="alias coverage"):
            cert.target_members(B)
    v = cert.dense(result["REGIONS"][0]["member_certificates"][0]["witness_counts"])
    for u in (
        tuple(c + int(i == 1) for i, c in enumerate(v)),
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
        "members": 61,
        "vectors": 69,
        "state_terms": 23,
        "classified_terms": 56550,
        "complete_r3": 355235139,
    }
    assert cert.verify_result(cast(dict[str, Any], json.loads(stored)))["vectors"] == 69
