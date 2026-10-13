"""Independent finite counts, event oracles, scope guards and semantic mutations."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_sts13_pointed_pasch_certificate_r1 as x


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def independent_pasches(blocks: Sequence[x.Support]) -> dict[x.Support, tuple[x.Support, ...]]:
    found: dict[x.Support, tuple[x.Support, ...]] = {}
    for four in combinations(sorted(blocks), 4):
        counts = Counter(v for b in four for v in b)
        if sorted(counts.values()) == [2] * 6:
            key = tuple(sorted(counts))
            assert key not in found
            found[key] = four
    return found


def brute_local_weight(n: int, edges: set[x.Pair], triples: Sequence[x.Support]) -> int:
    """Independent seven-subset oracle over local labels, collapsing outside labels."""
    supports: list[x.Support] = list(triples)
    consumed = {p for b in triples for p in combinations(b, 2)}
    supports.extend(sorted(edges - consumed))
    for v in range(n):
        supports.extend([(v,)] * (6 - sum(v in s for s in supports)))
    masks = [sum(1 << v for v in s) for s in supports]
    total = 0
    for k in range(min(7, len(masks)) + 1):
        for selected in combinations(masks, k):
            hits = [sum(bool(m & (1 << v)) for m in selected) for v in range(n)]
            if min(hits) >= 3:
                total += comb(49 - len(masks), 7 - k)
    return 7 * total


def pointed_records(result: dict[str, object]) -> list[dict[str, object]]:
    return [x.object_row(r) for r in x.rows(result["POINTED_DELETIONS"])]


def blocks_from_json(value: object) -> tuple[x.Support, ...]:
    return tuple(tuple(x.integer(v) for v in x.rows(b)) for b in x.rows(value))


def assert_all_pointed(records: Sequence[dict[str, object]]) -> None:
    assert {(r["CLASS"], r["DELETED_POINT"]) for r in records} == {
        (c, p) for c in ("CYCLIC", "NON_CYCLIC") for p in range(13)
    }
    assert len(records) == 26
    observed: dict[str, Counter[int]] = {"CYCLIC": Counter(), "NON_CYCLIC": Counter()}
    for r in records:
        core = cast(Sequence[x.Support], r["CORE_BLOCKS"])
        found = independent_pasches(core)
        p = len(found)
        assert p == r["P"]
        assert tuple(sorted(found)) == tuple(cast(Sequence[x.Support], r["PASCH_SIX_SETS"]))
        assert [r[f"S{i}"] for i in range(4, 8)] == [331240, 6860, 7 * p, 0]
        assert r["EXACT_UNION"] == 313263916 - 7 * p
        observed[cast(str, r["CLASS"])][p] += 1
    assert observed == {"CYCLIC": Counter({7: 13}), "NON_CYCLIC": Counter({4: 9, 5: 4})}


def test_immutable_base_sources_and_isolated_module(authority: x.Authority) -> None:
    assert x.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    path = f"{x.RESULT_DIRECTORY}/{x.BASE_FILENAME}"
    assert hashlib.sha256((x.ROOT / path).read_bytes()).hexdigest() == x.BASE_RESULT_SHA256
    assert len(authority.provenance) == 56
    for relative, expected in authority.provenance.items():
        assert hashlib.sha256((x.ROOT / relative).read_bytes()).hexdigest() == expected
    assert not any("shared_neighbor" in p for p in authority.provenance)
    source = Path(x.__file__).read_text()
    assert "from ." not in source
    assert "ortools" not in source


def test_universal_graph_structure_and_open_wedge_identity() -> None:
    proof = x.structural_proof()
    assert proof["D"] == (5,) * 12 + (1,) * 6 + (0,) * 2
    assert proof["G"] == (11,) * 12 + (7,) * 6 + (6,) * 2
    assert [proof[k] for k in ("W", "T", "W_MINUS_3T")] == [816, 270, 6]
    assert proof["HIGH_LOW_EDGE_MAX"] == 3
    assert proof["EVEN_CROSSING_CANDIDATES"] == [0, 2]
    assert proof["REJECTED_H_M_OW_LOWER_BOUND"] == [[2, 1, 10]]
    assert proof["HIGH_TRIPLE_INCIDENCES"] == 60
    assert proof["HIGH_TRIPLE_COUNT"] == 20
    assert proof["UNCOVERED_HIGH_DEGREE"] == 1
    for row in cast(list[list[int]], proof["LOCAL_IDENTITY_TABLE"]):
        assert row[2] == 2 * row[1]


def test_published_representatives_and_distinct_classes(result: dict[str, object]) -> None:
    reps = x.representatives()
    cyclic = {
        tuple(sorted((v + s) % 13 for v in b)) for s in range(13) for b in ((0, 1, 4), (0, 2, 8))
    }
    assert set(reps["CYCLIC"]) == cyclic
    noncyclic = cyclic.difference([(2, 3, 6), (2, 4, 10), (3, 4, 7), (6, 7, 10)]).union(
        [(2, 3, 4), (2, 6, 10), (3, 6, 7), (4, 7, 10)]
    )
    assert set(reps["NON_CYCLIC"]) == noncyclic
    assert len(cyclic & noncyclic) == 22
    for name, blocks in reps.items():
        pairs = Counter(e for b in blocks for e in combinations(b, 2))
        assert len(blocks) == 26 and len(pairs) == 78 and set(pairs.values()) == {1}
        assert pairs.keys() == set(combinations(range(13), 2))
        assert Counter(v for b in blocks for v in b) == Counter({v: 6 for v in range(13)})
        expected = 13 if name == "CYCLIC" else 8
        assert len(independent_pasches(blocks)) == expected
    assert x.object_row(result["CLASSIFICATION_REFERENCE"])["PAGE"] == 247
    assert result["POINTED_DELETION_COUNT"] == 26
    assert result["P_UNIVERSAL_LOWER_BOUND"] == 4


def test_all_26_deletions_independent_counts_and_unique_completion(
    result: dict[str, object],
) -> None:
    records = pointed_records(result)
    assert_all_pointed(records)
    for r in records:
        core = cast(Sequence[x.Support], r["CORE_BLOCKS"])
        covered = {e for b in core for e in combinations(b, 2)}
        uncovered = tuple(sorted(set(combinations(range(12), 2)) - covered))
        assert len(core) == 20 and len(covered) == 60 and len(uncovered) == 6
        assert Counter(v for e in uncovered for v in e) == Counter({v: 1 for v in range(12)})
        complete, matching = x.complete_deleted(core)
        assert matching == uncovered
        assert {b for b in complete if 12 in b} == {(*e, 12) for e in uncovered}
        assert x.delete_point(complete, 12) == tuple(core)
        assert len(x.pasches(core, tuple(range(12)))) == len(independent_pasches(core))
        for point in range(13):
            reduced = tuple(b for b in complete if point not in b)
            assert len(reduced) == 20


@pytest.mark.parametrize(
    ("n", "triples", "expected"),
    [
        (4, (), 679),
        (4, ((0, 1, 2),), 448),
        (5, ((0, 1, 2),), 7),
        (5, ((0, 1, 2), (2, 3, 4)), 28),
        (6, ((0, 1, 2), (0, 3, 4), (1, 3, 5), (2, 4, 5)), 7),
    ],
)
def test_exact_local_event_weights_independent_seven_subset_oracle(
    n: int, triples: tuple[x.Support, ...], expected: int
) -> None:
    edges = set(combinations(range(n), 2))
    assert brute_local_weight(n, edges, triples) == expected
    assert x.intersection_count(x.local_profile(n, edges, triples)) == expected


def test_official_event_special_choices_and_partial_external_labels(
    result: dict[str, object],
) -> None:
    for main_hits in range(7):
        for bonus_hit in (False, True):
            official = main_hits >= 3 or (main_hits == 2 and bonus_hit)
            assert official == (main_hits + int(bonus_hit) >= 3)
    witness = x.object_row(result["INCUMBENT_WITNESS"])
    tickets = cast(Sequence[x.Support], witness["TICKETS"])
    triples = cast(Sequence[x.Support], witness["TRIPLE_SUPPORTS"])
    graph = {e for t in triples for e in combinations(t, 2)} | set(
        cast(Sequence[x.Pair], witness["PAIR_SUPPORTS"])
    )
    for q in ((0, 1, 2, 3), (0, 1, 12, 18), (12, 13, 14, 15, 18), (0, 1, 2, 4, 7, 9)):
        relabel = {v: i for i, v in enumerate(q)}
        edges = {
            (min(relabel[a], relabel[b]), max(relabel[a], relabel[b]))
            for a, b in graph
            if {a, b} <= set(q)
        }
        contained = tuple(tuple(sorted(relabel[v] for v in b)) for b in triples if set(b) <= set(q))
        masks = Counter(
            sum(1 << i for i, v in enumerate(q) if label in tickets[v]) for label in range(1, 50)
        )
        assert x.local_profile(len(q), edges, contained) == tuple(
            masks[m] for m in range(1 << len(q))
        )
    assert x.first_three_moments() == (372228640, 63838600, 5198256)


def test_universal_s4_s5_s6_s7_proof_and_once_only_pasches(result: dict[str, object]) -> None:
    proof = x.object_row(result["MOMENT_IDENTITY_PROOF"])
    assert [proof[k] for k in ("S4", "S5", "S6", "S7", "R_CAP")] == [331240, 6860, "7*P", 0, 7]
    assert 679 * (550 - 190) + 448 * 190 + 112 * 15 == 331240
    assert 7 * (480 + 18 + 2) + 28 * 120 == 6860
    assert proof["K12_FIVE_SET_COUNTS_0_1_2"] == [192, 480, 120]
    assert comb(12 - 7, 2) < 7 * (5 - 3)
    for row in cast(list[list[int]], proof["MIXED_COMPONENT_MIN_SELECTED_LABELS"]):
        assert row[2] > 7
    for r in range(8):
        assert sum((-1) ** (i + 1) * comb(r, i) for i in range(1, 8)) == int(r > 0)
    for record in pointed_records(result):
        assert len(set(cast(Sequence[x.Support], record["PASCH_SIX_SETS"]))) == record["P"]
        assert record["S6"] == 7 * x.integer(record["P"])
        assert record["S7"] == 0


def test_incumbent_twenty_tickets_and_49_labels(result: dict[str, object]) -> None:
    w = x.object_row(result["INCUMBENT_WITNESS"])
    tickets = cast(Sequence[x.Support], w["TICKETS"])
    triples = cast(Sequence[x.Support], w["TRIPLE_SUPPORTS"])
    pairs = cast(Sequence[x.Pair], w["PAIR_SUPPORTS"])
    assert len(tickets) == len(set(tickets)) == 20 and all(len(t) == 6 for t in tickets)
    frequencies = Counter(label for t in tickets for label in t)
    assert set(frequencies) == set(range(1, 50))
    assert Counter(frequencies.values()) == Counter({3: 22, 2: 27})
    assert len(triples) == 22 and len(pairs) == 27
    assert all(len(set(a) & set(b)) <= 1 for a, b in combinations(tickets, 2))
    reconstructed = tuple(
        tuple(v for v, t in enumerate(tickets) if label in t) for label in range(1, 50)
    )
    assert reconstructed == (*triples, *pairs)
    assert len(independent_pasches(triples[:20])) == w["P"] == 4
    assert [w[f"S{i}"] for i in range(1, 8)] == [372228640, 63838600, 5198256, 331240, 6860, 28, 0]
    assert w["EXACT_UNION"] == 313263888
    assert (
        w["SUPPORTS_SHA256"] == "25adbde983a4b339c631fe6d31d688ef34b182263d9252045b1b6b2d4ea94ddd"
    )


def test_ticket_permutations_and_low_triple_partitions_not_excluded(
    result: dict[str, object],
) -> None:
    w = x.object_row(result["INCUMBENT_WITNESS"])
    triples = cast(Sequence[x.Support], w["TRIPLE_SUPPORTS"])
    pairs = cast(Sequence[x.Pair], w["PAIR_SUPPORTS"])
    for permutation in (tuple(reversed(range(20))), tuple((7 * v + 3) % 20 for v in range(20))):
        t = tuple(tuple(sorted(permutation[v] for v in b)) for b in triples)
        p = tuple(
            (min(permutation[a], permutation[b]), max(permutation[a], permutation[b]))
            for a, b in pairs
        )
        observed = x.exact_moments(t, p)
        assert [observed[f"S{i}"] for i in range(1, 8)] == [w[f"S{i}"] for i in range(1, 8)]
        assert observed["EXACT_UNION"] == w["EXACT_UNION"]
    core = tuple(b for b in triples if max(b) < 12)
    graph = set(combinations(range(12), 2)) | (set(combinations(range(12, 20), 2)) - {(18, 19)})
    partitions: list[x.Support] = []
    for first in combinations(range(12, 18), 3):
        if 12 not in first:
            continue
        second = tuple(v for v in range(12, 18) if v not in first)
        t = (*core, first, second)
        p = tuple(sorted(graph - {e for b in t for e in combinations(b, 2)}))
        assert x.exact_moments(t, p)["EXACT_UNION"] == 313263888
        partitions.append(first)
    assert len(partitions) == 10


def assert_term_scope(authority: x.Authority) -> None:
    cert = x.profile_certificate(authority, 4)
    base_cert = x.object_row(x.object_row(authority.sealed["RESOLVED_CERTIFICATES"])[x.PROFILE])
    special = x.object_row(x.object_row(authority.sealed["SPECIAL_PER_T_CERTIFICATES"])[x.PROFILE])
    old = [tuple(x.integer(v) for v in x.rows(r)) for r in x.rows(special["ALL_T_TERMS"])]
    before = [
        (t, min(b, 372228640 - 63838600 + s3 - s4 + 6860), k, a, s4, s3)
        for t, b, k, a, s4, s3 in old
    ]
    after = cast(list[x.Term], cert["ALL_T_TERMS"])
    assert x.digest(before) == base_cert["ALL_T_TERMS_SHA256"]
    assert after[:-1] == before[:-1]
    assert after[-1] == (270, 313263888, 550, 190, 331240, 5198256)
    assert len(after) == 249 and max(t[1] for t in after[:-1]) == 313261872
    assert cert["CERTIFIED_PROFILE_BOUND"] == 313263888
    bad = list(after)
    t, b, k, a, s4, s3 = bad[0]
    bad[0] = (t, b - 1, k, a, s4, s3)
    with pytest.raises(AssertionError, match="misplaced t scope"):
        x.validate_term_scope(before, bad, 313263888)
    with pytest.raises(AssertionError, match="incomplete"):
        x.validate_term_scope(before, after[1:], 313263888)


def test_all_248_lower_t_terms_and_base_family_retained(
    authority: x.Authority, result: dict[str, object]
) -> None:
    assert_term_scope(authority)
    family = x.object_row(result["FAMILY_CERTIFICATE"])
    resolved = x.object_row(authority.sealed["RESOLVED_CERTIFICATES"])
    frontier = x.object_row(authority.sealed["FRONTIER_CERTIFICATES"])
    bounds = {
        p: x.integer(x.object_row(c)["CERTIFIED_PROFILE_BOUND"])
        for p, c in {**resolved, **frontier}.items()
    }
    assert len(bounds) == 4844
    assert max(bounds.values()) == 313283936
    bounds[x.PROFILE] = 313263888
    assert max(bounds.values()) == 313283936
    assert sorted(p for p, b in bounds.items() if b == max(bounds.values())) == [
        "66555555555540000000"
    ]
    assert family["OTHER_CERTIFICATES_SHA256"] == x.digest(
        {p: c for p, c in resolved.items() if p != x.PROFILE}
    )
    assert family["FRONTIER_CERTIFICATES_SHA256"] == x.digest(frontier)
    assert family["PRESERVED_OTHER_RESOLVED_COUNT"] == 4646
    assert family["PRESERVED_FRONTIER_COUNT"] == 197
    assert family["FRONTIER_BOUND"] == 313226448
    assert family["NEIGHBOR_DEFICIT_CERTIFICATES_INCLUDED"] is False
    assert (
        result["BASE_COMPLETE_FAMILY_UB"]
        == result["COMPLETE_FAMILY_UB_WITH_STS13_ONLY"]
        == 313283936
    )


@pytest.mark.parametrize("kind", ["tree", "source", "result"])
def test_immutable_input_tampering_rejected(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    path = x.ROOT / (
        f"{x.RESULT_DIRECTORY}/{x.BASE_FILENAME}"
        if kind == "result"
        else "src/lottolab/research/b649_k20_min_s2_all_resolved_cursor_refinement_r1.py"
    )
    original = Path.read_bytes

    def tampered(target: Path) -> bytes:
        return original(target) + (b" " if target == path else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        if kind == "tree":
            patch.setattr(x, "BASE_TREE", "0" * 40)
        else:
            patch.setattr(Path, "read_bytes", tampered)
        with pytest.raises(AssertionError, match="immutable"):
            x.load_authority()
    x.load_authority.cache_clear()


@pytest.mark.parametrize(
    "kind", ["omit_deletion", "pasch", "s6", "s7", "scope", "family", "witness"]
)
def test_result_mutations_rejected(
    kind: str, authority: x.Authority, result: dict[str, object]
) -> None:
    changed = x.object_row(json.loads(x.render(result)))
    if kind == "omit_deletion":
        x.rows(changed["POINTED_DELETIONS"]).pop()
    elif kind in ("pasch", "s6", "s7"):
        r = x.object_row(x.rows(changed["POINTED_DELETIONS"])[0])
        key = {"pasch": "P", "s6": "S6", "s7": "S7"}[kind]
        r[key] = x.integer(r[key]) + 1
    elif kind == "scope":
        cert = x.object_row(changed["PROFILE_CERTIFICATE"])
        t = x.rows(x.rows(cert["ALL_T_TERMS"])[0])
        t[1] = x.integer(t[1]) - 28
    elif kind == "family":
        changed["COMPLETE_FAMILY_UB_WITH_STS13_ONLY"] = 313263888
    else:
        x.object_row(changed["INCUMBENT_WITNESS"])["LABEL_COUNT"] = 48
    with pytest.raises(AssertionError, match="tampered"):
        x.verify_result(changed, authority)


MUTATIONS = {
    "omit_point_12": (
        "pointed_deletions",
        "for point in range(13):",
        "for point in range(12):",
        "pointed",
    ),
    "omit_noncyclic_class": (
        "pointed_deletions",
        "representatives().items():",
        "{'CYCLIC': representatives()['CYCLIC']}.items():",
        "pointed",
    ),
    "wrong_pasch_count": (
        "pasches",
        "sorted(by_points.items())",
        "sorted(by_points.items())[:-1]",
        "pointed",
    ),
    "wrong_s6_weight": ("exact_moments", "7 * len(configs), 0", "6 * len(configs), 0", "pointed"),
    "wrong_s7_weight": ("exact_moments", "7 * len(configs), 0", "7 * len(configs), 1", "pointed"),
    "wrong_official_special_weight": (
        "intersection_count",
        "return 7 * states.get",
        "return 6 * states.get",
        "weights",
    ),
    "pointed_max_instead_of_min": (
        "validate_pointed_coverage",
        "return min(integer(r",
        "return max(integer(r",
        "minimum",
    ),
    "wrong_pasch_bound_weight": (
        "profile_certificate",
        "bound = OLD_BOUND - 7 * p_min",
        "bound = OLD_BOUND - 8 * p_min",
        "scope",
    ),
    "apply_credit_at_t269": (
        "profile_certificate",
        "bound if t == CAP else b",
        "bound if t >= CAP - 1 else b",
        "scope",
    ),
    "drop_lower_t_terms": (
        "profile_certificate",
        "for t, b, k, a, s4, s3 in terms",
        "for t, b, k, a, s4, s3 in terms[-1:]",
        "scope",
    ),
    "remove_lower_t_scope_guard": ("validate_term_scope", "new[:-1] != old[:-1] or ", "", "scope"),
    "wrong_high_low_edge_budget": (
        "structural_proof",
        "crossing_max = 2 * ow //",
        "crossing_max = ow //",
        "structure",
    ),
    "fano_wrong_outside_pairs": (
        "moment_identity_proof",
        "comb(12 - 7, 2)",
        "comb(12 - 7, 3) + 5",
        "proof",
    ),
    "family_equals_sts13_bound": (
        "family_certificate",
        "after = max(bounds.values())",
        "after = new_bound",
        "family",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_non_equivalent_source_mutations_killed(
    name: str, authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    function, old, new, guard_name = MUTATIONS[name]
    original = cast(Callable[..., object], inspect.unwrap(getattr(x, function)))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(old, new), f"<semantic-mutation:{name}>", "exec"), namespace)

    def guard() -> None:
        if guard_name == "pointed":
            assert_all_pointed(x.pointed_deletions())
        elif guard_name == "weights":
            assert (
                x.intersection_count(x.local_profile(4, set(combinations(range(4), 2)), ())) == 679
            )
        elif guard_name == "minimum":
            assert x.validate_pointed_coverage(x.pointed_deletions()) == 4
        elif guard_name == "scope":
            assert_term_scope(authority)
        elif guard_name == "structure":
            assert x.structural_proof()["HIGH_LOW_EDGE_MAX"] == 3
        elif guard_name == "proof":
            x.moment_identity_proof()
        elif guard_name == "family":
            assert (
                x.family_certificate(authority, 313263888)["COMPLETE_FAMILY_UB_WITH_STS13_ONLY"]
                == 313283936
            )
        else:
            pytest.fail("unknown mutation guard")

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(x, function, namespace[function])
        with pytest.raises((AssertionError, ValueError, pytest.fail.Exception)):
            guard()
    guard()


def test_result_verify_and_exact_byte_replay(
    authority: x.Authority, result: dict[str, object]
) -> None:
    raw = x.RESULT_PATH.read_bytes()
    assert raw == x.render(result)
    assert json.loads(raw) == json.loads(x.render(result))
    x.verify_result(result, authority)
    run = subprocess.run(
        [sys.executable, "-m", x.__name__, "--verify"],
        cwd=x.ROOT,
        env={**os.environ, "PYTHONPATH": str(x.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    output = x.object_row(json.loads(run.stdout))
    assert output["RESULT_REPLAY_STATUS"] == "PASS"
    assert output["STS13_PROFILE_BOUND"] == 313263888
    assert output["COMPLETE_FAMILY_UB_WITH_STS13_ONLY"] == 313283936
